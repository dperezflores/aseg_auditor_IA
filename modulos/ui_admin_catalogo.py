from __future__ import annotations

import pandas as pd
import streamlit as st

from modulos import administracion_catalogo as admin


REVISIONES = ["Pendiente", "Revisado", "Aprobado"]
OBLIGATORIEDADES = ["Obligatorio", "Condicional", "Opcional", "No aplica", "Por definir"]


@st.cache_data(ttl=60, show_spinner=False)
def _versiones():
    return admin.listar_versiones()


@st.cache_data(ttl=60, show_spinner=False)
def _documentos(version_id):
    return admin.listar_documentos(version_id)


@st.cache_data(ttl=60, show_spinner=False)
def _formatos(documento_id):
    return admin.listar_formatos(documento_id)


@st.cache_data(ttl=60, show_spinner=False)
def _campos(version_id, tipo_documental):
    return admin.listar_campos(version_id, tipo_documental)


@st.cache_data(ttl=60, show_spinner=False)
def _reglas(documento_id):
    return admin.cargar_reglas(documento_id)


@st.cache_data(ttl=60, show_spinner=False)
def _procedimientos(version_id, tipo_documental):
    return admin.listar_procedimientos(version_id, tipo_documental)


@st.cache_data(ttl=30, show_spinner=False)
def _errores_publicacion(version_id):
    return admin.validar_borrador(version_id)


def _limpiar_cache():
    for funcion in (_versiones, _documentos, _formatos, _campos, _reglas, _procedimientos, _errores_publicacion):
        funcion.clear()


def _indice(opciones, valor):
    return opciones.index(valor) if valor in opciones else 0


