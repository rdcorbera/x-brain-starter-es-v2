# Cómo se construye X-Brain v2

Este archivo es para quien **construye el sistema**. Si lo que quieres es *usarlo*, tu punto de
entrada es [`INSTALL.md`](INSTALL.md) y luego [`kernel/GUIA-DE-USO.md`](kernel/GUIA-DE-USO.md).

Dos distinciones que cambian todo lo que se haga aquí:

- Aquí se escribe el **kernel**; el conocimiento vive en el repositorio de cada usuario.
- **Este starter nunca contiene conocimiento.** Un `raw/`, un `inbox/` o un `cerebro/` vacíos
  son lo esperado, no un síntoma. No se sacan conclusiones de adopción a partir de este repo.

**v1 está en producción, en un entorno bancario.** El incentivo del rediseño es que el consumo
de tokens crece con el cerebro. Todo lo que se construya aquí se juzga contra esa pendiente.

## Referencia: la v1

Clonada en `../x-brain-starter-es` (**kernel 1.4.0**), publicada en
https://github.com/rdcorbera/x-brain-starter-es. **Consúltala antes de rediseñar algo**:
`kernel/AGENTS.md`, `kernel/GUIA-DE-USO.md`, `kernel/esquema/okf.md`, `kernel/CHANGELOG.md`,
`kernel/modulos/`.

**v1 sigue avanzando mientras construimos v2** — la 1.4.0 llegó a mitad de trabajo y trajo el
tipo `Plan`. **Revisa su `CHANGELOG.md` al empezar cada tramo.**

Es referencia, no destino. Se reutiliza lo que probó funcionar, no lo que simplemente estaba
ahí. El inventario de qué se conservó y qué se sustituyó está en
[`tmp/inventario-reglas-v1.md`](tmp/inventario-reglas-v1.md).

## Reglas de trabajo

1. **Español** en documentación, contenido y conversación. **Inglés** en código y archivos de
   configuración (`.json`, `.yml`): identificadores, claves, comentarios y nombres de
   subcomando. No traducir código al español.
2. **La documentación se mantiene viva.** Al cerrar una decisión: la entrada va a
   [`tmp/BITACORA.md`](tmp/BITACORA.md); al avanzar un paso o cambiar el alcance:
   [`tmp/PLAN.md`](tmp/PLAN.md); al agregar una pieza visible: `README.md`. Todo en el mismo
   turno, nunca «para después».
3. **No inventar.** Si falta un dato, se pregunta o se anota en «Preguntas abiertas».
4. **Decisión antes que código.** Registrar en la bitácora qué se decidió y por qué. Las
   alternativas descartadas valen tanto como la elegida.
5. **La prosa se escribe al final.** Solo se puede borrar una regla cuando ya existe el código
   que la sustituye. Escribirla primero fue el error de v1: la prosa se volvió portante.
6. **Mostrar antes de escribir** cuando el cambio sea grande o toque archivos ya acordados.
7. **Sin commits automáticos.** Se hace commit cuando el usuario lo pida.

## Invariantes de la capa determinista

No negociables. Si un cambio los rompe, el cambio está mal.

1. **Nunca llama a un LLM.** Por eso puede correr en CI, en un hook, o cien veces seguidas.
2. **Cero dependencias.** Stdlib pura, **Python 3.11+**. En un entorno bancario con `pip`
   restringido esto no es una preferencia, es el requisito de que el sistema funcione. El piso
   lo fijan los requisitos, no el intérprete de fábrica de una máquina: 3.11 es la versión
   mínima que parsea un instante ISO 8601 completo (`stale_after`), y 3.9/3.10 están fuera de
   soporte. Excepción deliberada: **`survey.py` y `sqlite-probe.py` se quedan en 3.9**, porque
   son preflight y corren antes de que se instale nada. La extracción de PDF en `to-markdown.py`
   y la proyección SQLite del corte 2 son capas opcionales.
3. **Idempotente.** `generate` e `init` dos veces producen el mismo árbol. Los derivados se
   comparan por **cuerpo**, no por archivo completo: su frontmatter lleva un timestamp de
   generación.
4. **`--fix` solo hace cambios que preservan el significado**, y lo verifica en vez de
   asumirlo. Índices y derivados se regeneran; el frontmatter solo se entrecomilla, reparseando
   cada línea antes de escribirla. Nunca reescribe lo que una persona redactó.
5. **Un artefacto generado no se edita.** Se edita `kernel/schema/contract.json` y se regenera.
   **V14 lo comprueba.**
6. **El corte es por trabajos, y va en un solo sentido.** `const → parse → generate → validate → project` *(project entró con T5)*. El orden histórico era `const → parse → generate → validate
   → report`, y `brain.py` encima como CLI. Un módulo solo importa de los que tiene a su
   izquierda. Partir el archivo no sirve de nada si los módulos acaban importándose en círculo:
   sería el mismo archivo repartido en cinco. **`check_layering` lo comprueba**, incluidos los
   imports diferidos dentro de una función, que Python sí tolera.

