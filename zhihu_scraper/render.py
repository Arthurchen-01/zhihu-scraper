"""Render normalized content to Markdown and dependency-free static HTML."""

from __future__ import annotations

import html
from collections.abc import Mapping, Sequence

from .domain import (
    Article,
    Block,
    CodeBlock,
    CodeSpan,
    Divider,
    FormulaBlock,
    Heading,
    Inline,
    InlineFormula,
    LineBreak,
    Link,
    ListBlock,
    MediaAsset,
    MediaBlock,
    Paragraph,
    Quote,
    TableBlock,
    Text,
)


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
article img,
article video {
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
table {
  border-collapse: collapse;
  display: block;
  overflow-x: auto;
}
th,
td {
  border: 1px solid currentColor;
  padding: 0.35rem 0.65rem;
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

        body = _blocks_to_markdown(article.blocks, paths=image_paths or {})
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

        body = _blocks_to_html(article.blocks, paths=image_paths or {})
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


def content_plain_text(blocks: Sequence[Block]) -> str:
    """Return searchable text without reparsing output formats."""

    parts: list[str] = []
    for block in blocks:
        if isinstance(block, (Paragraph, Heading)):
            parts.append(_inlines_plain_text(block.inlines))
        elif isinstance(block, Quote):
            parts.append(content_plain_text(block.blocks))
        elif isinstance(block, ListBlock):
            parts.extend(content_plain_text(item) for item in block.items)
        elif isinstance(block, CodeBlock):
            parts.append(block.code)
        elif isinstance(block, (FormulaBlock,)):
            parts.append(block.tex)
        elif isinstance(block, MediaBlock):
            parts.extend(part for part in (block.asset.alt_text, block.caption) if part)
        elif isinstance(block, TableBlock):
            parts.extend(block.headers)
            parts.extend(cell for row in block.rows for cell in row)
    return "\n\n".join(part for part in parts if part)


def _inlines_plain_text(inlines: Sequence[Inline]) -> str:
    parts: list[str] = []
    for inline in inlines:
        if isinstance(inline, Text):
            parts.append(inline.text)
        elif isinstance(inline, Link):
            parts.append(inline.label)
        elif isinstance(inline, CodeSpan):
            parts.append(inline.code)
        elif isinstance(inline, InlineFormula):
            parts.append(inline.tex)
        elif isinstance(inline, LineBreak):
            parts.append("\n")
    return "".join(parts)


def _blocks_to_markdown(
    blocks: Sequence[Block],
    *,
    paths: Mapping[str, str],
) -> str:
    rendered = [_block_to_markdown(block, paths=paths) for block in blocks]
    return "\n\n".join(part for part in rendered if part)


def _block_to_markdown(block: Block, *, paths: Mapping[str, str]) -> str:
    if isinstance(block, Paragraph):
        return _inlines_to_markdown(block.inlines)
    if isinstance(block, Heading):
        level = max(1, min(6, block.level))
        return f"{'#' * level} {_inlines_to_markdown(block.inlines)}"
    if isinstance(block, Quote):
        nested = _blocks_to_markdown(block.blocks, paths=paths)
        return "\n".join(f"> {line}" if line else ">" for line in nested.splitlines())
    if isinstance(block, ListBlock):
        lines: list[str] = []
        for index, item in enumerate(block.items, start=1):
            marker = f"{index}." if block.ordered else "-"
            nested = _blocks_to_markdown(item, paths=paths)
            item_lines = nested.splitlines() or [""]
            lines.append(f"{marker} {item_lines[0]}")
            lines.extend(f"   {line}" for line in item_lines[1:])
        return "\n".join(lines)
    if isinstance(block, CodeBlock):
        fence = "```"
        return f"{fence}{block.language}\n{block.code}\n{fence}"
    if isinstance(block, FormulaBlock):
        return f"$$\n{block.tex}\n$$"
    if isinstance(block, MediaBlock):
        source = _media_source(block.asset, paths=paths)
        return f"![{_escape_markdown_label(block.asset.alt_text)}]({source})"
    if isinstance(block, TableBlock):
        width = max(
            len(block.headers),
            max((len(row) for row in block.rows), default=0),
        )
        if width == 0:
            return ""
        headers = list(block.headers) or [""] * width
        headers.extend([""] * (width - len(headers)))
        lines = [
            "| " + " | ".join(_escape_table_cell(cell) for cell in headers) + " |",
            "| " + " | ".join("---" for _ in range(width)) + " |",
        ]
        for row in block.rows:
            cells = [*row, *([""] * (width - len(row)))]
            lines.append("| " + " | ".join(_escape_table_cell(cell) for cell in cells) + " |")
        return "\n".join(lines)
    if isinstance(block, Divider):
        return "---"
    raise TypeError(f"Unsupported block type: {type(block).__name__}")


def _inlines_to_markdown(inlines: Sequence[Inline]) -> str:
    rendered: list[str] = []
    for inline in inlines:
        if isinstance(inline, Text):
            value = inline.text
            if inline.bold:
                value = f"**{value}**"
            if inline.italic:
                value = f"*{value}*"
            rendered.append(value)
        elif isinstance(inline, Link):
            rendered.append(f"[{_escape_markdown_label(inline.label)}]({inline.url})")
        elif isinstance(inline, CodeSpan):
            fence = "``" if "`" in inline.code else "`"
            rendered.append(f"{fence}{inline.code}{fence}")
        elif isinstance(inline, InlineFormula):
            rendered.append(f"${inline.tex}$")
        elif isinstance(inline, LineBreak):
            rendered.append("  \n")
    return "".join(rendered)


def _blocks_to_html(
    blocks: Sequence[Block],
    *,
    paths: Mapping[str, str],
    indent: str = "      ",
) -> str:
    return "\n".join(
        _block_to_html(block, paths=paths, indent=indent)
        for block in blocks
    )


def _block_to_html(
    block: Block,
    *,
    paths: Mapping[str, str],
    indent: str,
) -> str:
    if isinstance(block, Paragraph):
        return f"{indent}<p>{_inlines_to_html(block.inlines)}</p>"
    if isinstance(block, Heading):
        level = max(1, min(6, block.level))
        return f"{indent}<h{level}>{_inlines_to_html(block.inlines)}</h{level}>"
    if isinstance(block, Quote):
        nested = _blocks_to_html(block.blocks, paths=paths, indent=f"{indent}  ")
        return f"{indent}<blockquote>\n{nested}\n{indent}</blockquote>"
    if isinstance(block, ListBlock):
        tag = "ol" if block.ordered else "ul"
        items = []
        for item in block.items:
            nested = _blocks_to_html(item, paths=paths, indent=f"{indent}    ")
            items.append(f"{indent}  <li>\n{nested}\n{indent}  </li>")
        return f"{indent}<{tag}>\n" + "\n".join(items) + f"\n{indent}</{tag}>"
    if isinstance(block, CodeBlock):
        language = (
            f' class="language-{html.escape(block.language, quote=True)}"'
            if block.language
            else ""
        )
        return (
            f"{indent}<pre><code{language}>"
            f"{html.escape(block.code)}</code></pre>"
        )
    if isinstance(block, FormulaBlock):
        tex = html.escape(block.tex)
        return f'{indent}<div class="math-display" data-tex="{tex}">{tex}</div>'
    if isinstance(block, MediaBlock):
        source = html.escape(_media_source(block.asset, paths=paths), quote=True)
        alt = html.escape(block.asset.alt_text, quote=True)
        if block.asset.kind.value == "video":
            media_html = f'<video controls src="{source}"></video>'
        else:
            media_html = f'<img src="{source}" alt="{alt}">'
        if block.caption:
            caption = html.escape(block.caption)
            return (
                f"{indent}<figure>{media_html}"
                f"<figcaption>{caption}</figcaption></figure>"
            )
        return f"{indent}<figure>{media_html}</figure>"
    if isinstance(block, TableBlock):
        head = ""
        if block.headers:
            cells = "".join(f"<th>{html.escape(cell)}</th>" for cell in block.headers)
            head = f"<thead><tr>{cells}</tr></thead>"
        rows = "".join(
            "<tr>" + "".join(f"<td>{html.escape(cell)}</td>" for cell in row) + "</tr>"
            for row in block.rows
        )
        return f"{indent}<table>{head}<tbody>{rows}</tbody></table>"
    if isinstance(block, Divider):
        return f"{indent}<hr>"
    raise TypeError(f"Unsupported block type: {type(block).__name__}")


def _inlines_to_html(inlines: Sequence[Inline]) -> str:
    rendered: list[str] = []
    for inline in inlines:
        if isinstance(inline, Text):
            value = html.escape(inline.text)
            if inline.bold:
                value = f"<strong>{value}</strong>"
            if inline.italic:
                value = f"<em>{value}</em>"
            rendered.append(value)
        elif isinstance(inline, Link):
            label = html.escape(inline.label)
            url = html.escape(inline.url, quote=True)
            rendered.append(f'<a href="{url}">{label}</a>')
        elif isinstance(inline, CodeSpan):
            rendered.append(f"<code>{html.escape(inline.code)}</code>")
        elif isinstance(inline, InlineFormula):
            tex = html.escape(inline.tex)
            rendered.append(f'<span class="math-inline" data-tex="{tex}">{tex}</span>')
        elif isinstance(inline, LineBreak):
            rendered.append("<br>")
    return "".join(rendered)


def _media_source(asset: MediaAsset, *, paths: Mapping[str, str]) -> str:
    if asset.archive_path:
        return asset.archive_path
    for rendition in asset.renditions:
        if local := paths.get(rendition.source_url):
            return local
    return asset.renditions[0].source_url if asset.renditions else ""


def _escape_markdown_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")


def _escape_table_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", "<br>")
