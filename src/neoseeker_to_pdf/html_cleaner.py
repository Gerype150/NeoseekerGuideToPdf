from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


_REMOVE_SELECTORS = """
    #comments,
    .comments,
    .comment,
    .sidebar,
    .ads,
    .advertisement,
    .ad-container,
    .section-vu,
    [class*='ad-'],
    [id*='ad'],
    [id*='inline']
"""


def _is_advertisement_block(tag) -> bool:
    if tag.name not in ["div", "section"]:
        return False

    attrs = tag.attrs or {}
    classes = " ".join(attrs.get("class", []))
    tag_id = attrs.get("id", "")
    text = tag.get_text(" ", strip=True).lower()

    return (
        "section-vu" in classes
        or "sticky" in classes
        or "inline" in tag_id.lower()
        or "primis" in str(tag).lower()
        or "advertisement" in text
    )


def _remove_ads(soup: BeautifulSoup) -> None:
    for element in soup.select(_REMOVE_SELECTORS):
        element.decompose()

    for script in soup.find_all("script"):
        if "primis" in str(script).lower() and script.parent:
            script.parent.decompose()

    for block in soup.find_all(_is_advertisement_block):
        block.decompose()


def clean_html(html: str, base_url: str) -> tuple[str, str, str]:
    soup = BeautifulSoup(html, "html.parser")

    _remove_ads(soup)

    title = soup.select_one("#page-title")
    content = soup.select_one("#wiki-content")

    if not content:
        return "", "", ""

    horizontal_rules = content.find_all("hr")
    if horizontal_rules:
        horizontal_rules[-1].decompose()

    clearfix = content.select(".clearfix")
    if clearfix:
        clearfix[-1].decompose()

    for anchor in content.find_all("a"):
        if anchor.find("img"):
            anchor.unwrap()

    # Remove embedded videos (YouTube/Vimeo and similar iframe embeds).
    for iframe in content.find_all("iframe"):
        iframe.decompose()

    # Remove now-empty wrappers left by embed cleanup.
    for paragraph in content.find_all("p"):
        if not paragraph.get_text("", strip=True) and not paragraph.find(["img", "table"]):
            paragraph.decompose()

    css = _download_stylesheets(soup, base_url)

    for block in content.find_all(_is_advertisement_block):
        block.decompose()

    return str(title) if title else "", content.decode_contents(), css


def _download_stylesheets(soup: BeautifulSoup, base_url: str) -> str:
    css = ""

    for link in soup.select('link[rel="stylesheet"]'):
        href = link.get("href")
        if not href:
            continue

        css_url = urljoin(base_url, href)
        try:
            response = requests.get(
                css_url,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=20,
            )
            if response.ok:
                css += '<style type="text/css">\n' + response.text + "\n</style>\n"
        except Exception:
            continue

    return css
