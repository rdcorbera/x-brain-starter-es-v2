"""Generar: plantillas, JSON Schemas, índices, derivados, stubs y ESQUEMA.md.

El trabajo que ESCRIBE. Todo lo que sale de aquí es un artefacto generado, y por
eso no se edita: se regenera. V14 lo comprueba."""

from __future__ import annotations

import json
import os
import re
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .const import (DATE_RE, DEFAULT_BUNDLE, GENERATED_MARK, VERSION,
                    WARNING)
from .parse import (Contract, Document, ParseError, parse_frontmatter,
                    read_frontmatter, quote_scalar, quoting_preserves_meaning,
                    scan_yaml_hazards)

PLACEHOLDER_IN_PATH = re.compile(r"\{(\w+)\}")


def _when_matches(when: Dict[str, Any], values: Dict[str, Any]) -> bool:
    """Same shape as derived_files.where, plus `{"not": x}`."""
    for field, expected in when.items():
        actual = values.get(field)
        if isinstance(expected, dict) and "not" in expected:
            if actual == expected["not"]:
                return False
        elif isinstance(expected, list):
            if actual not in expected:
                return False
        elif actual != expected:
            return False
    return True


def resolve_locations(contract: Contract, type_name: str,
                      values: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    """Where a document of this type belongs, given its field values.

    Returns (resolved paths, notes). Several paths means the tool could not
    decide -- it hands back the candidates rather than guessing.
    """
    resolved, notes = [], []
    for entry in contract.locations(type_name):
        path, role = entry["path"], entry.get("role")
        if role == "archive":
            notes.append(f"{path} — solo tras archivar; no es destino de un documento nuevo")
            continue
        if not _when_matches(entry.get("when", {}), values):
            continue
        missing = [ph for ph in PLACEHOLDER_IN_PATH.findall(path)
                   if not values.get(ph)]
        if missing:
            notes.append(f"{path} — falta {', '.join('`'+m+'`' for m in missing)}")
            continue
        resolved.append(PLACEHOLDER_IN_PATH.sub(
            lambda m: str(values[m.group(1)]), path))
    return resolved, notes


def location_patterns_for_match(contract: Contract, type_name: str,
                                role: Optional[str] = None) -> List[str]:
    """Every pattern of the type, as a regex, for validating a real path.

    `role` narrows to one kind of location. It is what lets a derived index say
    "only the initiatives of the period in course" without anybody writing the
    period down: an initiative leaves the current period by being MOVED to the
    archive, and the contract already declares both places.
    """
    out = []
    for entry in contract.locations(type_name):
        if role is not None and entry.get("role", "active") != role:
            continue
        path = entry["path"].rstrip("/")
        if path in ("", "."):
            out.append(r"^$")
            continue
        escaped = re.escape(path).replace(r"\{", "{").replace(r"\}", "}")
        out.append("^" + PLACEHOLDER_IN_PATH.sub(r"[^/]+", escaped) + "$")
    return out


def period_segments(contract: Contract, type_name: str, rel: str) -> List[str]:
    """The period folder names a document's own path actually carries.

    Reads the same location declarations as V19, but captures the `{periodo}`
    placeholder instead of wildcarding it -- so `04-archivo/{periodo}/{proyecto}/`
    yields the period, and nothing has to name the archive folder twice.
    """
    field = contract.period_formats.get("field", "periodo")
    token = "{" + field + "}"
    directory = str(Path(rel).parent).replace("\\", "/")
    directory = "" if directory == "." else directory
    out: List[str] = []
    for entry in contract.locations(type_name):
        path = entry["path"].rstrip("/")
        if token not in path:
            continue
        escaped = re.escape(path).replace(r"\{", "{").replace(r"\}", "}")
        regex = PLACEHOLDER_IN_PATH.sub(
            lambda m: "([^/]+)" if m.group(1) == field else "[^/]+", escaped)
        match = re.match("^" + regex + "$", directory)
        if match:
            out.extend(g for g in match.groups() if g not in out)
    return out


def render_template(contract: Contract, type_name: str) -> str:
    _DATA_TYPE_HINTS.update({
        name: ds.get("hint", "") for name, ds in contract.data_types.items()
        if isinstance(ds, dict) and ds.get("hint")
    })
    if type_name not in contract.types:
        raise SystemExit(f"error: tipo `{type_name}` no está en el contrato")
    spec = contract.types[type_name]
    defaults = spec.get("field_defaults", {})
    out = ["---"]
    for name, field in contract.fields_for(type_name).items():
        if field.get("deprecated_by"):
            continue
        if not field.get("required") and name not in defaults:
            continue
        out.append(f"{name}: {_placeholder(name, field, type_name, defaults, contract)}")
    out.append("---")
    out.append("")
    for section in contract.sections_for(type_name):
        out.append(f"# {section['heading']}")
        out.append("")
        if section.get("format") == "table":
            columns = section.get("columns", [])
            out.append("| " + " | ".join(columns) + " |")
            out.append("|" + "|".join(["---"] * len(columns)) + "|")
            out.append("| " + " | ".join(f"<{c.lower()}>" for c in columns) + " |")
        else:
            out.append(f"<{section.get('guide', 'contenido')}>")
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def _placeholder(name: str, field: Dict[str, Any], type_name: str,
                 defaults: Dict[str, Any], contract: "Contract") -> str:
    if name == "type":
        return type_name
    if name in defaults:
        return json.dumps(defaults[name], ensure_ascii=False)
    kind = field.get("data_type", "text")
    if name == contract.classification.get("field") and contract.levels:
        # The type's floor, never the global default: a template that proposes
        # a value its own validator rejects is the contradiction this whole
        # design exists to prevent.
        floor = contract.min_classification(type_name)
        return f"{floor}          # mínimo de {type_name}: {floor}"
    if name == contract.period_formats.get("field") and contract.period_format:
        # Same reasoning as classification: once the brain has DECLARED its
        # cycle, the template proposes that shape instead of asking the agent
        # to go and look it up. Undeclared falls through to the generic hint,
        # which keeps the kernel-level templates on disk stable.
        shape = contract.period_formats["shapes"][contract.period_format]
        return f"{shape.get('example', '')}          # formato {contract.period_format}"
    if kind == "enum":
        values = field.get("values", [])
        chosen = field.get("default", values[0] if values else "")
        return f"{chosen}          # {' | '.join(values)}"
    if "default" in field:
        value = field["default"]
        return json.dumps(value) if isinstance(value, bool) else str(value)
    if kind == "list":
        return "[]"
    if kind == "map":
        members = ", ".join(f"{k}: <{k}>" for k in field.get("fields", {}))
        return "{" + members + "}"
    if kind == "date":
        return "<YYYY-MM-DD>"
    if kind == "datetime":
        return "<ISO 8601 con offset UTC>"
    if kind == "boolean":
        return "false"
    # NEVER fall back to `note`. That key is engineering commentary for whoever
    # maintains the contract -- it is English, and it once dumped a whole
    # paragraph about migration costs and check numbers into the user's
    # document. A placeholder is content: it belongs to the bundle's language.
    # Quote if the placeholder itself would break YAML. Fixing the text in the
    # contract is the primary defence; this is the net under it, because a
    # template that a viewer cannot open is worse than an ugly one.
    # Fall back to the data type's own hint before the bare field name, the
    # same order the schema tables use -- so `type-key` explains itself once
    # instead of once per field that uses it.
    hint = _DATA_TYPE_HINTS.get(field.get("data_type", ""), "")
    return quote_scalar(f"<{field.get('placeholder') or hint or name}>")


def json_schema_for(contract: Contract, type_name: str) -> dict:
    """Emit standard JSON Schema so external tooling can validate too."""
    properties: Dict[str, Any] = {}
    required: List[str] = []
    for name, field in contract.fields_for(type_name).items():
        if field.get("deprecated_by"):
            continue
        properties[name] = _json_schema_field(field)
        if field.get("required"):
            required.append(name)
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"{type_name.lower()}.schema.json",
        "title": type_name,
        "description": contract.types[type_name].get("description", ""),
        "type": "object",
        "properties": properties,
        "required": required,
    }


