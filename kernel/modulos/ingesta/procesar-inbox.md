---
skill: x-procesar-inbox
description: 'Procesa todo lo que haya en inbox/: archiva el original, lo convierte, lo integra al wiki y deja el inbox vacío.'
---

# Skill: Procesar inbox (`/x-procesar-inbox`)

El ritual diario. Procesa **todo** lo que haya en `inbox/` salvo su `README.md`, y lo deja
vacío.

**Principio rector: integrar, no solo archivar.** Una fuente nueva no crea una nota: toca todas
las páginas que la nueva información afecta. Una reunión puede tocar diez.

**Regla central: no fabricar.** Lo que la fuente no diga, no se completa a ojo: se abre una
`Pregunta`. Y lo que la fuente contradiga, se dice — nunca se sobrescribe en silencio.

**Regla de zonas:** escribe en `cerebro/` y en `raw/`, y vacía `inbox/`. Es el **único** skill
que escribe en `raw/`.

---

## Fase 1 — Qué se lee y qué no

| Formato | Qué se hace |
|---|---|
| `.md` · `.txt` · `.vtt` | Se leen directo |
| `.pdf` `.docx` `.pptx` `.xlsx` `.drawio` `.html` `.yaml` | **Se convierten primero** (Fase 4) y se lee el `.md` resultante |
| Cualquier otro: imágenes, audio, vídeo, `.zip`, y los binarios legacy `.doc` `.ppt` `.xls` | **No se intenta ingerir.** Se quedan en `inbox/` y se reportan al final |

**Ningún agente abre un binario.** Leerlo quema miles de tokens y abre la puerta a inventar; la
conversión es determinista y cuesta cero. Y de un archivo que no se puede leer **no se deduce el
contenido**: se dice cuál es, por qué no se pudo y qué haría falta —exportarlo a un formato
moderno, pasarle OCR, pegar el texto—.

---

## Fase 2 — Clasificar

Qué es cada archivo —transcripción, documento recibido, nota, diagrama, correo— y **a qué
pertenece**. Si es ambiguo se pregunta: nunca se adivina el proyecto.

**Las carpetas del inbox son señal de destino.** Si una carpeta se llama como un proyecto de
`01-proyectos/`, un área de `02-areas/` o una carpeta de `03-recursos/`, **todo lo que cuelga de
ella pertenece a ese destino**: el usuario ya lo clasificó al agruparlo, y no se le pregunta
archivo por archivo.

- **Coincidencia tolerante**, no exacta: en kebab-case, minúsculas y sin acentos, aceptando el
  nombre completo o el nombre sin su prefijo de periodo — `inbox/migracion-erp/` es
  `01-proyectos/2026-q3-migracion-erp/`.
- **Recursiva**: la carpeta de primer nivel decide el destino de todo lo que cuelgue de ella, a
  cualquier profundidad. Las subcarpetas internas son organización del usuario y no re-enrutan.
- **La carpeta decide el destino; el contenido sigue decidiendo el tipo**, y el tipo decide la
  carpeta exacta — eso lo responde `./brain place`, no la prosa.
- **Varios candidatos → preguntar.** Se listan y elige el usuario.
- **Sin correspondencia → preguntar**, ofreciendo abrir el proyecto con `/x-nueva-iniciativa`,
  asignarla a algo que ya existe, o clasificar por contenido. **Nunca crear el proyecto por
  cuenta propia ni dispersar en silencio lo que el usuario agrupó a propósito.**
- **Si el contenido contradice a la carpeta** —el acta de otra iniciativa dentro de ella—, se
  señala; no se fuerza la carpeta.
- **Lo suelto en la raíz del inbox** se clasifica por contenido.

**Lo que no es de ningún proyecto lleva `proyecto: transversal`**, y tiene sitio propio: una
política de empresa, un 1:1, una decisión de área. `./brain place <Tipo> proyecto=transversal`
dice cuál.

---

## Fase 3 — Preservar el original

