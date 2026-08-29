#!/usr/bin/env python3
"""okf -- the deterministic layer of X-Brain.

Validates a knowledge bundle against the contract, and generates every artifact
the contract can produce: templates, JSON Schemas, the catalog, the portable
schema, directory indexes, derived indexes and skill stubs.

Two invariants govern this file:

  1. It NEVER calls an LLM. Everything here is deterministic and idempotent,
     so it can run in CI, on a hook, or a hundred times in a row.
  2. It has NO dependencies. Standard library only, Python 3.9+, so it runs
     with a stock interpreter in a locked-down environment. The binary
     converter and the DuckDB projection are optional layers; this is not.

Usage:
    brain.py validate [PATH] [--fix] [--json] [--full]
    brain.py template TYPE
    brain.py index [PATH]
    brain.py derive
    brain.py stubs
    brain.py generate
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

VERSION = "2.0.0-dev"

DEFAULT_CONTRACT = Path("kernel/schema/contract.json")
DEFAULT_BUNDLE = Path("cerebro")
USER_CONTRACT = "schema.json"

# Spanish, not English: this is an instruction to whoever opened the file, and
# it lands inside the bundle. Same rule as placeholders and section headings.
GENERATED_MARK = ("<!-- generado por brain.py — no editar a mano; "
                  "se edita kernel/schema/contract.json y se regenera -->")

ERROR, WARNING, INFO = "error", "warning", "info"
SEVERITY_ORDER = {ERROR: 0, WARNING: 1, INFO: 2}


# ============================================================================
# OKF-YAML -- a declared subset of YAML
# ============================================================================

class ParseError(Exception):
    """Raised when frontmatter falls outside the OKF-YAML subset.

    Never guess. An ambiguous line is an error with an explanation, because a
    silently mis-parsed value is worse than a refusal.
    """

    def __init__(self, line_no: int, message: str) -> None:
        super().__init__(f"line {line_no}: {message}")
        self.line_no = line_no
        self.message = message


SUBSET_HELP = (
    "OKF-YAML admite: `clave: escalar`, listas inline `[a, b]`, mapas inline "
    "de un nivel `{by: x, at: y}`, listas de bloque con `- `, comillas simples "
    "o dobles, y comentarios ` #`. No admite mapas anidados, escalares "
    "multilínea (`|`, `>`), anclas (`&`, `*`) ni tabulaciones."
)

KEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_.\-À-ɏ]*)\s*:(.*)$")

# --- YAML hazards -----------------------------------------------------------
# A plain (unquoted) YAML scalar cannot contain certain sequences. Our own
# parser is lenient and reads them anyway, which is the dangerous part: the
# validator passes a document that Obsidian and VS Code reject with "mapping
# values are not allowed here". Users hit exactly that. Detection lives here,
# quoting on write lives in `quote_scalar`, and V18 reports it.

YAML_INDICATORS = "-?:,[]{}#&*!|>'\"%@`"
YAML_BOOLISH = {"true", "false", "yes", "no", "on", "off", "null", "~", "y", "n"}
NUMERIC_RE = re.compile(r"^[+-]?(\d[\d_]*(\.\d*)?|\.\d+)([eE][+-]?\d+)?$")


def scalar_hazard(text: str, coercion: bool = True) -> Optional[str]:
    """Why `text` would break or change meaning if written unquoted."""
    if not isinstance(text, str):
        return None
    if text == "":
        return "cadena vacía"
    if text != text.strip():
        return "espacios al inicio o al final, que YAML descarta"
    if ": " in text:
        return "contiene `: ` — en YAML es el indicador de clave y valor, "\
               "y un visor falla con «mapping values are not allowed here»"
    if text.endswith(":"):
        return "termina en `:`, que YAML lee como clave"
    if " #" in text:
        return "contiene ` #` — YAML lo lee como inicio de comentario y "\
               "trunca el valor"
    if text[0] in YAML_INDICATORS:
        return f"empieza por `{text[0]}`, que es un indicador de YAML"
    if coercion and text.lower() in YAML_BOOLISH:
        return f"YAML leería `{text}` como booleano o nulo, no como texto"
    if coercion and NUMERIC_RE.match(text):
        return f"YAML leería `{text}` como número, no como texto"
    return None


def quote_scalar(value: Any) -> str:
    """Render a value for frontmatter, quoting only when it would break."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return ""
    text = str(value)
    if scalar_hazard(text) is None:
        return text
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def quoting_preserves_meaning(line: str) -> bool:
    """Would quoting this frontmatter line leave the value identical?

    The single source of truth for both the V18 message and `fix_yaml_hazards`,
    so the tool cannot promise a repair it will not perform.
    """
    match = KEY_RE.match(line.rstrip())
    if not match:
        return False
    key, rest = match.group(1), match.group(2).strip()
    candidate = f"{key}: {quote_scalar(rest)}"
    try:
        return parse_frontmatter([line.rstrip()]) == parse_frontmatter([candidate])
    except ParseError:
        return False


def scan_yaml_hazards(lines: List[str],
                      field_types: Optional[Dict[str, str]] = None
                      ) -> List[Tuple[int, str, str, bool]]:
    """Find unquoted frontmatter values a standard YAML parser would reject.

    Works on the RAW lines, because by the time our lenient parser is done the
    difference between quoted and unquoted is gone.
    """
    out: List[Tuple[int, str, str, bool]] = []   # (line, key, why, breaks_parsing)
    for offset, raw in enumerate(lines, start=1):
        line = raw.rstrip()
        if not line or line.startswith((" ", "\t", "-", "#")):
            continue
        match = KEY_RE.match(line)
        if not match:
            continue
        key, raw_rest = match.group(1), match.group(2).strip()
        if not raw_rest or raw_rest[0] in "\"'[{":
            continue                    # quoted or a flow collection: fine

        # Assess the VALUE, which is what precedes any comment. `# ...` after a
        # value is legitimate YAML -- our own enum templates use it -- so
        # judging the raw line flags correct files. This was a real bug: the
        # scanner rejected all 12 templates that PyYAML accepts.
        value = _strip_comment(raw_rest).strip()
        declared = (field_types or {}).get(key, "text")
        free_text = declared in ("text", "sentence")

        hazard = scalar_hazard(value, coercion=free_text) if value else None
        if hazard:
            out.append((offset, key, hazard, True))
        elif free_text and value != raw_rest:
            # Not a parse error -- the file opens fine -- but the text after
            # ` #` is silently gone, and on a free-text field that is far more
            # likely to be lost content than an intended comment.
            out.append((offset, key,
                        "contiene ` #`, así que YAML descarta todo lo que sigue "
                        "y el valor queda truncado. Si querías ese texto, "
                        "entrecomilla el valor", False))
    return out


def _strip_comment(text: str) -> str:
    """Remove a trailing ` #` comment that is not inside quotes."""
    out, quote = [], None
    i = 0
    while i < len(text):
        ch = text[i]
        if quote:
            out.append(ch)
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
            out.append(ch)
        elif ch == "#" and (i == 0 or text[i - 1] in " \t"):
            break
        else:
            out.append(ch)
        i += 1
    return "".join(out).rstrip()


