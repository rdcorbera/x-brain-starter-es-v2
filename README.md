# X-Brain v2

Base de conocimiento personal de trabajo, mantenida por agentes de IA — para **cualquier rol, en cualquier organización**. Tú aportas las fuentes (reuniones, documentos, lo que averiguas en el día) y haces las preguntas; los agentes clasifican, integran, cruzan referencias, detectan contradicciones y mantienen todo al día.

> **Estado: en construcción.** Reescritura desde cero de [x-brain-starter-es](https://github.com/rdcorbera/x-brain-starter-es) (kernel 1.3.0). Este repositorio es el **starter**: nunca contiene conocimiento. El conocimiento vive en el repositorio de cada usuario, en su máquina.

---

## Por qué una v2

v1 está en producción y funciona. Su problema es de escala: **el consumo de tokens crece conforme crece el cerebro**. En un cerebro de más de 10.000 documentos, eso deja de ser una molestia y pasa a ser el techo del sistema.

La pendiente tiene dos componentes, con causas y remedios distintos:

| | Qué pasa | Remedio |
|---|---|---|
| **Pendiente A** | `PREGUNTAS-ABIERTAS.md`, `ORGANIGRAMA.md` y cada `index.md` crecen con el cerebro, y v1 le pide al modelo **regenerarlos a mano** en cada ingesta — leer entero, reescribir entero. Ocho sitios del kernel lo ordenan; cuatro skills además los cargan completos en cada corrida | Generación determinista → **cero tokens** |
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
2. **No tiene dependencias.** Stdlib pura, Python 3.11+, sin `pip install`, en entornos restringidos. El piso lo fija lo que el código necesita —parseo ISO 8601 completo para `stale_after`— y no el intérprete que traiga el sistema; 3.9 y 3.10 además están fuera de soporte. `survey.py`, que es el preflight, se queda en 3.9 a propósito. El conversor de binarios y la proyección SQLite del corte 2 son capas opcionales; esto no.

```
kernel/schema/contract.json      ← EL CONTRATO. Fuente única.
        │
        ├─→ kernel/schema/templates/*.md      plantillas por tipo
        ├─→ kernel/schema/json/*.schema.json  JSON Schema, para tooling estándar
        ├─→ cerebro/ESQUEMA.md                el esquema legible y portable
        ├─→ .claude/skills/ y .github/prompts/  ambos árboles de stubs
        ├─→ cerebro/index.md, PREGUNTAS-ABIERTAS.md, ORGANIGRAMA.md
        └─→ (corte 2) el DDL de SQLite
```

Todo lo de la derecha es **generado**: no se edita, se regenera. Añadir un valor de enum es una línea en `contract.json`; en v1 era un grep manual sobre 15 archivos de prosa que rompía tres skills en silencio.

## Gobierno de datos

La política que no se ejecuta no es un control. v1 tenía **más** reglas de gobierno que v2 —todas en prosa dentro de `AGENTS.md`— y ninguna aplicaba nada. v2 tiene menos, pero son ejecutables.

**Clasificación.** Cuatro niveles —`publico`, `interno`, `confidencial`, `restringido`— y un **mínimo por tipo**. `Persona` no puede bajar de `confidencial` porque contiene dato personal, e `Insumo` tampoco porque es material externo cuyo contenido el sistema no controla. La ausencia de clasificación es un aviso mientras el corpus migra; **estar por debajo del mínimo es siempre un error**, y es el único control que no se relaja durante la migración.

**Responsabilidad.** `dueño`, `responsable` y `fuente` son `person-ref`: aceptan un enlace a una ficha `Persona` —que se verifica— o un nombre en texto libre, que se tolera y se reporta hasta resolverse. Así la propiedad se vuelve consultable de forma progresiva en vez de tras un muro de errores.

**Confianza.** `generated` frente a `verified` con prefijos de actor hace que *"esto lo escribió un agente y nadie lo revisó"* sea una propiedad consultable, no una suposición.

**Aplicación.** El pre-commit valida **solo lo que se commitea**; CI valida el bundle completo. Un hook que falle sobre el corpus heredado se desactiva el primer día.

**Frontmatter que abre en el visor.** Un valor con `: ` sin entrecomillar no es YAML válido: Obsidian y VS Code fallan con *«mapping values are not allowed here»*. V18 lo detecta sobre las líneas crudas, `--fix` entrecomilla lo que puede —verificando que el valor no cambie— y el bloque `frontmatter_rules` del contrato declara las reglas para el agente que escribe. Un valor con ` #` queda reportado sin arreglar: YAML ya lo trata como comentario, y entrecomillarlo resucitaría texto que nunca fue parte del valor.

```bash
python3 kernel/bin/brain.py govern cerebro       # informe de postura de gobierno
python3 kernel/bin/brain.py hooks --install      # instalar el pre-commit
```

No hay política de retención: sin un mecanismo de disposición sería decoración. Va con el archivado, en un corte posterior.

## Uso de la capa determinista

**Dónde va cada documento.** El contrato declara la ubicación de cada tipo con campos nombrados (`01-proyectos/{proyecto}/01-reuniones/`), así que `brain place` responde el destino y `/x-procesar-inbox` deja de decidirlo desde prosa. La misma declaración valida (V19) documentos ya escritos. Si aplican varios patrones, la herramienta devuelve los candidatos y decide el agente: quita la prosa, no el juicio.

```bash
python3 kernel/bin/brain.py place Reunion proyecto=2026-q3-erp
#  -> 01-proyectos/2026-q3-erp/01-reuniones/{fecha}-{tema}.md
```

```bash
python3 kernel/bin/brain.py validate cerebro     # validar (dos niveles: OKF / perfil)
python3 kernel/bin/brain.py validate --fix       # arreglar solo lo mecánico
python3 kernel/bin/brain.py validate --staged    # solo lo que se commitea
python3 kernel/bin/brain.py template Reunion     # imprimir una plantilla
python3 kernel/bin/brain.py index                # regenerar los index.md
python3 kernel/bin/brain.py derive               # regenerar los índices derivados
python3 kernel/bin/brain.py generate             # regenerar todos los artefactos

python3 kernel/bin/survey.py cerebro           # medir dónde se van los tokens
python3 kernel/bin/sqlite-probe.py .           # ¿puede esta máquina alojar la proyección?
python3 kernel/tests/test_roundtrip.py         # generador y validador se comprueban entre sí
```

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

**Hecho** — corte 1, en curso: el contrato con 13 tipos, el validador de 20 checks, la capa de gobierno de datos (clasificación, responsabilidad, aplicación en pre-commit y CI), el enrutamiento (`brain place`), la generación de plantillas, JSON Schemas, esquema portable, índices y derivados, el test de round-trip y el script de medición.

**Siguiente** — corte 1: la prosa del kernel (que se escribe *al final*, porque solo se puede borrar una regla cuando ya existe el código que la sustituye), los skills reescritos para invocar `brain.py`, y la migración del cerebro en producción.

**Corte 2**: la proyección SQLite contra la Pendiente B. Su DDL se genera desde el mismo contrato, así que nada del corte 1 se desecha.

## Cómo trabajamos en este repo

Las reglas, convenciones y la bitácora de decisiones están en [CLAUDE.md](CLAUDE.md).
