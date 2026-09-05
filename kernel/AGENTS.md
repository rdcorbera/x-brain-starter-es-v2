# X-Brain — instrucciones para agentes (kernel)

Este repositorio es la base de conocimiento personal de trabajo de una persona en su
organización, operada por agentes de IA. Su propósito: documentar lo que ocurre —reuniones,
decisiones, documentos, personas, aprendizajes— y recuperarlo rápido para trabajar mejor y
decidir con contexto completo.

Todo agente que trabaje aquí lee, antes de actuar:

1. **Este archivo** — las reglas del sistema.
2. **`cerebro/PERFIL.md`** — quién es el usuario, cómo trabaja, y sus reglas de comunicación
   y confidencialidad. Lo escribe `/x-setup`; si tiene TODOs pendientes, sugerir correrlo.
3. **`cerebro/ESQUEMA.md`** — el catálogo de tipos vigente de ESTE cerebro, con sus campos.
   **Es un artefacto generado**: no se edita.

---

## Lo primero: mucho de esto ya no hay que hacerlo a mano

X-Brain tiene una **capa determinista** —`kernel/bin/brain.py`— que nunca llama a un modelo,
no tiene dependencias y se puede correr cien veces seguidas. Todo lo que hace, lo hace gratis.

**Los comandos se invocan con `./brain`**, el lanzador de la raíz. No es cosmética: **no existe
un nombre de intérprete que funcione en los tres sistemas.** En Windows el instalador de
python.org no crea `python3.exe`, y Windows 10+ trae un alias con ese nombre que **abre la
Microsoft Store en vez de fallar** — para un agente, peor que un error. En macOS es `python` el
que falta. El lanzador prueba `py -3`, `python3` y `python` en ese orden, así que la resolución
ocurre una vez y de forma determinista en lugar de ser una regla que recordar por sistema.
También corre los demás scripts: `./brain kernel/bin/to-markdown.py <archivo>`.

**La regla que ordena tu trabajo: si hay un comando, se usa el comando.** No porque sea más
elegante, sino porque el modo alternativo —leer una especificación y escribir a mano— cuesta
tokens y se equivoca. `brain template Reunion` cuesta unos 200 tokens; leer el esquema
completo para deducir lo mismo, unos 10.000.

| En vez de… | Ejecuta |
|---|---|
| Deducir qué campos lleva un tipo | `brain.py template <Tipo>` |
| Decidir en qué carpeta va un documento | `brain.py place <Tipo> proyecto=<slug>` |
| Reescribir un `index.md` | `brain.py index` |
| Reescribir `PREGUNTAS-ABIERTAS.md`, `GOALS.md` u `ORGANIGRAMA.md` | `brain.py derive` |
| Revisar a ojo si un documento está bien | `brain.py validate cerebro` |
| Arreglar frontmatter mal entrecomillado, índices y derivados | `brain.py validate --fix` |
| Crear la estructura de un cerebro nuevo | `brain.py init cerebro` |
| Sembrar el `PERFIL.md` de un rol, en vez de entrevistar | `brain.py init cerebro --profile <slug>` |
| Leer un `.pdf`, `.docx`, `.pptx`, `.xlsx` o `.drawio` | `kernel/bin/to-markdown.py <archivo>` |

**Un artefacto generado no se edita: se regenera.** Si algo generado está mal, lo que está mal
es `kernel/schema/contract.json`. Editar la salida es trabajo que se pierde en la siguiente
corrida, y **V14 lo detecta**.

Lo que la herramienta **no** hace es decidir por ti. `brain place` devuelve los candidatos
cuando aplican varios patrones y el juicio sigue siendo tuyo: quita la prosa, no el criterio.

---

## Zonas de propiedad

El sistema sigue el principio abierto/cerrado: **abierto a extensión, cerrado a modificación
del kernel**. Cada carpeta tiene un dueño único.

| Zona | Dueño | Regla |
|---|---|---|
| `kernel/`, `CLAUDE.md`, `README.md`, `.github/`, stubs `x-*` | **El starter (GitHub)** | Nadie la edita localmente. Se actualiza con `/x-actualizar-sistema` |
| `cerebro/` | **El usuario** | Aquí vive TODO el conocimiento. Es portable: se copia entera a otro sistema |
| `raw/` | **El usuario** (escribe solo `/x-procesar-inbox`) | Originales inmutables + `manifiesto.md`. Nunca se edita ni se borra nada |
| `inbox/` | **El usuario** | Puerta de entrada transitoria. Se vacía al procesar |
| `plugins/` | **El usuario** | Skills, plantillas y profiles de rol propios |

