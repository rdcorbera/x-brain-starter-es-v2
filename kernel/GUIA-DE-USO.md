# Guía de uso — X-Brain

Cómo se opera la base de conocimiento, día a día. Sirve para cualquier rol en cualquier
organización: el sistema se adapta a tu trabajo durante el `/x-setup`.

Para instalarlo, ver [`INSTALL.md`](../INSTALL.md). Para las reglas que siguen los agentes,
[`AGENTS.md`](AGENTS.md).

---

## 1. Qué es esto

Un **wiki personal mantenido por agentes de IA**. Tú aportas las fuentes —transcripciones,
documentos, lo que averiguas en el día— y haces las preguntas; los agentes hacen el trabajo
pesado: clasificar, resumir, cruzar referencias, detectar contradicciones.

Combina cuatro patrones y una capa propia:

| | Qué aporta |
|---|---|
| **PARA** | Estructura temporal: proyectos (con fecha de fin), áreas (responsabilidades continuas), recursos, archivo |
| **OKF v0.2** | Formato verificable: markdown + frontmatter tipado, `index.md`, `log.md`, procedencia y ciclo de vida |
| **LLM Wiki** | Filosofía: un wiki que se integra con cada ingesta, con fuentes crudas inmutables |
| **Skills** | Mecánica: comandos `/x-*` que ejecutan flujos de entrevista y mantenimiento |
| **La capa determinista** | `brain.py`: valida, genera y enruta **sin llamar a un modelo**, así que cuesta cero tokens y se puede correr cien veces |

**Qué lo hace genérico:** nada de tu rol está cableado. El `/x-setup` te entrevista y crea tus
áreas, tu mapa de personas, tu ciclo de planificación e incluso tipos de documento propios.

**Qué lo hace actualizable y portable:** las zonas de propiedad. El sistema (`kernel/` y los
stubs) es del starter y se actualiza desde GitHub; tu conocimiento (`cerebro/`), tus fuentes
(`raw/`) y tus extensiones (`plugins/`) son tuyos y ninguna actualización los toca. La regla de
oro correspondiente: **tú tampoco tocas el kernel.**

---

## 2. El ritual de la mañana (5-10 min)

```
1. Soltar en inbox/ todo lo pendiente de ayer
   (transcripciones, documentos recibidos, notas sueltas)
2. /x-procesar-inbox      ← clasifica, archiva en raw/, integra, detecta contradicciones
3. /x-briefing-diario     ← repasa preguntas abiertas y pendientes vencidos
```

No hace falta nombrar prolijo lo que sueltas: cada original se archiva en `raw/` como
`AAAA-MM-DD-descripcion-uuid.ext`, registrado en `raw/manifiesto.md`. Solo evita `notas3.txt`.

Lo que sí ahorra preguntas es **agrupar por destino**: si sueltas una carpeta con el nombre de
un proyecto o de un área (`inbox/migracion-erp/`), todo lo que esté dentro se atribuye ahí sin
que te pregunte archivo por archivo. El nombre no tiene que ser exacto. Si no corresponde a
nada existente, te pregunta antes de tocar nada.

### Qué formatos acepta el inbox

Texto plano (`.md`, `.txt`, `.vtt`), y estos adjuntos, que se convierten solos:

| Formato | Qué hay que saber |
|---|---|
| `.docx` `.pptx` `.xlsx` | Van **sin instalar nada**. En PowerPoint entran también las notas del orador |
| `.xlsx` | Se muestrean las primeras 50 filas por hoja. Una hoja de 1.500 filas son ~18.800 tokens de ruido; muestreada, ~830. El original completo queda en `raw/` |
| `.drawio` | Se convierte a un diagrama Mermaid legible |
| `.html` `.yaml` | Se limpia la plantilla web (`nav`, `footer`) antes de convertir |
| `.pdf` | **El único que necesita una dependencia** (`pdfminer.six`). Si no está, el script propone la alternativa en vez de fallar. Si está escaneado, avisa en vez de devolver vacío |
| `.doc` `.ppt` `.xls` | **No se pueden leer** (binarios anteriores a 2007). Abrir en Office y «Guardar como» al formato moderno |

**Los «Avisos de conversión» importan.** Cuando la conversión pierde algo, el markdown lo dice
arriba de todo. No los ignores ni los borres: son la diferencia entre saber que falta un dato y
creer que no existe.

