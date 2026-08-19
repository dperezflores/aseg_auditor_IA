ALTER TABLE expedientes
    ADD COLUMN IF NOT EXISTS datos_aplicabilidad jsonb NOT NULL
        DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(datos_aplicabilidad) = 'object'),
    ADD COLUMN IF NOT EXISTS aplicabilidad_actualizada_en timestamptz;
