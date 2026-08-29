#!/usr/bin/env python3
"""Round-trip test: generator and validator check each other.

The invariant: every template `brain.py` generates, filled with values that
conform to the contract, must validate clean. If it does not, one of the two
is wrong -- and which one is a real bug, not a matter of taste.

This exists because the generator once proposed `classification: interno` on a
Persona whose own floor was `confidencial`. A human caught it. A test should.

Stdlib only. Run from the repo root:

    python3 kernel/tests/test_roundtrip.py
"""

from __future__ import annotations

import importlib.util
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parents[2]


def load_brain():
    spec = importlib.util.spec_from_file_location("brain", ROOT / "kernel" / "bin" / "brain.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


brain = load_brain()

# Conformant sample values, by declared data type.
SAMPLES = {
    "text": "Valor de prueba",
    "sentence": "Una oración de prueba que describe el documento.",
    "date": "2026-08-28",
    "datetime": "2026-08-28T10:00:00Z",
    "boolean": "false",
    "link": "/02-areas/personas/persona-de-prueba.md",
    "typed-ref": "/02-areas/personas/persona-de-prueba.md",
    "person-ref": "/02-areas/personas/persona-de-prueba.md",
    "actor": "human:prueba",
}

PLACEHOLDER = re.compile(r"<[^<>\n]{2,}>")


def fill(template: str, contract, type_name: str) -> str:
    """Replace every placeholder with a value the contract accepts."""
    fields = contract.fields_for(type_name)
    lines, in_frontmatter, out = template.splitlines(), False, []

    for line in lines:
        if line.strip() == "---":
            in_frontmatter = not in_frontmatter or False if in_frontmatter else True
            out.append(line)
            continue
        if ":" in line and PLACEHOLDER.search(line):
            key = line.split(":", 1)[0].strip()
            spec = fields.get(key, {})
            kind = spec.get("data_type", "text")
            if kind == "map":
                members = ", ".join(
                    f"{k}: {SAMPLES.get(v.get('data_type', 'text'), 'x')}"
                    for k, v in spec.get("fields", {}).items() if isinstance(v, dict))
                out.append(f"{key}: {{{members}}}")
                continue
            out.append(f"{key}: {SAMPLES.get(kind, SAMPLES['text'])}")
            continue
        out.append(PLACEHOLDER.sub("Contenido de prueba.", line))
    return "\n".join(out) + "\n"


def check_provenance(contract) -> List[str]:
    """Every path listed under `provenance` must still exist.

    The block answers "what do we update when a new OKF version ships". A list
    that silently rots answers it wrongly, which is worse than not having one.
    """
    problems = []
    buckets = ("from_okf", "from_v1", "from_x_brain")
    listed = [p for b in buckets for p in contract.provenance.get(b, [])]

    for path in listed:
        if contract._lookup(path) is None:
            problems.append(f"provenance lista `{path}`, que ya no existe en el contrato")

    seen = [p for p in listed if listed.count(p) > 1]
    for path in sorted(set(seen)):
        problems.append(f"`{path}` aparece en más de una categoría de provenance")

    declared = {p.split(".", 1)[1] for p in listed if p.startswith("common_fields.")}
    unlisted = set(contract.common) - declared
    if unlisted:
        problems.append(
            "campos comunes sin clasificar en provenance (¿del estándar o nuestros?): "
            + ", ".join(sorted(unlisted)))
    return problems


def check_locations(contract) -> List[str]:
    """Locations must be resolvable, and key references must have a target.

    Making `location` routable is what exposed that Insumo, Playbook and
    Iniciativa itself referenced `{proyecto}` without declaring the field. A
    pattern nobody can fill is documentation pretending to be a contract.
    """
    problems = []
    for type_name, spec in contract.types.items():
        declared = set(contract.fields_for(type_name))

        for entry in contract.locations(type_name):
            path = entry["path"]
            for holder in re.findall(r"\{(\w+)\}", path):
                if holder not in declared:
                    problems.append(
                        f"{type_name}: la ubicación `{path}` usa `{{{holder}}}`, "
                        f"que el tipo no declara como campo")
            for field in entry.get("when", {}):
                if field not in declared:
                    problems.append(
                        f"{type_name}: el `when` de `{path}` mira `{field}`, "
                        f"que el tipo no declara")
            if entry.get("role") not in (None, "active", "archive"):
                problems.append(f"{type_name}: `role` desconocido en `{path}`")

        for name, field in contract.fields_for(type_name).items():
            if field.get("data_type") != "type-key":
                continue
            target = field.get("to")
            if target not in contract.types:
                problems.append(
                    f"{type_name}.{name} referencia el tipo `{target}`, que no existe")
            elif not contract.key_field(target):
                problems.append(
                    f"{type_name}.{name} referencia a {target}, que no declara `key` "
                    "-- no hay contra qué resolver")
    return problems


def check_yaml_compatibility(contract) -> List[str]:
    """Every generated template must open in a real YAML parser.

    Users reported documents failing in Obsidian and VS Code with "mapping
    values are not allowed here" -- and the starter's own templates had the
    defect, because our parser is lenient and never complained. Two layers:
    our own hazard scan always, and PyYAML when it happens to be installed,
    since the kernel itself must not depend on it.
    """
    try:
        import yaml
    except ImportError:
        yaml = None

    problems = []
    for type_name in contract.types:
        if contract.types[type_name].get("generated_only"):
            continue
        text = brain.render_template(contract, type_name)
        match = re.search(r"^---\n(.*?)\n---", text, re.S | re.M)
        if not match:
            continue
        block = match.group(1).splitlines()

        declared = {n: s.get("data_type", "text")
                    for n, s in contract.fields_for(type_name).items()}
        for _, key, hazard, _breaks in brain.scan_yaml_hazards(block, declared):
            problems.append(f"plantilla {type_name}: `{key}` {hazard[:70]}")

        if yaml:
            try:
                yaml.safe_load(match.group(1))
            except Exception as exc:
                problems.append(
                    f"plantilla {type_name}: PyYAML la rechaza -- "
                    f"{str(exc).splitlines()[0]}")
    if yaml is None:
        print("  (PyYAML no instalado: solo se comprobó con scan_yaml_hazards)")
    return problems


def main() -> int:
    contract = brain.Contract.load(ROOT / "kernel" / "schema" / "contract.json")
    tmp = Path(tempfile.mkdtemp(prefix="brain-roundtrip-"))
    failures = (check_provenance(contract) + check_yaml_compatibility(contract)
                + check_locations(contract))

    try:
        (tmp / "02-areas" / "personas").mkdir(parents=True)
        # A real Persona so that typed-ref and person-ref targets resolve.
        anchor = brain.render_template(contract, "Persona")
        (tmp / "02-areas" / "personas" / "persona-de-prueba.md").write_text(
            fill(anchor, contract, "Persona"), encoding="utf-8")

        for type_name in contract.types:
            if contract.types[type_name].get("generated_only"):
                continue
            body = fill(brain.render_template(contract, type_name), contract, type_name)
            (tmp / f"caso-{type_name.lower()}.md").write_text(body, encoding="utf-8")

        validator = brain.Validator(contract, tmp)
        findings = validator.run()
        errors = [f for f in findings if f.severity == brain.ERROR
                  and f.check not in ("V12", "V13")]   # bundle-wide, not our subject

        for f in errors:
            failures.append(f"{f.path}: [{f.check}] {f.message}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    tested = [t for t in contract.types if not contract.types[t].get("generated_only")]
    if failures:
        print(f"FALLO -- {len(failures)} problema(s):\n")
        for line in failures:
            print(f"  {line}")
        print("\nEl contrato es inconsistente consigo mismo: o una plantilla generada "
              "no pasa su propio validador, o el bloque provenance no describe el "
              "archivo. En cualquier caso, uno de los dos está mal.")
        return 1

    print(f"OK -- provenance completo, y las plantillas de los {len(tested)} tipos, "
          "rellenadas, validan limpio.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
