-- generado por brain.py — no editar a mano; se edita kernel/schema/contract.json y se regenera

-- Las claves foráneas no están activas por defecto en SQLite: hay
-- que pedirlo en cada conexión, o las referencias son decorativas.
PRAGMA foreign_keys = ON;

CREATE TABLE "documentos" (
  "path" TEXT NOT NULL PRIMARY KEY,
  "hash" TEXT NOT NULL,
  "type" TEXT NOT NULL,
  "title" TEXT NOT NULL,
  "description" TEXT NOT NULL,
  "classification" TEXT NOT NULL CHECK ("classification" IN ('public', 'internal', 'confidential', 'restricted')),
  "generated_by" TEXT,
  "generated_at" TEXT,
  "status" TEXT CHECK ("status" IN ('draft', 'stable', 'deprecated')),
  "stale_after" TEXT,
  "resumen" TEXT NOT NULL,
  "resumen_hash" TEXT NOT NULL,
  "procedencia" TEXT NOT NULL CHECK ("procedencia" IN ('fuente', 'dialogo', 'inferido', 'manual', 'derivado'))
) STRICT;

CREATE TABLE "documentos_tags" (
  "doc" TEXT NOT NULL REFERENCES "documentos"("path") ON DELETE CASCADE,
  "idx" INTEGER NOT NULL,
  "value" TEXT NOT NULL,
  PRIMARY KEY ("doc", "idx")
) STRICT;

CREATE TABLE "documentos_verified" (
  "doc" TEXT NOT NULL REFERENCES "documentos"("path") ON DELETE CASCADE,
  "idx" INTEGER NOT NULL,
  "by" TEXT NOT NULL,
  "at" TEXT NOT NULL,
  PRIMARY KEY ("doc", "idx")
) STRICT;

CREATE TABLE "documentos_sources" (
  "doc" TEXT NOT NULL REFERENCES "documentos"("path") ON DELETE CASCADE,
  "idx" INTEGER NOT NULL,
  "resource" TEXT NOT NULL,
  "id" TEXT,
  "title" TEXT,
  "author" TEXT,
  "last_modified" TEXT,
  PRIMARY KEY ("doc", "idx")
) STRICT;

CREATE TABLE "analisis" (
  "doc" TEXT NOT NULL PRIMARY KEY REFERENCES "documentos"("path") ON DELETE CASCADE,
  "proyecto" TEXT NOT NULL,
  "fecha" TEXT NOT NULL
) STRICT;

CREATE TABLE "decision" (
  "doc" TEXT NOT NULL PRIMARY KEY REFERENCES "documentos"("path") ON DELETE CASCADE,
  "proyecto" TEXT NOT NULL,
  "estado" TEXT NOT NULL CHECK ("estado" IN ('propuesta', 'aceptada')),
  "fecha" TEXT NOT NULL,
  "valido_desde" TEXT,
  "valido_hasta" TEXT,
  "reemplazada_por" TEXT
) STRICT;

CREATE TABLE "decision_decisores" (
  "doc" TEXT NOT NULL REFERENCES "decision"("doc") ON DELETE CASCADE,
  "idx" INTEGER NOT NULL,
  "value" TEXT NOT NULL,
  PRIMARY KEY ("doc", "idx")
) STRICT;

CREATE TABLE "diagrama" (
  "doc" TEXT NOT NULL PRIMARY KEY REFERENCES "documentos"("path") ON DELETE CASCADE,
  "proyecto" TEXT NOT NULL,
  "clase" TEXT NOT NULL CHECK ("clase" IN ('flujo', 'proceso', 'secuencia', 'entidades', 'organizacion', 'arquitectura', 'cronograma', 'otro')),
  "version" TEXT NOT NULL
) STRICT;

CREATE TABLE "glosario" (
  "doc" TEXT NOT NULL PRIMARY KEY REFERENCES "documentos"("path") ON DELETE CASCADE
) STRICT;

CREATE TABLE "iniciativa" (
  "doc" TEXT NOT NULL PRIMARY KEY REFERENCES "documentos"("path") ON DELETE CASCADE,
  "proyecto" TEXT NOT NULL UNIQUE,
  "origen" TEXT NOT NULL CHECK ("origen" IN ('proyecto-asignado', 'objetivo-personal', 'objetivo-equipo')),
  "periodo" TEXT NOT NULL,
  "estado" TEXT NOT NULL CHECK ("estado" IN ('iniciando', 'en-progreso', 'bloqueada', 'entregada'))
) STRICT;

CREATE TABLE "iniciativa_sistemas" (
  "doc" TEXT NOT NULL REFERENCES "iniciativa"("doc") ON DELETE CASCADE,
  "idx" INTEGER NOT NULL,
  "value" TEXT NOT NULL,
  PRIMARY KEY ("doc", "idx")
) STRICT;

