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

from .const import (DATE_RE, DEFAULT_BUNDLE, GENERATED_MARK,
                    GENERATED_MARK_SQL, VERSION, WARNING)
from .parse import (Contract, Document, ParseError, parse_frontmatter,
                    read_frontmatter, quote_scalar, quoting_preserves_meaning,
                    scan_yaml_hazards, split_document, digest_body)

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
        properties[name] = _json_schema_field(field, contract)
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


def _json_schema_field(field: Dict[str, Any], contract: Contract) -> dict:
    """Un campo, en JSON Schema. El mapa vive en el contrato, como el de SQL.

    Estuvo hardcodeado aquí hasta el 2026-09-13, que es el patrón que D2
    rechazó para el DDL: un `data_type` nuevo se habría proyectado en silencio
    como `string`. Ahora los dos generadores leen del mismo sitio, y un tipo de
    dato nuevo sin su mapa se nota en vez de degradar.
    """
    kind = field.get("data_type", "text")
    spec = contract.data_types.get(kind, {})
    mapping = spec.get("json", {}) if isinstance(spec, dict) else {}
    strategy = mapping.get("strategy")
    if strategy == "enum_values":
        return {"type": "string", "enum": field.get("values", [])}
    if strategy == "array_of":
        element = {"data_type": field.get("of", "text")}
        return {"type": "array", "items": _json_schema_field(element, contract)}
    if strategy == "object_of_fields":
        members = {k: _json_schema_field(v, contract)
                   for k, v in field.get("fields", {}).items() if isinstance(v, dict)}
        return {
            "type": "object",
            "properties": members,
            "required": [k for k, v in field.get("fields", {}).items()
                         if isinstance(v, dict) and v.get("required")],
        }
    return {k: v for k, v in mapping.items() if k != "strategy"} or {"type": "string"}


# --- la proyección: el DDL, que es otro artefacto generado desde el contrato ---
#
# Aquí se produce el TEXTO del DDL, no la base. Aplicarlo y poblarlo es trabajo
# del proyector (T5), y vive aparte a propósito: si el DDL se renderizara allí,
# `generate` tendría que importar hacia la derecha y el corte por trabajos se
# rompería. De paso, `generate` y el round-trip siguen sin importar `sqlite3`,
# así que el DDL se verifica en CI aunque la máquina no pueda alojar una base.


def _sql_name(name: str) -> str:
    """El nombre de una columna o tabla. NO es el nombre del campo.

    `fecha-creacion` es un campo válido y `fecha-creacion` no es un
    identificador que se pueda escribir sin comillas en ninguna consulta, así
    que la columna se llama `fecha_creacion`. Mantener los dos nombres
    separados importa: el proyector inserta por nombre de COLUMNA y lee por
    nombre de CAMPO, y confundirlos costó un `no such column` en T5.
    """
    return name.lower().replace("-", "_")


def _sql_ident(name: str) -> str:
    """Identificador SQL. Entrecomillar siempre sale gratis y elimina de golpe
    la clase entera de choques con palabras reservadas."""
    return '"' + _sql_name(name) + '"'


def _sql_of(contract: Contract, field: Dict[str, Any]) -> Dict[str, Any]:
    spec = contract.data_types.get(field.get("data_type", "text"), {})
    return spec.get("sql", {}) if isinstance(spec, dict) else {}


def _sql_column(contract: Contract, name: str, field: Dict[str, Any],
                prefix: str = "", unique: bool = False) -> str:
    """Una columna, con su tipo, su nulabilidad y su CHECK si es un enum."""
    sql = _sql_of(contract, field)
    col = _sql_ident(f"{prefix}{name}")
    parts = [f"{col} {sql.get('type', 'TEXT')}"]
    # null_rule del contrato: un `required` relajado a warning es uno hacia el
    # que el corpus todavía migra. Proyectarlo NOT NULL sería una regla más
    # estricta que la del propio contrato, y el proyector rechazaría documentos
    # que el validador solo avisa.
    if field.get("required") and field.get("severity") not in (WARNING, "info"):
        parts.append("NOT NULL")
    if unique:
        parts.append("UNIQUE")
    if sql.get("check") == "in_values" and field.get("values"):
        allowed = ", ".join("'" + str(v).replace("'", "''") + "'"
                            for v in field["values"])
        parts.append(f"CHECK ({col} IN ({allowed}))")
    return " ".join(parts)


def _sql_members(contract: Contract, field: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in (field.get("fields") or {}).items()
            if isinstance(v, dict)}


