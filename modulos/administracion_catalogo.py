from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from psycopg.types.json import Jsonb

from modulos.persistencia import _conexion


CAMPOS_EDITABLES_DOCUMENTO = {
    "orden_en_procedimiento",
    "activo",
    "version_catalogo",
    "etapa",
    "tipo_documental",
    "codigo_base",
    "nombre_documento",
    "obligatoriedad",
    "condicion_aplicabilidad",
    "admite_multiples",
    "patron_consecutivo",
    "riesgo_predeterminado",
    "regla_formatos",
    "criterios_identificacion_ia",
    "datos_clave_a_validar",
    "fundamento_normativo",
    "vigencia_desde",
    "vigencia_hasta",
    "observaciones",
    "estado_revision",
}


def listar_versiones() -> list[dict[str, Any]]:
    with _conexion() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, COALESCE(nombre_version, archivo_nombre), estado,
                       creado_por, publicado_por, creado_en, activado_en, notas
                FROM catalogo_importaciones
                ORDER BY creado_en DESC
                """
            )
            claves = (
                "id", "nombre", "estado", "creado_por", "publicado_por",
                "creado_en", "activado_en", "notas",
            )
            return [dict(zip(claves, fila)) for fila in cur.fetchall()]


def crear_borrador(nombre: str, usuario: str, notas: str = "") -> str:
    marca = datetime.now(timezone.utc).isoformat()
    huella = hashlib.sha256(f"{nombre}:{usuario}:{marca}".encode()).hexdigest()
    with _conexion() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM catalogo_importaciones WHERE estado = 'ACTIVO'")
            activa = cur.fetchone()
            if not activa:
                raise RuntimeError("No existe una versión activa para crear el borrador")
            origen = activa[0]
            cur.execute(
                """
                INSERT INTO catalogo_importaciones (
                    archivo_nombre, archivo_sha256, estado, resumen, advertencias,
                    nombre_version, creado_por, notas
                )
                SELECT archivo_nombre, %s, 'BORRADOR', resumen, advertencias,
                       %s, %s, %s
                FROM catalogo_importaciones WHERE id = %s
                RETURNING id
                """,
                (huella, nombre, usuario, notas, origen),
            )
            borrador = cur.fetchone()[0]
            cur.execute(
                """
                INSERT INTO tipos_documentales (importacion_id, tipo_documental, etapa)
                SELECT %s, tipo_documental, etapa
                FROM tipos_documentales WHERE importacion_id = %s
                """,
                (borrador, origen),
            )
            cur.execute(
                """
                INSERT INTO catalogo_documentos (
                    importacion_id, clave_catalogo, orden_en_procedimiento, activo,
                    version_catalogo, procedimiento, etapa, tipo_documental,
                    codigo_base, nombre_documento, obligatoriedad,
                    condicion_aplicabilidad, admite_multiples, patron_consecutivo,
                    riesgo_predeterminado, regla_formatos, criterios_identificacion_ia,
                    datos_clave_a_validar, fundamento_normativo, vigencia_desde,
                    vigencia_hasta, observaciones, estado_revision, fuente_origen
                )
                SELECT %s, clave_catalogo, orden_en_procedimiento, activo,
                       version_catalogo, procedimiento, etapa, tipo_documental,
                       codigo_base, nombre_documento, obligatoriedad,
                       condicion_aplicabilidad, admite_multiples, patron_consecutivo,
                       riesgo_predeterminado, regla_formatos, criterios_identificacion_ia,
                       datos_clave_a_validar, fundamento_normativo, vigencia_desde,
                       vigencia_hasta, observaciones, estado_revision, fuente_origen
                FROM catalogo_documentos WHERE importacion_id = %s
                """,
                (borrador, origen),
            )
            cur.execute(
                """
                INSERT INTO formatos_documento (
                    importacion_id, formato_id, catalogo_documento_id, extension,
                    mime_type, nombre_por_formato, modalidad_formato, activo,
                    estado_revision, observaciones, fuente_origen
                )
                SELECT %s, f.formato_id, nuevo.id, f.extension, f.mime_type,
                       f.nombre_por_formato, f.modalidad_formato, f.activo,
                       f.estado_revision, f.observaciones, f.fuente_origen
                FROM formatos_documento f
                JOIN catalogo_documentos anterior ON anterior.id = f.catalogo_documento_id
                JOIN catalogo_documentos nuevo
                  ON nuevo.importacion_id = %s
                 AND nuevo.clave_catalogo = anterior.clave_catalogo
                WHERE f.importacion_id = %s
                """,
                (borrador, borrador, origen),
            )
            for tabla, columnas in (
                (
                    "procedimientos_validacion",
                    "procedimiento_id, tipo_documental, orden, procedimiento_validacion, resultado_esperado, evidencia_requerida, riesgo_codigo, activo, estado_revision, observaciones",
                ),
                (
                    "campos_extraccion",
                    "campo_id, tipo_documental, orden_salida, nombre_tecnico, etiqueta_salida, tipo_dato, obligatorio_ia, instruccion_extraccion, mostrar_en_detalle, celda_pt, estado_revision, observaciones",
                ),
            ):
                cur.execute(
                    f"INSERT INTO {tabla} (importacion_id, {columnas}) "
                    f"SELECT %s, {columnas} FROM {tabla} WHERE importacion_id = %s",
                    (borrador, origen),
                )
            cur.execute(
                """
                INSERT INTO reglas_aplicabilidad (
                    importacion_id, catalogo_documento_id, orden, tipo_regla,
                    fuente, fuente_tipo_documental, fuente_campo, operador,
                    valor_esperado, resultado_verdadero, resultado_falso,
                    resultado_sin_dato, justificacion, activa, estado_revision,
                    creado_por, actualizado_por
                )
                SELECT %s, nuevo.id, r.orden, r.tipo_regla, r.fuente,
                       r.fuente_tipo_documental, r.fuente_campo, r.operador,
                       r.valor_esperado, r.resultado_verdadero, r.resultado_falso,
                       r.resultado_sin_dato, r.justificacion, r.activa,
                       r.estado_revision, %s, %s
                FROM reglas_aplicabilidad r
                JOIN catalogo_documentos anterior ON anterior.id = r.catalogo_documento_id
                JOIN catalogo_documentos nuevo
                  ON nuevo.importacion_id = %s
                 AND nuevo.clave_catalogo = anterior.clave_catalogo
                WHERE r.importacion_id = %s
                """,
                (borrador, usuario, usuario, borrador, origen),
            )
            _auditar(cur, borrador, usuario, "catalogo_importaciones", borrador, "CREAR_BORRADOR", None, {"nombre": nombre}, notas)
        conn.commit()
    return str(borrador)


def listar_documentos(importacion_id: str) -> list[dict[str, Any]]:
    with _conexion() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, clave_catalogo, orden_en_procedimiento, activo,
                       procedimiento, etapa, tipo_documental, codigo_base,
                       nombre_documento, obligatoriedad, condicion_aplicabilidad,
                       admite_multiples, criterios_identificacion_ia,
                       datos_clave_a_validar, fundamento_normativo,
                       estado_revision, observaciones
                FROM catalogo_documentos
                WHERE importacion_id = %s
                ORDER BY procedimiento, orden_en_procedimiento, clave_catalogo
                """,
                (importacion_id,),
            )
            claves = (
                "id", "clave_catalogo", "orden_en_procedimiento", "activo",
                "procedimiento", "etapa", "tipo_documental", "codigo_base",
                "nombre_documento", "obligatoriedad", "condicion_aplicabilidad",
                "admite_multiples", "criterios_identificacion_ia",
                "datos_clave_a_validar", "fundamento_normativo",
                "estado_revision", "observaciones",
            )
            return [dict(zip(claves, fila)) for fila in cur.fetchall()]