Para convertir algo a mano, o para pedir más filas de una hoja:

```bash
python3 kernel/bin/to-markdown.py <archivo.xlsx> --rows 200 --stdout
```

---

## 3. Alrededor de cada reunión, y al trabajar

```
ANTES:    /x-preparar-reunion     ← agenda: preguntas a hacer, pendientes a cobrar
DESPUÉS:  soltar transcripción o notas en inbox/ → /x-procesar-inbox
```

```
/x-decision   ← registrar o deliberar una decisión (valida contra decisiones previas)
/x-diagrama   ← flujos, procesos, secuencias, organización, cronograma
/x-plan       ← crear o re-planificar el plan de tareas de un proyecto, o ver cuánto falta
/x-consultar  ← preguntar cualquier cosa a la base
```

Usa el modelo más capaz disponible para `/x-decision` y `/x-diagrama`: ahí el razonamiento es
lo que aporta.

### Commit diario

```bash
git add . && git commit -m "brain: $(date +%F)" && git push
```

El pre-commit valida lo que estás commiteando. Si algo falla, casi siempre lo arregla
`brain.py validate --fix`.

---

## 4. Rituales periódicos

| Frecuencia | Comando | Qué hace |
|---|---|---|
| **Semanal** | `/x-actualizacion-semanal` | Pulso, objetivos, avance de cada proyecto contra su plan, pendientes vencidos |
| **Mensual** | `/x-curar` | Lint de contenido: contradicciones, huérfanos, obsolescencia |
| **Por periodo** | `/x-cierre-periodo` | Archiva proyectos extrayendo el conocimiento reutilizable, y hace el retro |
| **Cuando haya versión nueva** | `/x-actualizar-sistema` | Trae el kernel más reciente desde GitHub |

> El lint **estructural** —índices, derivados, enlaces, frontmatter— ya no es un ritual: lo
> hace `brain.py validate` en cada commit y en cada corrida de CI, gratis. `/x-curar` se ocupa
> solo de lo que exige criterio.

---

## 5. La capa determinista, para cuando la necesites

No hace falta memorizarla —los skills la invocan— pero saber que existe cambia cómo trabajas.

```bash
python3 kernel/bin/brain.py validate cerebro     # validar (dos niveles: OKF / perfil)
python3 kernel/bin/brain.py validate --fix       # arreglar solo lo mecánico
python3 kernel/bin/brain.py template Reunion     # imprimir la plantilla de un tipo
python3 kernel/bin/brain.py place Reunion proyecto=2026-q3-erp   # ¿dónde va esto?
python3 kernel/bin/brain.py index                # regenerar los index.md
python3 kernel/bin/brain.py derive               # regenerar los índices derivados
python3 kernel/bin/brain.py init cerebro         # materializar o poner al día la estructura
python3 kernel/bin/brain.py govern cerebro       # informe de postura de gobierno de datos
```

**Lo que no se hace:** editar un archivo generado. `cerebro/ESQUEMA.md`, cada `index.md`,
`PREGUNTAS-ABIERTAS.md`, `GOALS.md` y `ORGANIGRAMA.md` se regeneran, y el cambio se pierde. Si
algo generado está mal, lo que hay que cambiar es `kernel/schema/contract.json`.

**Por qué `GOALS.md` ya no se escribe a mano:** es la lista de tus iniciativas del periodo
agrupadas por origen, y esos tres bloques son un campo (`origen`) de cada `CONTEXT.md`. Creas
la iniciativa y el archivo se actualiza solo. Al cerrar el periodo, mover el proyecto a
`04-archivo/` es lo que lo saca del listado.

### Los dos preflight

`survey.py` y `sqlite-probe.py` corren **antes** de que se instale nada, así que su piso es
Python 3.9. Los dos son de solo lectura y ninguno emite la ruta en su salida.

```bash
python3 kernel/bin/survey.py cerebro     # ¿dónde se van los tokens en este cerebro?
python3 kernel/bin/sqlite-probe.py .     # ¿puede esta máquina alojar la proyección?
```

---

## 6. Portar, compartir y reconstruir