- **Nunca escribas en `kernel/` ni en `.github/`.** Si un skill del kernel necesita cambiar, es
  un issue o un PR al starter, no una edición local. Excepciones: `/x-crear-skill` agrega stubs
  nuevos, y `/x-actualizar-sistema` trae cambios del upstream vía git.
- **Lo personalizable vive fuera del kernel:** el contexto en `cerebro/PERFIL.md`, los tipos
  propios en `cerebro/schema.json`, los skills propios en `plugins/skills/`, y los profiles
  de rol propios en `plugins/profiles/`.
- Si el usuario pide modificar el kernel, explícale la regla y ofrécele la alternativa.

> **Esta sección la sostiene la convención, no una comprobación.** Nada impide técnicamente
> escribir en `kernel/`. Se dice claro a propósito: en v1 todas las reglas se presentaban con
> el mismo tono, las verificadas y las que no, y así fue como la prosa acabó siendo portante.

---

## Principios: el patrón LLM Wiki

Este cerebro no es un archivo de notas: es un **wiki que se integra con cada ingesta**. Los
cuatro principios sobreviven escritos porque **son juicio, y ninguna comprobación los
sustituye**.

1. **Integrar, no solo archivar.** Al ingerir una fuente nueva, actualiza todas las páginas
   afectadas —fichas, lineamientos, planes—, no solo crees la nota. Una reunión puede tocar
   diez documentos.
2. **Señalar contradicciones.** Si algo nuevo contradice una página existente, nunca las dejes
   convivir en silencio: dilo. Al resolverse, la versión superada queda anotada como tal, con
   fecha y fuente — no se borra.
3. **Fuentes crudas inmutables, en un solo lugar.** Los originales se conservan siempre en
   `raw/`, como `AAAA-MM-DD-descripcion-uuid.ext`, y registrados en `raw/manifiesto.md`. El
   wiki los cita; jamás los edita ni los reemplaza.
4. **Las respuestas valiosas se archivan.** Una síntesis o un análisis generado al consultar la
   base no muere en el chat: ofrece archivarlo, para que las exploraciones compongan igual que
   las fuentes.

---

## Conformidad OKF v0.2

El bundle OKF de este sistema es la carpeta **`cerebro/`**: los enlaces que empiezan con `/`
se resuelven dentro de ella.

La [especificación real](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md)
es de terceros y no se reproduce aquí. **Qué es del estándar y qué es nuestro lo responde el
bloque `provenance` de `kernel/schema/contract.json`**, con la lista exacta — es lo que se
consulta cuando salga OKF v0.3.

**La conformidad se comprueba, no se recuerda.** `brain.py validate` trabaja en dos niveles:

| Nivel | Qué exige | Por qué separado |
|---|---|---|
| **OKF** | Frontmatter parseable · `type` no vacío · estructura de `index.md`/`log.md` | La spec es deliberadamente permisiva: *«consumers MUST tolerate broken links»*. Un validador estricto sobre ella no sería conformante |
| **Perfil** | Campos requeridos por tipo, enums, secciones, condicionales, ubicación | Es lo nuestro, y puede endurecerse sin romper la conformidad |

Un `cerebro/` compartido sigue siendo OKF-válido aunque no cumpla nuestro perfil. **Un enlace
roto es informativo, nunca un error**: marca conocimiento aún no escrito.

Dos convenciones que sí escribes tú, porque ninguna herramienta las genera:

- **Enlaces bundle-relativos.** Empiezan con `/`, p. ej. `[Ana García](/02-areas/personas/ana-garcia.md)`.
  El prefijo `/raw/...` es un **puntero reservado que apunta FUERA del bundle**; si un cerebro
  se comparte sin sus fuentes, esos enlaces quedan rotos y es aceptable.
- **`# Citations`.** Cuando un documento afirma algo con fuente, lista las fuentes al final,
  numeradas. *Nada lo comprueba todavía* — depende de ti.

Y una que es disciplina pura: **`log.md` por alcance — quien escribe, loguea.** Hay uno global
en `cerebro/` y uno por proyecto, agrupados por fecha con `## AAAA-MM-DD` y lo más reciente
arriba. `brain validate` comprueba que los encabezados sean fechas ISO (V3), pero **nadie
escribe la entrada por ti**: todo skill que cree o modifique archivos termina agregando la suya.

---

## Escribir frontmatter

Nuestro parser es deliberadamente tolerante y **el visor que abre el usuario no lo es**. Un
valor que el validador aceptaba hizo fallar a Obsidian y a VS Code con *«mapping values are not
allowed here»*, y lo reportaron usuarios reales.

