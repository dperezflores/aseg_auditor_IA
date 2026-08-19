from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from modulos import administracion_catalogo as admin


def renderizar(usuario: str, puede_publicar: bool) -> None:
    st.markdown("### Administración del catálogo maestro")
    st.caption(
        "Los cambios se realizan en una versión borrador. Los expedientes existentes "
        "conservan su catálogo y solo los nuevos expedientes reciben la versión publicada."
    )

    versiones = admin.listar_versiones()
    if not versiones:
        st.warning("No existen versiones del catálogo.")
        return

    with st.expander("Crear nueva versión de trabajo"):
        nombre = st.text_input("Nombre de la versión", placeholder="Catálogo 2026.2")
        notas = st.text_area("Objetivo o notas del cambio")
        if st.button("Crear borrador desde la versión activa", type="primary"):
            if not nombre.strip():
                st.error("Indique un nombre para la versión.")
            else:
                admin.crear_borrador(nombre.strip(), usuario, notas.strip())
                st.success("Borrador creado correctamente.")
                st.rerun()

    etiquetas = {
        str(item["id"]): f'{item["nombre"]} · {item["estado"]}' for item in versiones
    }
    version_id = st.selectbox(
        "Versión",
        options=list(etiquetas),
        format_func=etiquetas.get,
    )
    version = next(item for item in versiones if str(item["id"]) == version_id)
    documentos = admin.listar_documentos(version_id)

    if version["estado"] != "BORRADOR":
        st.info("Esta versión es de solo lectura. Cree un borrador para modificarla.")

    procedimientos = sorted({item["procedimiento"] for item in documentos})
    filtro = st.multiselect(
        "Procedimientos visibles",
        procedimientos,
        default=procedimientos,
    )
    visibles = [item for item in documentos if item["procedimiento"] in filtro]
    columnas_tabla = [
        "clave_catalogo", "orden_en_procedimiento", "activo", "procedimiento",
        "etapa", "nombre_documento", "obligatoriedad",
        "condicion_aplicabilidad", "estado_revision",
    ]
    original = pd.DataFrame(visibles)
    editada = st.data_editor(
        original[columnas_tabla],
        hide_index=True,
        use_container_width=True,
        disabled=["clave_catalogo", "procedimiento"],
        column_config={
            "obligatoriedad": st.column_config.SelectboxColumn(
                options=["Obligatorio", "Condicional", "Opcional", "No aplica", "Por definir"]
            ),
            "estado_revision": st.column_config.SelectboxColumn(
                options=["Pendiente", "Revisado", "Aprobado"]
            ),
        },
        key=f"catalogo_editor_{version_id}",
    )
    motivo = st.text_input(
        "Motivo del cambio",
        disabled=version["estado"] != "BORRADOR",
    )
    if st.button(
        "Guardar cambios de la tabla",
        disabled=version["estado"] != "BORRADOR",
    ):
        if not motivo.strip():
            st.error("El motivo es obligatorio para conservar la trazabilidad.")
        else:
            por_clave = {item["clave_catalogo"]: item for item in visibles}
            guardados = 0
            for fila in editada.to_dict("records"):
                anterior = por_clave[fila["clave_catalogo"]]
                cambios = {
                    clave: valor
                    for clave, valor in fila.items()
                    if clave not in {"clave_catalogo", "procedimiento"}
                    and valor != anterior.get(clave)
                }
                if cambios:
                    admin.actualizar_documento(
                        version_id, str(anterior["id"]), cambios, usuario, motivo.strip()
                    )
                    guardados += 1
            st.success(f"Cambios guardados en {guardados} documento(s).")
            st.rerun()

    st.markdown("#### Reglas de aplicabilidad")
    opciones_documento = {
        str(item["id"]): f'{item["clave_catalogo"]} · {item["nombre_documento"]}'
        for item in visibles
    }
    if opciones_documento:
        documento_id = st.selectbox(
            "Documento a configurar",
            list(opciones_documento),
            format_func=opciones_documento.get,
        )
        reglas = admin.cargar_reglas(documento_id)
        for regla in reglas:
            regla["valor_esperado"] = json.dumps(
                regla.get("valor_esperado"), ensure_ascii=False
            )
        base = pd.DataFrame(reglas or [{
            "orden": 1,
            "tipo_regla": "SIEMPRE",
            "fuente": "VALOR_FIJO",
            "fuente_tipo_documental": "",
            "fuente_campo": "",
            "operador": "EXISTE",
            "valor_esperado": "true",
            "resultado_verdadero": "APLICA",
            "resultado_falso": "NO_APLICA",
            "resultado_sin_dato": "PENDIENTE",
            "justificacion": "",
            "estado_revision": "Pendiente",
        }])
        reglas_editadas = st.data_editor(
            base,
            num_rows="dynamic",
            hide_index=True,
            use_container_width=True,
            disabled=version["estado"] != "BORRADOR",
            key=f"reglas_editor_{version_id}_{documento_id}",
        )
        motivo_reglas = st.text_input(
            "Motivo de la configuración de reglas",
            disabled=version["estado"] != "BORRADOR",
        )
        if st.button(
            "Guardar reglas",
            disabled=version["estado"] != "BORRADOR",
        ):
            if not motivo_reglas.strip():
                st.error("El motivo es obligatorio.")
            else:
                nuevas = reglas_editadas.to_dict("records")
                try:
                    for regla in nuevas:
                        regla["valor_esperado"] = json.loads(
                            str(regla.get("valor_esperado") or "null")
                        )
                    admin.guardar_reglas(
                        version_id, documento_id, nuevas, usuario, motivo_reglas.strip()
                    )
                    st.success("Reglas guardadas.")
                    st.rerun()
                except json.JSONDecodeError:
                    st.error("Valor esperado debe escribirse como JSON válido, por ejemplo true, 30 o \"Sí\".")

    if version["estado"] == "BORRADOR":
        st.markdown("#### Publicación")
        errores = admin.validar_borrador(version_id)
        for error in errores:
            st.warning(error)
        motivo_publicacion = st.text_input("Motivo de publicación")
        if st.button(
            "Publicar esta versión",
            type="primary",
            disabled=bool(errores) or not puede_publicar,
        ):
            admin.publicar_version(
                version_id, usuario, motivo_publicacion.strip() or "Publicación aprobada"
            )
            st.success("Versión publicada. Los nuevos expedientes usarán esta configuración.")
            st.rerun()
        if not puede_publicar:
            st.caption("Su rol permite editar, pero no publicar versiones.")
