import datetime
import math
import os
import sqlite3
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DB_PATH = DATA_DIR / "trades.sqlite3"


def _env_value(name: str) -> str:
    value = os.environ.get(name)
    if value:
        return value.strip()
    roots = [
        Path(__file__).resolve().parents[2] / ".env",
        Path(__file__).resolve().parents[1] / ".env",
    ]
    for path in roots:
        try:
            if not path.exists():
                continue
            for line in path.read_text(encoding="utf-8").splitlines():
                raw = line.strip()
                if not raw or raw.startswith("#") or "=" not in raw:
                    continue
                key, val = raw.split("=", 1)
                if key.strip() == name:
                    return val.strip().strip("\"'")
        except Exception:
            continue
    return ""


def _db_path() -> Path:
    configured = _env_value("ALPHAMATE_JOURNAL_DB_PATH")
    if configured:
        return Path(configured)
    return DB_PATH


def _ensure_column(conn, table: str, column: str, definition: str):
    columns = [row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _connect():
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL DEFAULT '',
            trade_date TEXT NOT NULL,
            ticker TEXT,
            name TEXT NOT NULL,
            side TEXT NOT NULL CHECK(side IN ('buy', 'sell')),
            price REAL NOT NULL,
            quantity REAL NOT NULL,
            fee REAL DEFAULT 0,
            tax REAL DEFAULT 0,
            memo TEXT DEFAULT '',
            source TEXT DEFAULT 'manual',
            created_at TEXT NOT NULL
        )
        """
    )
    _ensure_column(conn, "trades", "user_id", "TEXT NOT NULL DEFAULT ''")
    return conn


def normalize_trade(payload: dict) -> dict:
    side = str(payload.get("side", "")).strip().lower()
    if side in ("매수", "buy", "b"):
        side = "buy"
    elif side in ("매도", "sell", "s"):
        side = "sell"
    else:
        raise ValueError("side must be buy or sell")

    trade_date = str(payload.get("trade_date", "")).strip()
    name = str(payload.get("name", "")).strip()
    if not trade_date or not name:
        raise ValueError("trade_date and name are required")
    try:
        datetime.datetime.fromisoformat(trade_date.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("trade_date must be ISO date or datetime") from exc

    ticker = str(payload.get("ticker", "") or "").strip()
    price = float(payload.get("price", 0) or 0)
    quantity = float(payload.get("quantity", 0) or 0)
    if not math.isfinite(price) or not math.isfinite(quantity):
        raise ValueError("price and quantity must be finite")
    if price <= 0 or quantity <= 0:
        raise ValueError("price and quantity must be positive")
    fee = float(payload.get("fee", 0) or 0)
    tax = float(payload.get("tax", 0) or 0)
    if not math.isfinite(fee) or not math.isfinite(tax):
        raise ValueError("fee and tax must be finite")
    if fee < 0 or tax < 0:
        raise ValueError("fee and tax must be non-negative")

    return {
        "trade_date": trade_date,
        "ticker": ticker,
        "name": name,
        "side": side,
        "price": price,
        "quantity": quantity,
        "fee": fee,
        "tax": tax,
        "memo": str(payload.get("memo", "") or "").strip(),
        "source": str(payload.get("source", "manual") or "manual").strip(),
    }


def add_trade(payload: dict, user_id: str = "") -> dict:
    trade = normalize_trade(payload)
    now = datetime.datetime.now().isoformat(timespec="seconds")
    conn = _connect()
    try:
        cur = conn.execute(
            """
            INSERT INTO trades
            (user_id, trade_date, ticker, name, side, price, quantity, fee, tax, memo, source, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(user_id or ""),
                trade["trade_date"], trade["ticker"], trade["name"], trade["side"],
                trade["price"], trade["quantity"], trade["fee"], trade["tax"],
                trade["memo"], trade["source"], now,
            ),
        )
        conn.commit()
        trade["id"] = cur.lastrowid
        trade["user_id"] = str(user_id or "")
        trade["created_at"] = now
    finally:
        conn.close()
    return trade


