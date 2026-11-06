import os
import re
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx
import typer
from rich.console import Console
from rich.panel import Panel

from lanyard.browser.driver import get_browser_context
from lanyard.browser.session import has_valid_session, set_li_at_cookie
from lanyard.config import DEFAULT_OUTPUT_DIR, LanyardConfig
from lanyard.sources.linkedin import LinkedInScraper
from lanyard.storage.db import Database
from lanyard.storage.report import export_csv, export_html, export_jsonl
from lanyard.vision.cropper import crop_badge
from lanyard.vision.detector import BadgeDetector
from lanyard.vision.models import BadgeFinding

app = typer.Typer(
    name="lanyard",
    help="AI-driven badge OSINT, credential harvesting, and calibrated CR80 card cloning for physical red teams.",
    no_args_is_help=True,
)
console = Console()


@app.command()
def cookie(
    token: str = typer.Argument(..., help="Value of the LinkedIn 'li_at' session cookie."),
):
    """Save a LinkedIn 'li_at' session cookie for stealth authentication."""
    set_li_at_cookie(token)
    console.print("[bold green][+] Saved li_at session cookie to ~/.lanyard/cookies.json[/bold green]")


@app.command()
def login(
    email: str | None = typer.Option(None, "--email", "-e", help="Optional email to pre-fill in the browser."),
    password: str | None = typer.Option(None, "--password", "-p", help="Optional password to pre-fill in the browser."),
):
    """Launch Camoufox in a visible window to complete login or challenges and save session cookies."""
    console.print(
        Panel(
            "[bold cyan]Interactive Camoufox Browser[/bold cyan]\n"
            "A visible browser window will open on your desktop.\n"
            "Complete the login or verification challenge (email PIN/captcha).\n"
            "Once you are in your LinkedIn feed, return here and press [bold green]Enter[/bold green].",
            border_style="cyan",
        )
    )
    with get_browser_context(headless=False) as context:
        page = context.pages[0] if context.pages else context.new_page()
        page.goto("https://www.linkedin.com/login")

        if email:
            try:
                page.wait_for_timeout(2500)
                email_el = page.locator('input[type="email"]:visible').first
                if email_el.is_visible():
                    email_el.click()
                    for char in email:
                        page.keyboard.type(char)
                        time.sleep(0.04)
                    if password:
                        time.sleep(0.5)
                        pass_el = page.locator('input[type="password"]:visible').first
                        if pass_el.is_visible():
                            pass_el.click()
                            for char in password:
                                page.keyboard.type(char)
                                time.sleep(0.04)
                            time.sleep(0.5)
                            btn = page.locator(
                                "button:visible",
                                has_text=re.compile(r"^\s*Sign in\s*$"),
                            ).first
                            if btn.is_visible():
                                btn.click()
            except Exception:
                pass

        typer.prompt(
            "Press Enter after you have completed login and see your LinkedIn feed",
            default="",
        )
        cookies = context.cookies()
        li_at = next((c["value"] for c in cookies if c.get("name") == "li_at"), None)
        if li_at:
            console.print(
                f"[bold green][+] Successfully captured and saved LinkedIn session cookies! (li_at: {li_at[:12]}...)[/bold green]"
            )
        else:
            console.print(
                "[bold yellow][!] Could not find 'li_at' cookie. If you are logged in, make sure you reached linkedin.com/feed.[/bold yellow]"
            )


def _download_and_analyze(
    img_url: str,
    post_url: str,
    detector: BadgeDetector,
) -> tuple[str, str, bytes | None, BadgeFinding | None, str | None]:
    """Download an image and perform vision analysis concurrently."""
    try:
        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            resp = client.get(img_url)
            if resp.status_code != 200 or len(resp.content) < 4000:
                return (img_url, post_url, None, None, f"HTTP {resp.status_code}")
            img_bytes = resp.content
    except Exception as e:
        return (img_url, post_url, None, None, f"Download error: {e}")

    try:
        finding = detector.analyze_image(img_bytes)
        return (img_url, post_url, img_bytes, finding, None)
    except Exception as e:
        return (img_url, post_url, img_bytes, None, f"Vision API error: {e}")


