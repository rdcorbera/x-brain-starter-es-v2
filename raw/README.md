# raw — las fuentes crudas

Los originales de todo lo que entró al cerebro, **inmutables y en un solo lugar**. Cada archivo
se nombra `AAAA-MM-DD-descripcion-uuid.ext` y tiene su fila en [`manifiesto.md`](manifiesto.md).

## Las reglas, que son tres y no admiten excepción

1. **Nada se edita.** Ni se corrige, ni se renombra, ni se reorganiza. El wiki los cita; jamás
   los reemplaza.
2. **Nada se borra.** Aunque parezca redundante o superado.
3. **Solo escribe `/x-procesar-inbox`.** Es la única vía por la que algo llega aquí.

## Por qué

Es el seguro del sistema. Con `raw/` y su manifiesto se puede **reconstruir el cerebro entero**
(`/x-reconstruir`) si algo se corrompe o si quieres rehacerlo con criterios nuevos. Y es lo que
permite que una afirmación del wiki se pueda contrastar contra lo que realmente decía la fuente.

Los documentos del cerebro apuntan aquí con enlaces que empiezan por `/raw/...`. Ese prefijo
apunta **fuera** del bundle a propósito: si compartes tu `cerebro/` sin sus fuentes, esos
enlaces quedan rotos y es esperado — el conocimiento integrado sigue completo.