_JSON_TYPES = {
    "text": {"type": "string"}, "sentence": {"type": "string"},
    "boolean": {"type": "boolean"}, "link": {"type": "string"},
    "typed-ref": {"type": "string"}, "actor": {"type": "string"},
    "date": {"type": "string", "format": "date"},
    "datetime": {"type": "string", "format": "date-time"},
}


def _json_schema_field(field: Dict[str, Any]) -> dict:
    kind = field.get("data_type", "text")
    if kind == "enum":
        return {"type": "string", "enum": field.get("values", [])}
    if kind == "list":
        return {"type": "array", "items": _json_schema_field({"data_type": field.get("of", "text")})}
    if kind == "map":
        members = {k: _json_schema_field(v) for k, v in field.get("fields", {}).items()
                   if isinstance(v, dict)}
        return {
            "type": "object",
            "properties": members,
            "required": [k for k, v in field.get("fields", {}).items()
                         if isinstance(v, dict) and v.get("required")],
        }
    return dict(_JSON_TYPES.get(kind, {"type": "string"}))


def build_indexes(contract: Contract, docs: List[Document],
                  bundle: Path) -> Dict[Path, str]:
    """One index.md per directory that holds knowledge, derived from frontmatter."""
    by_dir: Dict[Path, List[Document]] = defaultdict(list)
    for doc in docs:
        if not doc.is_reserved:
            by_dir[doc.path.parent].append(doc)

    subdirs: Dict[Path, set] = defaultdict(set)
    for directory in list(by_dir):
        parent = directory.parent
        while parent != bundle.parent and parent != directory:
            subdirs[parent].add(directory if parent == directory.parent else None)
            directory, parent = parent, parent.parent

    out: Dict[Path, str] = {}
    for directory, entries in sorted(by_dir.items()):
        title = "Índice raíz del cerebro" if directory.resolve() == bundle.resolve() \
            else directory.name
        lines = [GENERATED_MARK, "", f"# {title}", ""]
        for doc in sorted(entries, key=lambda d: d.path.name):
            label = doc.meta.get("title") or doc.path.stem
            description = doc.meta.get("description") or ""
            suffix = f" - {description}" if description else ""
            lines.append(f"* [{label}]({doc.path.name}){suffix}")
        children = sorted({d for d in by_dir if d.parent == directory})
        if children:
            lines += ["", "# Secciones", ""]
            for child in children:
                lines.append(f"* [{child.name}]({child.name}/)")
        out[directory] = "\n".join(lines).rstrip() + "\n"
    return out


