# Cuestionario de setup — la vía larga

Este es el guion de la **vía (b)** de `/x-setup`: la entrevista completa, para quien no se
reconoce en ningún profile de rol o quiere construir su perfil desde cero.

**Si el usuario se reconoce en un profile, esto no se usa.** La vía corta —elegir un profile y
ajustarlo— cubre lo mismo en unos cinco minutos, y estas preguntas están precisamente entre las
que aquel evita. Ofrecer siempre la lista antes de empezar:

```bash
./brain profiles
```

**Reglas que atraviesan todas las rondas:**

- **No fabricar.** Una respuesta delgada da una sección delgada. Nunca se rellena un hueco con
  un supuesto.
- **Una ronda por vez**, en conversación. Resumir cada ronda antes de avanzar.
- **Insistir una vez y seguir.** Si una respuesta queda vaga, se repregunta una sola vez. Un
  cuestionario que persigue al usuario es exactamente lo que hace que no se termine.
- **Los ejemplos son para desatascar**, no para rellenar. Si el usuario adopta el ejemplo tal
  cual, preguntar si de verdad es así.

---

## Ronda 1 — Quién eres

*Alimenta:* `PERFIL.md` → `# Quién soy`.

1. **¿Cómo te llamas y en qué organización trabajas?**
2. **¿Cuál es tu rol y desde cuándo lo ocupas?** — la antigüedad calibra cuánto contexto de la
   organización se puede dar por sabido y cuánto hay que documentar desde cero.
3. **¿Qué entregables salen de tus manos?** Cosas concretas: documentos, código, actas,
   presentaciones. Son la salida del sistema, y definen qué te sirve al consultar la base.
4. **De todo eso, ¿qué te da energía y qué sientes como trámite?** No es una pregunta de
   satisfacción: marca dónde poner el énfasis cuando el agente tiene margen de criterio.
5. **¿En qué idioma quieres el contenido?** Español por defecto.
6. *(Opcional)* **¿Hay contexto personal que afecte cómo se prioriza?** Zona horaria distinta a
   la del equipo, compromisos fijos, turnos. Si no hay nada, se deja vacío.

## Ronda 2 — Cómo trabajas

*Alimenta:* `PERFIL.md` → `# Cómo trabajo`, y `period_format` en `cerebro/schema.json`.

1. **¿Cómo fluye un trabajo tuyo de inicio a fin?** Cómo nace y qué pasos atraviesa hasta darse
   por entregado. Es lo que permite saber en qué etapa está cada cosa sin preguntarlo cada vez.
2. **¿De quién recibes y a quién entregas?** **Por rol o área, nunca por nombre** — los nombres
   viven en las fichas `Persona`, y repetirlos aquí los desincroniza.
3. **¿Tu planificación es trimestral, mensual o por sprints?** Es la pregunta más estructural de
   todo el cuestionario: de ella dependen el campo `periodo` de cada `Iniciativa` y las carpetas
   de `04-archivo/`. Se escribe como `period_format` en `cerebro/schema.json`, con uno de tres
   valores: `quarterly` (`2026-Q3`), `monthly` (`2026-08`) o `sprint` (`2026-S14`).
4. *(Opcional)* **¿Qué rituales o hitos fijos tienes?** Comités, weeklies, cierres. Son las
   fechas contra las que `/x-briefing-diario` y `/x-preparar-reunion` anticipan.

## Ronda 3 — Reglas de comunicación

*Alimenta:* `PERFIL.md` → `# Reglas de comunicación`.

1. **¿Cómo quieres que te hablen los agentes?** Extensión y tono. De referencia: directo / con
   matices / equilibrado.
2. **¿Tienes manías de formato?** Qué prefieres en tabla y qué en prosa, si quieres emojis, si
   un documento para comité debe arrancar por la recomendación en vez de por el contexto. Valen
   más de lo que parecen.

## Ronda 4 — Tus límites

*Alimenta:* `PERFIL.md` → `# Lo que nunca se hace` y `# Confidencialidad`.

1. **¿Qué no deben hacer los agentes nunca, aunque tengan la información?** El kernel ya trae la
   regla genérica —«mostrar antes de escribir»—, pero no puede saber cuáles son tus límites.
   Esta es la sección que hace que el sistema se pueda dejar trabajar solo.
2. **¿Qué restricciones de confidencialidad aplican donde trabajas?** Qué nombres, qué sistemas
   o qué asuntos no entran en este cerebro. El kernel ya aplica lo aplicable —la clasificación
   tiene un mínimo por tipo (V16) y la responsabilidad se resuelve contra fichas `Persona`
   (V17)—; aquí va lo que ninguna comprobación puede saber.

   Sea cual sea la respuesta, esto rige siempre: **credenciales, secretos y tokens no entran
   nunca**, y ninguna comprobación detecta uno pegado en una nota.

---

## Lo que este cuestionario ya no pregunta

Cuatro rondas de v1 desaparecieron a propósito. Preguntaban por cosas que otros skills crean
solos en cuanto aparecen, y hacerlo aquí obligaba a describir un sistema que el usuario todavía
no había usado ni una vez.

| Lo que v1 preguntaba | Por qué ya no |
|---|---|
| La tabla de personas | Las fichas las crea `/x-procesar-inbox` cuando alguien aparece en una fuente, y `ORGANIGRAMA.md` se genera solo desde `reporta-a` |
| Las áreas de conocimiento | Se acuerdan al elegir profile, o se crean cuando hace falta la primera |
| Los tipos de documento propios | Pedía **diseñar una taxonomía** antes del primer uso. Ahora es `/x-crear-plantilla`, cuando el catálogo base se quede corto de verdad |
| Los objetivos del periodo | Son documentos `Iniciativa`, y los crea `/x-nueva-iniciativa`. `GOALS.md` es un derivado: **no se escribe a mano** |

Al terminar, volver a la **Fase 3** de `setup.md` para escribir y cerrar.
