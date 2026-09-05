#!/usr/bin/env python3
"""okf -- the deterministic layer of X-Brain.

Validates a knowledge bundle against the contract, and generates every artifact
the contract can produce: templates, JSON Schemas, the catalog, the portable
schema, directory indexes, derived indexes and skill stubs.

Two invariants govern this file:

  1. It NEVER calls an LLM. Everything here is deterministic and idempotent,
     so it can run in CI, on a hook, or a hundred times in a row.
  2. It has NO dependencies. Standard library only, Python 3.11+, so it runs
     with a stock interpreter in a locked-down environment. The binary
     converter and the cut-2 SQLite projection are optional layers; this is not.

Usage:
    brain.py validate [PATH] [--fix] [--json] [--full]
    brain.py template TYPE
    brain.py index [PATH]
    brain.py derive
    brain.py stubs
    brain.py generate
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# La librería vive junto a este archivo, no instalada: el sistema tiene que
# funcionar donde `pip` está restringido. Ejecutado como script, sys.path[0] ya
# sería este directorio; se inserta igualmente porque las pruebas lo cargan con
# importlib, y ahí no lo es.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from brainlib import *                                            # noqa: F403,E402
from brainlib import generate, parse, report, validate            # noqa: F401,E402


def pre_commit_script() -> str:
    """The hook Git runs, with the interpreter resolved at install time.

    `python3` is not a safe assumption on Windows: the launcher is `py`, and a
    bare `python3` can reach the Microsoft Store stub instead of an
    interpreter. `sys.executable` is whatever ran the install; `as_posix`
    keeps Git for Windows's sh from reading a Windows path's backslashes as
    escapes,
    and the quotes survive a path with spaces (`C:/Program Files/...`).
    """
    return (
        "#!/bin/sh\n"
        "# Installed by `brain.py hooks --install`. Validates only what is being\n"
        "# committed: a hook that fails on the inherited corpus gets disabled on\n"
        "# day one.\n"
        f'exec "{Path(sys.executable).as_posix()}" kernel/bin/brain.py validate --staged\n'
    )


def staged_paths(bundle: Path) -> set:
    """Bundle-relative paths of the .md files staged for commit."""
    import subprocess
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
            capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        raise SystemExit("error: no se pudo consultar el índice de git")
    out = set()
    for line in result.stdout.split("\n"):
        if not line.endswith(".md"):
            continue
        try:
            out.add(Path(line).resolve().relative_to(bundle.resolve()).as_posix())
        except ValueError:
            continue                    # outside the bundle; not our business
    return out


def cmd_validate(args) -> int:
    bundle = Path(args.path)
    require_bundle(bundle)
    if is_uninitialised(bundle) and not args.staged:
        print(f"\nbrain validate {bundle}: cerebro sin inicializar.\n"
              f"       Córrelo con `brain.py init {bundle}` y vuelve a validar.\n")
        return 0
    contract = Contract.load(Path(args.contract), bundle)

    only = staged_paths(bundle) if args.staged else None
    if only is not None and not only:
        print("brain validate --staged: nada del cerebro en el commit.")
        return 0

    validator = Validator(contract, bundle)
    findings = validator.run(only)

    if args.fix:
        changed = apply_fixes(contract, validator, bundle)
        for path in changed:
            print(f"fixed  {path}")
        validator = Validator(contract, bundle)
        findings = validator.run()

    if args.json:
        print(json.dumps([f.as_dict() for f in findings], indent=2, ensure_ascii=False))
    else:
        report(findings, bundle, args.full)
    return 1 if any(f.severity == ERROR for f in findings) else 0


def cmd_govern(args) -> int:
    bundle = Path(args.path)
    require_bundle(bundle)
    contract = Contract.load(Path(args.contract), bundle)
    validator = Validator(contract, bundle)
    validator.run()
    governance_report(contract, validator)
    return 0


def cmd_hooks(args) -> int:
    hook = Path(".git/hooks/pre-commit")
    if not hook.parent.is_dir():
        raise SystemExit("error: no hay un repositorio git aquí")
    if not args.install:
        state = "instalado" if hook.exists() else "no instalado"
        print(f"pre-commit: {state}")
        return 0
    if hook.exists() and PRE_COMMIT_MARKER not in hook.read_text(encoding="utf-8"):
        raise SystemExit(
            "error: ya existe un pre-commit distinto. Revísalo y compón a mano;\n"
            "       sobrescribir el hook de alguien más no es cosa de esta herramienta.")
    # LF without exception: sh fails on a CRLF shebang (`bad interpreter`).
    write_text_lf(hook, pre_commit_script())
    hook.chmod(0o755)
    print(f"instalado {hook} -- valida solo lo que se commitea")
    return 0


def cmd_place(args) -> int:
    contract = Contract.load(Path(args.contract), Path(args.bundle))
    if args.type not in contract.types:
        raise SystemExit(f"error: tipo `{args.type}` no está en el contrato")

    values: Dict[str, Any] = {}
    for pair in args.field:
        if "=" not in pair:
            raise SystemExit(f"error: `{pair}` no es campo=valor")
        key, _, val = pair.partition("=")
        values[key.strip()] = val.strip()
    for name, spec in contract.fields_for(args.type).items():
        values.setdefault(name, spec.get("default"))

    paths, notes = resolve_locations(contract, args.type, values)
    filename = contract.types[args.type].get("filename")

    if len(paths) == 1:
        print(paths[0] + (filename or ""))
    elif paths:
        print("varios destinos posibles; elige tú:")
        for path in paths:
            print(f"  {path}{filename or ''}")
    else:
        print(f"no se pudo resolver el destino de {args.type}.")
    for note in notes:
        print(f"  nota: {note}")
    if filename and len(paths) != 1:
        print(f"  nombre de archivo: {filename}")
    return 0 if len(paths) == 1 else 1


def cmd_template(args) -> int:
    contract = Contract.load(Path(args.contract), Path(args.bundle))
    sys.stdout.write(render_template(contract, args.type))
    return 0


def cmd_profiles(args) -> int:
    """The roles on offer, so /x-setup lists them instead of inventing them."""
    # `--contract` is relative to the working directory, so a wrong one has to
    # be an error: without this, running from outside the repo reported "no
    # profiles" -- a wrong answer, which is worse than a failure.
    if not Path(args.contract).is_file():
        raise SystemExit(f"error: no encuentro el contrato en `{args.contract}`. "
                         "Se corre desde la raíz del repositorio.")
    kernel = Path(args.contract).parent.parent
    profiles = find_profiles(kernel)
    if not profiles:
        print("no hay profiles. El kernel los trae en kernel/scaffold/profiles/, "
              "y los tuyos van en plugins/profiles/.")
        return 0
    width = max(len(s) for s in profiles)
    for slug in sorted(profiles):
        meta = profiles[slug]["meta"]
        print(f"  {slug:<{width}}  {meta.get('kind', '?'):<10} "
              f"{profiles[slug]['origin']:<7}  {meta.get('title', '')}")
        if meta.get("description"):
            print(f"  {'':<{width}}  {meta['description']}")
    print("\nSe aplican con `./brain init cerebro --profile <slug>`.")
    return 0


def cmd_index(args) -> int:
    bundle = Path(args.path)
    contract = Contract.load(Path(args.contract), bundle)
    validator = Validator(contract, bundle)
    validator.collect()
    for directory, content in build_indexes(contract, validator.docs, bundle).items():
        if write_if_changed(directory / "index.md", content):
            print(f"wrote  {(directory / 'index.md').relative_to(bundle)}")
    return 0


def cmd_derive(args) -> int:
    bundle = Path(args.path)
    contract = Contract.load(Path(args.contract), bundle)
    validator = Validator(contract, bundle)
    validator.collect()
    for name, body in build_derived(contract, validator.docs).items():
        path = bundle / name
        if not derived_is_current(path, body):
            write_if_changed(path, compose_derived(contract, name, body))
            print(f"wrote  {name}")
    return 0


def cmd_stubs(args) -> int:
    stubs = build_stubs(Path(args.contract).parent.parent)
    if not stubs:
        print("no hay módulos con frontmatter `skill:` todavía")
        return 0
    for rel, content in sorted(stubs.items()):
        if write_if_changed(Path(rel), content):
            print(f"wrote  {rel}")
    return 0


def cmd_generate(args) -> int:
    contract_path = Path(args.contract)
    kernel = contract_path.parent.parent
    contract = Contract.load(contract_path, Path(args.bundle))

    for type_name in contract.types:
        if contract.types[type_name].get("generated_only"):
            continue          # never hand-written: a template would be a lie
        template = render_template(contract, type_name)
        if write_if_changed(kernel / "schema" / "templates" / f"{type_name.lower()}.md",
                            GENERATED_MARK + "\n" + template):
            print(f"wrote  kernel/schema/templates/{type_name.lower()}.md")
        schema = json.dumps(json_schema_for(contract, type_name), indent=2,
                            ensure_ascii=False) + "\n"
        if write_if_changed(kernel / "schema" / "json" / f"{type_name.lower()}.schema.json",
                            schema):
            print(f"wrote  kernel/schema/json/{type_name.lower()}.schema.json")

    # The bundle is NOT written here. `generate` produces the kernel's own
    # artifacts -- what CI checks is up to date -- while materialising a brain
    # is an act of setup and belongs to `init`. Mixing them meant the starter,
    # which ships an empty cerebro/ by design, grew an ESQUEMA.md on every run.
    cmd_stubs(args)
    return 0


def cmd_init(args) -> int:
    """Materialise a brain: the deterministic half of the setup.

    Everything here is derivable from the contract, so it costs zero tokens and
    is safe to re-run -- after a kernel update it is how ESQUEMA.md and the
    derived indexes catch up. What it deliberately does NOT do is fill anything
    in: the interview is /x-setup's job. Structure is mechanical, context is not.
    """
    bundle = Path(args.path)
    contract = Contract.load(Path(args.contract), bundle)
    kernel = Path(args.contract).parent.parent
    wrote = 0

    bundle.mkdir(parents=True, exist_ok=True)
    # The PARA folders come from the same block that documents them in
    # ESQUEMA.md, so the tree and its explanation cannot drift apart. A .gitkeep
    # each, because git does not track an empty directory and the skeleton is
    # the part a new brain most needs to survive its first clone.
    for rel in contract.data.get("bundle_schema", {}).get("structure", {}):
        (bundle / rel).mkdir(parents=True, exist_ok=True)
        keep = bundle / rel / ".gitkeep"
        if not keep.exists():
            write_text_lf(keep, "")
    # personas/ is named by the organigrama's own declared path, so the folder
    # the derived file needs exists before anything tries to write into it.
    for name in contract.derived:
        parent = (bundle / name).parent
        if parent != bundle:
            parent.mkdir(parents=True, exist_ok=True)

    # A role profile is just another scaffold PERFIL.md: same six headings, with
    # the part the ROLE determines already written and only the part no profile
    # can know left as a TODO. So applying one is choosing which mould to copy,
    # which is work this loop already does -- not a new job.
    profile = None
    if getattr(args, "profile", None):
        profiles = find_profiles(kernel)
        profile = profiles.get(args.profile)
        if profile is None:
            known = ", ".join(f"`{s}`" for s in sorted(profiles)) or "ninguno"
            raise SystemExit(
                f"error: no existe el profile `{args.profile}`. Disponibles: {known}.\n"
                "       Se listan con `brain.py profiles`.")

    for source in sorted((kernel / "scaffold").glob("*.md")):
        target = bundle / source.name
        if target.exists():
            continue          # never overwrite what a person filled in
        text = source.read_text(encoding="utf-8")
        if profile is not None and source.name == "PERFIL.md":
            text = frontmatter_block(text) + "\n" + profile["body"]
        write_if_changed(target, text)
        print(f"wrote  {source.name}" +
              (f"  (profile {args.profile})"
               if profile is not None and source.name == "PERFIL.md" else ""))
        wrote += 1

    if write_bundle_schema(contract, bundle):
        print(f"wrote  {contract.data.get('bundle_schema', {}).get('path')}")
        wrote += 1

    validator = Validator(contract, bundle)
    validator.collect()
    for name, body in build_derived(contract, validator.docs).items():
        if not derived_is_current(bundle / name, body):
            write_if_changed(bundle / name, compose_derived(contract, name, body))
            print(f"wrote  {name}")
            wrote += 1
    # Indexes last: they list the files the steps above just created.
    validator = Validator(contract, bundle)
    validator.collect()
    for directory, content in build_indexes(contract, validator.docs, bundle).items():
        if write_if_changed(directory / "index.md", content):
            print(f"wrote  {(directory / 'index.md').relative_to(bundle)}")
            wrote += 1

    if not wrote:
        print(f"brain init {bundle}: ya estaba al día.")
    # Last, so the proposals are the part still on screen when the skill reads
    # them: everything above is a list of files, and this is the part a person
    # has to answer.
    if profile is not None:
        print_profile_proposals(profile)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="brain.py", description=__doc__.split("\n")[0])
    parser.add_argument("--contract", default=str(DEFAULT_CONTRACT))
    parser.add_argument("--bundle", default=str(DEFAULT_BUNDLE))
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("validate", help="validar el bundle contra el contrato")
    p.add_argument("path", nargs="?", default=str(DEFAULT_BUNDLE))
    p.add_argument("--fix", action="store_true", help="arreglar solo lo mecánico")
    p.add_argument("--staged", action="store_true",
                   help="validar solo los .md en el índice de git (para el pre-commit)")
    p.add_argument("--json", action="store_true")
    p.add_argument("--full", action="store_true", help="listar todos los hallazgos")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("govern", help="informe de postura de gobierno de datos")
    p.add_argument("path", nargs="?", default=str(DEFAULT_BUNDLE))
    p.set_defaults(func=cmd_govern)

    p = sub.add_parser("hooks", help="instalar o consultar el hook de pre-commit")
    p.add_argument("--install", action="store_true")
    p.set_defaults(func=cmd_hooks)

    p = sub.add_parser("place", help="dónde va un documento de este tipo")
    p.add_argument("type")
    p.add_argument("field", nargs="*", help="campo=valor, p.ej. proyecto=2026-q3-erp")
    p.set_defaults(func=cmd_place)

    p = sub.add_parser("template", help="imprimir la plantilla de un tipo")
    p.add_argument("type")
    p.set_defaults(func=cmd_template)

    p = sub.add_parser("profiles", help="listar los profiles de rol disponibles")
    p.set_defaults(func=cmd_profiles)

    p = sub.add_parser("index", help="regenerar los index.md")
    p.add_argument("path", nargs="?", default=str(DEFAULT_BUNDLE))
    p.set_defaults(func=cmd_index)

    p = sub.add_parser("init", help="materializar un cerebro (estructura y derivados)")
    p.add_argument("path", nargs="?", default=str(DEFAULT_BUNDLE))
    p.add_argument("--profile", help="sembrar PERFIL.md con un profile de rol "
                                     "(se listan con `brain.py profiles`)")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("derive", help="regenerar los índices derivados")
    p.add_argument("path", nargs="?", default=str(DEFAULT_BUNDLE))
    p.set_defaults(func=cmd_derive)

    p = sub.add_parser("stubs", help="generar los stubs de ambas herramientas")
    p.set_defaults(func=cmd_stubs)

    p = sub.add_parser("generate", help="regenerar todos los artefactos")
    p.set_defaults(func=cmd_generate)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