## Convenciones

- Archivos y carpetas en **kebab-case**. Los valores de `type` conservan los que producción ya
  usa (`Reunion`, `Pregunta`…): cambiarlos sería migrar todos los cerebros.
- **Diagramas siempre como texto** (Mermaid), nunca solo imágenes.
- **Los comandos se escriben `./brain <sub>`**, nunca `python3 kernel/bin/brain.py`. No hay un
  nombre de intérprete portable: en Windows `python3` no existe y su alias abre la Microsoft
  Store. El lanzador de la raíz resuelve `py -3`, `python3` y `python`, y corre también los
  demás scripts: `./brain kernel/bin/to-markdown.py <archivo>`.
- **Nunca pruebes contra el `cerebro/` del repositorio.** Se versiona vacío a propósito, y
  `init`, `index` o `derive` lo llenan. Los temporales van al scratchpad.
- Nada de credenciales, secretos ni datos de terceros — tampoco en ejemplos. Los ejemplos usan
  datos ficticios y se marcan como tales.

## Contexto del rediseño

Todo el contexto para continuar vive en `tmp/`. **Léelo antes de retomar el trabajo** — no
reabras decisiones ya cerradas sin consultar la bitácora.

> **`tmp/` está en `.gitignore`**: es local a esta máquina y no se versiona, porque son notas
> del rediseño y no parte del starter que los usuarios clonan. En un clon estos archivos **no
> existen** — si trabajas desde otro sitio, pídelos. Y no hay historial: respáldalos aparte.

| Archivo | Qué es | Cuándo leerlo |
|---|---|---|
| `tmp/ESTADO-Y-PRUEBAS.md` | **El encargo de pruebas, reescrito el 2026-09-19.** El estado exacto de lo construido —corte 1 y 2 completos—, qué NO existe, cómo montar el entorno y qué probar por orden de valor. **La prueba de punta a punta sigue sin hacerse** | **Al retomar, después de `PLAN.md`** |
| `tmp/PLAN.md` | **El plan vigente.** Empieza por «Dónde estamos» y «Qué sigue». Diagnóstico de las dos pendientes, los 10 pasos con su estado, riesgos y preguntas abiertas —incluida la **deuda del contrato, que es lo único que se encarece con el tiempo** | **Lo primero, siempre.** Si algo lo contradice, manda este |
| `tmp/BITACORA.md` | Las decisiones cerradas con su razón y lo que se descartó | Antes de reabrir cualquier decisión de diseño |
| `tmp/inventario-reglas-v1.md` | Regla por regla de la prosa de v1, con su veredicto: sustituida, reducida o sobrevive | Al escribir o revisar prosa del kernel, y al construir los módulos |
| `tmp/plan-implementacion-x-brain-v2.md` | Propuesta del equipo. **Insumo, no plan** | Al retomar la proyección, hechos atómicos o capa semántica (cortes 2–3). Ojo: propone DuckDB, **descartado como motor** — la proyección se hace sobre SQLite |
| `tmp/plan-agent-zero-x-brain-v2.md` | El plan de implementación: las ideas del paper Agent Zero llevadas a tareas con criterio de aceptación. **Sus 13 tareas están cerradas** (T4–T11 entre el 13 y el 17 de septiembre); cada una conserva su enunciado original junto a lo que se entregó y lo que salió al construirla | Antes de tocar el contrato o la proyección: dice por qué cada cosa está como está |
| `tmp/competency-questions-research.md` | La revisión de literatura de la que salen las 24 CQs | Antes de tocar `competency-questions.yml`, o al discutir si un tipo se sostiene |
| `tmp/encargo-competency-questions.md` | El encargo con el que se pidieron las 24 CQs. **Formato de referencia** para cualquier encargo nuevo | Al escribir un encargo de investigación |
| `tmp/encargo-memoria-largo-plazo.md` | **RETIRADO el 2026-09-11.** No se mandan más encargos al equipo de investigación externo. Se conserva como registro; lo que pedía y no estaba respondido —el olvido y la capa de hechos— vive ahora en las preguntas abiertas de `tmp/PLAN.md` | Solo como registro histórico |
| `tmp/cerebro-survey.json` | La medición del cerebro real: 301 documentos, veredicto A/B, tipos, salud del frontmatter | Registro histórico: **la migración se canceló**. Sirve para el diagnóstico, no para planificar |
| `tmp/sqlite-results.json` | La sonda en la máquina de destino: SQLite 3.50.4, las 8 capacidades en verde. **El veredicto vigente es `viable: true`**, medido fuera de OneDrive; el JSON guardado es el de la primera corrida —con el cerebro aún dentro de OneDrive— y por eso dice `viable: false`. Volcar el de la corrida buena | Ya no bloquea nada: el corte 2 está construido y corre |
| `tmp/rediseño second brain primera investigacion.md` | Búsqueda agéntica, grafos ligeros, OKF v0.2, progressive disclosure | Al evaluar recuperación a escala |
| `tmp/rediseño second brain segunda investigacion.md` | Paradigmas alternativos y veredicto sobre Markdown-en-Git como fuente de verdad | Antes de reconsiderar la fuente de verdad |

