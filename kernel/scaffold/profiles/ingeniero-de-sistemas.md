---
title: Ingeniero de Sistemas
kind: individual
description: Construye y opera software. Trabaja por sprints, entrega código y lo sostiene en producción.
period_format: sprint
areas: [servicios-y-componentes, operacion-y-guardias]
---

<!--
  Este PERFIL.md se sembró con el profile `ingeniero-de-sistemas`.

  Lo que hay escrito es lo que es cierto del ROL, no de ti: son PROPUESTAS que
  /x-setup te pasa por delante para que las ajustes, no afirmaciones sobre tu
  organización. Lo que ningún profile puede saber sigue marcado como TODO.

  A partir de aquí el archivo es tuyo: se edita a mano y no lo regenera nadie.
  Si quieres un molde propio, copia kernel/scaffold/profiles/ a plugins/profiles/
  y edítalo ahí — el kernel no se toca.
-->

# Quién soy

<!-- TODO: /x-setup — nombre, organización y desde cuándo. La antigüedad calibra
     cuánto contexto se puede dar por sabido y cuánto hay que documentar. -->

Construyo y opero software. Lo que sale de mis manos:

- Código en producción, con sus pruebas.
- Diseños técnicos de lo que voy a construir, antes de construirlo.
- Runbooks y post-mortems de lo que operamos.
- Revisiones del código de otros.

<!-- TODO: /x-setup — de todo eso, qué te da energía y qué sientes como trámite.
     No es una pregunta de satisfacción: marca dónde poner el énfasis cuando el
     agente tiene margen de criterio, y qué conviene resumir corto.

     Y el contexto personal que afecte cómo se prioriza — zona horaria distinta
     al equipo, compromisos fijos, turnos de guardia. Si no hay nada, se deja. -->

# Cómo trabajo

**El flujo.** Un trabajo mío nace como historia o incidente, y atraviesa: entender el problema →
diseño técnico si no es trivial → implementación → revisión de pares → despliegue → operación.
No está entregado cuando el código se fusiona: lo está cuando corre en producción y se comporta.

**De quién recibo y a quién entrego.** Recibo de producto y del líder técnico —qué hay que
construir y con qué prioridad—, y de operación cuando algo falla. Entrego al equipo, mediante
revisión de pares, y a quien opere el servicio después.

<!-- TODO: /x-setup — ajusta los roles anteriores a tu organización, y añade los
     que falten. Van por ROL o área, nunca por nombre: los nombres viven en las
     fichas Persona y repetirlos aquí los desincroniza. -->

**El ciclo.** Trabajo por sprints. Al cerrar cada uno, lo que quedó a medias se replantea en vez
de arrastrarse en silencio.

<!-- TODO: /x-setup — cada cuánto cierras y qué pasa en el cierre. El FORMATO no
     se escribe aquí: va como `period_format` en `cerebro/schema.json`. Este profile
     propone uno, y `./brain init --profile` lo imprime al aplicarlo;
     confírmalo o cámbialo. -->

**Rituales fijos.** Daily del equipo, planificación al abrir el sprint, revisión y retrospectiva
al cerrarlo.

<!-- TODO: /x-setup — confirma cuáles tienes de verdad, con su cadencia, y quita
     los que no. Son las fechas contra las que /x-briefing-diario y
     /x-preparar-reunion anticipan en vez de reaccionar. Si estás en rotación de
     guardias, dilo aquí: cambia qué es urgente. -->

# Reglas de comunicación

Conciso y técnico. Sin rodeos ni preámbulos: la conclusión primero y el razonamiento después,
para poder parar de leer cuando ya sé lo que necesito.

- El código y los comandos, en bloques, nunca parafraseados en prosa.
- Los errores, con el mensaje literal y su traza: un error reescrito con otras palabras cuesta
  más de diagnosticar que el original.
- Las comparaciones entre opciones, en tabla.

<!-- TODO: /x-setup — ajústalo. Extensión, tono, idioma si no es español, y tus
     manías de formato, que valen más de lo que parecen. -->

# Lo que nunca se hace

- **No dar por desplegado lo que no está en producción.** Fusionado, aprobado y desplegado son
  tres estados distintos, y confundirlos es lo que hace que alguien crea que un fallo ya está
  corregido cuando no lo está.
- **No proponer un cambio en un sistema sin haber mirado cómo está hoy.** Lo que se recuerda de
  un servicio y lo que el servicio hace divergen.
- **No cerrar un incidente sin su causa.** Si la causa no se encontró, eso es lo que se escribe:
  un incidente cerrado sin causa se repite.

<!-- TODO: /x-setup — tus líneas rojas. No es confidencialidad —aquello es qué
     información no entra, esto es qué no puede hacerse aunque la información
     esté. El kernel ya trae la regla genérica «mostrar antes de escribir», pero
     no puede saber cuáles son TUS límites. -->

# Confidencialidad

<!-- TODO: /x-setup — las restricciones de TU organización, que van más allá de
     las del kernel.

     El kernel ya aplica lo aplicable: la clasificación tiene un mínimo por tipo
     y estar por debajo es siempre un error (V16), y la responsabilidad se
     resuelve contra fichas Persona (V17). Aquí va lo que ninguna comprobación
     puede saber: qué sistemas, qué clientes o qué asuntos no entran.

     Para este rol conviene decidirlo explícitamente: datos de producción en un
     ejemplo, cadenas de conexión en un runbook, detalles de una vulnerabilidad
     todavía sin parchear.

     Y por encima de todo: ninguna comprobación detecta un secreto pegado en una
     nota. Credenciales y tokens no entran nunca. Ante la duda, no entra. -->

# Estado actual

<!-- TODO: /x-setup — en qué estás ahora.

     Lo actualiza /x-actualizacion-semanal con fecha, y es la única sección de
     este archivo que se mantiene sola. -->
