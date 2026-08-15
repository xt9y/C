#!/usr/bin/env python3
"""Render every Markdown table as an SVG while preserving the original table."""

import argparse
import html
import re
from pathlib import Path

SEP_CELL = re.compile(r"^:?-{3,}:?$")


def split_row(line: str) -> list[str]:
    text = line.strip()
    if text.startswith("|"):
        text = text[1:]
    if text.endswith("|"):
        text = text[:-1]
    cells = []
    current = []
    escaped = False
    for char in text:
        if escaped:
            current.append(char)
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == "|":
            cells.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    cells.append("".join(current).strip())
    return cells


def is_separator(line: str) -> bool:
    if "|" not in line:
        return False
    cells = split_row(line)
    return bool(cells) and all(SEP_CELL.fullmatch(cell.replace(" ", "")) for cell in cells)


def plain(text: str) -> str:
    text = text.replace("`", "").replace("**", "").replace("__", "")
    text = re.sub(r"<br\s*/?>", " / ", text, flags=re.I)
    text = re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", text)
    return html.unescape(text)


def nearest_title(lines: list[str], index: int, fallback: str) -> str:
    for pos in range(index - 1, -1, -1):
        value = lines[pos].strip()
        if not value:
            continue
        if value.startswith("#"):
            return value.lstrip("#").strip()
        break
    return fallback


def fit(text: str, width: int) -> str:
    max_chars = max(8, int((width - 22) / 7.2))
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1] + "…"


def render_svg(path: Path, title: str, rows: list[list[str]]) -> None:
    columns = max(len(row) for row in rows)
    normalized = [row + [""] * (columns - len(row)) for row in rows]
    clean = [[plain(cell) for cell in row] for row in normalized]

    widths = []
    for column in range(columns):
        longest = max(len(row[column]) for row in clean)
        widths.append(min(340, max(96, longest * 7 + 28)))

    margin = 20
    title_h = 52
    row_h = 36
    width = sum(widths) + margin * 2
    height = title_h + row_h * len(clean) + margin

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" rx="8" fill="#ffffff"/>',
        f'<text x="{margin}" y="31" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif" font-size="18" font-weight="700" fill="#1f2328">{html.escape(title)}</text>',
    ]

    y = title_h
    for row_index, row in enumerate(clean):
        x = margin
        fill = "#f6f8fa" if row_index == 0 else "#ffffff"
        weight = "600" if row_index == 0 else "400"
        for column, cell in enumerate(row):
            cell_w = widths[column]
            out.append(
                f'<rect x="{x}" y="{y}" width="{cell_w}" height="{row_h}" fill="{fill}" stroke="#d0d7de"/>'
            )
            shown = fit(cell, cell_w)
            out.append(
                f'<text x="{x + 11}" y="{y + 23}" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif" font-size="13" font-weight="{weight}" fill="#1f2328">{html.escape(shown)}</text>'
            )
            x += cell_w
        y += row_h

    out.append("</svg>")
    path.write_text("\n".join(out) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("output_dir")
    parser.add_argument("prefix")
    args = parser.parse_args()

    source = Path(args.input)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    lines = source.read_text().splitlines()

    starts: dict[int, tuple[str, str]] = {}
    table_index = 0
    i = 0
    while i + 1 < len(lines):
        if "|" in lines[i] and is_separator(lines[i + 1]):
            table_index += 1
            j = i + 2
            rows = [split_row(lines[i])]
            while j < len(lines) and "|" in lines[j] and lines[j].strip():
                rows.append(split_row(lines[j]))
                j += 1
            filename = f"{args.prefix}-table-{table_index}.svg"
            title = nearest_title(lines, i, f"{args.prefix} table {table_index}")
            render_svg(out_dir / filename, title, rows)
            starts[i] = (filename, title)
            i = j
            continue
        i += 1

    decorated = []
    for index, line in enumerate(lines):
        if index in starts:
            filename, title = starts[index]
            decorated.append(f"![{title}](__ASSET_BASE__/__RUN_PREFIX__{filename})")
            decorated.append("")
        decorated.append(line)

    (out_dir / "summary.md").write_text("\n".join(decorated).rstrip() + "\n")
    print(f"rendered {table_index} Markdown table(s) from {source}")


if __name__ == "__main__":
    main()
