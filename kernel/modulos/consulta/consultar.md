---
skill: x-consultar
description: 'Responde una pregunta usando solo lo que hay en el cerebro, con su fuente, y ofrece archivar la respuesta si hubo síntesis real.'
---

# Skill: Consultar (`/x-consultar`)

Responde una pregunta del usuario **usando solo el contenido del cerebro**. Conocimiento general
únicamente si él lo pide explícitamente, y dicho como lo que es: aportado por el modelo, no por
la base.

**Regla central: no fabricar.** Si la base no tiene la respuesta, la respuesta es «no está» — y
lo que se ofrece es abrir una `Pregunta` con su responsable, no un supuesto redactado con
seguridad. **Una respuesta plausible sin fuente es el peor resultado posible de este skill**,
porque se parece a la buena.

**Regla de zonas:** este skill lee todo el cerebro y escribe, como mucho, tres cosas: el
documento que se archive, una `Pregunta`, y su línea en `cerebro/log-consultas.md`.

---

## Fase 0 — La compuerta de intención

**Antes de abrir nada**, decidir de qué tipo es la pregunta. Una consulta que se responde sin el
cerebro no debe pagar la lectura del cerebro.

| Modo | Cuándo | Qué se abre |
|---|---|---|
| `directa` | La pregunta se responde sin la base: es general, o ya está respondida en esta misma conversación | **Nada.** Se responde y se registra |
| `acotada` | El enunciado nombra un tipo, un proyecto o una persona | Solo ese alcance, **declarado antes de buscar** |
| `abierta` | No hay ancla; hay que buscar de verdad | Fase 1 completa |

El modo se declara **antes** de buscar, no después: elegirlo a posteriori es describir lo que se
hizo, no decidirlo. Y se registra en la Fase 4, que es lo que permite saber después si la
compuerta sobra, si está mal calibrada, o cuánto ahorra.

**En `directa` se responde igual con honestidad:** si la respuesta viene del modelo y no de la
base, se dice. Es la misma regla de siempre, no una excepción.

---

## Fase 1 — Encontrar, y **abrir lo menos posible**

**Barrer el cerebro entero es el gasto que este sistema existe para evitar.** Pero el gasto no
está donde parece: encontrar cuesta el 5% de una consulta; **leer cuesta el 95%**. Por eso esta
fase tiene dos mitades, y la segunda importa más.

### 1.1 Encontrar — con la proyección, si está

```bash
./brain project                                  # deja la base al día (barato: solo lo que cambió)
./brain project --search "<término>"             # por texto: devuelve rutas y ranking, nunca contenido
```

Y para lo que no es texto libre, una consulta responde de una vez lo que navegar carpetas
responde a trozos:

| Lo que preguntas | Dónde mirar |
|---|---|
| Qué pasó en un proyecto entre dos fechas | vista `eventos` |
| Qué decisión o lineamiento regía en una fecha | vista `vigencia` |
| Qué caducó sin que nadie lo reemplazara | vista `vigencia`, estado `caducada` |
| Todo lo de un proyecto, sea del tipo que sea | vista `documento_proyecto` |

Las consultas exactas de cada pregunta frecuente están en `kernel/tests/competency-questions.yml`,
en la clave `sql:` — **no las inventes si ya están escritas.**

**Si no hay proyección** —no se ha corrido `project`, o este SQLite no trae FTS5— se navega por
índices, que siguen estando y siguen valiendo: `cerebro/index.md` y los de las carpetas
plausibles, `GOALS.md` y `PREGUNTAS-ABIERTAS.md` para lo que está en curso y lo que está sin
responder, `04-archivo/` solo si la pregunta es histórica, y los `log.md` solo para «¿qué pasó en
X las últimas semanas?».

Los índices y los derivados son artefactos generados: si alguno se ve viejo, se regenera antes de
sacar conclusiones de él —nunca se corrige a mano—, y si aun así falta, **eso es el hallazgo**: lo
que no está escrito no está en el cerebro.

### 1.2 Leer por niveles — el presupuesto

Encontrar diez candidatos no autoriza a abrir diez documentos. Se baja un nivel cada vez, y solo
para lo que el nivel anterior no descartó:

| Nivel | Qué es | Cuándo se abre |
|---|---|---|
| **L0** | `description`, una frase | Siempre: es lo que devuelve la consulta, gratis |
| **L1** | **`resumen`**, ~600 caracteres | Solo si el L0 no descartó el documento |
| **L2** | El cuerpo entero | Solo si el L1 tampoco. **Máximo 5 por consulta** |