def _split_top_level(text: str, sep: str = ",") -> List[str]:
    """Split on `sep`, ignoring separators inside quotes or brackets."""
    parts, buf, quote, depth = [], [], None, 0
    for ch in text:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
            buf.append(ch)
        elif ch in "[{":
            depth += 1
            buf.append(ch)
        elif ch in "]}":
            depth -= 1
            buf.append(ch)
        elif ch == sep and depth == 0:
            parts.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    if quote:
        raise ParseError(0, "comilla sin cerrar")
    tail = "".join(buf).strip()
    if tail or parts:
        parts.append(tail)
    return [p for p in parts if p != ""]


def _scalar(raw: str, line_no: int) -> Any:
    raw = raw.strip()
    if not raw:
        return None
    if raw[0] in "|>":
        raise ParseError(line_no, f"escalar multilínea no admitido. {SUBSET_HELP}")
    if raw[0] in "&*":
        raise ParseError(line_no, f"anclas y alias no admitidos. {SUBSET_HELP}")
    if raw[0] in "\"'":
        quote = raw[0]
        if len(raw) < 2 or raw[-1] != quote:
            raise ParseError(line_no, "comilla sin cerrar")
        return raw[1:-1]
    low = raw.lower()
    if low in ("true", "false"):
        return low == "true"
    if low in ("null", "~"):
        return None
    return raw


def _inline_map(raw: str, line_no: int) -> Dict[str, Any]:
    inner = raw.strip()[1:-1]
    out: Dict[str, Any] = {}
    for item in _split_top_level(inner):
        if ":" not in item:
            raise ParseError(line_no, f"`{item}` no es `clave: valor` dentro del mapa")
        key, _, value = item.partition(":")
        key = key.strip()
        if value.strip().startswith(("{", "[")):
            raise ParseError(
                line_no, f"mapa anidado en `{key}` no admitido. {SUBSET_HELP}")
        out[key] = _scalar(value, line_no)
    return out


def _inline_list(raw: str, line_no: int) -> List[Any]:
    inner = raw.strip()[1:-1]
    out: List[Any] = []
    for item in _split_top_level(inner):
        if item.startswith("{"):
            if not item.endswith("}"):
                raise ParseError(line_no, "mapa inline sin cerrar")
            out.append(_inline_map(item, line_no))
        elif item.startswith("["):
            raise ParseError(line_no, f"lista anidada no admitida. {SUBSET_HELP}")
        else:
            out.append(_scalar(item, line_no))
    return out


def _value(raw: str, line_no: int) -> Any:
    raw = raw.strip()
    if raw.startswith("["):
        if not raw.endswith("]"):
            raise ParseError(line_no, "lista inline sin cerrar")
        return _inline_list(raw, line_no)
    if raw.startswith("{"):
        if not raw.endswith("}"):
            raise ParseError(line_no, "mapa inline sin cerrar")
        return _inline_map(raw, line_no)
    return _scalar(raw, line_no)


def parse_frontmatter(lines: List[str]) -> Dict[str, Any]:
    """Parse an OKF-YAML frontmatter block (without its `---` delimiters)."""
    data: Dict[str, Any] = {}
    pending_key: Optional[str] = None
    i = 0
    while i < len(lines):
        raw_line = lines[i]
        line_no = i + 1
        if "\t" in raw_line:
            raise ParseError(line_no, f"tabulación. {SUBSET_HELP}")
        line = _strip_comment(raw_line)
        if not line.strip():
            i += 1
            continue

        stripped = line.lstrip()
        indent = len(line) - len(stripped)

        if stripped.startswith("- "):
            if pending_key is None:
                raise ParseError(line_no, "elemento de lista sin clave que lo preceda")
            item = stripped[2:].strip()
            value = _inline_map(item, line_no) if item.startswith("{") else _scalar(item, line_no)
            data.setdefault(pending_key, [])
            if not isinstance(data[pending_key], list):
                raise ParseError(line_no, f"`{pending_key}` ya tiene un valor escalar")
            data[pending_key].append(value)
            i += 1
            continue

        if indent:
            raise ParseError(
                line_no, f"indentación inesperada; los mapas anidados no se admiten. {SUBSET_HELP}")

        match = KEY_RE.match(line)
        if not match:
            raise ParseError(line_no, f"no es `clave: valor`. {SUBSET_HELP}")
        key, rest = match.group(1), match.group(2)
        if key in data:
            raise ParseError(line_no, f"clave duplicada `{key}`")
        value = _value(rest, line_no)
        if value is None and not rest.strip():
            pending_key = key           # a block list may follow
            data[key] = None
        else:
            pending_key = None
            data[key] = value
        i += 1
    return {k: v for k, v in data.items()}


# ============================================================================
# Documents
# ============================================================================

