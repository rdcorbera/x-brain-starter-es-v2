"""Leer: OKF-YAML, documentos, contrato y los moldes del kernel.

El primero de los cuatro trabajos. No escribe nada y no valida nada: convierte
texto en estructuras. Todo lo demás depende de esto y esto no depende de nada."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .const import ERROR, GENERATED_MARK, USER_CONTRACT

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
        self.kernel: Optional[Path] = None
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
        self.user_contract: Dict[str, Any] = data.get("user_contract", {})
        self.period_formats: Dict[str, Any] = data.get("period_formats", {})
        self.period_format: Optional[str] = None   # set by merge_user
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
        # Where this contract came from, so V14 can ask whether the artifacts it
        # produces are still what is on disk. Without it the check could only be
        # declared, which is what it was.
        contract.kernel = kernel_path.parent.parent
        if bundle:
            user_path = bundle / USER_CONTRACT
            if user_path.exists():
                contract.merge_user(json.loads(user_path.read_text(encoding="utf-8")))
        return contract

    def merge_user(self, user: Dict[str, Any]) -> None:
        """Apply cerebro/schema.json, dispatching on what the contract declares.

        The accepted keys and their `mode` live in the contract's `user_contract`
        block, so the next user-settable knob costs a contract edit and not a
        code change. An undeclared key is refused rather than ignored: a typo in
        a config file that quietly does nothing is the exact failure this block
        exists to remove.
        """
        declared = self.user_contract.get("keys", {})
        for key, value in user.items():
            if key == "note":
                continue
            spec = declared.get(key)
            if spec is None:
                accepted = ", ".join(f"`{k}`" for k in sorted(declared))
                raise SystemExit(
                    f"error: {USER_CONTRACT} declara `{key}`, que el contrato no acepta. "
                    f"Claves admitidas: {accepted}."
                )
            mode = spec.get("mode")
            if mode == "add":
                self._merge_add(key, value)
            elif mode == "choose":
                self._merge_choose(key, value, spec)
            else:
                raise SystemExit(
                    f"error: el contrato declara `{key}` con mode `{mode}`, "
                    "que esta versión del kernel no sabe aplicar."
                )

    def _merge_add(self, key: str, value: Dict[str, Any]) -> None:
        """User entries are ADDED. Base entries can be neither overridden nor removed."""
        base = getattr(self, key)
        for name, spec in (value or {}).items():
            if name in base:
                raise SystemExit(
                    f"error: {USER_CONTRACT} redefine el tipo base `{name}`. "
                    "Los tipos del usuario se añaden; los base no se sobrescriben."
                )
            base[name] = spec

    def _merge_choose(self, key: str, value: Any, spec: Dict[str, Any]) -> None:
        """The user names one option; the kernel owns what the option means."""
        options = self._lookup(spec.get("from", "")) or {}
        if value not in options:
            allowed = ", ".join(f"`{k}`" for k in options)
            raise SystemExit(
                f"error: {USER_CONTRACT} declara {key} = `{value}`, que no es una "
                f"opción. Admitidas: {allowed}."
            )
        setattr(self, key, value)

    def period_patterns(self) -> List[Tuple[str, str]]:
        """(shape name, regex) for the declared shape -- or for all of them.

        With nothing declared every shape is accepted. That still catches
        `tercer trimestre` without demanding configuration and without assuming
        a cycle the user never chose.
        """
        shapes = self.period_formats.get("shapes", {})
        if self.period_format and self.period_format in shapes:
            names = [self.period_format]
        else:
            names = list(shapes)
        return [(n, shapes[n]["pattern"]) for n in names if shapes[n].get("pattern")]

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


def read_frontmatter(path: Path) -> Optional[Tuple[Dict[str, Any], str]]:
    """(metadata, body) of a kernel markdown file, or None if it has no block.

    Not a Document: these files live in the kernel, not in the bundle, and are
    never validated as knowledge. What they share with a Document is the OKF
    frontmatter, so they share its parser.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return None
    try:
        meta = parse_frontmatter(lines[1:end])
    except ParseError:
        return None
    return meta, "\n".join(lines[end + 1:]).lstrip("\n")


def frontmatter_block(text: str) -> str:
    """The opening `---` block, verbatim and delimiters included.

    A role profile replaces only the BODY of PERFIL.md. Its frontmatter --
    `type`, `classification: confidential` -- is the same for every role, so it
    stays declared once in the generic scaffold instead of being copied into
    each profile, where it would drift.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return ""
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    return "" if end is None else "\n".join(lines[:end + 1]) + "\n"


def find_profiles(kernel: Path) -> Dict[str, Dict[str, Any]]:
    """The role profiles on offer, by slug: the kernel's, then the user's.

    Two directories, one shape. `plugins/` is searched last and wins on a slug
    collision, which is how a user adapts a shipped role without editing the
    kernel -- copy it across and change it there.

    `kernel/scaffold/profiles/` is deliberately a SUBdirectory: `cmd_init`
    copies the scaffold with a non-recursive glob, so the moulds sit next to
    PERFIL.md without being poured into every brain.

    The slug is the FILENAME. It was a `profile:` field until the audit found
    that the only value it was allowed to hold was the file's own stem -- a
    field that can only ever be wrong is one to delete, not to validate.
    """
    out: Dict[str, Dict[str, Any]] = {}
    for origin, directory in (("kernel", kernel / "scaffold" / "profiles"),
                              ("usuario", kernel.parent / "plugins" / "profiles")):
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.md")):
            parsed = read_frontmatter(path)
            if parsed is None:
                continue
            meta, body = parsed
            out[path.stem] = {"meta": meta, "body": body,
                              "path": path, "origin": origin}
    return out


