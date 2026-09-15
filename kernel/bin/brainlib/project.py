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

import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .const import DEFAULT_BUNDLE
from .parse import Contract, Document
from .generate import projection_plan, render_ddl, search_columns, split_document


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
    indexable = True
    if fresh:
        indexable = _apply_ddl(db, contract)
    else:
        indexable = bool(db.execute(
            "select count(*) from sqlite_master where name = ?",
            (contract.projection.get("search", {}).get("table"),)).fetchone()[0])
    columns = search_columns(contract) if indexable else []

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
        if columns:
            _index_document(db, contract, doc, columns)
        stats["escritos"] += 1

    for rel in sorted(set(known) - seen):
        # ON DELETE CASCADE se lleva las filas de tipo y las hijas.
        db.execute(f'delete from "{docs_table["table"]}" '
                   f'where "{docs_table["key"]}" = ?', (rel,))
        if columns:
            # El índice es una tabla virtual: ninguna clave foránea lo limpia,
            # así que si no se borra aquí, un documento retirado seguiría
            # apareciendo en las búsquedas.
            db.execute(f'delete from "{contract.projection["search"]["table"]}" '
                       f'where "{columns[0]}" = ?', (rel,))
        stats["retirados"] += 1

    consultas = _project_query_log(db, contract, bundle)
    if consultas:
        stats["consultas"] = consultas
    if not indexable:
        stats["sin índice"] = 1
    db.commit()
    db.close()
    return stats


def has_fts5() -> bool:
    """¿Trae FTS5 este SQLite? Es un flag de compilación, no una versión.

    Un SQLite perfectamente reciente puede no traerlo, así que preguntarle a la
    versión no sirve: se comprueba intentándolo, que es lo mismo que hace
    `sqlite-probe.py` y por lo mismo.
    """
    try:
        db = sqlite3.connect(":memory:")
        db.execute("create virtual table t using fts5(x)")
        db.close()
        return True
    except sqlite3.Error:
        return False


def _apply_ddl(db: sqlite3.Connection, contract: Contract) -> bool:
    """Crea el esquema. Devuelve si el índice de texto quedó disponible."""
    ddl = render_ddl(contract)
    if has_fts5():
        db.executescript(ddl)
        return True
    # Sin FTS5 se proyecta igual, sin índice, y se dice en voz alta: perder la
    # búsqueda es peor que no perder nada, y perder la proyección entera por
    # ella es peor todavía.
    sentencias = [s for s in ddl.split(";") if "VIRTUAL TABLE" not in s.upper()]
    db.executescript(";".join(sentencias) + ";")
    return False


def _index_document(db: sqlite3.Connection, contract: Contract, doc: Document,
                    columns: List[str]) -> None:
    """Una fila del índice de texto: los tres niveles de lectura y el cuerpo."""
    table = contract.projection["search"]["table"]
    db.execute(f'delete from "{table}" where "{columns[0]}" = ?', (doc.rel,))
    values = [doc.rel]
    for column in columns[1:]:
        if column == "cuerpo":
            values.append(split_document(doc.text)[1])
        else:
            values.append(str(doc.meta.get(column) or ""))
    marks = ", ".join("?" * len(columns))
    names = ", ".join(f'"{c}"' for c in columns)
    db.execute(f'insert into "{table}" ({names}) values ({marks})', values)


def search(contract: Contract, query: str, db_path: Optional[Path] = None,
           limit: int = 10) -> List[Tuple[str, float, str]]:
    """Buscar. Devuelve (ruta, rank, título) -- nunca el texto encontrado."""
    db_path = Path(db_path) if db_path else database_path(contract)
    table = contract.projection.get("search", {}).get("table")
    if not db_path.exists():
        raise SystemExit(f"error: no hay proyección en `{db_path}`.\n"
                         "       Créala con `brain project`.")
    db = connect(db_path)
    existe = db.execute("select count(*) from sqlite_master where name = ?",
                        (table,)).fetchone()[0]
    if not existe:
        db.close()
        raise SystemExit(
            "error: esta proyección no tiene índice de texto.\n"
            "       Este SQLite no trae FTS5 compilado -- no es cuestión de versión,\n"
            "       es un flag de compilación. Compruébalo con:\n"
            "         ./brain kernel/bin/sqlite-probe.py <ruta>\n"
            "       El resto de la proyección funciona: `brain project` sin `--search`.")
    key = search_columns(contract)[0]
    rows = db.execute(
        f'select f."{key}", bm25("{table}"), d."title" from "{table}" f '
        f'join "documentos" d on d."path" = f."{key}" '
        f'where "{table}" match ? order by bm25("{table}") limit ?',
        (query, limit)).fetchall()
    db.close()
    return rows


