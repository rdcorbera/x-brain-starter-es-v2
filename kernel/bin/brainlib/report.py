"""Reportar: rendir a una persona lo que los otros tres encontraron.

Separado a propósito. Un informe que se mezcla con la comprobación acaba
decidiendo qué se comprueba, y en el paso 7 este rendía en inglés a una persona
contra la política de idioma sin que nada lo notara."""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List

from .const import ERROR, INFO, SEVERITY_ORDER, WARNING
from .parse import Contract
from .validate import CHECKS, Finding, Validator

def report(findings: List[Finding], bundle: Path, full: bool) -> None:
    if not findings:
        print(f"\nbrain validate {bundle}: sin hallazgos.\n")
        return

    by_check = defaultdict(list)
    for f in findings:
        by_check[f.check].append(f)

    counts = Counter(f.severity for f in findings)
    print()
    print("=" * 66)
    print(f"  BRAIN VALIDATE  --  {bundle}")
    print("=" * 66)
    print()
    print("RESUMEN")
    print(f"  {'check':<6} {'nivel':<8} {'error':>7} {'aviso':>7} {'info':>6}   qué")
    for check in sorted(by_check, key=lambda c: (SEVERITY_ORDER[by_check[c][0].severity], c)):
        group = by_check[check]
        level, label = CHECKS[check]
        # Counts per severity, not "worst severity + total": one check can
        # report both, and "error 2" reading as "2 errors" is a lie when one
        # of them is a warning.
        by_sev = Counter(f.severity for f in group)
        cells = (f"{by_sev.get(ERROR, 0) or '-':>7} "
                 f"{by_sev.get(WARNING, 0) or '-':>7} "
                 f"{by_sev.get(INFO, 0) or '-':>6}")
        print(f"  {check:<6} {level:<8} {cells}   {label}")
    print()
    print("  " + "  ".join(f"{k}: {v:,}" for k, v in
                           sorted(counts.items(), key=lambda kv: SEVERITY_ORDER[kv[0]])))

    limit = None if full else 8
    print()
    print("DETALLE" + ("" if full else f"  (hasta {limit} por check; --full para todo)"))
    for check in sorted(by_check, key=lambda c: (SEVERITY_ORDER[by_check[c][0].severity], c)):
        group = by_check[check]
        print()
        print(f"  {check} -- {CHECKS[check][1]}")
        for f in group[:limit]:
            where = f"{f.path}:{f.line}" if f.line else f.path
            print(f"    [{f.severity:<7}] {where}")
            print(f"              {f.message}")
        if limit and len(group) > limit:
            print(f"    ... y {len(group) - limit:,} más")
    print()


# ============================================================================
def governance_report(contract: Contract, validator: Validator) -> None:
    """The posture report a data-governance function would actually ask for."""
    docs = [d for d in validator.docs
            if not d.is_reserved and not validator.is_exempt(d) and d.type]
    field = contract.classification.get("field", "classification")

    print()
    print("=" * 66)
    print(f"  GOBIERNO DE DATOS  --  {validator.bundle}")
    print("=" * 66)

    gov = contract.governance
    print()
    print("MARCO")
    print(f"  responsable del contrato   {gov.get('steward', '(sin definir)')}")
    print(f"  revisión                   {gov.get('review_cadence', '(sin definir)')}")
    print(f"  documentos clasificables   {len(docs):,}")

    print()
    print("CLASIFICACIÓN")
    counts = Counter(d.meta.get(field) for d in docs)
    for level in contract.levels:
        n = counts.get(level, 0)
        pct = (100 * n // len(docs)) if docs else 0
        print(f"  {level:<14} {n:>7,}  ({pct:>3}%)")
    unset = counts.get(None, 0)
    if unset:
        print(f"  {'sin clasificar':<14} {unset:>7,}  "
              f"({100 * unset // len(docs) if docs else 0:>3}%)  <- deuda de migración")

    print()
    print("DATO PERSONAL")
    personal = [t for t, s in contract.types.items() if s.get("personal_data")]
    if personal:
        for type_name in personal:
            n = sum(1 for d in docs if d.type == type_name)
            floor = contract.min_classification(type_name)
            print(f"  {type_name:<14} {n:>7,} documentos   piso `{floor}`")
        print("  Revisar estos antes de compartir o exportar el cerebro.")
    else:
        print("  ningún tipo declarado como dato personal")

    print()
    print("RESPONSABILIDAD")
    unresolved = [f for f in validator.findings if f.check == "V17"]
    stewarded = sum(
        1 for d in docs
        for name, spec in contract.fields_for(d.type).items()
        if spec.get("steward") and d.meta.get(name))
    print(f"  campos de responsabilidad con valor   {stewarded:>7,}")
    print(f"  sin resolver a ficha Persona          {len(unresolved):>7,}")

    print()
    print("CONFIANZA  (¿qué escribió un agente y nadie confirmó?)")
    unverified = [d for d in docs if not d.meta.get("verified")]
    by_agent = [d for d in unverified
                if isinstance(d.meta.get("generated"), dict)
                and not str(d.meta["generated"].get("by", "")).startswith("human:")]
    print(f"  sin `verified`                        {len(unverified):>7,}")
    print(f"  de esos, generados por un agente      {len(by_agent):>7,}  <- deuda de revisión")

    print()
    print("CICLO DE VIDA")
    stale = [f for f in validator.findings if f.check == "V15"]
    deprecated = sum(1 for d in docs if d.meta.get("status") == "deprecated")
    print(f"  vencidos y aún `stable`               {len(stale):>7,}")
    print(f"  marcados `deprecated`                 {deprecated:>7,}")

    print()
    print("=" * 66)
    print("  Conteos y formas. No se extrajo contenido de ningún documento.")
    print("=" * 66)
    print()


def print_profile_proposals(profile: Dict[str, Any]) -> None:
    """What the profile SUGGESTS, handed over by the command that applied it.

    `init --profile` copies only the body, so the machine-readable suggestions
    -- the period shape, the area folders -- never reach the bundle. Without
    this they would have to be fetched by opening a kernel file by hand, which
    is exactly the reading a command is supposed to replace.

    They are printed as proposals, not applied. Areas in particular belong to
    an organisation and not to a role: the name is almost always wrong until a
    person renames it, and creating them here would be writing without asking.
    """
    meta = profile["meta"]
    period, areas = meta.get("period_format"), meta.get("areas") or []
    if not period and not areas:
        return
    print("\nPropuestas de este profile — se confirman con el usuario, no se aplican:")
    if period:
        print(f"  period_format: {period}"
              "   -> cerebro/schema.json, una vez confirmado")
    if areas:
        print(f"  areas:         {', '.join(areas)}")
        print("                 -> renombrarlas antes de crearlas: un área es de la "
              "organización,\n                    no del rol")
