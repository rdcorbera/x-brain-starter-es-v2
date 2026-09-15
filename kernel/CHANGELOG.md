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
idempotente. Doce subcomandos; los que cambian el día a día:

- **`init`** — materializa un cerebro: estructura, esquema portable, índices y derivados. El
  starter ya no versiona un `cerebro/` con TODOs: llega vacío y esto lo construye.
- **`validate`** — 26 comprobaciones en dos niveles (OKF / perfil), porque OKF es
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

### `brain.py` se corta por sus cuatro trabajos

- El archivo llegó a **2.582 líneas**, por encima del umbral que el rediseño se había fijado.
  Ahora la lógica vive en `kernel/bin/brainlib/`, cortada **por trabajo**: `parse` (leer),
  `generate` (escribir), `validate` (comprobar) y `report` (rendir), más `const` con el
  vocabulario compartido. Ningún archivo pasa de 705 líneas.
- **`kernel/bin/brain.py` sigue siendo el punto de entrada** y se queda con la CLI: `argparse`,
  los `cmd_*` y el hook de git. Ni un comando cambia, y los artefactos generados salen **byte a
  byte idénticos** — es lo que verifica que el corte no alteró comportamiento.
- Las dependencias van en **un solo sentido** (`const → parse → generate → validate → report`)
  y `check_layering` lo comprueba, incluidos los imports diferidos dentro de una función.

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

### El esquema de la proyección SQLite, generado desde el contrato

- **`kernel/schema/ddl.sql`** es un artefacto generado más: lo escribe `brain generate` y **V14
  lo vigila**, igual que a las plantillas y los JSON Schemas. Si está mal, lo que se corrige es
  `contract.json`.
- **`./brain project --ddl`** imprime el esquema de *este* cerebro —con sus tipos propios de
  `cerebro/schema.json`, si los tiene— sin tocar disco.
- Una tabla por tipo, `documentos` con los campos comunes, y **tabla hija por cada campo
  estructurado**: `sources` y `verified` proyectan una columna por miembro en vez de un JSON
  opaco, que es lo que permite consultarlos. Las tablas son `STRICT` y cada enum lleva su
  `CHECK`: el motor rechaza lo que el contrato no admite.
- **El mapa de tipos a SQL vive en el contrato**, no en el generador. Agregar un campo, o un
  `data_type` entero, cambia el DDL sin tocar código — y el round-trip lo comprueba agregando
  uno, además de ejecutar el DDL contra SQLite.
- Nada de esto abre una base de datos todavía: proyectar y consultar llega después. Por eso
  `generate` y las pruebas siguen sin importar `sqlite3`, y el DDL se verifica en CI aunque la
  máquina no pueda alojar una base.

### La clave de una iniciativa es única, y se comprueba en los tres sitios

- **`proyecto` identifica a una `Iniciativa`**: es lo que todos los demás documentos escriben en
  su propio campo `proyecto`. Dos iniciativas con el mismo slug hacen ambigua cada referencia del
  cerebro — y **V20 no lo veía**, porque resolver encuentra una y encontrar una basta.
- Se declara en el contrato (`key_unique`) y de ahí salen las tres aplicaciones, cada una
  haciendo lo que solo ella puede: **`/x-nueva-iniciativa` comprueba antes de crear** —lo único
  que lo previene, y mira también `04-archivo/`, porque reusar el slug de una iniciativa cerrada
  rompe lo que se archivó con ella—, **V27** lo detecta en un cerebro que ya lo tiene, y el
  **`UNIQUE`** de la proyección impide que llegue a la base.

### El mapa a JSON Schema se muda al contrato

- Estaba hardcodeado en el generador, que es el patrón que se rechazó al declarar el de SQL: un
  `data_type` nuevo se habría emitido como `string` **en silencio**. Ahora los dos mapas viven en
  `data_types` y el round-trip exige que todo tipo de dato declare los dos.
- Los 13 JSON Schemas generados son **byte a byte idénticos** tras la migración, que es la prueba
  de que el cambio preserva el significado en vez de suponerlo.

### El `resumen` se sella contra su cuerpo (`resumen_hash` y V23)

- **Un resumen desfasado es peor que no tener ninguno.** Sin resumen se abre el documento y se
  pierde contexto; con uno que ya no describe el cuerpo, se decide **no** abrirlo creyendo algo
  que dejó de ser cierto — y el sistema entero está construido sobre poder descartar sin abrir.
- **`resumen_hash`** guarda el SHA-256 del **cuerpo** en el momento en que se escribió el resumen,
  y **V23** avisa cuando el cuerpo cambió después. Es un aviso y no un error a propósito: el hash
  no puede saber si el cambio afecta a lo que el resumen afirma —corregir una errata no lo
  invalida—, pero sí sabe que **nadie lo ha vuelto a mirar**.
- **`./brain hash <archivo> --body --write`** lo calcula y lo escribe. Existe porque un agente no
  puede hacer un SHA-256 a ojo: sin el comando, el campo se rellenaría a mano y V23 vigilaría un
  número inventado.
- **`validate --fix` no lo toca, y es deliberado.** Recalcular el hash silenciaría el aviso sin
  que nadie compruebe si el resumen sigue siendo cierto: falsificar la garantía en vez de
  repararla. Sellar es una afirmación, y la hace quien acaba de escribir las dos mitades.
- Requerido pero relajado a aviso mientras el corpus migra: los 301 documentos de producción son
  anteriores al campo.

