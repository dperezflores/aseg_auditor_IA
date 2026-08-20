ALTER TABLE documentos
    ADD COLUMN IF NOT EXISTS eliminado_en timestamptz,
    ADD COLUMN IF NOT EXISTS eliminado_por text,
    ADD COLUMN IF NOT EXISTS motivo_eliminacion text;

CREATE INDEX IF NOT EXISTS idx_documentos_expediente_vigentes
    ON documentos (expediente_id, actualizado_en DESC)
    WHERE eliminado_en IS NULL;
