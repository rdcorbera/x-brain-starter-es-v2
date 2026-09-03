#!/usr/bin/env python3
"""Convierte un insumo binario a markdown para que un agente lo lea sin quemar tokens.

Determinista y sin modelo: el binario nunca entra en contexto. Leer un `.pptx`
crudo cuesta miles de tokens y abre la puerta a inventar; convertirlo cuesta cero.

**Sin dependencias.** Los formatos de Office son ZIP + XML y `.drawio` es XML:
nada de eso las necesita. v1 pasaba por `markitdown` dentro de un `.venv`
hermano, y en un entorno donde `pip` está restringido eso convierte al conversor
en el eslabón que no se puede instalar. El único formato que sí necesita una
dependencia es `.pdf`, y ahí degrada con aviso en vez de fallar.

    python3 to-markdown.py <archivo> [--out DIR] [--rows N] [--source RUTA]
                                     [--project SLUG] [--stdout]

La salida es un documento `Insumo` (o `Diagrama`, para `.drawio`) conforme al
contrato: `brain.py validate` lo acepta sin que nadie lo retoque.
"""

from __future__ import annotations

import argparse
import base64
import datetime
import html
import re
import sys
import urllib.parse
import zipfile
import zlib
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

if sys.version_info < (3, 11):
    sys.exit("ERROR: to-markdown.py necesita Python 3.11+ y este es "
             f"{'.'.join(map(str, sys.version_info[:3]))}.\n"
             "       Es el mismo piso que el resto del kernel; ver INSTALL.md.")

# Windows' console is not UTF-8 by default: without this, printing an accent or
# an em dash to --stdout dies with UnicodeEncodeError.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")

DEFAULT_ROWS = 50
LEGACY = {".doc": ".docx", ".ppt": ".pptx", ".xls": ".xlsx"}

# The values the contract allows in `Insumo.formato`. The extension is NOT the
# value: v1 emitted `formato: htm` and `formato: yml`, outside the enum, and
# nothing caught it. `.drawio` is absent on purpose -- it produces a Diagrama,
# which declares no `formato` at all.
FORMAT_BY_EXT = {
    ".docx": "docx", ".pdf": "pdf", ".html": "html", ".htm": "html",
    ".pptx": "pptx", ".xlsx": "xlsx", ".yaml": "yaml", ".yml": "yaml",
}

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
S = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


class ConversionError(Exception):
    """An expected, actionable failure -- reported without a traceback."""


# ---------------------------------------------------------------- helpers

def _read_text(path: Path, errors: str = "strict") -> str:
    """Read text, dropping the BOM that Notepad and many Windows exporters add.

    `utf-8-sig` strips it when present and behaves like utf-8 when it is not.
    """
    return path.read_text(encoding="utf-8-sig", errors=errors)