def _project_query_log(db: sqlite3.Connection, contract: Contract,
                       bundle: Path) -> int:
    """El log de consultas, en números. Lo que se PREGUNTÓ al cerebro.

    El patrón sale de `reserved_files`, que es el mismo que comprueba V26: el
    proyector parsea exactamente lo que el validador valida, así que no hay una
    segunda lectura de la misma línea que pueda discrepar de la primera.

    Una línea mal formada **no se proyecta y no se inventa**: V26 ya la reporta
    como lo que es, un defecto del log. Rellenar aquí un hueco sería fabricar
    un dato de instrumentación, que es el peor sitio donde fabricar.
    """
    cfg = contract.projection.get("query_log", {})
    tabla = cfg.get("table")
    fuente = bundle / cfg.get("source", "log-consultas.md")
    if not tabla or not fuente.exists():
        return 0
    spec = contract.reserved.get(cfg.get("source", ""), {}).get("line_format", {})
    patron = spec.get("pattern")
    if not patron:
        return 0
    db.execute(f'delete from "{tabla}"')
    fecha, filas = None, 0
    for numero, linea in enumerate(fuente.read_text(encoding="utf-8").splitlines(), 1):
        encabezado = re.match(r"^##\s+(\d{4}-\d{2}-\d{2})\s*$", linea)
        if encabezado:
            fecha = encabezado.group(1)
            continue
        hit = re.match(patron, linea)
        if not hit or not fecha:
            continue
        g = hit.groupdict()
        db.execute(f'insert into "{tabla}" ("linea", "fecha", "docs", "completos", '
                   f'"citados", "modo", "archivada") values (?, ?, ?, ?, ?, ?, ?)',
                   (numero, fecha, int(g["docs"]), int(g["completos"]),
                    int(g["citados"]), g["modo"], int(g["archivada"] == "archivada")))
        filas += 1
    return filas


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


def snapshot(db_path: Path, contract: Optional[Contract] = None) -> str:
    """El contenido lógico de la base, en texto ordenado y estable.

    Comparar dos archivos `.db` byte a byte no sirve: SQLite reutiliza páginas
    y el mismo contenido puede ocupar bytes distintos. Lo que el criterio de T5
    pide comparar es lo que la base DICE, y eso es esto.
    """
    db = connect(db_path)
    out: List[str] = []
    # Las tablas sombra del índice (`<fts>_data`, `_idx`, `_docsize`…) guardan
    # su estructura interna en blobs: reconstruir el índice puede dejarlos
    # distintos aunque las búsquedas den lo mismo. Compararlos haría fallar el
    # criterio de T5 por una diferencia que no significa nada. La tabla virtual
    # SÍ se vuelca, que es donde está su contenido.
    fts = (contract.projection.get("search", {}).get("table", "")
           if contract else "")
    for (table,) in db.execute("select name from sqlite_master where type='table' "
                               "order by name"):
        if fts and table.startswith(fts + "_"):
            continue
        columns = [r[1] for r in db.execute(f'pragma table_info("{table}")')]
        order = ", ".join(f'"{c}"' for c in columns)
        out.append(f"# {table}({', '.join(columns)})")
        for row in db.execute(f'select {order} from "{table}" order by {order}'):
            out.append(" | ".join("" if v is None else str(v) for v in row))
    db.close()
    return "\n".join(out) + "\n"