Las reglas exactas están en el bloque **`frontmatter_rules.agent_rules_es`** del contrato, en
español y con `enforced_by: V18`. Las dos que más se rompen:

- **Nunca escribas `: ` (dos puntos y espacio) dentro de un valor sin entrecomillar.** Es el
  indicador de clave/valor de YAML y rompe el visor.
- **Nunca escribas ` #` (espacio y almohadilla) dentro de un valor.** YAML lo lee como
  comentario y **borra en silencio todo lo que sigue**. Ni `--fix` puede recuperarlo, porque no
  hay forma de saber si querías un comentario.

Ante la duda, entrecomilla con comillas dobles: entrecomillar de más nunca rompe nada. Y la
prosa larga va en el cuerpo del documento, no en el frontmatter.

---

## Gobierno de datos

La política que no se ejecuta no es un control. Estas son ejecutables.

- **Clasificación.** Cuatro niveles —`public`, `internal`, `confidential`, `restricted`— y un
  **mínimo por tipo**. `Persona` no baja de `confidential` porque contiene dato personal, e
  `Insumo` tampoco porque es material externo cuyo contenido el sistema no controla. La
  *ausencia* de clasificación es un aviso mientras el corpus migra; **estar por debajo del
  mínimo es siempre un error**, y es el único control que no se relaja.
- **Responsabilidad.** `dueño`, `responsable` y `fuente` aceptan un enlace a una ficha
  `Persona` —que se verifica— o un nombre en texto libre, que se tolera y se reporta hasta
  resolverse (V17).
- **Confianza.** `generated` frente a `verified`: que *«esto lo escribió un agente y nadie lo
  revisó»* sea consultable, y no una suposición.

**Lo que ninguna comprobación puede saber va en `cerebro/PERFIL.md`:** qué nombres, qué
sistemas o qué asuntos no entran en este cerebro. Y por encima de todo — **nunca almacenes
credenciales, secretos ni tokens.** Eso no lo detecta nada, ni aquí ni en producción.

---

## Reglas que no sustituye ningún comando

Sobreviven escritas porque nada determinista las cumple. Ninguna es opcional.

- **Nunca fabricar.** Si falta información, se crea un documento `Pregunta`. Jamás se inventa
  una respuesta ni se rellena un hueco con un supuesto. Es la regla central del sistema.
- **Idioma: español** por defecto, configurable en `cerebro/PERFIL.md`.
- **Una sola fuente por pendiente.** Lo que hace falta para entregar un proyecto vive en su
  `PLAN.md`, lo haga quien lo haga; las tablas «Pendientes conmigo» de las fichas `Persona` son
  **espejos con enlace a la fila**, nunca listas independientes. Lo que no se sabe es una
  `Pregunta`, no una tarea. Y toda tarea rastrea a la definición de «entregado» del
  `CONTEXT.md`: si no aporta a eso, sobra.
- **Diagramas siempre como texto** (Mermaid preferido) dentro de markdown. Nunca solo imágenes.
- **Mostrar antes de escribir.** Ante cambios masivos o al editar documentos fuera del alcance
  del skill en ejecución, muestra un resumen y pide confirmación. Ese punto de control existe
  para usarse.
- **No repetir preguntas** cuya respuesta ya está en la base: busca primero.

---

## Insumos binarios

El inbox recibe `.pdf`, `.docx`, `.pptx`, `.xlsx`, `.drawio`, `.html` y `.yaml`. **Ningún
agente abre un binario ni lo interpreta**: lo convierte y lee el `.md` resultante.

```bash
./brain kernel/bin/to-markdown.py <archivo> --project <slug> --source /raw/<original>
```

Leer el binario quema miles de tokens y abre la puerta a inventar; la conversión es
determinista y cuesta cero. Emite un documento `Insumo` (o `Diagrama`, para `.drawio`) que ya
valida contra el contrato.

**No necesita `pip`:** los formatos de Office son ZIP + XML y `.drawio` es XML, así que van con
la biblioteca estándar. **El `.pdf` es la única excepción** — necesita `pdfminer.six`, y si no
está, el script lo dice y propone la alternativa en vez de fallar a medias.

- `.doc`, `.ppt`, `.xls` **no se pueden leer** (binarios anteriores a 2007): abrir en Office y
  «Guardar como» al formato moderno.
- Un `.xlsx` se **muestrea** (50 filas por hoja por defecto, `--filas` para más): una hoja de
  1.500 filas son ~18.800 tokens de ruido, y el original íntegro queda en `raw/`.
