# Changelog del kernel

Historial de versiones del sistema. `/x-actualizar-sistema` muestra las entradas nuevas al
actualizar; si una versión requiere pasos de migración, se listan en su sección **Migración**.

## 2.0.0 — en construcción

Reescritura completa. v1 funcionaba, y su problema era de escala: **el consumo de tokens crecía
conforme crecía el cerebro**. Esta versión ataca la causa, que eran dos cosas distintas con el
mismo síntoma.

**El diagnóstico, en una frase.** `PREGUNTAS-ABIERTAS.md`, `ORGANIGRAMA.md`, `GOALS.md` y cada
`index.md` crecen con el cerebro, y v1 le pedía al modelo **regenerarlos a mano** en cada
ingesta. El detalle que lo delata: esos archivos se auto-declaraban *«Autogenerado. No editar a
mano»* — **y en v1 no existía ningún generador.** El vocabulario del sistema ya asumía la capa
que faltaba.

### El contrato: una fuente, y todo lo demás se genera

- **`kernel/schema/contract.json`** declara los **14 tipos** con sus campos, enums,
  condicionales, ubicaciones y mínimos de clasificación. En v1 el catálogo vivía en tres sitios
  a la vez y los enums estaban en comentarios YAML dentro de las plantillas.
- De ahí salen, **generadas**: las plantillas por tipo, los JSON Schema, el `ESQUEMA.md`
  portable del cerebro, los índices de cada carpeta, los índices derivados y los stubs de
  ambas herramientas. Añadir un valor de enum es una línea; en v1 era un grep sobre 15 archivos
  de prosa que rompía tres skills en silencio.
- **`Playbook` se escindió en dos:** un `Playbook` se **sigue** (proceso reutilizable), un
  `Analisis` se **consulta** (estudio archivado). El contrato de v1 lo decía sin querer — su
  descripción rezaba *«a reusable process, OR an archived analysis»*.
- **`Indice`** entra como tipo: OKF exige frontmatter tipado en todo `.md` no reservado, así
  que un derivado como `PREGUNTAS-ABIERTAS.md` necesita uno para ser conformante.

### La capa determinista: `kernel/bin/brain.py`

Nunca llama a un modelo, no tiene dependencias (stdlib pura, **Python 3.11+**) y es
idempotente. Diez subcomandos; los que cambian el día a día:

- **`init`** — materializa un cerebro: estructura, esquema portable, índices y derivados. El
  starter ya no versiona un `cerebro/` con TODOs: llega vacío y esto lo construye.
- **`validate`** — 20 comprobaciones en dos niveles (OKF / perfil), porque OKF es
  deliberadamente permisivo y un validador estricto sobre él no sería conformante.
  **`--fix`** repara lo mecánico *preservando el significado, y verificándolo*: reparsea cada
  línea de frontmatter antes de escribirla, y nunca reescribe lo que redactó una persona.
- **`index` / `derive`** — la Pendiente A a cero. Lo que el modelo reescribía en cada ingesta
  ahora cuesta cero tokens.
- **`place`** — dónde va un documento, desde la misma declaración que lo valida. Saca del skill
  la prosa sobre destinos, que en v1 estaba repartida entre tres módulos.
- **`template`** — la plantilla de un tipo, unos 200 tokens frente a los ~10.000 de leer el
  contrato.

### Gobierno de datos

v1 tenía **más** reglas de gobierno que v2 —todas en prosa dentro de `AGENTS.md`— y ninguna
aplicaba nada.

- **Clasificación** en cuatro niveles con **mínimo por tipo**. La ausencia es un aviso mientras
  el corpus migra; **estar por debajo del mínimo es siempre un error**.
- **Responsabilidad**: `dueño`, `responsable` y `fuente` aceptan enlace a ficha `Persona` —que
  se verifica— o texto libre, que se tolera y se reporta. La propiedad se vuelve consultable de
  forma progresiva, en vez de tras un muro de errores.
- **Confianza**: `generated` frente a `verified`, con prefijos de actor, hace que *«esto lo
  escribió un agente y nadie lo revisó»* sea una propiedad consultable.
- **Aplicación**: pre-commit sobre lo que cambia, CI sobre el bundle completo. Un hook que
  falle sobre 10.000 documentos heredados se desactiva el primer día.

### Frontmatter que abre en el visor