def _derived_frontmatter(contract: Contract, name: str) -> List[str]:
    """Conformant frontmatter for a generated file, from its contract entry.

    This is what makes a derived artifact fully OKF-conformant without anyone
    maintaining it -- and it is why v1's ORGANIGRAMA defect (type Diagrama with
    no `clase`, `proyecto` or `version`) cannot recur.
    """
    spec = contract.derived.get(name, {})
    stamp = datetime.now().astimezone().replace(microsecond=0).isoformat()
    lines = ["---", f"type: {spec.get('type', 'Indice')}"]
    if spec.get("title"):
        lines.append(f"title: {quote_scalar(spec['title'])}")
    if spec.get("description"):
        lines.append(f"description: {quote_scalar(spec['description'])}")
    # `resumen` is required of every document, and a generated index is a
    # document. Its summary is the one case the deterministic layer may write
    # itself, because for an index the overview genuinely IS mechanical -- and
    # `procedencia: derivado` says exactly that: nothing here was read, said or
    # inferred; it was computed from other documents.
    if spec.get("resumen"):
        lines.append(f"resumen: {quote_scalar(spec['resumen'])}")
    lines.append("procedencia: derivado")
    for key, value in spec.get("fields", {}).items():
        lines.append(f"{key}: {value}")
    if "version" in contract.fields_for(spec.get("type", "")):
        lines.append(f"version: {date.today().isoformat()}")
    lines.append("tags: [generado]")
    lines.append(f"generated: {{by: process:brain-derive, at: {stamp}}}")
    lines += ["---", ""]
    return lines