def _sql_child_table(contract: Contract, parent: str, field_name: str,
                     field: Dict[str, Any]) -> str:
    """Un campo `list` es una tabla hija, nunca texto con comas.

    Con `of: map` cada miembro es su propia columna -- que es lo que separa a
    `sources` y `verified` de una tabla de unión de dos columnas.
    """
    cfg = contract.projection.get("child_tables", {})
    name = cfg.get("name_pattern", "{parent}_{field}").format(
        parent=parent, field=field_name)
    parent_col = _sql_ident(cfg.get("parent_column", "doc"))
    order_col = _sql_ident(cfg.get("order_column", "idx"))
    cols = [f"{parent_col} TEXT NOT NULL REFERENCES {_sql_ident(parent)}"
            f"({_sql_ident(_primary_key(contract, parent))}) ON DELETE CASCADE",
            f"{order_col} INTEGER NOT NULL"]
    of = field.get("of", "text")
    if of == "map":
        for member, spec in _sql_members(contract, field).items():
            cols.append(_sql_column(contract, member, spec))
    else:
        element = {"data_type": of, "required": True}
        cols.append(_sql_column(contract, cfg.get("value_column", "value"), element))
    cols.append(f"PRIMARY KEY ({parent_col}, {order_col})")
    return _sql_create(name, cols)


def _primary_key(contract: Contract, table: str) -> str:
    """`documentos` se identifica por su ruta; una tabla de tipo, por `doc`."""
    if table == contract.projection.get("documents_table", "documentos"):
        for name, spec in contract.projection.get("synthetic_columns", {}).items():
            if isinstance(spec, dict) and spec.get("role") == "primary_key":
                return name
    return contract.projection.get("child_tables", {}).get("parent_column", "doc")


def _sql_create(name: str, columns: List[str]) -> str:
    body = ",\n".join(f"  {c}" for c in columns)
    return f"CREATE TABLE {_sql_ident(name)} (\n{body}\n) STRICT;"


def _sql_fields(contract: Contract, fields: Dict[str, Any], prefix: str = "",
                unique_field: Optional[str] = None
                ) -> Tuple[List[Dict[str, Any]], List[Tuple[str, Dict[str, Any]]]]:
    """Reparte los campos en columnas y en tablas hijas, según su estrategia."""
    columns: List[Dict[str, Any]] = []
    children: List[Tuple[str, Dict[str, Any]]] = []
    for name, field in fields.items():
        if not isinstance(field, dict) or field.get("deprecated_by"):
            continue
        strategy = _sql_of(contract, field).get("strategy")
        if strategy == "child_table":
            children.append((name, field))
        elif strategy == "inline_columns":
            # Un map aplanado hereda la exigencia del padre. `generated` es
            # `required` pero con severidad relajada: si sus columnas salieran
            # NOT NULL, el proyector rechazaría un documento que el contrato
            # acepta -- una regla más estricta que la del propio contrato.
            relaxed = (not field.get("required")
                       or field.get("severity") in (WARNING, "info"))
            for member, spec in _sql_members(contract, field).items():
                spec = dict(spec) if not relaxed else {**spec, "required": False}
                columns.append({"column": _sql_name(f"{name}_{member}"),
                                "field": name, "member": member,
                                "sql": _sql_column(contract, member, spec,
                                                   prefix=f"{name}_")})
        else:
            columns.append({"column": _sql_name(name), "field": name, "member": None,
                            "sql": _sql_column(contract, name, field, prefix=prefix,
                                               unique=(name == unique_field))})
    return columns, children


