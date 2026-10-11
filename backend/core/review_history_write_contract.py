"""Pure access admission for a new history write, independent of legacy/cache.

This module is deliberately not connected to production writers. It validates
only access and the two scalar review coordinates. It never repairs, copies,
normalizes, authenticates, reads configuration/storage or consults a clock.
"""

from datetime import date, datetime, timedelta
import re


class HistoryWriteContractError(ValueError):
    """An access snapshot is outside the supported new-history contract."""


_MAX_SAFE_INTEGER = 2**53 - 1
_BASIC = dict.fromkeys((
    "signup_remaining", "free_daily_remaining", "free_daily_max_remaining", "free_available_now",
    "rewarded_ad_available", "rewarded_ad_daily_remaining", "free_monthly_remaining",
    "free_monthly_limit", "pro_monthly_remaining", "purchased_remaining",
), int)
_ADVANCED = dict.fromkeys((
    "signup_remaining", "pro_monthly_remaining", "weekly_reward_remaining", "weekly_advanced_granted",
    "weekly_ad_views", "weekly_ad_views_needed", "purchased_remaining", "max_hold",
), int)
_PRODUCTS = {
    "basic_review_15": ("basic", 15, 2900),
    "basic_review_25": ("basic", 25, 4500),
    "advanced_review_10": ("advanced", 10, 3900),
    "advanced_review_20": ("advanced", 20, 6900),
}
_RESETS = ("daily_reset_at", "weekly_reset_at", "monthly_reset_at", "weekly_reward_expires_at")
_ACCESS = {
    "auth_mode": str, "plan": str, "review_type": str, "source": str,
    "refunded": bool, "idempotent_replay": bool,
    "quota": {"basic": _BASIC, "advanced": _ADVANCED},
    "wallet": {
        "plan": str, "basic": _BASIC, "advanced": _ADVANCED,
        "products": {key: {"kind": str, "quantity": int, "price_krw": int} for key in _PRODUCTS},
        "settings": {
            "allow_advanced_ticket_for_basic": bool,
            "ad_policy": {
                "basic_reviews_per_rewarded_ad": int, "rewarded_basic_daily_max": int,
                "ads_per_advanced_ticket": int, "force_rewarded_ad_chain": bool,
                "preferred_rewarded_ad_sequence": str,
            },
            "free_policy": {
                "daily_basic": int, "rewarded_basic_daily_max": int,
                "monthly_basic_max": int, "weekly_advanced_max": int,
            },
        },
        "validity": {
            "timezone": str, **dict.fromkeys(_RESETS, (str, type(None))),
            "signup_pass_expires_at": type(None), "purchased_pass_expires_at": type(None),
            "pro_allowance_resets_at": (str, type(None)),
        },
    },
}
_SOURCES = {
    "free": {
        "basic": {"signup_basic", "free_daily_basic", "rewarded_ad_basic", "purchased_basic", "purchased_advanced_as_basic"},
        "advanced": {"signup_advanced", "weekly_ad_advanced", "purchased_advanced"},
    },
    "pro": {
        "basic": {"pro_monthly_basic", "purchased_basic"},
        "advanced": {"pro_monthly_advanced", "purchased_advanced", "signup_advanced", "weekly_ad_advanced"},
    },
}
_EXPIRY = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}[T ][0-9]{2}:[0-9]{2}"
    r"(?::[0-9]{2}(?:\.[0-9]{1,6})?)?(?:Z|(?P<sign>[+-])(?P<hour>[0-9]{2}):(?P<minute>[0-9]{2}))"
)
_RESET = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T00:00\+09:00")


def _require(condition, path):
    if not condition:
        # Only fixed schema paths are included; never reflect rejected values.
        raise HistoryWriteContractError("invalid new-history access: " + path)


def _shape(value, schema, path="access"):
    if type(schema) is dict:
        _require(type(value) is dict, path)
        _require(all(type(key) is str for key in value) and value.keys() == schema.keys(), path)
        for key, child in schema.items():
            _shape(value[key], child, path + "." + key)
    else:
        expected_types = schema if type(schema) is tuple else (schema,)
        _require(any(type(value) is expected for expected in expected_types), path)
        if type(value) is int:
            _require(0 <= value <= _MAX_SAFE_INTEGER, path)


def _expiry(value, path):
    _require(type(value) is str, path)
    match = _EXPIRY.fullmatch(value)
    _require(match is not None, path)
    if match["sign"] is not None:
        _require(int(match["hour"]) <= 23 and int(match["minute"]) <= 59, path)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise HistoryWriteContractError("invalid new-history access: " + path) from None
    _require(parsed.tzinfo is not None and parsed.utcoffset() is not None, path)


def _validity(wallet, *, review_mode, plan):
    validity = wallet["validity"]
    _require(validity["timezone"] == "Asia/Seoul", "wallet.validity.timezone")
    if review_mode:
        _require(all(validity[key] is None for key in _RESETS), "wallet.validity.review_resets")
    else:
        for key in _RESETS:
            value = validity[key]
            _require(type(value) is str and _RESET.fullmatch(value) is not None, "wallet.validity." + key)
        _require(validity["weekly_reward_expires_at"] == validity["weekly_reset_at"], "wallet.validity.weekly_reward_expires_at")
        try:
            # All three internal deadlines share one producer clock call.
            # Derive their calendar relationship without asking today's date.
            producer_day = date.fromisoformat(validity["daily_reset_at"][:10]) - timedelta(days=1)
            weekly = producer_day + timedelta(days=7 - producer_day.weekday())
            monthly = (producer_day.replace(day=28) + timedelta(days=4)).replace(day=1)
            actual_weekly = date.fromisoformat(validity["weekly_reset_at"][:10])
            actual_monthly = date.fromisoformat(validity["monthly_reset_at"][:10])
        except (ValueError, OverflowError):
            raise HistoryWriteContractError("invalid new-history access: wallet.validity.reset_calendar") from None
        _require(actual_weekly == weekly and actual_monthly == monthly, "wallet.validity.reset_calendar")
    expiry = validity["pro_allowance_resets_at"]
    if plan == "free" and not review_mode:
        _require(expiry is None, "wallet.validity.pro_allowance_resets_at")
    else:
        # The expiry can already be past and need not equal monthly_reset_at.
        _expiry(expiry, "wallet.validity.pro_allowance_resets_at")


