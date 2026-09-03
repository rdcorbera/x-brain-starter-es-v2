# X-Brain — instrucciones para Claude Code

Las reglas del sistema viven en el kernel y el contexto del usuario en su cerebro. Ambos se
cargan automáticamente en cada sesión:

@kernel/AGENTS.md

@cerebro/PERFIL.md

<!--
  Mientras este repositorio sea el del rediseño y no el que clona un usuario, se carga
  también cómo se construye el sistema. Esta línea se quita al publicar: quien clone el
  starter viene a usarlo, no a construirlo.
-->
@CONTRIBUTING.md

## Notas para Claude Code

- **Antes de escribir un documento a mano, comprueba si hay un comando.**
  `brain.py template <Tipo>` da los campos exactos por unos 200 tokens; deducirlos leyendo el
  contrato cuesta unos 10.000. `brain.py place <Tipo> proyecto=<slug>` dice dónde va, y
  `brain.py validate cerebro` comprueba el resultado. La lista completa está en
  [`kernel/AGENTS.md`](kernel/AGENTS.md).
- **Un artefacto generado no se edita: se regenera.** `cerebro/ESQUEMA.md`, cada `index.md`,
  `PREGUNTAS-ABIERTAS.md`, `GOALS.md` y `ORGANIGRAMA.md` salen de
  `kernel/schema/contract.json`. Si algo generado está mal, lo que se corrige es el contrato —
  editar la salida es trabajo que se pierde en la siguiente corrida, y **V14 lo detecta**.
- Los skills se invocan con el prefijo `x-`. Los de `.claude/skills/` son **stubs generados**:
  la lógica real vive en `kernel/modulos/` (skills del kernel) o `plugins/skills/` (del
  usuario). **Editar la lógica de un skill del kernel es editar el kernel: no se hace** — los
  ajustes propios van como plugins (`/x-crear-skill`).
- Este archivo es parte del kernel: no editarlo localmente. La personalización vive en
  `cerebro/PERFIL.md`.
