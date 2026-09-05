"""Vocabulario compartido por los cuatro trabajos.

Vive aparte porque no pertenece a ninguno. Si estas constantes estuvieran dentro
de `parse` o de `validate`, los otros tres importarían de ese módulo por algo que
no es su trabajo, y el corte dejaría de ser por trabajos.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Fails loudly rather than degrading quietly: below 3.11 `fromisoformat`
# rejects the `Z` suffix, `parse_instant` would return None for a perfectly
# valid instant, and V15 would skip every stale document without saying so.
if sys.version_info < (3, 11):
    raise SystemExit(
        "error: brain.py necesita Python 3.11+ (este intérprete es "
        f"{sys.version_info.major}.{sys.version_info.minor}).\n"
        "       3.11 trae el parseo ISO 8601 completo que exige `stale_after`;\n"
        "       por debajo, la caducidad se evaluaría mal en silencio.")

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

# Formatos, no comprobaciones: los usan tanto el validador como el
# generador, así que no pueden vivir dentro de ninguno de los dos.
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

DATETIME_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2})?(\.\d+)?(Z|[+-]\d{2}:?\d{2})$")
