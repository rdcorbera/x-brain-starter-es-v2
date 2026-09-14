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
  "classification" TEXT CHECK ("classification" IN ('public', 'internal', 'confidential', 'restricted')),
  "generated_by" TEXT,
  "generated_at" TEXT,
  "status" TEXT CHECK ("status" IN ('draft', 'stable', 'deprecated')),
  "stale_after" TEXT,
  "resumen" TEXT NOT NULL,
  "resumen_hash" TEXT,
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
  "estado" TEXT NOT NULL CHECK ("estado" IN ('propuesta', 'aceptada', 'reemplazada', 'obsoleta')),
  "fecha" TEXT NOT NULL,
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
  "origen" TEXT NOT NULL
) STRICT;

CREATE TABLE "lineamiento" (
  "doc" TEXT NOT NULL PRIMARY KEY REFERENCES "documentos"("path") ON DELETE CASCADE,
  "area" TEXT NOT NULL,
  "fuente" TEXT NOT NULL,
  "vigencia" TEXT NOT NULL CHECK ("vigencia" IN ('vigente', 'en-revision', 'derogado'))
) STRICT;

CREATE TABLE "persona" (
  "doc" TEXT NOT NULL PRIMARY KEY REFERENCES "documentos"("path") ON DELETE CASCADE,
  "rol" TEXT NOT NULL,
  "equipo" TEXT,
  "reporta_a" TEXT
) STRICT;

CREATE TABLE "plan" (
  "doc" TEXT NOT NULL PRIMARY KEY REFERENCES "documentos"("path") ON DELETE CASCADE,
  "proyecto" TEXT NOT NULL,
  "fuente_de_verdad" TEXT NOT NULL CHECK ("fuente_de_verdad" IN ('cerebro', 'externa')),
  "tracker_externo" TEXT,
  "ultima_revision" TEXT NOT NULL
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
  "fecha_creacion" TEXT NOT NULL,
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
  "dueño" TEXT NOT NULL,
  "categoria" TEXT NOT NULL CHECK ("categoria" IN ('sistema', 'herramienta', 'producto', 'proceso')),
  "estado" TEXT NOT NULL CHECK ("estado" IN ('activo', 'en-cambio', 'deprecado'))
) STRICT;
