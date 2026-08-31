# X-Brain v2 — instrucciones para Claude Code

## Qué es este repositorio

El **starter en construcción** de X-Brain v2. Dos distinciones que cambian todo lo que hagas aquí:

- Estamos **construyendo el sistema**, no operando un cerebro. Aquí se escribe el kernel; el conocimiento vive en el repositorio de cada usuario.
- **Este starter nunca contiene conocimiento.** Un `raw/` o un `inbox/` vacíos son lo esperado, no un síntoma. No saques conclusiones de adopción a partir de este repo ni de los starters anteriores.

**v1 está en producción, en un entorno bancario, con más de 10.000 documentos.** El incentivo del rediseño es que el consumo de tokens crece con el cerebro. Todo lo que se construya aquí se juzga contra esa pendiente.

## Referencia: la v1

Clonada en `../x-brain-starter-es` (**kernel 1.4.0**), publicada en https://github.com/rdcorbera/x-brain-starter-es. **Consúltala antes de rediseñar algo**: `kernel/AGENTS.md`, `kernel/GUIA-DE-USO.md`, `kernel/esquema/okf.md`, `kernel/CHANGELOG.md`, `kernel/modulos/`. Sus 11 plantillas son la especificación de facto de la que salió el contrato de v2.

**v1 sigue avanzando mientras construimos v2.** La 1.4.0 llegó a mitad de trabajo y trajo el tipo `Plan`. **Revisa `kernel/CHANGELOG.md` de v1 al empezar cada tramo** — sobre todo antes del paso 7, donde se escribe prosa contra un sistema que puede haber cambiado.

Es referencia, no destino. Reutiliza lo que probó funcionar, no lo que simplemente estaba ahí.

## Reglas de trabajo

1. **Español** en documentación, contenido y conversación. **Inglés** en código y archivos de configuración (`.json`, `.yml`): identificadores, claves, comentarios y nombres de subcomando. No traducir código al español.
2. **La documentación se mantiene viva.** Al cerrar una decisión: la entrada va a [`tmp/BITACORA.md`](tmp/BITACORA.md); al avanzar un paso o cambiar el alcance: [`tmp/PLAN.md`](tmp/PLAN.md); al agregar una pieza visible: `README.md`. Todo en el mismo turno, nunca «para después».
3. **No inventar.** Si falta un dato, se pregunta o se anota en «Preguntas abiertas».
4. **Decisión antes que código.** Registrar en la bitácora qué se decidió y por qué. Las alternativas descartadas valen tanto como la elegida.
5. **La prosa se escribe al final.** Solo se puede borrar una regla cuando ya existe el código que la sustituye. Escribirla primero fue el error de v1: la prosa se volvió portante.
6. **Mostrar antes de escribir** cuando el cambio sea grande o toque archivos ya acordados.
7. **Sin commits automáticos.** Se hace commit cuando el usuario lo pida.

## Invariantes de la capa determinista

No negociables. Si un cambio los rompe, el cambio está mal.

1. **Nunca llama a un LLM.** Por eso puede correr en CI, en un hook, o cien veces seguidas.
2. **Cero dependencias.** Stdlib pura, **Python 3.11+**. En un entorno bancario con `pip` restringido esto no es una preferencia, es el requisito de que el sistema funcione. El piso lo fijan los requisitos, no el intérprete de fábrica de una máquina: 3.11 es la versión mínima que parsea un instante ISO 8601 completo (`stale_after`), y 3.9/3.10 están fuera de soporte. Excepción deliberada: **`survey.py` se queda en 3.9**, porque es el preflight y corre antes de que se instale nada. El conversor de binarios y la proyección SQLite del corte 2 son capas opcionales.
3. **Idempotente.** `generate` dos veces produce el mismo árbol. Los derivados se comparan por **cuerpo**, no por archivo completo: su frontmatter lleva un timestamp de generación.
4. **`--fix` solo hace cambios que preservan el significado**, y lo verifica en vez de asumirlo. Índices y derivados se regeneran; el frontmatter solo se entrecomilla, reparseando cada línea antes de escribirla. Nunca reescribe lo que una persona redactó.
5. **Un artefacto generado no se edita.** Se edita `kernel/schema/contract.json` y se regenera.

