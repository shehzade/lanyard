import random
import time
from collections.abc import Generator
from contextlib import contextmanager

from camoufox.sync_api import Camoufox
from playwright.sync_api import BrowserContext, Page

from lanyard.browser.session import get_saved_cookies, save_cookies
from lanyard.config import DEFAULT_SESSION_DIR


@contextmanager
def get_browser_context(headless: bool = True) -> Generator[BrowserContext, None, None]:
    DEFAULT_SESSION_DIR.mkdir(parents=True, exist_ok=True)
    with Camoufox(
        persistent_context=True,
        user_data_dir=str(DEFAULT_SESSION_DIR),
        headless=headless,
        i_know_what_im_doing=True,
        humanize=True,
        viewport={"width": 1440, "height": 900},
    ) as context:
        cookies = get_saved_cookies()
        if cookies:
            try:
                context.add_cookies(cookies)
            except Exception:
                pass
        try:
            yield context
        finally:
            try:
                current_cookies = context.cookies()
                has_auth = any(c.get("name") in ("li_at", "li_rm") for c in current_cookies)
                if current_cookies and has_auth:
                    save_cookies(current_cookies)
            except Exception:
                pass


def human_scroll(page: Page, distance_px: int = 800) -> None:
    try:
        page.mouse.move(random.randint(450, 750), random.randint(300, 600))
    except Exception:
        pass
    steps = random.randint(3, 5)
    delta = distance_px // steps
    for _ in range(steps):
        jitter = random.randint(-30, 40)
        step_px = delta + jitter
        try:
            page.mouse.wheel(0, step_px)
        except Exception:
            pass
        try:
            page.evaluate(
                """(dist) => {
                const ws = document.querySelector("#workspace") ||
                           document.querySelector(".scaffold-layout__main") ||
                           document.querySelector("main") ||
                           document.scrollingElement ||
                           document.documentElement;
                if (ws) {
                    ws.scrollTop += dist;
                    ws.dispatchEvent(new Event("scroll", { bubbles: true }));
                }
                window.scrollBy(0, dist);
            }""",
                step_px,
            )
        except Exception:
            pass
        time.sleep(random.uniform(0.15, 0.35))
    time.sleep(random.uniform(0.6, 1.2))


def scroll_to_bottom(page: Page) -> None:
    """Scrolls the actual feed container to the bottom to trigger infinite-scroll loading."""
    try:
        page.mouse.move(random.randint(450, 750), random.randint(400, 700))
    except Exception:
        pass
    try:
        page.evaluate(
            """() => {
            const ws = document.querySelector("#workspace") ||
                       document.querySelector(".scaffold-layout__main") ||
                       document.querySelector("main") ||
                       document.scrollingElement ||
                       document.documentElement;
            if (ws) {
                ws.scrollTop = ws.scrollHeight;
                ws.dispatchEvent(new Event("scroll", { bubbles: true }));
            }
            window.scrollTo(0, document.body.scrollHeight);
        }"""
        )
    except Exception:
        pass
    time.sleep(random.uniform(1.2, 2.0))
