# plugins — tus extensiones

Esta zona es **tuya**. El kernel no la toca y ninguna actualización la sobrescribe.

| Carpeta | Qué va aquí | Quién la crea |
|---|---|---|
| `skills/` | La lógica de tus skills propios | `/x-crear-skill` |
| `plantillas/` | Plantillas de tipos de documento propios | `/x-crear-plantilla` |
| `profiles/` | Profiles de rol propios, para `/x-setup` | Tú, copiando uno del kernel |

## Por qué existe

El sistema sigue el principio abierto/cerrado: **abierto a extensión, cerrado a modificación
del kernel**. Si un skill del kernel hace algo que no te sirve, la respuesta no es editarlo
—eso rompe la actualización limpia con `/x-actualizar-sistema`— sino crear el tuyo aquí.

## Profiles de rol

Un profile es el molde con el que `/x-setup` siembra un `PERFIL.md`: la prosa que es cierta de
un **rol**, para no tener que responder una entrevista de treinta minutos. El kernel trae tres
en `kernel/scaffold/profiles/`; los tuyos van aquí.

```bash
./brain profiles                       # ver los disponibles
cp kernel/scaffold/profiles/<uno>.md plugins/profiles/     # partir de uno del kernel
./brain init cerebro --profile <slug>  # aplicarlo
```

**El slug es el nombre del archivo, y ante el mismo nombre gana el tuyo** — así se adapta un rol
del kernel sin editarlo. El cuerpo lleva los mismos encabezados que `kernel/scaffold/PERFIL.md`,
y **no repite su frontmatter**: ese lo pone el scaffold genérico, una sola vez.

El frontmatter del profile es corto a propósito: `title` y `description` para que
`./brain profiles` liste sin abrir los archivos, `kind` (`individual` o `leadership`), y las dos
propuestas —`period_format` y `areas`— que `./brain init --profile` imprime al aplicarlo.

Y la regla que lo gobierna: **un profile propone, nunca afirma.** Solo puede llevar lo que es
cierto del rol, no de tu organización. Por eso ninguno siembra lineamientos ni sistemas.

## Tipos propios

Un tipo de documento propio (`Cliente`, `Experimento`, `Caso`…) se declara en
**`cerebro/schema.json`**, no aquí y no en el kernel. El validador lo lee al arrancar y lo trata
como uno más: campos requeridos, enums y ubicación incluidos. Los tipos base no se pueden
redefinir ni quitar — solo se añaden.
