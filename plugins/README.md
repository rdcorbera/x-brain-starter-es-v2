# plugins — tus extensiones

Esta zona es **tuya**. El kernel no la toca y ninguna actualización la sobrescribe.

| Carpeta | Qué va aquí | Quién la crea |
|---|---|---|
| `skills/` | La lógica de tus skills propios | `/x-crear-skill` |
| `plantillas/` | Plantillas de tipos de documento propios | `/x-crear-plantilla` |

## Por qué existe

El sistema sigue el principio abierto/cerrado: **abierto a extensión, cerrado a modificación
del kernel**. Si un skill del kernel hace algo que no te sirve, la respuesta no es editarlo
—eso rompe la actualización limpia con `/x-actualizar-sistema`— sino crear el tuyo aquí.

## Tipos propios

Un tipo de documento propio (`Cliente`, `Experimento`, `Caso`…) se declara en
**`cerebro/schema.json`**, no aquí y no en el kernel. El validador lo lee al arrancar y lo trata
como uno más: campos requeridos, enums y ubicación incluidos. Los tipos base no se pueden
redefinir ni quitar — solo se añaden.