def list_trades(limit: int = 500, user_id: str | None = None) -> list[dict]:
    conn = _connect()
    try:
        if user_id is not None:
            rows = conn.execute(
                """
                SELECT * FROM trades
                WHERE user_id = ?
                ORDER BY trade_date DESC, id DESC
                LIMIT ?
                """,
                (str(user_id or ""), limit),
            ).fetchall()
            return [dict(row) for row in rows]
        rows = conn.execute(
            """
            SELECT * FROM trades
            ORDER BY trade_date DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def count_trades(user_id: str | None = None) -> int:
    conn = _connect()
    try:
        if user_id is None:
            row = conn.execute("SELECT COUNT(*) AS count FROM trades").fetchone()
        else:
            row = conn.execute(
                "SELECT COUNT(*) AS count FROM trades WHERE user_id = ?",
                (str(user_id or ""),),
            ).fetchone()
        return int(row["count"] if row else 0)
    finally:
        conn.close()


def delete_trade(trade_id: int, user_id: str | None = None):
    conn = _connect()
    try:
        if user_id is None:
            cur = conn.execute("DELETE FROM trades WHERE id = ?", (trade_id,))
        else:
            cur = conn.execute("DELETE FROM trades WHERE id = ? AND user_id = ?", (trade_id, str(user_id or "")))
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def clear_trades(user_id: str | None = None):
    conn = _connect()
    try:
        if user_id is None:
            cur = conn.execute("DELETE FROM trades")
        else:
            cur = conn.execute("DELETE FROM trades WHERE user_id = ?", (str(user_id or ""),))
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def build_review(trades: list[dict] | None = None) -> dict:
    trades = trades if trades is not None else list_trades(limit=5000)
    ordered = sorted(trades, key=lambda row: (row.get("trade_date", ""), row.get("id", 0)))
    if not ordered:
        return {
            "summary": {
                "trade_count": 0,
                "realized_pnl": 0,
                "realized_return_pct": 0,
                "win_rate_pct": 0,
            },
            "by_symbol": [],
            "advice": ["매매 내역을 가져오면 평균 매수가, 실현손익, 반복 패턴을 계산합니다."],
        }

    positions = {}
    realized_pnl = 0.0
    realized_cost = 0.0
    wins = 0
    closed_count = 0
    by_symbol = {}

    for trade in ordered:
        key = trade.get("ticker") or trade.get("name")
        side = trade["side"]
        qty = float(trade["quantity"])
        price = float(trade["price"])
        fee_tax = float(trade.get("fee") or 0) + float(trade.get("tax") or 0)
        position = positions.setdefault(key, {"qty": 0.0, "cost": 0.0})
        symbol = by_symbol.setdefault(key, {
            "ticker": trade.get("ticker", ""),
            "name": trade.get("name", key),
            "buy_amount": 0.0,
            "sell_amount": 0.0,
            "realized_pnl": 0.0,
            "open_quantity": 0.0,
        })

        if side == "buy":
            amount = price * qty + fee_tax
            position["qty"] += qty
            position["cost"] += amount
            symbol["buy_amount"] += amount
        else:
            sell_amount = price * qty - fee_tax
            avg_cost = position["cost"] / position["qty"] if position["qty"] > 0 else 0
            matched_qty = min(qty, position["qty"]) if position["qty"] > 0 else qty
            matched_cost = avg_cost * matched_qty
            pnl = sell_amount - matched_cost
            realized_pnl += pnl
            realized_cost += matched_cost
            symbol["sell_amount"] += sell_amount
            symbol["realized_pnl"] += pnl
            closed_count += 1
            if pnl > 0:
                wins += 1
            if position["qty"] > 0:
                position["qty"] -= matched_qty
                position["cost"] -= matched_cost

    for key, position in positions.items():
        if key in by_symbol:
            by_symbol[key]["open_quantity"] = round(position["qty"], 4)
            buy_amount = by_symbol[key]["buy_amount"]
            pnl = by_symbol[key]["realized_pnl"]
            by_symbol[key]["realized_return_pct"] = round((pnl / buy_amount) * 100, 2) if buy_amount else 0
            by_symbol[key]["realized_pnl"] = round(pnl, 0)
            by_symbol[key]["buy_amount"] = round(buy_amount, 0)
            by_symbol[key]["sell_amount"] = round(by_symbol[key]["sell_amount"], 0)

    symbol_rows = sorted(by_symbol.values(), key=lambda row: row["realized_pnl"], reverse=True)
    ret_pct = (realized_pnl / realized_cost) * 100 if realized_cost else 0
    win_rate = (wins / closed_count) * 100 if closed_count else 0

    advice = []
    if closed_count == 0:
        advice.append("아직 매도 기록이 없어 실현 손익보다 보유 포지션 관리가 핵심입니다.")
    elif ret_pct < 0:
        advice.append("전체 실현 손익이 마이너스입니다. 진입 이유와 손절 기준을 기록해 반복 손실 구간을 먼저 찾으세요.")
    else:
        advice.append("전체 실현 손익은 플러스입니다. 수익 매매의 진입 조건을 따로 모아 재현 가능한 규칙으로 정리하세요.")
    if win_rate and win_rate < 45:
        advice.append("승률이 낮은 편입니다. 한 번의 손실 크기가 커지지 않도록 분할 진입보다 손절 조건을 먼저 고정하는 편이 좋습니다.")
    elif win_rate >= 60:
        advice.append("승률은 양호합니다. 다음 단계는 수익 매매를 더 오래 끌고 손실 매매를 짧게 끊는 비율 관리입니다.")
    if any(row["open_quantity"] > 0 for row in symbol_rows):
        advice.append("아직 미청산 수량이 있는 종목이 있습니다. 복기 화면에서는 실현 손익과 보유 리스크를 분리해서 보세요.")

    return {
        "summary": {
            "trade_count": len(ordered),
            "closed_count": closed_count,
            "realized_pnl": round(realized_pnl, 0),
            "realized_return_pct": round(ret_pct, 2),
            "win_rate_pct": round(win_rate, 1),
        },
        "by_symbol": symbol_rows,
        "advice": advice,
    }
