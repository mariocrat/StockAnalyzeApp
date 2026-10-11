"""Test-only insertion of old/corrupt rows for ownership and legacy read tests.

These fixtures deliberately bypass the production ApprovedHistoryWrite writer.
They require H4-owned synthetic storage and are never imported by production.
"""

from tests.storage_fixture import require_storage_boundary

require_storage_boundary()


def add_legacy_history_fixture(
    history, *, user_id, review_type, ticker="", name="", trade_date="", target_trade_id=None,
    trade_snapshot=None, recent_trades_snapshot=None, chart_snapshot=None,
    ai_review=None, access_snapshot=None, model="", source="",
):
    require_storage_boundary()
    connection = history._connect()
    try:
        cursor = connection.execute(
            """INSERT INTO review_history (
                user_id, review_type, ticker, name, trade_date, target_trade_id,
                trade_snapshot_json, recent_trades_snapshot_json, chart_snapshot_json,
                ai_review_json, access_snapshot_json, model, source, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (str(user_id), "advanced" if review_type == "advanced" else "basic",
             str(ticker or ""), str(name or ""), str(trade_date or ""), target_trade_id,
             history._json_dumps(trade_snapshot),
             history._json_dumps(recent_trades_snapshot if recent_trades_snapshot is not None else []),
             history._json_dumps(chart_snapshot), history._json_dumps(ai_review),
             history._json_dumps(access_snapshot), str(model or ""), str(source or ""), history._now()),
        )
        connection.commit()
        return history.get_review_history(cursor.lastrowid, user_id=user_id)
    finally:
        connection.close()
