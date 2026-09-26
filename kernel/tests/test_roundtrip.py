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

import ast
import importlib.util
import io
import re
import shutil
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
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


def accepts_sentinel(entry: dict, field: str, value: str) -> bool:
    """Can this location receive a document whose `field` is the sentinel?

    Two ways it cannot: the path interpolates the field -- so the sentinel ends
    up as a directory name, which is not a place -- or a `when` rules it out.
    """
    if "{%s}" % field in entry["path"]:
        return False
    condition = entry.get("when", {}).get(field)
    if condition is None:
        return True
    if isinstance(condition, dict):
        return condition.get("not") != value
    return condition == value


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
            # A sentinel is a value declared valid without resolving to a
            # document -- so SOME location has to be able to receive it. Four
            # types declared `transversal` (three of them as the DEFAULT) with
            # nowhere to put such a document: every location interpolated
            # `{proyecto}`, so the sentinel would have become a literal folder
            # named `transversal`, and V19 flagged the document wherever it
            # actually went. Found by hand while writing /x-procesar-inbox,
            # which is the skill that routes them; checked here so the next one
            # is not.
            for sentinel in field.get("sentinels", []):
                if not any(accepts_sentinel(entry, name, sentinel)
                           for entry in contract.locations(type_name)):
                    problems.append(
                        f"{type_name}.{name} admite `{sentinel}` pero ninguna "
                        f"ubicación puede recibirlo: o se declara una rama "
                        f"`when: {{{name}: {sentinel}}}`, o sobra el centinela")

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


def check_derived_specs(contract) -> List[str]:
    """A derived index must select and group by things that actually exist.

    `GOALS.md` groups Iniciativa by `origen`, and the whole point of deriving it
    is that nobody maintains it. If a group value drifts from the enum, the
    documents in it disappear from the index in silence -- and a derived file
    people cannot trust is worse than the hand-written one it replaced.
    """
    problems = []
    for name, spec in contract.derived.items():
        if not isinstance(spec, dict) or not spec.get("from"):
            continue
        source = spec["from"]
        if source not in contract.types:
            problems.append(f"{name}: `from` es `{source}`, que no está en el catálogo")
            continue
        fields = contract.fields_for(source)

        role = spec.get("from_role")
        if role is not None:
            roles = {e.get("role", "active") for e in contract.locations(source)}
            if role not in roles:
                problems.append(
                    f"{name}: `from_role: {role}` y {source} no declara ninguna "
                    f"ubicación con ese rol (tiene: {', '.join(sorted(roles)) or 'ninguna'})")

        group_by = spec.get("group_by")
        if not group_by:
            continue
        field = group_by.get("field")
        if field not in fields:
            problems.append(f"{name}: agrupa por `{field}`, que {source} no declara")
            continue
        allowed = fields[field].get("values")
        for group in group_by.get("groups", []):
            value = group.get("value")
            if allowed and value not in allowed:
                problems.append(
                    f"{name}: el grupo `{value}` no es un valor de {source}.{field} "
                    f"({' | '.join(allowed)})")
        if allowed:
            covered = {g.get("value") for g in group_by.get("groups", [])}
            missing = [v for v in allowed if v not in covered]
            if missing and not group_by.get("other"):
                problems.append(
                    f"{name}: no cubre {', '.join(missing)} y no declara `other`, "
                    "así que esos documentos no saldrían en ningún bloque")
    return problems