def _analyze_local_file(
    file_path: Path,
    detector: BadgeDetector,
) -> tuple[Path, bytes | None, BadgeFinding | None, str | None]:
    """Analyze a local image file concurrently."""
    try:
        img_bytes = file_path.read_bytes()
        finding = detector.analyze_image(img_bytes)
        return (file_path, img_bytes, finding, None)
    except Exception as e:
        return (file_path, None, None, str(e))


@app.command()
def hunt(
    company: str = typer.Option(..., "--company", "-c", help="Target company or organization name."),
    keyword: str | None = typer.Option(
        None, "--keyword", "-k", help="Specific search keyword or comma-separated list."
    ),
    depth: int = typer.Option(12, "--depth", "-d", help="Number of scroll iterations per search query."),
    provider: str | None = typer.Option(
        None,
        "--provider",
        "-P",
        help="AI vision provider: gemini, openai, anthropic, ollama, openrouter (default: auto/gemini).",
    ),
    model: str | None = typer.Option(
        None,
        "--model",
        "-m",
        help="Vision model name (e.g. gemini-3.8-flash, gpt-4o, claude-3-7-sonnet-20250219, llama3.2-vision).",
    ),
    threads: int = typer.Option(
        4,
        "--threads",
        "-t",
        help="Number of concurrent worker threads for vision inference.",
    ),
    multi_query: bool = typer.Option(
        True,
        "--multi-query/--single-query",
        help="Execute multiple high-yield search angles.",
    ),
    headless: bool = typer.Option(
        True,
        "--headless/--headed",
        "--headless/--no-headless",
        help="Run Camoufox in headless or visible (headed) mode.",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Output directory for results (defaults to ./{company}_results).",
    ),
    min_confidence: float = typer.Option(
        0.5, "--min-confidence", help="Minimum AI confidence threshold to record badge."
    ),
    serve: bool = typer.Option(
        False,
        "--serve",
        help="Launch a local HTTP server to view the report immediately after scanning.",
    ),
    port: int = typer.Option(8088, "--port", "-p", help="Port for web server when --serve is used."),
):
    """Search LinkedIn posts for employee badge photos and analyze with multimodal AI vision."""
    cfg = LanyardConfig.load()
    effective_provider = (provider or cfg.vision_provider or "gemini").lower()

    if effective_provider == "openai":
        api_key = cfg.openai_api_key or cfg.gemini_api_key
        model_name = model or cfg.openai_model
        api_base = cfg.openai_base_url
    elif effective_provider == "anthropic":
        api_key = cfg.anthropic_api_key
        model_name = model or cfg.anthropic_model
        api_base = None
    elif effective_provider == "openrouter":
        api_key = cfg.openrouter_api_key
        model_name = model or cfg.openrouter_model
        api_base = None
    elif effective_provider == "ollama":
        api_key = ""
        model_name = model or cfg.ollama_model
        api_base = cfg.ollama_base_url
    else:
        api_key = cfg.gemini_api_key
        model_name = model or cfg.gemini_model
        api_base = None

    if effective_provider != "ollama" and not api_key:
        console.print(f"[bold red][!] Error: API key for provider '{effective_provider}' is not set.[/bold red]")
        raise typer.Exit(code=1)

    if not has_valid_session():
        console.print(
            "[bold yellow][!] Warning: No saved session cookie found.[/bold yellow]\n"
            "To avoid login blocks, run [bold cyan]lanyard login[/bold cyan] or [bold cyan]lanyard cookie <token>[/bold cyan] before hunting."
        )

    if output is None:
        safe_company = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in company.strip().lower())
        output = Path(f"./{safe_company}_results")

    output.mkdir(parents=True, exist_ok=True)
    orig_dir = output / "originals"
    crop_dir = output / "cropped"
    cr80_dir = output / "cr80"
    orig_dir.mkdir(exist_ok=True)
    crop_dir.mkdir(exist_ok=True)
    cr80_dir.mkdir(exist_ok=True)

    db = Database(output / "lanyard.db")
    detector = BadgeDetector(
        api_key=api_key,
        model_name=model_name,
        provider=effective_provider,
        api_base=api_base,
    )

    queries: list[str] = []
    if keyword:
        if "," in keyword:
            queries = [f'"{company}" ({kw.strip()})' for kw in keyword.split(",") if kw.strip()]
        else:
            queries = [f'"{company}" ({keyword.strip()})']
    elif multi_query:
        queries = [
            f'{company} "ID badge"',
            f'{company} "employee badge"',
            f'{company} "first day" badge',
            f'{company} "last day" badge',
            f'"As I depart {company}"',
            f'{company} "turned in my badge"',
            f"{company} lanyard",
            f"{company} intern badge",
            f'{company} "got my badge"',
        ]
    else:
        search_kw = " OR ".join(f'"{k}"' for k in cfg.default_keywords[:3])
        queries = [f'"{company}" ({search_kw})']

    console.print(
        Panel(
            f"[bold]Target:[/bold] {company}\n"
            f"[bold]Queries ({len(queries)}):[/bold] {', '.join(queries)}\n"
            f"[bold]Scroll Depth:[/bold] {depth} per query\n"
            f"[bold]Model:[/bold] {cfg.gemini_model}\n"
            f"[bold]Threads:[/bold] {threads}\n"
            f"[bold]Output:[/bold] {output}",
            title="Lanyard Badge Hunt",
            border_style="cyan",
        )
    )

    total_scraped = 0
    total_badges = 0

    candidates: list[tuple[str, str, str | None, str | None]] = []
    with get_browser_context(headless=headless) as context:
        scraper = LinkedInScraper(context)
        for (
            img_url,
            post_url,
            author_name,
            post_caption,
        ) in scraper.search_multiple_queries(queries=queries, scroll_depth=depth):
            total_scraped += 1
            if not db.is_image_analyzed(img_url):
                candidates.append((img_url, post_url, author_name, post_caption))

    console.print(
        f"[bold cyan][*] Discovered {len(candidates)} new media images across posts/albums. Dispatching to {threads} workers...[/bold cyan]"
    )

    cr80_dir = output / "cr80"
    cr80_dir.mkdir(exist_ok=True)

    with ThreadPoolExecutor(max_workers=max(1, threads)) as executor:
        futures = {
            executor.submit(_download_and_analyze, img_url, post_url, detector): (
                img_url,
                post_url,
                author_name,
                post_caption,
            )
            for img_url, post_url, author_name, post_caption in candidates
        }

        completed_count = 0
        for future in as_completed(futures):
            completed_count += 1
            img_url, post_url, author_name, post_caption = futures[future]
            _img_url_res, _post_url_res, img_bytes, finding, err = future.result()

            if err:
                console.print(f"[dim yellow][!] ({completed_count}/{len(candidates)}) Skipped: {err}[/dim yellow]")
                continue

            img_id = db.record_image(
                image_url=img_url,
                post_url=post_url,
                post_author=author_name,
                post_caption=post_caption,
            )
            crop_path = None
            orig_path = None
            cr80_path = None

            if finding and finding.has_badge and finding.confidence >= min_confidence:
                total_badges += 1
                uid = uuid.uuid4().hex[:8]
                orig_path = orig_dir / f"badge_{uid}_orig.jpg"
                crop_path = crop_dir / f"badge_{uid}_crop.jpg"
                cr80_path = cr80_dir / f"badge_{uid}_cr80.png"
                cr80_svg_path = cr80_dir / f"badge_{uid}_cr80.svg"

                orig_path.write_bytes(img_bytes)
                if finding.bounding_box:
                    crop_badge(img_bytes, finding.bounding_box, crop_path)

                if not finding.employee_name and author_name:
                    finding.employee_name = author_name

                try:
                    from lanyard.storage.cr80 import convert_badge_to_cr80

                    src_card = (
                        orig_path
                        if (finding.card_corners and orig_path and orig_path.exists())
                        else (crop_path if (crop_path and crop_path.exists()) else img_bytes)
                    )
                    convert_badge_to_cr80(
                        source_image=src_card,
                        output_png=cr80_path,
                        output_svg=cr80_svg_path,
                        corners=finding.card_corners,
                    )
                except Exception as e:
                    console.print(f"[dim yellow][!] CR80 conversion notice: {e}[/dim yellow]")

                console.print(
                    f"[bold green][+] BADGE DETECTED ({int(finding.confidence * 100)}%)[/bold green] "
                    f"Type: [cyan]{finding.badge_type}[/cyan] | "
                    f"Employee: [yellow]{finding.employee_name or 'N/A'}[/yellow] | "
                    f"Org: [yellow]{finding.company_name or 'N/A'}[/yellow] | "
                    f"Features: [magenta]{', '.join(finding.security_features) if finding.security_features else 'none'}[/magenta]"
                )
            else:
                conf = f"{int(finding.confidence * 100)}%" if finding else "0%"
                console.print(f"[dim][*] ({completed_count}/{len(candidates)}) No badge detected ({conf})[/dim]")

            if finding:
                db.record_finding(
                    image_id=img_id,
                    finding=finding,
                    crop_path=str(crop_path) if crop_path else None,
                    original_path=str(orig_path) if orig_path else None,
                    template_path=str(cr80_path) if (cr80_path and cr80_path.exists()) else None,
                )

    findings = db.get_all_badge_findings()
    export_html(findings, output / "report.html")
    export_jsonl(findings, output / "findings.jsonl")
    export_csv(findings, output / "findings.csv")

    console.print(
        Panel(
            f"[bold green]Scan Complete[/bold green]\n"
            f"Images Scraped: {total_scraped}\n"
            f"Badges Discovered: {len(findings)}\n"
            f"HTML Report: [cyan]{output.resolve() / 'report.html'}[/cyan]\n"
            f"JSONL Export: [cyan]{output.resolve() / 'findings.jsonl'}[/cyan]\n"
            f"CSV Export: [cyan]{output.resolve() / 'findings.csv'}[/cyan]\n"
            f"Database: [cyan]{output.resolve() / 'lanyard.db'}[/cyan]",
            border_style="green",
        )
    )

    if findings:
        from rich.table import Table

        table = Table(title="Physical Security Badge Findings Summary", border_style="green")
        table.add_column("ID", justify="right", style="cyan")
        table.add_column("Type", style="bold")
        table.add_column("Employee", style="yellow")
        table.add_column("Organization", style="magenta")
        table.add_column("Role / Dept", style="blue")
        table.add_column("Confidence", justify="right", style="green")
        table.add_column("Features")
        table.add_column("Crop File", style="dim")

        for f in findings:
            crop_p = f.get("crop_path")
            crop_name = Path(crop_p).name if crop_p else "N/A"
            feats = f.get("security_features") or []
            if isinstance(feats, str):
                import json

                try:
                    feats = json.loads(feats)
                except Exception:
                    feats = [feats]
            conf = f.get("confidence", 0.0)
            table.add_row(
                str(f.get("id")),
                str(f.get("badge_type") or "N/A"),
                str(f.get("employee_name") or "N/A"),
                str(f.get("company_name") or "N/A"),
                str(f.get("department_or_role") or "N/A"),
                f"{int(conf * 100)}%",
                ", ".join(feats) if feats else "None",
                crop_name,
            )
        console.print(table)

    if serve:
        _run_server(output, port)


