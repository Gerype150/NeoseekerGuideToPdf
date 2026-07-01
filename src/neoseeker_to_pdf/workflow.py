import os
import shutil
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

from .config import AppConfig
from .html_cleaner import clean_html
from .neoseeker_client import NeoseekerClient
from .pdf_generator import generate_pdf
from .storage import read_text, write_text


def _remove_runtime_dirs(paths: list[str]) -> None:
    for path in paths:
        if not path:
            continue
        if os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)


def _normalize_guide_url(url: str) -> str:
    parts = urlsplit(url)
    path = parts.path.rstrip("/")
    return urlunsplit((parts.scheme, parts.netloc, path, "", ""))


def _rewrite_internal_links(content_html: str, current_url: str, chapter_map: dict[str, str]) -> str:
    soup = BeautifulSoup(content_html, "html.parser")

    for anchor in soup.find_all("a"):
        href = anchor.get("href")
        if not href:
            continue

        absolute = _normalize_guide_url(urljoin(current_url, href))
        target_anchor = chapter_map.get(absolute)
        if target_anchor:
            anchor["href"] = f"#{target_anchor}"

    return soup.decode_contents()


def build_guide_html(config: AppConfig) -> str:
    runtime_dirs = [config.cache_dir, config.chrome_profile_dir]

    if config.cleanup_runtime_dirs:
        _remove_runtime_dirs(runtime_dirs)

    try:
        client = NeoseekerClient(
            cache_dir=config.cache_dir,
            retries=config.retries,
            profile_dir=config.chrome_profile_dir,
            wait_for_cloudflare_input=config.wait_for_cloudflare_input,
        )
        chapters = client.get_chapter_urls(config.url)
        print(f"{len(chapters)} capitulos encontrados")

        chapter_anchor_map = {
            _normalize_guide_url(chapter_url): f"chapter-{index:03d}"
            for index, chapter_url in enumerate(chapters, start=1)
        }

        css = read_text(config.static_css_file)

        output = [
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            "<meta charset=\"utf-8\">",
            "<style>",
            css,
            "</style>",
            "</head>",
            "<body>",
            "<h1>Neoseeker Walkthrough</h1>",
        ]

        for index, chapter_url in enumerate(chapters, start=1):
            print(f"Procesando {index}/{len(chapters)}")

            raw_html = client.get_page_html(chapter_url)
            if not raw_html:
                continue

            title, content, chapter_css = clean_html(raw_html, chapter_url)
            chapter_anchor = chapter_anchor_map[_normalize_guide_url(chapter_url)]
            rewritten_content = _rewrite_internal_links(content, chapter_url, chapter_anchor_map)
            output.extend(
                [
                    chapter_css,
                    f"<section class=\"chapter\" id=\"{chapter_anchor}\">",
                    title,
                    rewritten_content,
                    "</section>",
                ]
            )

        output.extend(["</body>", "</html>"])
        write_text(config.guide_file, "\n".join(output))
        print("HTML generado:", config.guide_file)

        return config.guide_file
    finally:
        if config.cleanup_runtime_dirs:
            _remove_runtime_dirs(runtime_dirs)


def build_pdf(config: AppConfig) -> None:
    generate_pdf(
        config.guide_file,
        config.output_pdf,
        margin_top_mm=config.pdf_margin_top_mm,
        margin_bottom_mm=config.pdf_margin_bottom_mm,
        margin_left_mm=config.pdf_margin_left_mm,
        margin_right_mm=config.pdf_margin_right_mm,
    )
