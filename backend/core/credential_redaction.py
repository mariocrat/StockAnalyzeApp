from urllib.parse import unquote


SECRET_FIELD_IDS = {
    "accesstoken",
    "adrewardtoken",
    "alphamateadmintoken",
    "alphamatedevadrewardtoken",
    "alphamatedevauthtoken",
    "alphamatedevproentitlementtoken",
    "alphamateopenaiapikey",
    "alphamatereviewaccesspasswordhash",
    "apikey",
    "apisecret",
    "appsecret",
    "authtoken",
    "authorization",
    "authorizationcode",
    "authorizationheader",
    "bearertoken",
    "clientsecret",
    "code",
    "configuredtoken",
    "cookie",
    "cookieheader",
    "credential",
    "credentials",
    "devadtoken",
    "devauthtoken",
    "devprotoken",
    "entitlementtoken",
    "googleplaypurchasetokenencryptionkey",
    "googleplayrtdnsharedtoken",
    "googleplayserviceaccountjson",
    "idtoken",
    "kakaoclientsecret",
    "naverclientsecret",
    "oauthcode",
    "oauthclientsecret",
    "oauthstate",
    "oauthticket",
    "openaiapikey",
    "password",
    "passwordhash",
    "privatekey",
    "purchasetoken",
    "refreshtoken",
    "secret",
    "sessiontoken",
    "sharedtoken",
    "setcookie",
    "signature",
    "state",
    "ticket",
    "token",
    "verificationtoken",
    "xalphamatertdntoken",
    "xapikey",
    "xauthtoken",
}
_HEADER_FIELD_IDS = {
    "authorization",
    "authorizationheader",
    "cookie",
    "cookieheader",
    "setcookie",
}
_HEX_DIGITS = frozenset("0123456789abcdefABCDEF")
_KEY_PUNCTUATION = frozenset("_.-")
_QUOTES = frozenset("\"'")
_TRUNCATED_MARKER = "[truncated]"


def _is_ascii_alphanumeric(character: str) -> bool:
    return "a" <= character.lower() <= "z" or "0" <= character <= "9"


def _key_unit_end(text: str, position: int) -> int:
    if position >= len(text):
        return position
    character = text[position]
    if _is_ascii_alphanumeric(character) or character in _KEY_PUNCTUATION:
        return position + 1
    if (
        character == "%"
        and position + 2 < len(text)
        and text[position + 1] in _HEX_DIGITS
        and text[position + 2] in _HEX_DIGITS
    ):
        return position + 3
    return position


def _has_key_boundary(text: str, position: int) -> bool:
    if position == 0:
        return True
    previous = text[position - 1]
    return not (_is_ascii_alphanumeric(previous) or previous in {"_", "%"})


def _assignment_candidate(text: str, start: int):
    """Return (key, value_start, advance_to) while scanning each byte once."""
    if not _has_key_boundary(text, start):
        return None, start + 1

    position = start
    if position + 1 < len(text) and text[position] == "\\" and text[position + 1] in _QUOTES:
        position += 2
    elif position < len(text) and text[position] in _QUOTES:
        position += 1

    key_start = position
    while position < len(text):
        unit_end = _key_unit_end(text, position)
        if unit_end == position:
            break
        position = unit_end
    if position == key_start:
        return None, start + 1

    key_end = position
    if position + 1 < len(text) and text[position] == "\\" and text[position + 1] in _QUOTES:
        position += 2
    elif position < len(text) and text[position] in _QUOTES:
        position += 1
    while position < len(text) and text[position].isspace():
        position += 1
    if position >= len(text) or text[position] not in {"=", ":"}:
        return None, max(position, key_end, start + 1)

    position += 1
    while position < len(text) and text[position].isspace():
        position += 1
    return (text[key_start:key_end], position), position


def normalized_credential_key(key: str) -> str:
    decoded = unquote(str(key or "").strip())
    return "".join(character for character in decoded.lower() if _is_ascii_alphanumeric(character))


def is_credential_key(key: str) -> bool:
    normalized = normalized_credential_key(key)
    if normalized in SECRET_FIELD_IDS:
        return True
    return normalized.startswith(("authorization", "password", "purchasetoken"))


def _line_end(text: str, start: int) -> int:
    position = start
    while position < len(text) and text[position] != "\r" and text[position] != "\n":
        position += 1
    return position


def _quoted_value_end(text: str, start: int, quote: str) -> int:
    position = start + 1
    while position < len(text):
        if text[position] == quote:
            backslashes = 0
            previous = position - 1
            while previous >= start and text[previous] == "\\":
                backslashes += 1
                previous -= 1
            if backslashes % 2 == 0:
                return position + 1
        position += 1
    return len(text)


def _credential_value_end(text: str, start: int, normalized_key: str) -> int:
    if start >= len(text):
        return start
    if text.startswith(("\\\"", "\\'"), start):
        return len(text)
    if text[start] in {"\"", "'"}:
        return _quoted_value_end(text, start, text[start])
    if normalized_key in _HEADER_FIELD_IDS:
        return _line_end(text, start)

    position = start
    if text[position : position + 6].lower() == "bearer":
        position += 6
        while position < len(text) and text[position].isspace():
            position += 1
    while position < len(text) and not text[position].isspace():
        position += 1
    return position


def _bounded_result(text: str, *, limit: int | None, truncated: bool) -> str:
    if limit is None:
        return text
    if not truncated and len(text) <= limit:
        return text
    if limit <= len(_TRUNCATED_MARKER):
        return _TRUNCATED_MARKER[:limit]
    return f"{text[: limit - len(_TRUNCATED_MARKER)]}{_TRUNCATED_MARKER}"


def sanitize_text(value, *, limit: int | None = None) -> str:
    raw_text = str(value or "")
    if limit is not None:
        limit = max(0, int(limit))
    truncated = limit is not None and len(raw_text) > limit
    text = raw_text if limit is None else raw_text[:limit]
    safe_parts = []
    copied_until = 0
    position = 0

    while position < len(text):
        candidate, advance_to = _assignment_candidate(text, position)
        if candidate is None:
            position = advance_to
            continue

        key, value_start = candidate
        if not is_credential_key(key):
            position = advance_to
            continue

        normalized_key = normalized_credential_key(key)
        value_end = _credential_value_end(text, value_start, normalized_key)
        safe_parts.append(text[copied_until:value_start])
        safe_parts.append("[redacted]")
        copied_until = value_end
        position = max(value_end, value_start + 1)

    if not safe_parts:
        return _bounded_result(text, limit=limit, truncated=truncated)
    safe_parts.append(text[copied_until:])
    return _bounded_result("".join(safe_parts), limit=limit, truncated=truncated)