Usuarios de v1 reportaron que Obsidian y VS Code fallaban con *«mapping values are not allowed
here»*, y el starter era la fuente: un escalar con `: ` sin entrecomillar no es YAML válido, y
nuestro parser lo aceptaba en silencio. Ahora **V18** lo detecta sobre las líneas crudas,
`--fix` entrecomilla lo que puede verificando que el valor no cambie, y las reglas de escritura
están declaradas en el contrato.

### `GOALS.md` deja de escribirse a mano

Era un `Playbook` cuyos tres bloques el modelo reescribía en cada `/x-nueva-iniciativa` y en
cada `/x-actualizacion-semanal`. No hacía falta un tipo nuevo: `Iniciativa.origen` ya era un
enum de exactamente esos tres bloques. Ahora es un derivado que se genera solo, y una
iniciativa sale del listado al moverse a `04-archivo/`.

### Insumos binarios sin `pip`

`to-markdown.py` se reescribió en **stdlib pura**. Los formatos de Office son ZIP + XML y
`.drawio` es XML: nada de eso necesitaba una dependencia. v1 pasaba por `markitdown` dentro de
un `.venv` hermano, que en un entorno con `pip` restringido convierte el conversor en el eslabón
que no se puede instalar. **El `.pdf` es la única excepción**, y degrada con aviso en vez de
fallar. Desaparecen el `.venv`, el `requirements.txt` y el re-exec.

### El setup deja de ser una entrevista de 30 minutos

- **Profiles de rol.** `/x-setup` ofrece elegir un rol —`ingeniero-de-sistemas`,
  `arquitecto-de-tecnologia`, `manager-de-ingenieria`— y ajustarlo: **~5 minutos** en vez de las
  6 rondas y 23 preguntas de v1. El profile trae escrito lo que es cierto del *rol*; solo se
  pregunta lo que nadie puede saber por ti.
- **Un profile propone, nunca afirma.** No siembra `Lineamiento`s ni `Sistema`s: un lineamiento
  es un estándar real de una organización, e inventarlo sería fabricar. Las carpetas de área se
  proponen, y se renombran antes de crearse.
- **Extensible sin código:** `./brain profiles` lista los del kernel
  (`kernel/scaffold/profiles/`) y los tuyos (`plugins/profiles/`), que **ganan ante el mismo
  slug**. Añadir un rol es dejar caer un archivo.
- Personas, objetivos y tipos propios ya no se preguntan en el setup: los crean
  `/x-procesar-inbox`, `/x-nueva-iniciativa` y `/x-crear-plantilla` cuando aparecen.

### `./brain`: un lanzador, porque `python3` no es portable

- **No existe un nombre de intérprete que funcione en Windows, macOS y Linux.** En Windows el
  instalador de python.org no crea `python3.exe`, y Windows 10+ trae un alias con ese nombre que
  **abre la Microsoft Store en vez de fallar**. En macOS el que falta es `python`.
- El repositorio trae `brain` (sh) y `brain.cmd` (cmd/PowerShell), que prueban `py -3`,
  `python3` y `python` en ese orden. Toda la documentación y los módulos usan `./brain`.
- Corre también los demás scripts: `./brain kernel/bin/to-markdown.py <archivo>`.

### Migración desde un cerebro v1

Los cerebros de v1 **no son conformes al perfil de v2** hasta migrarlos, pero siguen siendo
OKF-válidos y legibles. El camino:

1. **Copia tu `cerebro/`, `raw/` y `plugins/`** a un clon del starter v2.
2. **`./brain init cerebro`** — crea lo que falte sin tocar lo que exista.
   Nunca sobrescribe un archivo que ya está.
3. **`./brain validate cerebro`** — el informe de qué falta. Espera muchos hallazgos la primera
   vez: la capa OKF v0.2 (`classification`, `generated`, `sources`, `status`) no existe en
   ningún documento de v1.
4. **`validate --fix`** — resuelve lo mecánico: índices, derivados y entrecomillado.
5. **Lo que queda pide criterio**, y es sobre todo `classification`: es una decisión de
   gobierno por documento y **no se puede autocompletar**. Por eso su ausencia es aviso y no
   error mientras `profile_version` sea 1.
6. **Los `Playbook` hay que triarlos a mano** para separar los `Analisis`. No es automatizable:
   decidir cuál es cuál exige leerlos.

`timestamp`, el campo de v1 que OKF v0.2 reemplaza por `generated.at`, queda declarado como
obsoleto y auto-migrable.
