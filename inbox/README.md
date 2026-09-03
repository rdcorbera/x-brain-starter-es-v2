# inbox — la puerta de entrada

Suelta aquí **todo** lo que quieras que entre al cerebro: transcripciones, documentos
recibidos, notas sueltas, capturas de documentación. Luego corre `/x-procesar-inbox`.

**Es transitoria.** Se vacía al procesar: cada original se archiva en `raw/` con su fila en el
manifiesto, y el conocimiento integrado queda en `cerebro/`. Nada debería quedarse aquí más de
un día — el valor está en lo integrado, no en el material acumulado.

## Dos cosas que ahorran preguntas

**Agrupa por destino.** Si sueltas una carpeta con el nombre de un proyecto o de un área
(`inbox/migracion-erp/`), todo lo que cuelgue de ella se atribuye ahí sin que te pregunten
archivo por archivo. El nombre no tiene que ser exacto.

**No hace falta nombrar prolijo**, pero evita `notas3.txt`: el nombre es de lo poco que ayuda a
clasificar antes de leer el contenido.

## Formatos

Texto plano (`.md`, `.txt`, `.vtt`) entra directo. Los adjuntos de Office, `.drawio`, `.html` y
`.yaml` se convierten solos y **sin instalar nada**; el `.pdf` es el único que necesita una
dependencia. Los binarios anteriores a 2007 (`.doc`, `.ppt`, `.xls`) no se pueden leer: ábrelos
en Office y usa «Guardar como».

Detalle en [`kernel/GUIA-DE-USO.md`](../kernel/GUIA-DE-USO.md), sección 2.