L0 y L1 son **columnas de la proyección**: orientarse cuesta una consulta y no abre un archivo.

```sql
select path, type, title, description, resumen from documentos where …
```

**El tope no es lo que ahorra.** Cinco aperturas es exactamente lo que costaba una consulta antes
de que existiera el nivel intermedio, así que el tope no recorta nada por sí solo: lo que ahorra
es que el `resumen` permita abrir **menos de cinco**. El tope está ahí para que, cuando no
alcance, la respuesta lo diga en vez de disimularlo.

**Y si no alcanza, se dice.** Nombra qué quedó sin abrir. **Nunca respondas como si hubieras
leído lo que no abriste** — es la mitad de la disciplina de cita que ningún validador puede ver,
y la única defensa es que quien responde la cumpla.

> Las reglas exactas, con su tope, están declaradas en **`read_budget.agent_rules_es`** del
> contrato. Si este módulo y el contrato dijeran topes distintos, mandaría el contrato — y el
> round-trip comprueba que no se bifurquen.

---

## Fase 2 — Responder

- **Toda afirmación con su fuente**, como enlace bundle-relativo al documento, y a la decisión o
  la reunión concreta cuando la haya. Una respuesta sin enlaces no se distingue de una inventada.
- **La lista de fuentes se arma desde lo que abriste, no desde lo que recuerdes.** Lleva la cuenta
  de los documentos que abriste en esta sesión y construye `# Citations` **desde esa lista**. Es la
  única forma de que una cita no pueda salir de la memoria del modelo. Si no puedes armarla, **no
  respondas afirmando**: dilo y abre una `Pregunta`.
- **Solo se cita lo que existe.** Una cita que no resuelve a un documento del cerebro es una cita
  fabricada, y **V22 la rechaza**. Si el documento que querías citar no está escrito todavía, eso
  es un hueco declarado, no una cita.
- **Las contradicciones se dicen, no se resuelven en silencio.** Si dos páginas se contradicen,
  van las dos con sus fuentes y se señala cuál es más reciente. Elegir una por el usuario es
  quitarle la decisión sin avisarle.
- **Distinguir lo verificado de lo generado.** Un documento sin entrada `verified` de un actor
  `human:` es una propuesta, no conocimiento. Si la respuesta se apoya en uno, decirlo.
- **Y distinguir cómo entró cada cosa, que es otro eje.** `verified` dice **quién lo confirmó**;
  `procedencia` dice **cómo entró**. Un agente transcribiendo un PDF y un agente infiriendo de una
  discusión son el mismo actor con fiabilidad distinta, y `generated` no los separa.

  **Nunca mezcles en una misma lista, sin marca, lo leído de una fuente y lo inferido que nadie ha
  verificado.** Si la respuesta combina las dos cosas:

  | Lo que responde | Cómo se presenta |
  |---|---|
  | `procedencia: fuente` o `dialogo`, o con `verified` de una persona | Se afirma, con su cita |
  | `procedencia: inferido` **sin** `verified` humano | Se marca: «esto lo dedujo un agente y nadie lo ha confirmado» |

  Una vez mezcladas, ninguna revisión posterior las separa — la señal que las distinguía no se
  guardó en la respuesta. Es ADV-14, y es el motivo por el que `procedencia` existe.
- **Si la base no responde**, decirlo y ofrecer abrir la pregunta con el responsable probable
  según las fichas y el organigrama:
  ```bash
  ./brain place Pregunta proyecto=<slug>     # o proyecto=transversal
  ./brain template Pregunta
  ```
  Sin responsable claro, el campo queda vacío: es un hueco declarado, nunca un supuesto.
- **El formato lo decide la pregunta**: prosa para un porqué, tabla para una comparación,
  Mermaid para algo estructural. Los diagramas van siempre como texto.

---

## Fase 3 — Archivar, que es el paso que compone

Si la respuesta implicó **síntesis real** —comparar opciones, cruzar varios proyectos, escribir
una conexión que no estaba en ninguna página—, ofrecer archivarla:

> «¿Archivo este análisis como página, para que no se pierda?»

**Una respuesta trivial no se archiva.** Un dato puntual que ya estaba escrito en una ficha no
gana nada por copiarse a un documento nuevo: gana una segunda copia que se desactualiza.