**Compartir tu cerebro.** Copia la carpeta `cerebro/` completa. Es un bundle OKF
autodescriptivo: su `ESQUEMA.md` explica tipos, estructura y convenciones sin necesitar el
kernel. Quien lo recibe lo coloca en un starter limpio y corre `/x-setup`, que detecta el
cerebro heredado, lo adopta sin tocarlo y solo re-entrevista la identidad del nuevo dueño.
Compartir `raw/` es opcional: sin él, los punteros `/raw/...` quedan rotos pero el conocimiento
integrado está completo.

**Reconstruir desde las fuentes.** Copia `raw/` con su `manifiesto.md` a un starter limpio y
corre `/x-reconstruir`. Recrea lo derivable de las fuentes; la curaduría manual posterior no
está en `raw/` y no se recupera — para portar un cerebro curado, usa el escenario anterior.

**Actualizar el sistema.** `/x-actualizar-sistema` trae la última versión del kernel. Como el
upstream solo toca `kernel/`, los stubs y los archivos raíz —y tú nunca los editas— el merge es
limpio. Si una versión requiere pasos manuales, su entrada en [`CHANGELOG.md`](CHANGELOG.md)
los trae bajo **Migración**. Después de actualizar, corre `brain.py init cerebro`: pone al día
`ESQUEMA.md` y los derivados si el contrato cambió.

---

## 7. Reglas de oro del operador

1. **Todo pasa por el inbox.** Si no está en el cerebro, no existe. La disciplina de soltar
   todo en `inbox/` es lo único que el sistema no puede hacer por ti.
2. **Nada se queda en el inbox más de un día.** El valor está en el conocimiento integrado, no
   en el material crudo acumulado.
3. **Los originales no se tocan.** `raw/` es inmutable y completo; el wiki lo cita. Es tu
   seguro para reconstruir.
4. **Lo que no sabes es una `Pregunta`, no un supuesto.** Nunca dejes que un agente —ni tú—
   rellene un hueco con una suposición sin registrarla.
5. **El plan es la fuente de lo pendiente.** Si una tarea del proyecto no está en su `PLAN.md`,
   para el sistema no existe. Lo que no es trabajo de proyecto vive en la ficha de la persona.
6. **El kernel no se edita.** Si un skill hace algo que no te sirve, créate uno propio con
   `/x-crear-skill`: editar `kernel/` rompe la actualización limpia.
7. **Confidencialidad.** Nunca ingreses credenciales, secretos ni datos personales de terceros.
   Registra las restricciones de tu organización en el `/x-setup` para que los agentes las
   respeten — y ten presente que el sistema comprueba la clasificación, pero **no puede
   detectar un secreto pegado en una nota**.
8. **Revisa antes de confirmar.** Los skills muestran los cambios antes de escribir. Ese punto
   de control existe para usarse, especialmente las primeras semanas.

---

## 8. Problemas

Los de instalación están en [`INSTALL.md`](../INSTALL.md). Los de operación:

**`brain validate` marca un `index.md` desactualizado.**
`brain.py validate --fix`, o `brain.py index`. Nunca lo edites a mano: se regenera.

**Un enlace aparece como «sin destino».**
Es `info`, no un error: marca conocimiento aún no escrito. Si debía existir, créalo; si no,
déjalo — es la señal de dónde falta contenido.

**«placeholder sin rellenar».**
Un documento creado desde plantilla que quedó a medias. Los `<…>` son huecos que alguien debía
completar.

**Un documento aparece «en una ubicación no declarada» (aviso).**
Es dónde debería vivir según su tipo: `brain.py place <Tipo> proyecto=<slug>` te lo dice. Es
aviso y no error a propósito, porque un cerebro heredado tiene muchos.

**Un `.xlsx` salió con columnas vacías.**
Fórmulas sin valor calculado en caché: libros generados por otro sistema y nunca abiertos en
Excel. El aviso de conversión lo dice. Ábrelo en Excel o LibreOffice y guárdalo.

**Un `.pdf` se convirtió casi vacío.**
Está escaneado: es imagen, no texto. El markdown lo avisa. Pide el original digital o pásale
OCR. **No dejes que el agente «deduzca» el contenido.**

**El cerebro creció y las consultas se sienten lentas o incompletas.**
El patrón índice-primero funciona hasta cientos de páginas. Corre `python3 kernel/bin/survey.py
cerebro`: mide dónde se van los tokens y dice si ya toca la capa de consulta.
