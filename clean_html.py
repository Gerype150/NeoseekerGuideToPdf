from bs4 import BeautifulSoup


from bs4 import BeautifulSoup


def clean_html(html):

    soup = BeautifulSoup(
        html,
        "html.parser"
    )


    # eliminar basura real
    for e in soup.select(
        """
        script,
        iframe,
        header,
        nav,
        footer,
        .sidebar,
        #comments,
        .comments,
        .comment,
        .user-comments
        """
    ):
        e.decompose()


    # anuncios
    for e in soup.select(
        """
        .ads,
        .advertisement,
        .ad-container,
        [class*="ad"],
        [id*="ad"]
        """
    ):
        e.decompose()


    # mantener imágenes pero quitar link envolvente
    for a in soup.find_all("a"):
        if a.find("img"):
            a.unwrap()


    title = (
        soup.title.get_text()
        if soup.title
        else "Neoseeker"
    )


    return title, str(soup.body)