def check_init(contract) -> List[str]:
    """`brain init` produces a bundle that passes its own validator, twice.

    The starter ships an empty cerebro/ on purpose, so `init` is what every user
    runs first. If its output does not validate, the very first thing a new
    brain reports is a defect in itself.
    """
    problems = []
    tmp = Path(tempfile.mkdtemp(prefix="brain-init-"))
    try:
        args = SimpleNamespace(
            path=str(tmp / "cerebro"),
            contract=str(ROOT / "kernel" / "schema" / "contract.json"))
        with redirect_stdout(io.StringIO()):
            brain.cmd_init(args)
        bundle = Path(args.path)

        before = {p: p.read_bytes() for p in sorted(bundle.rglob("*")) if p.is_file()}
        with redirect_stdout(io.StringIO()):
            brain.cmd_init(args)
        after = {p: p.read_bytes() for p in sorted(bundle.rglob("*")) if p.is_file()}
        for path in sorted(set(before) | set(after)):
            if before.get(path) != after.get(path):
                problems.append(
                    f"init no es idempotente: `{path.name}` cambia en la segunda corrida")

        findings = brain.Validator(contract, bundle).run()
        for f in findings:
            if f.severity == brain.ERROR:
                problems.append(f"init deja un cerebro que no valida: "
                                f"{f.path}: [{f.check}] {f.message}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
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


def check_period_formats(contract) -> List[str]:
    """The period shapes, and the user declaration that selects one.

    V14 shipped declared and dead for a whole cut because nothing exercised it.
    V21 gets its test in the same commit as its code: each shape must accept its
    own documented example and reject the other two, the undeclared brain must
    accept all three, and every wrong declaration must be refused rather than
    ignored -- a config typo that quietly does nothing is what V21 exists to end.
    """
    problems = []
    shapes = contract.period_formats.get("shapes", {})
    if not shapes:
        return ["el contrato no declara `period_formats.shapes`"]

    examples = {n: s["example"] for n, s in shapes.items()}
    for name, spec in shapes.items():
        pattern = spec["pattern"]
        if not re.match(pattern, spec["example"]):
            problems.append(
                f"period_formats.{name}: su propio ejemplo `{spec['example']}` "
                "no casa con su patrón")
        for other, example in examples.items():
            if other != name and re.match(pattern, example):
                problems.append(
                    f"period_formats.{name}: acepta `{example}`, que es el "
                    f"ejemplo de `{other}` -- las formas deben ser disjuntas")

    # Values the prose used to allow because `periodo` was an unchecked text field.
    for junk in ("2026-q3", "Q3-2026", "tercer trimestre", "T3", "2026-8", "2026-S4"):
        for name, spec in shapes.items():
            if re.match(spec["pattern"], junk):
                problems.append(f"period_formats.{name}: acepta `{junk}`")

    base = ROOT / "kernel" / "schema" / "contract.json"
    undeclared = brain.Contract.load(base)
    if len(undeclared.period_patterns()) != len(shapes):
        problems.append("sin declarar, period_patterns() no ofrece todas las formas")

    for name in shapes:
        c = brain.Contract.load(base)
        c.merge_user({"period_format": name})
        got = [n for n, _ in c.period_patterns()]
        if got != [name]:
            problems.append(f"declarado `{name}`, period_patterns() dio {got}")

    for bad in ({"period_format": "trimestral"}, {"periodo_format": "monthly"},
                {"types": {"Reunion": {}}}):
        c = brain.Contract.load(base)
        try:
            c.merge_user(bad)
        except SystemExit:
            continue
        problems.append(f"{bad} debía ser rechazado por merge_user y pasó")

    return problems


def check_role_profiles(contract) -> List[str]:
    """Every role profile is a usable PERFIL.md, not just a file that parses.

    The failure this prevents is silent: a profile missing one of the six
    headings would seed a PERFIL.md with a section simply absent, and nothing
    downstream would complain -- PERFIL.md is in `exempt_files`, so the
    validator only asks it for a `type`.

    The headings are read from the generic scaffold rather than listed here, so
    adding a section to PERFIL.md makes this test demand it of every profile
    instead of quietly passing.
    """
    problems = []
    kernel = ROOT / "kernel"
    scaffold = kernel / "scaffold" / "PERFIL.md"
    expected = re.findall(r"^# (.+)$", scaffold.read_text(encoding="utf-8"), re.M)
    if len(expected) < 2:
        return [f"no se pudieron leer los encabezados de {scaffold}"]

    profiles = brain.find_profiles(kernel)
    if not profiles:
        return ["no hay profiles en kernel/scaffold/profiles/"]

    shapes = contract.period_formats.get("shapes", {})
    for slug, entry in sorted(profiles.items()):
        meta, body, path = entry["meta"], entry["body"], entry["path"]
        where = path.relative_to(ROOT).as_posix()
        assert path.stem == slug

        if meta.get("profile"):
            problems.append(f"{where}: trae `profile:`, que se eliminó — el slug es el "
                            "nombre del archivo")
        for key in ("title", "description"):
            if not meta.get(key):
                problems.append(f"{where}: falta `{key}`")
        if meta.get("kind") not in ("individual", "leadership"):
            problems.append(f"{where}: `kind` es `{meta.get('kind')}`, "
                            "y solo vale individual o leadership")
        period = meta.get("period_format")
        if period not in shapes:
            problems.append(f"{where}: propone period_format `{period}`, "
                            f"que no es una forma del contrato ({', '.join(shapes)})")

        found = re.findall(r"^# (.+)$", body, re.M)
        for heading in expected:
            if heading not in found:
                problems.append(f"{where}: le falta la sección `# {heading}`")
        if brain.frontmatter_block(body):
            problems.append(f"{where}: el cuerpo trae su propio frontmatter; "
                            "el de PERFIL.md lo pone el scaffold genérico")

    return problems


def check_competency_questions(contract) -> List[str]:
    """Every `fields` entry of a CQ must exist on at least one of its `types`.

    The CQs are the acceptance criterion of the contract, and in cut 2 each
    grows a `sql:` key -- a field that exists on none of its types cannot be
    queried, so the test would fail then instead of now. The defect is not
    hypothetical: the yml's own `intake_corrections` records it being caught by
    hand once (`Pregunta no declara fecha`), and the Agent Zero intake
    reproduced it exactly on another question. Nothing parsed this file until
    now, so its consistency depended on somebody looking.

    The semantics are UNION, not intersection: a CQ may list several types and
    draw a different field from each -- CQ-32 needs `Reunion.asistentes` and
    `Decision.decisores` at once, and that is correct. Only a field that exists
    on NO declared type is an error.
    """
    path = ROOT / "kernel" / "tests" / "competency-questions.yml"
    if not path.exists():
        return []
    problems: List[str] = []
    common = set(contract.common)
    # Fields a plan has decided to add but that are not in the contract yet.
    # Declared in the yml itself so this list is not a second source of truth.
    text = path.read_text(encoding="utf-8")
    pending = set(re.findall(r"^\s*#\s*pending-field:\s*(\S+)", text, re.M))

    for block in re.split(r"\n  - id: ", text)[1:]:
        cq = block.split("\n", 1)[0].strip()
        if cq.startswith("ADV"):
            continue
        types_m = re.search(r"^\s*types:\s*\[(.*?)\]", block, re.M)
        fields_m = re.search(r"^\s*fields:\s*\[(.*?)\]", block, re.M)
        if not types_m or not fields_m:
            continue
        types = [x.strip() for x in types_m.group(1).split(",") if x.strip()]
        fields = [x.strip() for x in fields_m.group(1).split(",") if x.strip()]
        for name in types:
            if name not in contract.types:
                problems.append(f"{cq} declara el tipo `{name}`, que no existe en el contrato")
        if not types:
            continue                       # transversal: only common fields apply
        declared = set()
        for name in types:
            declared |= set(contract.fields_for(name)) if name in contract.types else set()
        declared |= common
        # A pending field is declared bare (`valido_hasta`, coming to several
        # types) or scoped (`Lineamiento.estado`, coming to exactly one). The
        # scoped form exists so that granting one type a field does not excuse
        # the same name being missing everywhere else.
        for field in fields:
            if field in declared or field in pending:
                continue
            if any(f"{name}.{field}" in pending for name in types):
                continue
            problems.append(
                f"{cq}: `{field}` no existe en ninguno de {types} ni es campo común "
                "(si un plan lo va a añadir, decláralo con `# pending-field: <nombre>` "
                "o `# pending-field: <Tipo>.<nombre>`)")
    return problems


def check_ddl(contract) -> List[str]:
    """El DDL se genera, el motor lo acepta, y un campo nuevo llega solo.

    Los tres criterios de aceptación de T4, comprobados como se comprueban las
    cosas aquí: ejecutándolos. Que el DDL «parezca» SQL válido no dice nada --
    STRICT, los CHECK de enum y las claves foráneas o los acepta SQLite o no.
    Y «agregar un campo al contrato cambia el DDL sin tocar código» se verifica
    agregando uno, no leyendo el generador.
    """
    problems = []
    ddl = brain.render_ddl(contract)

    try:
        import sqlite3
    except ImportError:                      # mismo trato que PyYAML: se dice
        print("  (sqlite3 no disponible: el DDL no se ejecutó contra el motor)")
    else:
        try:
            db = sqlite3.connect(":memory:")
            db.executescript(ddl)
            tablas = {r[0] for r in db.execute(
                "select name from sqlite_master where type='table'")}
            db.close()
        except sqlite3.Error as exc:
            problems.append(f"SQLite rechaza el DDL generado: {exc}")
        else:
            esperadas = {t.lower() for t in contract.types
                         if not contract.types[t].get("generated_only")}
            faltan = esperadas - tablas
            if faltan:
                problems.append("tipos del contrato sin tabla en el DDL: "
                                + ", ".join(sorted(faltan)))
            if "Indice" in contract.types and "indice" in tablas:
                problems.append("`Indice` es generado y no debería proyectarse")

    # T4, criterio 2: el contrato manda, y manda solo.
    sonda_campo = {"data_type": "enum", "values": ["si", "no"], "required": True}
    contract.common["campo_sonda"] = sonda_campo
    contract.data_types["sonda"] = {"note": "probe", "sql": {"type": "REAL"}}
    contract.common["medida_sonda"] = {"data_type": "sonda"}
    try:
        con_sonda = brain.render_ddl(contract)
    finally:
        del contract.common["campo_sonda"]
        del contract.common["medida_sonda"]
        del contract.data_types["sonda"]
    if '"campo_sonda" TEXT NOT NULL CHECK' not in con_sonda:
        problems.append("un campo nuevo del contrato no llega al DDL con su tipo "
                        "y su CHECK: el generador no está derivando del contrato")
    if '"medida_sonda" REAL' not in con_sonda:
        problems.append("un `data_type` nuevo no llega al DDL: su mapa a SQL no "
                        "se está leyendo del contrato")

    # La vista de eventos (T6) todavía no existe, pero su regla ya está
    # declarada, y una declaración que nadie comprueba es cómo se cuela una
    # afirmación de control sin control. Dos cosas baratas la sostienen:
    # que el opt-out solo se declare donde tiene efecto, y que la lista del
    # contrato diga la verdad en vez de ser una copia que se desincroniza.
    timeline = contract.projection.get("timeline", {})
    if timeline:
        declarado, fuera = [], []
        for type_name, spec in contract.types.items():
            for name, field in (spec.get("fields") or {}).items():
                if not isinstance(field, dict) or "timeline" not in field:
                    continue
                declarado.append(f"{type_name}.{name}")
                if field.get("data_type") != "date":
                    problems.append(f"{type_name}.{name} declara `timeline` sin ser "
                                    f"un campo `date`: la clave no tendría efecto")
                if field.get("timeline") is False:
                    fuera.append(f"{type_name}.{name}")
        if sorted(fuera) != sorted(timeline.get("opted_out", [])):
            problems.append(
                "`projection.timeline.opted_out` no coincide con los campos que "
                f"declaran `timeline: false` (contrato: {sorted(fuera)}, "
                f"lista: {sorted(timeline.get('opted_out', []))})")
        if not [f for t_, s in contract.types.items()
                for f, spec_ in (s.get("fields") or {}).items()
                if isinstance(spec_, dict) and spec_.get("data_type") == "date"
                and spec_.get("timeline") is not False]:
            problems.append("ningún campo entraría en la vista de eventos")

    # El mapa a JSON Schema vive en el mismo sitio desde el 2026-09-13, así que
    # se comprueba igual: los dos generadores derivan del contrato o ninguno.
    for kind, spec in contract.data_types.items():
        if isinstance(spec, dict) and "json" not in spec:
            problems.append(f"el `data_type` `{kind}` no declara su mapa a JSON "
                            f"Schema: se proyectaría como `string` en silencio")
        if isinstance(spec, dict) and "sql" not in spec:
            problems.append(f"el `data_type` `{kind}` no declara su mapa a SQL")
    return problems


def check_projection(contract) -> List[str]:
    """El criterio de T5: `--full` y una pasada incremental dicen lo mismo.

    Es la propiedad que hace que la proyección sea desechable, y por tanto la
    que permite tratar el markdown como la única fuente: si reconstruir desde
    cero diera un resultado distinto de ir actualizando, habría estado en la
    base que no está en los documentos, y nadie sabría cuál de las dos creer.

    Se comprueba sobre un cerebro de verdad, escrito aquí mismo, y por los
    cuatro caminos que tiene una proyección: crear, no hacer nada, modificar y
    borrar.
    """
    try:
        import sqlite3                                            # noqa: F401
    except ImportError:
        print("  (sqlite3 no disponible: la proyección no se ejercitó)")
        return []

    problems = []
    tmp = Path(tempfile.mkdtemp(prefix="brain-project-"))
    try:
        bundle = tmp / "cerebro"
        with redirect_stdout(io.StringIO()):
            brain.cmd_init(SimpleNamespace(
                path=str(bundle), contract=str(ROOT / "kernel/schema/contract.json"),
                bundle=str(bundle), profile=None))
        local = brain.Contract.load(ROOT / "kernel/schema/contract.json", bundle)

        # Un documento por tipo, rellenado desde su propia plantilla: así el
        # proyector se ejercita contra TODOS los tipos, no contra los dos que
        # a alguien se le ocurrieran.
        for type_name in local.types:
            if local.types[type_name].get("generated_only"):
                continue
            body = fill(brain.render_template(local, type_name), local, type_name)
            # Una fecha distinta por tipo: con todas iguales, la comprobación
            # del orden de la vista de eventos no distinguiría nada.
            dia = f"2026-{(len(body) % 12) + 1:02d}-{(len(type_name) % 28) + 1:02d}"
            body = re.sub(r"(?m)^((?:fecha|created|last_review): )\d{4}-\d{2}-\d{2}$",
                          lambda m: m.group(1) + dia, body)
            (bundle / f"caso-{type_name.lower()}.md").write_text(body, encoding="utf-8")

        db = tmp / "prueba.db"
        brain.project(local, bundle, db, full=True)
        estado_full = brain.snapshot(db, local)
        if estado_full.count("\n") < len(local.types):
            problems.append("la proyección completa dejó la base casi vacía")

        brain.project(local, bundle, db)
        if brain.snapshot(db, local) != estado_full:
            problems.append("una pasada incremental sin cambios alteró la base")

        # T6: la vista de eventos, y CQ-47 respondida con ella. Se ejecuta el
        # `sql:` que declara la propia pregunta -- si la consulta de una CQ no
        # corre contra el esquema, la CQ no está respondida, está redactada.
        problems += _check_timeline(local, db)

        # Un documento con `verified` humano: sin él, `documentos_verified`
        # queda vacía y toda consulta sobre esa tabla vuelve vacía por falta de
        # datos, no por estar sano el corpus. Un test sobre una tabla vacía no
        # distingue una cosa de la otra.
        revisado = bundle / "caso-reunion.md"
        revisado.write_text(
            revisado.read_text(encoding="utf-8").replace(
                "\nprocedencia:",
                "\nverified: [{by: \"human:revisora\", at: 2026-09-14T09:00:00Z}]"
                "\nprocedencia:", 1),
            encoding="utf-8")
        brain.project(local, bundle, db, full=True)

        # T7: el índice de texto, en la misma pasada que la proyección.
        problems += _check_search(local, bundle, db)

        # T9: el modelo de vigencia, sobre datos escritos para eso.
        problems += _check_validity(local, bundle, db)

        # T10: la cosecha, que se ve por el enlace al origen o no se ve.
        problems += _check_cosecha(local, bundle, db)

        # T8: y con la base poblada, las competency questions enteras.
        problems += check_cq_sql(local, bundle, db)

        objetivo = bundle / "caso-reunion.md"
        objetivo.write_text(objetivo.read_text(encoding="utf-8")
                            .replace("title: ", "title: Reescrito "), encoding="utf-8")
        brain.project(local, bundle, db)
        tras_incremental = brain.snapshot(db, local)
        if tras_incremental == estado_full:
            problems.append("un documento modificado no llegó a la base")
        brain.project(local, bundle, db, full=True)
        if brain.snapshot(db, local) != tras_incremental:
            problems.append("tras modificar, `--full` y la incremental difieren")

        objetivo.unlink()
        brain.project(local, bundle, db)
        # El índice es una tabla virtual: ninguna clave foránea lo limpia. Se
        # mira la TABLA, no el resultado de buscar: `search` hace join con
        # `documentos`, así que un huérfano del índice nunca sale en una
        # búsqueda -- lo cual protege a quien busca, y por eso mismo esconde
        # que el índice esté acumulando basura. Comprobar por la búsqueda
        # habría sido un control que no controla.
        if brain.has_fts5():
            import sqlite3
            tabla = local.projection["search"]["table"]
            aparte = sqlite3.connect(db)
            restos = aparte.execute(
                f'select count(*) from "{tabla}" where "path" = ?',
                ("caso-reunion.md",)).fetchone()[0]
            aparte.close()
            if restos:
                problems.append("un documento borrado sigue en el índice de texto")
        tras_borrado = brain.snapshot(db, local)
        if "caso-reunion.md |" in tras_borrado:
            problems.append("un documento borrado dejó filas en la base")
        brain.project(local, bundle, db, full=True)
        if brain.snapshot(db, local) != tras_borrado:
            problems.append("tras borrar, `--full` y la incremental difieren")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return problems


def _cq_sql(cq: str) -> str:
    """El `sql:` que declara una competency question, tal cual."""
    yml = (ROOT / "kernel" / "tests" / "competency-questions.yml").read_text(encoding="utf-8")
    i = yml.index(f"  - id: {cq}\n")
    bloque = yml[i:yml.index("\n  - id: ", i + 1)]
    m = re.search(r"^(\s*)sql: >-\n((?:\1[ ]+\S.*\n)+)", bloque, re.M)
    return " ".join(l.strip() for l in m.group(2).splitlines()) if m else ""


# Valores de muestra para los parámetros de las CQs. El nombre del parámetro
# ES su tipo: una consulta que pida `:proyecto` recibe un slug, una que pida
# `:fecha` recibe una fecha. Así el runner no necesita saber nada de cada
# pregunta, y una consulta que invente un parámetro nuevo falla en vez de
# recibir un valor silenciosamente equivocado.
CQ_PARAMS = {
    "proyecto": "transversal", "persona": "/caso-persona.md",
    "sistema": "/caso-sistema.md", "area": "seguridad", "equipo": "Pruebas",
    "fecha": "2026-05-15", "desde": "2026-01-01", "hasta": "2026-12-31",
    "hoy": "2026-09-14", "ahora": "2026-09-14T00:00:00Z", "dias": 30,
    "termino": "contenido", "periodo": "2026-Q3", "actor": "human:prueba",
    "clase": "flujo", "tema": "erp", "umbral": 90, "tipo": "Decision",
}


# Un defecto por adversarial. Sin esto, una consulta adversarial «pasa» por no
# encontrar nada -- y no encontrar nada es su resultado esperado, así que una
# consulta ciega es indistinguible de una que vigila. Verificado: quitarle la
# condición a ADV-09 no hacía fallar el test, porque el cerebro de prueba no
# tenía ni una fila de `documentos_verified` que pudiera dispararla.
ADV_DEFECTOS = {
    "ADV-03": ["insert into persona values ('p.md','Rol','Eq','/no-existe.md')"],
    "ADV-04": ["update documentos set status='stable', stale_after='2020-01-01' "
               "where path='d.md'"],
    "ADV-05": ["update documentos set type='Persona', classification='internal' "
               "where path='d.md'"],
    "ADV-06": ["insert into decision_decisores values ('d.md',0,'/fantasma.md')"],
    "ADV-07": ["update decision set estado='propuesta', valido_hasta='2026-05-01' "
               "where doc='d.md'"],
    "ADV-08": ["update decision set reemplazada_por='/otra.md', valido_hasta=null "
               "where doc='d.md'"],
    "ADV-09": ["insert into documentos_verified values "
               "('d.md',0,'agente/1.0','2026-01-01T00:00:00Z')"],
    "ADV-10": ["update documentos set stale_after='2020-01-01', status='stable' "
               "where path='d.md'"],
    "ADV-11": ["insert into persona values ('pa.md','R','E','/pb.md')",
               "insert into persona values ('pb.md','R','E','/pa.md')"],
    "ADV-12": ["insert into documentos_sources values ('d.md',0,'   ',null,null,null,null)"],
}


def _base_de_prueba(contract):
    """Una base mínima con una decisión y dos personas, para romperla a propósito."""
    import sqlite3
    db = sqlite3.connect(":memory:")
    db.executescript(brain.render_ddl(contract))
    for path, tipo in (("d.md", "Decision"), ("pa.md", "Persona"),
                       ("pb.md", "Persona"), ("p.md", "Persona")):
        db.execute('insert into documentos ("path","hash","type","title",'
                   '"description","resumen","resumen_hash","procedencia",'
                   '"classification") '
                   "values (?,?,?,'T','D','R','h','manual','confidential')",
                   (path, "h", tipo))
    db.execute("insert into decision values "
               "('d.md','transversal','aceptada','2026-01-01',null,null,null)")
    return db


def _check_adversariales_ven(contract, yml) -> List[str]:
    """Cada adversarial tiene que DETECTAR su defecto, no solo volver vacía."""
    import sqlite3
    problems = []
    for m in re.finditer(r"^  - id: (ADV-\S+)", yml, re.M):
        ident = m.group(1)
        fin = yml.find("\n  - id: ", m.end())
        sql = _sql_de_bloque(yml[m.start(): fin if fin > 0 else len(yml)])
        if not sql:
            continue
        if ident not in ADV_DEFECTOS:
            problems.append(f"{ident} lleva `sql:` pero no hay un defecto con el que "
                            f"comprobar que lo ve: sin eso, «no devuelve filas» no "
                            f"distingue vigilar de estar ciega")
            continue
        db = _base_de_prueba(contract)
        try:
            for sentencia in ADV_DEFECTOS[ident]:
                db.execute(sentencia)
            if not db.execute(sql, {n: CQ_PARAMS[n]
                                    for n in set(re.findall(r":(\w+)", sql))}).fetchall():
                problems.append(f"{ident} no ve su propio defecto: la consulta corre, "
                                f"vuelve vacía siempre, y no vigila nada")
        except sqlite3.Error as exc:
            problems.append(f"{ident}: no se pudo comprobar que ve su defecto -- {exc}")
        finally:
            db.close()
    return problems


def _sql_de_bloque(bloque: str) -> str:
    m = re.search(r"^(\s*)sql: >-\n((?:\1[ ]+\S.*\n)+)", bloque, re.M)
    return " ".join(l.strip() for l in m.group(2).splitlines()) if m else ""


def check_cq_sql(contract, bundle, db_path) -> List[str]:
    """T8: toda competency question corre, y ninguna adversarial devuelve nada.

    Las CQs eran el criterio de aceptación del contrato y se comprobaban a ojo.
    Con `sql:` dejan de ser una lista de deseos: o la consulta corre contra el
    esquema o no corre. Y las adversariales se ejecutan **al revés** -- describen
    lo que el sistema no debe poder responder, así que su consulta busca el
    defecto y tiene que volver vacía.
    """
    import sqlite3
    yml_path = ROOT / "kernel" / "tests" / "competency-questions.yml"
    if not yml_path.exists():
        return []
    yml = yml_path.read_text(encoding="utf-8")
    exentas = set(re.findall(r"^\s*sql_exempt:\s*\[(.*?)\]", yml, re.M))
    exentas = {x.strip() for grupo in exentas for x in grupo.split(",") if x.strip()}
    problems, corridas = [], 0
    db = sqlite3.connect(db_path)

    for m in re.finditer(r"^  - id: (\S+)", yml, re.M):
        ident = m.group(1)
        fin = yml.find("\n  - id: ", m.end())
        bloque = yml[m.start(): fin if fin > 0 else len(yml)]
        sql = _sql_de_bloque(bloque)
        if not sql:
            if ident not in exentas:
                problems.append(f"{ident} no tiene `sql:`: sigue siendo una "
                                f"pregunta escrita, no una que el cerebro sepa "
                                f"responder")
            continue
        faltan = [n for n in re.findall(r":(\w+)", sql) if n not in CQ_PARAMS]
        if faltan:
            problems.append(f"{ident} usa parámetros sin valor de muestra: "
                            f"{', '.join(sorted(set(faltan)))}")
            continue
        params = {n: CQ_PARAMS[n] for n in set(re.findall(r":(\w+)", sql))}
        try:
            filas = db.execute(sql, params).fetchall()
        except sqlite3.Error as exc:
            problems.append(f"{ident}: su `sql:` no corre -- {exc}")
            continue
        corridas += 1
        if ident.startswith("ADV") and filas:
            problems.append(f"{ident} devuelve {len(filas)} fila(s) y debería "
                            f"volver vacía: describe lo que el cerebro NO debe "
                            f"poder responder")
    db.close()
    problems += _check_adversariales_ven(contract, yml)
    if corridas < 40:
        problems.append(f"solo corrieron {corridas} consultas: el corte 2 se "
                        f"cierra cuando las 32 CQs y las adversariales pasan")
    return problems


def _check_cosecha(contract, bundle, db_path) -> List[str]:
    """T10: lo promovido conserva enlace a su origen, y sin él no se ve.

    El criterio dice «lo promovido conserva enlace a su origen». Aquí se
    comprueba lo que eso significa de verdad: el enlace **es** lo que hace la
    promoción visible. Sin `sources`, una iniciativa cosechada es
    indistinguible de una archivada en crudo -- y CQ-50, que pregunta
    exactamente por esa diferencia, la cuenta entre las que no dejaron nada.
    """
    import sqlite3
    def doc(ruta, tipo, extra):
        cuerpo = fill(brain.render_template(contract, tipo), contract, tipo)
        # Se quitan las claves que `extra` redefine: repetirlas dejaría el
        # frontmatter con la misma clave dos veces, que es YAML ambiguo.
        redefinidas = [l.split(":", 1)[0] for l in extra.splitlines() if ":" in l]
        cuerpo = re.sub(r"(?m)^(" + "|".join(redefinidas) + r"): .*\n", "", cuerpo)
        frente, resto = cuerpo.split("---", 2)[1], cuerpo.split("---", 2)[2]
        destino = bundle / ruta
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text("---" + frente + extra + "---" + resto, encoding="utf-8")

    cosechada = "01-proyectos/c-cosechada"
    doc(f"{cosechada}/CONTEXT.md", "Iniciativa",
        "proyecto: c-cosechada\nestado: entregada\n")
    doc(f"{cosechada}/02-decisiones/dec-001.md", "Decision",
        "proyecto: c-cosechada\nestado: aceptada\n")
    doc("02-areas/operaciones/regla-promovida.md", "Lineamiento",
        "area: operaciones\nestado: aprobado\nsources: [{resource: "
        f"/{cosechada}/02-decisiones/dec-001.md" + "}]\n")
    doc("01-proyectos/c-cruda/CONTEXT.md", "Iniciativa",
        "proyecto: c-cruda\nestado: entregada\n")
    brain.project(contract, bundle, db_path, full=True)

    problems = []
    sql = _cq_sql("CQ-50")
    db = sqlite3.connect(db_path)
    filas = {(r[0], r[3]) for r in db.execute(sql)}
    if ("promovido", "02-areas/operaciones/regla-promovida.md") not in filas:
        problems.append("CQ-50 no ve la promoción: un documento de área con "
                        "`sources` a una iniciativa entregada es exactamente lo "
                        "que la cosecha produce")
    if ("sin cosechar", "01-proyectos/c-cruda/CONTEXT.md") not in filas:
        problems.append("CQ-50 no ve la iniciativa cerrada sin nada promovido, "
                        "que es la mitad que nadie echa en falta")
    if ("sin cosechar", f"{cosechada}/CONTEXT.md") in filas:
        problems.append("CQ-50 cuenta como no cosechada una iniciativa que sí "
                        "promovió algo")
    db.close()

    # Sin el enlace al origen, la promoción deja de existir para el sistema.
    promovido = bundle / "02-areas/operaciones/regla-promovida.md"
    promovido.write_text(
        re.sub(r"(?m)^sources:.*\n", "", promovido.read_text(encoding="utf-8")),
        encoding="utf-8")
    brain.project(contract, bundle, db_path, full=True)
    db = sqlite3.connect(db_path)
    sin_enlace = {(r[0], r[3]) for r in db.execute(sql)}
    db.close()
    # Las DOS mitades. Comprobar solo que la iniciativa pase a «sin cosechar»
    # no basta: una consulta rota puede devolverla por los dos lados a la vez,
    # y de hecho lo hizo al inyectarle el defecto. Lo que prueba que el enlace
    # es lo que sostiene la promoción es que la promoción DESAPAREZCA.
    if ("promovido", "02-areas/operaciones/regla-promovida.md") in sin_enlace:
        problems.append("sin `sources`, el documento de área sigue contando como "
                        "promovido: entonces la promoción se detecta por la "
                        "carpeta y no por el enlace, y CQ-50 mide otra cosa")
    if ("sin cosechar", f"{cosechada}/CONTEXT.md") not in sin_enlace:
        problems.append("al quitar `sources` la iniciativa no pasa a contar como "
                        "no cosechada: el enlace no está sosteniendo nada")

    for ruta in (f"{cosechada}/CONTEXT.md", f"{cosechada}/02-decisiones/dec-001.md",
                 "02-areas/operaciones/regla-promovida.md",
                 "01-proyectos/c-cruda/CONTEXT.md"):
        (bundle / ruta).unlink()
    brain.project(contract, bundle, db_path, full=True)
    return problems


def _check_validity(contract, bundle, db_path) -> List[str]:
    """T9: el intervalo manda, y CQ-48 y CQ-51 lo demuestran sobre los dos tipos.

    Se escriben a mano una cadena de tres decisiones y una regla que caducó sin
    sucesor, porque es el caso que ningún modelo derivado de `reemplazada_por`
    sabe expresar -- sin sucesor no hay fecha de cierre y la regla figura
    vigente para siempre. Si la proyección no lo distingue, T9 no sirve de nada.
    """
    import sqlite3
    model = contract.data.get("validity_model", {})
    if not model.get("view"):
        return ["el contrato no declara la vista de vigencia"]
    problems = []

    def escribir(nombre, tipo, campos, extra=""):
        cuerpo = fill(brain.render_template(contract, tipo), contract, tipo)
        # Se quitan las claves que `campos` redefine -- todas, no una lista
        # fija: con una lista fija, añadir un campo nuevo a una prueba lo deja
        # duplicado en el frontmatter y el documento queda ambiguo en silencio.
        redefinidas = [l.split(":", 1)[0] for l in campos.splitlines() if ":" in l]
        cuerpo = re.sub(r"(?m)^(" + "|".join(redefinidas) + r"): .*\n", "", cuerpo)
        frente, resto = cuerpo.split("---", 2)[1], cuerpo.split("---", 2)[2]
        (bundle / nombre).write_text(
            "---" + frente + campos + "---" + resto + extra, encoding="utf-8")

    escribir("v-uno.md", "Decision",
             "estado: aceptada\nvalido_desde: 2026-01-01\nvalido_hasta: 2026-04-01\n"
             "reemplazada_por: /v-dos.md\n")
    escribir("v-dos.md", "Decision",
             "estado: aceptada\nvalido_desde: 2026-04-01\nvalido_hasta: 2026-07-01\n"
             "reemplazada_por: /v-tres.md\n")
    escribir("v-tres.md", "Decision", "estado: aceptada\nvalido_desde: 2026-07-01\n")
    escribir("v-caducada.md", "Lineamiento",
             "estado: aprobado\nvalido_desde: 2025-01-01\nvalido_hasta: 2026-03-01\n")
    brain.project(contract, bundle, db_path, full=True)
    db = sqlite3.connect(db_path)

    # Criterio 1 y 3: cada pregunta, con su propio SQL, sobre los dos tipos.
    vigentes = db.execute(_cq_sql("CQ-48"), {"fecha": "2026-05-15"}).fetchall()
    titulos = {r[2] for r in vigentes}
    if "v-dos.md" not in titulos:
        problems.append("CQ-48 no devuelve la decisión que regía en la fecha dada")
    if "v-uno.md" in titulos or "v-tres.md" in titulos:
        problems.append("CQ-48 devuelve documentos fuera del intervalo consultado")
    if "v-caducada.md" in titulos:
        problems.append("CQ-48 devuelve una regla que ya había caducado")

    caducadas = {r[2] for r in db.execute(_cq_sql("CQ-51"), {"hoy": "2026-09-14"})}
    if "v-caducada.md" not in caducadas:
        problems.append("CQ-51 no encuentra la regla que caducó sin sucesor -- "
                        "que es el caso entero por el que el intervalo se declara")
    if caducadas & {"v-uno.md", "v-dos.md"}:
        problems.append("CQ-51 cuenta como caducada una decisión que sí fue reemplazada")
    tipos = {r[0] for r in vigentes} | {
        r[0] for r in db.execute(_cq_sql("CQ-51"), {"hoy": "2026-09-14"})}
    if not {"Decision", "Lineamiento"} <= tipos:
        problems.append("la vigencia no se responde sobre los dos tipos, solo sobre "
                        + ", ".join(sorted(tipos)))

    # Criterio 2: la cadena de tres, contigua y sin solape.
    # Solo la cadena escrita aquí: el cerebro de prueba lleva además un
    # `caso-decision.md` por tipo, que no forma parte de ninguna cadena.
    cadena = db.execute(
        'select "valido_desde", "valido_hasta" from "vigencia" '
        'where "tipo" = ? and "doc" like \'v-%\' order by "valido_desde"',
        ("Decision",)).fetchall()
    if len(cadena) != 3:
        problems.append(f"la cadena de decisiones tiene {len(cadena)} eslabones, no 3")
    elif any(a[1] != b[0] for a, b in zip(cadena, cadena[1:])):
        problems.append("los intervalos de la cadena no son contiguos: hay hueco o solape")
    db.close()

    # Criterio 4: V24 se ejercita por su camino negativo. Comprobar que el
    # check existe mirando `CHECKS` no diría nada -- V14 estuvo declarado y
    # muerto un corte entero. Se rompe el intervalo de tres maneras y se exige
    # que las nombre.
    escribir("v-rota.md", "Decision",
             "estado: aceptada\nvalido_desde: 2026-05-01\nvalido_hasta: 2026-01-01\n")
    escribir("v-suelta.md", "Decision",
             "estado: aceptada\nvalido_desde: 2026-01-01\n"
             "reemplazada_por: /v-tres.md\n")
    escribir("v-ciclo-a.md", "Decision",
             "estado: aceptada\nvalido_desde: 2026-01-01\nvalido_hasta: 2026-06-01\n"
             "reemplazada_por: /v-ciclo-b.md\n")
    escribir("v-ciclo-b.md", "Decision",
             "estado: aceptada\nvalido_desde: 2026-06-01\nvalido_hasta: 2026-09-01\n"
             "reemplazada_por: /v-ciclo-a.md\n")
    # V25 se ejercita aquí mismo, y por la misma razón que V24: un check que
    # nadie rompe a propósito es un check del que solo se sabe que existe.
    escribir("v-sin-fuente.md", "Lineamiento",
             "estado: aprobado\nprocedencia: fuente\n")
    todos = brain.Validator(contract, bundle).run()
    if not any(f.check == "V25" and f.path == "v-sin-fuente.md" for f in todos):
        problems.append("V25 no marca un `procedencia: fuente` que no declara "
                        "ninguna fuente: el valor más fiable del enum sería el "
                        "más barato de escribir")
    (bundle / "v-sin-fuente.md").unlink()

    hallazgos = [f for f in todos if f.check == "V24"]
    for archivo, senal in (("v-rota.md", "acaba antes de empezar"),
                           ("v-suelta.md", "sigue contando como vigente"),
                           ("v-ciclo-a.md", "no un círculo")):
        if not any(f.path == archivo and senal in f.message for f in hallazgos):
            problems.append(f"V24 no marca `{archivo}`: el intervalo puede romperse "
                            f"de esa manera sin que nadie avise")
    for nombre in ("v-rota.md", "v-suelta.md", "v-ciclo-a.md", "v-ciclo-b.md"):
        (bundle / nombre).unlink()

    for nombre in ("v-uno.md", "v-dos.md", "v-tres.md", "v-caducada.md"):
        (bundle / nombre).unlink()
    brain.project(contract, bundle, db_path, full=True)
    return problems


def _check_search(contract, bundle, db_path) -> List[str]:
    """El índice FTS5: encuentra, ordena por BM25 y se reconstruye sin pérdida."""
    import sqlite3
    cfg = contract.projection.get("search", {})
    if not cfg.get("table"):
        return ["el contrato no declara el índice de texto"]
    if not brain.has_fts5():
        print("  (este SQLite no trae FTS5: el índice de texto no se ejercitó)")
        return []

    problems = []
    termino = "contenido"          # lo que `fill` deja en el cuerpo de cada caso
    antes = brain.search(contract, termino, db_path, limit=50)
    if not antes:
        problems.append("el índice no encuentra un término que está en el cuerpo "
                        "de todos los documentos de prueba")
    if any(len(fila) != 3 for fila in antes):
        problems.append("la búsqueda devuelve algo distinto de (ruta, rank, título)")

    # Criterio 3: reconstruir no puede perder nada.
    brain.project(contract, bundle, db_path, full=True)
    despues = brain.search(contract, termino, db_path, limit=50)
    if {f[0] for f in antes} != {f[0] for f in despues}:
        problems.append("reconstruir el índice cambió lo que encuentra")

    # Criterio 2: sin índice se falla nombrando la sonda, no con un stack trace.
    vacia = Path(str(db_path) + ".sin-indice")
    db = sqlite3.connect(vacia)
    db.execute('create table "documentos" ("path" TEXT)')
    db.close()
    try:
        brain.search(contract, termino, vacia)
        problems.append("buscar sin índice no falló")
    except SystemExit as exc:
        if "sqlite-probe" not in str(exc):
            problems.append("el error de «sin índice» no nombra la sonda: "
                            "quien lo lea no sabrá qué comprobar")
    except Exception as exc:                                   # noqa: BLE001
        problems.append(f"buscar sin índice lanzó {type(exc).__name__}, "
                        f"no un error explicado: {exc}")
    finally:
        vacia.unlink(missing_ok=True)
    return problems


def _check_timeline(contract, db_path) -> List[str]:
    """La vista de eventos: los cinco tipos, en orden, y sin los que no lo son."""
    import sqlite3
    problems = []
    cfg = contract.projection.get("timeline", {})
    view = cfg.get("view")
    if not view:
        return ["el contrato no declara la vista de eventos"]

    db = sqlite3.connect(db_path)
    try:
        filas = list(db.execute(f'select "fecha", "tipo", "campo" from "{view}"'))
    except sqlite3.Error as exc:
        db.close()
        return [f"la vista `{view}` no se puede consultar: {exc}"]

    # La referencia se lee del CONTRATO, no de `timeline_fields`. Usar la
    # función que se está probando como patrón de lo que debería salir es
    # comparar el generador consigo mismo: al rompernos la regla a propósito
    # —seleccionar por el nombre `fecha`, el defecto original— la vista se
    # quedó en tres tipos y este test decía OK. Un control cuya referencia
    # depende de lo controlado no controla nada.
    esperados = {name for name, spec in contract.types.items()
                 if not spec.get("generated_only")
                 and any(isinstance(f, dict) and f.get("data_type") == "date"
                         and f.get("timeline") is not False
                         for f in (spec.get("fields") or {}).values())}
    presentes = {f[1] for f in filas}
    if esperados - presentes:
        problems.append("tipos fechados que no aparecen en la vista de eventos: "
                        + ", ".join(sorted(esperados - presentes)))
    for excluido in cfg.get("opted_out", []):
        tipo = excluido.split(".")[0]
        if tipo in presentes and tipo not in esperados:
            problems.append(f"`{excluido}` declara `timeline: false` y aun así "
                            f"aparece en la vista")

    fechas = [f[0] for f in filas if f[0]]
    orden = sorted(fechas, reverse=str(cfg.get("order", "desc")).lower() == "desc")
    if fechas != orden:
        problems.append("la vista de eventos no sale en orden cronológico")
    if len(set(fechas)) < 2:
        # Con todas las fechas iguales, cualquier orden «pasa»: la
        # comprobación de arriba no habría distinguido una vista ordenada de
        # una que no lo está. Quien prepara los datos tiene que variarlas.
        problems.append("la prueba del orden es vacua: las fechas de los "
                        "documentos de prueba no son distintas entre sí")
    definicion = db.execute("select sql from sqlite_master where name = ?",
                            (view,)).fetchone()
    if definicion and "order by" not in (definicion[0] or "").lower():
        problems.append("la vista no declara `order by`: el orden cronológico "
                        "quedaría a merced del plan de ejecución")

    # Y la pregunta que justifica la vista, ejecutada tal y como la declara.
    yml = (ROOT / "kernel" / "tests" / "competency-questions.yml").read_text(encoding="utf-8")
    bloque = next((b for b in re.split(r"\n  - id: ", yml) if b.startswith("CQ-47")), "")
    # Solo las líneas MÁS indentadas que la clave: `\s+` se comería el blanco
    # y el comentario que siguen, y el SQL acabaría con un `#` dentro.
    consulta = re.search(r"^(\s*)sql: >-\n((?:\1[ ]+\S.*\n)+)", bloque, re.M)
    if not consulta:
        problems.append("CQ-47 no declara su `sql:`, que es el criterio de T6")
    else:
        texto = " ".join(l.strip() for l in consulta.group(2).splitlines())
        try:
            db.execute(texto, {"proyecto": "x", "desde": "2000-01-01",
                               "hasta": "2100-01-01"}).fetchall()
        except sqlite3.Error as exc:
            problems.append(f"el `sql:` de CQ-47 no corre contra el esquema: {exc}")
    db.close()
    return problems


def check_read_budget(contract) -> List[str]:
    """T2: el presupuesto de lectura está declarado, y no se bifurca.

    La regla que más importa —«si el tope no alcanza, dilo y nombra qué quedó
    sin abrir»— es conducta y ningún test la ve. Lo que sí se puede comprobar,
    y es donde estaba el riesgo real, es que **el número viva en un solo
    sitio**: el módulo de consulta enseña un tope y el contrato declara otro, el
    agente obedece al módulo, y la instrumentación de CQ-46 mide contra un tope
    que nadie aplica. Un desacuerdo silencioso entre dos números que dicen ser
    el mismo.
    """
    budget = contract.data.get("read_budget", {})
    if not budget:
        return ["el contrato no declara `read_budget`: el presupuesto de lectura "
                "seguiría viviendo solo en la prosa de un skill"]
    problems = []
    for nivel, campo in (("L0", "description"), ("L1", "resumen")):
        declarado = budget.get("levels", {}).get(nivel, {}).get("field")
        if declarado != campo:
            problems.append(f"`read_budget` declara {nivel} como `{declarado}` "
                            f"y debería ser `{campo}`")
        if declarado not in contract.common:
            problems.append(f"{nivel} apunta a `{declarado}`, que no es un campo común: "
                            f"no se podría proyectar como columna")
    if not budget.get("agent_rules_es"):
        problems.append("`read_budget` no declara reglas para el agente")
    elif not any("no abriste" in r or "sin abrir" in r
                 for r in budget["agent_rules_es"]):
        problems.append("`read_budget` no dice qué hacer cuando el tope no alcanza, "
                        "que es la regla que evita responder como si se hubiera "
                        "leído lo que no se abrió")

    tope = budget.get("default_body_cap")
    modulo = ROOT / "kernel" / "modulos" / "consulta" / "consultar.md"
    if tope and modulo.exists():
        texto = modulo.read_text(encoding="utf-8")
        topes = {int(n) for n in re.findall(r"[Mm]áximo (\d+) por consulta", texto)}
        topes |= {int(n) for n in re.findall(r"como máximo (\d+) documentos", texto)}
        if topes and topes != {tope}:
            problems.append(f"el módulo de consulta enseña un tope de "
                            f"{sorted(topes)} y el contrato declara {tope}: el "
                            f"agente obedecería al módulo y la medición iría "
                            f"contra otro número")
        if not topes:
            problems.append(f"el módulo de consulta no enseña el tope de aperturas; "
                            f"el contrato declara {tope} y nadie se lo dice al agente")
    return problems


def check_layering() -> List[str]:
    """El corte por trabajos sigue siendo un corte.

    Partir el archivo no vale de nada si al mes siguiente los módulos se
    importan entre sí en círculo: volvería a ser un solo archivo, repartido en
    cinco. Aquí se comprueba lo único que sostiene la separación — que las
    dependencias van en UN sentido — y de paso que ningún módulo vuelve a
    acercarse al umbral que obligó a cortar.

    El orden declarado es const -> parse -> generate -> validate -> report
    -> project. Un módulo solo puede importar de los que tiene a su izquierda.

    `project` entró al final el 2026-09-13 con T5: es un consumidor —lee
    documentos, usa el contrato y da por hecha la validación—, y nadie tiene
    por qué importar de él. La posición se eligió por compatibilidad con esta
    regla, no por convicción de que la regla siga siendo la mejor: eso queda
    abierto en el plan, con su disparador.
    """
    order = ["const", "parse", "generate", "validate", "report", "project"]
    lib = ROOT / "kernel" / "bin" / "brainlib"
    problems = []

    for rank, name in enumerate(order):
        path = lib / f"{name}.py"
        if not path.exists():
            problems.append(f"falta kernel/bin/brainlib/{name}.py")
            continue
        source = path.read_text(encoding="utf-8")
        for node in ast.walk(ast.parse(source)):
            if not isinstance(node, ast.ImportFrom) or node.level != 1:
                continue
            target = node.module
            if target not in order:
                problems.append(f"{name}.py importa de `{target}`, que no es un trabajo")
            elif order.index(target) >= rank:
                problems.append(
                    f"{name}.py importa de `{target}`: rompe el sentido único "
                    f"({' -> '.join(order)})")

    # Todo módulo de brainlib declara su sitio. Sin esto, el bucle de arriba solo
    # mira los que ya están en `order`: uno nuevo entra sin que nadie revise sus
    # imports -- ni siquiera un ciclo entre dos módulos nuevos -- y el test sigue
    # diciendo «las capas sin ciclos», que es afirmar un control que no se hizo.
    # Mismo patrón que `completeness_rule` del contrato: obliga a una respuesta
    # consciente al añadir, en vez de confiar en que alguien recuerde la lista.
    for name in sorted({p.stem for p in lib.glob("*.py")} - set(order) - {"__init__"}):
        problems.append(f"{name}.py no declara su sitio en la cadena: añádelo a "
                        f"`order` ({' -> '.join(order)}), o no es un trabajo")

    # 2.500 fue lo que disparó R6. Se mide por archivo, que es lo que el corte
    # arregla; el total puede crecer y no es el problema.
    for path in sorted(lib.glob("*.py")) + [ROOT / "kernel" / "bin" / "brain.py"]:
        lines = len(path.read_text(encoding="utf-8").splitlines())
        if lines > 1200:
            problems.append(f"{path.name}: {lines} líneas — toca volver a cortar")
    return problems


def main() -> int:
    contract = brain.Contract.load(ROOT / "kernel" / "schema" / "contract.json")
    tmp = Path(tempfile.mkdtemp(prefix="brain-roundtrip-"))
    failures = (check_provenance(contract) + check_yaml_compatibility(contract)
                + check_locations(contract) + check_derived_specs(contract)
                + check_period_formats(contract) + check_role_profiles(contract)
                + check_layering() + check_read_budget(contract)
                + check_ddl(contract)
                + check_projection(contract) + check_init(contract)
                + check_competency_questions(contract))

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

    profiles = brain.find_profiles(ROOT / "kernel")
    print(f"OK -- provenance completo, derivados consistentes, el presupuesto de "
          f"lectura sin bifurcar, el DDL lo acepta "
          f"SQLite y deriva del contrato, la proyección incremental dice lo mismo "
          f"que `--full`, formas de periodo "
          f"disjuntas, los {len(profiles)} profiles de rol completos, las capas "
          f"sin ciclos, `init` idempotente y validando, las competency questions "
          f"cuadran con el contrato, y las plantillas de los {len(tested)} tipos, "
          f"rellenadas, validan limpio.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
