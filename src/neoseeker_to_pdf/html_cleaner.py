from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


def clean_html(html: str, base_url: str) -> tuple[str, str, str]:
    soup = BeautifulSoup(html, "html.parser")

    for element in soup.find_all("script"):
        if "primis" in str(element).lower() and element.parent:
            element.parent.decompose()

    for element in soup.select(
        """
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
    ):
        element.decompose()

    for div in soup.find_all("div"):
        if "Advertisement" in div.get_text(" ", strip=True):
            div.decompose()

    for element in soup.find_all(
        lambda tag: tag.name in ["div", "section"] and "Advertisement" in tag.get_text()
    ):
        element.decompose()

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

    css = _download_stylesheets(soup, base_url)

    for div in content.find_all("div"):
        attrs = div.attrs or {}
        classes = " ".join(attrs.get("class", []))
        div_id = attrs.get("id", "")
        text = div.get_text(" ", strip=True).lower()

        if (
            "section-vu" in classes
            or "sticky" in classes
            or "inline" in div_id.lower()
            or "primis" in str(div).lower()
            or "advertisement" in text
        ):
            div.decompose()

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
