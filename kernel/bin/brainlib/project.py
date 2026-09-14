"""Proyectar: los documentos del cerebro, como una base consultable.

Es el último trabajo de la cadena y el único que abre `sqlite3`. Lo que produce
es **derivado y desechable**: el markdown sigue siendo la fuente de verdad, y
`--full` reconstruye la base entera desde cero. Por eso no se versiona.

El reparto de campo a columna NO se decide aquí: lo describe `projection_plan`
en `generate`, que es de donde sale también el DDL. Si cada uno lo dedujera por
su cuenta, un día el esquema declararía una columna que nadie rellena.

La pasada incremental compara el SHA-256 de cada archivo con el que guarda su
fila. Un cerebro de 301 documentos se proyecta entero en decenas de
milisegundos, así que lo incremental no está aquí por velocidad: está porque
`--full` y una pasada incremental tienen que producir **exactamente lo mismo**,
y esa es una propiedad que se puede comprobar.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .const import DEFAULT_BUNDLE
from .parse import Contract, Document
from .generate import projection_plan, render_ddl


def database_path(contract: Contract) -> Path:
    return Path(contract.projection.get("database", {}).get("path", "_db/brain.db"))


def connect(path: Path) -> sqlite3.Connection:
    """Una conexión con las claves foráneas activas.

    SQLite las trae apagadas por compatibilidad, y una FK que no se aplica es
    decoración: la base aceptaría una fila hija huérfana sin decir nada.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.execute("PRAGMA foreign_keys = ON")
    return db


def _value(doc: Document, column: Dict[str, Any]) -> Any:
    """El valor de una columna para este documento, o None."""
    if column.get("source") == "path":
        return doc.rel
    raw = doc.meta.get(column["field"])
    if column.get("member"):
        raw = raw[0] if isinstance(raw, list) and raw else raw
        raw = raw.get(column["member"]) if isinstance(raw, dict) else None
    return _scalar(raw)


def _scalar(raw: Any) -> Any:
    if raw is None or isinstance(raw, (int, float)):
        return raw
    if isinstance(raw, bool):
        return int(raw)
    return str(raw)


def _entries(doc: Document, table: Dict[str, Any]) -> List[Any]:
    """Las entradas de un campo de lista, normalizadas.

    `accepts_scalar` del contrato dice que un mapa suelto vale por una lista de
    un elemento. Hasta ahora eso solo lo sabía el validador; si el proyector no
    lo supiera, el mismo documento proyectaría distinto según cómo lo escribió
    quien lo redactó.
    """
    raw = doc.meta.get(table["field"])
    if raw is None:
        return []
    return raw if isinstance(raw, list) else [raw]


def project(contract: Contract, bundle: Path, db_path: Optional[Path] = None,
            full: bool = False) -> Dict[str, int]:
    """Proyecta el bundle. Devuelve qué cambió."""
    db_path = Path(db_path) if db_path else database_path(contract)
    plan = projection_plan(contract)
    docs_table = next(t for t in plan if t["role"] == "documents")

    if full and db_path.exists():
        db_path.unlink()
        for sidecar in (db_path.with_name(db_path.name + "-wal"),
                        db_path.with_name(db_path.name + "-shm")):
            sidecar.unlink(missing_ok=True)

    db = connect(db_path)
    fresh = not db.execute(
        "select count(*) from sqlite_master where type='table'").fetchone()[0]
    if fresh:
        db.executescript(render_ddl(contract))

    known: Dict[str, str] = {}
    if not fresh:
        known = dict(db.execute(f'select "{docs_table["key"]}", "hash" '
                                f'from "{docs_table["table"]}"'))

    tables = {t["type_name"] for t in plan if t["role"] == "type"}
    stats = {"escritos": 0, "sin cambios": 0, "retirados": 0}
    seen = set()
    for path in sorted(bundle.rglob("*.md")):
        if any(part.startswith(".") for part in path.relative_to(bundle).parts):
            continue
        doc = Document(path, bundle, contract.reserved)
        if not _projectable(contract, doc, tables):
            continue
        seen.add(doc.rel)
        digest = _file_digest(path)
        if known.get(doc.rel) == digest:
            stats["sin cambios"] += 1
            continue
        _write_document(db, plan, doc, digest)
        stats["escritos"] += 1

    for rel in sorted(set(known) - seen):
        # ON DELETE CASCADE se lleva las filas de tipo y las hijas.
        db.execute(f'delete from "{docs_table["table"]}" '
                   f'where "{docs_table["key"]}" = ?', (rel,))
        stats["retirados"] += 1

    db.commit()
    db.close()
    return stats