CREATE TABLE "iniciativa_personas" (
  "doc" TEXT NOT NULL REFERENCES "iniciativa"("doc") ON DELETE CASCADE,
  "idx" INTEGER NOT NULL,
  "value" TEXT NOT NULL,
  PRIMARY KEY ("doc", "idx")
) STRICT;

CREATE TABLE "insumo" (
  "doc" TEXT NOT NULL PRIMARY KEY REFERENCES "documentos"("path") ON DELETE CASCADE,
  "proyecto" TEXT NOT NULL,
  "formato" TEXT NOT NULL CHECK ("formato" IN ('pdf', 'docx', 'pptx', 'xlsx', 'html', 'yaml')),
  "original" TEXT NOT NULL
) STRICT;

CREATE TABLE "lineamiento" (
  "doc" TEXT NOT NULL PRIMARY KEY REFERENCES "documentos"("path") ON DELETE CASCADE,
  "area" TEXT NOT NULL,
  "fuente" TEXT NOT NULL,
  "estado" TEXT NOT NULL CHECK ("estado" IN ('aprobado', 'en-revision')),
  "fecha" TEXT,
  "valido_desde" TEXT,
  "valido_hasta" TEXT,
  "reemplazada_por" TEXT
) STRICT;

CREATE TABLE "persona" (
  "doc" TEXT NOT NULL PRIMARY KEY REFERENCES "documentos"("path") ON DELETE CASCADE,
  "rol" TEXT NOT NULL,
  "equipo" TEXT,
  "reports_to" TEXT
) STRICT;

CREATE TABLE "plan" (
  "doc" TEXT NOT NULL PRIMARY KEY REFERENCES "documentos"("path") ON DELETE CASCADE,
  "proyecto" TEXT NOT NULL,
  "source_of_truth" TEXT NOT NULL CHECK ("source_of_truth" IN ('cerebro', 'externa')),
  "external_tracker" TEXT,
  "last_review" TEXT NOT NULL
) STRICT;

CREATE TABLE "playbook" (
  "doc" TEXT NOT NULL PRIMARY KEY REFERENCES "documentos"("path") ON DELETE CASCADE,
  "proyecto" TEXT NOT NULL
) STRICT;

CREATE TABLE "pregunta" (
  "doc" TEXT NOT NULL PRIMARY KEY REFERENCES "documentos"("path") ON DELETE CASCADE,
  "proyecto" TEXT NOT NULL,
  "estado" TEXT NOT NULL CHECK ("estado" IN ('abierta', 'en-progreso', 'respondida')),
  "responsable" TEXT,
  "bloqueante" INTEGER NOT NULL,
  "created" TEXT NOT NULL,
  "respondida_por" TEXT
) STRICT;

CREATE TABLE "reunion" (
  "doc" TEXT NOT NULL PRIMARY KEY REFERENCES "documentos"("path") ON DELETE CASCADE,
  "proyecto" TEXT NOT NULL,
  "fecha" TEXT NOT NULL
) STRICT;

CREATE TABLE "reunion_asistentes" (
  "doc" TEXT NOT NULL REFERENCES "reunion"("doc") ON DELETE CASCADE,
  "idx" INTEGER NOT NULL,
  "value" TEXT NOT NULL,
  PRIMARY KEY ("doc", "idx")
) STRICT;

CREATE TABLE "sistema" (
  "doc" TEXT NOT NULL PRIMARY KEY REFERENCES "documentos"("path") ON DELETE CASCADE,
  "owner" TEXT NOT NULL,
  "categoria" TEXT NOT NULL CHECK ("categoria" IN ('sistema', 'herramienta', 'producto', 'proceso')),
  "estado" TEXT NOT NULL CHECK ("estado" IN ('activo', 'en-cambio', 'deprecado'))
) STRICT;