def _thousands(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def _cell(value: Any) -> str:
    """A value as text that is safe inside a markdown table."""
    if value is None:
        return ""
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.isoformat()[:19]
    return re.sub(r"\s+", " ", str(value)).replace("|", r"\|").strip()


def _md_table(rows: List[Tuple]) -> List[str]:
    """`rows`: list of tuples, the first one being the header. Trims empty columns."""
    width = 0
    for row in rows:
        for i, value in enumerate(row):
            if _cell(value):
                width = max(width, i + 1)
    if not width:
        return []
    out = []
    for n, row in enumerate(rows):
        cells = [_cell(v) for v in list(row)[:width]]
        cells += [""] * (width - len(cells))
        out.append("| " + " | ".join(cells) + " |")
        if n == 0:
            out.append("|" + "---|" * width)
    return out


def _clean_label(raw: Optional[str]) -> str:
    """drawio labels arrive with HTML embedded in them."""
    text = re.sub(r"<br\s*/?>", " ", raw or "", flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text).replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def _open_zip(path: Path) -> zipfile.ZipFile:
    try:
        return zipfile.ZipFile(path)
    except zipfile.BadZipFile as e:
        raise ConversionError(
            f"{path.name} no es un archivo de Office válido (no abre como ZIP). "
            "Puede estar corrupto, o ser un formato antiguo renombrado.") from e


def _read_xml(archive: zipfile.ZipFile, name: str):
    try:
        return ET.fromstring(archive.read(name))
    except KeyError:
        return None


def _has_any(root, tag: str) -> bool:
    """Does the tree contain this tag at all?

    `root.iter(tag)` is a GENERATOR, so it is truthy even when it yields
    nothing -- a check written as `if root.iter(tag)` is always true and the
    condition it guards silently never works. That bug shipped here once.
    """
    return any(True for _ in root.iter(tag))


# ---------------------------------------------------------------- docx

def _docx_text(element) -> str:
    """A paragraph's text, honouring tabs and explicit breaks."""
    parts = []
    for node in element.iter():
        if node.tag == W + "t":
            parts.append(node.text or "")
        elif node.tag == W + "tab":
            parts.append(" ")
        elif node.tag in (W + "br", W + "cr"):
            parts.append("\n")
    return "".join(parts).strip()


# Word keeps style IDs in English even in a localised install ("Heading1"), but
# documents converted from other editors do carry translated ones.
HEADING_STYLE = re.compile(r"^(?:heading|t[ií]tulo|titulo|berschrift)(\d)$", re.I)
LIST_STYLE = re.compile(r"^(?:listparagraph|p[áa]rrafodelista)", re.I)


def _docx_paragraph(paragraph) -> str:
    """A paragraph as markdown, keeping heading level and list bullets."""
    text = _docx_text(paragraph)
    if not text:
        return ""
    style = paragraph.find(f"{W}pPr/{W}pStyle")
    name = (style.get(W + "val") or "") if style is not None else ""
    heading = HEADING_STYLE.match(name)
    if heading:
        return "#" * min(int(heading.group(1)), 6) + " " + text
    if LIST_STYLE.match(name) or paragraph.find(f"{W}pPr/{W}numPr") is not None:
        return "- " + text
    return text


def from_docx(path: Path, _rows: int):
    with _open_zip(path) as archive:
        root = _read_xml(archive, "word/document.xml")
        if root is None:
            raise ConversionError(f"{path.name} no contiene word/document.xml.")
        body = root.find(W + "body")
        if body is None:
            raise ConversionError(f"{path.name} no tiene cuerpo de documento.")

        parts: List[str] = []
        warnings: List[str] = []
        for child in body:
            if child.tag == W + "p":
                line = _docx_paragraph(child)
                if line:
                    parts += [line, ""]
            elif child.tag == W + "tbl":
                rows = [tuple(_docx_text(tc) for tc in tr.findall(W + "tc"))
                        for tr in child.findall(W + "tr")]
                table = _md_table(rows)
                if table:
                    parts += table + [""]

        # A .docx can hold its real text inside text boxes, which hang off a
        # different branch of the XML. Saying so beats returning almost nothing.
        if not parts and _has_any(root, W + "t"):
            warnings.append(
                "El documento tiene texto, pero no en el cuerpo: probablemente está "
                "dentro de cuadros de texto o de imágenes. El original en /raw/ manda.")
    return "\n".join(parts).strip(), warnings, "Insumo"


# ---------------------------------------------------------------- pptx

def _pptx_shape_text(shape) -> List[str]:
    """A shape's paragraphs, in order."""
    out = []
    for paragraph in shape.iter(A + "p"):
        text = "".join(t.text or "" for t in paragraph.iter(A + "t")).strip()
        if text:
            out.append(text)
    return out


def _pptx_text_bodies(root) -> List:
    """A slide's text bodies, ignoring the namespace prefix.

    A shape's is `p:txBody` (presentationml) and a table cell's is `a:txBody`
    (drawingml). Looking for only one of the two drops half the slide, silently.
    """
    return [el for el in root.iter() if el.tag.endswith("}txBody")]


def from_pptx(path: Path, _rows: int):
    """Slides, tables and **speaker notes**.

    The notes are kept on purpose: they hold what the presenter meant to say and
    did not put on the slide, which is often the most informative part of the
    file. They are resolved through each slide's .rels, not by the number in the
    filename: slideN -> notesSlideN is the common case, not a guarantee.
    """
    with _open_zip(path) as archive:
        names = [n for n in archive.namelist()
                 if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)]
        if not names:
            raise ConversionError(f"{path.name} no contiene diapositivas.")
        names.sort(key=lambda n: int(re.search(r"(\d+)", n.rsplit("/", 1)[1]).group(1)))

        parts: List[str] = []
        warnings: List[str] = []
        with_notes = 0

        for index, name in enumerate(names, start=1):
            root = _read_xml(archive, name)
            if root is None:
                continue
            parts += [f"## Diapositiva {index}", ""]

            tables = list(root.iter(A + "tbl"))
            # Table cells are text bodies too: without excluding them every cell
            # would appear twice, loose and inside the table.
            in_table = {id(body) for t in tables for body in _pptx_text_bodies(t)}
            for body in _pptx_text_bodies(root):
                if id(body) in in_table:
                    continue
                for line in _pptx_shape_text(body):
                    parts += [line, ""]
            for table in tables:
                rows = [tuple(" ".join(_pptx_shape_text(cell))
                              for cell in row.iter(A + "tc"))
                        for row in table.iter(A + "tr")]
                rendered = _md_table(rows)
                if rendered:
                    parts += rendered + [""]

            notes = _pptx_notes(archive, name, index)
            if notes:
                with_notes += 1
                parts += ["### Notas del orador", ""]
                parts += [line for note in notes for line in (note, "")]

    if with_notes:
        warnings.append(f"{with_notes} de {len(names)} diapositivas traen notas del "
                        "orador, incluidas bajo «Notas del orador».")
    return "\n".join(parts).strip(), warnings, "Insumo"