def _projectable(contract: Contract, doc: Document, tables: set) -> bool:
    """Qué se proyecta: conocimiento, y solo conocimiento.

    Fuera quedan tres cosas, cada una por su motivo:

    - **Los reservados** (`log.md`, `log-consultas.md`, el manifiesto): son
      registros con formato propio, no conceptos tipados.
    - **Los exentos y derivados** (`index.md`, `GOALS.md`, `ESQUEMA.md`): los
      escribe el generador desde este mismo contenido. Proyectarlos sería
      guardar dos veces lo mismo y que una copia envejezca.
    - **Un `type` sin tabla**, que es como se excluye solo lo `generated_only`.

    Es la misma frontera que usa la validación de perfil, y eso no es casual:
    un documento que el validador no juzga como conocimiento tampoco es
    conocimiento para el proyector.
    """
    if doc.is_reserved or not doc.has_frontmatter:
        return False
    if doc.rel in contract.exempt or doc.path.name in contract.exempt:
        return False
    return doc.meta.get("type") in tables


def _file_digest(path: Path) -> str:
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_document(db: sqlite3.Connection, plan: List[Dict[str, Any]],
                    doc: Document, digest: str) -> None:
    """Reescribe un documento entero: su fila, la de su tipo y las hijas.

    Se borra y se vuelve a insertar en vez de actualizar campo a campo. Es más
    simple y no deja restos: si un documento pierde una etiqueta, un UPDATE
    dejaría la fila hija vieja ahí, y nadie la echaría en falta.
    """
    docs_table = next(t for t in plan if t["role"] == "documents")
    db.execute(f'delete from "{docs_table["table"]}" '
               f'where "{docs_table["key"]}" = ?', (doc.rel,))

    for table in plan:
        if table["role"] == "type" and table["type_name"] != doc.meta.get("type"):
            continue
        if table["role"] == "child" and table["parent"] not in (
                docs_table["table"], str(doc.meta.get("type", "")).lower()):
            continue
        if table["role"] == "child":
            for idx, entry in enumerate(_entries(doc, table)):
                values = [doc.rel, idx]
                for column in table["columns"]:
                    values.append(_scalar(entry.get(column["member"])
                                          if isinstance(entry, dict) and column["member"]
                                          else entry))
                _insert(db, table["table"],
                        [table["parent_column"], table["order_column"]]
                        + [c["column"] for c in table["columns"]], values)
            continue
        columns = [c["column"] for c in table["columns"]]
        values = [digest if c["column"] == "hash" else _value(doc, c)
                  for c in table["columns"]]
        _insert(db, table["table"], columns, values)


def _insert(db: sqlite3.Connection, table: str, columns: List[str],
            values: List[Any]) -> None:
    names = ", ".join(f'"{c}"' for c in columns)
    marks = ", ".join("?" * len(columns))
    db.execute(f'insert into "{table}" ({names}) values ({marks})', values)


def snapshot(db_path: Path) -> str:
    """El contenido lógico de la base, en texto ordenado y estable.

    Comparar dos archivos `.db` byte a byte no sirve: SQLite reutiliza páginas
    y el mismo contenido puede ocupar bytes distintos. Lo que el criterio de T5
    pide comparar es lo que la base DICE, y eso es esto.
    """
    db = connect(db_path)
    out: List[str] = []
    for (table,) in db.execute("select name from sqlite_master where type='table' "
                               "order by name"):
        columns = [r[1] for r in db.execute(f'pragma table_info("{table}")')]
        order = ", ".join(f'"{c}"' for c in columns)
        out.append(f"# {table}({', '.join(columns)})")
        for row in db.execute(f'select {order} from "{table}" order by {order}'):
            out.append(" | ".join("" if v is None else str(v) for v in row))
    db.close()
    return "\n".join(out) + "\n"
