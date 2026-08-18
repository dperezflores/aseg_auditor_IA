CREATE TABLE IF NOT EXISTS catalogo_importaciones (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    archivo_nombre text NOT NULL,
    archivo_sha256 char(64) NOT NULL UNIQUE,
    estado text NOT NULL DEFAULT 'VALIDADO'
        CHECK (estado IN ('VALIDADO', 'ACTIVO', 'ARCHIVADO', 'ERROR')),
    resumen jsonb NOT NULL DEFAULT '{}'::jsonb,
    advertencias jsonb NOT NULL DEFAULT '[]'::jsonb,
    creado_en timestamptz NOT NULL DEFAULT now(),
    activado_en timestamptz
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_catalogo_importacion_activa
    ON catalogo_importaciones ((estado))
    WHERE estado = 'ACTIVO';

CREATE TABLE IF NOT EXISTS tipos_documentales (
    importacion_id uuid NOT NULL
        REFERENCES catalogo_importaciones(id) ON DELETE CASCADE,
    tipo_documental text NOT NULL,
    etapa text NOT NULL CHECK (etapa IN ('PPP', 'ADJ', 'CNT', 'EJE', 'ETR')),
    PRIMARY KEY (importacion_id, tipo_documental)
);

CREATE TABLE IF NOT EXISTS catalogo_documentos (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    importacion_id uuid NOT NULL
        REFERENCES catalogo_importaciones(id) ON DELETE CASCADE,
    clave_catalogo text NOT NULL,
    orden_en_procedimiento integer NOT NULL CHECK (orden_en_procedimiento > 0),
    activo boolean NOT NULL,
    version_catalogo text NOT NULL,
    procedimiento text NOT NULL CHECK (procedimiento IN ('LPU', 'LSI', 'DIR', 'ADM')),
    etapa text NOT NULL CHECK (etapa IN ('PPP', 'ADJ', 'CNT', 'EJE', 'ETR')),
    tipo_documental text NOT NULL,
    codigo_base text NOT NULL,
    nombre_documento text NOT NULL,
    obligatoriedad text NOT NULL
        CHECK (obligatoriedad IN ('Obligatorio', 'Condicional', 'Opcional', 'No aplica', 'Por definir')),
    condicion_aplicabilidad text NOT NULL,
    admite_multiples boolean NOT NULL,
    patron_consecutivo text,
    riesgo_predeterminado text NOT NULL,
    regla_formatos text NOT NULL,
    criterios_identificacion_ia text NOT NULL,
    datos_clave_a_validar text NOT NULL,
    fundamento_normativo text NOT NULL,
    vigencia_desde date,
    vigencia_hasta date,
    observaciones text NOT NULL DEFAULT '',
    estado_revision text NOT NULL
        CHECK (estado_revision IN ('Pendiente', 'Revisado', 'Aprobado')),
    fuente_origen text NOT NULL,
    creado_en timestamptz NOT NULL DEFAULT now(),
    UNIQUE (importacion_id, clave_catalogo),
    FOREIGN KEY (importacion_id, tipo_documental)
        REFERENCES tipos_documentales(importacion_id, tipo_documental),
    CHECK (vigencia_hasta IS NULL OR vigencia_desde IS NULL OR vigencia_hasta >= vigencia_desde),
    CHECK (admite_multiples OR patron_consecutivo IS NULL)
);

CREATE TABLE IF NOT EXISTS formatos_documento (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    importacion_id uuid NOT NULL
        REFERENCES catalogo_importaciones(id) ON DELETE CASCADE,
    formato_id text NOT NULL,
    catalogo_documento_id uuid NOT NULL
        REFERENCES catalogo_documentos(id) ON DELETE CASCADE,
    extension text NOT NULL,
    mime_type text NOT NULL,
    nombre_por_formato text NOT NULL,
    modalidad_formato text NOT NULL
        CHECK (modalidad_formato IN ('Requerido', 'Alternativo', 'Por definir')),
    activo boolean NOT NULL,
    estado_revision text NOT NULL
        CHECK (estado_revision IN ('Pendiente', 'Revisado', 'Aprobado')),
    observaciones text NOT NULL DEFAULT '',
    fuente_origen text NOT NULL,
    UNIQUE (importacion_id, formato_id)
);

CREATE TABLE IF NOT EXISTS procedimientos_validacion (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    importacion_id uuid NOT NULL
        REFERENCES catalogo_importaciones(id) ON DELETE CASCADE,
    procedimiento_id text NOT NULL,
    tipo_documental text NOT NULL,
    orden integer NOT NULL CHECK (orden > 0),
    procedimiento_validacion text NOT NULL,
    resultado_esperado text,
    evidencia_requerida text,
    riesgo_codigo text NOT NULL,
    activo boolean NOT NULL,
    estado_revision text NOT NULL
        CHECK (estado_revision IN ('Pendiente', 'Revisado', 'Aprobado')),
    observaciones text NOT NULL DEFAULT '',
    UNIQUE (importacion_id, procedimiento_id),
    FOREIGN KEY (importacion_id, tipo_documental)
        REFERENCES tipos_documentales(importacion_id, tipo_documental)
);

CREATE TABLE IF NOT EXISTS campos_extraccion (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    importacion_id uuid NOT NULL
        REFERENCES catalogo_importaciones(id) ON DELETE CASCADE,
    campo_id text NOT NULL,
    tipo_documental text NOT NULL,
    orden_salida integer NOT NULL CHECK (orden_salida > 0),
    nombre_tecnico text NOT NULL,
    etiqueta_salida text NOT NULL,
    tipo_dato text NOT NULL
        CHECK (tipo_dato IN ('Texto', 'Fecha', 'Decimal', 'Entero', 'Booleano', 'Lista', 'JSON')),
    obligatorio_ia boolean NOT NULL,
    instruccion_extraccion text NOT NULL,
    mostrar_en_detalle boolean NOT NULL,
    celda_pt text,
    estado_revision text NOT NULL
        CHECK (estado_revision IN ('Pendiente', 'Revisado', 'Aprobado')),
    observaciones text NOT NULL DEFAULT '',
    UNIQUE (importacion_id, campo_id),
    UNIQUE (importacion_id, tipo_documental, nombre_tecnico),
    FOREIGN KEY (importacion_id, tipo_documental)
        REFERENCES tipos_documentales(importacion_id, tipo_documental)
);

ALTER TABLE documentos
    ADD COLUMN IF NOT EXISTS catalogo_documento_id uuid;

ALTER TABLE documentos
    ADD COLUMN IF NOT EXISTS clave_catalogo text;

ALTER TABLE documentos
    ADD COLUMN IF NOT EXISTS tipo_documental text;

CREATE INDEX IF NOT EXISTS idx_catalogo_documentos_operacion
    ON catalogo_documentos (
        importacion_id,
        procedimiento,
        etapa,
        estado_revision,
        activo,
        orden_en_procedimiento
    );

CREATE INDEX IF NOT EXISTS idx_formatos_catalogo_documento
    ON formatos_documento (catalogo_documento_id, activo);

CREATE INDEX IF NOT EXISTS idx_procedimientos_tipo
    ON procedimientos_validacion (importacion_id, tipo_documental, orden);

CREATE INDEX IF NOT EXISTS idx_campos_tipo
    ON campos_extraccion (importacion_id, tipo_documental, orden_salida);

CREATE OR REPLACE VIEW catalogo_documentos_vigentes AS
SELECT
    d.*
FROM catalogo_documentos d
JOIN catalogo_importaciones i ON i.id = d.importacion_id
WHERE i.estado = 'ACTIVO'
  AND d.activo
  AND d.estado_revision = 'Aprobado'
  AND (d.vigencia_desde IS NULL OR d.vigencia_desde <= CURRENT_DATE)
  AND (d.vigencia_hasta IS NULL OR d.vigencia_hasta >= CURRENT_DATE);