Si acepta, el tipo depende de qué es la respuesta:

| Si la respuesta es… | Tipo |
|---|---|
| Un estudio de un asunto, para consultarlo como precedente | `Analisis` |
| Un proceso que se va a volver a seguir | `Playbook` |
| Una decisión que en realidad se tomó en la conversación | `Decision` |

**`Analisis` es el caso normal, no `Playbook`.** Un playbook se *sigue* otra vez; si el
documento no dice «la próxima vez, haz esto», no lo es. En v1 todo esto salía como `Playbook` y
esa mezcla es la que el contrato deshizo.

```bash
./brain place <Tipo> proyecto=<slug>
./brain template <Tipo>
```

El documento lleva **`# Citations` con las páginas usadas**: es lo que permite releerlo dentro de
seis meses sabiendo sobre qué se apoyaba. Después:

```bash
./brain index cerebro
./brain derive cerebro     # si se creó alguna Pregunta
./brain validate cerebro
```

Y la entrada en `cerebro/log.md`, porque aquí sí se escribió:
`**Consulta**: <título> archivado en <ruta>.`

---

## Fase 4 — Registrar la consulta

**Siempre, se haya archivado o no**, una línea en `cerebro/log-consultas.md` bajo su
`## AAAA-MM-DD`, lo más reciente arriba:

```markdown
- <la pregunta, en una línea> — <N> docs (<C> completos, <U> citados) · <modo> · archivada | no
```

**El formato no es libre: lo declara el contrato y lo comprueba V26**, porque la proyección del
corte 2 lee estas líneas para que CQ-45 y CQ-46 se puedan responder con SQL como cualquier otra
pregunta. Una línea mal formada no es un detalle de estilo: es un dato perdido.

| Campo | Qué es |
|---|---|
| `<N>` | Cuántos documentos se miraron en total |
| `<C>` | Cuántos se abrieron **enteros** |
| `<U>` | Cuántos de esos completos acabaron **sosteniendo una afirmación** de la respuesta — es decir, cuántos entraron en `# Citations` |
| `<modo>` | `directa` · `acotada` · `abierta`, el de la Fase 0 |

**`<U>` no se cuenta a ojo: es el tamaño de la lista de citas**, cruzada con las aperturas
completas. Por eso `<U>` nunca puede superar a `<C>` —citar lo que no se abrió es lo que prohíbe
la regla de citas— y **V26 lo rechaza** si ocurre.

No es burocracia: **v1 no registraba ninguna pregunta**, y sin eso hay tres cosas que no se
pueden saber mirando atrás — con qué frecuencia se pregunta cada cosa, cuántas consultas hay por
cada ingesta, y **cuánto de lo que se abre sobra**. Esa última, `<U>` contra `<C>`, es la que
decide dónde poner el tope de aperturas: hoy está en 5 a propósito, sin apretar, para que la
distribución real se pueda ver antes de recortarla.

**No escribas la razón `<U>/<C>`**: se calcula al consultar. Un derivado dentro de un log es lo
que este sistema no hace.

Una línea, sin prosa. Si la pregunta lleva un dato que el `PERFIL.md` marca como confidencial,
se registra el asunto, no el dato — **el texto de la pregunta no se proyecta**, solo los números,
pero la línea vive en el cerebro y se comparte con él.

---

## Lo que este skill NO hace, y por qué

| Qué | Quién lo hace en su lugar |
|---|---|
| Escribir los `index.md` que toque el documento archivado | `./brain index` |
| Añadir la pregunta nueva a `cerebro/PREGUNTAS-ABIERTAS.md` | `./brain derive` |
| Corregir a mano un índice o un derivado que se vea viejo | `./brain index` y `./brain derive`; editarlos se pierde en la siguiente corrida |
| Resolver una contradicción entre dos páginas | El usuario. El skill la expone con ambas fuentes; anotar la versión superada es `/x-curar` |
| Actualizar el `CONTEXT.md` o el `PLAN.md` de un proyecto con lo aprendido | `/x-actualizacion-semanal` o `/x-plan`. Consultar no reescribe el proyecto |
| Archivar cualquier respuesta | Solo las que tienen síntesis. Copiar un dato ya escrito crea una segunda fuente de verdad |
| Decidir el modo después de buscar | La Fase 0. Elegirlo a posteriori describe lo que pasó, no lo decide |
| Citar de memoria | La lista de aperturas. Una cita que no salga de ahí no se escribe |
