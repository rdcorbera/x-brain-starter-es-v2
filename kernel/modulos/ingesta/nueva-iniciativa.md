---
skill: x-nueva-iniciativa
description: 'Abre una iniciativa —proyecto asignado u objetivo— con su CONTEXT.md, su plan y la documentación inicial ya procesada.'
---

# Skill: Nueva iniciativa (`/x-nueva-iniciativa`)

Crea una iniciativa en `cerebro/01-proyectos/`: el `CONTEXT.md` que la encuadra, el `PLAN.md`
que la lleva a «entregado», y la documentación inicial convertida, archivada y leída.

**Regla central: no fabricar.** Lo que el usuario no sepa todavía queda como `<!-- TODO -->` o
como documento `Pregunta`, nunca relleno con un supuesto plausible. Un plan con tareas
inventadas se ve igual que uno real y se descubre semanas después.

**Regla de zonas:** todo lo que este skill escribe vive en `cerebro/` y en `raw/`. Jamás edita
`kernel/`, `.github/` ni los stubs de `.claude/skills/`.

**`GOALS.md` no se toca.** Es un derivado de `Iniciativa.origen`: al crear el `CONTEXT.md` con
su `origen` y correr `./brain derive`, la iniciativa aparece sola en su bloque. Escribirla a
mano es trabajo que se pierde en la siguiente corrida.

---

## Fase 0 — Buscar antes de preguntar

Antes de la primera pregunta, mirar `cerebro/GOALS.md`, `cerebro/01-proyectos/` y
`cerebro/PERFIL.md`.

| Lo que se encuentra | Qué hacer |
|---|---|
| Nada parecido | Fase 1 |
| Una iniciativa del mismo asunto **activa** | No se crea otra: se amplía la que existe. Duplicar parte el historial en dos y ningún skill vuelve a juntarlo |
| Una iniciativa del mismo asunto **en `04-archivo/`** | Es una nueva, y la archivada es su precedente: enlazarla desde `# Qué es` |

Y no preguntar lo que ya está escrito: el ciclo de planificación, las personas con ficha y los
sistemas ya registrados salen de la base, no del usuario.

---

## Fase 1 — La entrevista

Nueve preguntas, **una por vez y en conversación** — no volcarlas de golpe. Si una respuesta
viene vaga, se repregunta **una sola vez** y se sigue. Los ejemplos son para desatascar a quien
no entiende la pregunta, nunca una respuesta sugerida que solo haya que aceptar.

1. **¿Cómo se llama, y es un proyecto asignado, un objetivo personal o uno del equipo?**
   El origen decide contra qué vara se revisa y en qué bloque de `GOALS.md` aparece. Un objetivo
   personal registrado como proyecto asignado termina priorizado como si alguien lo esperara.
   → `title`, `origen`, `periodo`, y el slug de la carpeta.
2. **¿Qué es?** Un párrafo: qué se construye o se logra, para quién, y por qué ahora.
   → `description` y la sección `# Qué es`.
3. **¿Qué significa «entregado»?** Pedir algo observable —una fecha, una métrica, un estado
   verificable—: «que quede bien» no permite decidir nada. Es la directiva que todo agente lee
   al abrir el proyecto, y la raíz a la que rastrea cada tarea del plan.
   → la sección `# Qué significa "entregado"`.
4. **¿Cómo fluye el trabajo, de inicio a fin?** Repreguntar una vez: *¿algo de esto no puede
   arrancar hasta que pase otra cosa?* — las dependencias reales son lo que después permite
   decir «esto está esperando a X» en vez de mostrar una lista plana.
   → las fases del `PLAN.md`. **Las subcarpetas del proyecto no salen de aquí**: las nombra
   `./brain place`, y se crean cuando entra el primer documento de ese tipo.
5. **¿Qué sistemas, herramientas o productos de la organización toca?** Los sistemas son
   conocimiento permanente: sobreviven al cierre del proyecto y se comparten con los demás.
   → el campo `sistemas`, y una ficha mínima por cada uno que no la tenga.
6. **¿Quiénes están involucrados, y con qué rol en esta iniciativa?** De aquí salen los
   responsables de las preguntas abiertas — y una pregunta sin responsable no se resuelve, se
   acumula.
   → el campo `personas`, la sección `# Personas clave`, y una ficha mínima por cada persona
   nueva.
7. **¿Ya tienes documentación inicial?** Brief, requerimientos, propuesta, contrato: lo que sea
   que dispara el trabajo. Es la fuente más densa que el proyecto va a tener y la única que
   existe antes de la primera reunión.
   → si la hay, se deja en `inbox/` o se indica la ruta, y la procesa la Fase 2. Si no la hay,
   el proyecto arranca vacío y se llena con `/x-procesar-inbox`.
8. **¿Qué fechas o hitos ya están fijos?** Interesan las que **no** se mueven, no las
   estimaciones: sin fecha no hay «vencido», y sin vencido no hay seguimiento.
   → las líneas `> **Hito:**` de cada fase y los límites de las tareas.
9. **¿Dónde vive hoy el plan de este proyecto?** Jira, Asana, un Excel del área, tu cabeza, o no
   existe. **No es para armar la lista: es para no duplicarla.** Si las tareas ya viven en un
   tracker, un plan completo en el cerebro es una segunda fuente de verdad que se desactualiza
   en dos semanas, y desde ahí todo lo que el cerebro diga del avance es falso.
   → `fuente-de-verdad`. Con `cerebro`, el plan manda. Con `externa`, se guarda **solo la tajada
   del usuario** más el puntero en `tracker-externo`, y ningún skill afirma progreso global.