def _policy(wallet):
    settings = wallet["settings"]
    ad_policy = settings["ad_policy"]
    _require(ad_policy["basic_reviews_per_rewarded_ad"] == 1
             and ad_policy["rewarded_basic_daily_max"] == 2
             and 1 <= ad_policy["ads_per_advanced_ticket"] <= 20
             and ad_policy["preferred_rewarded_ad_sequence"] == "single", "wallet.settings.ad_policy")
    _require(settings["free_policy"] == {
        "daily_basic": 1, "rewarded_basic_daily_max": 2,
        "monthly_basic_max": 30, "weekly_advanced_max": 1,
    }, "wallet.settings.free_policy")
    for key, expected in _PRODUCTS.items():
        product = wallet["products"][key]
        _require((product["kind"], product["quantity"], product["price_krw"]) == expected, "wallet.products." + key)


def _balances(wallet, *, review_mode, plan):
    basic, advanced = wallet["basic"], wallet["advanced"]
    _require(basic["free_monthly_limit"] == 30 and advanced["max_hold"] == 1, "wallet.balance_limits")
    if review_mode:
        _require(wallet["settings"]["allow_advanced_ticket_for_basic"] is False, "wallet.settings.allow_advanced_ticket_for_basic")
        _require(all(basic[key] == 0 for key in _BASIC if key not in {"free_monthly_limit", "pro_monthly_remaining"}), "wallet.basic.review")
        _require(all(advanced[key] == 0 for key in _ADVANCED if key not in {"max_hold", "pro_monthly_remaining"}), "wallet.advanced.review")
        if wallet["plan"] == "free":
            _require(basic["pro_monthly_remaining"] == advanced["pro_monthly_remaining"] == 0, "wallet.review_expired_quota")
        return
    _require(basic["free_daily_remaining"] <= 1 and basic["free_monthly_remaining"] <= 30, "wallet.basic.free_limits")
    _require(basic["free_available_now"] == basic["signup_remaining"] + basic["free_daily_remaining"], "wallet.basic.free_available_now")
    _require(basic["rewarded_ad_available"] == basic["rewarded_ad_daily_remaining"], "wallet.basic.rewarded_ad_available")
    if plan == "free":
        _require(basic["pro_monthly_remaining"] == advanced["pro_monthly_remaining"] == 0, "wallet.free_pro_quota")
        _require(basic["rewarded_ad_daily_remaining"] <= 2, "wallet.basic.rewarded_ad_daily_remaining")
        _require(basic["free_daily_max_remaining"] == basic["free_daily_remaining"] + basic["rewarded_ad_daily_remaining"], "wallet.basic.free_daily_max_remaining")
    else:
        _require(basic["pro_monthly_remaining"] <= 35 and advanced["pro_monthly_remaining"] <= 25, "wallet.pro_quota")
        _require(basic["rewarded_ad_daily_remaining"] == 0, "wallet.basic.rewarded_ad_daily_remaining")
        # Pro hides rewarded counts, but its producer still includes them here.
        _require(0 <= basic["free_daily_max_remaining"] - basic["free_daily_remaining"] <= 2, "wallet.basic.free_daily_max_remaining")
    _require(advanced["weekly_ad_views_needed"] == max(0, wallet["settings"]["ad_policy"]["ads_per_advanced_ticket"] - advanced["weekly_ad_views"]), "wallet.advanced.weekly_ad_views_needed")


def validate_new_history_access(access, *, review_type, status):
    """Validate a new-write access snapshot in place without changing it.

    Storage-capable dev paths serialize as ordinary session access. Auth and
    storage consent remain the route's responsibility. Returns None or raises
    HistoryWriteContractError; no content/write approval object is created.
    """
    _require(type(review_type) is str and review_type in {"basic", "advanced"}, "review_type")
    _require(type(status) is str and status in {"ready", "missing_key"}, "status")
    _shape(access, _ACCESS)
    _require(access["auth_mode"] in {"session", "review"}, "auth_mode")
    _require(access["plan"] in {"free", "pro"} and access["wallet"]["plan"] in {"free", "pro"}, "plan")
    _require(access["review_type"] == review_type, "review_type")
    _require(access["refunded"] is False and access["idempotent_replay"] is False, "write_flags")
    wallet, plan = access["wallet"], access["plan"]
    review_mode = access["auth_mode"] == "review"
    if review_mode:
        _require(plan == "pro" and access["source"] == "review_" + review_type, "review_source_plan")
    else:
        _require(wallet["plan"] == plan and access["source"] in _SOURCES[plan][review_type], "session_source_plan")
    _require(access["source"] != "purchased_advanced_as_basic" or wallet["settings"]["allow_advanced_ticket_for_basic"] is True, "advanced_as_basic_setting")
    # Both copies have already passed exact scalar type checks, so Python's
    # numeric equality cannot disguise bool/int/float differences here.
    _require(access["quota"] == {key: wallet[key] for key in ("basic", "advanced")}, "quota_wallet")
    _policy(wallet)
    _balances(wallet, review_mode=review_mode, plan=plan)
    _validity(wallet, review_mode=review_mode, plan=plan)
