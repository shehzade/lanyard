import time
import urllib.parse
from collections.abc import Generator

from playwright.sync_api import BrowserContext, Page
from rich.console import Console

from lanyard.browser.driver import human_scroll, scroll_to_bottom

console = Console()


class LinkedInScraper:
    def __init__(self, context: BrowserContext):
        self.context = context

    def is_authenticated(self, page: Page) -> bool:
        url = page.url.lower()
        return not ("login" in url or "checkpoint" in url or "authwall" in url)

    def warm_session(self, page: Page) -> bool:
        try:
            page.goto(
                "https://www.linkedin.com/feed",
                wait_until="domcontentloaded",
                timeout=30000,
            )
            time.sleep(2.5)
            return self.is_authenticated(page)
        except Exception:
            return False

    def search_posts(
        self,
        query: str,
        scroll_depth: int = 10,
        page: Page | None = None,
    ) -> Generator[tuple[str, str, str | None, str | None], None, None]:
        encoded_query = urllib.parse.quote(query)
        search_url = (
            f"https://www.linkedin.com/search/results/content/?keywords={encoded_query}&origin=SWITCH_SEARCH_VERTICAL"
        )

        close_page = False
        if page is None:
            page = self.context.pages[0] if self.context.pages else self.context.new_page()
            close_page = False

        try:
            console.print(f"[cyan][*] Navigating to search feed: [bold]{query}[/bold][/cyan]")
            page.goto(search_url, wait_until="domcontentloaded", timeout=45000)
            time.sleep(3.5)

            if not self.is_authenticated(page):
                console.print("[dim yellow][*] Session warming up via /feed...[/dim yellow]")
                if not self.warm_session(page):
                    console.print(
                        "[bold red][!] LinkedIn authentication required.[/bold red]\n"
                        "Run [bold cyan]lanyard login[/bold cyan] or set your session cookie with [bold cyan]lanyard cookie <li_at>[/bold cyan]."
                    )
                    return
                page.goto(search_url, wait_until="domcontentloaded", timeout=45000)
                time.sleep(3.0)

            seen_images: set[str] = set()

            for step in range(scroll_depth):
                console.print(
                    f"[dim][*] Scrolling feed (step {step + 1}/{scroll_depth} | {len(seen_images)} images harvested)...[/dim]"
                )

                try:
                    page.evaluate("""() => {
                        const btns = Array.from(document.querySelectorAll("button")).filter(b => {
                            const t = (b.innerText || "").toLowerCase();
                            return t.includes("show more") || t.includes("see more results") || t.includes("load more");
                        });
                        btns.forEach(b => { try { b.click(); } catch(e){} });
                    }""")
                except Exception:
                    pass

                for _ in range(10):
                    try:
                        advanced = page.evaluate("""() => {
                            let count = 0;
                            const nextButtons = document.querySelectorAll(
                                'button[aria-label*="Next slide" i], button[aria-label*="Next image" i], ' +
                                'button[aria-label*="Next photo" i], button[aria-label*="Next page" i], ' +
                                'button[aria-label*="Next media" i], button[aria-label*="next" i], ' +
                                'button.feed-shared-carousel__nav-btn--next, button.artdeco-carousel__nav-btn--next, ' +
                                'button.document-carousel__nav-btn--next, [data-view-name*="carousel-next"], ' +
                                '[data-control-name*="carousel_next" i], [data-test-carousel-next-btn]'
                            );
                            nextButtons.forEach(btn => {
                                if (btn && !btn.disabled && btn.offsetParent !== null) {
                                    try {
                                        btn.click();
                                        count++;
                                    } catch (e) {}
                                }
                            });
                            return count;
                        }""")
                        if not advanced or advanced == 0:
                            break
                        time.sleep(0.3)
                    except Exception:
                        break

                if step % 2 == 0:
                    scroll_to_bottom(page)
                else:
                    human_scroll(page, distance_px=1400)

                try:
                    items = page.evaluate("""() => {
                        const results = [];
                        const candidateElements = [];

                        document.querySelectorAll('img').forEach(el => candidateElements.push({ el: el, type: 'img' }));
                        document.querySelectorAll('picture source[srcset]').forEach(el => candidateElements.push({ el: el, type: 'source' }));
                        document.querySelectorAll('[style*="background-image"], [class*="multi-image"] [style*="background"]').forEach(el => {
                            candidateElements.push({ el: el, type: 'bg' });
                        });

                        const seenInPass = new Set();

                        for (const item of candidateElements) {
                            const el = item.el;
                            let src = '';

                            if (item.type === 'img') {
                                src = el.currentSrc || el.src || el.getAttribute('data-delayed-url') || el.getAttribute('data-src') || '';
                                if (!src && el.srcset) {
                                    const parts = el.srcset.split(',');
                                    const best = parts[parts.length - 1].trim().split(' ')[0];
                                    if (best) src = best;
                                }
                            } else if (item.type === 'source') {
                                const ss = el.getAttribute('srcset') || '';
                                const parts = ss.split(',');
                                const best = parts[parts.length - 1].trim().split(' ')[0];
                                if (best) src = best;
                            } else if (item.type === 'bg') {
                                const bg = el.style.backgroundImage || '';
                                const m = bg.match(/url\\(["']?(https:\\/\\/media\\.licdn\\.com\\/dms\\/image[^"']+)["']?\\)/);
                                if (m && m[1]) src = m[1];
                            }

                            if (!src || !src.includes('media.licdn.com/dms/image')) continue;
                            if (seenInPass.has(src)) continue;
                            seenInPass.add(src);

                            if (
                                src.includes('profile-displayphoto') ||
                                src.includes('company-logo') ||
                                src.includes('series-logo') ||
                                src.includes('ghost-person') ||
                                src.includes('ghost-company') ||
                                src.includes('emojis') ||
                                src.includes('vector') ||
                                src.includes('collect/?pid=')
                            ) {
                                continue;
                            }

                            if (item.type === 'img' && el.naturalWidth > 0 && el.naturalWidth < 120 && el.naturalHeight < 120) {
                                continue;
                            }

                            let postUrl = window.location.href;
                            let authorName = null;
                            let postCaption = null;
                            let p = el.parentElement;

                            while (p && p !== document.body) {
                                if (!postUrl || postUrl === window.location.href) {
                                    const link = p.querySelector('a[href*="/feed/update/"], a[href*="/posts/"]');
                                    if (link && link.href) {
                                        postUrl = link.href.split('?')[0];
                                    } else {
                                        const urn = p.getAttribute('data-urn');
                                        if (urn) {
                                            postUrl = 'https://www.linkedin.com/feed/update/' + urn;
                                        }
                                    }
                                }

                                if (!authorName) {
                                    const actor = p.querySelector('[class*="actor__name"], [class*="actor-name"], .feed-shared-actor__title, a[href*="/in/"]');
                                    if (actor) {
                                        const raw = (actor.innerText || '').trim().split('\\n')[0].trim();
                                        if (raw && raw.length < 60) authorName = raw;
                                    }
                                }

                                if (!postCaption) {
                                    const txt = p.querySelector('[class*="update-v2__description"], [class*="update-components-text"], [data-test-id*="commentary"]');
                                    if (txt) {
                                        const cleanTxt = (txt.innerText || '').trim().replace(/\\s+/g, ' ');
                                        if (cleanTxt.length > 15) postCaption = cleanTxt.slice(0, 300);
                                    }
                                }

                                p = p.parentElement;
                            }

                            results.push({
                                src: src,
                                postUrl: postUrl,
                                authorName: authorName,
                                postCaption: postCaption
                            });
                        }
                        return results;
                    }""")

                    for item in items:
                        src = item.get("src", "")
                        post_url = item.get("postUrl", page.url)
                        author_name = item.get("authorName")
                        post_caption = item.get("postCaption")
                        if src and src not in seen_images:
                            seen_images.add(src)
                            yield src, post_url, author_name, post_caption

                except Exception as e:
                    console.print(f"[dim yellow][!] DOM extraction notice: {e}[/dim yellow]")

        finally:
            if close_page:
                page.close()

    def search_multiple_queries(
        self,
        queries: list[str],
        scroll_depth: int = 10,
    ) -> Generator[tuple[str, str, str | None, str | None], None, None]:
        seen_images: set[str] = set()
        page = self.context.pages[0] if self.context.pages else self.context.new_page()
        try:
            self.warm_session(page)
            for idx, query in enumerate(queries):
                console.print(
                    f"[bold cyan][*] Executing Search Angle ({idx + 1}/{len(queries)}):[/bold cyan] [yellow]{query}[/yellow]"
                )
                for src, post_url, author_name, post_caption in self.search_posts(
                    query=query, scroll_depth=scroll_depth, page=page
                ):
                    if src not in seen_images:
                        seen_images.add(src)
                        yield src, post_url, author_name, post_caption
        finally:
            page.close()