### La proyección: el cerebro, consultable con SQL

- **`./brain project`** puebla una base SQLite desde el markdown. Compara el SHA-256 de cada
  archivo con el de su fila, así que una segunda corrida no reescribe nada; **`--full`**
  reconstruye la base entera.
- **`--full` y una pasada incremental producen exactamente lo mismo**, y el round-trip lo
  comprueba por los cuatro caminos: crear, no tocar nada, modificar y borrar. Esa propiedad es lo
  que permite tratar la base como desechable — y por tanto seguir tratando el markdown como la
  única fuente. Si difirieran, habría estado en la base que no está en los documentos y nadie
  sabría cuál creer.
- **Se proyecta conocimiento y solo conocimiento.** Fuera quedan los archivos reservados
  (`log.md`), los derivados y los índices: los escribe el generador desde este mismo contenido, y
  guardarlos sería tener dos copias para que una envejezca.
- **El reparto de campo a columna se decide una vez** (`projection_plan`): el DDL lo renderiza y
  el proyector lo puebla. Deducirlo dos veces es cómo un esquema acaba declarando columnas que
  nadie rellena.
- La base no se versiona: `.gitignore` cubre `_db/`, `*.db`, `*.sqlite` y los sidecars `-wal` y
  `-shm` del modo WAL.

### La vista de eventos: qué pasó, en una consulta

- **`eventos`** junta en una sola lista ordenada todo lo que tiene fecha —reuniones, decisiones,
  preguntas abiertas, análisis y revisiones de plan—, con su tipo, su fecha, su título y el
  enlace a su documento. Reconstruir lo que pasó en una iniciativa deja de exigir abrir su
  carpeta entera.
- **Se genera por regla, nunca por una lista de nombres**: entra todo campo con
  `data_type: date`. Seleccionar por el nombre `fecha` habría omitido `Pregunta.fecha-creacion` y
  `Plan.ultima-revision` **en silencio**, que es el defecto que esta regla vino a eliminar. Un
  tipo nuevo con fecha entra solo.
- **Un campo que es fecha pero no es un evento se excluye declarándolo**, no con una excepción en
  el código: `Diagrama.version` lleva `timeline: false` y la razón escrita en su propio campo.
- Una fila por campo fechado, no por documento: un tipo con dos fechas aporta dos eventos, y por
  eso la vista lleva `campo`.

### Búsqueda por texto: rutas y ranking, nunca contenido

- **`./brain project --search "<término>"`** consulta un índice **FTS5** sobre el título, la
  descripción, el `resumen` y el cuerpo, y ordena por **BM25**. Se puebla en la misma pasada que
  la proyección.
- **Devuelve rutas, ranking y título — nunca el texto encontrado.** Entregar fragmentos dejaría
  al lector donde empezó: leyendo texto para decidir qué leer. Lo que abarata encontrar es elegir
  bien con `description` y `resumen`, y abrir pocos.
- **Busca sin acentos.** `migracion` encuentra `migración`: el español es el idioma por defecto de
  un cerebro, y sin eso el índice sería una trampa para quien escribe deprisa.
- **Si este SQLite no trae FTS5, la proyección se hace igual, sin índice, y lo dice** — nombrando
  `sqlite-probe.py`, que es lo que responde por qué. FTS5 es un flag de compilación, no una
  versión: un SQLite reciente puede no traerlo. Perder la búsqueda es peor que no perder nada;
  perder la proyección entera porque falta la búsqueda sería peor aún.
- Saltarse los vectores densos no es una concesión: la ablación del paper de Agent Zero mide esta
  misma restricción —solo léxico pierde 1,8 puntos frente al híbrido— y las tres variantes
  restringidas siguen por encima del mejor sistema externo.

### La vigencia deja de estar en seis sitios

- **Había seis mecanismos** para responder *«¿esto sigue valiendo?»* —`status`, `stale_after`,
  `Decision.estado`, `reemplazada_por`, `Lineamiento.vigencia` y las fechas nuevas—, y el propio
  contrato admitía que uno sobraba. Seis respuestas solapadas no hacen un sistema más estricto:
  hacen imposible saber cuál vale cuando se contradicen.
- **Ahora manda el intervalo.** `valido_desde`/`valido_hasta` son la única fuente de «¿rigió?».
  `Decision.estado` adelgaza a `propuesta`·`aceptada`; `Lineamiento.vigencia` se **renombra a
  `estado`** y pierde `derogado`; ambos tipos ganan el intervalo, y `Lineamiento` también
  `reemplazada_por`.
- **Los tres estados dejan de ser valores y pasan a ser consultas**: vigente es `valido_hasta`
  vacío; reemplazada, con sucesor; **caducada, sin él**. Ese último caso es el que un modelo
  derivado de la cadena de supersesión no puede expresar —sin sucesor no hay fecha de cierre y la
  regla figura vigente para siempre—, y es exactamente lo que hay que detectar antes de que
  alguien decida sin criterio.
- **Una decisión tomada en julio puede regir desde mayo.** El intervalo lo dice; la fecha del
  documento, no.
- **`V24`** comprueba lo que un intervalo puede tener de incoherente: que acabe antes de empezar,
  que algo sustituido no tenga fecha de cierre, y que dos documentos se declaren sucesores el uno
  del otro.
- El reparto completo —cinco ejes, qué responde cada campo— vive en **`validity_model`** dentro
  del contrato, no en un plan aparte.

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