### Cómo retomar

**Estado a 2026-09-19: corte 1 y corte 2 completos, y lo siguiente no es construir sino
probar.** Las 13 tareas del plan de implementación están cerradas. La implementación se detuvo el
2026-09-11 para probar de punta a punta, **no se probó**, y se construyó el corte 2 encima.

1. **Lee `tmp/PLAN.md`** — empieza por el recuadro «Dónde estamos» y por «Qué sigue», que traen
   el estado y el orden recomendado. La tabla de pasos dice qué está hecho y qué no.
2. **Luego `tmp/ESTADO-Y-PRUEBAS.md`**, que es el encargo de la prueba y está al día.
3. **Comprueba que todo sigue en verde** antes de tocar nada:
   ```bash
   ./brain kernel/tests/test_roundtrip.py   # el contrato es consistente consigo mismo
   ./brain generate                         # los artefactos generados, al día
   git diff --exit-code -- kernel/schema .claude .github/prompts   # no cambian al regenerar
   git status --porcelain -- cerebro        # vacío: el starter no versiona conocimiento
   ./brain verify-raw                       # los originales de raw/ no han cambiado
   ```
   El `git diff` va **acotado a lo generado**, no al árbol entero: mientras haya trabajo sin
   commitear, un `--exit-code` a secas falla siempre y deja de informar.

   El round-trip es ahora bastante más que un round-trip: además del contrato comprueba que el
   DDL lo acepta SQLite y deriva del contrato, que la proyección incremental dice lo mismo que
   `--full`, que el presupuesto de lectura no se bifurca, y que **las 42 competency questions
   corren** —las adversariales al revés, y cada una tiene que ver su propio defecto—.
4. **Revisa `kernel/CHANGELOG.md` de v1** — avanza mientras construimos.

### Una lección de estas dos semanas, que conviene no reaprender

**Cinco veces seguidas se escribió un control que no controlaba**, cada vez de una forma distinta:
la referencia salía de lo controlado (T6), la observación pasaba por un join que tapaba el fallo
(T7), el check no se ejercitaba en ninguna parte (T9, y antes V14 un corte entero), la consulta no
tenía datos que pudieran dispararla (T8), y se comprobaba que algo aparece sin comprobar que lo
contrario desaparece (T10).

**Un control se termina cuando se le ha visto fallar.** Si al escribir una comprobación no se
rompe a propósito lo que vigila, no se sabe si vigila — y las cinco veces el test estaba en verde.

## Preguntas abiertas

Viven en `tmp/PLAN.md`, junto a los riesgos. Las que bloquean trabajo hoy:

- ~~La **taxonomía de clasificación** es una propuesta nuestra~~ **Cerrado el 2026-09-16:** los
  cuatro niveles y los mínimos por tipo quedan como están y pasan a ser la taxonomía del sistema.
- **v2 no es retrocompatible con v1, y no habrá migración** *(decidido el 2026-09-16)*. Un cerebro
  de v1 no se convierte: su conocimiento se vuelve a cargar por `/x-procesar-inbox` o
  reconstruyéndolo desde `raw/`. **Consecuencia que conviene tener presente al tocar el kernel:**
  todo lo que el contrato conserva «por coste de migración» —los nombres con guion, `type-key`
  frente a enlaces, las tres formas de `periodo` sin declarar, las severidades relajadas «mientras
  el corpus migra»— se quedó sin ese argumento y vuelve a ser discutible por sus méritos.
- ~~**`Decision` tiene cero documentos en el cerebro real** (R8)~~ **Cerrado el 2026-09-12.** El
  vacío se atribuye al **nivel de pruebas de v1**, escaso o nulo, no al diseño del tipo: v1 nunca
  ejercitó una ingesta verificando qué tipos debía producir. Lo que sustituye a la encuesta a los
  pilotos es la **batería de pruebas de v2**, que comprueba sobre un cerebro temporal que una
  ingesta genera los tipos que corresponden, `Decision` incluido. **Deja de ser precondición del
  corte 2.** Si tras esas pruebas el tipo siguiera sin aparecer sobre material real, se reabre —
  con evidencia de v2, no heredada de v1.
- ~~**El formato de `periodo` vive en prosa**~~ **Cerrado (2026-09-03)**: vive en
  `cerebro/schema.json` como `period_format`, con tres formas del kernel, y lo comprueba V21.
