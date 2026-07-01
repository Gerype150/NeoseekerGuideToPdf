from .config import load_config
from .workflow import build_guide_html, build_pdf


def run_build_guide(config_path: str = "config.json") -> None:
    config = load_config(config_path)
    build_guide_html(config)


def run_generate_pdf(config_path: str = "config.json") -> None:
    config = load_config(config_path)
    build_pdf(config)