- **Los «Avisos de conversión» importan.** Cuando la conversión pierde algo, el markdown lo
  dice arriba. No los ignores ni los borres: son la diferencia entre saber que falta un dato y
  creer que no existe.

---

## Estructura del repositorio

Esto es el **sistema**. La estructura del conocimiento —`01-proyectos/`, `02-areas/`…— la
describe `cerebro/ESQUEMA.md`, que se genera y viaja con el cerebro cuando se comparte.

```
x-brain/
├── CLAUDE.md                     ← carga este archivo + el perfil (kernel)
├── README.md                     ← presentación y puesta en marcha (kernel)
├── INSTALL.md                    ← instalación paso a paso (kernel)
├── .claude/skills/x-*/           ← stubs generados → kernel/modulos/
├── .github/
│   ├── copilot-instructions.md   ← arranque para Copilot
│   ├── prompts/x-*.prompt.md     ← stubs generados, equivalentes
│   └── workflows/validate.yml    ← valida el bundle completo en CI
├── kernel/                       ← EL SISTEMA (solo lectura; se actualiza de GitHub)
│   ├── AGENTS.md                 ← este archivo
│   ├── VERSION · CHANGELOG.md    ← versión del kernel y notas de cada release
│   ├── GUIA-DE-USO.md            ← instructivo de operación
│   ├── bin/
│   │   ├── brain.py              ← la capa determinista: validar, generar, enrutar
│   │   ├── to-markdown.py         ← insumos binarios → markdown (cero tokens)
│   │   ├── survey.py             ← preflight: dónde se van los tokens
│   │   └── sqlite-probe.py       ← preflight: ¿sirve esta ruta para la proyección?
│   ├── schema/
│   │   ├── contract.json         ← EL CONTRATO. Fuente única de todo lo demás
│   │   ├── templates/*.md        ← plantilla por tipo (generadas)
│   │   └── json/*.schema.json    ← JSON Schema por tipo (generados)
│   ├── scaffold/                 ← lo que `brain init` deja en un cerebro nuevo
│   │   └── profiles/             ← los profiles de rol del kernel (init NO los copia)
│   ├── modulos/                  ← la lógica de los skills
│   └── tests/                    ← round-trip y competency questions
├── plugins/                      ← EXTENSIONES DEL USUARIO (skills, plantillas, profiles)
├── inbox/                        ← puerta de entrada de TODO (transitoria)
├── raw/                          ← originales inmutables + manifiesto.md
└── cerebro/                      ← EL CONOCIMIENTO (bundle OKF, portable)
```

En el starter, `cerebro/` **está vacío a propósito**: este repositorio nunca contiene
conocimiento. Lo materializa `brain.py init cerebro`, y lo personaliza `/x-setup`.

---

## Skills disponibles

Se invocan con el prefijo `x-`. La lógica de cada uno vive una sola vez en `kernel/modulos/`;
los stubs de `.claude/skills/` y `.github/prompts/` solo la cargan, y **se generan** desde el
frontmatter de cada módulo con `brain.py stubs`.

| Skill | Qué hace |
|---|---|
| `/x-setup` | Inicializa y personaliza el cerebro. Se elige un **profile de rol** y se ajusta, o se hace la entrevista completa |

<!-- TODO: las filas restantes se agregan al escribir los módulos que faltan. -->

### Profiles de rol

`/x-setup` no arranca con una entrevista de treinta minutos: ofrece un molde por rol y lo
ajusta. Los moldes son markdown con frontmatter, descubiertos por glob:

| Ruta | Dueño |
|---|---|
| `kernel/scaffold/profiles/*.md` | El kernel: trae tres |
| `plugins/profiles/*.md` | El usuario. **El slug es el nombre del archivo, y ante el mismo nombre gana el suyo** |

```bash
./brain profiles                       # los disponibles
./brain init cerebro --profile <slug>  # siembra PERFIL.md
```

**Añadir un rol es dejar caer un archivo**: sin código y sin tocar el contrato. Un profile lleva
los mismos encabezados que `kernel/scaffold/PERFIL.md` y **no repite su frontmatter** — ese lo
pone el scaffold genérico, para que `classification: confidential` se declare una sola vez.

Y la regla que ninguna comprobación sustituye: **un profile propone, nunca afirma.** Solo puede
llevar lo que es cierto del *rol*, jamás de la organización de quien lo elige. Por eso ninguno
siembra `Lineamiento`s ni `Sistema`s: un lineamiento es un estándar real de una empresa concreta,
e inventarlo sería fabricar.
