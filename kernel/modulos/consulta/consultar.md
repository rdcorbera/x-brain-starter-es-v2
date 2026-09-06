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

## Fase 1 — Buscar por los índices, nunca a ciegas

**Barrer el cerebro entero es el gasto que este sistema existe para evitar.** El orden importa:

| Paso | Dónde | Para qué |
|---|---|---|
| 1 | `cerebro/index.md` y los `index.md` de las carpetas plausibles | Ubicar candidatos por título y descripción, sin abrirlos |
| 2 | `cerebro/GOALS.md` y `cerebro/PREGUNTAS-ABIERTAS.md` | Lo que está en curso y lo que está sin responder, ya agregados |
| 3 | Solo las páginas prometedoras | `CONTEXT.md`, decisiones, fichas de `Sistema` y `Persona`, lineamientos, reuniones |
| 4 | `cerebro/04-archivo/` | Solo si la pregunta es histórica |
| 5 | Los `log.md` | Solo para preguntas del tipo «¿qué pasó en X las últimas semanas?» |

Los índices y los derivados son artefactos generados: están al día porque `./brain index` y
`./brain derive` los reescriben. Si alguno se ve viejo, se regenera antes de sacar conclusiones
de él —no se corrige a mano—, y si aun así falta, **eso es el hallazgo**: lo que no está escrito
no está en el cerebro.

> **Hoy esto es navegación, y se sabe.** Encontrar los documentos relevantes entre N es la
> Pendiente B del rediseño, y su sustituto —una proyección consultable— es el corte 2. Hasta
> entonces se navega por índices, que es lo que los hace valer.

---

## Fase 2 — Responder

- **Toda afirmación con su fuente**, como enlace bundle-relativo al documento, y a la decisión o
  la reunión concreta cuando la haya. Una respuesta sin enlaces no se distingue de una inventada.
- **Las contradicciones se dicen, no se resuelven en silencio.** Si dos páginas se contradicen,
  van las dos con sus fuentes y se señala cuál es más reciente. Elegir una por el usuario es
  quitarle la decisión sin avisarle.
- **Distinguir lo verificado de lo generado.** Un documento sin entrada `verified` de un actor
  `human:` es una propuesta, no conocimiento. Si la respuesta se apoya en uno, decirlo.
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
- <la pregunta, en una línea> — <N> docs · archivada | no
```

No es burocracia: **v1 no registraba ninguna pregunta**, y sin eso hay dos cosas que no se
pueden saber mirando atrás — con qué frecuencia se pregunta cada cosa, y cuántas consultas hay
por cada ingesta, que es lo que decide cuándo conviene la proyección consultable del corte 2. El
`N` de documentos abiertos es la medida directa de lo que cuesta hoy navegar índices.

Una línea, sin prosa. Si la pregunta lleva un dato que el `PERFIL.md` marca como confidencial,
se registra el asunto, no el dato.

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