-- Un evento por campo fechado, no por documento: un tipo con dos
-- fechas aporta dos filas, y por eso la vista lleva `campo`.
CREATE VIEW "eventos" AS
  select t."fecha" as "fecha", 'Analisis' as "tipo", 'fecha' as "campo",
         d."path" as "doc", d."title" as "title",
         t."proyecto" as "proyecto"
    from "analisis" t join "documentos" d on d."path" = t."doc"
  union all
  select t."fecha" as "fecha", 'Decision' as "tipo", 'fecha' as "campo",
         d."path" as "doc", d."title" as "title",
         t."proyecto" as "proyecto"
    from "decision" t join "documentos" d on d."path" = t."doc"
  union all
  select t."valido_desde" as "fecha", 'Decision' as "tipo", 'valido_desde' as "campo",
         d."path" as "doc", d."title" as "title",
         t."proyecto" as "proyecto"
    from "decision" t join "documentos" d on d."path" = t."doc"
  union all
  select t."valido_hasta" as "fecha", 'Decision' as "tipo", 'valido_hasta' as "campo",
         d."path" as "doc", d."title" as "title",
         t."proyecto" as "proyecto"
    from "decision" t join "documentos" d on d."path" = t."doc"
  union all
  select t."fecha" as "fecha", 'Lineamiento' as "tipo", 'fecha' as "campo",
         d."path" as "doc", d."title" as "title",
         null as "proyecto"
    from "lineamiento" t join "documentos" d on d."path" = t."doc"
  union all
  select t."valido_desde" as "fecha", 'Lineamiento' as "tipo", 'valido_desde' as "campo",
         d."path" as "doc", d."title" as "title",
         null as "proyecto"
    from "lineamiento" t join "documentos" d on d."path" = t."doc"
  union all
  select t."valido_hasta" as "fecha", 'Lineamiento' as "tipo", 'valido_hasta' as "campo",
         d."path" as "doc", d."title" as "title",
         null as "proyecto"
    from "lineamiento" t join "documentos" d on d."path" = t."doc"
  union all
  select t."last_review" as "fecha", 'Plan' as "tipo", 'last_review' as "campo",
         d."path" as "doc", d."title" as "title",
         t."proyecto" as "proyecto"
    from "plan" t join "documentos" d on d."path" = t."doc"
  union all
  select t."created" as "fecha", 'Pregunta' as "tipo", 'created' as "campo",
         d."path" as "doc", d."title" as "title",
         t."proyecto" as "proyecto"
    from "pregunta" t join "documentos" d on d."path" = t."doc"
  union all
  select t."fecha" as "fecha", 'Reunion' as "tipo", 'fecha' as "campo",
         d."path" as "doc", d."title" as "title",
         t."proyecto" as "proyecto"
    from "reunion" t join "documentos" d on d."path" = t."doc"
  order by "fecha" desc;

-- Nueve tipos declaran `proyecto`: la unión se genera, no se
-- reteclea en cada consulta que la necesita.
CREATE VIEW "documento_proyecto" AS
  select "doc", "proyecto" from "analisis"
  union all
  select "doc", "proyecto" from "decision"
  union all
  select "doc", "proyecto" from "diagrama"
  union all
  select "doc", "proyecto" from "iniciativa"
  union all
  select "doc", "proyecto" from "insumo"
  union all
  select "doc", "proyecto" from "plan"
  union all
  select "doc", "proyecto" from "playbook"
  union all
  select "doc", "proyecto" from "pregunta"
  union all
  select "doc", "proyecto" from "reunion";

-- Solo los conteos: el texto de la pregunta puede llevar lo que
-- `PERFIL.md` marca confidencial, y estas consultas piden números.
CREATE TABLE "consultas" (
  "linea" INTEGER NOT NULL PRIMARY KEY,
  "fecha" TEXT NOT NULL,
  "docs" INTEGER NOT NULL,
  "completos" INTEGER NOT NULL,
  "citados" INTEGER NOT NULL,
  "modo" TEXT NOT NULL,
  "archivada" INTEGER NOT NULL
) STRICT;

-- Los tres estados de vigencia son una CONSULTA, no un enum: un
-- valor puede contradecir a las fechas que tiene al lado; un CASE no.
CREATE VIEW "vigencia" AS
  select d."path" as "doc", 'Decision' as "tipo", d."title" as "title",
         t."valido_desde" as "valido_desde", t."valido_hasta" as "valido_hasta",
         t."reemplazada_por" as "reemplazada_por", t."estado" as "estado",
         case
           when valido_hasta IS NULL then 'vigente'
           when valido_hasta IS NOT NULL AND reemplazada_por IS NOT NULL then 'reemplazada'
           when valido_hasta IS NOT NULL AND reemplazada_por IS NULL then 'caducada'
         end as "vigencia"
    from "decision" t join "documentos" d on d."path" = t."doc"
  union all
  select d."path" as "doc", 'Lineamiento' as "tipo", d."title" as "title",
         t."valido_desde" as "valido_desde", t."valido_hasta" as "valido_hasta",
         t."reemplazada_por" as "reemplazada_por", t."estado" as "estado",
         case
           when valido_hasta IS NULL then 'vigente'
           when valido_hasta IS NOT NULL AND reemplazada_por IS NOT NULL then 'reemplazada'
           when valido_hasta IS NOT NULL AND reemplazada_por IS NULL then 'caducada'
         end as "vigencia"
    from "lineamiento" t join "documentos" d on d."path" = t."doc";

-- Devuelve rutas y ranking, nunca contenido: entregar fragmentos
-- dejaría al lector donde empezó, leyendo texto para decidir qué leer.
CREATE VIRTUAL TABLE "busqueda" USING fts5(
  "path" UNINDEXED,
  "title",
  "description",
  "resumen",
  "cuerpo",
  tokenize = 'unicode61 remove_diacritics 2'
);
