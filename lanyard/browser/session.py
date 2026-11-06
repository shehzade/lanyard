import json

from lanyard.config import DEFAULT_COOKIES_FILE


def get_saved_cookies() -> list[dict]:
    if DEFAULT_COOKIES_FILE.exists():
        try:
            return json.loads(DEFAULT_COOKIES_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def save_cookies(cookies: list[dict]) -> None:
    DEFAULT_COOKIES_FILE.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_COOKIES_FILE.write_text(json.dumps(cookies, indent=2), encoding="utf-8")


def set_li_at_cookie(li_at_value: str) -> None:
    cookie = {
        "name": "li_at",
        "value": li_at_value.strip(),
        "domain": ".linkedin.com",
        "path": "/",
        "httpOnly": True,
        "secure": True,
        "sameSite": "None",
    }
    cookies = get_saved_cookies()
    cookies = [c for c in cookies if c.get("name") != "li_at"]
    cookies.append(cookie)
    save_cookies(cookies)


def has_valid_session() -> bool:
    cookies = get_saved_cookies()
    for cookie in cookies:
        if cookie.get("name") == "li_at" and cookie.get("value"):
            return True
    return False