def renderizar(usuario: str, puede_publicar: bool) -> None:
    st.markdown("### Administración del catálogo maestro")
    st.caption("Los cambios se guardan en un borrador y solo afectan expedientes nuevos después de publicarlo.")
    versiones = _versiones()
    if not versiones:
        st.warning("No existen versiones del catálogo.")
        return

    with st.expander("➕ Crear nueva versión de trabajo"):
        with st.form("crear_borrador"):
            nombre = st.text_input("Nombre de la versión", placeholder="Catálogo 2026.2")
            notas = st.text_area("Objetivo o notas del cambio")
            crear = st.form_submit_button("Crear borrador desde la versión activa", type="primary")
        if crear:
            if not nombre.strip():
                st.error("Indique un nombre para la versión.")
            else:
                admin.crear_borrador(nombre.strip(), usuario, notas.strip())
                _limpiar_cache()
                st.success("Borrador creado correctamente.")
                st.rerun()

    etiquetas = {str(v["id"]): f'{v["nombre"]} · {v["estado"]}' for v in versiones}
    version_id = st.selectbox("Versión", list(etiquetas), format_func=etiquetas.get)
    version = next(v for v in versiones if str(v["id"]) == version_id)
    editable = version["estado"] == "BORRADOR"
    documentos = _documentos(version_id)
    if not editable:
        st.info("Esta versión es de solo lectura. Cree un borrador para modificarla.")

    procedimientos = sorted({d["procedimiento"] for d in documentos})
    filtro = st.multiselect("Procedimientos visibles", procedimientos, default=procedimientos)
    visibles = [d for d in documentos if d["procedimiento"] in filtro]
    st.dataframe(pd.DataFrame([{
        "Clave": d["clave_catalogo"], "Orden": d["orden_en_procedimiento"],
        "Activo": d["activo"], "Procedimiento": d["procedimiento"],
        "Etapa": d["etapa"], "Documento": d["nombre_documento"],
        "Obligatoriedad": d["obligatoriedad"], "Revisión": d["estado_revision"],
    } for d in visibles]), hide_index=True, use_container_width=True)
    if not visibles:
        return

    opciones_documento = {str(d["id"]): f'{d["clave_catalogo"]} · {d["nombre_documento"]}' for d in visibles}
    documento_id = st.selectbox("Documento a configurar", list(opciones_documento), format_func=opciones_documento.get)
    documento = next(d for d in visibles if str(d["id"]) == documento_id)
    tab_doc, tab_formato, tab_campos, tab_proc, tab_reglas, tab_publicar = st.tabs(
        ["Documento", "Archivos permitidos", "Campos de extracción", "Procedimientos de revisión", "Aplicabilidad", "Publicación"]
    )

    with tab_doc:
        st.caption("Edite un documento a la vez. Nada se guarda hasta pulsar el botón.")
        with st.form(f"documento_{documento_id}"):
            c1, c2, c3 = st.columns(3)
            orden = c1.number_input("Orden", min_value=1, value=int(documento["orden_en_procedimiento"]))
            etapas = ["PPP", "ADJ", "CNT", "EJE", "ETR"]
            etapa = c2.selectbox("Etapa", etapas, index=_indice(etapas, documento["etapa"]))
            obligatoriedad = c3.selectbox("Obligatoriedad", OBLIGATORIEDADES, index=_indice(OBLIGATORIEDADES, documento["obligatoriedad"]))
            nombre = st.text_input("Nombre del documento", value=documento["nombre_documento"])
            condicion = st.text_area("Condición de aplicabilidad", value=documento["condicion_aplicabilidad"] or "")
            criterios = st.text_area("Criterios de identificación para IA", value=documento["criterios_identificacion_ia"] or "")
            fundamento = st.text_area("Fundamento normativo", value=documento["fundamento_normativo"] or "")
            c1, c2, c3 = st.columns(3)
            activo = c1.checkbox("Documento activo", value=bool(documento["activo"]))
            multiples = c2.checkbox("Permitir varios archivos", value=bool(documento["admite_multiples"]), help="Actívelo cuando un concepto pueda integrarse con más de un archivo.")
            revision = c3.selectbox("Estado de revisión", REVISIONES, index=_indice(REVISIONES, documento["estado_revision"]))
            motivo = st.text_input("Motivo del cambio", help="Quedará registrado en la bitácora.")
            guardar = st.form_submit_button("Guardar documento", type="primary", disabled=not editable)
        if guardar:
            if not motivo.strip():
                st.error("El motivo del cambio es obligatorio.")
            else:
                admin.actualizar_documento(version_id, documento_id, {
                    "orden_en_procedimiento": int(orden), "etapa": etapa, "obligatoriedad": obligatoriedad,
                    "nombre_documento": nombre.strip(), "condicion_aplicabilidad": condicion.strip(),
                    "criterios_identificacion_ia": criterios.strip(), "fundamento_normativo": fundamento.strip(),
                    "activo": activo, "admite_multiples": multiples, "estado_revision": revision,
                }, usuario, motivo.strip())
                _limpiar_cache()
                st.success("Documento actualizado.")
                st.rerun()

    with tab_formato:
        st.caption("Defina las extensiones permitidas y si puede recibir uno o varios archivos.")
        formatos = _formatos(documento_id)
        st.dataframe(pd.DataFrame(formatos), hide_index=True, use_container_width=True)
        with st.form(f"formato_{documento_id}"):
            c1, c2, c3 = st.columns(3)
            extension = c1.text_input("Extensión", placeholder="pdf")
            mime = c2.text_input("Tipo MIME", value="application/pdf")
            modalidad = c3.selectbox("Modalidad", ["Requerido", "Alternativo", "Por definir"])
            c1, c2 = st.columns(2)
            formato_activo = c1.checkbox("Formato activo", value=True)
            revision_formato = c2.selectbox("Estado de revisión", REVISIONES, key=f"rev_fmt_{documento_id}")
            observaciones = st.text_input("Observaciones")
            motivo_formato = st.text_input("Motivo del cambio", key=f"motivo_fmt_{documento_id}")
            guardar_formato = st.form_submit_button("Guardar formato", disabled=not editable)
        if guardar_formato:
            if not motivo_formato.strip():
                st.error("El motivo del cambio es obligatorio.")
            else:
                try:
                    admin.guardar_formato(version_id, documento_id, extension, mime, modalidad,
                                          formato_activo, revision_formato, observaciones,
                                          usuario, motivo_formato.strip())
                    _limpiar_cache()
                    st.success("Formato guardado.")
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))

    with tab_campos:
        st.caption("Estos son los datos que la IA buscará y mostrará en el orden indicado.")
        campos = _campos(version_id, documento["tipo_documental"])
        st.dataframe(pd.DataFrame(campos), hide_index=True, use_container_width=True)
        existentes = {c["nombre_tecnico"]: c for c in campos}
        elegir = st.selectbox("Campo", ["➕ Crear campo"] + list(existentes), key=f"elegir_campo_{documento_id}")
        base = existentes.get(elegir, {})
        with st.form(f"campo_{documento_id}_{elegir}"):
            c1, c2 = st.columns(2)
            tecnico = c1.text_input("Nombre técnico", value=base.get("nombre_tecnico", ""), placeholder="incluye_especificaciones_construccion")
            etiqueta = c2.text_input("Etiqueta para el usuario", value=base.get("etiqueta_salida", ""))
            c1, c2 = st.columns(2)
            orden_campo = c1.number_input("Orden de salida", min_value=1, value=int(base.get("orden_salida", len(campos) + 1)))
            tipos = ["Texto", "Fecha", "Decimal", "Entero", "Booleano", "Lista", "JSON"]
            tipo = c2.selectbox("Tipo de dato", tipos, index=_indice(tipos, base.get("tipo_dato", "Texto")))
            instruccion = st.text_area("Instrucción para la IA", value=base.get("instruccion_extraccion", ""))
            c1, c2, c3 = st.columns(3)
            obligatorio_ia = c1.checkbox("La IA debe responderlo", value=bool(base.get("obligatorio_ia", False)))
            mostrar = c2.checkbox("Mostrar en el análisis", value=bool(base.get("mostrar_en_detalle", True)))
            revision_campo = c3.selectbox("Estado de revisión", REVISIONES, index=_indice(REVISIONES, base.get("estado_revision", "Pendiente")), key=f"rev_campo_{documento_id}")
            motivo_campo = st.text_input("Motivo del cambio", key=f"motivo_campo_{documento_id}")
            guardar_campo = st.form_submit_button("Guardar campo", disabled=not editable)
        if guardar_campo:
            if not motivo_campo.strip():
                st.error("El motivo del cambio es obligatorio.")
            else:
                try:
                    admin.guardar_campo(version_id, documento["tipo_documental"], {
                        "orden_salida": int(orden_campo), "nombre_tecnico": tecnico,
                        "etiqueta_salida": etiqueta, "tipo_dato": tipo, "obligatorio_ia": obligatorio_ia,
                        "instruccion_extraccion": instruccion, "mostrar_en_detalle": mostrar,
                        "estado_revision": revision_campo, "observaciones": "",
                    }, usuario, motivo_campo.strip())
                    _limpiar_cache()
                    st.success("Campo de extracción guardado.")
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))

    with tab_proc:
        st.caption("Defina cada comprobación que la IA debe ejecutar y explicar en el análisis.")
        procedimientos_revision = _procedimientos(version_id, documento["tipo_documental"])
        st.dataframe(pd.DataFrame(procedimientos_revision), hide_index=True, use_container_width=True)
        existentes_proc = {p["procedimiento_id"]: p for p in procedimientos_revision}
        elegir_proc = st.selectbox("Procedimiento", ["➕ Crear procedimiento"] + list(existentes_proc), key=f"elegir_proc_{documento_id}")
        base_proc = existentes_proc.get(elegir_proc, {})
        with st.form(f"procedimiento_{documento_id}_{elegir_proc}"):
            c1, c2 = st.columns(2)
            clave_proc = c1.text_input("Clave técnica", value=base_proc.get("procedimiento_id", ""), placeholder="CNT_FIRMAS")
            orden_proc = c2.number_input("Orden", min_value=1, value=int(base_proc.get("orden", len(procedimientos_revision) + 1)))
            texto_proc = st.text_area("¿Qué debe verificar la IA?", value=base_proc.get("procedimiento_validacion", ""))
            esperado_proc = st.text_area("Resultado esperado", value=base_proc.get("resultado_esperado", "") or "")
            evidencia_proc = st.text_area("Evidencia requerida", value=base_proc.get("evidencia_requerida", "") or "")
            c1, c2, c3 = st.columns(3)
            riesgo_proc = c1.text_input("Código de riesgo", value=base_proc.get("riesgo_codigo", "Sin riesgo"))
            activo_proc = c2.checkbox("Procedimiento activo", value=bool(base_proc.get("activo", True)))
            revision_proc = c3.selectbox("Estado de revisión", REVISIONES, index=_indice(REVISIONES, base_proc.get("estado_revision", "Pendiente")), key=f"rev_proc_{documento_id}")
            motivo_proc = st.text_input("Motivo del cambio", key=f"motivo_proc_{documento_id}")
            guardar_proc = st.form_submit_button("Guardar procedimiento", disabled=not editable)
        if guardar_proc:
            if not motivo_proc.strip():
                st.error("El motivo del cambio es obligatorio.")
            elif not texto_proc.strip():
                st.error("Describa qué debe verificar la IA.")
            else:
                try:
                    admin.guardar_procedimiento(version_id, documento["tipo_documental"], {
                        "procedimiento_id": clave_proc, "orden": int(orden_proc),
                        "procedimiento_validacion": texto_proc.strip(),
                        "resultado_esperado": esperado_proc.strip(),
                        "evidencia_requerida": evidencia_proc.strip(),
                        "riesgo_codigo": riesgo_proc.strip(), "activo": activo_proc,
                        "estado_revision": revision_proc, "observaciones": "",
                    }, usuario, motivo_proc.strip())
                    _limpiar_cache()
                    st.success("Procedimiento de revisión guardado.")
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))

    with tab_reglas:
        reglas = _reglas(documento_id)
        st.caption("Responda cómo decide el sistema si el documento aplica. No necesita llenar la tabla técnica.")
        with st.form(f"regla_guiada_{documento_id}"):
            opciones = ["Siempre se exige", "Nunca se exige", "Depende de otro documento", "Depende de un dato extraído por IA"]
            modo = st.radio("¿Cuándo se exige este documento?", opciones)
            fuente_tipo = fuente_campo = None
            operador, valor = "EXISTE", True
            if modo == "Depende de otro documento":
                fuente_tipo = st.selectbox("Documento del que depende", sorted({d["tipo_documental"] for d in documentos}))
                operador = st.selectbox("Condición", ["EXISTE", "NO_EXISTE"], format_func={"EXISTE": "Está presente", "NO_EXISTE": "No está presente"}.get)
            elif modo == "Depende de un dato extraído por IA":
                fuente_tipo = st.selectbox("Documento del que se extrae el dato", sorted({d["tipo_documental"] for d in documentos}))
                campos_fuente = _campos(version_id, fuente_tipo)
                fuente_campo = st.selectbox("Dato que se evaluará", [c["nombre_tecnico"] for c in campos_fuente]) if campos_fuente else None
                operador = st.selectbox("Comparación", ["IGUAL", "DISTINTO", "CONTIENE", "EXISTE", "NO_EXISTE"], format_func={"IGUAL": "Es igual a", "DISTINTO": "Es distinto de", "CONTIENE": "Contiene", "EXISTE": "Tiene algún valor", "NO_EXISTE": "No tiene valor"}.get)
                if operador not in {"EXISTE", "NO_EXISTE"}:
                    valor = st.text_input("Valor esperado", placeholder="Sí")
            justificacion = st.text_area("Explicación para el usuario", value=(reglas[0].get("justificacion", "") if reglas else ""))
            revision_regla = st.selectbox("Estado de revisión", REVISIONES, key=f"rev_regla_{documento_id}")
            motivo_regla = st.text_input("Motivo del cambio", key=f"motivo_regla_{documento_id}")
            guardar_regla = st.form_submit_button("Guardar regla", disabled=not editable)
        if guardar_regla:
            if not motivo_regla.strip():
                st.error("El motivo del cambio es obligatorio.")
            elif modo == "Depende de un dato extraído por IA" and not fuente_campo:
                st.error("Primero cree el campo de extracción del que dependerá la regla.")
            else:
                tipo_regla = "SIEMPRE" if modo == "Siempre se exige" else "NO_APLICA" if modo == "Nunca se exige" else "CONDICIONAL"
                fuente = "VALOR_FIJO" if tipo_regla != "CONDICIONAL" else "DOCUMENTO_PRESENTE" if modo == "Depende de otro documento" else "CAMPO_EXTRAIDO"
                admin.guardar_reglas(version_id, documento_id, [{
                    "tipo_regla": tipo_regla, "fuente": fuente,
                    "fuente_tipo_documental": fuente_tipo, "fuente_campo": fuente_campo,
                    "operador": operador, "valor_esperado": valor,
                    "resultado_verdadero": "APLICA", "resultado_falso": "NO_APLICA",
                    "resultado_sin_dato": "PENDIENTE", "justificacion": justificacion,
                    "estado_revision": revision_regla,
                }], usuario, motivo_regla.strip())
                _limpiar_cache()
                st.success("Regla guardada.")
                st.rerun()

    with tab_publicar:
        if not editable:
            st.info("La versión seleccionada ya no es un borrador.")
        else:
            errores = _errores_publicacion(version_id)
            if errores:
                st.error("La versión todavía no puede publicarse.")
                for numero, error in enumerate(errores, 1):
                    st.write(f"{numero}. {error}")
            else:
                st.success("La versión está lista para publicarse.")
            with st.form(f"publicar_{version_id}"):
                motivo_publicacion = st.text_input("Motivo de publicación")
                confirmar = st.checkbox("Confirmo que revisé la configuración")
                publicar = st.form_submit_button("Publicar esta versión", type="primary", disabled=bool(errores) or not puede_publicar)
            if publicar:
                if not confirmar or not motivo_publicacion.strip():
                    st.error("Confirme la revisión e indique el motivo.")
                else:
                    admin.publicar_version(version_id, usuario, motivo_publicacion.strip())
                    _limpiar_cache()
                    st.success("Versión publicada.")
                    st.rerun()
            if not puede_publicar:
                st.warning("Su cuenta puede editar, pero no publicar versiones.")
