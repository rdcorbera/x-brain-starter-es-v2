# X-Brain v2

Base de conocimiento personal de trabajo, mantenida por agentes de IA — para **cualquier rol, en cualquier organización**. Tú aportas las fuentes (reuniones, documentos, lo que averiguas en el día) y haces las preguntas; los agentes clasifican, integran, cruzan referencias, detectan contradicciones y mantienen todo al día.

> **Estado: en construcción.** Reescritura desde cero de [x-brain-starter-es](https://github.com/rdcorbera/x-brain-starter-es) (kernel 1.3.0). Este repositorio es el **starter**: nunca contiene conocimiento. El conocimiento vive en el repositorio de cada usuario, en su máquina.

---

## Por qué una v2

v1 está en producción y funciona. Su problema es de escala: **el consumo de tokens crece conforme crece el cerebro**. En un cerebro de más de 10.000 documentos, eso deja de ser una molestia y pasa a ser el techo del sistema.

La pendiente tiene dos componentes, con causas y remedios distintos:

| | Qué pasa | Remedio |
|---|---|---|
| **Pendiente A** | `PREGUNTAS-ABIERTAS.md`, `ORGANIGRAMA.md`, `GOALS.md` y cada `index.md` crecen con el cerebro, y v1 le pide al modelo **regenerarlos a mano** en cada ingesta — leer entero, reescribir entero. Ocho sitios del kernel lo ordenan; cuatro skills además los cargan completos en cada corrida | Generación determinista → **cero tokens** |
| **Pendiente B** | Encontrar los documentos relevantes o afectados entre N navegando índices | Proyección consultable (SQLite) → un `SELECT` en vez de leer índices |

El detalle que lo delata: esos tres archivos se auto-declaran *"Autogenerado. No editar a mano"* — **y en v1 no existe ningún generador.** El vocabulario del sistema ya asumía la capa que faltaba.

Ninguno de los dos remedios se podía construir sobre el contrato de v1, porque **no existía como artefacto**: cero archivos de configuración, `okf.md` sin un solo campo especificado, las plantillas como especificación de facto con los enums en comentarios YAML, y el catálogo duplicado en tres sitios. No se puede generar ni proyectar lo que no está declarado.

De ahí el orden del trabajo: **el contrato primero, porque es la dependencia bloqueante de ambos remedios.**

## Lo que se hereda (probado en v1)

| Concepto | Qué aporta |
|---|---|
| **PARA** | Estructura temporal: proyectos, áreas, recursos, archivo |
| **OKF** | Markdown + frontmatter tipado, `index.md` por carpeta, `log.md` por alcance, enlaces bundle-relativos, `# Citations`. **v2 sube a [OKF v0.2](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md)** |
| **LLM Wiki** | Integrar, no archivar: cada ingesta actualiza todas las páginas afectadas y señala contradicciones |
| **Fuentes crudas inmutables** | Todo original queda en `raw/` con su manifiesto → el cerebro es reconstruible |
| **Zonas de propiedad** | Dueño único por carpeta: el sistema es del starter, el conocimiento es del usuario |
| **Cerebro portable** | La carpeta del conocimiento se explica a sí misma y viaja sola |
| **Nunca fabricar** | Lo que no se sabe es una `Pregunta`, no un supuesto |

## Arquitectura

**Distribución:** repo template, como v1. **Herramientas:** Claude Code y VS Code + Copilot, ambas de primera clase — la lógica vive en markdown neutro invocable desde las dos.

Sobre eso, v2 añade una capa determinista con dos invariantes:

1. **Nunca llama a un LLM.** La extracción ocurre una vez, en la ingesta, con revisión humana. La validación, la generación y (en el corte 2) la proyección ocurren cuantas veces se quiera, gratis, y son reconstruibles.
2. **No tiene dependencias.** Stdlib pura, Python 3.11+, sin `pip install`, en entornos restringidos. El piso lo fija lo que el código necesita —parseo ISO 8601 completo para `stale_after`— y no el intérprete que traiga el sistema; 3.9 y 3.10 además están fuera de soporte. `survey.py` y `sqlite-probe.py`, que son los preflight, se quedan en 3.9 a propósito. **El conversor de insumos también es stdlib pura** — su única excepción es la extracción de PDF, y degrada con aviso. La proyección SQLite del corte 2 va sobre `sqlite3`, que también es stdlib.

```
kernel/schema/contract.json      ← EL CONTRATO. Fuente única.
        │
        ├─ brain generate ─→ kernel/schema/templates/*.md      plantillas por tipo
        │                 ─→ kernel/schema/json/*.schema.json  JSON Schema, para tooling estándar
        │                 ─→ .claude/skills/ y .github/prompts/  ambos árboles de stubs
        │
        ├─ brain init ────→ cerebro/ESQUEMA.md   el esquema legible y portable
        │                 ─→ la estructura PARA del cerebro
        │
        ├─ brain index ───→ cerebro/**/index.md
        ├─ brain derive ──→ PREGUNTAS-ABIERTAS.md, GOALS.md, ORGANIGRAMA.md
        └─ (corte 2) ─────→ el DDL de SQLite
```

Todo lo de la derecha es **generado**: no se edita, se regenera — y **V14 lo comprueba**. Añadir un valor de enum es una línea en `contract.json`; en v1 era un grep manual sobre 15 archivos de prosa que rompía tres skills en silencio.

**`generate` produce los artefactos del kernel; `init` materializa un cerebro.** La separación importa: este starter versiona un `cerebro/` **vacío a propósito** —nunca contiene conocimiento— así que generar no puede escribir dentro de él.

## Gobierno de datos

La política que no se ejecuta no es un control. v1 tenía **más** reglas de gobierno que v2 —todas en prosa dentro de `AGENTS.md`— y ninguna aplicaba nada. v2 tiene menos, pero son ejecutables.

**Clasificación.** Cuatro niveles —`public`, `internal`, `confidential`, `restricted`— y un **mínimo por tipo**. `Persona` no puede bajar de `confidential` porque contiene dato personal, e `Insumo` tampoco porque es material externo cuyo contenido el sistema no controla. La ausencia de clasificación es un aviso mientras el corpus migra; **estar por debajo del mínimo es siempre un error**, y es el único control que no se relaja durante la migración.

**Responsabilidad.** `dueño`, `responsable` y `fuente` son `person-ref`: aceptan un enlace a una ficha `Persona` —que se verifica— o un nombre en texto libre, que se tolera y se reporta hasta resolverse. Así la propiedad se vuelve consultable de forma progresiva en vez de tras un muro de errores.

**Confianza.** `generated` frente a `verified` con prefijos de actor hace que *"esto lo escribió un agente y nadie lo revisó"* sea una propiedad consultable, no una suposición.

**Aplicación.** El pre-commit valida **solo lo que se commitea**; CI valida el bundle completo. Un hook que falle sobre el corpus heredado se desactiva el primer día.

**Frontmatter que abre en el visor.** Un valor con `: ` sin entrecomillar no es YAML válido: Obsidian y VS Code fallan con *«mapping values are not allowed here»*. V18 lo detecta sobre las líneas crudas, `--fix` entrecomilla lo que puede —verificando que el valor no cambie— y el bloque `frontmatter_rules` del contrato declara las reglas para el agente que escribe. Un valor con ` #` queda reportado sin arreglar: YAML ya lo trata como comentario, y entrecomillarlo resucitaría texto que nunca fue parte del valor.

```bash
./brain govern cerebro       # informe de postura de gobierno
./brain hooks --install      # instalar el pre-commit
```

No hay política de retención: sin un mecanismo de disposición sería decoración. Va con el archivado, en un corte posterior.

## Uso de la capa determinista

**Dónde va cada documento.** El contrato declara la ubicación de cada tipo con campos nombrados (`01-proyectos/{proyecto}/01-reuniones/`), así que `brain place` responde el destino y `/x-procesar-inbox` deja de decidirlo desde prosa. La misma declaración valida (V19) documentos ya escritos. Si aplican varios patrones, la herramienta devuelve los candidatos y decide el agente: quita la prosa, no el juicio.

```bash
./brain place Reunion proyecto=2026-q3-erp
#  -> 01-proyectos/2026-q3-erp/01-reuniones/{fecha}-{tema}.md
```

> Todo va por `./brain`, el lanzador de la raíz (`brain.cmd` en PowerShell). **No existe un
> nombre de intérprete que funcione en Windows, macOS y Linux a la vez**: en Windows `python3`
> no lo crea el instalador y su alias abre la Microsoft Store. El lanzador prueba `py -3`,
> `python3` y `python`, así que la resolución ocurre una vez y no como regla a recordar.

```bash
./brain profiles            # los profiles de rol disponibles
./brain init cerebro         # materializar (o poner al día) un cerebro
./brain init cerebro --profile <slug>   # sembrando PERFIL.md con un rol
./brain validate cerebro     # validar (dos niveles: OKF / perfil)
./brain validate --fix       # arreglar solo lo mecánico
./brain validate --staged    # solo lo que se commitea
./brain template Reunion     # imprimir una plantilla
./brain index                # regenerar los index.md
./brain derive               # regenerar los índices derivados
./brain generate             # regenerar los artefactos del kernel

./brain kernel/bin/to-markdown.py <archivo>     # insumo binario → markdown, sin dependencias
./brain kernel/bin/survey.py cerebro           # medir dónde se van los tokens
./brain kernel/bin/sqlite-probe.py .           # ¿puede esta máquina alojar la proyección?
./brain kernel/tests/test_roundtrip.py         # generador y validador se comprueban entre sí
```

### Insumos binarios sin `pip`

El inbox recibe `.pdf`, `.docx`, `.pptx`, `.xlsx`, `.drawio`, `.html` y `.yaml`, y ningún agente abre un binario: lo convierte y lee el `.md`. **`to-markdown.py` es stdlib pura** — los formatos de Office son ZIP + XML y `.drawio` es XML, así que nada de eso necesitaba una dependencia. v1 pasaba por `markitdown` dentro de un `.venv` hermano, que en un entorno con `pip` restringido convierte el conversor en el eslabón que no se puede instalar.

**El `.pdf` es la única excepción** y degrada con aviso en vez de fallar: un PDF es un contenedor binario con flujos comprimidos, y sacar texto de ahí sin librería no es razonable. Lo que emite el conversor es un `Insumo` que ya valida contra el contrato, con su `generated: {by: process:to-markdown}` — así «esto lo produjo un script y nadie lo ha revisado» es consultable.

### Los dos preflight

`survey.py` y `sqlite-probe.py` son distintos del resto: **su piso es Python 3.9, no 3.11**, porque corren en la máquina de destino *antes* de que se instale nada. Un preflight que depende de sus propios hallazgos no es un preflight. Los dos son de solo lectura y no extraen contenido de documentos.

**`survey.py`** mide **dónde se van los tokens**: cuánto cuesta regenerar los índices derivados en cada ingesta frente a cuánto cuesta navegarlos en cada consulta. Reporta formas y conteos, así que su salida se puede compartir desde un entorno restringido. Sirve para decidir en qué orden atacar el problema, y para saber **cuándo toca el corte 2**: el disparador es su veredicto, o pasar de ~2.000 documentos.

**`sqlite-probe.py`** responde si una máquina puede alojar la proyección del corte 2, y son tres preguntas, no una:

| | |
|---|---|
| Qué SQLite hay | En Windows, Python empaqueta su propio `sqlite3.dll`, así que la versión la fija el intérprete y no el sistema |
| Qué capacidades están compiladas | FTS5 es una **bandera de compilación, no una versión**: puede faltar en un SQLite reciente. Solo las CTE recursivas son bloqueantes |
| Si la ruta elegida sirve | Tipo de unidad, detección de carpeta sincronizada, y **modo WAL como prueba decisiva** |

Ese último punto es el que más veces se pasa por alto: **una carpeta sincronizada (OneDrive, Dropbox) o una unidad de red corrompen la base**, porque el cliente reescribe el archivo por debajo del proceso que lo tiene abierto. Y no basta con mirar si el disco es local: dentro de OneDrive, el disco *es* local y WAL activa sin problema. Solo lo detecta la comprobación explícita de sincronización. Sale con código 1 si la ruta no sirve, así que vale como paso de instalación.

Ninguno escribe en el cerebro. La sonda crea una base de prueba en un directorio temporal bajo la ruta indicada y lo borra; y ninguna de las dos emite la ruta en su salida.

### Dos niveles de validación

OKF v0.2 es deliberadamente permisivo — *"consumers MUST tolerate broken links"*, *"MUST NOT reject a concept for missing any optional family"*. Un validador estricto sobre eso no sería conformante. Por eso hay dos niveles:

| Nivel | Qué exige |
|---|---|
| **OKF** | Frontmatter parseable · `type` no vacío · estructura de `index.md`/`log.md` |
| **Perfil** | Campos requeridos por tipo, enums, secciones, condicionales |

Un `cerebro/` compartido sigue siendo OKF-válido aunque no cumpla nuestro perfil. Los enlaces rotos son informativos, nunca errores: marcan conocimiento aún no escrito.

## Estado

**Hecho** — corte 1: el contrato con 14 tipos, el validador de 20 checks, la capa de gobierno de datos (clasificación, responsabilidad, aplicación en pre-commit y CI), el enrutamiento (`brain place`), la generación de plantillas, JSON Schemas, esquema portable, índices y derivados, `brain init`, el conversor de insumos sin dependencias, el test de round-trip y los dos preflight. **Y la prosa del kernel** — `AGENTS.md`, la guía de uso, la instalación y el changelog—, escrita al final y contra un inventario regla por regla de v1: cada regla que desapareció nombra el comando que la sustituye.

**Siguiente** — corte 1: los skills reescritos para invocar `brain.py`, y la migración del cerebro en producción.

**Corte 2**: la proyección SQLite contra la Pendiente B. Su DDL se genera desde el mismo contrato, así que nada del corte 1 se desecha.

## Documentación

| | |
|---|---|
| [INSTALL.md](INSTALL.md) | Instalar, de cero a un cerebro que funciona |
| [kernel/GUIA-DE-USO.md](kernel/GUIA-DE-USO.md) | Operarlo día a día |
| [kernel/AGENTS.md](kernel/AGENTS.md) | Las reglas que siguen los agentes |
| [kernel/CHANGELOG.md](kernel/CHANGELOG.md) | Qué cambió en cada versión, y cómo migrar |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Cómo se **construye** este sistema — reglas de trabajo e invariantes |
