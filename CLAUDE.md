# X-Brain v2 — instrucciones para Claude Code

## Qué es este repositorio

El **starter en construcción** de X-Brain v2. Ojo con la distinción, porque cambia todo lo que hagas aquí:

- Hoy estamos **construyendo el sistema**: escribimos el kernel, los skills, el esquema y la documentación.
- No estamos **operando un cerebro**: no hay conocimiento de nadie que ingerir, ni inbox que procesar.

Cuando el starter esté listo, este mismo archivo pasará a ser el que cargue el sistema en la sesión del usuario final. Mientras tanto, es la guía de trabajo del proyecto.

## Referencia: la v1

La versión anterior está clonada localmente en `../x-brain-starter-es` (kernel 1.3.0) y publicada en https://github.com/rdcorbera/x-brain-starter-es. **Consúltala antes de rediseñar algo**: `kernel/AGENTS.md` (reglas y zonas), `kernel/GUIA-DE-USO.md` (operación completa), `kernel/esquema/okf.md` (formato), `kernel/CHANGELOG.md` (qué se aprendió en cada versión) y `kernel/modulos/` (la lógica de los 15 skills).

Es referencia, no destino: v2 se rehace desde cero. Reutiliza lo que probó funcionar, no lo que simplemente estaba ahí.

## Reglas de trabajo

1. **Español** en todo: documentación, nombres de archivo, mensajes de commit, conversación.
2. **README.md y CLAUDE.md se mantienen vivos.** Cuando se cierre una decisión de diseño o se agregue una pieza, actualizar el archivo que corresponda en el mismo turno — no dejarlo para después. La bitácora de abajo es parte de esto.
3. **No inventar.** Si falta un dato para decidir, se pregunta o se anota en «Preguntas abiertas». Nunca rellenar un hueco con un supuesto sin marcarlo.
4. **Decisión antes que código.** Antes de escribir una pieza nueva del sistema, dejar registrado en la bitácora qué se decidió y por qué. Las alternativas descartadas valen tanto como la elegida.
5. **Mostrar antes de escribir** cuando el cambio sea grande o toque archivos ya acordados.
6. **Sin commits automáticos.** Se hace commit cuando el usuario lo pida.

## Convenciones

- Archivos y carpetas en **kebab-case**, descriptivos y autocontenidos.
- Documentación en markdown; **diagramas siempre como texto** (Mermaid preferido), nunca solo imágenes.
- Nada de credenciales, secretos ni datos personales de terceros en el repo — tampoco en ejemplos.
- Los ejemplos que ilustren el sistema usan datos ficticios y se marcan como tales.

## Estado del diseño

**Definido:** la herencia conceptual del README (PARA, OKF, LLM Wiki, raw inmutable, zonas de propiedad, cerebro portable, nunca fabricar), el modelo de distribución (repo template) y las herramientas soportadas (Claude Code + Copilot).

**Por decidir:** estructura de carpetas, catálogo de tipos, inventario de skills, mecánica de ingesta de binarios, estrategia de recuperado a escala y validación determinista.

## Bitácora de decisiones

Una entrada por decisión cerrada: fecha, qué se decidió, por qué, qué se descartó.

### 2026-08-26 — Soporte de primera clase para Claude Code y Copilot

v2 sigue sirviendo a las dos herramientas, como v1. Se descartó apuntar solo a Claude Code (habría dado acceso a hooks, subagentes y plugins sin denominador común, pero deja fuera a los usuarios de Copilot) y también posponer Copilot para después.

**Consecuencia de diseño:** la lógica del sistema vive en markdown neutro, invocable desde ambas. Ninguna capacidad esencial puede depender de una herramienta sola; lo específico de cada una queda como capa fina de invocación. Los stubs duplicados se quedan — lo que hay que eliminar es mantenerlos a mano.

### 2026-08-26 — Distribución como repo template, igual que v1

El sistema viaja dentro del repositorio del usuario y se actualiza con merge desde upstream. Se descartó distribuir el kernel como plugin de Claude Code (habría sacado el kernel del repo del usuario y eliminado el merge, pero es incompatible con soportar Copilot) y también el híbrido.

**Consecuencia de diseño:** nada impide editar el kernel, así que la separación sistema/conocimiento hay que sostenerla por convención, documentación y validación propia. Es una de las mejoras pendientes del README.

### 2026-08-26 — Rehacer desde cero en vez de evolucionar el kernel 1.3.0

v1 acumuló fricciones estructurales (cumplimiento de las zonas, stubs duplicados, validación no determinista) que no se arreglan con una versión más del kernel. Se descartó seguir el changelog de v1 con una 1.4.0. Se conserva la herencia conceptual, no el código.

## Preguntas abiertas

- ¿Qué mecanismo hace cumplir la separación sistema/conocimiento, dado que el kernel vive dentro del repo del usuario?
- ¿Cómo se generan y mantienen sincronizados los stubs de las dos herramientas desde una sola fuente?
- ¿Hay ruta de migración desde un cerebro v1, o v2 arranca limpio?
- ¿Cómo se llama el producto y el repo definitivo?
