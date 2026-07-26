"""Markdown and static HTML renderers for normalized archive content."""

from __future__ import annotations

import html
import re
from collections.abc import Mapping, Sequence

from bs4 import BeautifulSoup, Tag
from markdownify import markdownify

from .domain import Article, ContentBlock, Paragraph, RichText


ARCHIVE_CSS = """\
:root {
  color-scheme: light dark;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  line-height: 1.75;
}
body {
  margin: 0 auto;
  max-width: 860px;
  padding: 2rem 1.25rem 5rem;
}
article img {
  height: auto;
  max-width: 100%;
}
pre {
  overflow-x: auto;
  padding: 1rem;
}
.metadata {
  opacity: 0.75;
}
.math-inline,
.math-display {
  font-family: "STIX Two Math", "Cambria Math", serif;
}
.math-display {
  margin: 1rem 0;
  overflow-x: auto;
  padding: 0.75rem;
  text-align: center;
}
"""


class MarkdownRenderer:
    def render(
        self,
        article: Article,
        *,
        image_paths: Mapping[str, str] | None = None,
    ) -> str:
        metadata = [
            f"# {article.title}",
            "",
            f"> 作者：{article.author.name}",
            f"> 知乎原文：[{article.source_url}]({article.source_url})",
        ]
        if article.published_at is not None:
            metadata.append(f"> 发布时间：{article.published_at.date().isoformat()}")

        body = "\n\n".join(
            _block_to_markdown(block, image_paths=image_paths or {})
            for block in article.blocks
        )
        return "\n".join([*metadata, "", body.strip(), ""])


class HtmlRenderer:
    def render(
        self,
        article: Article,
        *,
        image_paths: Mapping[str, str] | None = None,
    ) -> str:
        title = html.escape(article.title)
        author = html.escape(article.author.name)
        source_url = html.escape(article.source_url, quote=True)
        published = ""
        if article.published_at is not None:
            date = html.escape(article.published_at.date().isoformat())
            published = f"\n        <p>发布时间：{date}</p>"

        body = "\n".join(
            _block_to_html(block, image_paths=image_paths or {})
            for block in article.blocks
        )
        return (
            "<!doctype html>\n"
            '<html lang="zh-CN">\n'
            "  <head>\n"
            '    <meta charset="utf-8">\n'
            '    <meta name="viewport" content="width=device-width, initial-scale=1">\n'
            f"    <title>{title}</title>\n"
            '    <link rel="stylesheet" href="assets/archive.css">\n'
            "  </head>\n"
            "  <body>\n"
            "    <article>\n"
            f"      <h1>{title}</h1>\n"
            '      <section class="metadata">\n'
            f"        <p>作者：{author}</p>{published}\n"
            f'        <p><a href="{source_url}">知乎原文</a></p>\n'
            "      </section>\n"
            f"{body}\n"
            "    </article>\n"
            "  </body>\n"
            "</html>\n"
        )

    @staticmethod
    def assets() -> Mapping[str, str]:
        return {"archive.css": ARCHIVE_CSS}


def content_plain_text(blocks: Sequence[ContentBlock]) -> str:
    text_parts: list[str] = []
    for block in blocks:
        if isinstance(block, Paragraph):
            text_parts.append(block.text)
        else:
            soup = BeautifulSoup(block.html, "html.parser")
            text_parts.append(soup.get_text("\n", strip=True))
    return "\n\n".join(part for part in text_parts if part)