def _run_server(output: Path, port: int) -> None:
    import http.server
    import socketserver

    os.chdir(str(output.resolve()))
    console.print(
        f"[bold green][+] Serving Dossier at:[/bold green] [bold cyan]http://127.0.0.1:{port}/report.html[/bold cyan]"
    )
    console.print("[dim]Press Ctrl+C to exit server.[/dim]")
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", port), handler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            console.print("\n[yellow][*] Stopped server.[/yellow]")


@app.command()
def serve(
    output: Path = typer.Option(
        DEFAULT_OUTPUT_DIR,
        "--output",
        "-o",
        help="Output directory containing report.html.",
    ),
    port: int = typer.Option(8088, "--port", "-p", help="Port to serve report on."),
):
    """Serve the badge report HTML and image crops via a local HTTP server."""
    if not output.exists():
        console.print(f"[bold red][!] Output directory not found: {output}[/bold red]")
        raise typer.Exit(code=1)
    _run_server(output, port)


@app.command("analyze-dir")
def analyze_dir(
    folder: Path = typer.Argument(..., help="Path to local folder with photos to analyze."),
    provider: str | None = typer.Option(
        None,
        "--provider",
        "-P",
        help="AI vision provider: gemini, openai, anthropic, ollama, openrouter (default: auto/gemini).",
    ),
    model: str | None = typer.Option(
        None,
        "--model",
        "-m",
        help="Vision model name (e.g. gemini-3.8-flash, gpt-4o, claude-3-7-sonnet-20250219, llama3.2-vision).",
    ),
    threads: int = typer.Option(4, "--threads", "-t", help="Number of concurrent worker threads."),
    output: Path = typer.Option(DEFAULT_OUTPUT_DIR, "--output", "-o", help="Output directory."),
    min_confidence: float = typer.Option(0.5, "--min-confidence", help="Minimum confidence threshold."),
):
    """Analyze a local directory of images directly for employee badges."""
    cfg = LanyardConfig.load()
    effective_provider = (provider or cfg.vision_provider or "gemini").lower()

    if effective_provider == "openai":
        api_key = cfg.openai_api_key or cfg.gemini_api_key
        model_name = model or cfg.openai_model
        api_base = cfg.openai_base_url
    elif effective_provider == "anthropic":
        api_key = cfg.anthropic_api_key
        model_name = model or cfg.anthropic_model
        api_base = None
    elif effective_provider == "openrouter":
        api_key = cfg.openrouter_api_key
        model_name = model or cfg.openrouter_model
        api_base = None
    elif effective_provider == "ollama":
        api_key = ""
        model_name = model or cfg.ollama_model
        api_base = cfg.ollama_base_url
    else:
        api_key = cfg.gemini_api_key
        model_name = model or cfg.gemini_model
        api_base = None

    if effective_provider != "ollama" and not api_key:
        console.print(f"[bold red][!] Error: API key for provider '{effective_provider}' is not set.[/bold red]")
        raise typer.Exit(code=1)

    if not folder.exists() or not folder.is_dir():
        console.print(f"[bold red][!] Folder does not exist: {folder}[/bold red]")
        raise typer.Exit(code=1)

    output.mkdir(parents=True, exist_ok=True)
    orig_dir = output / "originals"
    crop_dir = output / "cropped"
    cr80_dir = output / "cr80"
    orig_dir.mkdir(exist_ok=True)
    crop_dir.mkdir(exist_ok=True)
    cr80_dir.mkdir(exist_ok=True)

    db = Database(output / "lanyard.db")
    detector = BadgeDetector(
        api_key=api_key,
        model_name=model_name,
        provider=effective_provider,
        api_base=api_base,
    )

    image_extensions = {".jpg", ".jpeg", ".png", ".webp"}
    files = [f for f in folder.iterdir() if f.suffix.lower() in image_extensions]

    console.print(f"[*] Found {len(files)} image files in {folder}. Analyzing with {threads} threads...")
    badges_found = 0

    unprocessed_files = [f for f in files if not db.is_image_analyzed(str(f.resolve()))]

    with ThreadPoolExecutor(max_workers=max(1, threads)) as executor:
        futures = {executor.submit(_analyze_local_file, f, detector): f for f in unprocessed_files}

        for idx, future in enumerate(as_completed(futures), 1):
            f, img_bytes, finding, err = future.result()
            rel_key = str(f.resolve())

            if err:
                console.print(f"[red][!] Vision error on {f.name}: {err}[/red]")
                continue

            img_id = db.record_image(rel_key, post_url="local_file")
            crop_path = None
            orig_path = None

            if finding and finding.has_badge and finding.confidence >= min_confidence:
                badges_found += 1
                uid = uuid.uuid4().hex[:8]
                orig_path = orig_dir / f"badge_{uid}_orig{f.suffix}"
                crop_path = crop_dir / f"badge_{uid}_crop{f.suffix}"

                orig_path.write_bytes(img_bytes)
                if finding.bounding_box:
                    crop_badge(img_bytes, finding.bounding_box, crop_path)

                cr80_path = cr80_dir / f"badge_{uid}_cr80.png"
                cr80_svg_path = cr80_dir / f"badge_{uid}_cr80.svg"
                try:
                    from lanyard.storage.cr80 import convert_badge_to_cr80

                    src_card = (
                        orig_path
                        if (finding.card_corners and orig_path and orig_path.exists())
                        else (crop_path if (crop_path and crop_path.exists()) else img_bytes)
                    )
                    convert_badge_to_cr80(
                        source_image=src_card,
                        output_png=cr80_path,
                        output_svg=cr80_svg_path,
                        corners=finding.card_corners,
                    )
                except Exception as e:
                    console.print(f"[dim yellow][!] CR80 conversion notice: {e}[/dim yellow]")

                console.print(
                    f"[bold green][+] BADGE DETECTED in {f.name} ({int(finding.confidence * 100)}%)[/bold green] "
                    f"Employee: [yellow]{finding.employee_name or 'N/A'}[/yellow] | Org: [yellow]{finding.company_name or 'N/A'}[/yellow]"
                )
            else:
                console.print(f"[dim][*] ({idx}/{len(unprocessed_files)}) No badge in {f.name}[/dim]")

            if finding:
                db.record_finding(
                    image_id=img_id,
                    finding=finding,
                    crop_path=str(crop_path) if crop_path else None,
                    original_path=str(orig_path) if orig_path else None,
                    template_path=str(cr80_path) if (cr80_path and cr80_path.exists()) else None,
                )

    findings = db.get_all_badge_findings()
    export_html(findings, output / "report.html")
    export_jsonl(findings, output / "findings.jsonl")
    export_csv(findings, output / "findings.csv")

    console.print(
        f"[bold green][+] Finished! Detected {badges_found} badges. Report: {output / 'report.html'}[/bold green]"
    )