def _pptx_notes(archive: zipfile.ZipFile, slide: str, index: int) -> List[str]:
    """The speaker notes of one slide, resolved through its relationships."""
    base = slide.rsplit("/", 1)[1]
    rels = _read_xml(archive, f"ppt/slides/_rels/{base}.rels")
    if rels is None:
        return []
    target = next((rel.get("Target", "").replace("../", "ppt/")
                   for rel in rels if rel.get("Type", "").endswith("/notesSlide")), None)
    if not target:
        return []
    root = _read_xml(archive, target)
    if root is None:
        return []
    text = [t for body in _pptx_text_bodies(root) for t in _pptx_shape_text(body)]
    # The slide-number placeholder comes through as one more shape, and it is
    # not content.
    return [t for t in text if t.strip() != str(index)]


# ---------------------------------------------------------------- xlsx

# The number formats Excel reserves for dates and times. Without this a date
# comes out as 45678, which is worse than not converting it: it looks like data.
BUILTIN_DATE_FORMATS = set(range(14, 23)) | set(range(45, 48))
CELL_REF = re.compile(r"([A-Z]+)(\d+)")


def _column_index(ref: str) -> int:
    """`C7` -> 2. Excel's columns are base-26 with no zero."""
    match = CELL_REF.match(ref)
    letters = match.group(1) if match else "A"
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def _xlsx_date_styles(archive: zipfile.ZipFile) -> set:
    """Indexes into `cellXfs` whose number format is a date."""
    styles = _read_xml(archive, "xl/styles.xml")
    if styles is None:
        return set()
    custom = set()
    for fmt in styles.iter(S + "numFmt"):
        # Quoted literals are stripped before looking for y/m/d, or a format
        # like `0" días"` would pass for a date.
        code = re.sub(r'"[^"]*"', "", fmt.get("formatCode", ""))
        if re.search(r"[ymdhs]", code, re.I):
            custom.add(int(fmt.get("numFmtId")))

    dates = set()
    cell_xfs = styles.find(S + "cellXfs")
    if cell_xfs is None:
        return dates
    for index, xf in enumerate(cell_xfs.findall(S + "xf")):
        fmt_id = int(xf.get("numFmtId", "0"))
        if fmt_id in BUILTIN_DATE_FORMATS or fmt_id in custom:
            dates.add(index)
    return dates