FENCE_RE = re.compile(r"^\s*(```|~~~)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
# `<...>` marks an unfilled template slot -- but an HTML comment is not one,
# and every generated file carries one.
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
PLACEHOLDER_RE = re.compile(r"<[^<>\n]{2,}>")
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


class Document:
    def __init__(self, path: Path, bundle: Path,
                 reserved: Optional[Dict[str, Any]] = None) -> None:
        # Which filenames are reserved is declared in the contract, not here.
        self.reserved: Dict[str, Any] = reserved or {}
        self.path = path
        self.rel = path.relative_to(bundle).as_posix()
        self.text = path.read_text(encoding="utf-8", errors="replace")
        self.lines = self.text.splitlines()
        self.meta: Dict[str, Any] = {}
        self.parse_error: Optional[ParseError] = None
        self.has_frontmatter = False
        self.body_start = 0
        self._read_frontmatter()

    def _read_frontmatter(self) -> None:
        if not self.lines or self.lines[0].strip() != "---":
            return
        for idx in range(1, len(self.lines)):
            if self.lines[idx].strip() == "---":
                self.has_frontmatter = True
                self.body_start = idx + 1
                block = self.lines[1:idx]
                try:
                    self.meta = parse_frontmatter(block)
                except ParseError as exc:
                    self.parse_error = ParseError(exc.line_no + 1, exc.message)
                return
        self.parse_error = ParseError(1, "bloque de frontmatter sin cerrar")

    @property
    def type(self) -> Optional[str]:
        value = self.meta.get("type")
        return value if isinstance(value, str) and value.strip() else None

    @property
    def is_reserved(self) -> bool:
        return self.path.name in self.reserved

    @property
    def reserved_format(self) -> Optional[str]:
        """Which structural rule applies, per the contract."""
        return self.reserved.get(self.path.name, {}).get("format")

    def body_lines(self) -> List[Tuple[int, str]]:
        """Body lines with 1-based file line numbers, code fences excluded."""
        out, in_fence = [], False
        for offset, line in enumerate(self.lines[self.body_start:], start=self.body_start + 1):
            if FENCE_RE.match(line):
                in_fence = not in_fence
                continue
            if not in_fence:
                out.append((offset, line))
        return out

    def headings(self) -> List[str]:
        return [HEADING_RE.match(l).group(2) for _, l in self.body_lines() if HEADING_RE.match(l)]

    def links(self) -> List[Tuple[int, str]]:
        out = []
        for line_no, line in self.body_lines():
            for target in LINK_RE.findall(line):
                out.append((line_no, target))
        return out


# ============================================================================
# Contract
# ============================================================================

class Contract:
    def __init__(self, data: Dict[str, Any]) -> None:
        self.data = data
        self.okf_version = data.get("okf_version", "0.2")
        self.profile_version = data.get("profile_version", 1)
        self.common: Dict[str, Any] = data.get("common_fields", {})
        self.types: Dict[str, Any] = data.get("types", {})
        self.actors: Dict[str, str] = {
            k: v for k, v in data.get("actors", {}).items() if k != "note"
        }
        self.data_types: Dict[str, Any] = data.get("data_types", {})
        self.derived: Dict[str, Any] = {
            k: v for k, v in data.get("derived_files", {}).items() if k != "note"
        }
        # Generated and free-prose files are not typed knowledge. Validating
        # them as such would report defects in artifacts this tool itself
        # writes. V13 and V14 cover them instead.
        self.exempt: set = set(self.derived) | {
            k for k in data.get("exempt_files", {}) if k != "note"
        }
        self.governance: Dict[str, Any] = data.get("governance", {})
        self.classification: Dict[str, Any] = data.get("classification", {})
        self.levels: List[str] = [
            lv["value"] for lv in self.classification.get("levels", [])
        ]
        self.provenance: Dict[str, Any] = data.get("provenance", {})
        self.reserved: Dict[str, Any] = {
            k: v for k, v in data.get("reserved_files", {}).items()
            if k != "note" and isinstance(v, dict)
        }
        # The migration ladder declares the default severity; the code used to
        # hardcode it, so the file could say one thing and the validator do
        # another. Same defect class as the hardcoded type names.
        self.default_severity: str = data.get("severity_policy", {}).get("default", ERROR)
        self._resolve_references()

    def _resolve_references(self) -> None:
        """Resolve `values_from` / `default_from` into concrete values.

        A field whose allowed values come from a taxonomy declares where they
        come from instead of repeating the list. Repeating it is how the same
        contract ends up disagreeing with itself.
        """
        for name, field in self.common.items():
            if not isinstance(field, dict):
                continue
            for key, target in (("values_from", "values"), ("default_from", "default")):
                path = field.get(key)
                if not path:
                    continue
                resolved = self._lookup(path)
                if resolved is None:
                    raise SystemExit(
                        f"error: `common_fields.{name}.{key}` apunta a `{path}`, "
                        "que no existe en el contrato.")
                field[target] = resolved

    def _lookup(self, path: str) -> Any:
        node: Any = self.data
        for part in path.split("."):
            if not isinstance(node, dict) or part not in node:
                return None
            node = node[part]
        if isinstance(node, list):
            # A taxonomy is a list of objects; its `value` keys are the enum.
            return [item["value"] for item in node
                    if isinstance(item, dict) and "value" in item] or node
        return node

    def key_field(self, type_name: str) -> Optional[str]:
        """Which field carries this type's identity, if any."""
        return self.types.get(type_name, {}).get("key")

    def locations(self, type_name: str) -> List[Dict[str, Any]]:
        """Location patterns, normalised: a bare string becomes {path: ...}."""
        out = []
        for entry in self.types.get(type_name, {}).get("location", []):
            out.append({"path": entry} if isinstance(entry, str) else dict(entry))
        return out

    def rank(self, level: Optional[str]) -> int:
        """Position in the classification ladder; -1 if unknown or absent."""
        return self.levels.index(level) if level in self.levels else -1

    def min_classification(self, type_name: str) -> str:
        spec = self.types.get(type_name, {})
        return spec.get("min_classification") or \
            self.classification.get("default_min", "interno")

    @classmethod
    def load(cls, kernel_path: Path, bundle: Optional[Path] = None) -> "Contract":
        data = json.loads(kernel_path.read_text(encoding="utf-8"))
        contract = cls(data)
        if bundle:
            user_path = bundle / USER_CONTRACT
            if user_path.exists():
                contract.merge_user(json.loads(user_path.read_text(encoding="utf-8")))
        return contract

    def merge_user(self, user: Dict[str, Any]) -> None:
        """User types are ADDED. Base types can be neither overridden nor removed."""
        for name, spec in user.get("types", {}).items():
            if name in self.types:
                raise SystemExit(
                    f"error: {USER_CONTRACT} redefine el tipo base `{name}`. "
                    "Los tipos del usuario se añaden; los base no se sobrescriben."
                )
            self.types[name] = spec

    def fields_for(self, type_name: str) -> Dict[str, Any]:
        spec = self.types.get(type_name, {})
        merged = dict(self.common)
        merged.update(spec.get("fields", {}))
        return {k: v for k, v in merged.items() if isinstance(v, dict)}

    def sections_for(self, type_name: str) -> List[Dict[str, Any]]:
        out = []
        for section in self.types.get(type_name, {}).get("sections", []):
            if isinstance(section, dict):
                out.append(section)
        return out


# ============================================================================
# Findings
# ============================================================================

class Finding:
    __slots__ = ("check", "severity", "level", "path", "line", "message")

    def __init__(self, check: str, severity: str, level: str,
                 path: str, message: str, line: int = 0) -> None:
        self.check = check
        self.severity = severity
        self.level = level          # "okf" | "profile" | "kernel"
        self.path = path
        self.line = line
        self.message = message

    def as_dict(self) -> dict:
        return {
            "check": self.check, "severity": self.severity, "level": self.level,
            "path": self.path, "line": self.line, "message": self.message,
        }


CHECKS = {
    "V1": ("okf", "frontmatter parseable como OKF-YAML"),
    "V2": ("okf", "`type` presente y no vacío"),
    "V3": ("okf", "estructura de index.md / log.md"),
    "V4": ("profile", "`type` en el catálogo"),
    "V5": ("profile", "campos requeridos presentes"),
    "V6": ("profile", "valores conformes al tipo declarado"),
    "V7": ("profile", "condiciones satisfechas"),
    "V8": ("profile", "campos no declarados"),
    "V9": ("profile", "placeholders sin rellenar"),
    "V10": ("profile", "enlaces bundle-relativos"),
    "V11": ("profile", "typed-ref apunta al tipo declarado"),
    "V12": ("profile", "index.md al día"),
    "V13": ("profile", "derivados sincronizados"),
    "V14": ("kernel", "artefactos generados sincronizados"),
    "V15": ("profile", "stale_after vencido con status stable"),
    "V16": ("profile", "clasificación presente y no por debajo del mínimo del tipo"),
    "V17": ("profile", "responsabilidad resuelta a una ficha Persona"),
    "V18": ("okf", "el frontmatter lo acepta un parser YAML estándar"),
    "V19": ("profile", "el documento está en una ubicación declarada para su tipo"),
    "V20": ("profile", "las referencias por clave resuelven a un documento existente"),
}


# ============================================================================
# Value checking
# ============================================================================

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DATETIME_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2})?(\.\d+)?(Z|[+-]\d{2}:?\d{2})$")


