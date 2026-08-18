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
                        ) AS procedimientos
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
    return str(expediente_id), creado


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
        conn.commit()


def serializar_diagnostico() -> str:
    return json.dumps(
        {
            "neon_configurado": disponible(),
            "usuario": _secreto("APP_USER_ID", "usuario_local"),
        },
        ensure_ascii=False,
    )
