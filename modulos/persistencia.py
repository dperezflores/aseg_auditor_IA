from __future__ import annotations

import json
import os
from contextlib import contextmanager
from typing import Any, Iterator

import streamlit as st


HISTORIAL_BASE = {
    "Estimaciones": [],
    "Facturas": [],
    "Comprobantes de Pago": [],
    "Pólizas": [],
}


def _secreto(nombre: str, default: str = "") -> str:
    try:
        return str(st.secrets.get(nombre, default))
    except Exception:
        return os.getenv(nombre, default)


def disponible() -> bool:
    return bool(_secreto("DATABASE_URL"))


def cargar_roles_usuario(usuario_externo: str) -> set[str]:
    with _conexion() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT ur.rol_codigo
                FROM usuarios u
                JOIN usuario_roles ur ON ur.usuario_id = u.id
                JOIN roles r ON r.codigo = ur.rol_codigo AND r.activo
                WHERE u.external_id = %s
                """,
                (usuario_externo,),
            )
            return {fila[0] for fila in cur.fetchall()}


def cargar_catalogo_vigente(procedimiento: str):
    """Devuelve únicamente definiciones aprobadas de la importación activa."""
    if not disponible():
        return []

    from modulos.catalogo import desde_fila

    try:
        with _conexion() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        d.id, d.clave_catalogo, d.orden_en_procedimiento,
                        d.procedimiento, d.etapa, d.tipo_documental, d.codigo_base,
                        d.nombre_documento, d.obligatoriedad,
                        d.condicion_aplicabilidad, d.admite_multiples,
                        d.patron_consecutivo,
                        COALESCE(
                            (
                                SELECT array_agg(DISTINCT f.extension)
                                FROM formatos_documento f
                                WHERE f.catalogo_documento_id = d.id
                                  AND f.activo
                                  AND f.extension IS NOT NULL
                            ),
                            ARRAY['pdf']::text[]
                        ) AS extensiones,
                        d.version_catalogo,
                        d.criterios_identificacion_ia,
                        d.datos_clave_a_validar,
                        d.fundamento_normativo,
                        COALESCE(
                            (
                                SELECT jsonb_agg(
                                    jsonb_build_object(
                                        'orden', c.orden_salida,
                                        'nombre_tecnico', c.nombre_tecnico,
                                        'etiqueta', c.etiqueta_salida,
                                        'tipo_dato', c.tipo_dato,
                                        'obligatorio', c.obligatorio_ia,
                                        'instruccion', c.instruccion_extraccion,
                                        'estado_revision', c.estado_revision
                                    ) ORDER BY c.orden_salida
                                )
                                FROM campos_extraccion c
                                WHERE c.importacion_id = d.importacion_id
                                  AND c.tipo_documental = d.tipo_documental
                            ),
                            '[]'::jsonb
                        ) AS campos,
                        COALESCE(
                            (
                                SELECT jsonb_agg(
                                    jsonb_build_object(
                                        'orden', p.orden,
                                        'procedimiento_id', p.procedimiento_id,
                                        'procedimiento', p.procedimiento_validacion,
                                        'resultado_esperado', p.resultado_esperado,
                                        'evidencia_requerida', p.evidencia_requerida,
                                        'riesgo_codigo', p.riesgo_codigo,
                                        'estado_revision', p.estado_revision
                                    ) ORDER BY p.orden
                                )
                                FROM procedimientos_validacion p
                                WHERE p.importacion_id = d.importacion_id
                                  AND p.tipo_documental = d.tipo_documental
                                  AND p.activo
                            ),
                            '[]'::jsonb
                        ) AS procedimientos,
                        COALESCE(
                            (
                                SELECT jsonb_agg(
                                    jsonb_build_object(
                                        'id', r.id,
                                        'orden', r.orden,
                                        'tipo_regla', r.tipo_regla,
                                        'fuente', r.fuente,
                                        'fuente_tipo_documental', r.fuente_tipo_documental,
                                        'fuente_campo', r.fuente_campo,
                                        'operador', r.operador,
                                        'valor_esperado', r.valor_esperado,
                                        'resultado_verdadero', r.resultado_verdadero,
                                        'resultado_falso', r.resultado_falso,
                                        'resultado_sin_dato', r.resultado_sin_dato,
                                        'justificacion', r.justificacion,
                                        'estado_revision', r.estado_revision
                                    ) ORDER BY r.orden
                                )
                                FROM reglas_aplicabilidad r
                                WHERE r.catalogo_documento_id = d.id
                                  AND r.activa
                                  AND r.estado_revision = 'Aprobado'
                            ),
                            '[]'::jsonb
                        ) AS reglas_aplicabilidad
                    FROM catalogo_documentos_vigentes d
                    WHERE d.procedimiento = %s
                    ORDER BY d.orden_en_procedimiento, d.clave_catalogo
                    """,
                    (procedimiento[:3],),
                )
                return [desde_fila(fila) for fila in cur.fetchall()]
    except Exception as exc:
        # La migración del catálogo puede desplegarse después del código sin
        # interrumpir la operación actual de los expedientes.
        if exc.__class__.__name__ in {"UndefinedTable", "UndefinedColumn"}:
            return []
        raise