def check_value(name: str, value: Any, spec: Dict[str, Any],
                contract: Contract) -> List[str]:
    """Return a list of problems with `value` against its field spec."""
    problems: List[str] = []
    kind = spec.get("data_type", "text")

    if kind == "list":
        if not isinstance(value, list):
            return [f"`{name}` debe ser una lista"]
        element = {"data_type": spec.get("of", "text")}
        if spec.get("of") == "typed-ref":
            element["to"] = spec.get("to")
        for item in value:
            if spec.get("of") == "map":
                problems += _check_map(name, item, spec, contract)
            else:
                problems += check_value(f"{name}[]", item, element, contract)
        return problems

    if kind == "map":
        if isinstance(value, list):
            if not spec.get("accepts_scalar"):
                problems.append(f"`{name}` no admite lista")
                return problems
            for item in value:
                problems += _check_map(name, item, spec, contract)
            return problems
        return _check_map(name, value, spec, contract)

    if value is None:
        return []
    if isinstance(value, list):
        return [f"`{name}` no debe ser una lista"]

    text = value if isinstance(value, str) else str(value)

    if kind == "enum":
        allowed = spec.get("values", [])
        if text not in allowed:
            problems.append(f"`{name}`: `{text}` no está en {' | '.join(allowed)}")
    elif kind == "boolean":
        if not isinstance(value, bool):
            problems.append(f"`{name}` debe ser true o false")
    elif kind == "date":
        if not DATE_RE.match(text):
            problems.append(f"`{name}`: `{text}` no es YYYY-MM-DD")
    elif kind == "datetime":
        if not DATETIME_RE.match(text):
            problems.append(
                f"`{name}`: `{text}` no es ISO 8601 con offset UTC explícito")
    elif kind == "actor":
        if not any(re.match(p, text) for p in contract.actors.values()):
            problems.append(
                f"`{name}`: `{text}` no es un actor válido "
                "(`human:id`, `process:id` o `producer/version`)")
    elif kind == "sentence":
        limit = spec.get("max_chars", contract.data_types.get("sentence", {}).get("max_chars", 200))
        if len(text) > limit:
            problems.append(f"`{name}`: {len(text)} caracteres, máximo {limit}")
    elif kind in ("link", "typed-ref"):
        if not text.startswith(("/", "./", "../")) and "://" not in text:
            problems.append(f"`{name}`: `{text}` no es un enlace bundle-relativo")
    elif kind == "type-key":
        # A key value, not a path. Resolution is V20's job: doing it here
        # would need the whole bundle, and check_value only sees one field.
        pass
    elif kind == "person-ref":
        # Free text is deliberately allowed here: it is how ownership migrates
        # from names to ficha links without a wall of errors. V17 reports it.
        pass

    return problems


def _check_map(name: str, value: Any, spec: Dict[str, Any],
               contract: Contract) -> List[str]:
    if not isinstance(value, dict):
        return [f"`{name}` debe ser un mapa `{{clave: valor}}`"]
    problems = []
    members = {k: v for k, v in spec.get("fields", {}).items() if isinstance(v, dict)}
    for key, member_spec in members.items():
        if key not in value or value[key] is None:
            if member_spec.get("required"):
                problems.append(f"`{name}.{key}` es requerido")
            continue
        problems += check_value(f"{name}.{key}", value[key], member_spec, contract)
    for key in value:
        if key not in members:
            problems.append(f"`{name}.{key}` no está declarado")
    return problems


# ============================================================================
# Validation
# ============================================================================