## Convenciones

- Archivos y carpetas en **kebab-case**. Los valores de `type` conservan los que producción ya usa (`Reunion`, `Pregunta`…): cambiarlos sería migrar todos los cerebros.
- **Diagramas siempre como texto** (Mermaid), nunca solo imágenes.
- Nada de credenciales, secretos ni datos de terceros — tampoco en ejemplos. Los ejemplos usan datos ficticios y se marcan como tales.

## Contexto del rediseño

Todo el contexto para continuar vive en `tmp/`. **Léelo antes de retomar el trabajo**
— no reabras decisiones ya cerradas sin consultar la bitácora.

> **`tmp/` está en `.gitignore`**: es local a esta máquina y no se versiona, porque son notas
> del rediseño y no parte del starter que los usuarios clonan. En un clon estos archivos **no
> existen** — si trabajas desde otro sitio, pídelos. Y no hay historial: respáldalos aparte.

| Archivo | Qué es | Cuándo leerlo |
|---|---|---|
| [tmp/PLAN.md](tmp/PLAN.md) | **El plan vigente.** Diagnóstico de las dos pendientes, los 10 pasos con su estado, riesgos y preguntas abiertas | Siempre, al retomar. Si algo lo contradice, manda este |
| [tmp/BITACORA.md](tmp/BITACORA.md) | 22 decisiones cerradas con su razón y lo que se descartó | Antes de reabrir cualquier decisión de diseño |
| [tmp/plan-implementacion-x-brain-v2.md](tmp/plan-implementacion-x-brain-v2.md) | Propuesta del equipo. **Insumo, no plan** — evaluada y adoptada en parte | Al retomar la proyección, hechos atómicos o capa semántica (cortes 2–3). Ojo: propone DuckDB, y el motor se decidió SQLite |
| [tmp/rediseño second brain primera investigacion.md](tmp/rediseño%20second%20brain%20primera%20investigacion.md) | Investigación: búsqueda agéntica, grafos ligeros, OKF v0.2, progressive disclosure | Al evaluar recuperación a escala |
| [tmp/rediseño second brain segunda investigacion.md](tmp/rediseño%20second%20brain%20segunda%20investigacion.md) | Investigación: paradigmas alternativos y veredicto sobre Markdown-en-Git como fuente de verdad | Antes de reconsiderar la fuente de verdad |

### Cómo retomar

1. **Lee [tmp/PLAN.md](tmp/PLAN.md)** — la tabla de pasos dice qué está hecho y qué no.
2. **Comprueba que todo sigue en verde** antes de tocar nada:
   ```bash
   python3 kernel/tests/test_roundtrip.py     # contrato consistente consigo mismo
   python3 kernel/bin/brain.py generate       # los artefactos generados, al día
   ```
3. **Revisa `kernel/CHANGELOG.md` de v1** — avanza mientras construimos; la 1.4.0 llegó a
   mitad de sesión y trajo un tipo nuevo.

**El paso 0 está cerrado** (2026-08-31). El survey sobre el cerebro real dio **A domina
8,7×**: el plan está bien ordenado y la prosa del kernel (paso 7) se escribe sobre este sistema,
sin adelantar la proyección. Las competency questions ya no son un borrador: 24 más 12
adversariales, verificadas contra el contrato. La proyección del corte 2 se hará sobre **SQLite**,
verificado en la máquina de destino.

**Lo que bloquea hoy:** dos decisiones de catálogo que la prosa del paso 7 tiene que describir —
qué pasa con `Glosario` y cómo se llama el tipo escindido de `Playbook`. Y `R8`: `Decision` tiene
cero documentos en el cerebro real, diferido a propósito hasta que los skills se prueben con datos
ficticios (paso 8).

## Preguntas abiertas

Viven en [tmp/PLAN.md](tmp/PLAN.md), junto a los riesgos. Las que bloquean trabajo hoy:
la **taxonomía de clasificación** es una propuesta nuestra y conviene validarla con
gobierno de datos **antes** de migrar el corpus; y `governance.steward` sigue en TODO —
un artefacto gobernado sin dueño no está gobernado.
