---
skill: x-cosechar
description: 'Al cerrar una iniciativa, propone qué conocimiento promover a un área permanente y qué se archiva tal cual.'
---

# Skill: Cosechar (`/x-cosechar`)

Una iniciativa que se cierra se lleva consigo lo que se aprendió en ella. Este skill lo saca antes
de que eso pase: recorre lo que produjo, **propone** qué merece vivir fuera del proyecto, y deja
que la persona decida pieza por pieza.

**Lo que no es.** No es archivar —eso lo hace `/x-cierre-periodo`— ni resumir el proyecto. Es
decidir qué sobrevive al proyecto, que es una pregunta distinta y la contesta una persona.

**Regla central: propone, nunca promueve solo.** Escribir sin confirmación aquí es peor que en
otros sitios: promover convierte una conclusión de un proyecto concreto en una regla del área, que
otros leerán fuera de su contexto. **Una promoción equivocada no ensucia: desinforma.**

**Regla de zonas:** escribe en `cerebro/` y en ningún otro sitio.

**Usa el modelo más capaz que tengas.** Todo el valor está en la Fase 2: separar lo que valía para
este proyecto de lo que vale para el área.

---

## Fase 0 — Qué se cierra

Se pide el proyecto si no viene en la invocación. Debe existir y su `CONTEXT.md` debe estar
`estado: entregada` o a punto de estarlo.

```bash
./brain place Iniciativa proyecto=<slug>        # dónde vive
```

**Si la iniciativa no está entregada, se dice y se pregunta** si se cosecha igualmente. Cosechar
un proyecto vivo es legítimo —a mitad de camino ya hay aprendizajes— pero conviene que sea una
decisión y no un descuido.

---

## Fase 1 — Inventario

Se listan, sin abrirlos enteros, los documentos que produjo la iniciativa. Con la proyección al
día, esto es una consulta y no un recorrido de carpetas:

```bash
./brain project                                 # deja la base al día
```

```sql
select d.type, d.title, d.path, d.resumen
from documentos d join documento_proyecto p on p.doc = d.path
where p.proyecto = '<slug>' and d.type in ('Decision', 'Analisis', 'Pregunta', 'Playbook')
order by d.type;
```

**El `resumen` es justo para esto:** permite descartar sin abrir. Solo se abren enteros los
candidatos reales, y **el tope son 5**; si hicieran falta más, es que el criterio de la Fase 2 no
está claro todavía.

Las `Pregunta` entran **solo si están respondidas**: una pregunta abierta no es un aprendizaje, es
trabajo pendiente, y al cerrar la iniciativa hay que decidir si muere con ella o se reabre en otro
sitio. Eso se pregunta aparte.

---

## Fase 2 — Qué merece salir del proyecto

Es la fase que exige juicio, y la única prueba que hay que pasar es esta:

> **¿Esto seguiría siendo cierto en el próximo proyecto, con otra gente y otro contexto?**

| Se promueve | Se queda en el proyecto |
|---|---|
| Una regla que se aplicará otra vez — pasa a `Lineamiento` | La decisión de usar X *en este proyecto*, por sus plazos |
| Un procedimiento que funcionó y se repetirá — pasa a `Playbook` | El análisis de una alternativa que solo tenía sentido aquí |
| Un hecho estable sobre un sistema o un área — enriquece su ficha | Lo que ya cambió desde que se escribió |
| Un término que el equipo usa — pasa a `Glosario` | Lo que solo es cierto para este cliente o este trimestre |

**Dos trampas, dichas por su nombre:**

- **Promover una decisión tal cual.** Una `Decision` responde *qué hicimos y por qué*, atada a su
  contexto. Un `Lineamiento` responde *qué hacemos siempre*. Mover el documento de carpeta no lo
  convierte en el otro: hay que **reescribirlo** como regla, y si al reescribirlo no queda nada
  que valga fuera del proyecto, es que no había nada que promover.
- **Promover lo que no se cumplió.** Que algo se decidiera no significa que funcionara. Si el
  proyecto no confirmó que la regla sirve, se dice y se propone como `Lineamiento` en
  `estado: en-revision`, no como aprobado.

**Lo que no se promueve no se descarta: se archiva igual**, con la iniciativa. Queda consultable
donde está — no promover nunca significa borrar.

---

## Fase 3 — Proponer, y esperar

Se muestra una tabla y **se para**:

| Origen | Qué se propone | Tipo destino | Dónde iría | Por qué sale del proyecto |
|---|---|---|---|---|
| `dec-003-formato-de-actas.md` | «Las actas se publican dentro de las 24 h» | `Lineamiento` | `02-areas/operaciones/` | Se cumplió las 9 veces y no depende del proyecto |

**Cada fila se confirma por separado.** Un «sí» global no vale: la persona tiene que poder aceptar
tres de cinco. Y si duda de una, **esa no se promueve** — lo que no se promueve hoy sigue ahí para
promoverse mañana; lo promovido mal hay que encontrarlo primero para poder retirarlo.

---

## Fase 4 — Escribir lo confirmado

Por cada promoción aceptada:

```bash
./brain template <Tipo>                         # los campos exactos
./brain place <Tipo> area=<area>                # dónde va
```

1. **Se redacta como el tipo destino**, no se copia el original. Un `Lineamiento` empieza por la
   regla, no por el contexto en que se descubrió.
2. **Conserva el enlace a su origen**, y esto no es cortesía: es lo que permite responder «¿de
   dónde salió esta regla?» dentro de un año, cuando nadie recuerde el proyecto.
   ```yaml
   sources: [{resource: /01-proyectos/<slug>/02-decisiones/dec-003-formato-de-actas.md}]
   ```
   Va en `sources` y no en el cuerpo porque ahí es consultable: es lo que hace que CQ-50 pueda
   distinguir una iniciativa cosechada de una archivada en crudo.
3. **`procedencia: derivado`** — la regla no se leyó de una fuente ni se dijo en una reunión: se
   destiló de lo que produjo el proyecto.
4. **Se sella el resumen**: `./brain hash <archivo> --body --write`.
5. **En el documento de origen se deja el puntero de vuelta**, una línea bajo `# Consecuencias` o
   la sección equivalente: `Promovido a [<título>](/02-areas/<area>/<archivo>.md) al cerrar la
   iniciativa.` Sin eso, la genealogía solo se puede recorrer en un sentido.

**Al terminar:**

```bash
./brain validate cerebro                        # V10 y V20 en verde: los enlaces resuelven
./brain index && ./brain derive                 # los índices del área destino
./brain project                                 # la proyección, al día
```

Y **la entrada en los dos `log.md`** —el del proyecto y el global—: quien escribe, loguea. Una
línea por promoción, con origen y destino.

---

## Fase 5 — Qué quedó sin cosechar

Se dice en voz alta, porque es la mitad que se olvida:

- **Preguntas respondidas que no se promovieron** y por qué.
- **Preguntas abiertas que mueren con la iniciativa**: se pregunta si alguna debe reabrirse en
  otro proyecto o pasar a un área. Una pregunta abierta que se archiva sin decidirlo es un hueco
  que nadie volverá a ver.
- **Si no se promovió nada**, se dice claramente. Es un resultado legítimo —hay proyectos que no
  dejan nada reutilizable— pero tiene que ser una conclusión, no un silencio. CQ-50 pregunta
  exactamente por eso: iniciativas cerradas sin nada promovido.
