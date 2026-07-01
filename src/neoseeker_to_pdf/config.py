import json
from dataclasses import dataclass


@dataclass(frozen=True)
class AppConfig:
    url: str
    output_pdf: str
    retries: int = 3
    cache_dir: str = "cache"
    chrome_profile_dir: str = "chrome_profile"
    cleanup_runtime_dirs: bool = True
    guide_file: str = "guide.html"
    static_css_file: str = "neoseeker.css"
    wait_for_cloudflare_input: bool = False
    pdf_margin_top_mm: float = 20.0
    pdf_margin_bottom_mm: float = 16.0
    pdf_margin_left_mm: float = 14.0
    pdf_margin_right_mm: float = 14.0


def load_config(path: str = "config.json") -> AppConfig:
    with open(path, encoding="utf-8") as file:
        data = json.load(file)

    return AppConfig(
        url=data["url"],
        output_pdf=data["output"],
        retries=data.get("retries", 3),
        cache_dir=data.get("cache_dir", "cache"),
        chrome_profile_dir=data.get("chrome_profile_dir", "chrome_profile"),
        cleanup_runtime_dirs=data.get("cleanup_runtime_dirs", True),
        guide_file=data.get("guide_file", "guide.html"),
        static_css_file=data.get("static_css_file", "neoseeker.css"),
        wait_for_cloudflare_input=data.get("wait_for_cloudflare_input", False),
        pdf_margin_top_mm=data.get("pdf_margin_top_mm", 20.0),
        pdf_margin_bottom_mm=data.get("pdf_margin_bottom_mm", 16.0),
        pdf_margin_left_mm=data.get("pdf_margin_left_mm", 14.0),
        pdf_margin_right_mm=data.get("pdf_margin_right_mm", 14.0),
    )