def projection_plan(contract: Contract) -> List[Dict[str, Any]]:
    """Qué tablas hay y qué campo alimenta cada columna. **Una sola vez.**

    El DDL lo renderiza y el proyector lo puebla, y por eso existe: si cada uno
    dedujera el reparto por su cuenta, divergirían -- y el síntoma sería una
    columna que el esquema declara y nadie rellena, o al revés. Es el mismo
    argumento por el que el mapa a SQL vive en el contrato y no en el código,
    aplicado una capa más arriba.
    """
    proj = contract.projection
    if not proj:
        raise SystemExit("error: el contrato no declara el bloque `projection`")
    docs = proj.get("documents_table", "documentos")
    cfg = proj.get("child_tables", {})
    parent_col = cfg.get("parent_column", "doc")
    order_col = cfg.get("order_column", "idx")
    value_col = cfg.get("value_column", "value")
    plan: List[Dict[str, Any]] = []

    def child(parent: str, parent_pk: str, field_name: str,
              field: Dict[str, Any]) -> Dict[str, Any]:
        name = cfg.get("name_pattern", "{parent}_{field}").format(
            parent=parent, field=field_name)
        of = field.get("of", "text")
        members = (list(_sql_members(contract, field).items()) if of == "map"
                   else [(value_col, {"data_type": of, "required": True})])
        columns = [{"column": _sql_name(m),
                    "member": (m if of == "map" else None), "field": field_name,
                    "sql": _sql_column(contract, m, spec)} for m, spec in members]
        return {"table": name, "role": "child", "parent": parent,
                "parent_column": parent_col, "parent_key": parent_pk,
                "order_column": order_col, "field": field_name, "of": of,
                "columns": columns}

    synthetic = [{"column": name, "source": name, "sql":
                  f"{_sql_ident(name)} {spec.get('sql', {}).get('type', 'TEXT')} NOT NULL"
                  + (" PRIMARY KEY" if spec.get("role") == "primary_key" else "")}
                 for name, spec in proj.get("synthetic_columns", {}).items()
                 if isinstance(spec, dict)]
    common_cols, common_children = _sql_fields(contract, contract.common)
    plan.append({"table": docs, "role": "documents", "key": _primary_key(contract, docs),
                 "columns": synthetic + common_cols})
    for field_name, field in common_children:
        plan.append(child(docs, _primary_key(contract, docs), field_name, field))

    for type_name in sorted(contract.types):
        spec = contract.types[type_name]
        if spec.get("generated_only"):
            continue                      # nunca es un documento escrito: no se proyecta
        own = {k: v for k, v in (spec.get("fields") or {}).items()
               if k not in contract.common}
        table = type_name.lower()
        # La clave de un tipo que se declara única lo es también para el motor.
        type_cols, type_children = _sql_fields(
            contract, own,
            unique_field=spec.get("key") if spec.get("key_unique") else None)
        link = (f"{_sql_ident(parent_col)} TEXT NOT NULL PRIMARY KEY "
                f"REFERENCES {_sql_ident(docs)}"
                f"({_sql_ident(_primary_key(contract, docs))}) ON DELETE CASCADE")
        plan.append({"table": table, "role": "type", "type_name": type_name,
                     "key": parent_col,
                     "columns": [{"column": _sql_name(parent_col), "source": "path",
                              "sql": link}]
                                + type_cols})
        for field_name, field in type_children:
            plan.append(child(table, parent_col, field_name, field))
    return plan


def render_ddl(contract: Contract) -> str:
    """El esquema SQL entero, derivado del contrato: ni una tabla escrita a mano.

    Agregar un campo -- o un `data_type` nuevo -- cambia este archivo sin tocar
    una línea de código. Es el criterio de aceptación de T4, y la razón de que
    el mapa a tipos SQL viva en el contrato y no aquí.
    """
    out = [GENERATED_MARK_SQL, "",
           "-- Las claves foráneas no están activas por defecto en SQLite: hay",
           "-- que pedirlo en cada conexión, o las referencias son decorativas.",
           "PRAGMA foreign_keys = ON;", ""]
    for table in projection_plan(contract):
        columns = [c["sql"] for c in table["columns"]]
        if table["role"] == "child":
            columns = [
                f'{_sql_ident(table["parent_column"])} TEXT NOT NULL '
                f'REFERENCES {_sql_ident(table["parent"])}'
                f'({_sql_ident(table["parent_key"])}) ON DELETE CASCADE',
                f'{_sql_ident(table["order_column"])} INTEGER NOT NULL',
            ] + columns + [
                f'PRIMARY KEY ({_sql_ident(table["parent_column"])}, '
                f'{_sql_ident(table["order_column"])})']
        out.append(_sql_create(table["table"], columns))
        out.append("")
    vista = render_timeline_view(contract)
    if vista:
        out.append(vista)
        out.append("")
    alcance = render_scope_view(contract)
    if alcance:
        out.append(alcance)
        out.append("")
    log = render_query_log(contract)
    if log:
        out.append(log)
        out.append("")
    vigencia = render_validity_view(contract)
    if vigencia:
        out.append(vigencia)
        out.append("")
    indice = render_search_index(contract)
    if indice:
        out.append(indice)
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def search_columns(contract: Contract) -> List[str]:
    """Las columnas del índice de texto, en orden. La ruta va primero y sin indexar."""
    cfg = contract.projection.get("search", {})
    if not cfg.get("table"):
        return []
    docs = contract.projection.get("documents_table", "documentos")
    columns = [_primary_key(contract, docs)] + list(cfg.get("fields", []))
    if cfg.get("include_body"):
        columns.append("cuerpo")
    return columns


