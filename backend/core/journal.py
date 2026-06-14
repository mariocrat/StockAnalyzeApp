import datetime
import sqlite3
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DB_PATH = DATA_DIR / "trades.sqlite3"


def _connect():
    DATA_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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

    ticker = str(payload.get("ticker", "") or "").strip()
    price = float(payload.get("price", 0) or 0)
    quantity = float(payload.get("quantity", 0) or 0)
    if price <= 0 or quantity <= 0:
        raise ValueError("price and quantity must be positive")

    return {
        "trade_date": trade_date,
        "ticker": ticker,
        "name": name,
        "side": side,
        "price": price,
        "quantity": quantity,
        "fee": float(payload.get("fee", 0) or 0),
        "tax": float(payload.get("tax", 0) or 0),
        "memo": str(payload.get("memo", "") or "").strip(),
        "source": str(payload.get("source", "manual") or "manual").strip(),
    }


def add_trade(payload: dict) -> dict:
    trade = normalize_trade(payload)
    now = datetime.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO trades
            (trade_date, ticker, name, side, price, quantity, fee, tax, memo, source, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                trade["trade_date"], trade["ticker"], trade["name"], trade["side"],
                trade["price"], trade["quantity"], trade["fee"], trade["tax"],
                trade["memo"], trade["source"], now,
            ),
        )
        conn.commit()
        trade["id"] = cur.lastrowid
        trade["created_at"] = now
    return trade


def list_trades(limit: int = 500) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM trades
            ORDER BY trade_date DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def delete_trade(trade_id: int):
    with _connect() as conn:
        conn.execute("DELETE FROM trades WHERE id = ?", (trade_id,))
        conn.commit()


def clear_trades():
    with _connect() as conn:
        conn.execute("DELETE FROM trades")
        conn.commit()


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
