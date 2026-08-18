CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS usuarios (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id text NOT NULL UNIQUE,
    nombre text NOT NULL,
    creado_en timestamptz NOT NULL DEFAULT now(),
    actualizado_en timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS expedientes (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    usuario_id uuid NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    nombre text NOT NULL,
    procedimiento text NOT NULL CHECK (procedimiento IN ('DIR', 'LPU', 'LSI')),
    creado_en timestamptz NOT NULL DEFAULT now(),
    actualizado_en timestamptz NOT NULL DEFAULT now(),
    UNIQUE (usuario_id, nombre)
);

CREATE TABLE IF NOT EXISTS documentos (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    expediente_id uuid NOT NULL REFERENCES expedientes(id) ON DELETE CASCADE,
    categoria text NOT NULL,
    nombre_archivo text NOT NULL,
    huella_sha256 char(64) NOT NULL,
    clave_procesamiento text NOT NULL,
    estado text NOT NULL CHECK (estado IN ('PROCESANDO', 'OK', 'ERROR')),
    error text,
    modelo text NOT NULL,
    version_prompt text NOT NULL,
    intentos integer NOT NULL DEFAULT 0,
    creado_en timestamptz NOT NULL DEFAULT now(),
    actualizado_en timestamptz NOT NULL DEFAULT now(),
    UNIQUE (expediente_id, clave_procesamiento)
);

CREATE TABLE IF NOT EXISTS resultados_extraccion (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    documento_id uuid NOT NULL UNIQUE REFERENCES documentos(id) ON DELETE CASCADE,
    datos jsonb NOT NULL,
    metadatos jsonb NOT NULL DEFAULT '{}'::jsonb,
    creado_en timestamptz NOT NULL DEFAULT now(),
    actualizado_en timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_expedientes_usuario
    ON expedientes (usuario_id, actualizado_en DESC);

CREATE INDEX IF NOT EXISTS idx_documentos_expediente_estado
    ON documentos (expediente_id, estado, actualizado_en DESC);

CREATE INDEX IF NOT EXISTS idx_documentos_huella
    ON documentos (huella_sha256);

