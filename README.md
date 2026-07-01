# NeoseekerToPdf

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10%2B-1f6feb?style=for-the-badge&logo=python&logoColor=white">
  <img alt="Playwright" src="https://img.shields.io/badge/Playwright-Chromium-2da44e?style=for-the-badge&logo=playwright&logoColor=white">
  <img alt="Estado" src="https://img.shields.io/badge/Estado-Listo_para_usar-f0883e?style=for-the-badge">
</p>

> Descarga una guia completa de Neoseeker, la limpia y genera un PDF final con tabla de contenidos.

---

## Qué hace este proyecto

Este proyecto nació porque adoro las guías físicas de los JRPG largos, y no hay guía física del Dragon Quest XI.
Como la única guía decente era por internet pero llena de anuncios y links, hice este script para tener un pdf que imprimir.
El resultado no es perfecto, ya que es una plantilla para las guías de la página web y cada una tiene estilos algo distintos, pero es suficientemente bueno para imprimir.

Este repo automatiza 2 fases:

1. Construye un `guide.html` unificado desde una guía de Neoseeker.
2. Genera un PDF final (`output`) a partir de ese HTML.

Por defecto, si `guide.html` ya existe, lo reutiliza para ahorrar tiempo.

---

## Requisitos

- Python 3.10 o superior
- Windows (probado), Linux o macOS
- Conexión a internet

Dependencias Python usadas por el proyecto:

- `requests`
- `beautifulsoup4`
- `playwright`
- `pypdf`
- `reportlab`

---

## Instalación rápida

### 1) Clonar el repositorio

```bash
git clone <URL_DE_TU_REPO>
cd NeoseekerToPdf
```

### 2) Crear entorno virtual

```bash
python -m venv .venv
```

Activar entorno:

- Windows (PowerShell):

```powershell
.\.venv\Scripts\Activate.ps1
```

- Linux/macOS:

```bash
source .venv/bin/activate
```

### 3) Instalar dependencias

```bash
pip install requests beautifulsoup4 playwright pypdf reportlab
```

### 4) Instalar navegador de Playwright (Chromium)

```bash
python -m playwright install chromium
```

---

## Configuración

Edita `config.json`:

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

### Campos principales

| Campo | Descripcion |
|---|---|
| `url` | URL de la guía de Neoseeker que quieres descargar |
| `output` | Nombre del PDF final |
| `wait_for_cloudflare_input` | Si es `true`, abre navegador y espera ENTER manual tras pasar Cloudflare, por si la página te pide captcha |
| `pdf_margin_*_mm` | Márgenes del PDF en milímetros |

---

## Cómo descargar la guia y generar el PDF

### Flujo recomendado (automático)

```bash
python neoseeker_to_pdf.py
```

Esto hace lo siguiente:

1. Si `guide.html` no existe, lo construye desde Neoseeker.
2. Si ya existe, lo reutiliza.
3. Genera el PDF definido en `output`.

### Forzar reconstrucción del HTML

```bash
python neoseeker_to_pdf.py --rebuild-html
```

Usa esta opción cuando cambies la `url` o quieras refrescar capítulos/cache.

### Usar otro archivo de configuración

```bash
python neoseeker_to_pdf.py --config mi_config.json
```

---

## Ejemplo completo

1. Cambia `url` y `output` en `config.json`.
2. Ejecuta:

```bash
python neoseeker_to_pdf.py --rebuild-html
```

3. Espera a que termine.
4. Abre el archivo PDF generado (por ejemplo, `DQXI.pdf`).

---

## Solución de problemas

### No encuentra Playwright o Chromium

Ejecuta:

```bash
python -m playwright install chromium
```

### Cloudflare bloquea la carga de capítulos

En `config.json` pon:

```json
"wait_for_cloudflare_input": true
```

Luego ejecuta el script, completa el captcha en el navegador y pulsa ENTER en terminal.

### El PDF sale sin cambios tras editar la URL

Fuerza reconstrucción:

```bash
python neoseeker_to_pdf.py --rebuild-html
```

---

## Estructura principal

```text
neoseeker_to_pdf.py        # Punto de entrada principal
config.json                # Configuración
guide.html                 # HTML combinado generado
src/neoseeker_to_pdf/
  neoseeker_client.py      # Descarga/crawling de capítulos
  html_cleaner.py          # Limpieza del HTML
  workflow.py              # El flujo
  pdf_generator.py         # Generación de PDF
```

---

## Nota legal

El contenido descargado pertenece a sus autores originales. Usa este proyecto de forma personal y respetando los términos de uso y copyright del sitio fuente.
