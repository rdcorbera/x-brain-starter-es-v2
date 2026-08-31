#!/usr/bin/env python3
"""Read-only probe: can this machine host the cut-2 SQLite projection?

Answers three questions that decide the design, not one:

  1. Does `sqlite3` exist here, and which SQLite does it carry? On Windows
     Python bundles its own sqlite3.dll, so the version follows the
     interpreter rather than the OS -- but that only helps once measured.
  2. Which features are compiled in? FTS5 is a build flag, not a version:
     it can be missing from a perfectly recent SQLite. Whether it is there
     decides BM25 search versus a hand-rolled inverted index.
  3. Is the chosen directory a place a database can actually live? A synced
     folder or a network share corrupts SQLite -- the locking it needs is
     not reliable there. WAL mode is the sharpest probe of that: it fails on
     exactly the filesystems that are unsafe.

Writes only inside a temporary directory it creates under the path being
tested, and removes it. Touches nothing else. No network.

Stdlib only. Python 3.9+ -- the same floor as survey.py and for the same
reason: this runs on the target machine to find out what is there, so it
cannot depend on its own findings.

Usage:
    python sqlite-probe.py [PATH] [--json]

    PATH    Directory the projection would live in (default: current dir).
            Pass the folder you actually plan to use.
    --json  Machine-readable output.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import sys
import tempfile
import time
from pathlib import Path

# Feature -> (probe SQL, why it matters, whether cut 2 can proceed without it)
FEATURES = [
    ("fts5", "CREATE VIRTUAL TABLE p USING fts5(x)",
     "búsqueda de texto BM25", "degradado: índice invertido propio"),
    ("window_functions", "SELECT row_number() OVER (ORDER BY 1)",
     "«última versión por clase», rankings", "degradado: subconsultas"),
    ("json", "SELECT json_extract('{\"a\":1}','$.a')",
     "leer campos de lista/mapa del frontmatter", "degradado: normalizar a tablas"),
    ("cte_recursive", "WITH RECURSIVE t(n) AS (SELECT 1 UNION ALL SELECT n+1 FROM t WHERE n<3) SELECT count(*) FROM t",
     "recorrer el grafo reporta-a (organigrama)", "BLOQUEANTE para CQ-31"),
    ("strict_tables", "CREATE TABLE s(a INT) STRICT",
     "proyección tipada: el motor rechaza el tipo malo", "degradado: validar en Python"),
    ("upsert", "CREATE TABLE u(a INT PRIMARY KEY, b INT); INSERT INTO u VALUES(1,1) ON CONFLICT(a) DO UPDATE SET b=2",
     "reproyectar sin borrar la base", "degradado: DELETE + INSERT"),
    ("returning", "CREATE TABLE r(a); INSERT INTO r VALUES(1) RETURNING a",
     "comodidad al escribir", "irrelevante"),
    ("generated_columns", "CREATE TABLE g(a INT, b INT AS (a*2))",
     "columnas derivadas del frontmatter", "degradado: calcular al proyectar"),
]


def probe_interpreter():
    return {
        "python_version": platform.python_version(),
        "bits": 64 if sys.maxsize > 2**32 else 32,
        "platform": platform.system(),
        "release": platform.release(),
    }


def probe_sqlite():
    out = {"module": False}
    try:
        import sqlite3
    except Exception as exc:                       # noqa: BLE001
        out["error"] = f"{type(exc).__name__}: {exc}"
        return out, None
    out["module"] = True
    # `sqlite3.version` is the driver's own version, not the engine's. It was
    # deprecated in 3.12 and REMOVED in 3.14, so reading it would crash on the
    # newest interpreters -- and it never said anything useful anyway.
    out["sqlite_version"] = sqlite3.sqlite_version
    out["threadsafety"] = sqlite3.threadsafety
    return out, sqlite3


def probe_features(sqlite3):
    """Each feature in its own connection: a failed DDL can poison the rest."""
    results = {}
    for name, sql, why, without in FEATURES:
        con = sqlite3.connect(":memory:")
        try:
            for stmt in sql.split(";"):            # executescript would autocommit
                if stmt.strip():
                    con.execute(stmt)
            results[name] = {"ok": True, "why": why}
        except Exception as exc:                   # noqa: BLE001
            results[name] = {"ok": False, "why": why,
                             "without_it": without,
                             "error": f"{type(exc).__name__}: {exc}"}
        finally:
            con.close()
    return results


def probe_compile_options(sqlite3):
    con = sqlite3.connect(":memory:")
    try:
        return sorted(r[0] for r in con.execute("PRAGMA compile_options"))
    except Exception:                              # noqa: BLE001
        return []
    finally:
        con.close()


def drive_kind(path: Path):
    """DRIVE_FIXED is the only safe answer. ctypes is stdlib, so no dependency."""
    if platform.system() != "Windows":
        return "n/a (no es Windows)"
    try:
        import ctypes
        root = os.path.splitdrive(str(path.resolve()))[0] + "\\"
        kinds = {0: "desconocido", 1: "no existe", 2: "extraíble",
                 3: "disco local", 4: "unidad de red", 5: "CD-ROM", 6: "disco RAM"}
        return kinds.get(ctypes.windll.kernel32.GetDriveTypeW(root), "?")
    except Exception as exc:                       # noqa: BLE001
        return f"no se pudo determinar: {exc}"


def synced_folder(path: Path):
    """Name the sync client if the path sits under one. Cheap and reliable."""
    resolved = str(path.resolve())
    hits = []
    for var in ("OneDrive", "OneDriveCommercial", "OneDriveConsumer"):
        root = os.environ.get(var)
        if root and resolved.lower().startswith(root.lower()):
            hits.append(f"{var} ({root})")
    for marker in ("onedrive", "dropbox", "google drive", "iclouddrive", "box sync"):
        if marker in resolved.lower() and not any(marker in h.lower() for h in hits):
            hits.append(f"coincidencia por nombre: {marker}")
    return hits


def probe_storage(sqlite3, target: Path):
    """Create a scratch DB where the projection would live, then clean up."""
    out = {"path_kind": drive_kind(target), "synced": synced_folder(target)}
    if not target.is_dir():
        # The path itself never enters the output: the last survey's did, and it
        # carried the organisation and a user id. Its character is enough.
        out["error"] = "la ruta indicada no existe o no es un directorio"
        return out
    out["writable"] = os.access(str(target), os.W_OK)
    if not out["writable"]:
        return out

    tmp = Path(tempfile.mkdtemp(prefix=".sqlite-probe-", dir=str(target)))
    db = tmp / "probe.db"
    try:
        con = sqlite3.connect(str(db))
        # WAL is the real test: it needs shared memory and honest file locking,
        # which is exactly what a synced or networked filesystem does not give.
        out["journal_mode_wal"] = con.execute(
            "PRAGMA journal_mode=WAL").fetchone()[0].lower() == "wal"
        con.execute("CREATE TABLE t(a INTEGER PRIMARY KEY, b TEXT)")
        con.commit()

        rows = 5000
        start = time.perf_counter()
        con.executemany("INSERT INTO t(b) VALUES(?)", [(f"fila {i}",) for i in range(rows)])
        con.commit()
        elapsed = time.perf_counter() - start
        out["insert_rows"] = rows
        out["insert_seconds"] = round(elapsed, 3)
        out["insert_rows_per_second"] = int(rows / elapsed) if elapsed else None

        # A second connection while the first is open: the pre-commit hook and
        # an editor will do exactly this.
        con2 = sqlite3.connect(str(db))
        out["second_connection_reads"] = con2.execute("SELECT count(*) FROM t").fetchone()[0] == rows
        con2.close()
        con.close()
        out["db_bytes"] = db.stat().st_size
        out["ok"] = True
    except Exception as exc:                       # noqa: BLE001
        out["ok"] = False
        out["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return out


def verdict(data):
    """What the numbers mean for cut 2, stated plainly."""
    problems, warnings = [], []
    sq = data["sqlite"]
    if not sq.get("module"):
        problems.append("`sqlite3` no está disponible: sin él no hay proyección posible.")
        return problems, warnings

    feats = data["features"]
    if not feats.get("cte_recursive", {}).get("ok"):
        problems.append("Sin CTE recursivas no se puede recorrer el organigrama (CQ-31).")
    if not feats.get("fts5", {}).get("ok"):
        warnings.append("Sin FTS5 no hay BM25: la búsqueda de texto sería un índice invertido propio.")
    for name in ("window_functions", "json", "strict_tables", "upsert", "generated_columns"):
        if not feats.get(name, {}).get("ok"):
            warnings.append(f"Sin `{name}`: {feats[name]['without_it']}.")

    st = data["storage"]
    # Anything short of a completed storage probe is a problem, not silence:
    # a missing directory used to fall through here and report "viable".
    if not st.get("ok"):
        problems.append(
            "No se pudo probar el almacenamiento en esa ruta: "
            + (st.get("error") or ("no es escribible" if st.get("writable") is False
                                   else "la prueba no llegó a completarse")))
    if st.get("synced"):
        problems.append(
            "La ruta está dentro de una carpeta sincronizada: SQLite se corrompe ahí. "
            "Elegir un directorio local fuera del cliente de sincronización.")
    if st.get("path_kind") == "unidad de red":
        problems.append("La ruta está en una unidad de red: el bloqueo de SQLite no es fiable ahí.")
    if st.get("ok") and not st.get("journal_mode_wal"):
        problems.append(
            "WAL no se pudo activar en esa ruta. Es la señal de que el sistema de "
            "archivos no da el bloqueo que SQLite necesita.")
    if st.get("ok") and (st.get("insert_rows_per_second") or 0) < 5000:
        warnings.append(
            f"Escritura lenta ({st['insert_rows_per_second']:,} filas/s): "
            "probable antivirus o EDR escaneando cada escritura.")
    if st.get("ok") is False:
        problems.append(f"No se pudo crear una base de prueba: {st.get('error')}")
    return problems, warnings


def report(data):
    w = print
    w("=" * 66)
    w("  SONDA SQLITE  --  ¿puede vivir aquí la proyección del corte 2?")
    w("=" * 66)

    i = data["interpreter"]
    w(f"\nINTÉRPRETE\n  Python {i['python_version']} ({i['bits']} bits) en {i['platform']} {i['release']}")

    sq = data["sqlite"]
    w("\nSQLITE")
    if not sq.get("module"):
        w(f"  módulo sqlite3            NO DISPONIBLE -- {sq.get('error')}")
    else:
        w(f"  versión de SQLite         {sq['sqlite_version']}")
        w(f"  hilos (threadsafety)      {sq['threadsafety']}")

        w("\nCAPACIDADES")
        for name, res in data["features"].items():
            mark = "OK " if res["ok"] else "NO "
            w(f"  {mark} {name:20} {res['why']}")
            if not res["ok"]:
                w(f"      sin ella: {res['without_it']}")

    st = data["storage"]
    w(f"\nALMACENAMIENTO  ({data['target_note']})")
    w(f"  tipo de unidad            {st.get('path_kind')}")
    w(f"  carpeta sincronizada      {', '.join(st['synced']) if st.get('synced') else 'no'}")
    w(f"  escribible                {'sí' if st.get('writable') else 'NO'}")
    if st.get("ok"):
        w(f"  modo WAL                  {'sí' if st['journal_mode_wal'] else 'NO -- señal de alarma'}")
        w(f"  segunda conexión lee      {'sí' if st['second_connection_reads'] else 'NO'}")
        w(f"  escritura                 {st['insert_rows']:,} filas en {st['insert_seconds']}s "
          f"({st['insert_rows_per_second']:,} filas/s)")
    elif "error" in st:
        w(f"  error                     {st['error']}")

    problems, warnings = data["verdict"]["problems"], data["verdict"]["warnings"]
    w("\n" + "=" * 66)
    if not problems and not warnings:
        w("  VEREDICTO: la proyección SQLite es viable aquí, sin reservas.")
    elif not problems:
        w("  VEREDICTO: viable, con degradaciones.")
        for x in warnings:
            w(f"    - {x}")
    else:
        w("  VEREDICTO: NO viable tal cual. Hay que resolver:")
        for x in problems:
            w(f"    ! {x}")
        for x in warnings:
            w(f"    - {x}")
    w("=" * 66)
    w("  No se leyó ningún documento. La base de prueba se creó y se borró.")
    w("=" * 66)


def main() -> int:
    ap = argparse.ArgumentParser(description="¿Puede esta máquina alojar la proyección SQLite?")
    ap.add_argument("path", nargs="?", default=".",
                    help="directorio donde viviría la base (por defecto: el actual)")
    ap.add_argument("--json", action="store_true", help="salida procesable")
    args = ap.parse_args()

    target = Path(args.path).expanduser()
    data = {"interpreter": probe_interpreter(),
            "target_note": "ruta indicada" if args.path != "." else "directorio actual"}
    data["sqlite"], sqlite3 = probe_sqlite()
    data["features"] = probe_features(sqlite3) if sqlite3 else {}
    data["compile_options"] = probe_compile_options(sqlite3) if sqlite3 else []
    data["storage"] = probe_storage(sqlite3, target) if sqlite3 else {}
    problems, warnings = verdict(data)
    data["verdict"] = {"problems": problems, "warnings": warnings,
                       "viable": not problems}

    if args.json:
        # The path itself is deliberately not emitted: on the last survey it
        # carried the organisation and a user id. Only its character is.
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        report(data)
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