**Antes de convertir nada**, el original se mueve de `inbox/` a `raw/`:

```
AAAA-MM-DD-descripcion-uuid.ext
```

- **Fecha**: la del contenido si se conoce —la de la reunión, la del nombre original—; si no, la
  de hoy.
- **Descripción**: kebab-case, corta y autocontenida.
- **uuid**: seis caracteres hex, solo para evitar colisiones. Se comprueba que el nombre no
  exista ya en `raw/`.

**`raw/` es plano**: las carpetas del inbox no se replican ahí. Esa información no se pierde,
vive en la columna «Destino en el cerebro» del manifiesto, que es exactamente para eso.

Y se agrega su fila a `raw/manifiesto.md`, **con el SHA-256 del original**:

```bash
./brain hash raw/<archivo>      # el valor que va en la columna SHA-256
```

**Nada de `raw/` se edita ni se borra nunca**: es la fuente que el wiki cita, y junto al
manifiesto es lo que permite reconstruir con `/x-reconstruir`. El hash es lo que hace esa regla
comprobable — al cerrar, `./brain verify-raw` dice si algún original cambió o si quedó un archivo
sin fila.

---

## Fase 4 — Convertir

```bash
./brain kernel/bin/to-markdown.py raw/<archivo> \
    --project <slug|transversal> --source /raw/<archivo> --out <lo que dijo ./brain place>
```

Emite un `Insumo` —o un `Diagrama`, si es `.drawio`— que ya valida contra el contrato, con su
puntero `/raw/...` y su `# Citations`. Un `.xlsx` se **muestrea** a 50 filas por hoja; `--rows`
sube el límite cuando de verdad hace falta, y el original íntegro se queda en `raw/`.

Tres cosas que sí necesitan criterio:

1. **La `description` que deja el script dice «pendiente de resumir al integrarlo».** Se
   sustituye por una de verdad. Es el único campo que la conversión no puede saber.
2. **Los «Avisos de conversión» se atienden, no se borran.** Dicen qué se perdió. Un PDF sin
   capa de texto o una hoja truncada que importe se le dice al usuario o se abre una `Pregunta`;
   **nunca se rellena el hueco a ojo**.
3. **Un `.doc`, `.ppt` o `.xls` no se puede leer.** El script lo dice y pide «Guardar como» al
   formato moderno. Ese archivo **no se mueve a `raw/`** hasta tener la versión legible: se
   queda en el inbox y se reporta.

El `.md` resultante es un insumo más y sigue a la Fase 5.

---

## Fase 5 — Transformar según el tipo

`./brain place <Tipo> proyecto=<slug>` dice dónde va y `./brain template <Tipo>` con qué campos.
El catálogo vigente es `cerebro/ESQUEMA.md`.

**Transcripción de reunión** (`.vtt` o texto) → una `Reunion`. Antes de integrarla se elabora un
**resumen extenso y autocontenido**: participantes, temas, acuerdos, compromisos con fecha,
decisiones, riesgos y datos nuevos. Ese resumen es el cuerpo de la nota; **la transcripción
cruda no se copia al wiki, se cita**. Que se entienda sin abrir el `.vtt`.

**Documento recibido** → el `Insumo` que ya dejó la conversión, con su `description` real.

**Nota rápida o correo** → al tipo que corresponda, o anexado a un documento existente. **Los
nombres de las cabeceras `To`, `From` y `CC` no crean fichas `Persona`**: una lista de
distribución no es conocimiento. Se crea o actualiza una ficha solo si alguien es relevante en
la conversación — toma un compromiso, decide algo, es la referencia de un tema, o el usuario
trata con esa persona a menudo.

---

## Fase 6 — Integrar al wiki, que es el paso que compone

Por cada dato extraído, actualizar las páginas afectadas:

