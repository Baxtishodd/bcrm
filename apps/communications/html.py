import html
from html.parser import HTMLParser
from urllib.parse import urlparse

ALLOWED_TAGS = {
    "a",
    "b",
    "blockquote",
    "br",
    "div",
    "em",
    "i",
    "li",
    "ol",
    "p",
    "strong",
    "u",
    "ul",
}
VOID_TAGS = {"br"}


def _safe_href(value):
    value = value.strip()
    parsed = urlparse(value)
    if parsed.scheme.lower() not in {"http", "https", "mailto"}:
        return ""
    return value


class _EmailHTMLSanitizer(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag not in ALLOWED_TAGS:
            return
        attributes = ""
        if tag == "a":
            href = _safe_href(dict(attrs).get("href", ""))
            if href:
                attributes = (
                    f' href="{html.escape(href, quote=True)}"'
                    ' target="_blank" rel="noopener noreferrer"'
                )
        self.parts.append(f"<{tag}{attributes}>")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in ALLOWED_TAGS and tag not in VOID_TAGS:
            self.parts.append(f"</{tag}>")

    def handle_data(self, data):
        self.parts.append(html.escape(data))


def sanitize_email_html(value):
    sanitizer = _EmailHTMLSanitizer()
    sanitizer.feed(value or "")
    sanitizer.close()
    return "".join(sanitizer.parts).strip()