def render_scope_view(contract: Contract) -> str:
    """Qué documento pertenece a qué proyecto, sobre todos los tipos que lo dicen."""
    cfg = contract.projection.get("scope_view", {})
    view, campo = cfg.get("view"), cfg.get("field", "proyecto")
    if not view:
        return ""
    link = contract.projection.get("child_tables", {}).get("parent_column", "doc")
    partes = [f'  select {_sql_ident(link)}, {_sql_ident(campo)} '
              f'from {_sql_ident(name.lower())}'
              for name in sorted(contract.types)
              if not contract.types[name].get("generated_only")
              and campo in (contract.types[name].get("fields") or {})]
    if not partes:
        return ""
    return (f"-- Nueve tipos declaran `{campo}`: la unión se genera, no se\n"
            f"-- reteclea en cada consulta que la necesita.\n"
            f"CREATE VIEW {_sql_ident(view)} AS\n" + "\n  union all\n".join(partes) + ";")


def render_query_log(contract: Contract) -> str:
    """La tabla del log de consultas: qué se PREGUNTÓ, en números.

    Sin el texto de la pregunta, a propósito. Las dos CQs que la consultan
    necesitan conteos, y el enunciado puede llevar lo que `PERFIL.md` marca
    confidencial: proyectar la palabra sería sacar de su sitio algo que el
    perfil decidió que no salga.
    """
    cfg = contract.projection.get("query_log", {})
    if not cfg.get("table"):
        return ""
    tipos = {"fecha": "TEXT", "docs": "INTEGER", "completos": "INTEGER",
             "citados": "INTEGER", "modo": "TEXT", "archivada": "INTEGER"}
    columnas = [f'  {_sql_ident(c)} {tipos.get(c, "TEXT")} NOT NULL'
                for c in cfg.get("columns", [])]
    columnas.insert(0, '  "linea" INTEGER NOT NULL PRIMARY KEY')
    return ("-- Solo los conteos: el texto de la pregunta puede llevar lo que\n"
            "-- `PERFIL.md` marca confidencial, y estas consultas piden números.\n"
            + _sql_create(cfg["table"], [c.strip() for c in columnas]))


def render_validity_view(contract: Contract) -> str:
    """Qué regía y cuándo, sobre todos los tipos que llevan intervalo.

    El estado derivado se construye desde `derived_states` del contrato, no se
    reescribe aquí: las tres frases que antes eran valores de enum —vigente,
    reemplazada, caducada— se generan de donde está declarado qué significan.
    Retecleadas en SQL, acabarían diciendo algo distinto del contrato sin que
    nadie lo notara, que es exactamente el defecto que T9 vino a cerrar.
    """
    model = contract.data.get("validity_model", {})
    view = model.get("view")
    tipos = [t for t in model.get("applies_to", []) if t in contract.types]
    if not view or not tipos:
        return ""
    docs = contract.projection.get("documents_table", "documentos")
    key = _primary_key(contract, docs)
    link = contract.projection.get("child_tables", {}).get("parent_column", "doc")
    estados = {k: v for k, v in model.get("derived_states", {}).items() if k != "note"}
    caso = "\n".join(f"           when {expr} then '{nombre}'"
                      for nombre, expr in estados.items())
    partes = []
    for type_name in tipos:
        partes.append(
            f'  select d.{_sql_ident(key)} as {_sql_ident(link)}, '
            f"'{type_name}' as \"tipo\", d.\"title\" as \"title\",\n"
            f'         t."valido_desde" as "valido_desde", '
            f't."valido_hasta" as "valido_hasta",\n'
            f'         t."reemplazada_por" as "reemplazada_por", '
            f't."estado" as "estado",\n'
            f'         case\n{caso}\n         end as {_sql_ident(view)}\n'
            f'    from {_sql_ident(type_name.lower())} t '
            f'join {_sql_ident(docs)} d on d.{_sql_ident(key)} = t.{_sql_ident(link)}')
    return ("-- Los tres estados de vigencia son una CONSULTA, no un enum: un\n"
            "-- valor puede contradecir a las fechas que tiene al lado; un CASE no.\n"
            f"CREATE VIEW {_sql_ident(view)} AS\n" + "\n  union all\n".join(partes) + ";")