def _xlsx_serial_to_date(value: float, epoch_1904: bool):
    """Excel's serial number to a real date.

    The epoch is 1899-12-30, not 12-31: Excel deliberately keeps the bug of
    treating 1900 as a leap year, and that extra day is exactly the offset.
    """
    base = datetime.date(1904, 1, 1) if epoch_1904 else datetime.date(1899, 12, 30)
    days = int(value)
    fraction = value - days
    day = base + datetime.timedelta(days=days)
    if fraction:
        return (datetime.datetime.combine(day, datetime.time())
                + datetime.timedelta(seconds=round(fraction * 86400)))
    return day


def _xlsx_shared_strings(archive: zipfile.ZipFile) -> List[str]:
    root = _read_xml(archive, "xl/sharedStrings.xml")
    if root is None:
        return []
    return ["".join(t.text or "" for t in si.iter(S + "t"))
            for si in root.findall(S + "si")]


class _SheetScan:
    """What one worksheet yielded, plus whether it hid uncached formulas."""

    def __init__(self) -> None:
        self.kept: List[Dict[int, Any]] = []
        self.total = 0
        self.width = 0
        self.uncached_formula = False


def _xlsx_cell_value(cell, strings: List[str], date_styles: set,
                     epoch_1904: bool, scan: _SheetScan):
    """One cell's value, or None when there is nothing to show.

    A formula with no <v> is a computed column that would come out EMPTY with no
    warning. Excel caches the result; a workbook generated by a script and never
    opened does not have that cache.
    """
    has_formula = cell.find(S + "f") is not None
    node = cell.find(S + "v")
    if has_formula and node is None:
        scan.uncached_formula = True
        return None
    if node is None:
        inline = cell.find(f"{S}is")
        if inline is None:
            return None
        return "".join(t.text or "" for t in inline.iter(S + "t"))

    kind = cell.get("t")
    raw = node.text or ""
    if kind == "s":
        return strings[int(raw)] if raw.isdigit() and int(raw) < len(strings) else ""
    if kind == "b":
        return "VERDADERO" if raw == "1" else "FALSO"

    style = cell.get("s")
    if style is not None and int(style) in date_styles:
        try:
            return _xlsx_serial_to_date(float(raw), epoch_1904)
        except ValueError:
            return raw
    if re.fullmatch(r"-?\d+\.\d+", raw):
        return raw.rstrip("0").rstrip(".")
    return raw