def _block_to_markdown(
    block: ContentBlock,
    *,
    image_paths: Mapping[str, str],
) -> str:
    if isinstance(block, Paragraph):
        return block.text

    soup = _clean_fragment(block.html, image_paths=image_paths, formulas_as_html=False)

    def code_language(element: Tag) -> str:
        code = element.find("code") if element.name == "pre" else element
        classes = code.get("class", []) if isinstance(code, Tag) else []
        return next(
            (
                css_class.removeprefix("language-")
                for css_class in classes
                if css_class.startswith("language-")
            ),
            "",
        )

    rendered = markdownify(
        str(soup),
        heading_style="ATX",
        bullets="-",
        code_language_callback=code_language,
    )
    formula_store = getattr(soup, "_zhihu_formula_store", {})
    for placeholder, (formula, is_display) in formula_store.items():
        replacement = (
            f"\n\n$$\n{formula}\n$$\n\n"
            if is_display
            else f"${formula}$"
        )
        rendered = rendered.replace(placeholder, replacement)
    rendered = re.sub(r"\n{3,}", "\n\n", rendered)
    return rendered.strip()


def _block_to_html(
    block: ContentBlock,
    *,
    image_paths: Mapping[str, str],
) -> str:
    if isinstance(block, Paragraph):
        return f"      <p>{html.escape(block.text)}</p>"
    soup = _clean_fragment(block.html, image_paths=image_paths, formulas_as_html=True)
    return "\n".join(f"      {line}" for line in str(soup).splitlines())


def _clean_fragment(
    fragment: str,
    *,
    image_paths: Mapping[str, str],
    formulas_as_html: bool,
) -> BeautifulSoup:
    soup = BeautifulSoup(fragment, "html.parser")
    formula_store: dict[str, tuple[str, bool]] = {}

    for unwanted in soup.find_all(
        ["script", "style", "noscript", "iframe", "object", "embed"]
    ):
        unwanted.decompose()

    for tag in soup.find_all(True):
        for attribute in tuple(tag.attrs):
            if attribute.casefold().startswith("on") or attribute.casefold() == "style":
                del tag.attrs[attribute]

    formula_nodes = [
        *soup.select("span.ztext-math"),
        *soup.select("img.ztext-math"),
    ]
    for index, node in enumerate(formula_nodes):
        formula = _extract_formula(node)
        if not formula:
            continue
        is_display = _is_display_formula(node, formula)
        formula = _normalize_formula(formula)
        if formulas_as_html:
            replacement_name = "div" if is_display else "span"
            replacement = soup.new_tag(replacement_name)
            replacement["class"] = "math-display" if is_display else "math-inline"
            replacement["data-tex"] = formula
            replacement.string = formula
        else:
            placeholder = f"ZHFORMULA{index}X"
            formula_store[placeholder] = (formula, is_display)
            replacement = soup.new_tag("var")
            replacement.string = placeholder
        node.replace_with(replacement)

    for image in soup.find_all("img"):
        source_url = _image_source(image)
        if not source_url:
            image.decompose()
            continue
        image["src"] = image_paths.get(source_url, source_url)
        for attribute in (
            "data-actualsrc",
            "data-original",
            "srcset",
            "data-default-watermark-src",
        ):
            image.attrs.pop(attribute, None)

    setattr(soup, "_zhihu_formula_store", formula_store)
    return soup


def _extract_formula(node: Tag) -> str:
    for attribute in ("data-tex", "data-formula", "alt"):
        value = node.get(attribute)
        if value:
            return str(value).strip()
    return ""


def _normalize_formula(formula: str) -> str:
    normalized = formula.strip()
    if normalized.startswith(r"\[") and normalized.endswith(r"\]"):
        normalized = normalized[2:-2].strip()
    return normalized


def _is_display_formula(node: Tag, formula: str) -> bool:
    stripped = formula.strip()
    if stripped.startswith(r"\[") and stripped.endswith(r"\]"):
        return True
    if re.search(r"\\begin\{[a-zA-Z*]+\}", stripped):
        return True
    parent = node.parent
    return bool(
        parent
        and parent.name in {"p", "div", "figure"}
        and not parent.get_text(" ", strip=True)
    )


def _image_source(image: Tag) -> str:
    for attribute in ("data-original", "data-actualsrc", "src"):
        value = image.get(attribute)
        if value and not str(value).startswith("data:"):
            return str(value)
    return ""
