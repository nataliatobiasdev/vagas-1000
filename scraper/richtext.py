"""HTML de vaga -> HTML limpo e seguro para guardar e exibir offline.

As descrições vêm de terceiros (Greenhouse, Lever, Gupy...). Antes de gravar no banco passam por uma lista de
permissões: só tags de texto, sem atributos (exceto `href` http/https/mailto em links), sem script, estilo,
iframe, formulário nem imagem (imagem faria o painel chamar a rede ao abrir). O painel ainda exibe esse HTML
dentro de um elemento isolado, então uma falha aqui não vira execução de código.
"""
from __future__ import annotations

import html as html_lib
import re

from bs4 import BeautifulSoup, Comment, NavigableString

ALLOWED = {"p", "br", "ul", "ol", "li", "strong", "b", "em", "i", "u", "a", "blockquote", "pre", "code",
           "table", "thead", "tbody", "tr", "th", "td", "hr", "h3", "h4", "h5", "sup", "sub", "span", "div"}
HEADINGS = {"h1": "h3", "h2": "h3", "h3": "h3", "h4": "h4", "h5": "h5", "h6": "h5"}
DROP = {"script", "style", "iframe", "object", "embed", "form", "input", "button", "select", "textarea", "svg",
        "video", "audio", "noscript", "link", "meta", "head", "title"}
SAFE_HREF = re.compile(r"^(https?://|mailto:)", re.I)


def clean_html(raw: str) -> str:
    """Devolve HTML permitido. Aceita HTML escapado (`&lt;p&gt;`), como o Greenhouse envia."""
    if not raw:
        return ""
    s = raw
    if "&lt;" in s and not re.search(r"<[a-zA-Z/]", s):      # HTML escapado (&lt;p&gt;), como o Greenhouse envia
        s = html_lib.unescape(s)
    soup = BeautifulSoup(s, "lxml")
    root = soup.body or soup
    for c in root.find_all(string=lambda x: isinstance(x, Comment)):
        c.extract()
    for el in list(root.find_all(True)):
        # Filho de uma tag DROP já removida (ex.: <path> dentro de <svg>): sai da árvore junto com o pai e não pode mais
        # ser desempacotado ("Cannot replace an element with its contents when that element is not part of a tree").
        if getattr(el, "decomposed", False) or el.parent is None:
            continue
        name = el.name
        if name in DROP:
            el.decompose()
        elif name == "img":                                 # sem rede ao abrir: fica o texto alternativo
            alt = (el.get("alt") or "").strip()
            el.replace_with(NavigableString(alt) if alt else "")
        elif name in HEADINGS:
            el.name = HEADINGS[name]
            el.attrs = {}
        elif name in ALLOWED:
            href = el.get("href") if name == "a" else None
            el.attrs = {}
            if name == "a" and href and SAFE_HREF.match(href.strip()):
                el.attrs = {"href": href.strip(), "target": "_blank", "rel": "noopener noreferrer"}
        else:
            el.unwrap()                                     # tag desconhecida: mantém só o conteúdo
    out = _tidy("".join(str(x) for x in root.contents))
    return out


def _tidy(h: str) -> str:
    h = re.sub(r"(?:<br\s*/?>\s*){3,}", "<br/><br/>", h)
    h = re.sub(r"<(p|div|span|li|b|strong|em|i|u)>\s*(?:&nbsp;|\xa0|<br\s*/?>)*\s*</\1>", "", h)
    h = re.sub(r"\n{3,}", "\n\n", h)
    return h.strip()


def html_to_text(h: str) -> str:
    """HTML (já limpo ou não) -> texto corrido, com quebras de parágrafo."""
    if not h:
        return ""
    soup = BeautifulSoup(h, "lxml")
    for br in soup.find_all("br"):
        br.replace_with("\n")
    for li in soup.find_all("li"):
        li.insert_before("• ")
    for blk in soup.find_all(["p", "div", "li", "h3", "h4", "h5", "tr", "blockquote", "pre"]):
        blk.append("\n")
    text = soup.get_text("").replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    return "\n".join(line.strip() for line in text.splitlines()).strip()


def section(title: str, raw_html: str) -> dict | None:
    """Seção rotulada (Requisitos, Benefícios...) com HTML limpo; None se vier vazia."""
    h = clean_html(raw_html)
    return {"title": title, "html": h} if h and html_to_text(h) else None