class Validator:
    def __init__(self, contract: Contract, bundle: Path) -> None:
        self.contract = contract
        self.bundle = bundle
        self.findings: List[Finding] = []
        self.docs: List[Document] = []
        self.by_path: Dict[str, Document] = {}

    def add(self, check: str, path: str, message: str,
            severity: Optional[str] = None, line: int = 0) -> None:
        level, _ = CHECKS[check]
        if severity is None:
            severity = INFO if level == "okf" and check == "V10" else ERROR
        self.findings.append(Finding(check, severity, level, path, message, line))

    def is_exempt(self, doc: Document) -> bool:
        """Exempt from the PROFILE checks only -- never from OKF conformance.

        A derived or free-prose file still has to be a conformant OKF concept:
        parseable frontmatter with a non-empty `type`. What it does not have to
        do is match a catalog type's field set.
        """
        return doc.rel in self.contract.exempt or doc.path.name in self.contract.exempt

    def collect(self) -> None:
        for root, dirnames, filenames in os.walk(self.bundle):
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            for name in sorted(filenames):
                if name.endswith(".md"):
                    doc = Document(Path(root) / name, self.bundle,
                                   self.contract.reserved)
                    self.docs.append(doc)
                    self.by_path[doc.rel] = doc

    def run(self, only: Optional[set] = None) -> List[Finding]:
        """Validate the bundle. `only` restricts to a set of bundle-relative paths.

        In restricted mode the bundle-wide checks (V12-V14) are skipped: whether
        an index is stale is a property of the whole bundle, not of the files
        someone happens to be committing.
        """
        self.collect()
        for doc in self.docs:
            if only is not None and doc.rel not in only:
                continue
            if doc.is_reserved:
                self.check_reserved(doc)
                continue
            self.check_frontmatter(doc, okf_only=self.is_exempt(doc))
        if only is None:
            self.check_indexes()
            self.check_derived()
        return sorted(
            self.findings,
            key=lambda f: (SEVERITY_ORDER[f.severity], f.check, f.path, f.line),
        )

    # -- per document -------------------------------------------------------

    def check_reserved(self, doc: Document) -> None:
        fmt = doc.reserved_format
        if fmt == "log":
            for line in doc.lines:
                match = HEADING_RE.match(line)
                if match and match.group(1) == "##" and not DATE_RE.match(match.group(2).split()[0]):
                    self.add("V3", doc.rel,
                             f"encabezado de log `{match.group(2)}` no es ISO YYYY-MM-DD")
        elif fmt == "index":
            is_root = doc.path.parent.resolve() == self.bundle.resolve()
            if doc.has_frontmatter and not is_root:
                self.add("V3", doc.rel,
                         "index.md no lleva frontmatter salvo en la raíz del bundle")
            if is_root and doc.has_frontmatter:
                extra = set(doc.meta) - {"okf_version"}
                if extra:
                    self.add("V3", doc.rel,
                             f"el index.md raíz solo admite okf_version; sobra: {', '.join(sorted(extra))}")

    def check_frontmatter(self, doc: Document, okf_only: bool = False) -> None:
        if doc.parse_error:
            self.add("V1", doc.rel, doc.parse_error.message, line=doc.parse_error.line_no)
            return
        if not doc.has_frontmatter:
            self.add("V1", doc.rel, "sin bloque de frontmatter")
            return
        if not doc.type:
            self.add("V2", doc.rel, "falta `type` o está vacío")
            return
        self.check_yaml_safety(doc)
        if okf_only:
            return                      # conformant OKF concept; profile is not its job

        type_name = doc.type
        if type_name not in self.contract.types:
            # OKF requires tolerating unknown types: a warning, never an error.
            self.add("V4", doc.rel, f"tipo `{type_name}` fuera del catálogo",
                     severity=WARNING)
            return

        fields = self.contract.fields_for(type_name)
        owned_elsewhere = {self.contract.classification.get("field", "classification")}

        for name, spec in fields.items():
            if name in owned_elsewhere:
                continue                # V16 owns it, message and severity included
            severity = spec.get("severity", self.contract.default_severity)
            present = name in doc.meta and doc.meta[name] is not None
            if spec.get("deprecated_by") and present:
                self.add("V6", doc.rel,
                         f"`{name}` está obsoleto; usar `{spec['deprecated_by']}`",
                         severity=WARNING)
                continue
            if not present:
                if spec.get("required"):
                    self.add("V5", doc.rel, f"falta `{name}`", severity=severity)
                continue
            for problem in check_value(name, doc.meta[name], spec, self.contract):
                self.add("V6", doc.rel, problem, severity=severity)

        for name in doc.meta:
            if name not in fields:
                self.add("V8", doc.rel, f"`{name}` no está declarado para {type_name}",
                         severity=WARNING)

        self.check_location(doc, type_name)
        self.check_type_keys(doc, type_name)
        self.check_conditions(doc, type_name)
        self.check_classification(doc, type_name)
        self.check_stewardship(doc, type_name)
        self.check_placeholders(doc)
        self.check_links(doc)

    def check_classification(self, doc: Document, type_name: str) -> None:
        """The one classification rule that does NOT relax during migration.

        A missing classification is a warning while the corpus catches up, but
        a document classified BELOW its type's floor is always an error: a
        Persona marked `publico` is a data leak waiting to happen, and no
        migration schedule makes that acceptable.
        """
        field = self.contract.classification.get("field", "classification")
        floor = self.contract.min_classification(type_name)
        value = doc.meta.get(field)

        if not value:
            spec = self.contract.common.get(field, {})
            self.add("V16", doc.rel,
                     f"sin `{field}`; el mínimo de {type_name} es `{floor}`",
                     severity=spec.get("severity", WARNING))
            return
        if self.contract.rank(value) < 0:
            self.add("V16", doc.rel, f"`{field}`: `{value}` no es un nivel conocido")
            return
        if self.contract.rank(value) < self.contract.rank(floor):
            note = self.contract.types[type_name].get("governance_note", "")
            message = f"`{value}` está por debajo del mínimo de {type_name} (`{floor}`)"
            self.add("V16", doc.rel, f"{message}. {note}".strip(), severity=ERROR)

    def check_stewardship(self, doc: Document, type_name: str) -> None:
        """Ownership you cannot resolve is ownership you cannot query."""
        for name, spec in self.contract.fields_for(type_name).items():
            if spec.get("data_type") != "person-ref":
                continue
            value = doc.meta.get(name)
            if not isinstance(value, str) or not value.strip():
                continue
            if not value.startswith("/"):
                self.add("V17", doc.rel,
                         f"`{name}`: `{value}` es texto libre, sin ficha Persona",
                         severity=WARNING)
                continue
            target = self.by_path.get(value.lstrip("/"))
            if target is None:
                self.add("V17", doc.rel, f"`{name}` apunta a {value}, que no existe",
                         severity=WARNING)
            elif target.type != "Persona":
                self.add("V17", doc.rel,
                         f"`{name}` apunta a {value}, que es {target.type}, no Persona")

    def check_yaml_safety(self, doc: Document) -> None:
        """Our parser is lenient; the viewer the user opens is not.

        OKF conformance requires "parseable YAML frontmatter", and a plain
        scalar containing `: ` is not that -- however happily we read it.
        """
        block = doc.lines[1:max(doc.body_start - 1, 1)]
        declared = {n: s.get("data_type", "text")
                    for n, s in self.contract.fields_for(doc.type or "").items()}
        for offset, key, hazard, breaks in scan_yaml_hazards(block, declared):
            # Ask the repair itself whether it can handle this, so the advice
            # and the behaviour cannot drift apart.
            remedy = ("Entrecomillar el valor; `--fix` lo hace."
                      if quoting_preserves_meaning(block[offset - 1])
                      else "`--fix` NO puede arreglarlo: entrecomillar cambiaría "
                           "el valor. Resuélvelo a mano — reescribe el texto o "
                           "entrecomíllalo tú si de verdad querías ese contenido.")
            # Breaking the parser is an error: the file will not open. A
            # truncated value still opens, so it is a warning -- loud, but not
            # something that should block a commit.
            self.add("V18", doc.rel, f"`{key}`: {hazard}. {remedy}",
                     severity=ERROR if breaks else WARNING, line=offset + 1)

    def check_location(self, doc: Document, type_name: str) -> None:
        """The same declaration that routes a new document validates an old one."""
        patterns = location_patterns_for_match(self.contract, type_name)
        if not patterns:
            return
        directory = str(Path(doc.rel).parent).replace("\\", "/")
        directory = "" if directory == "." else directory
        if any(re.match(p, directory) for p in patterns):
            return
        declared = " o ".join(e["path"] for e in self.contract.locations(type_name))
        self.add("V19", doc.rel,
                 f"está en `{directory or '/'}`, y {type_name} se declara en {declared}",
                 severity=WARNING)

    def check_type_keys(self, doc: Document, type_name: str) -> None:
        """A reference by key is only a reference if it resolves."""
        for name, spec in self.contract.fields_for(type_name).items():
            if spec.get("data_type") != "type-key":
                continue
            value = doc.meta.get(name)
            if not isinstance(value, str) or not value.strip():
                continue
            if value in (spec.get("sentinels") or []):
                continue
            target_type = spec.get("to")
            key_field = self.contract.key_field(target_type)
            if not key_field:
                continue
            known = {d.meta.get(key_field) for d in self.docs
                     if d.type == target_type}
            if value not in known:
                self.add("V20", doc.rel,
                         f"`{name}`: no existe ningún {target_type} con "
                         f"{key_field} = `{value}`",
                         severity=WARNING)

    def check_conditions(self, doc: Document, type_name: str) -> None:
        for cond in self.contract.types[type_name].get("conditions", []):
            trigger = cond.get("if", {})
            if not all(str(doc.meta.get(k)) == str(v) for k, v in trigger.items()):
                continue
            described = ", ".join(f"{k}={v}" for k, v in trigger.items())
            for required in cond.get("then_required", []):
                if not doc.meta.get(required):
                    self.add("V7", doc.rel,
                             f"con {described}, `{required}` es requerido",
                             severity=cond.get("severity", self.contract.default_severity))

    def check_placeholders(self, doc: Document) -> None:
        for line_no, raw in doc.body_lines():
            line = HTML_COMMENT_RE.sub("", raw)
            if HEADING_RE.match(line) and "<" not in line:
                continue
            if PLACEHOLDER_RE.search(line) or "TODO" in line:
                self.add("V9", doc.rel, "placeholder sin rellenar", line=line_no)
                return
        for name, value in doc.meta.items():
            if isinstance(value, str) and (PLACEHOLDER_RE.search(value) or "TODO" in value):
                self.add("V9", doc.rel, f"placeholder sin rellenar en `{name}`")
                return

    def check_links(self, doc: Document) -> None:
        for line_no, target in doc.links():
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            if target.startswith("/raw/"):
                continue                      # reserved pointer outside the bundle
            if target.startswith("/"):
                resolved = self.bundle / target.lstrip("/").split("#")[0]
                if not resolved.exists():
                    # OKF: "consumers MUST tolerate broken links" -- they mark
                    # knowledge not yet written. Informational, never an error.
                    self.add("V10", doc.rel, f"enlace sin destino: {target}",
                             severity=INFO, line=line_no)
            elif "://" in target:
                self.add("V10", doc.rel, f"enlace malformado: {target}",
                         severity=ERROR, line=line_no)

        for name, spec in self.contract.fields_for(doc.type or "").items():
            if spec.get("data_type") != "typed-ref" and spec.get("of") != "typed-ref":
                continue
            expected = spec.get("to")
            values = doc.meta.get(name)
            if values is None:
                continue
            for value in (values if isinstance(values, list) else [values]):
                if not isinstance(value, str) or not value.startswith("/"):
                    continue
                target = self.by_path.get(value.lstrip("/"))
                if target and target.type and target.type != expected:
                    self.add("V11", doc.rel,
                             f"`{name}` apunta a {value} que es {target.type}, no {expected}")

    # -- bundle wide --------------------------------------------------------

    def check_indexes(self) -> None:
        for directory, expected in build_indexes(self.contract, self.docs, self.bundle).items():
            path = directory / "index.md"
            rel = path.relative_to(self.bundle).as_posix()
            if not path.exists():
                self.add("V12", rel, "falta index.md en un directorio con conocimiento")
            elif path.read_text(encoding="utf-8").strip() != expected.strip():
                self.add("V12", rel, "index.md desactualizado (auto-arreglable con --fix)")

    def check_derived(self) -> None:
        now = datetime.now()
        for name, body in build_derived(self.contract, self.docs).items():
            path = self.bundle / name
            if not path.exists():
                self.add("V13", name, "derivado ausente (auto-arreglable con --fix)")
            elif not derived_is_current(path, body):
                self.add("V13", name, "derivado desactualizado (auto-arreglable con --fix)")

        for doc in self.docs:
            stale = doc.meta.get("stale_after")
            if not isinstance(stale, str):
                continue
            status = doc.meta.get("status", "stable")
            try:
                when = datetime.strptime(stale[:10], "%Y-%m-%d")
            except ValueError:
                continue
            if when < now and status == "stable":
                self.add("V15", doc.rel,
                         f"stale_after venció el {stale[:10]} y sigue en status stable",
                         severity=WARNING)


