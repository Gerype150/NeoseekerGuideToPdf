import hashlib
import os
from urllib.parse import unquote

import requests
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


class NeoseekerClient:
    def __init__(
        self,
        cache_dir: str,
        retries: int,
        profile_dir: str,
        wait_for_cloudflare_input: bool = False,
    ) -> None:
        self._cache_dir = cache_dir
        self._retries = retries
        self._profile_dir = profile_dir
        self._wait_for_cloudflare_input = wait_for_cloudflare_input
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 "
                    "(KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": (
                    "text/html,application/xhtml+xml,"
                    "application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
                ),
                "Accept-Language": "en-US,en;q=0.9",
            }
        )
        os.makedirs(self._cache_dir, exist_ok=True)

    def get_chapter_urls(self, start_url: str) -> list[str]:
        chapters_cache = self._chapter_cache_file(start_url)
        if os.path.exists(chapters_cache):
            with open(chapters_cache, encoding="utf-8") as file:
                cached_chapters = [line.strip() for line in file if line.strip()]

            if cached_chapters:
                print(f"Capitulos cargados desde cache: {len(cached_chapters)}")
                return cached_chapters

        print("Abriendo navegador...")

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch_persistent_context(
                self._profile_dir,
                headless=False,
                viewport={"width": 1280, "height": 900},
                locale="en-US",
            )

            page = browser.new_page()
            page.goto(start_url, wait_until="commit", timeout=120000)
            if self._wait_for_cloudflare_input:
                input("Pasa Cloudflare y pulsa ENTER...")
            else:
                self._wait_for_chapter_page_ready(page, start_url)

            self._copy_cookies(browser)
            chapters = self._extract_chapters(page, start_url)

            if not chapters:
                print("No se detectaron capitulos al primer intento. Reintentando...")
                page.wait_for_timeout(5000)
                chapters = self._extract_chapters(page, start_url)

            browser.close()

        with open(chapters_cache, "w", encoding="utf-8") as file:
            file.write("\n".join(chapters))

        return chapters

    def get_page_html(self, url: str) -> str:
        decoded_url = unquote(url)
        path = self._cache_file(decoded_url)

        if os.path.exists(path):
            with open(path, encoding="utf-8") as file:
                return file.read()

        for attempt in range(self._retries):
            try:
                response = self._session.get(decoded_url, timeout=30)
                print(response.status_code, decoded_url)

                if response.status_code in [403, 404]:
                    print("Saltando:", response.status_code, decoded_url)
                    return ""

                response.raise_for_status()

                with open(path, "w", encoding="utf-8") as file:
                    file.write(response.text)

                return response.text
            except Exception:
                if attempt == self._retries - 1:
                    raise

        return ""

    def _cache_file(self, url: str) -> str:
        return os.path.join(
            self._cache_dir,
            hashlib.md5(url.encode()).hexdigest() + ".html",
        )

    def _chapter_cache_file(self, start_url: str) -> str:
        digest = hashlib.md5(start_url.encode()).hexdigest()
        return os.path.join(self._cache_dir, f"chapters_{digest}.txt")

    def _copy_cookies(self, browser_context) -> None:
        cookies = browser_context.cookies()

        for cookie in cookies:
            self._session.cookies.set(
                cookie["name"],
                cookie["value"],
                domain=cookie.get("domain"),
                path=cookie.get("path"),
            )

        print("Cookies copiadas:", len(cookies))

    def _wait_for_chapter_page_ready(self, page, start_url: str) -> None:
        # Some pages keep long-lived network requests open, so networkidle can time out.
        page.wait_for_timeout(3000)

        try:
            page.wait_for_load_state("load", timeout=20000)
        except PlaywrightTimeoutError:
            print("Aviso: timeout esperando 'load'; continuando con HTML parcial.")

        try:
            page.wait_for_load_state("networkidle", timeout=5000)
        except PlaywrightTimeoutError:
            print("Aviso: 'networkidle' no alcanzado; continuando sin bloquear.")

        chapter_prefix = self._chapter_prefix(start_url)
        try:
            page.wait_for_selector(f'a[href^="{chapter_prefix}"]', timeout=20000)
        except PlaywrightTimeoutError:
            print("Aviso: no se confirmaron enlaces de capitulos por selector.")

    @staticmethod
    def _chapter_prefix(start_url: str) -> str:
        if "/walkthrough" in start_url:
            return start_url.split("/walkthrough", 1)[0] + "/"

        return start_url.rsplit("/", 1)[0] + "/"

    def _extract_chapters(self, page, start_url: str) -> list[str]:
        links = page.locator("a").evaluate_all(
            """
            elements => elements.map(a => ({
                text: a.innerText,
                href: a.href
            }))
            """
        )

        prefix = self._chapter_prefix(start_url)
        chapters: list[str] = []
        seen: set[str] = set()

        for link in links:
            href = link["href"].split("#")[0]
            text = (link["text"] or "").strip()

            if (
                href.startswith(prefix)
                and text
                and "/File:" not in href
                and "/Image:" not in href
                and "Special:" not in href
                and "javascript:" not in href
                and href.rstrip("/") != start_url.rstrip("/")
                and href not in seen
            ):
                seen.add(href)
                chapters.append(href)

        return chapters
