---
title: Arquitecto de Tecnología
kind: individual
description: Evalúa opciones, registra decisiones y sostiene los estándares que otros equipos siguen.
period_format: quarterly
areas: [dominios-y-capacidades, estandares-y-tecnologia]
---

<!--
  Este PERFIL.md se sembró con el profile `arquitecto-de-tecnologia`.

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

Decido cómo se construye, y sostengo esas decisiones en el tiempo. Lo que sale de mis manos:

- Decisiones de arquitectura registradas, con las alternativas que se descartaron y por qué.
- Diagramas de lo que existe y de lo que se propone.
- Estándares y lineamientos que otros equipos siguen.
- Evaluaciones de tecnología y de proveedores.

<!-- TODO: /x-setup — de todo eso, qué te da energía y qué sientes como trámite.
     No es una pregunta de satisfacción: marca dónde poner el énfasis cuando el
     agente tiene margen de criterio, y qué conviene resumir corto.

     Y el contexto personal que afecte cómo se prioriza — zona horaria distinta
     al equipo, compromisos fijos. Si no hay nada, se deja vacío. -->

# Cómo trabajo

**El flujo.** Un trabajo mío nace como necesidad de negocio o como tensión técnica, y atraviesa:
entender la necesidad → levantar el estado actual → evaluar opciones con sus concesiones →
decidir y registrar la decisión → convertirla en estándar → acompañar a los equipos que la
aplican. No está entregado cuando se decide: lo está cuando algo construido la sigue.

**De quién recibo y a quién entrego.** Recibo de negocio y de los equipos de ingeniería —lo que
hace falta y lo que duele—, y de proveedores cuando se evalúa comprar. Entrego a los equipos que
construyen y al comité que aprueba.

<!-- TODO: /x-setup — ajusta los roles anteriores a tu organización, y añade los
     que falten. Van por ROL o área, nunca por nombre: los nombres viven en las
     fichas Persona y repetirlos aquí los desincroniza. -->

**El ciclo.** Trimestral, porque una decisión de arquitectura tarda más de un sprint en
demostrar si era buena.

<!-- TODO: /x-setup — cada cuánto cierras y qué pasa en el cierre. El FORMATO no
     se escribe aquí: va como `period_format` en `cerebro/schema.json`. Este profile
     propone uno, y `./brain init --profile` lo imprime al aplicarlo;
     confírmalo o cámbialo. -->

**Rituales fijos.** Comité de arquitectura, revisiones de diseño con los equipos, y el cierre
trimestral.

<!-- TODO: /x-setup — confirma cuáles tienes de verdad, con su cadencia, y quita
     los que no. Son las fechas contra las que /x-briefing-diario y
     /x-preparar-reunion anticipan en vez de reaccionar. -->

# Reglas de comunicación

**La recomendación primero, el contexto después.** Un documento mío que empieza por los
antecedentes obliga a leerlo entero para saber qué se propone; empezar por la recomendación deja
elegir cuánto profundizar.

- Toda opción evaluada se presenta con lo que se gana y lo que se cede. Una opción sin coste
  declarado no está evaluada.
- Los diagramas, siempre como texto (Mermaid), nunca solo como imagen.
- Las comparaciones entre alternativas, en tabla.

<!-- TODO: /x-setup — ajústalo. Extensión, tono, idioma si no es español, y tus
     manías de formato, que valen más de lo que parecen. -->

# Lo que nunca se hace

- **No cerrar una decisión sin registrar las alternativas descartadas.** Lo descartado vale
  tanto como lo elegido: sin eso, dentro de un año nadie sabrá si la opción obvia ya se estudió,
  y se volverá a estudiar.
- **No proponer arquitectura sobre un sistema sin haber levantado cómo está hoy.** Lo que se
  documentó hace dos años y lo que corre ahora no son lo mismo.
- **No presentar una posición de otra área sin una fuente.** Si no está confirmada, es una
  `Pregunta`, no un supuesto.
- **No dar por adoptado un estándar que nadie ha aplicado todavía.** Escrito y adoptado son
  estados distintos.

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
     puede saber: qué sistemas, qué proveedores o qué asuntos no entran.

     Para este rol conviene decidirlo explícitamente: condiciones comerciales de
     un contrato con proveedor, evaluaciones que nombran a competidores, y
     debilidades conocidas de un sistema que sigue en producción.

     Y por encima de todo: ninguna comprobación detecta un secreto pegado en una
     nota. Credenciales y tokens no entran nunca. Ante la duda, no entra. -->

# Estado actual

<!-- TODO: /x-setup — en qué estás ahora.

     Lo actualiza /x-actualizacion-semanal con fecha, y es la única sección de
     este archivo que se mantiene sola. -->
