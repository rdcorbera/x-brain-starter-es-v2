# X-Brain v2

Base de conocimiento personal de trabajo, mantenida por agentes de IA — para **cualquier rol, en cualquier organización**. Tú aportas las fuentes (reuniones, documentos, lo que averiguas en el día) y haces las preguntas; los agentes clasifican, integran, cruzan referencias, detectan contradicciones y mantienen todo al día.

> **Estado: en construcción.** Este repositorio es la reescritura desde cero de [x-brain-starter-es](https://github.com/rdcorbera/x-brain-starter-es) (kernel 1.3.0), que a su vez evolucionó de [second-brain-starter-es](https://github.com/rdcorbera/second-brain-starter-es). Todavía no es instalable ni usable: este README y `CLAUDE.md` se van llenando conforme avanza el diseño.

---

## Por qué una v2

v1 demostró que la idea funciona: un wiki compilado, con fuentes crudas inmutables, operado por skills. Lo que no resolvió del todo es *cómo se mantiene y cómo escala* con el uso diario. v2 se rehace desde cero para incorporar lo aprendido usándolo, en vez de parchar el kernel existente.

## Lo que se hereda (probado en v1)

Estos conceptos se dan por buenos y son el punto de partida:

| Concepto | Qué aporta |
|---|---|
| **PARA** | Estructura temporal: proyectos, áreas, recursos, archivo |
| **OKF** (Open Knowledge Format) | Markdown + frontmatter tipado, `index.md` por carpeta, `log.md` por alcance, enlaces bundle-relativos, `# Citations` |
| **LLM Wiki** | Integrar, no archivar: cada ingesta actualiza todas las páginas afectadas y señala contradicciones |
| **Fuentes crudas únicas e inmutables** | Todo original queda en `raw/` con su manifiesto → el cerebro es reconstruible |
| **Zonas de propiedad** | Dueño único por carpeta: el sistema es del starter, el conocimiento es del usuario |
| **Cerebro portable y autodescriptivo** | La carpeta del conocimiento se explica a sí misma (`ESQUEMA.md`) y viaja sola |
| **Nunca fabricar** | Lo que no se sabe es una `Pregunta`, no un supuesto |

## Arquitectura

**Modelo de distribución: repo template**, igual que v1. El sistema viaja dentro del repositorio del usuario y se actualiza con un merge desde upstream. **Herramientas: Claude Code y VS Code + GitHub Copilot**, ambas de primera clase.

De ahí salen dos restricciones que condicionan todo el diseño:

1. **La lógica vive en markdown neutro**, invocable desde cualquiera de las dos herramientas. Nada esencial puede depender de una capacidad exclusiva de una de ellas.
2. **La separación sistema/conocimiento no la impone la herramienta**: el kernel está dentro del repo del usuario y nada le impide editarlo. Hay que sostenerla con convención, documentación y validación propia.

La estructura de carpetas concreta y el contenido del kernel están por definir.

## Lo que se quiere mejorar (lista viva)

Fricciones reales detectadas en v1. Ninguna está resuelta todavía — se van cerrando y documentando conforme trabajamos.

- **Hacer cumplir «no edites el kernel».** Hoy es solo disciplina del usuario: nada detecta ni avisa cuando se rompe, y el costo aparece recién al actualizar, como conflicto de merge.
- **Stubs duplicados.** 15 skills × 2 stubs (`.claude/skills/` + `.github/prompts/`) sincronizados a mano. Con soporte para las dos herramientas la duplicación se queda; lo que debe irse es el mantenimiento manual.
- **Costo de arranque.** Una entrevista de ~30 minutos antes de que el sistema sirva para algo. El valor debería empezar antes.
- **Escala del recuperado.** El patrón índice-primero aguanta cientos de páginas; más allá, las consultas se degradan sin un buscador real.
- **Validación determinista.** El lint de estructura (OKF, índices, enlaces, manifiesto) es un skill que el modelo ejecuta; debería ser código que no falla ni improvisa.
- **Dependencia de Python.** El conversor de insumos binarios exige Python 3.10+ y un venv — el paso donde más gente se traba.
- **Fan-out del trabajo pesado.** Ingestas grandes y curaduría se hacen en un solo hilo de conversación en vez de repartirse.
- **Migración entre versiones.** Pasar de un sistema al siguiente hoy es manual.

## Cómo trabajamos en este repo

Las reglas de trabajo, las convenciones y la bitácora de decisiones están en [CLAUDE.md](CLAUDE.md).