@app.command()
def report(
    output: Path = typer.Option(
        DEFAULT_OUTPUT_DIR,
        "--output",
        "-o",
        help="Output directory containing lanyard.db.",
    ),
):
    """Regenerate HTML, JSONL, and CSV reports from the lanyard database."""
    db_file = output / "lanyard.db"
    if not db_file.exists():
        console.print(f"[bold red][!] Database not found: {db_file}[/bold red]")
        raise typer.Exit(code=1)

    db = Database(db_file)
    findings = db.get_all_badge_findings()

    html_path = export_html(findings, output / "report.html")
    jsonl_path = export_jsonl(findings, output / "findings.jsonl")
    csv_path = export_csv(findings, output / "findings.csv")

    console.print(f"[bold green][+] Exported {len(findings)} badge records:[/bold green]")
    console.print(f"  - HTML:  {html_path}")
    console.print(f"  - JSONL: {jsonl_path}")
    console.print(f"  - CSV:   {csv_path}")


@app.command("config")
def config_cmd(
    set_key: str | None = typer.Option(
        None,
        "--set-key",
        help="Save Gemini API key to config (alias for --gemini-key).",
    ),
    gemini_key: str | None = typer.Option(None, "--gemini-key", help="Save Gemini API key to config."),
    gemini_model: str | None = typer.Option(None, "--gemini-model", help="Set default Gemini model."),
    openai_key: str | None = typer.Option(None, "--openai-key", help="Save OpenAI API key to config."),
    openai_model: str | None = typer.Option(None, "--openai-model", help="Set default OpenAI model."),
    openai_base: str | None = typer.Option(None, "--openai-base", help="Set OpenAI base URL."),
    anthropic_key: str | None = typer.Option(None, "--anthropic-key", help="Save Anthropic API key to config."),
    anthropic_model: str | None = typer.Option(None, "--anthropic-model", help="Set default Anthropic model."),
    openrouter_key: str | None = typer.Option(None, "--openrouter-key", help="Save OpenRouter API key to config."),
    openrouter_model: str | None = typer.Option(None, "--openrouter-model", help="Set default OpenRouter model."),
    ollama_base: str | None = typer.Option(
        None, "--ollama-base", help="Set Ollama base URL (e.g. http://localhost:11434)."
    ),
    ollama_model: str | None = typer.Option(None, "--ollama-model", help="Set default Ollama model."),
    provider: str | None = typer.Option(
        None,
        "--provider",
        "-P",
        help="Set default vision provider (gemini, openai, anthropic, ollama, openrouter).",
    ),
    show: bool = typer.Option(False, "--show", help="Display current configuration."),
):
    """Manage Lanyard settings, AI vision providers, and API keys."""
    cfg = LanyardConfig.load()
    changed = False

    effective_gemini_key = gemini_key or set_key
    if effective_gemini_key:
        cfg.gemini_api_key = effective_gemini_key.strip()
        changed = True
        console.print("[bold green][+] Saved Gemini API key.[/bold green]")

    if gemini_model:
        cfg.gemini_model = gemini_model.strip()
        changed = True
        console.print(f"[bold green][+] Saved Gemini model: {cfg.gemini_model}[/bold green]")

    if openai_key:
        cfg.openai_api_key = openai_key.strip()
        changed = True
        console.print("[bold green][+] Saved OpenAI API key.[/bold green]")

    if openai_model:
        cfg.openai_model = openai_model.strip()
        changed = True
        console.print(f"[bold green][+] Saved OpenAI model: {cfg.openai_model}[/bold green]")

    if openai_base:
        cfg.openai_base_url = openai_base.strip()
        changed = True
        console.print(f"[bold green][+] Saved OpenAI base URL: {cfg.openai_base_url}[/bold green]")

    if anthropic_key:
        cfg.anthropic_api_key = anthropic_key.strip()
        changed = True
        console.print("[bold green][+] Saved Anthropic API key.[/bold green]")

    if anthropic_model:
        cfg.anthropic_model = anthropic_model.strip()
        changed = True
        console.print(f"[bold green][+] Saved Anthropic model: {cfg.anthropic_model}[/bold green]")

    if openrouter_key:
        cfg.openrouter_api_key = openrouter_key.strip()
        changed = True
        console.print("[bold green][+] Saved OpenRouter API key.[/bold green]")

    if openrouter_model:
        cfg.openrouter_model = openrouter_model.strip()
        changed = True
        console.print(f"[bold green][+] Saved OpenRouter model: {cfg.openrouter_model}[/bold green]")

    if ollama_base:
        cfg.ollama_base_url = ollama_base.strip()
        changed = True
        console.print(f"[bold green][+] Saved Ollama base URL: {cfg.ollama_base_url}[/bold green]")

    if ollama_model:
        cfg.ollama_model = ollama_model.strip()
        changed = True
        console.print(f"[bold green][+] Saved Ollama model: {cfg.ollama_model}[/bold green]")

    if provider:
        valid_providers = ["gemini", "openai", "anthropic", "ollama", "openrouter"]
        if provider.lower() not in valid_providers:
            console.print(
                f"[bold red][!] Invalid provider '{provider}'. Must be one of: {', '.join(valid_providers)}[/bold red]"
            )
            raise typer.Exit(code=1)
        cfg.vision_provider = provider.lower()
        changed = True
        console.print(f"[bold green][+] Default vision provider set to: {cfg.vision_provider}[/bold green]")

    if changed:
        cfg.save()
        console.print("[dim]Config saved to ~/.lanyard/config.json[/dim]")
        return

    def _mask(k: str) -> str:
        if not k:
            return "(not set)"
        return f"{k[:6]}...{k[-4:]}" if len(k) > 10 else "***"

    console.print("[bold cyan]=== Lanyard Configuration ===[/bold cyan]")
    console.print(f"[bold]Active Provider:[/bold] [yellow]{cfg.vision_provider}[/yellow]")
    console.print(
        f"[bold]LinkedIn Session:[/bold] {'[green]Valid[/green]' if has_valid_session() else '[red]Not logged in[/red]'}"
    )
    console.print("")
    console.print(
        f"[bold green]Gemini:[/bold green]     model=[cyan]{cfg.gemini_model}[/cyan]  key={_mask(cfg.gemini_api_key)}"
    )
    console.print(
        f"[bold green]OpenAI:[/bold green]     model=[cyan]{cfg.openai_model}[/cyan]  key={_mask(cfg.openai_api_key)}  base={cfg.openai_base_url}"
    )
    console.print(
        f"[bold green]Anthropic:[/bold green]  model=[cyan]{cfg.anthropic_model}[/cyan]  key={_mask(cfg.anthropic_api_key)}"
    )
    console.print(
        f"[bold green]OpenRouter:[/bold green] model=[cyan]{cfg.openrouter_model}[/cyan]  key={_mask(cfg.openrouter_api_key)}"
    )
    console.print(
        f"[bold green]Ollama:[/bold green]     model=[cyan]{cfg.ollama_model}[/cyan]  base={cfg.ollama_base_url}"
    )


def main():
    app()


if __name__ == "__main__":
    main()