def asegurar_snapshot_expediente(expediente_id: str, procedimiento: str) -> None:
    """Fija una copia del catálogo activo sin modificarla en actualizaciones futuras."""
    from modulos.catalogo import a_snapshot
    from psycopg.types.json import Jsonb

    with _conexion() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM expediente_requisitos WHERE expediente_id = %s",
                (expediente_id,),
            )
            if cur.fetchone()[0] > 0:
                return

    definiciones = cargar_catalogo_vigente(procedimiento)
    if not definiciones:
        return
    with _conexion() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT catalogo_importacion_id FROM expedientes WHERE id = %s",
                (expediente_id,),
            )
            fila = cur.fetchone()
            if not fila:
                raise RuntimeError("No se encontró el expediente activo")
            importacion_id = fila[0]
            if not importacion_id:
                cur.execute(
                    "SELECT id FROM catalogo_importaciones WHERE estado = 'ACTIVO'",
                )
                activa = cur.fetchone()
                if not activa:
                    return
                importacion_id = activa[0]
                cur.execute(
                    "UPDATE expedientes SET catalogo_importacion_id = %s WHERE id = %s",
                    (importacion_id, expediente_id),
                )

            for documento in definiciones:
                cur.execute(
                    """
                    INSERT INTO expediente_requisitos (
                        expediente_id, importacion_id, catalogo_documento_origen_id,
                        clave_catalogo, orden, etapa, tipo_documental,
                        nombre_documento, obligatoriedad, admite_multiples,
                        definicion_snapshot
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (expediente_id, clave_catalogo) DO NOTHING
                    """,
                    (
                        expediente_id, importacion_id, documento.id,
                        documento.clave_catalogo, documento.orden, documento.etapa,
                        documento.tipo_documental, documento.nombre,
                        documento.obligatoriedad, documento.admite_multiples,
                        Jsonb(a_snapshot(documento)),
                    ),
                )
        conn.commit()


