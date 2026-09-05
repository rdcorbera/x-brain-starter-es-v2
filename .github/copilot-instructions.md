# X-Brain — instrucciones para agentes (arranque Copilot)

Este archivo es solo el punto de entrada. Antes de actuar en este repositorio, **leer en este
orden**:

1. **`kernel/AGENTS.md`** — las reglas del sistema: qué hace la capa determinista para que no
   lo hagas a mano, zonas de propiedad, principios, conformidad OKF y gobierno de datos.
2. **`cerebro/PERFIL.md`** — quién es el usuario, cómo trabaja, y sus reglas de comunicación y
   confidencialidad.
3. **`cerebro/ESQUEMA.md`** — el catálogo de tipos vigente de este cerebro. Es generado: no se
   edita.

**Lo más importante si solo lees una línea:** hay comandos deterministas que ya hacen buena
parte del trabajo, y usarlos no es opcional. `./brain template <Tipo>` para
saber qué campos lleva un documento, `place` para saber dónde va, `validate` para comprobarlo.
Escribir frontmatter a mano deduciéndolo cuesta tokens y se equivoca.

Los skills se invocan con el prefijo `x-` y viven como stubs en `.github/prompts/` (requieren
`chat.promptFiles: true`); cada stub carga su lógica desde `kernel/modulos/` o
`plugins/skills/`.

Este archivo es parte del kernel: no se edita localmente ni lo modifica ningún skill. La
personalización vive en `cerebro/PERFIL.md`.
