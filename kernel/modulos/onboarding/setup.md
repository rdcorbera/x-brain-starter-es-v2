---
skill: x-setup
description: 'Inicializa y personaliza el cerebro. Se elige un profile de rol y se ajusta, o se hace la entrevista completa.'
---

# Skill: Setup (`/x-setup`)

Deja el cerebro listo para trabajar: la estructura, el `PERFIL.md` y el formato de periodo.

**Regla central: no fabricar.** Si una respuesta es delgada, la sección queda delgada. Se usan
las palabras del usuario, no se reescriben en tono corporativo, y lo que no se sabe se queda
como está o se convierte en una `Pregunta`. **Un profile propone; nunca afirma.**

**Regla de zonas:** todo lo que este skill genera vive en `cerebro/`, y los moldes propios en
`plugins/profiles/`. Jamás edita `kernel/`, `.github/` ni los stubs de `.claude/skills/`.

---

## Fase 0 — Escanear antes de preguntar

Mirar `cerebro/` y distinguir tres estados:

| Estado | Señal | Qué hacer |
|---|---|---|
| **Sin inicializar** | `cerebro/` vacío o sin `PERFIL.md` | Fase 1 |
| **Ya personalizado** | `PERFIL.md` sin TODOs | Preguntar: ¿empezar de cero, o construir encima? Nunca decidirlo por el usuario |
| **Adoptado** | Hay conocimiento, pero de otra persona | Leer `cerebro/ESQUEMA.md` y correr solo la parte de identidad, **sin tocar el conocimiento heredado**. Si lo que recibió fue un `raw/` en vez de un cerebro, esto es `/x-reconstruir` |

---

## Fase 1 — Elegir la vía

Mostrar los profiles disponibles y las tres vías:

```bash
./brain profiles
```

| Vía | Cuándo | Coste |
|---|---|---|
| **(a) Profile de rol** | El usuario se reconoce en uno de los listados. **Es la de por defecto** | ~5 min |
| **(b) Entrevista completa** | No se reconoce en ninguno, o quiere el detalle | Ver `cuestionario-setup.md` |
| **(c) Documentos existentes** | Tiene descripción de cargo, CV, organigrama o plan del periodo | Se convierten y se usan para precargar |

En **(c)**: convertir con `kernel/bin/to-markdown.py`, no leer el binario. Los originales van a
`raw/` con su fila en `raw/manifiesto.md`. **Un CV dice el rol; no dice qué le da energía a una
persona** — lo que el documento no diga, se pregunta o se queda vacío.

Si elige **(b)**, seguir `cuestionario-setup.md` y saltar a la Fase 3.

---

## Fase 2 — La vía del profile

### 1. Materializar

```bash
./brain init cerebro --profile <slug>
```

Esto crea la estructura, siembra `PERFIL.md` con la prosa del rol y escribe los derivados y los
índices. Es determinista y **no sobrescribe nada que ya exista**.

**Al terminar imprime las propuestas del profile** —el `period_format` y las carpetas de área—,
que son las que se confirman en los pasos 4 y 5. Vienen por la salida del comando: no hay que
abrir ningún archivo del kernel para leerlas.

### 2. Preguntar solo lo irreducible

Cuatro cosas, porque ningún profile puede saberlas:

1. **Nombre y organización.**
2. **Desde cuándo en el rol** — calibra cuánto contexto se puede dar por sabido.
3. **Idioma del contenido**, si no es español.
4. **Qué le da energía y qué siente como trámite** — marca dónde poner el énfasis cuando el
   agente tiene margen de criterio.

No preguntar nada más aquí. Todo lo demás ya está propuesto y se revisa en el paso siguiente.

### 3. Recorrer las seis secciones

Mostrar cada sección del `PERFIL.md` sembrado y preguntar: **¿te describe? ¿qué cambias?**

`# Quién soy` · `# Cómo trabajo` · `# Reglas de comunicación` · `# Lo que nunca se hace` ·
`# Confidencialidad` · `# Estado actual`

Una sección por vez. Si algo no aplica, se quita — un profile que no encaja del todo es normal y
no hay que defenderlo. **Los TODO que queden sin responder se borran**, no se dejan puestos:
`PERFIL.md` se carga en cada sesión y un TODO ahí es ruido permanente.

### 4. Confirmar el formato de periodo

`init --profile` lo imprimió en el paso 1. Confirmarlo o cambiarlo, y escribirlo en
`cerebro/schema.json`:

```json
{ "period_format": "quarterly" }
```

Los valores admitidos son `quarterly` (`2026-Q3`), `monthly` (`2026-08`) y `sprint`
(`2026-S14`). **No se escribe el formato en `PERFIL.md`**: allí va la prosa del ciclo —cada
cuánto se cierra, qué pasa en el cierre—, y el formato es un dato que V21 comprueba.

### 5. Confirmar o renombrar las áreas

`init --profile` las imprimió en el paso 1. **Son propuestas, y casi siempre hay que
renombrarlas**: las áreas de alguien son de su organización, no de su rol.

Mostrarlas, dejar que las renombre, quite o añada, y **crear solo las confirmadas**:

```bash
mkdir -p cerebro/02-areas/<area-confirmada>
./brain index cerebro
```

Si no reconoce ninguna, no se crea ninguna. Una carpeta vacía con un nombre que no significa
nada es peor que no tenerla.

---

## Fase 3 — Cerrar

1. **Mostrar antes de escribir.** Un resumen de todo lo que se va a dejar en disco, y confirmar.
2. Escribir `cerebro/PERFIL.md` con las secciones acordadas.
3. Escribir `cerebro/schema.json` con el `period_format`.
4. Crear las carpetas de área confirmadas.
5. Poner al día lo generado:
   ```bash
   ./brain index cerebro
   ./brain derive cerebro
   ./brain validate cerebro
   ```
   `validate` debe terminar **sin hallazgos**. Si los hay, se resuelven antes de dar el setup por
   cerrado.
6. Agregar la entrada al log, en `cerebro/log.md`, bajo su `## AAAA-MM-DD`:
   `**Setup**: cerebro inicializado con el profile <slug> — N áreas, periodo <formato>.`

---

## Lo que este skill NO hace, y por qué

Cuatro cosas que en v1 se pedían aquí y ahora se dejan para cuando aparezcan. Pedirlas en el
setup es pedirle a alguien que describa un sistema que todavía no ha usado.

| Qué | Quién lo crea | Cuándo |
|---|---|---|
| Fichas `Persona` y el organigrama | `/x-procesar-inbox`, al aparecer alguien en una fuente | `ORGANIGRAMA.md` se genera solo desde `reporta-a` |
| Objetivos e iniciativas | `/x-nueva-iniciativa` | `GOALS.md` es un derivado de `Iniciativa.origen`; **no se escribe a mano** |
| Tipos de documento propios | `/x-crear-plantilla` | Cuando el catálogo base se quede corto de verdad |
| Lineamientos | `/x-decision` o a mano | Un lineamiento es un estándar real; **inventarlo sería fabricar** |

Y dos que son deterministas y ya tienen comando: **la estructura de carpetas** la crea
`brain init`, y **los índices y derivados** los escriben `brain index` y `brain derive`. Nunca
se redactan a mano.