def from_xlsx(path: Path, rows: int):
    """The number-one token bomb: it gets sampled. The whole .xlsx stays in /raw/.

    A 1.500-row sheet is ~18.800 tokens of noise; sampled, ~830.
    """
    with _open_zip(path) as archive:
        workbook = _read_xml(archive, "xl/workbook.xml")
        if workbook is None:
            raise ConversionError(f"{path.name} no contiene xl/workbook.xml.")
        properties = workbook.find(S + "workbookPr")
        epoch_1904 = bool(properties is not None
                          and properties.get("date1904") in ("1", "true"))

        rels = _read_xml(archive, "xl/_rels/workbook.xml.rels")
        targets = {rel.get("Id"): rel.get("Target")
                   for rel in (rels if rels is not None else []) if rel.get("Id")}
        strings = _xlsx_shared_strings(archive)
        date_styles = _xlsx_date_styles(archive)

        sheets = []
        for sheet in workbook.iter(S + "sheet"):
            target = targets.get(sheet.get(R + "id"), "")
            if target:
                sheets.append((sheet.get("name", "?"),
                               target if target.startswith("xl/")
                               else "xl/" + target.lstrip("/")))

        parts: List[str] = []
        warnings: List[str] = []
        uncached_formula = False

        for title, sheet_path in sheets:
            root = _read_xml(archive, sheet_path)
            if root is None:
                continue
            scan = _SheetScan()
            for row in root.iter(S + "row"):
                values: Dict[int, Any] = {}
                for cell in row.findall(S + "c"):
                    value = _xlsx_cell_value(cell, strings, date_styles,
                                             epoch_1904, scan)
                    if _cell(value):
                        values[_column_index(cell.get("r", "A1"))] = value
                if not values:
                    continue
                scan.total += 1
                scan.width = max(scan.width, max(values) + 1)
                if len(scan.kept) < rows + 1:
                    scan.kept.append(values)
            uncached_formula = uncached_formula or scan.uncached_formula

            if not scan.total:
                continue
            grid = [tuple(v.get(i) for i in range(scan.width)) for v in scan.kept]
            parts += [f"### Hoja: {title}", ""]
            if scan.total > len(scan.kept):
                note = (f"> {_thousands(scan.total)} filas × {scan.width} columnas — se "
                        f"muestran las primeras {_thousands(len(scan.kept) - 1)}. El "
                        "original completo está en /raw/.")
                warnings.append(f"Hoja «{title}»: truncada a "
                                f"{_thousands(len(scan.kept) - 1)} de "
                                f"{_thousands(scan.total)} filas.")
            else:
                note = f"> {_thousands(scan.total)} filas × {scan.width} columnas (completa)."
            parts += [note, ""] + _md_table(grid) + [""]

        if uncached_formula:
            warnings.insert(0,
                            "El libro tiene fórmulas sin valor calculado en caché: esas celdas "
                            "salen VACÍAS. Suele pasar con libros generados por script y nunca "
                            "abiertos en Excel. Para materializarlas: abrir en Excel o "
                            "LibreOffice y guardar.")
        if not parts:
            warnings.append("El libro no tiene ninguna hoja con datos.")
    return "\n".join(parts).strip(), warnings, "Insumo"


# ---------------------------------------------------------------- drawio

def _drawio_model(diagram, filename: str):
    """The graph model, decompressing the packed variant when needed."""
    model = diagram.find(".//mxGraphModel")
    if model is not None:
        return model
    packed = (diagram.text or "").strip()
    if not packed:
        return None
    try:
        xml = zlib.decompress(base64.b64decode(packed), -15).decode("utf-8")
        return ET.fromstring(urllib.parse.unquote(xml))
    except Exception as e:
        raise ConversionError(
            f"No se pudo descomprimir la página «{diagram.get('name') or '?'}» "
            f"de {filename}: {e}") from e


def _drawio_graph(model) -> Tuple[Dict[str, str], List[Tuple]]:
    """Nodes and edges, unwrapping the `object` cells that carry the label."""
    nodes: Dict[str, str] = {}
    edges: List[Tuple] = []
    wrapped = {id(cell) for holder in model.iter()
               if holder.tag in ("object", "UserObject")
               for cell in holder.findall("mxCell")}

    for element in model.iter():
        if element.tag in ("object", "UserObject"):
            cell = element.find("mxCell")
            if cell is None:
                continue
            key, label, attrs = element.get("id"), element.get("label") or "", cell
        elif element.tag == "mxCell" and id(element) not in wrapped:
            key, label, attrs = element.get("id"), element.get("value") or "", element
        else:
            continue
        if attrs.get("vertex") == "1":
            nodes[key] = _clean_label(label)
        elif attrs.get("edge") == "1":
            edges.append((attrs.get("source"), attrs.get("target"),
                          _clean_label(label)))
    return nodes, edges


