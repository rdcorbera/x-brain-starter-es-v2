---
type: Perfil
title: Perfil del usuario
description: Quién opera este cerebro, cómo trabaja y qué reglas de comunicación y confidencialidad respetan los agentes.
classification: confidential
---

<!--
  Este archivo lo rellena /x-setup con una entrevista. `brain init` solo lo deja
  puesto, porque la estructura es mecánica y el contexto no.

  Es el segundo archivo que lee todo agente, después de kernel/AGENTS.md, y se
  carga en CADA sesión. Por eso cada sección tiene que ganarse el sitio: no está
  aquí lo que se pueda consultar (eso son documentos del cerebro), sino lo que
  evita que te vuelvan a preguntar lo que ya dijiste.

  Lo que NO va aquí, porque ya vive estructurado en otro lado:
    · personas          → fichas Persona en 02-areas/personas/
    · objetivos         → documentos Iniciativa; GOALS.md se genera solo
    · áreas             → carpetas de 02-areas/
    · reglas de trabajo → documentos Lineamiento
  Duplicarlos aquí es el defecto que v2 existe para eliminar.

  Está exento de los checks de perfil (`exempt_files`), así que se escribe en
  prosa libre: solo necesita frontmatter con `type` para ser conforme a OKF.
  Como nada lo valida, es el único archivo del cerebro que se pudre en silencio:
  revísalo cuando cambies de rol, de ciclo o de equipo.
-->

# Quién soy

<!-- TODO: /x-setup — nombre, rol, área, organización, y desde cuándo.

     La antigüedad calibra cuánto contexto de la organización se puede dar por
     sabido y cuánto hay que documentar desde cero.

     Añade también:
     · Qué entregables salen de tus manos (documentos, presentaciones, actas…).
       Son la salida del sistema: definen qué te sirve cuando consultas la base.
     · De todo eso, qué te da energía y qué sientes como trámite. No es una
       pregunta de satisfacción: marca dónde poner el énfasis cuando el agente
       tiene margen de criterio, y qué conviene resumir corto.
     · Contexto personal que afecte cómo se prioriza — zona horaria distinta al
       equipo, compromisos fijos. Opcional; si no hay nada, se deja vacío. -->

# Cómo trabajo

<!-- TODO: /x-setup — cuatro cosas, y las cuatro se usan a diario.

     1. EL FLUJO, de inicio a fin. Cómo nace un trabajo tuyo y qué pasos
        atraviesa hasta que se da por entregado. Es lo que permite al agente
        saber en qué etapa está cada proyecto y qué le falta para cerrarse, sin
        preguntártelo cada vez.

     2. DE QUIÉN RECIBES Y A QUIÉN ENTREGAS, por rol o área — no por nombre.
        Los nombres viven en las fichas Persona; repetirlos aquí los
        desincroniza. Esto define qué llega al inbox y de quién.

     3. TU CICLO DE PLANIFICACIÓN y su formato de periodo (trimestral →
        `2026-Q3`; mensual → `2026-08`; sprints → `2026-S14`). Es la decisión
        más estructural del perfil: de ella dependen el campo `periodo` de cada
        Iniciativa y las carpetas de `04-archivo/`. Escríbelo con un ejemplo
        literal y respétalo — hoy nada comprueba que no derive.

     4. RITUALES E HITOS FIJOS. Comités, weeklies, cierres. Son las fechas
        recurrentes contra las que /x-briefing-diario y /x-preparar-reunion
        pueden anticipar qué hay que tener listo en vez de reaccionar. -->

# Reglas de comunicación

<!-- TODO: /x-setup — cómo quieres que te hablen los agentes: extensión, tono,
     idioma si no es español.

     Y las manías de formato, que valen más de lo que parecen: qué prefieres en
     tabla y qué en prosa, si quieres emojis o no, si un documento para comité
     debe arrancar por la recomendación en vez de por el contexto. -->

# Lo que nunca se hace

<!-- TODO: /x-setup — tus líneas rojas de comportamiento. No es lo mismo que
     confidencialidad: aquello es qué información no entra, esto es qué no puede
     hacer un agente aunque la información esté.

     Ejemplos del tipo de regla que va aquí: no escribir en tu nombre como si
     fuera un mensaje ya enviado; no dar por cerrada una decisión que no
     confirmaste; no asumir la posición de otra área sin una fuente.

     El kernel ya trae la regla genérica —«mostrar antes de escribir»—, pero no
     puede saber cuáles son TUS límites. Esta sección es la que hace que el
     sistema se pueda dejar trabajar solo. -->

# Confidencialidad

<!-- TODO: /x-setup — las restricciones de TU organización, que van más allá de
     las del kernel.

     El kernel ya aplica lo que se puede aplicar: la clasificación tiene un
     mínimo por tipo y estar por debajo es siempre un error (V16), y la
     responsabilidad se resuelve contra fichas Persona (V17). Lo que se escribe
     aquí es lo que ninguna comprobación puede saber: qué nombres, qué sistemas
     o qué asuntos no entran en este cerebro.

     Recuerda que ninguna comprobación detecta un secreto pegado en una nota.
     Ante la duda, el dato sensible no entra. -->

# Estado actual

<!-- TODO: /x-setup — en qué estás ahora.

     Lo actualiza /x-actualizacion-semanal con fecha, y es la única sección de
     este archivo que se mantiene sola. Es lo que evita que los agentes te
     pregunten por algo que ya resolviste la semana pasada. -->