def cargar_catalogo_expediente(expediente_id: str, procedimiento: str):
    """Lee la fotografía del expediente; la crea una sola vez si aún no existe."""
    from modulos.catalogo import desde_snapshot

    try:
        asegurar_snapshot_expediente(expediente_id, procedimiento)
        with _conexion() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT definicion_snapshot
                    FROM expediente_requisitos
                    WHERE expediente_id = %s
                    ORDER BY orden, clave_catalogo
                    """,
                    (expediente_id,),
                )
                return [desde_snapshot(fila[0]) for fila in cur.fetchall()]
    except Exception as exc:
        if exc.__class__.__name__ in {"UndefinedTable", "UndefinedColumn"}:
            return cargar_catalogo_vigente(procedimiento)
        raise


@contextmanager
def _conexion() -> Iterator[Any]:
    if not disponible():
        raise RuntimeError("DATABASE_URL no está configurada")

    import psycopg

    with psycopg.connect(_secreto("DATABASE_URL"), connect_timeout=10) as conn:
        yield conn


def obtener_o_crear_expediente(
    nombre: str,
    procedimiento: str,
    usuario_externo: str,
) -> tuple[str, bool]:
    with _conexion() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO usuarios (external_id, nombre)
                VALUES (%s, %s)
                ON CONFLICT (external_id)
                DO UPDATE SET nombre = EXCLUDED.nombre
                RETURNING id
                """,
                (usuario_externo, usuario_externo),
            )
            usuario_id = cur.fetchone()[0]
            cur.execute(
                """
                SELECT id
                FROM expedientes
                WHERE usuario_id = %s AND nombre = %s
                """,
                (usuario_id, nombre),
            )
            expediente_existente = cur.fetchone()

            if expediente_existente:
                expediente_id = expediente_existente[0]
                creado = False
                cur.execute(
                    """
                    UPDATE expedientes
                    SET procedimiento = %s, actualizado_en = now()
                    WHERE id = %s
                    """,
                    (procedimiento[:3], expediente_id),
                )
            else:
                cur.execute(
                    """
                    INSERT INTO expedientes (usuario_id, nombre, procedimiento)
                    VALUES (%s, %s, %s)
                    RETURNING id
                    """,
                    (usuario_id, nombre, procedimiento[:3]),
                )
                expediente_id = cur.fetchone()[0]
                creado = True
        conn.commit()
    expediente_texto = str(expediente_id)
    try:
        asegurar_snapshot_expediente(expediente_texto, procedimiento)
    except Exception as exc:
        if exc.__class__.__name__ not in {"UndefinedTable", "UndefinedColumn"}:
            raise
    return expediente_texto, creado


def cargar_expediente(expediente_id: str) -> tuple[dict[str, list], set[str]]:
    historial = {k: list(v) for k, v in HISTORIAL_BASE.items()}
    procesados: set[str] = set()

    with _conexion() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT d.categoria, d.clave_procesamiento, r.datos
                FROM documentos d
                JOIN resultados_extraccion r ON r.documento_id = d.id
                WHERE d.expediente_id = %s AND d.estado = 'OK'
                ORDER BY d.creado_en, r.creado_en
                """,
                (expediente_id,),
            )
            for categoria, clave, datos in cur.fetchall():
                historial.setdefault(categoria, []).extend(datos or [])
                procesados.add(clave)
    return historial, procesados


def cargar_control_expediente(expediente_id: str) -> tuple[dict[str, str], list[dict]]:
    """Carga respuestas de aplicabilidad y documentos registrados en Neon."""
    datos_aplicabilidad: dict[str, str] = {}
    archivos: list[dict] = []

    with _conexion() as conn:
        with conn.cursor() as cur:
            cur.execute("SAVEPOINT cargar_aplicabilidad")
            try:
                cur.execute(
                    """
                    SELECT datos_aplicabilidad
                    FROM expedientes
                    WHERE id = %s
                    """,
                    (expediente_id,),
                )
                fila = cur.fetchone()
                datos_aplicabilidad = dict((fila and fila[0]) or {})
            except Exception as exc:
                if exc.__class__.__name__ != "UndefinedColumn":
                    raise
                cur.execute("ROLLBACK TO SAVEPOINT cargar_aplicabilidad")

            cur.execute("SAVEPOINT cargar_archivos_expediente")
            try:
                cur.execute(
                    """
                    SELECT a.nombre_archivo, a.huella_sha256, a.estado,
                           er.clave_catalogo, er.tipo_documental
                    FROM archivos_expediente a
                    LEFT JOIN expediente_requisitos er ON er.id = a.requisito_id
                    WHERE a.expediente_id = %s AND a.estado <> 'ELIMINADO'
                    UNION ALL
                    SELECT d.nombre_archivo, d.huella_sha256, d.estado,
                           d.clave_catalogo, d.tipo_documental
                    FROM documentos d
                    WHERE d.expediente_id = %s
                      AND NOT EXISTS (
                          SELECT 1
                          FROM archivos_expediente a
                          WHERE a.expediente_id = d.expediente_id
                            AND a.huella_sha256 = d.huella_sha256
                            AND a.nombre_archivo = d.nombre_archivo
                            AND a.estado <> 'ELIMINADO'
                      )
                    ORDER BY 1
                    """,
                    (expediente_id, expediente_id),
                )
            except Exception as exc:
                if exc.__class__.__name__ not in {"UndefinedTable", "UndefinedColumn"}:
                    raise
                cur.execute("ROLLBACK TO SAVEPOINT cargar_archivos_expediente")
                cur.execute(
                    """
                    SELECT nombre_archivo, huella_sha256, estado,
                           clave_catalogo, tipo_documental
                    FROM documentos
                    WHERE expediente_id = %s
                    ORDER BY creado_en, nombre_archivo
                    """,
                    (expediente_id,),
                )
            archivos = [
                {
                    "nombre": nombre,
                    "huella": huella,
                    "estado_procesamiento": estado,
                    "clave_catalogo": clave_catalogo,
                    "tipo_documental": tipo_documental,
                    "origen": "guardado",
                }
                for nombre, huella, estado, clave_catalogo, tipo_documental
                in cur.fetchall()
            ]
    return datos_aplicabilidad, archivos


def cargar_resultados_requisitos(expediente_id: str) -> dict[str, str]:
    try:
        with _conexion() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT clave_catalogo, resultado_ia
                    FROM expediente_requisitos
                    WHERE expediente_id = %s
                    """,
                    (expediente_id,),
                )
                return {clave: resultado for clave, resultado in cur.fetchall()}
    except Exception as exc:
        if exc.__class__.__name__ in {"UndefinedTable", "UndefinedColumn"}:
            return {}
        raise