| Lo que trae la fuente | Dónde va |
|---|---|
| Acuerdos y compromisos del proyecto | **Filas del `PLAN.md`.** Si la tarea existe, se le cambia el estado; si no, se agrega a su fase con el id siguiente y la nota de reunión como Origen. Lo que la fuente da por entregado pasa a `hecha` — **sin borrar la fila** |
| Pendientes de una persona | La tabla «Pendientes conmigo» de su ficha. **Si es trabajo del proyecto, la fuente es la fila del `PLAN.md` y la ficha la espeja con enlace** — nunca dos listas |
| Dudas nuevas | Documentos `Pregunta`. Si la fuente **responde** una que ya estaba, se cierra: `estado: respondida` y `respondida_por` apuntando a lo que la respondió |
| Una decisión relevante | Se **propone** `/x-decision`; no se crea sola |
| Conocimiento permanente | La ficha `Sistema`, la ficha `Persona` o el `Lineamiento` que corresponda |

Si el proyecto no tiene `PLAN.md`, se sigue con las tablas de la reunión y de las fichas, y se
ofrece `/x-plan` una vez al final, sin insistir.

**Detectar contradicciones es obligatorio.** Un lineamiento que cambió, un dato de sistema
viejo, una tarea que la reunión da por entregada y el plan tiene `en-progreso`: no se
sobrescribe en silencio ni se ignora. Se dice —«la reunión dice X pero [página] dice Y, ¿cuál
vale?»— y al resolverse la página queda con su nota de supersesión:

```markdown
> Hasta AAAA-MM-DD se creía X (fuente); superado por Y (fuente).
```

---

## Fase 7 — Cerrar

```bash
./brain index cerebro      # los index.md de todo lo tocado
./brain derive cerebro     # PREGUNTAS-ABIERTAS.md, GOALS.md y ORGANIGRAMA.md
./brain validate cerebro   # debe terminar sin hallazgos
```

Y lo que ningún comando hace:

1. **Completar la columna «Destino en el cerebro»** de las filas nuevas del manifiesto, con
   enlaces a las páginas que salieron de cada fuente.
2. **Actualizar `ultima-revision`** en el `PLAN.md` de cada proyecto tocado.
3. **Loguear**: en el `log.md` de cada proyecto tocado y en `cerebro/log.md`, bajo su
   `## AAAA-MM-DD`:
   `**Ingesta**: N fuentes procesadas — N páginas creadas, N actualizadas, N preguntas nuevas.`
4. **Vaciar el inbox.** Se borran las carpetas que quedaron vacías. Si dentro sobrevivió algo no
   convertible, la carpeta se conserva con ello y se reporta.

---

## Fase 8 — Reportar

Un resumen final con: cuántas fuentes se procesaron y a qué destino fue cada carpeta, páginas
creadas y actualizadas, preguntas nuevas y cerradas, **tareas abiertas y cerradas en los
planes**, las contradicciones encontradas y cómo se resolvieron, y lo que quedó esperando
decisión del usuario.

---

## Lo que este skill NO hace, y por qué

| Qué | Quién lo hace en su lugar |
|---|---|
| Escribir los `index.md` de las carpetas tocadas | `./brain index` |
| Regenerar `PREGUNTAS-ABIERTAS.md`, `GOALS.md` u `ORGANIGRAMA.md` | `./brain derive`. `ORGANIGRAMA.md` sale de `reporta-a`; basta con que las fichas lo lleven |
| Actualizar `cerebro/PENDIENTES.md` | Nadie: **no existe en v2**. Las tareas viven dentro del `PLAN.md` |
| Decidir en qué carpeta va cada documento | `./brain place` |
| Abrir un proyecto que no existe | `/x-nueva-iniciativa`, y solo si el usuario lo pide |
| Registrar una decisión | `/x-decision`. Aquí solo se propone |
| Re-planificar un proyecto | `/x-plan`. Aquí se actualizan filas, no se rehace el árbol de tareas |
| Abrir o interpretar un binario | `./brain kernel/bin/to-markdown.py` |
| Editar, renombrar o borrar algo de `raw/` | Nadie. Nunca — y `./brain verify-raw` lo detecta |