def from_drawio(path: Path, _rows: int):
    """No tool on the market covers this, and it fits the kernel's own rule:
    diagrams are stored as text, never as an image alone."""
    root = ET.fromstring(_read_text(path))
    diagrams = root.findall(".//diagram") or [root]
    parts: List[str] = []
    warnings: List[str] = []

    for diagram in diagrams:
        model = _drawio_model(diagram, path.name)
        if model is None:
            continue
        nodes, edges = _drawio_graph(model)

        referenced = {s for s, _, _ in edges} | {t for _, t, _ in edges}
        visible = {k: label for k, label in nodes.items() if label or k in referenced}
        if not visible:
            continue

        ids = {key: f"n{i}" for i, key in enumerate(visible)}
        lines = ["flowchart TD"]
        for key, label in visible.items():
            lines.append(f'    {ids[key]}["{(label or "(sin etiqueta)").replace(chr(34), "#quot;")}"]')
        for source, target, label in edges:
            if source not in ids or target not in ids:
                continue          # a dangling edge says nothing without an end
            if label:
                lines.append(f'    {ids[source]} -->|"{label.replace(chr(34), "#quot;")}"| {ids[target]}')
            else:
                lines.append(f"    {ids[source]} --> {ids[target]}")

        name = diagram.get("name")
        if len(diagrams) > 1 and name:
            parts += [f"## {name}", ""]
        parts += ["```mermaid"] + lines + ["```", ""]
        warnings.append(
            f"Página «{name or path.stem}»: "
            f"{len(visible)} nodo{'s' if len(visible) != 1 else ''}, "
            f"{len(edges)} conexi{'ones' if len(edges) != 1 else 'ón'}.")

    if not parts:
        raise ConversionError(f"{path.name} no contiene ningún diagrama con nodos.")
    return "\n".join(parts).strip(), warnings, "Diagrama"


# ---------------------------------------------------------------- html

# Web-template junk: on a real page these are hundreds of tokens of noise.
HTML_NOISE = {"nav", "footer", "header", "aside", "form", "script", "style",
              "noscript", "svg", "iframe", "button"}
BLOCK_TAGS = {"p", "div", "section", "article", "br", "tr", "ul", "ol", "table",
              "blockquote", "pre"}
HEADINGS = {"h1", "h2", "h3", "h4", "h5", "h6"}