def cargar_reglas(documento_id: str) -> list[dict[str, Any]]:
    with _conexion() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT orden, tipo_regla, fuente, fuente_tipo_documental,
                       fuente_campo, operador, valor_esperado,
                       resultado_verdadero, resultado_falso, resultado_sin_dato,
                       justificacion, estado_revision
                FROM reglas_aplicabilidad
                WHERE catalogo_documento_id = %s AND activa
                ORDER BY orden
                """,
                (documento_id,),
            )
            claves = (
                "orden", "tipo_regla", "fuente", "fuente_tipo_documental",
                "fuente_campo", "operador", "valor_esperado",
                "resultado_verdadero", "resultado_falso", "resultado_sin_dato",
                "justificacion", "estado_revision",
            )
            return [dict(zip(claves, fila)) for fila in cur.fetchall()]


def actualizar_documento(
    importacion_id: str,
    documento_id: str,
    cambios: dict[str, Any],
    usuario: str,
    motivo: str,
) -> None:
    cambios = {k: v for k, v in cambios.items() if k in CAMPOS_EDITABLES_DOCUMENTO}
    if not cambios:
        return
    with _conexion() as conn:
        with conn.cursor() as cur:
            _exigir_borrador(cur, importacion_id)
            cur.execute(
                "SELECT to_jsonb(d) FROM catalogo_documentos d WHERE id = %s AND importacion_id = %s",
                (documento_id, importacion_id),
            )
            fila = cur.fetchone()
            if not fila:
                raise RuntimeError("No se encontró el documento del catálogo")
            anterior = fila[0]
            asignaciones = ", ".join(f"{campo} = %s" for campo in cambios)
            cur.execute(
                f"UPDATE catalogo_documentos SET {asignaciones} WHERE id = %s AND importacion_id = %s",
                (*cambios.values(), documento_id, importacion_id),
            )
            _auditar(cur, importacion_id, usuario, "catalogo_documentos", documento_id, "ACTUALIZAR", anterior, cambios, motivo)
        conn.commit()


def guardar_reglas(
    importacion_id: str,
    documento_id: str,
    reglas: list[dict[str, Any]],
    usuario: str,
    motivo: str,
) -> None:
    with _conexion() as conn:
        with conn.cursor() as cur:
            _exigir_borrador(cur, importacion_id)
            cur.execute(
                "SELECT COALESCE(jsonb_agg(to_jsonb(r) ORDER BY orden), '[]') FROM reglas_aplicabilidad r WHERE catalogo_documento_id = %s",
                (documento_id,),
            )
            anterior = cur.fetchone()[0]
            cur.execute("DELETE FROM reglas_aplicabilidad WHERE catalogo_documento_id = %s", (documento_id,))
            for orden, regla in enumerate(reglas, start=1):
                cur.execute(
                    """
                    INSERT INTO reglas_aplicabilidad (
                        importacion_id, catalogo_documento_id, orden, tipo_regla,
                        fuente, fuente_tipo_documental, fuente_campo, operador,
                        valor_esperado, resultado_verdadero, resultado_falso,
                        resultado_sin_dato, justificacion, activa,
                        estado_revision, creado_por, actualizado_por
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, true, %s, %s, %s)
                    """,
                    (
                        importacion_id, documento_id, orden, regla["tipo_regla"],
                        regla["fuente"], regla.get("fuente_tipo_documental"),
                        regla.get("fuente_campo"), regla.get("operador", "EXISTE"),
                        Jsonb(regla.get("valor_esperado")),
                        regla.get("resultado_verdadero", "APLICA"),
                        regla.get("resultado_falso", "NO_APLICA"),
                        regla.get("resultado_sin_dato", "PENDIENTE"),
                        regla.get("justificacion", ""),
                        regla.get("estado_revision", "Pendiente"), usuario, usuario,
                    ),
                )
            _auditar(cur, importacion_id, usuario, "reglas_aplicabilidad", documento_id, "REEMPLAZAR", anterior, reglas, motivo)
        conn.commit()


def validar_borrador(importacion_id: str) -> list[str]:
    errores: list[str] = []
    with _conexion() as conn:
        with conn.cursor() as cur:
            _exigir_borrador(cur, importacion_id)
            cur.execute("SELECT count(*) FROM catalogo_documentos WHERE importacion_id = %s AND activo", (importacion_id,))
            if cur.fetchone()[0] == 0:
                errores.append("La versión no contiene documentos activos.")
            cur.execute(
                """
                SELECT count(*) FROM catalogo_documentos d
                WHERE d.importacion_id = %s AND d.activo
                  AND d.obligatoriedad = 'Condicional'
                  AND NOT EXISTS (
                      SELECT 1 FROM reglas_aplicabilidad r
                      WHERE r.catalogo_documento_id = d.id
                        AND r.activa AND r.estado_revision = 'Aprobado'
                  )
                """,
                (importacion_id,),
            )
            pendientes = cur.fetchone()[0]
            if pendientes:
                errores.append(f"Hay {pendientes} documento(s) condicional(es) sin regla aprobada.")
    return errores


def publicar_version(importacion_id: str, usuario: str, motivo: str) -> None:
    errores = validar_borrador(importacion_id)
    if errores:
        raise ValueError(" ".join(errores))
    with _conexion() as conn:
        with conn.cursor() as cur:
            _exigir_borrador(cur, importacion_id)
            cur.execute("UPDATE catalogo_importaciones SET estado = 'ARCHIVADO' WHERE estado = 'ACTIVO'")
            cur.execute(
                """
                UPDATE catalogo_importaciones
                SET estado = 'ACTIVO', publicado_por = %s, activado_en = now()
                WHERE id = %s
                """,
                (usuario, importacion_id),
            )
            _auditar(cur, importacion_id, usuario, "catalogo_importaciones", importacion_id, "PUBLICAR", {"estado": "BORRADOR"}, {"estado": "ACTIVO"}, motivo)
        conn.commit()


def _exigir_borrador(cur, importacion_id: str) -> None:
    cur.execute("SELECT estado FROM catalogo_importaciones WHERE id = %s", (importacion_id,))
    fila = cur.fetchone()
    if not fila or fila[0] != "BORRADOR":
        raise PermissionError("Solo se pueden editar versiones en estado BORRADOR")


def _auditar(cur, importacion_id, usuario, entidad, entidad_id, accion, anterior, nuevo, motivo):
    cur.execute(
        """
        INSERT INTO auditoria_catalogo (
            importacion_id, usuario_externo, entidad, entidad_id, accion,
            valores_anteriores, valores_nuevos, motivo
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            importacion_id, usuario, entidad, str(entidad_id), accion,
            Jsonb(anterior) if anterior is not None else None,
            Jsonb(nuevo) if nuevo is not None else None,
            motivo,
        ),
    )