def registrar_archivo_cargado(
    expediente_id: str,
    etapa: str,
    nombre_archivo: str,
    huella: str,
    mime_type: str | None,
    tamano_bytes: int | None,
    clave_catalogo: str | None,
    usuario: str,
) -> str | None:
    """Registra metadatos al cargar; el PDF permanece fuera de PostgreSQL."""
    try:
        with _conexion() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id FROM expediente_requisitos
                    WHERE expediente_id = %s AND clave_catalogo = %s
                    """,
                    (expediente_id, clave_catalogo),
                )
                fila = cur.fetchone()
                requisito_id = fila[0] if fila else None
                cur.execute(
                    """
                    INSERT INTO archivos_expediente (
                        expediente_id, requisito_id, etapa, nombre_archivo,
                        huella_sha256, mime_type, tamano_bytes, creado_por
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (expediente_id, huella_sha256, nombre_archivo)
                    DO UPDATE SET requisito_id = COALESCE(EXCLUDED.requisito_id, archivos_expediente.requisito_id),
                                  estado = CASE WHEN archivos_expediente.estado = 'ANALIZADO' THEN 'ANALIZADO' ELSE 'CARGADO' END,
                                  actualizado_en = now()
                    RETURNING id
                    """,
                    (
                        expediente_id, requisito_id, etapa, nombre_archivo,
                        huella, mime_type, tamano_bytes, usuario,
                    ),
                )
                archivo_id = cur.fetchone()[0]
            conn.commit()
        return str(archivo_id)
    except Exception as exc:
        if exc.__class__.__name__ in {"UndefinedTable", "UndefinedColumn"}:
            return None
        raise


def guardar_datos_aplicabilidad(
    expediente_id: str,
    datos: dict[str, str],
) -> None:
    """Persiste únicamente respuestas normalizadas del motor determinístico."""
    from modulos.aplicabilidad import NO, PENDIENTE, SI
    from psycopg.types.json import Jsonb

    permitidos = {SI, NO, PENDIENTE}
    normalizados = {
        str(clave): str(valor).upper()
        if str(valor).upper() in permitidos
        else PENDIENTE
        for clave, valor in datos.items()
    }
    with _conexion() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE expedientes
                SET datos_aplicabilidad = %s,
                    aplicabilidad_actualizada_en = now(),
                    actualizado_en = now()
                WHERE id = %s
                """,
                (Jsonb(normalizados), expediente_id),
            )
            if cur.rowcount != 1:
                raise RuntimeError("No se encontró el expediente activo")
        conn.commit()


