import argparse
import os

from src.neoseeker_to_pdf.config import load_config
from src.neoseeker_to_pdf.runner import run_build_guide, run_generate_pdf


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Construye el HTML de Neoseeker y genera el PDF. "
            "Si guide.html ya existe, por defecto lo reutiliza."
        )
    )
    parser.add_argument(
        "--config",
        default="config.json",
        help="Ruta al archivo de configuracion.",
    )
    parser.add_argument(
        "--rebuild-html",
        action="store_true",
        help="Fuerza reconstruccion del HTML aunque ya exista.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    config = load_config(args.config)

    should_build_html = args.rebuild_html or not os.path.exists(config.guide_file)

    if should_build_html:
        run_build_guide(args.config)
    else:
        print(f"Reutilizando HTML existente: {config.guide_file}")

    run_generate_pdf(args.config)