class _HtmlToMarkdown(HTMLParser):
    """HTML to markdown with what the standard library already ships.

    v1 used BeautifulSoup only to strip `nav`/`footer` before handing the file
    to markitdown. Both dependencies go: removing noise and pulling out text is
    exactly what an event-driven parser does.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: List[str] = []
        self.skipping = 0
        self.dropped = 0

    def handle_starttag(self, tag, attrs):
        if tag in HTML_NOISE:
            self.skipping += 1
            self.dropped += 1
        elif self.skipping:
            return
        elif tag in HEADINGS:
            self.out.append("\n\n" + "#" * int(tag[1]) + " ")
        elif tag == "li":
            self.out.append("\n- ")
        elif tag in BLOCK_TAGS:
            self.out.append("\n\n")

    def handle_endtag(self, tag):
        if tag in HTML_NOISE:
            self.skipping = max(0, self.skipping - 1)
        elif self.skipping:
            return
        elif tag in HEADINGS or tag in BLOCK_TAGS:
            self.out.append("\n\n")

    def handle_data(self, data):
        if self.skipping:
            return
        text = re.sub(r"\s+", " ", data)
        if text.strip():
            self.out.append(text)

    def markdown(self) -> str:
        text = re.sub(r"[ \t]+", " ", "".join(self.out))
        text = re.sub(r" *\n *", "\n", text)
        return re.sub(r"\n{3,}", "\n\n", text).strip()


def from_html(path: Path, _rows: int):
    source = _read_text(path, errors="replace")
    # The real content, when the page marks it. A <main> trims the template
    # better than any list of noise tags can.
    match = re.search(r"<(main|article)\b[^>]*>(.*?)</\1>", source, re.S | re.I)
    if match:
        source = match.group(2)

    parser = _HtmlToMarkdown()
    parser.feed(source)
    parser.close()

    warnings = []
    if parser.dropped:
        warnings.append(f"Se descartaron {parser.dropped} bloques de plantilla "
                        "(nav/footer/script…).")
    if match:
        # No angle brackets on purpose: V9 reads `<something>` as an unfilled
        # placeholder, so a warning written with them would fail the document.
        warnings.append(f"Se tomó solo el contenido de la sección {match.group(1)}.")
    return parser.markdown(), warnings, "Insumo"


# ---------------------------------------------------------------- yaml

def from_yaml(path: Path, _rows: int):
    """Already near-optimal text for an agent: converting it would cost tokens
    and lose fidelity."""
    return "```yaml\n" + _read_text(path).strip() + "\n```", [], "Insumo"


# ---------------------------------------------------------------- pdf

def from_pdf(path: Path, _rows: int):
    """The one format the standard library cannot do.

    A PDF is a binary container with compressed streams and its own font
    encodings: pulling legible text out of that is not reasonable without a
    library. So this is the kernel's only optional layer, and it degrades with a
    message instead of failing: the original is still in /raw/, which is the
    source of truth anyway.
    """
    try:
        from pdfminer.high_level import extract_text            # type: ignore
    except ImportError:
        raise ConversionError(
            f"{path.name}: el `.pdf` es el único formato que necesita una "
            "dependencia, y no está instalada.\n"
            "       Opción A — instalarla:  pip install pdfminer.six\n"
            "       Opción B — sin `pip`:   abrir el PDF y «Guardar como» / imprimir "
            "a .docx, o copiar el texto a un .md, y dejar eso en inbox/.\n"
            "       El original se archiva igual en /raw/ y se sigue citando.")

    try:
        text = (extract_text(str(path)) or "").strip()
    except Exception as e:
        # An unreadable PDF is an expected, actionable failure -- not a defect
        # in this script. Report it as such, without a traceback.
        raise ConversionError(
            f"{path.name}: el PDF no se pudo leer ({type(e).__name__}: {e}).\n"
            "       Puede estar corrupto, protegido con contraseña o incompleto. "
            "El original se archiva igual en /raw/.") from e

    warnings = []
    try:
        from pdfminer.pdfpage import PDFPage                    # type: ignore
        with open(path, "rb") as fh:
            pages = len(list(PDFPage.get_pages(fh)))
    except Exception:
        pages = 0
    # A scanned PDF extracts almost nothing: say so, do not return empty.
    if pages and len(text) / pages < 100:
        warnings.append(
            f"PDF probablemente escaneado o sin capa de texto: {pages} páginas y solo "
            f"{_thousands(len(text))} caracteres extraídos. Lo convertido puede estar "
            "incompleto; el original en /raw/ sigue siendo la fuente.")
    return re.sub(r"\n{3,}", "\n\n", text), warnings, "Insumo"


ENGINES = {
    ".docx": from_docx, ".pdf": from_pdf, ".html": from_html, ".htm": from_html,
    ".pptx": from_pptx, ".xlsx": from_xlsx, ".drawio": from_drawio,
    ".yaml": from_yaml, ".yml": from_yaml,
}


# ---------------------------------------------------------------- output

def _bundle_root(path: Path) -> Optional[Path]:
    for candidate in [path.resolve()] + list(path.resolve().parents):
        if (candidate / "kernel").is_dir() and (candidate / "cerebro").is_dir():
            return candidate
    return None


def _source_pointer(path: Path, given: Optional[str]) -> str:
    if given:
        return given
    root = _bundle_root(path)
    if root:
        try:
            return "/" + str(path.resolve().relative_to(root)).replace("\\", "/")
        except ValueError:
            pass
    return path.name


def _title_from_filename(path: Path) -> str:
    """The filename without the date prefix or the /raw/ suffix.

    Originals are archived as `AAAA-MM-DD-description-uuid.ext`. The uuid must
    carry at least one digit, so a short all-hex word is not eaten by mistake.
    """
    title = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", path.stem)
    title = re.sub(r"-(?=[0-9a-f]*\d)[0-9a-f]{6,8}$", "", title)
    title = title.replace("-", " ").replace("_", " ").strip()
    if not title:
        return path.stem
    return title[:1].upper() + title[1:]


def build_document(path: Path, rows: int, source: Optional[str],
                   project: str) -> Tuple[str, List[str]]:
    ext = path.suffix.lower()
    if ext in LEGACY:
        raise ConversionError(
            f"{path.name} está en formato binario legacy ({ext}), que no se puede leer.\n"
            f"       Ábrelo en Office y usa «Guardar como» → {LEGACY[ext]}, y vuelve a "
            "dejarlo en inbox/.")
    if ext not in ENGINES:
        raise ConversionError(
            f"No hay motor para {ext}. Soportados: {', '.join(sorted(ENGINES))}.")
    if not path.is_file():
        raise ConversionError(f"No existe el archivo: {path}")

    body, warnings, doc_type = ENGINES[ext](path, rows)
    if not body.strip():
        warnings.append("La conversión no extrajo texto. Revisar el original en /raw/.")

    now = datetime.datetime.now().astimezone().replace(microsecond=0).isoformat()
    pointer = _source_pointer(path, source)

    # A mechanical, true description -- not a placeholder. v1 emitted
    # `<pendiente — al integrar>`, and that FAILS V9: the document was born
    # invalid and the user saw errors in something the system had just written.
    # Inventing a summary is not an option either -- that would be fabricating.
    # Saying what the file is, is not, and the agent improves it when integrating.
    what = "Diagrama" if doc_type == "Diagrama" else f"Documento {FORMAT_BY_EXT[ext]}"

    # Frontmatter conformant to the contract: `brain.py validate` accepts it with
    # nobody touching it. `generated` records who wrote it and when, so "a script
    # produced this and nobody has reviewed it" is a queryable property.
    front = ["---",
             f"type: {doc_type}",
             f"title: {_title_from_filename(path)}",
             f"description: {what} recibido, convertido a markdown desde "
             f"{path.name}; pendiente de resumir al integrarlo.",
             "tags: []",
             "classification: confidential",
             f"generated: {{by: process:to-markdown, at: {now}}}",
             f"proyecto: {project}"]
    if doc_type == "Diagrama":
        front += ["clase: flujo", f"version: {now[:10]}"]
    else:
        front += [f"formato: {FORMAT_BY_EXT[ext]}", f"origen: {pointer}"]
    front += ["---", ""]

    document = front + [
        "> Convertido automáticamente desde el original crudo por `to-markdown.py`. "
        "El original manda: ante cualquier duda, se cita y se revisa.", ""]
    if warnings:
        document += ["# Avisos de conversión", ""] + [f"- {w}" for w in warnings] + [""]
    document += [f"# {'Diagrama' if doc_type == 'Diagrama' else 'Contenido'}", "",
                 body, "", "# Citations", "",
                 f"[1] Original: [{path.name}]({pointer})"]
    return "\n".join(document) + "\n", warnings


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convierte un insumo a markdown legible por un agente, "
                    "sin gastar tokens y sin dependencias.")
    parser.add_argument("archivo", type=Path)
    parser.add_argument("--out", type=Path,
                        help="directorio de salida (por defecto: junto al archivo)")
    parser.add_argument("--rows", type=int, default=DEFAULT_ROWS,
                        help=f"filas por hoja en .xlsx (por defecto {DEFAULT_ROWS})")
    parser.add_argument("--source",
                        help="puntero al raw a citar "
                             "(ej. /raw/2026-07-16-propuesta-3f2a9c.pptx)")
    parser.add_argument("--project", default="transversal",
                        help="slug del proyecto al que pertenece (por defecto: transversal)")
    parser.add_argument("--stdout", action="store_true",
                        help="imprimir el markdown en vez de escribirlo")
    args = parser.parse_args()

    try:
        document, warnings = build_document(args.archivo, args.rows,
                                            args.source, args.project)
    except ConversionError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    if args.stdout:
        print(document, end="")
        return 0

    target = (args.out or args.archivo.parent) / (args.archivo.stem + ".md")
    target.parent.mkdir(parents=True, exist_ok=True)
    # newline="\n": without it Windows would write CRLF and the same input would
    # produce a different diff depending on who converted it.
    target.write_text(document, encoding="utf-8", newline="\n")
    print(f"OK: {target}  ({_thousands(len(document))} caracteres)")
    for warning in warnings:
        print(f"  aviso: {warning}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