def render_search_index(contract: Contract) -> str:
    """La tabla virtual FTS5. Se emite siempre; aplicarla es otra cosa.

    El DDL es el esquema canónico y no depende de con qué SQLite se lea. Que
    una máquina concreta no traiga FTS5 compilado lo resuelve el proyector, que
    omite esta sentencia y lo dice -- perder la búsqueda es peor que no perder
    nada, y perder la proyección entera porque falta la búsqueda es peor aún.
    """
    cfg = contract.projection.get("search", {})
    columns = search_columns(contract)
    if not columns:
        return ""
    docs = contract.projection.get("documents_table", "documentos")
    key = _primary_key(contract, docs)
    partes = [f"{_sql_ident(c)}" + (" UNINDEXED" if c == key else "") for c in columns]
    tokenize = cfg.get("tokenize")
    if tokenize:
        partes.append(f"tokenize = '{tokenize}'")
    cuerpo = ",\n".join(f"  {p}" for p in partes)
    return ("-- Devuelve rutas y ranking, nunca contenido: entregar fragmentos\n"
            "-- dejaría al lector donde empezó, leyendo texto para decidir qué leer.\n"
            f"CREATE VIRTUAL TABLE {_sql_ident(cfg['table'])} USING fts5(\n{cuerpo}\n);")


def timeline_fields(contract: Contract) -> List[Tuple[str, str]]:
    """(tipo, campo) de todo lo que es un evento, por REGLA y nunca por nombre.

    Listar los nombres a mano fue el defecto original: `Pregunta` llama a su
    fecha `fecha-creacion` y `Plan` `ultima-revision`, así que seleccionar por
    el nombre `fecha` omitía dos de los cinco tipos **en silencio**. La regla
    mecánica los recoge solos, y un tipo nuevo con fecha entra sin tocar nada.

    El opt-out existe para el caso contrario, que la regla sola tampoco sabe
    resolver: `Diagrama.version` es una fecha y no es un evento.
    """
    out = []
    for type_name in sorted(contract.types):
        spec = contract.types[type_name]
        if spec.get("generated_only"):
            continue
        for name, field in (spec.get("fields") or {}).items():
            if (isinstance(field, dict) and field.get("data_type") == "date"
                    and field.get("timeline") is not False):
                out.append((type_name, name))
    return out


def render_timeline_view(contract: Contract) -> str:
    """La vista de eventos: qué pasó, en una sola lista ordenada."""
    cfg = contract.projection.get("timeline", {})
    view = cfg.get("view")
    campos = timeline_fields(contract)
    if not view or not campos:
        return ""
    docs = contract.projection.get("documents_table", "documentos")
    key = _primary_key(contract, docs)
    link = contract.projection.get("child_tables", {}).get("parent_column", "doc")
    scope = cfg.get("scope_field", "proyecto")
    partes = []
    for type_name, field in campos:
        table = type_name.lower()
        tiene_scope = scope in (contract.types[type_name].get("fields") or {})
        partes.append(
            f'  select t.{_sql_ident(field)} as "fecha", '
            f"'{type_name}' as \"tipo\", '{field}' as \"campo\",\n"
            f'         d.{_sql_ident(key)} as {_sql_ident(link)}, d."title" as "title",\n'
            f'         {("t." + _sql_ident(scope)) if tiene_scope else "null"} as {_sql_ident(scope)}\n'
            f'    from {_sql_ident(table)} t '
            f'join {_sql_ident(docs)} d on d.{_sql_ident(key)} = t.{_sql_ident(link)}')
    orden = "desc" if str(cfg.get("order", "desc")).lower() == "desc" else "asc"
    return (f"-- Un evento por campo fechado, no por documento: un tipo con dos\n"
            f"-- fechas aporta dos filas, y por eso la vista lleva `campo`.\n"
            f"CREATE VIEW {_sql_ident(view)} AS\n"
            + "\n  union all\n".join(partes)
            + f'\n  order by "fecha" {orden};')


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


def bundle_schema_frontmatter(contract: Contract, body: str = "") -> str:
    """Header for the bundle schema, with a fresh generation timestamp.

    Lleva `resumen_hash` como cualquier otro documento: el sistema no puede
    publicar un esquema que incumple el contrato que ese mismo esquema
    describe. Aquí además es el único caso en que el hash se calcula solo sin
    afirmar nada de más -- el generador acaba de escribir ese cuerpo, así que
    sí sabe que el resumen y el cuerpo son de la misma corrida.
    """
    spec = contract.data.get("bundle_schema", {})
    stamp = datetime.now().astimezone().replace(microsecond=0).isoformat()
    digest = digest_body(body)
    return "\n".join([
        "---", f"type: {spec.get('type', 'Indice')}",
        f"title: {quote_scalar(spec.get('title', 'Esquema'))}",
        f"description: {quote_scalar(spec.get('description', ''))}",
        f"resumen: {quote_scalar(spec.get('resumen', ''))}",
        f"resumen_hash: {digest}",
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
    write_if_changed(bundle / rel, bundle_schema_frontmatter(contract, body) + body)
    return True