def split_document(text: str) -> Tuple[str, str]:
    """Split a file into (frontmatter block, body)."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return "", text
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            return "\n".join(lines[:idx + 1]), "\n".join(lines[idx + 1:])
    return "", text


def derived_is_current(path: Path, body: str) -> bool:
    """Compare BODIES only.

    The frontmatter carries a generation timestamp, so comparing whole files
    would make every run report a change and break idempotency. What matters is
    whether the derived content still reflects the corpus.
    """
    if not path.exists():
        return False
    _, existing = split_document(path.read_text(encoding="utf-8"))
    return existing.strip() == body.strip()


def compose_derived(contract: Contract, name: str, body: str) -> str:
    return "\n".join(_derived_frontmatter(contract, name)) + body.lstrip("\n")


def _days_since(raw: Any) -> str:
    if not isinstance(raw, str) or not DATE_RE.match(raw):
        return "-"
    return str((date.today() - date(*map(int, raw.split("-")))).days)


def _cell(doc: Document, column: Dict[str, Any],
          lookup: Dict[str, Document]) -> str:
    source = column.get("value", "title")
    if source.startswith("days_since:"):
        return _days_since(doc.meta.get(source.split(":", 1)[1]))
    value = doc.meta.get(source) or (doc.path.stem if source == "title" else None)
    if value is None:
        return "-"
    if column.get("resolve") and isinstance(value, str) and value.startswith("/"):
        # A person-ref that points at a ficha reads as the person's name, not
        # as a path. Free text passes through untouched -- that is the point
        # of person-ref being tolerant during migration.
        target = lookup.get(value.lstrip("/"))
        if target:
            value = target.meta.get("title") or target.path.stem
    return f"[{value}](/{doc.rel})" if column.get("link") else str(value)


def _in_role(doc: Document, patterns: List[str]) -> bool:
    """Does this document sit in one of the locations of a given role?"""
    directory = str(Path(doc.rel).parent).replace("\\", "/")
    directory = "" if directory == "." else directory
    return any(re.match(p, directory) for p in patterns)


def _matches(doc: Document, where: Dict[str, Any]) -> bool:
    for field, allowed in where.items():
        value = doc.meta.get(field)
        if isinstance(allowed, list):
            if value not in allowed:
                return False
        elif value != allowed:
            return False
    return True


def _render_table(spec: Dict[str, Any], rows: List[Document],
                  lookup: Dict[str, Document]) -> List[str]:
    columns = spec.get("columns", [{"header": "Documento", "value": "title", "link": True}])
    headers = [c.get("header", c.get("value", "")) for c in columns]
    lines = ["| " + " | ".join(headers) + " |",
             "|" + "|".join(["---"] * len(headers)) + "|"]
    flag = spec.get("flag") or {}
    for doc in rows:
        cells = [_cell(doc, c, lookup) for c in columns]
        if flag and doc.meta.get(flag.get("field")):
            cells[0] = flag.get("prefix", "") + cells[0]
        lines.append("| " + " | ".join(cells) + " |")
    if not rows:
        empty = spec.get("empty_row", "-")
        lines.append("| " + empty + " |" + " |" * (len(headers) - 1))
    return lines


def _render_groups(spec: Dict[str, Any], rows: List[Document],
                   lookup: Dict[str, Document]) -> List[str]:
    """One subsection per declared group -- GOALS.md's three blocks.

    The groups are declared in order, so the enum that already exists is what
    fixes the reading order; the engine still knows no type by name.

    A row whose value matches no declared group is NEVER dropped: it lands in a
    trailing section. Silently losing a document from a derived index is the
    failure mode that makes people stop trusting the index and go back to
    maintaining it by hand -- which is the cost this whole layer removes.
    """
    group_by = spec["group_by"]
    field = group_by["field"]
    lines: List[str] = []
    claimed = set()
    for group in group_by.get("groups", []):
        value = group.get("value")
        claimed.add(value)
        members = [d for d in rows if d.meta.get(field) == value]
        lines += ["", f"## {group.get('heading', value)}", ""]
        if group.get("guide"):
            lines += [group["guide"], ""]
        lines += _render_table(spec, members, lookup)
    orphans = [d for d in rows if d.meta.get(field) not in claimed]
    if orphans:
        lines += ["", f"## {group_by.get('other', 'Sin clasificar')}", ""]
        lines += _render_table(spec, orphans, lookup)
    return lines


def _render_graph(spec: Dict[str, Any], rows: List[Document]) -> List[str]:
    edge_field = spec.get("edge")
    label_field = spec.get("label", "title")
    nodes, edges, gaps = [], [], []
    for doc in rows:
        node = doc.path.stem
        label = doc.meta.get(label_field) or node
        nodes.append(f'    {_ident(node)}["{label}"]')
        target = doc.meta.get(edge_field)
        if isinstance(target, str) and target.strip():
            edges.append(f"    {_ident(Path(target).stem)} --> {_ident(node)}")
        else:
            gaps.append(label)
    lines = ["```mermaid", "graph TD"] + nodes + edges + ["```"]
    gap_spec = spec.get("gaps")
    if gaps and gap_spec:
        lines += ["", f"# {gap_spec.get('heading', 'Gaps')}", ""]
        if gap_spec.get("guide"):
            lines += [gap_spec["guide"], ""]
        lines += [f"* {name}" for name in gaps]
    return lines


def build_derived(contract: Contract, docs: List[Document]) -> Dict[str, str]:
    """Bodies of the artifacts the model rewrites by hand today.

    Fully driven by `derived_files` in the contract: which type to select, how
    to filter, sort and render. The engine knows nothing about X-Brain's types
    by name -- that is the whole point of having a contract.

    Frontmatter is composed separately so idempotency can be checked on
    content alone.
    """
    out: Dict[str, str] = {}
    lookup = {d.rel: d for d in docs}

    for name, spec in contract.derived.items():
        if not isinstance(spec, dict) or not spec.get("from"):
            continue
        if spec.get("deferred"):
            continue      # declared so tooling knows it exists; not generable yet
        rows = [d for d in docs if d.type == spec["from"]
                and _matches(d, spec.get("where", {}))]
        if spec.get("from_role"):
            patterns = location_patterns_for_match(contract, spec["from"],
                                                   spec["from_role"])
            rows = [d for d in rows if _in_role(d, patterns)]

        for key in reversed(spec.get("order_by", []) or []):
            field = key.get("field") if isinstance(key, dict) else str(key)
            reverse = bool(key.get("desc")) if isinstance(key, dict) else False
            rows.sort(key=lambda d: str(d.meta.get(field) or ""), reverse=reverse)
        if not spec.get("order_by"):
            rows.sort(key=lambda d: d.rel)

        body = ["", GENERATED_MARK, "", f"# {spec.get('heading', name)}", ""]
        if spec.get("render") == "mermaid-graph":
            body += _render_graph(spec, rows)
        elif spec.get("group_by"):
            body += _render_groups(spec, rows, lookup)
        else:
            body += _render_table(spec, rows, lookup)
        out[name] = "\n".join(body).rstrip() + "\n"
    return out


def _ident(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", name) or "n"


def build_stubs(kernel: Path) -> Dict[str, str]:
    """Both stub trees from one source: the module frontmatter."""
    out: Dict[str, str] = {}
    modules = kernel / "modulos"
    if not modules.is_dir():
        return out
    for path in sorted(modules.rglob("*.md")):
        parsed = read_frontmatter(path)
        if parsed is None:
            continue
        meta, _ = parsed
        skill, description = meta.get("skill"), meta.get("description", "")
        if not skill:
            continue
        rel = path.relative_to(kernel).as_posix()
        body = (
            f"Skill del kernel de X-Brain. La lógica vive en el kernel para que el "
            f"sistema pueda actualizarse sin conflictos; no la dupliques ni la edites aquí.\n\n"
            f"Lee `kernel/AGENTS.md` y `cerebro/PERFIL.md` si aún no están cargados, "
            f"y ejecuta las instrucciones de `kernel/{rel}`.\n"
        )
        out[f".claude/skills/{skill}/SKILL.md"] = (
            f"---\nname: {skill}\ndescription: '{description}'\n---\n\n{body}")
        out[f".github/prompts/{skill}.prompt.md"] = (
            f"---\nmode: agent\ndescription: '{description}'\n---\n\n{body}")
    return out


# ============================================================================
# Reporting
# ============================================================================

def write_text_lf(path: Path, content: str) -> None:
    """Write LF, never the platform's line ending.

    Left to itself `write_text` translates \n to os.linesep, so on Windows
    every generated artifact comes out CRLF: the whole file reads as modified
    in the diff and CI's `generate` + `git diff --exit-code` fails on a tree
    nobody touched. Named rather than inlined so there is one place to look,
    not so callers have to remember an argument.
    """
    path.write_text(content, encoding="utf-8", newline="\n")


def write_if_changed(path: Path, content: str) -> bool:
    # Compare RAW -- newlines included. A normalising read reports a CRLF file
    # as already up to date, so it would stay CRLF forever. The validator does
    # normalise: it judges content, this judges bytes on disk.
    #
    # This one has to go through open(): `read_text` gained `newline` in 3.13
    # and the floor is 3.11. Collapse it into `read_text` if the floor moves.
    if path.exists():
        with open(path, "r", encoding="utf-8", newline="") as fh:
            if fh.read() == content:
                return False
    path.parent.mkdir(parents=True, exist_ok=True)
    write_text_lf(path, content)
    return True


# Identifies a hook as ours across installs: the interpreter path is resolved
# at install time, so the script text differs from machine to machine.
PRE_COMMIT_MARKER = "brain.py validate --staged"


def render_bundle_schema(contract: Contract) -> str:
    """The portable ESQUEMA.md written into the bundle.

    This is what makes a shared `cerebro/` self-describing: someone who
    receives the folder without the kernel can still read its data. All prose
    comes from the contract's `bundle_schema` block, not from this file --
    code is English, bundle content is not.
    """
    spec = contract.data.get("bundle_schema", {})
    out = ["", GENERATED_MARK, "",
           f"# {spec.get('title', 'Esquema')}", "",
           f"> {spec.get('intro', '')}", "",
           f"OKF {contract.okf_version} · perfil {contract.profile_version}", ""]

    out += [f"## {spec.get('conventions_heading', 'Convenciones')}", ""]
    for i, rule in enumerate(spec.get("conventions", []), start=1):
        out.append(f"{i}. {rule}")

    structure = spec.get("structure", {})
    if structure:
        out += ["", f"## {spec.get('structure_heading', 'Estructura')}", "",
                "| Carpeta | Semántica |", "|---|---|"]
        for folder, meaning in structure.items():
            out.append(f"| `{folder}` | {meaning} |")

    if contract.levels:
        out += ["", f"## {spec.get('classification_heading', 'Clasificación')}", "",
                spec.get("classification_intro", ""), "",
                "| Nivel | Qué es | Cómo se maneja |", "|---|---|---|"]
        for level in contract.classification.get("levels", []):
            out.append(f"| `{level['value']}` | {level.get('description', '')} "
                       f"| {level.get('handling', '')} |")

    _DATA_TYPE_HINTS.clear()
    _DATA_TYPE_HINTS.update({
        name: ds.get("hint", "") for name, ds in contract.data_types.items()
        if isinstance(ds, dict) and ds.get("hint")
    })
    out += ["", f"## {spec.get('types_heading', 'Tipos')}", "",
            spec.get("types_intro", ""), "",
            f"### {spec.get('common_heading', 'Campos comunes')}", "",
            "Los lleva todo documento, sea del tipo que sea.", ""]
    out += ["| Campo | Tipo | Requerido | Defecto | Guía |", "|---|---|---|---|---|"]
    for name, field in contract.common.items():
        if field.get("deprecated_by"):
            continue
        out.append(_schema_row(name, field))

    labels = spec.get("type_labels", {})
    for type_name, type_spec in contract.types.items():
        # Bundle-facing label if the contract has one; the English engineering
        # description is the fallback, not the default.
        blurb = labels.get(type_name) or type_spec.get("description", "")
        out += ["", f"### {type_name}", "", blurb, ""]
        floor = contract.min_classification(type_name)
        marks = [f"clasificación mínima: `{floor}`"]
        if type_spec.get("personal_data"):
            marks.append("**contiene dato personal**")
        out += ["> " + " · ".join(marks), ""]
        fields = {k: v for k, v in type_spec.get("fields", {}).items()
                  if isinstance(v, dict)}
        if fields:
            out += ["| Campo | Tipo | Requerido | Defecto | Guía |", "|---|---|---|---|---|"]
            for name, field in fields.items():
                out.append(_schema_row(name, field))
        sections = contract.sections_for(type_name)
        if sections:
            out += ["", "Secciones: " + " · ".join(
                f"**{s['heading']}**" + ("" if s.get("required") else " (opcional)")
                for s in sections)]
    return "\n".join(out).rstrip() + "\n"


_DATA_TYPE_HINTS: Dict[str, str] = {}


def bundle_schema_frontmatter(contract: Contract) -> str:
    """Header for the bundle schema, with a fresh generation timestamp."""
    spec = contract.data.get("bundle_schema", {})
    stamp = datetime.now().astimezone().replace(microsecond=0).isoformat()
    return "\n".join([
        "---", f"type: {spec.get('type', 'Indice')}",
        f"title: {quote_scalar(spec.get('title', 'Esquema'))}",
        f"description: {quote_scalar(spec.get('description', ''))}",
        f"resumen: {quote_scalar(spec.get('resumen', ''))}",
        "procedencia: derivado",
        f"classification: {contract.classification.get('default_min', 'internal')}",
        "tags: [generado, esquema]",
        f"generated: {{by: process:brain-generate, at: {stamp}}}",
        "---",
    ])


def _schema_row(name: str, field: Dict[str, Any]) -> str:
    """One row of the bundle schema.

    NEVER renders `note`: that is commentary for whoever maintains the
    contract. Writer-facing guidance lives in `hint`, the same split as
    `placeholder` versus `note`.
    """
    kind = field.get("data_type", "text")
    if kind == "enum":
        kind = " \\| ".join(f"`{v}`" for v in field.get("values", []))
    elif kind == "list":
        kind = f"lista de {field.get('of', 'text')}"
        if field.get("to"):
            kind += f" → {field['to']}"
    elif field.get("to"):
        kind = f"{kind} → {field['to']}"

    required = "sí" if field.get("required") else "no"
    if field.get("severity") == WARNING:
        required += " (aviso)"

    default = field.get("default")
    default = "" if default is None else f"`{json.dumps(default, ensure_ascii=False).strip(chr(34))}`"

    guide = (field.get("hint") or field.get("placeholder")
             or _DATA_TYPE_HINTS.get(field.get("data_type", ""), "") or "")
    if field.get("deprecated_by"):
        guide = f"**obsoleto** → `{field['deprecated_by']}`. {guide}".strip()
    return f"| `{name}` | {kind} | {required} | {default} | {guide} |"


def write_bundle_schema(contract: Contract, bundle: Path) -> bool:
    """The portable schema, inside the bundle.

    It is what makes a shared cerebro/ readable without the system that produced
    it. Compared by BODY, never whole file: the frontmatter carries a generation
    timestamp, so a full comparison would rewrite it on every run and produce a
    spurious diff in every user's repo.
    """
    rel = contract.data.get("bundle_schema", {}).get("path", "ESQUEMA.md")
    body = render_bundle_schema(contract)
    if derived_is_current(bundle / rel, body):
        return False
    write_if_changed(bundle / rel, bundle_schema_frontmatter(contract) + body)
    return True


