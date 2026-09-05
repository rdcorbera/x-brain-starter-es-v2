"""La capa determinista de X-Brain, cortada por sus cuatro trabajos.

`brain.py` era un solo archivo de 2.582 líneas. El riesgo R6 fijaba el corte en
~2.500 «o al aparecer un quinto trabajo», y los profiles de rol lo dispararon.

El corte es **por trabajo, nunca arbitrario** — esa era la condición:

    const.py      el vocabulario compartido, que no es de nadie
    parse.py      LEER      OKF-YAML, documentos, contrato, moldes
    generate.py   ESCRIBIR  plantillas, esquemas, índices, derivados, stubs
    validate.py   COMPROBAR los 21 checks, en dos niveles
    report.py     RENDIR    lo que los otros tres encontraron

Las dependencias van en un solo sentido y no hay ciclos:

    const → parse → generate → validate → report → brain.py (la CLI)

`brain.py` se queda con la interfaz: argparse, los `cmd_*` y el hook de git. Es
el punto de entrada que la documentación, el lanzador y el pre-commit nombran,
así que su ruta no cambia.

Los invariantes siguen siendo los mismos: nunca llama a un modelo, cero
dependencias fuera de la stdlib, y Python 3.11+.
"""

from __future__ import annotations

from .const import (DATE_RE, DATETIME_RE, DEFAULT_BUNDLE, DEFAULT_CONTRACT,
                    ERROR, GENERATED_MARK, INFO, SEVERITY_ORDER,
                    USER_CONTRACT, VERSION, WARNING)
from .parse import (Contract, Document, ParseError, find_profiles,
                    frontmatter_block, parse_frontmatter, quote_scalar,
                    quoting_preserves_meaning, read_frontmatter,
                    scan_yaml_hazards)
from .generate import (build_derived, build_indexes, build_stubs,
                       bundle_schema_frontmatter, compose_derived,
                       derived_is_current, json_schema_for,
                       location_patterns_for_match, period_segments,
                       render_bundle_schema, render_template,
                       PRE_COMMIT_MARKER, resolve_locations, split_document,
                       write_bundle_schema, write_if_changed, write_text_lf)
from .validate import (CHECKS, Finding, Validator, apply_fixes, check_value,
                       fix_yaml_hazards, is_uninitialised, parse_instant,
                       require_bundle)
from .report import governance_report, print_profile_proposals, report

__all__ = [n for n in dir() if not n.startswith("_")]
