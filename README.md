# NeoseekerToPdf

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10%2B-1f6feb?style=for-the-badge&logo=python&logoColor=white">
  <img alt="Playwright" src="https://img.shields.io/badge/Playwright-Chromium-2da44e?style=for-the-badge&logo=playwright&logoColor=white">
  <img alt="Status" src="https://img.shields.io/badge/Status-Ready_to_use-f0883e?style=for-the-badge">
</p>

> Downloads a full Neoseeker guide, cleans it up, and generates a final PDF with a table of contents.

---
Este proyecto nació porque adoro las guías físicas de los JRPG largos, y no hay guía física del Dragon Quest XI.

Como la única guía decente era por internet pero llena de anuncios y links, hice este script para tener un pdf que imprimir.

El resultado no es perfecto, ya que es una plantilla para las guías de la página web y cada una tiene estilos algo distintos, pero es suficientemente bueno para imprimir.

## What this project does

This repo automates 2 phases:

1. Builds a unified `guide.html` from a Neoseeker guide.
2. Generates a final PDF (`output`) from that HTML.

By default, if `guide.html` already exists, it is reused to save time.

---

## Requirements

- Python 3.10 or higher
- Windows (tested), Linux or macOS
- Internet connection

Python dependencies used by the project:

- `requests`
- `beautifulsoup4`
- `playwright`
- `pypdf`
- `reportlab`

---

## Quick setup

### 1) Clone the repository

```bash
git clone <YOUR_REPO_URL>
cd NeoseekerToPdf
```

### 2) Create a virtual environment

```bash
python -m venv .venv
```

Activate the environment:

- Windows (PowerShell):

```powershell
.\.venv\Scripts\Activate.ps1
```

- Linux/macOS:

```bash
source .venv/bin/activate
```

### 3) Install dependencies

```bash
pip install requests beautifulsoup4 playwright pypdf reportlab
```

### 4) Install the Playwright browser (Chromium)

```bash
python -m playwright install chromium
```

---

## Configuration

Edit `config.json`:

```json
{
  "url": "https://www.neoseeker.com/dragon-quest-xi/walkthrough",
  "output": "DQXI.pdf",
  "wait_for_cloudflare_input": false,
  "pdf_margin_top_mm": 20,
  "pdf_margin_bottom_mm": 16,
  "pdf_margin_left_mm": 14,
  "pdf_margin_right_mm": 14
}
```

### Main fields

| Field | Description |
|---|---|
| `url` | URL of the Neoseeker guide you want to download |
| `output` | Name of the final PDF |
| `wait_for_cloudflare_input` | If `true`, opens the browser and waits for manual ENTER after passing Cloudflare, in case the page requires a captcha |
| `pdf_margin_*_mm` | PDF margins in millimeters |

---

## How to download the guide and generate the PDF

### Recommended flow (automatic)

```bash
python neoseeker_to_pdf.py
```

This does the following:

1. If `guide.html` does not exist, it builds it from Neoseeker.
2. If it already exists, it reuses it.
3. Generates the PDF defined in `output`.

### Force HTML rebuild

```bash
python neoseeker_to_pdf.py --rebuild-html
```

Use this option when you change the `url` or want to refresh chapters/cache.

### Use a different configuration file

```bash
python neoseeker_to_pdf.py --config my_config.json
```

---

## Full example

1. Change `url` and `output` in `config.json`.
2. Run:

```bash
python neoseeker_to_pdf.py --rebuild-html
```

3. Wait for it to finish.
4. Open the generated PDF file (e.g., `DQXI.pdf`).

---

## Troubleshooting

### Playwright or Chromium not found

Run:

```bash
python -m playwright install chromium
```

### Cloudflare blocks chapter loading

In `config.json` set:

```json
"wait_for_cloudflare_input": true
```

Then run the script, complete the captcha in the browser, and press ENTER in the terminal.

### PDF has no changes after editing the URL

Force a rebuild:

```bash
python neoseeker_to_pdf.py --rebuild-html
```

---

## Project structure

```text
neoseeker_to_pdf.py        # Main entry point
config.json                # Configuration
guide.html                 # Generated combined HTML
src/neoseeker_to_pdf/
  neoseeker_client.py      # Chapter downloading/crawling
  html_cleaner.py          # HTML cleanup
  workflow.py              # The workflow
  pdf_generator.py         # PDF generation
```

---

## Legal notice

Downloaded content belongs to its original authors. Use this project for personal use only, respecting the terms of use and copyright of the source site.