def registrar_inicio(
    expediente_id: str,
    categoria: str,
    nombre_archivo: str,
    huella: str,
    clave_procesamiento: str,
    modelo: str,
    version_prompt: str,
    catalogo_documento_id: str | None = None,
    clave_catalogo: str | None = None,
    tipo_documental: str | None = None,
) -> None:
    with _conexion() as conn:
        with conn.cursor() as cur:
            parametros_base = (
                expediente_id, categoria, nombre_archivo, huella,
                clave_procesamiento, modelo, version_prompt,
            )
            cur.execute("SAVEPOINT guardar_documento_catalogado")
            try:
                cur.execute(
                    """
                    INSERT INTO documentos (
                        expediente_id, categoria, nombre_archivo, huella_sha256,
                        clave_procesamiento, estado, modelo, version_prompt, intentos,
                        catalogo_documento_id, clave_catalogo, tipo_documental
                    ) VALUES (%s, %s, %s, %s, %s, 'PROCESANDO', %s, %s, 1, %s, %s, %s)
                    ON CONFLICT (expediente_id, clave_procesamiento)
                    DO UPDATE SET estado = 'PROCESANDO', error = NULL,
                                  intentos = documentos.intentos + 1,
                                  catalogo_documento_id = EXCLUDED.catalogo_documento_id,
                                  clave_catalogo = EXCLUDED.clave_catalogo,
                                  tipo_documental = EXCLUDED.tipo_documental,
                                  actualizado_en = now()
                    """,
                    parametros_base + (
                        catalogo_documento_id, clave_catalogo, tipo_documental,
                    ),
                )
            except Exception as exc:
                if exc.__class__.__name__ != "UndefinedColumn":
                    raise
                cur.execute("ROLLBACK TO SAVEPOINT guardar_documento_catalogado")
                cur.execute(
                    """
                    INSERT INTO documentos (
                        expediente_id, categoria, nombre_archivo, huella_sha256,
                        clave_procesamiento, estado, modelo, version_prompt, intentos
                    ) VALUES (%s, %s, %s, %s, %s, 'PROCESANDO', %s, %s, 1)
                    ON CONFLICT (expediente_id, clave_procesamiento)
                    DO UPDATE SET estado = 'PROCESANDO', error = NULL,
                                  intentos = documentos.intentos + 1,
                                  actualizado_en = now()
                    """,
                    parametros_base,
                )
            cur.execute("SAVEPOINT vincular_archivo_requisito")
            try:
                cur.execute(
                    """
                    UPDATE documentos d
                    SET archivo_expediente_id = a.id
                    FROM archivos_expediente a
                    WHERE d.expediente_id = %s
                      AND d.clave_procesamiento = %s
                      AND a.expediente_id = d.expediente_id
                      AND a.huella_sha256 = d.huella_sha256
                      AND a.nombre_archivo = d.nombre_archivo
                    """,
                    (expediente_id, clave_procesamiento),
                )
                cur.execute(
                    """
                    UPDATE expediente_requisitos er
                    SET resultado_ia = 'PROCESANDO', actualizado_en = now()
                    FROM documentos d
                    WHERE d.expediente_id = %s
                      AND d.clave_procesamiento = %s
                      AND er.expediente_id = d.expediente_id
                      AND er.clave_catalogo = d.clave_catalogo
                    """,
                    (expediente_id, clave_procesamiento),
                )
            except Exception as exc:
                if exc.__class__.__name__ not in {"UndefinedTable", "UndefinedColumn"}:
                    raise
                cur.execute("ROLLBACK TO SAVEPOINT vincular_archivo_requisito")
        conn.commit()


