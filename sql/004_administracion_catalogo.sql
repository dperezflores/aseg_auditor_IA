ALTER TABLE catalogo_importaciones
    DROP CONSTRAINT IF EXISTS catalogo_importaciones_estado_check;

ALTER TABLE catalogo_importaciones
    ADD CONSTRAINT catalogo_importaciones_estado_check
    CHECK (estado IN ('BORRADOR', 'VALIDADO', 'ACTIVO', 'ARCHIVADO', 'ERROR'));

ALTER TABLE catalogo_importaciones
    ADD COLUMN IF NOT EXISTS nombre_version text,
    ADD COLUMN IF NOT EXISTS creado_por text,
    ADD COLUMN IF NOT EXISTS publicado_por text,
    ADD COLUMN IF NOT EXISTS notas text NOT NULL DEFAULT '';

CREATE TABLE IF NOT EXISTS roles (
    codigo text PRIMARY KEY,
    nombre text NOT NULL,
    descripcion text NOT NULL DEFAULT '',
    activo boolean NOT NULL DEFAULT true
);

INSERT INTO roles (codigo, nombre, descripcion)
VALUES
    ('ADMIN_GENERAL', 'Administrador general', 'Control total de la aplicación y del catálogo.'),
    ('ADMIN_CATALOGO', 'Administrador del catálogo', 'Edita borradores y reglas del catálogo.'),
    ('APROBADOR_CATALOGO', 'Aprobador del catálogo', 'Valida y publica versiones del catálogo.'),
    ('USUARIO', 'Usuario operativo', 'Integra y analiza expedientes.'),
    ('CONSULTA', 'Consulta', 'Acceso de solo lectura.')
ON CONFLICT (codigo) DO UPDATE
SET nombre = EXCLUDED.nombre,
    descripcion = EXCLUDED.descripcion;

CREATE TABLE IF NOT EXISTS usuario_roles (
    usuario_id uuid NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    rol_codigo text NOT NULL REFERENCES roles(codigo),
    asignado_por text,
    asignado_en timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (usuario_id, rol_codigo)
);

CREATE TABLE IF NOT EXISTS reglas_aplicabilidad (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    importacion_id uuid NOT NULL REFERENCES catalogo_importaciones(id) ON DELETE CASCADE,
    catalogo_documento_id uuid NOT NULL REFERENCES catalogo_documentos(id) ON DELETE CASCADE,
    orden integer NOT NULL CHECK (orden > 0),
    tipo_regla text NOT NULL CHECK (tipo_regla IN ('SIEMPRE', 'NO_APLICA', 'CONDICIONAL')),
    fuente text NOT NULL CHECK (fuente IN ('VALOR_FIJO', 'CAMPO_EXTRAIDO', 'DOCUMENTO_PRESENTE')),
    fuente_tipo_documental text,
    fuente_campo text,
    operador text NOT NULL CHECK (operador IN ('EXISTE', 'NO_EXISTE', 'IGUAL', 'DISTINTO', 'MAYOR_QUE', 'MENOR_QUE', 'CONTIENE')),
    valor_esperado jsonb NOT NULL DEFAULT 'null'::jsonb,
    resultado_verdadero text NOT NULL CHECK (resultado_verdadero IN ('APLICA', 'NO_APLICA', 'PENDIENTE')),
    resultado_falso text NOT NULL CHECK (resultado_falso IN ('APLICA', 'NO_APLICA', 'PENDIENTE')),
    resultado_sin_dato text NOT NULL DEFAULT 'PENDIENTE' CHECK (resultado_sin_dato IN ('APLICA', 'NO_APLICA', 'PENDIENTE')),
    justificacion text NOT NULL DEFAULT '',
    activa boolean NOT NULL DEFAULT true,
    estado_revision text NOT NULL DEFAULT 'Pendiente' CHECK (estado_revision IN ('Pendiente', 'Revisado', 'Aprobado')),
    creado_por text,
    actualizado_por text,
    creado_en timestamptz NOT NULL DEFAULT now(),
    actualizado_en timestamptz NOT NULL DEFAULT now(),
    UNIQUE (catalogo_documento_id, orden),
    CHECK (
        tipo_regla <> 'CONDICIONAL'
        OR fuente = 'DOCUMENTO_PRESENTE'
        OR NULLIF(btrim(fuente_campo), '') IS NOT NULL
    )
);

