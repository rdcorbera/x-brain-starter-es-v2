# Instalación

Del repositorio vacío a un cerebro que funciona. Una sola vez, unos 45 minutos —
la mayoría son de la entrevista del paso 5.

Para operarlo día a día, ver [`kernel/GUIA-DE-USO.md`](kernel/GUIA-DE-USO.md).

---

## Lo que hace falta

| Herramienta | Para qué | Obligatoria |
|---|---|---|
| **Git** | Historial, respaldo y actualizaciones del kernel | Sí |
| **Un agente de código** | [Claude Code](https://claude.com/claude-code), o VS Code + GitHub Copilot (Chat, modo Agent) | Sí |
| **Python 3.11+** | `brain.py` es el núcleo del sistema, no un accesorio | Sí |
| **Obsidian** | Ver el cerebro como wiki: grafo, navegación por enlaces | No |
| **`pdfminer.six`** | El único formato de insumo que necesita una dependencia | No |

> **Verifica la política de uso de IA de tu organización** antes de ingresar información
> interna, y su política sobre dónde puede alojarse este repositorio.

### Por qué 3.11 y no menos

No es higiene: antes de 3.11, `datetime.fromisoformat` **rechaza el sufijo `Z`**, la forma
habitual de escribir un instante UTC. El campo `stale_after` es un instante ISO 8601 completo,
y sin ese soporte un documento que caduca hoy a las 23:59Z se interpretaba como medianoche
local y se reportaba vencido **nueve horas antes de estarlo**. Además 3.9 y 3.10 están fuera de
soporte.

Lo que instales puede ser más nuevo: **3.14 es lo recomendable**, por ventana de soporte. El
piso dice qué tolera el código, no qué conviene instalar.

- **Windows** — [python.org](https://www.python.org/downloads/) o `winget install Python.Python.3.14`
- **macOS** — el del sistema no sirve: `brew install python@3.14`
- **Linux** — según la distro

Comprueba con `py -3 --version` en Windows, `python3 --version` en macOS y Linux. **Esos
nombres no coinciden a propósito**, y por eso el repositorio trae un lanzador —`./brain`—
que resuelve el intérprete por ti: los comandos de esta guía se escriben una sola vez y
funcionan en los tres sistemas.

> Cuidado con `python3` en Windows: el instalador de python.org **no crea `python3.exe`**, y
> Windows 10+ trae un alias que abre la Microsoft Store con ese nombre. No falla con un
> error: abre una tienda.

---

## Paso 1 — Obtener el repositorio

```bash
git clone https://github.com/rdcorbera/x-brain-starter-es-v2 mi-brain
cd mi-brain
```

Recomendado: crea tu repositorio remoto **privado** como respaldo y apunta `origin` ahí,
dejando el starter como `upstream` (así `/x-actualizar-sistema` sabe de dónde traer versiones):

```bash
git remote rename origin upstream
git remote add origin <url-de-tu-repo-privado>
git push -u origin main
```

## Paso 2 — Elegir dónde vive el cerebro, y comprobarlo

**Este paso no es opcional y no es una recomendación: es una comprobación que puede fallar.**

```bash
./brain kernel/bin/sqlite-probe.py .
```

Sale con código 1 si la ruta no sirve. Comprueba tres cosas:

1. **Qué SQLite trae tu Python.** En Windows el intérprete empaqueta el suyo, así que la
   versión la fija Python y no el sistema.
2. **Qué capacidades están compiladas.** FTS5 es una bandera de compilación, no una versión:
   puede faltar en un SQLite reciente.
3. **Si la ruta elegida sirve** — tipo de unidad, carpeta sincronizada, y el modo WAL como
   prueba decisiva.

> **Lo más importante, y lo que más se pasa por alto: no pongas el repositorio dentro de
> OneDrive, Dropbox ni una unidad de red.** El cliente de sincronización reescribe el archivo
> por debajo del proceso que lo tiene abierto, así que la base **se corrompe** — no se
> ralentiza. Y no basta con mirar si el disco es local: dentro de OneDrive, el disco *es* local
> y WAL activa sin problema. Solo lo detecta la comprobación explícita de sincronización, que
> es justo lo que hace la sonda.
>
> Ventaja adicional de una ruta corta y local (`D:\x-brain\`): Windows mantiene el límite de
> 260 caracteres salvo que el soporte de rutas largas esté habilitado, y las rutas del cerebro
> se acumulan rápido.

La sonda es de solo lectura, crea su base de prueba en un temporal y la borra, y **no emite la
ruta en su salida**: se puede compartir desde un entorno restringido.

## Paso 3 — Materializar el cerebro

```bash
./brain init cerebro
```

Crea la estructura, el esquema portable y los índices derivados vacíos. Es determinista,
cuesta cero tokens y **se puede volver a correr cuando quieras** — es también como se ponen al
día `ESQUEMA.md` y los derivados después de actualizar el kernel.

Comprueba que quedó bien:

```bash
./brain validate cerebro   # debe decir «sin hallazgos»
```

## Paso 4 — Activar los skills en tu herramienta

- **Claude Code**: nada que hacer — los de `.claude/skills/` se detectan solos. Escribir `/x-`
  debe listarlos.
- **VS Code + Copilot**: activar el setting **Chat: Prompt Files** (`chat.promptFiles: true`),
  abrir Copilot Chat en modo **Agent**, y comprobar que `/x-setup` aparece al escribir `/`.

## Paso 5 — Correr el setup (aquí el sistema se vuelve tuyo)

```
/x-setup
```

Te ofrece elegir un **profile de rol** —ingeniero de sistemas, arquitecto de tecnología, manager
de ingeniería— y ajustarlo: **unos 5 minutos**. El profile trae escrito lo que es cierto del
rol; tú respondes solo lo que nadie puede saber por ti —nombre, organización, antigüedad— y
corriges lo que no encaje.

Si no te reconoces en ninguno, la entrevista completa sigue estando ahí. Y si ninguno se parece
a tu trabajo, puedes hacerte el tuyo: `plugins/profiles/`.

**Nada se escribe sin que lo revises y confirmes.**

Todo lo generado queda en `cerebro/`; el kernel no se toca.

## Paso 6 — Instalar el control de calidad

```bash
./brain hooks --install
```

Instala un pre-commit que valida **solo lo que se commitea**. Un hook que falle sobre el corpus
heredado se desactiva el primer día, así que a propósito no mira el bundle entero: de eso se
encarga la CI.

## Paso 7 (opcional) — El conversor de PDF

Los insumos de Office (`.docx`, `.pptx`, `.xlsx`), los `.drawio`, `.html` y `.yaml` funcionan
sin instalar nada. **Solo el `.pdf` necesita una dependencia:**

```bash
pip install pdfminer.six
```

Si `pip` está restringido en tu organización, no pasa nada: el script te lo dice y propone la
alternativa (guardar el PDF como `.docx` y dejar eso en `inbox/`). El original se archiva igual
en `raw/` y se sigue citando.

---

## Comprobación final

```bash
./brain validate cerebro    # sin hallazgos
./brain kernel/tests/test_roundtrip.py          # el contrato es consistente consigo mismo
```

Si los dos pasan, el sistema está instalado. Sigue con
[`kernel/GUIA-DE-USO.md`](kernel/GUIA-DE-USO.md).

---

## Problemas

**«to-markdown.py necesita Python 3.11+ y este es 3.9.x».**
Es el Python del sistema (macOS trae 3.9). Instala uno propio y vuelve a comprobar con
`python3 --version` (en Windows, `py -3 --version`).

**La sonda de SQLite sale con código 1.**
Lee lo que reporta: casi siempre es una carpeta sincronizada o una unidad de red. Mueve el
repositorio a una ruta local y vuelve a correrla. No lo ignores: el modo de fallo no es
lentitud, es corrupción.

**`brain validate cerebro` dice «cerebro sin inicializar».**
Falta el paso 3: `./brain init cerebro`.

**`brain validate` reporta muchos hallazgos en un cerebro heredado.**
Es lo esperado al migrar desde v1. Empieza por `validate --fix`, que arregla todo lo mecánico
—índices, derivados y entrecomillado de frontmatter— sin tocar lo que redactó una persona.
Lo que quede pide criterio.

**Los comandos `/x-*` no aparecen.**
Claude Code: comprueba que abriste la carpeta raíz del repositorio, no una subcarpeta.
Copilot: (a) `chat.promptFiles: true`; (b) el workspace es la carpeta del repositorio; (c)
versión reciente de VS Code y de Copilot Chat.

**`/x-actualizar-sistema` reporta conflictos.**
Alguien editó archivos del kernel localmente. Conserva la versión del upstream para `kernel/` y
los stubs; si la edición local era valiosa, rescátala como plugin o propónla al starter.

**Los diagramas Mermaid no se ven.**
VS Code: instalar `Markdown Preview Mermaid Support` y abrir con `Ctrl+Shift+V`. Obsidian los
renderiza de forma nativa.
