import os
import shutil

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
            output.extend(
                [
                    chapter_css,
                    "<section class=\"chapter\">",
                    title,
                    content,
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
    generate_pdf(config.guide_file, config.output_pdf)