# ============================================================================
# Generation
# ============================================================================

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


def location_patterns_for_match(contract: Contract, type_name: str) -> List[str]:
    """Every pattern of the type, as a regex, for validating a real path."""
    out = []
    for entry in contract.locations(type_name):
        path = entry["path"].rstrip("/")
        if path in ("", "."):
            out.append(r"^$")
            continue
        escaped = re.escape(path).replace(r"\{", "{").replace(r"\}", "}")
        out.append("^" + PLACEHOLDER_IN_PATH.sub(r"[^/]+", escaped) + "$")
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

        for key in reversed(spec.get("order_by", []) or []):
            field = key.get("field") if isinstance(key, dict) else str(key)
            reverse = bool(key.get("desc")) if isinstance(key, dict) else False
            rows.sort(key=lambda d: str(d.meta.get(field) or ""), reverse=reverse)
        if not spec.get("order_by"):
            rows.sort(key=lambda d: d.rel)

        body = ["", GENERATED_MARK, "", f"# {spec.get('heading', name)}", ""]
        if spec.get("render") == "mermaid-graph":
            body += _render_graph(spec, rows)
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
        lines = path.read_text(encoding="utf-8").splitlines()
        if not lines or lines[0].strip() != "---":
            continue
        end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
        if end is None:
            continue
        try:
            meta = parse_frontmatter(lines[1:end])
        except ParseError:
            continue
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

def report(findings: List[Finding], bundle: Path, full: bool) -> None:
    if not findings:
        print(f"\nbrain validate {bundle}: sin hallazgos.\n")
        return

    by_check = defaultdict(list)
    for f in findings:
        by_check[f.check].append(f)

    counts = Counter(f.severity for f in findings)
    print()
    print("=" * 66)
    print(f"  BRAIN VALIDATE  --  {bundle}")
    print("=" * 66)
    print()
    print("RESUMEN")
    print(f"  {'check':<6} {'nivel':<8} {'error':>7} {'aviso':>7} {'info':>6}   qué")
    for check in sorted(by_check, key=lambda c: (SEVERITY_ORDER[by_check[c][0].severity], c)):
        group = by_check[check]
        level, label = CHECKS[check]
        # Counts per severity, not "worst severity + total": one check can
        # report both, and "error 2" reading as "2 errors" is a lie when one
        # of them is a warning.
        by_sev = Counter(f.severity for f in group)
        cells = (f"{by_sev.get(ERROR, 0) or '-':>7} "
                 f"{by_sev.get(WARNING, 0) or '-':>7} "
                 f"{by_sev.get(INFO, 0) or '-':>6}")
        print(f"  {check:<6} {level:<8} {cells}   {label}")
    print()
    print("  " + "  ".join(f"{k}: {v:,}" for k, v in
                           sorted(counts.items(), key=lambda kv: SEVERITY_ORDER[kv[0]])))

    limit = None if full else 8
    print()
    print("DETALLE" + ("" if full else f"  (hasta {limit} por check; --full para todo)"))
    for check in sorted(by_check, key=lambda c: (SEVERITY_ORDER[by_check[c][0].severity], c)):
        group = by_check[check]
        print()
        print(f"  {check} -- {CHECKS[check][1]}")
        for f in group[:limit]:
            where = f"{f.path}:{f.line}" if f.line else f.path
            print(f"    [{f.severity:<7}] {where}")
            print(f"              {f.message}")
        if limit and len(group) > limit:
            print(f"    ... y {len(group) - limit:,} más")
    print()


# ============================================================================
# Commands
# ============================================================================

def write_if_changed(path: Path, content: str) -> bool:
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


PRE_COMMIT = """#!/bin/sh
# Installed by `brain.py hooks --install`. Validates only what is being committed:
# a hook that fails on the inherited corpus gets disabled on day one.
exec python3 kernel/bin/brain.py validate --staged
"""


def staged_paths(bundle: Path) -> set:
    """Bundle-relative paths of the .md files staged for commit."""
    import subprocess
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
            capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        raise SystemExit("error: no se pudo consultar el índice de git")
    out = set()
    for line in result.stdout.split("\n"):
        if not line.endswith(".md"):
            continue
        try:
            out.add(Path(line).resolve().relative_to(bundle.resolve()).as_posix())
        except ValueError:
            continue                    # outside the bundle; not our business
    return out


