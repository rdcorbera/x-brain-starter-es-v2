---
skill: x-decision
description: 'Registra o delibera una decisión, validándola contra las decisiones previas, los lineamientos y las fichas de sistema.'
---

# Skill: Decisión (`/x-decision`)

Registra una decisión con su contexto, sus alternativas y sus consecuencias — **validándola contra
lo que el cerebro ya sabe**. Aplica a cualquier decisión con consecuencias: técnica, comercial, de
proceso, de contratación, de priorización.

**Usa el modelo más capaz que tengas.** Es el skill donde el razonamiento aporta más: casi todo su
valor está en la Fase 2, que es cruzar la decisión contra lo ya decidido.

**Regla central: no fabricar.** Si no se sabe quién decidió, el campo queda vacío; si no se sabe
qué alternativas se consideraron, se dice que no consta. Una decisión con alternativas inventadas
parece deliberada y no lo fue.

**Regla de zonas:** escribe en `cerebro/` y en ningún otro sitio.

---

## Fase 0 — Cuál de los dos modos

| Modo | Cuándo | Qué escribe |
|---|---|---|
| **Registro** | La decisión **ya se tomó**, típicamente en una reunión | La documenta fielmente. `estado: aceptada` |
| **Deliberación** | La decisión **está abierta** | Estructura opciones y compromisos **antes** de decidir. `estado: propuesta` |

Se elige al empezar y se dice en voz alta. **En deliberación no se cierra por el usuario:** el
documento queda en `propuesta` hasta que alguien decida, y `# Decisión` dice qué falta para poder
hacerlo.

---

## Fase 1 — Capturar

Preguntar **solo lo que falte**, buscando antes en la base:

1. **¿Qué se decidió, o qué hay que decidir?**
2. **¿De qué proyecto es?** Si no es de ninguno, es `transversal` y tiene sitio propio.
3. **¿Qué opciones se consideraron?** Las que se descartaron valen tanto como la elegida: son lo
   que impide volver a discutirlas dentro de seis meses.
4. **¿Quién decidió?** Enlace a ficha `Persona`. Un comité o un área en texto libre se tolera y se
   reporta hasta resolverse (V17).
5. **¿Dónde se decidió?** La reunión, el correo o el documento. Es la cita, y es obligatoria.

---

## Fase 2 — Validar, que es el paso que agrega valor

**Antes de escribir nada**, cruzar la decisión contra tres cosas. Este es el trabajo del skill;
escribir el documento es el trámite.

| Contra qué | Dónde | Si hay choque |
|---|---|---|
| **Decisiones previas** sobre el mismo tema | `02-decisiones/` de los proyectos, `02-areas/decisiones/`, y `04-archivo/` si la pregunta es histórica | **Se señala explícitamente** y se pregunta si esta la reemplaza |
| **Lineamientos vigentes** | `02-areas/` | Se advierte con el enlace. **El usuario decide** si procede como excepción, y entonces la excepción se documenta en `# Consecuencias` |
| **Fichas de `Sistema`** | `03-recursos/sistemas-y-herramientas/` | Si lo que la decisión asume no coincide con la ficha, **eso es una `Pregunta`**, no un supuesto |

**La supersesión se registra, no se narra.** Si esta decisión reemplaza a otra, la anterior pasa a
`estado: reemplazada` con `reemplazada_por` apuntando a la nueva — el contrato exige ese campo
cuando el estado lo dice. **La decisión superada no se borra ni se edita en su fondo:** queda
donde está, marcada, y por eso se puede reconstruir qué se creía y cuándo.

**Nunca se elige en silencio.** Dos decisiones que se contradicen y conviven sin decirlo son
exactamente el modo de fallo que el sistema existe para evitar.

---

## Fase 3 — Escribir

```bash
./brain place Decision proyecto=<slug>     # o proyecto=transversal
./brain template Decision
```

El nombre lo dice `place`: `dec-NNN-tema.md`, con **`NNN` secuencial dentro de su carpeta** — se
mira cuál es el último y se suma uno.

Tres campos que necesitan criterio:

- **`procedencia`** — para una decisión casi siempre es `dialogo` (se decidió hablando) o `manual`
  (la escribió una persona). `inferido` solo si el agente la dedujo de una fuente, y entonces
  **no está verificada**: dilo en la respuesta.
- **`resumen`** — el panorama que permite descartar este documento sin abrirlo. Para una decisión:
  qué se decidió, contra qué alternativa y qué obliga. No repitas el `title`.
- **`# Citations`** — la reunión o la fuente donde se decidió. **Es obligatoria y ahora se
  comprueba**: una cita que no resuelve a un documento del cerebro es un error (V22). Si la fuente
  no está escrita todavía, eso es un hueco, no una cita.

---

## Fase 4 — Integrar y cerrar

Una decisión no termina en su documento: **toca lo que decide.**

1. **Las fichas de `Sistema` afectadas** ganan su línea en `# Decisiones históricas que lo afectan`,
   con enlace.
2. **Lo que quede desactualizado por esta decisión** —un diagrama, un `PLAN.md`, un lineamiento—
   se señala y se ofrece actualizarlo. No se actualiza en silencio.
3. **Si la decisión responde una `Pregunta` abierta**, se cierra: `estado: respondida` y
   `respondida_por` apuntando a esta decisión.

```bash
./brain index cerebro
./brain derive cerebro     # si se tocó alguna Pregunta
./brain validate cerebro   # debe terminar sin hallazgos
```

Y el log, en el `log.md` del proyecto y en `cerebro/log.md`, bajo su `## AAAA-MM-DD`:
`**Decisión**: dec-NNN <título> — <aceptada|propuesta>. Reemplaza a <dec-MMM>, si aplica.`

---

## Lo que este skill NO hace, y por qué

| Qué | Quién lo hace en su lugar |
|---|---|
| Escribir los `index.md` de las carpetas tocadas | `./brain index` |
| Regenerar `PREGUNTAS-ABIERTAS.md` al cerrar una pregunta | `./brain derive` |
| Decidir por el usuario cuando hay choque con un lineamiento | El usuario. El skill advierte y enlaza; la excepción la autoriza quien manda |
| Cerrar una deliberación | Nadie automáticamente. Queda en `propuesta` hasta que alguien decida |
| Borrar o reescribir una decisión superada | Nadie. Se marca `reemplazada` y se enlaza; el registro de lo que se creyó es el valor |
| Crear el lineamiento que una decisión implique | `/x-decision` registra la decisión; un `Lineamiento` es un estándar vigente y se escribe aparte |
| Inventar las alternativas consideradas | Nadie. Si no constan, se dice que no constan |
