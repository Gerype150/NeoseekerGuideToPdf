import os
import re
import shutil
from html import escape
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


def _extract_title_text(title_html: str, index: int) -> str:
    soup = BeautifulSoup(title_html, "html.parser")
    text = soup.get_text(" ", strip=True)
    if not text:
        return f"Capitulo {index}"

    # Remove the repeated title-prefix based on the <strong> text in the heading block.
    strong = soup.find("strong")
    strong_text = strong.get_text(" ", strip=True) if strong else ""
    if strong_text:
        strong_pattern = re.escape(strong_text)
        text = re.sub(
            rf"^{strong_pattern}\s*[-:|]?\s*",
            "",
            text,
            flags=re.IGNORECASE,
        ).strip()

    return text or f"Capitulo {index}"


def build_guide_html(config: AppConfig) -> str:
    runtime_dirs = [config.cache_dir, config.chrome_profile_dir]

    if config.cleanup_runtime_dirs:
        _remove_runtime_dirs(runtime_dirs)

    try:
        client = NeoseekerClient(
            retries=config.retries,
            profile_dir=config.chrome_profile_dir,
            wait_for_cloudflare_input=config.wait_for_cloudflare_input,
        )
        chapters = client.get_chapter_urls(config.url)
        print(f"{len(chapters)} chapters detected.")

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
        ]
        toc_entries: list[tuple[str, str]] = []
        chapter_sections: list[str] = []

        for index, chapter_url in enumerate(chapters, start=1):
            print(f"Processing {index}/{len(chapters)}")

            raw_html = client.get_page_html(chapter_url)
            if not raw_html:
                continue

            title, content, chapter_css = clean_html(raw_html, chapter_url)
            chapter_anchor = chapter_anchor_map[_normalize_guide_url(chapter_url)]
            rewritten_content = _rewrite_internal_links(content, chapter_url, chapter_anchor_map)
            chapter_title = _extract_title_text(title, index)
            toc_entries.append((chapter_anchor, chapter_title))
            chapter_sections.extend(
                [
                    chapter_css,
                    f"<section class=\"chapter\" id=\"{chapter_anchor}\">",
                    title,
                    rewritten_content,
                    "</section>",
                ]
            )

        output.extend(
            [
                "<section class=\"toc\" id=\"table-of-contents\" style=\"page-break-after: always;\">",
                "<h1>Index</h1>",
                "<style>",
                ".toc-list { list-style: none; padding: 0; margin: 0; }",
                ".toc-item { margin: 0.1rem 0; padding: 0.1rem 0.35rem; border-radius: 2px; }",
                ".toc-item:nth-child(odd) { background-color: rgba(34, 42, 58, 0.04); }",
                ".toc-link {",
                "  color: inherit;",
                "  text-decoration: none;",
                "  font-weight: 700;",
                "  display: grid;",
                "  grid-template-columns: 3ch auto 1fr auto;",
                "  align-items: baseline;",
                "  column-gap: 0.35rem;",
                "}",
                ".toc-index { min-width: 2ch; text-align: right; font-variant-numeric: tabular-nums; }",
                ".toc-title { margin-left: 1.15rem; }",
                ".toc-dots { border-bottom: 1px dotted rgba(25, 25, 25, 0.45); margin: 0 0.25rem 0.25rem 0.2rem; }",
                ".toc-page { min-width: 3ch; text-align: right; font-variant-numeric: tabular-nums; }",
                "</style>",
                "<ol class=\"toc-list\">",
            ]
        )
        for index, (chapter_anchor, chapter_title) in enumerate(toc_entries, start=1):
            output.append(
                (
                    f"<li class=\"toc-item\" data-chapter-anchor=\"{chapter_anchor}\">"
                    f"<a class=\"toc-link\" href=\"#{chapter_anchor}\">"
                    f"<span class=\"toc-index\">{index:02d}</span>"
                    f"<span class=\"toc-title\">{escape(chapter_title)}</span>"
                    "<span class=\"toc-dots\"></span>"
                    "<span class=\"toc-page\">--</span>"
                    "</a>"
                    "</li>"
                )
            )
        output.extend(["</ol>", "</section>"])
        output.extend(chapter_sections)

        output.extend(["</body>", "</html>"])
        write_text(config.guide_file, "\n".join(output))
        print("HTML generated:", config.guide_file)

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