def governance_report(contract: Contract, validator: Validator) -> None:
    """The posture report a data-governance function would actually ask for."""
    docs = [d for d in validator.docs
            if not d.is_reserved and not validator.is_exempt(d) and d.type]
    field = contract.classification.get("field", "classification")

    print()
    print("=" * 66)
    print(f"  GOBIERNO DE DATOS  --  {validator.bundle}")
    print("=" * 66)

    gov = contract.governance
    print()
    print("MARCO")
    print(f"  responsable del contrato   {gov.get('steward', '(sin definir)')}")
    print(f"  revisión                   {gov.get('review_cadence', '(sin definir)')}")
    print(f"  documentos clasificables   {len(docs):,}")

    print()
    print("CLASIFICACIÓN")
    counts = Counter(d.meta.get(field) for d in docs)
    for level in contract.levels:
        n = counts.get(level, 0)
        pct = (100 * n // len(docs)) if docs else 0
        print(f"  {level:<14} {n:>7,}  ({pct:>3}%)")
    unset = counts.get(None, 0)
    if unset:
        print(f"  {'sin clasificar':<14} {unset:>7,}  "
              f"({100 * unset // len(docs) if docs else 0:>3}%)  <- deuda de migración")

    print()
    print("DATO PERSONAL")
    personal = [t for t, s in contract.types.items() if s.get("personal_data")]
    if personal:
        for type_name in personal:
            n = sum(1 for d in docs if d.type == type_name)
            floor = contract.min_classification(type_name)
            print(f"  {type_name:<14} {n:>7,} documentos   piso `{floor}`")
        print("  Revisar estos antes de compartir o exportar el cerebro.")
    else:
        print("  ningún tipo declarado como dato personal")

    print()
    print("RESPONSABILIDAD")
    unresolved = [f for f in validator.findings if f.check == "V17"]
    stewarded = sum(
        1 for d in docs
        for name, spec in contract.fields_for(d.type).items()
        if spec.get("steward") and d.meta.get(name))
    print(f"  campos de responsabilidad con valor   {stewarded:>7,}")
    print(f"  sin resolver a ficha Persona          {len(unresolved):>7,}")

    print()
    print("CONFIANZA  (¿qué escribió un agente y nadie confirmó?)")
    unverified = [d for d in docs if not d.meta.get("verified")]
    by_agent = [d for d in unverified
                if isinstance(d.meta.get("generated"), dict)
                and not str(d.meta["generated"].get("by", "")).startswith("human:")]
    print(f"  sin `verified`                        {len(unverified):>7,}")
    print(f"  de esos, generados por un agente      {len(by_agent):>7,}  <- deuda de revisión")

    print()
    print("CICLO DE VIDA")
    stale = [f for f in validator.findings if f.check == "V15"]
    deprecated = sum(1 for d in docs if d.meta.get("status") == "deprecated")
    print(f"  vencidos y aún `stable`               {len(stale):>7,}")
    print(f"  marcados `deprecated`                 {deprecated:>7,}")

    print()
    print("=" * 66)
    print("  Conteos y formas. No se extrajo contenido de ningún documento.")
    print("=" * 66)
    print()


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


def require_bundle(path: Path) -> None:
    """A missing bundle is a usage error, not a bundle full of findings."""
    if not path.is_dir():
        raise SystemExit(
            f"error: no existe el bundle `{path}`.\n"
            "       Pasa la ruta del cerebro, p.ej. `brain.py validate ruta/al/cerebro`."
        )


def cmd_validate(args) -> int:
    bundle = Path(args.path)
    require_bundle(bundle)
    contract = Contract.load(Path(args.contract), bundle)

    only = staged_paths(bundle) if args.staged else None
    if only is not None and not only:
        print("brain validate --staged: nada del cerebro en el commit.")
        return 0

    validator = Validator(contract, bundle)
    findings = validator.run(only)

    if args.fix:
        changed = apply_fixes(contract, validator, bundle)
        for path in changed:
            print(f"fixed  {path}")
        validator = Validator(contract, bundle)
        findings = validator.run()

    if args.json:
        print(json.dumps([f.as_dict() for f in findings], indent=2, ensure_ascii=False))
    else:
        report(findings, bundle, args.full)
    return 1 if any(f.severity == ERROR for f in findings) else 0


def fix_yaml_hazards(doc: Document) -> bool:
    """Quote the frontmatter values a standard YAML parser would reject.

    Meaning-preserving by construction, and VERIFIED rather than assumed: the
    frontmatter is re-parsed after quoting and must yield an identical mapping,
    otherwise the file is left untouched.
    """
    block_end = max(doc.body_start - 1, 1)
    lines = list(doc.lines)
    hazards = scan_yaml_hazards(lines[1:block_end])
    if not hazards:
        return False

    fixed = False
    for offset, key, _, _breaks in hazards:
        original = lines[offset]
        _, _, rest = original.partition(":")
        candidate = f"{key}: {quote_scalar(rest.strip())}"

        # Verify PER LINE, not per document. A ` #` value is a real comment to
        # YAML and to us, so quoting it would resurrect text that was never
        # part of the value -- that one must stay for a human to resolve. A
        # `: ` value reads the same either way, so it can be quoted safely.
        if not quoting_preserves_meaning(original):
            continue                  # would change meaning: leave it reported
        lines[offset] = candidate
        fixed = True

    if fixed:
        doc.path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return fixed


def apply_fixes(contract: Contract, validator: Validator, bundle: Path) -> List[str]:
    """Only mechanical repairs. Never touches knowledge content.

    Runs to a fixed point: writing a derived file adds a document to the
    bundle, which changes what the indexes should list. Derive first, then
    index, then re-check -- otherwise one pass leaves the bundle inconsistent.
    """
    changed: List[str] = []

    # Quoting comes first: it is per-document and does not depend on the
    # bundle-wide passes below.
    for doc in validator.docs:
        if doc.has_frontmatter and not doc.parse_error and fix_yaml_hazards(doc):
            changed.append(doc.rel + " (frontmatter entrecomillado)")
    if changed:
        validator = Validator(contract, bundle)
        validator.collect()

    for _ in range(3):
        pass_changed: List[str] = []

        for name, body in build_derived(contract, validator.docs).items():
            path = bundle / name
            if not derived_is_current(path, body):
                write_if_changed(path, compose_derived(contract, name, body))
                pass_changed.append(name)

        if pass_changed:                       # the bundle grew; re-read it
            validator = Validator(contract, bundle)
            validator.collect()

        for directory, content in build_indexes(contract, validator.docs, bundle).items():
            if write_if_changed(directory / "index.md", content):
                pass_changed.append((directory / "index.md").relative_to(bundle).as_posix())

        if not pass_changed:
            break
        changed += pass_changed
        validator = Validator(contract, bundle)
        validator.collect()
    return changed


def cmd_govern(args) -> int:
    bundle = Path(args.path)
    require_bundle(bundle)
    contract = Contract.load(Path(args.contract), bundle)
    validator = Validator(contract, bundle)
    validator.run()
    governance_report(contract, validator)
    return 0


def cmd_hooks(args) -> int:
    hook = Path(".git/hooks/pre-commit")
    if not hook.parent.is_dir():
        raise SystemExit("error: no hay un repositorio git aquí")
    if not args.install:
        state = "instalado" if hook.exists() else "no instalado"
        print(f"pre-commit: {state}")
        return 0
    if hook.exists() and PRE_COMMIT not in hook.read_text(encoding="utf-8"):
        raise SystemExit(
            "error: ya existe un pre-commit distinto. Revísalo y compón a mano;\n"
            "       sobrescribir el hook de alguien más no es cosa de esta herramienta.")
    hook.write_text(PRE_COMMIT, encoding="utf-8")
    hook.chmod(0o755)
    print(f"instalado {hook} -- valida solo lo que se commitea")
    return 0


def cmd_place(args) -> int:
    contract = Contract.load(Path(args.contract), Path(args.bundle))
    if args.type not in contract.types:
        raise SystemExit(f"error: tipo `{args.type}` no está en el contrato")

    values: Dict[str, Any] = {}
    for pair in args.field:
        if "=" not in pair:
            raise SystemExit(f"error: `{pair}` no es campo=valor")
        key, _, val = pair.partition("=")
        values[key.strip()] = val.strip()
    for name, spec in contract.fields_for(args.type).items():
        values.setdefault(name, spec.get("default"))

    paths, notes = resolve_locations(contract, args.type, values)
    filename = contract.types[args.type].get("filename")

    if len(paths) == 1:
        print(paths[0] + (filename or ""))
    elif paths:
        print("varios destinos posibles; elige tú:")
        for path in paths:
            print(f"  {path}{filename or ''}")
    else:
        print(f"no se pudo resolver el destino de {args.type}.")
    for note in notes:
        print(f"  nota: {note}")
    if filename and len(paths) != 1:
        print(f"  nombre de archivo: {filename}")
    return 0 if len(paths) == 1 else 1


def cmd_template(args) -> int:
    contract = Contract.load(Path(args.contract), Path(args.bundle))
    sys.stdout.write(render_template(contract, args.type))
    return 0


def cmd_index(args) -> int:
    bundle = Path(args.path)
    contract = Contract.load(Path(args.contract), bundle)
    validator = Validator(contract, bundle)
    validator.collect()
    for directory, content in build_indexes(contract, validator.docs, bundle).items():
        if write_if_changed(directory / "index.md", content):
            print(f"wrote  {(directory / 'index.md').relative_to(bundle)}")
    return 0


def cmd_derive(args) -> int:
    bundle = Path(args.bundle)
    contract = Contract.load(Path(args.contract), bundle)
    validator = Validator(contract, bundle)
    validator.collect()
    for name, body in build_derived(contract, validator.docs).items():
        path = bundle / name
        if not derived_is_current(path, body):
            write_if_changed(path, compose_derived(contract, name, body))
            print(f"wrote  {name}")
    return 0


def cmd_stubs(args) -> int:
    stubs = build_stubs(Path(args.contract).parent.parent)
    if not stubs:
        print("no hay módulos con frontmatter `skill:` todavía")
        return 0
    for rel, content in sorted(stubs.items()):
        if write_if_changed(Path(rel), content):
            print(f"wrote  {rel}")
    return 0


def cmd_generate(args) -> int:
    contract_path = Path(args.contract)
    kernel = contract_path.parent.parent
    contract = Contract.load(contract_path, Path(args.bundle))

    for type_name in contract.types:
        if contract.types[type_name].get("generated_only"):
            continue          # never hand-written: a template would be a lie
        template = render_template(contract, type_name)
        if write_if_changed(kernel / "schema" / "templates" / f"{type_name.lower()}.md",
                            GENERATED_MARK + "\n" + template):
            print(f"wrote  kernel/schema/templates/{type_name.lower()}.md")
        schema = json.dumps(json_schema_for(contract, type_name), indent=2,
                            ensure_ascii=False) + "\n"
        if write_if_changed(kernel / "schema" / "json" / f"{type_name.lower()}.schema.json",
                            schema):
            print(f"wrote  kernel/schema/json/{type_name.lower()}.schema.json")

    # The portable schema lives in the bundle, not the kernel: it is what makes
    # a shared cerebro/ readable without the system that produced it.
    bundle = Path(args.bundle)
    rel = contract.data.get("bundle_schema", {}).get("path", "ESQUEMA.md")
    if bundle.is_dir():
        body = render_bundle_schema(contract)
        # Compare bodies, never whole files: the frontmatter carries a
        # generation timestamp, so a full comparison would rewrite it on every
        # run and produce a spurious diff in every user's repo. Same rule the
        # derived files already followed -- this one had been missed.
        if not derived_is_current(bundle / rel, body):
            write_if_changed(bundle / rel,
                             bundle_schema_frontmatter(contract) + body)
            print(f"wrote  {bundle / rel}")
    else:
        print(f"nota   sin {bundle}/ en este repositorio; se omite {rel}")

    cmd_stubs(args)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="brain.py", description=__doc__.split("\n")[0])
    parser.add_argument("--contract", default=str(DEFAULT_CONTRACT))
    parser.add_argument("--bundle", default=str(DEFAULT_BUNDLE))
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("validate", help="validar el bundle contra el contrato")
    p.add_argument("path", nargs="?", default=str(DEFAULT_BUNDLE))
    p.add_argument("--fix", action="store_true", help="arreglar solo lo mecánico")
    p.add_argument("--staged", action="store_true",
                   help="validar solo los .md en el índice de git (para el pre-commit)")
    p.add_argument("--json", action="store_true")
    p.add_argument("--full", action="store_true", help="listar todos los hallazgos")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("govern", help="informe de postura de gobierno de datos")
    p.add_argument("path", nargs="?", default=str(DEFAULT_BUNDLE))
    p.set_defaults(func=cmd_govern)

    p = sub.add_parser("hooks", help="instalar o consultar el hook de pre-commit")
    p.add_argument("--install", action="store_true")
    p.set_defaults(func=cmd_hooks)

    p = sub.add_parser("place", help="dónde va un documento de este tipo")
    p.add_argument("type")
    p.add_argument("field", nargs="*", help="campo=valor, p.ej. proyecto=2026-q3-erp")
    p.set_defaults(func=cmd_place)

    p = sub.add_parser("template", help="imprimir la plantilla de un tipo")
    p.add_argument("type")
    p.set_defaults(func=cmd_template)

    p = sub.add_parser("index", help="regenerar los index.md")
    p.add_argument("path", nargs="?", default=str(DEFAULT_BUNDLE))
    p.set_defaults(func=cmd_index)

    p = sub.add_parser("derive", help="regenerar los índices derivados")
    p.set_defaults(func=cmd_derive)

    p = sub.add_parser("stubs", help="generar los stubs de ambas herramientas")
    p.set_defaults(func=cmd_stubs)

    p = sub.add_parser("generate", help="regenerar todos los artefactos")
    p.set_defaults(func=cmd_generate)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