> Las preguntas 8 y 9 son de planificación. Si la iniciativa no da para un plan —un objetivo
> personal chico, algo de dos semanas—, se saltan sin insistir y el proyecto arranca sin
> `PLAN.md`. Se agrega después con `/x-plan`.

---

## Fase 2 — Construir

**Mostrar antes de escribir**: un resumen de la estructura y los documentos que se van a crear,
y confirmar. A partir de ahí, cada destino lo responde un comando.

### 1. El `CONTEXT.md`

```bash
./brain place Iniciativa proyecto=<slug>      # dónde va
./brain template Iniciativa                   # con qué campos
```

El slug lleva el periodo delante, como propone la plantilla: `2026-q3-migracion-erp`. El
`periodo` sigue la forma declarada en `cerebro/schema.json`, y la plantilla ya propone el
ejemplo correcto — no hay que deducirla.

### 2. La documentación inicial, si la hay

1. **El original va a `raw/`** con su nombre `AAAA-MM-DD-descripcion-uuid.ext` y su fila en
   `raw/manifiesto.md`, según la convención de `kernel/AGENTS.md`. Nunca se edita ni se mueve.
2. **Se convierte; no se abre el binario.**
   ```bash
   ./brain kernel/bin/to-markdown.py <archivo> --project <slug> \
       --source /raw/<original> --out cerebro/01-proyectos/<slug>/00-insumos/
   ```
   Emite un `Insumo` que ya valida contra el contrato. **Los «Avisos de conversión» que traiga
   arriba no se borran**: son la diferencia entre saber que falta un dato y creer que no existe.

### 3. El análisis inicial

Con lo convertido, un documento **`Analisis`** en la raíz del proyecto —`analisis-inicial.md`—
con el resumen en palabras propias, el inventario de requerimientos y entregables detectados, y
las dudas clasificadas por quién las resuelve.

```bash
./brain place Analisis proyecto=<slug>
./brain template Analisis
```

**Es `Analisis`, no `Playbook`**: un playbook se *sigue* otra vez, y esto se *consulta*. En v1
salía como `Playbook` y esa mezcla es justo la que el contrato deshizo.

### 4. Las dudas, como documentos

Cada duda del análisis se crea como `Pregunta` con su responsable. Sin responsable se queda
vacío — es un hueco declarado, nunca un supuesto.

```bash
./brain place Pregunta proyecto=<slug>
./brain template Pregunta
```

### 5. Las fichas que falten

Una ficha mínima por cada sistema y cada persona de las preguntas 5 y 6 que todavía no la
tenga, con sus TODOs. Nada más: rellenarlas es trabajo de `/x-procesar-inbox` cuando aparezcan
en una fuente.

```bash
./brain place Sistema   # y ./brain template Sistema
./brain place Persona   # y ./brain template Persona
```

### 6. El `PLAN.md`

Salvo que se hayan saltado las preguntas 8 y 9. **Se arma cruzando lo ya respondido; no se
pregunta nada nuevo:**

| Parte del plan | De dónde sale |
|---|---|
| `# Entregado` | La respuesta 3, **copiada literal** del `CONTEXT.md` |
| Las fases | El flujo de la 4, con los hitos de la 8 como línea `> **Hito:**` |
| Las tareas | El inventario del análisis inicial; responsables de la 6, dependencias de la repregunta de la 4. Ids `T01`, `T02`… |
| `fuente-de-verdad` | La respuesta 9. Si es `externa`, solo el esqueleto de fases, la tajada del usuario y el puntero en `tracker-externo` — nunca copiar el tracker |

**Sin documentación inicial el plan sale delgado**, con las fases y las pocas tareas que el
usuario haya mencionado. Es correcto. **No rellenar con tareas plausibles.**

### 7. Poner al día lo generado

```bash
./brain index cerebro      # index.md del proyecto y del árbol
./brain derive cerebro     # GOALS.md y PREGUNTAS-ABIERTAS.md
./brain validate cerebro   # debe terminar sin hallazgos
```

Si `validate` reporta algo, se resuelve antes de dar la iniciativa por abierta.

### 8. Loguear

Una entrada en `cerebro/log.md` y otra en el `log.md` del proyecto —creándolo—, bajo su
`## AAAA-MM-DD`:
`**Nueva iniciativa**: <título> abierta como <origen>, periodo <periodo> — N insumos, N preguntas.`

---

## Fase 3 — Confirmar

Mostrar la estructura creada, el resumen del `CONTEXT.md`, **el plan completo**, las preguntas
generadas y los TODOs que quedaron abiertos. El plan es lo que más conviene revisar en voz alta:
una tarea mal atribuida se arrastra semanas.

---

## Lo que este skill NO hace, y por qué

| Qué | Quién lo hace en su lugar |
|---|---|
| Enlazar la iniciativa en `cerebro/GOALS.md` | `./brain derive`, desde `Iniciativa.origen`. **Es la regresión más fácil de cometer aquí**: v1 lo ordenaba a mano |
| Escribir el `index.md` del proyecto ni el de `01-proyectos/` | `./brain index` |
| Añadir las dudas a `cerebro/PREGUNTAS-ABIERTAS.md` | `./brain derive`, desde los documentos `Pregunta` |
| Actualizar `cerebro/PENDIENTES.md` | Nadie: **ese archivo no existe en v2**. Las tareas viven dentro del `PLAN.md` |
| Actualizar la sección `# Estado actual` de `cerebro/PERFIL.md` | `/x-actualizacion-semanal`, que es quien la mantiene |
| Inventar subcarpetas para el proyecto | `./brain place` las nombra por tipo; se crean cuando entra el primer documento |
| Rellenar las fichas de personas y sistemas | `/x-procesar-inbox`, cuando aparezcan en una fuente |
| Abrir o interpretar un binario | `./brain kernel/bin/to-markdown.py` |