CREATE TABLE IF NOT EXISTS auditoria_catalogo (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    importacion_id uuid REFERENCES catalogo_importaciones(id) ON DELETE SET NULL,
    usuario_externo text NOT NULL,
    entidad text NOT NULL,
    entidad_id text,
    accion text NOT NULL,
    valores_anteriores jsonb,
    valores_nuevos jsonb,
    motivo text NOT NULL DEFAULT '',
    creado_en timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE expedientes
    ADD COLUMN IF NOT EXISTS catalogo_importacion_id uuid
        REFERENCES catalogo_importaciones(id) ON DELETE RESTRICT;

CREATE TABLE IF NOT EXISTS expediente_requisitos (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    expediente_id uuid NOT NULL REFERENCES expedientes(id) ON DELETE CASCADE,
    importacion_id uuid NOT NULL REFERENCES catalogo_importaciones(id) ON DELETE RESTRICT,
    catalogo_documento_origen_id uuid REFERENCES catalogo_documentos(id) ON DELETE SET NULL,
    clave_catalogo text NOT NULL,
    orden integer NOT NULL CHECK (orden > 0),
    etapa text NOT NULL CHECK (etapa IN ('PPP', 'ADJ', 'CNT', 'EJE', 'ETR')),
    tipo_documental text NOT NULL,
    nombre_documento text NOT NULL,
    obligatoriedad text NOT NULL,
    admite_multiples boolean NOT NULL DEFAULT false,
    definicion_snapshot jsonb NOT NULL CHECK (jsonb_typeof(definicion_snapshot) = 'object'),
    aplicabilidad text NOT NULL DEFAULT 'PENDIENTE' CHECK (aplicabilidad IN ('APLICA', 'NO_APLICA', 'OPCIONAL', 'PENDIENTE')),
    justificacion_aplicabilidad text NOT NULL DEFAULT '',
    resultado_ia text NOT NULL DEFAULT 'SIN_ANALIZAR' CHECK (resultado_ia IN ('SIN_ANALIZAR', 'PROCESANDO', 'CUMPLE', 'NO_CUMPLE', 'REVISION_REQUERIDA', 'ERROR')),
    ultimo_documento_id uuid REFERENCES documentos(id) ON DELETE SET NULL,
    creado_en timestamptz NOT NULL DEFAULT now(),
    actualizado_en timestamptz NOT NULL DEFAULT now(),
    UNIQUE (expediente_id, clave_catalogo)
);

CREATE TABLE IF NOT EXISTS archivos_expediente (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    expediente_id uuid NOT NULL REFERENCES expedientes(id) ON DELETE CASCADE,
    requisito_id uuid REFERENCES expediente_requisitos(id) ON DELETE SET NULL,
    etapa text NOT NULL CHECK (etapa IN ('PPP', 'ADJ', 'CNT', 'EJE', 'ETR')),
    nombre_archivo text NOT NULL,
    huella_sha256 char(64) NOT NULL,
    mime_type text,
    tamano_bytes bigint CHECK (tamano_bytes IS NULL OR tamano_bytes >= 0),
    referencia_contenido text,
    estado text NOT NULL DEFAULT 'CARGADO' CHECK (estado IN ('CARGADO', 'PROCESANDO', 'ANALIZADO', 'ERROR', 'ELIMINADO')),
    creado_por text,
    creado_en timestamptz NOT NULL DEFAULT now(),
    actualizado_en timestamptz NOT NULL DEFAULT now(),
    UNIQUE (expediente_id, huella_sha256, nombre_archivo)
);

ALTER TABLE documentos
    ADD COLUMN IF NOT EXISTS archivo_expediente_id uuid
        REFERENCES archivos_expediente(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_usuario_roles_rol
    ON usuario_roles (rol_codigo, usuario_id);

CREATE INDEX IF NOT EXISTS idx_reglas_aplicabilidad_documento
    ON reglas_aplicabilidad (catalogo_documento_id, activa, orden);

CREATE INDEX IF NOT EXISTS idx_auditoria_catalogo_version
    ON auditoria_catalogo (importacion_id, creado_en DESC);

CREATE INDEX IF NOT EXISTS idx_expediente_requisitos_control
    ON expediente_requisitos (expediente_id, etapa, orden);

CREATE INDEX IF NOT EXISTS idx_archivos_expediente_control
    ON archivos_expediente (expediente_id, requisito_id, estado, actualizado_en DESC);