def registrar_resultado(
    expediente_id: str,
    clave_procesamiento: str,
    datos: list[dict[str, Any]],
    metadatos: dict[str, Any],
) -> None:
    from psycopg.types.json import Jsonb

    with _conexion() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE documentos
                SET estado = 'OK', error = NULL, actualizado_en = now()
                WHERE expediente_id = %s AND clave_procesamiento = %s
                RETURNING id
                """,
                (expediente_id, clave_procesamiento),
            )
            fila = cur.fetchone()
            if not fila:
                raise RuntimeError("No se encontró el documento iniciado")
            documento_id = fila[0]
            cur.execute(
                """
                INSERT INTO resultados_extraccion (documento_id, datos, metadatos)
                VALUES (%s, %s, %s)
                ON CONFLICT (documento_id)
                DO UPDATE SET datos = EXCLUDED.datos,
                              metadatos = EXCLUDED.metadatos,
                              actualizado_en = now()
                """,
                (documento_id, Jsonb(datos), Jsonb(metadatos)),
            )
            resultado_ia = _resultado_ia_global(datos)
            cur.execute(
                """
                UPDATE expediente_requisitos er
                SET resultado_ia = %s,
                    ultimo_documento_id = %s,
                    actualizado_en = now()
                FROM documentos d
                WHERE d.id = %s
                  AND er.expediente_id = d.expediente_id
                  AND er.clave_catalogo = d.clave_catalogo
                """,
                (resultado_ia, documento_id, documento_id),
            )
            cur.execute(
                """
                UPDATE archivos_expediente a
                SET estado = 'ANALIZADO', actualizado_en = now()
                FROM documentos d
                WHERE d.id = %s AND a.id = d.archivo_expediente_id
                """,
                (documento_id,),
            )
        conn.commit()


def registrar_error(
    expediente_id: str,
    clave_procesamiento: str,
    mensaje: str,
) -> None:
    with _conexion() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE documentos
                SET estado = 'ERROR', error = %s, actualizado_en = now()
                WHERE expediente_id = %s AND clave_procesamiento = %s
                """,
                (mensaje[:4000], expediente_id, clave_procesamiento),
            )
            cur.execute("SAVEPOINT marcar_error_requisito")
            try:
                cur.execute(
                    """
                    UPDATE expediente_requisitos er
                    SET resultado_ia = 'ERROR', actualizado_en = now()
                    FROM documentos d
                    WHERE d.expediente_id = %s
                      AND d.clave_procesamiento = %s
                      AND er.expediente_id = d.expediente_id
                      AND er.clave_catalogo = d.clave_catalogo
                    """,
                    (expediente_id, clave_procesamiento),
                )
                cur.execute(
                    """
                    UPDATE archivos_expediente a
                    SET estado = 'ERROR', actualizado_en = now()
                    FROM documentos d
                    WHERE d.expediente_id = %s
                      AND d.clave_procesamiento = %s
                      AND a.id = d.archivo_expediente_id
                    """,
                    (expediente_id, clave_procesamiento),
                )
            except Exception as exc:
                if exc.__class__.__name__ not in {"UndefinedTable", "UndefinedColumn"}:
                    raise
                cur.execute("ROLLBACK TO SAVEPOINT marcar_error_requisito")
        conn.commit()


def _resultado_ia_global(datos: list[dict[str, Any]]) -> str:
    from modulos.motor_catalogo import resultado_global

    analisis = datos[0] if datos and isinstance(datos[0], dict) else {}
    return resultado_global(analisis)


def serializar_diagnostico() -> str:
    return json.dumps(
        {
            "neon_configurado": disponible(),
            "usuario": _secreto("APP_USER_ID", "usuario_local"),
        },
        ensure_ascii=False,
    )
