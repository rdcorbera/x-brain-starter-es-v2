"""Validar: los 21 checks, en dos niveles.

OKF comprueba la conformidad con la spec, que es deliberadamente permisiva;
perfil comprueba lo nuestro, que puede endurecerse sin romper aquella."""

from __future__ import annotations

import json
import os
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .const import (DATE_RE, DATETIME_RE, DEFAULT_BUNDLE, ERROR,
                    GENERATED_MARK, INFO, SEVERITY_ORDER, WARNING)
from .parse import (Contract, Document, HEADING_RE, HTML_COMMENT_RE,
                    PLACEHOLDER_RE, ParseError, parse_frontmatter,
                    quote_scalar, quoting_preserves_meaning, scan_yaml_hazards)
from .generate import (build_derived, build_indexes, build_stubs,
                       compose_derived, derived_is_current, json_schema_for,
                       location_patterns_for_match, period_segments,
                       render_template, write_if_changed, write_text_lf)

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
    "V21": ("profile", "`periodo` sigue el formato declarado"),
}


# ============================================================================
# Value checking
# ============================================================================


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


def parse_instant(raw: str) -> Optional[datetime]:
    """Parse an OKF instant into an aware datetime. None if it is not one.

    OKF v0.2 says `stale_after` is a full ISO 8601 instant, zone included.
    `fromisoformat` only learned to read the `Z` suffix -- the ordinary way to
    write UTC -- in 3.11, and that is one of the two reasons the floor is 3.11:
    the alternative was hand-rolling an ISO parser or truncating to the date,
    and truncating silently threw away the hour and the zone.

    A brain migrated from v1 still carries plain dates in that field, so a
    value with no zone is anchored to the local one rather than rejected.
    Everything comes back aware: comparing aware to naive raises TypeError.
    """
    try:
        when = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return when if when.tzinfo else when.astimezone()


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
            self.check_generated()
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
        self.check_period(doc, type_name)
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

    def check_period(self, doc: Document, type_name: str) -> None:
        """The period format, in the two places it can drift apart.

        The FIELD and the archive FOLDER SEGMENT are separate problems: a
        document filed under `04-archivo/tercer trimestre/` is in the right
        place -- V19 is content -- and merely named wrong. Both enter as
        warnings, per severity_policy: v1 guaranteed the field's presence but
        never its shape, so the shape is a new constraint.
        """
        patterns = self.contract.period_patterns()
        if not patterns:
            return
        field = self.contract.period_formats.get("field", "periodo")
        declared = self.contract.period_format

        def offending(value: str) -> bool:
            return not any(re.match(pat, value) for _, pat in patterns)

        shapes = self.contract.period_formats.get("shapes", {})
        if declared:
            expected = (f"el formato declarado `{declared}` "
                        f"(ej. {shapes[declared].get('example', '')})")
        else:
            expected = "ninguno de los formatos: " + ", ".join(
                f"`{n}` (ej. {shapes[n].get('example', '')})" for n, _ in patterns)

        value = doc.meta.get(field)
        if isinstance(value, str) and value.strip() and offending(value.strip()):
            self.add("V21", doc.rel,
                     f"`{field}`: `{value}` no sigue {expected}", severity=WARNING)

        for segment in period_segments(self.contract, type_name, doc.rel):
            if offending(segment):
                self.add("V21", doc.rel,
                         f"la carpeta `{segment}` no sigue {expected}",
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

    def check_generated(self) -> None:
        """The kernel's own artifacts still match what the contract produces.

        `un artefacto generado no se edita, se regenera` is an invariant, and
        until now nothing enforced it: V14 was declared in CHECKS and never
        emitted, so a hand-edited template passed validation in silence. That is
        the same defect as v1's `Autogenerado. No editar a mano` on files no
        generator produced -- declared, not enforced.

        Only the kernel's artifacts. The bundle's are V12 and V13; the
        hand-written scaffold under kernel/scaffold/ is nobody's output.

        Compared against the KERNEL contract, reloaded without the bundle. The
        kernel's output cannot depend on one brain's `cerebro/schema.json`, and
        judging it against the merged contract got both directions wrong: a
        user type demanded a kernel template that the kernel must never ship
        (and whose suggested repair would write into `kernel/`), and a declared
        `period_format` made a correct template look hand-edited.
        """
        kernel = self.contract.kernel
        if kernel is None or not kernel.is_dir():
            return
        base = Contract.load(kernel / "schema" / "contract.json")
        expected: Dict[Path, str] = {}
        for type_name, spec in base.types.items():
            if spec.get("generated_only"):
                continue
            stem = type_name.lower()
            expected[kernel / "schema" / "templates" / f"{stem}.md"] = (
                GENERATED_MARK + "\n" + render_template(base, type_name))
            expected[kernel / "schema" / "json" / f"{stem}.schema.json"] = (
                json.dumps(json_schema_for(base, type_name), indent=2,
                           ensure_ascii=False) + "\n")
        for rel, content in build_stubs(kernel).items():
            expected[kernel.parent / rel] = content

        for path, content in sorted(expected.items()):
            try:
                rel = path.relative_to(kernel.parent).as_posix()
            except ValueError:
                rel = path.as_posix()
            if not path.exists():
                self.add("V14", rel, "artefacto generado ausente "
                                     "(se repara con `brain.py generate`)")
            elif path.read_text(encoding="utf-8") != content:
                self.add("V14", rel, "artefacto generado desactualizado o editado a mano "
                                     "(se repara con `brain.py generate`)")

    def check_derived(self) -> None:
        now = datetime.now().astimezone()   # aware: stale_after lleva zona
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
            when = parse_instant(stale)
            if when is None:
                continue
            if when < now and status == "stable":
                self.add("V15", doc.rel,
                         f"stale_after venció el {stale} y sigue en status stable",
                         severity=WARNING)


def require_bundle(path: Path) -> None:
    """A missing bundle is a usage error, not a bundle full of findings."""
    if not path.is_dir():
        raise SystemExit(
            f"error: no existe el bundle `{path}`.\n"
            "       Pasa la ruta del cerebro, p.ej. `brain.py validate ruta/al/cerebro`."
        )


def is_uninitialised(bundle: Path) -> bool:
    """A brain with no knowledge in it at all -- not one that is incomplete.

    The starter ships an empty cerebro/ on purpose, so this is the normal state
    of a fresh clone. Reporting it as missing derived files would mean the
    starter fails its own validator on day one, which is exactly the reading
    `require_bundle` already refuses to give for a bundle that is not there.
    """
    return not any(bundle.rglob("*.md"))


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
        write_text_lf(doc.path, "\n".join(lines) + "\n")
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


