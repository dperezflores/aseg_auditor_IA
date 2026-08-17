from __future__ import annotations

import hashlib
import os

import streamlit as st

from modulos import extraccion, generador_excel, persistencia, utilidades_ui


st.set_page_config(
    page_title="ASEG - Auditoría",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)
utilidades_ui.cargar_css("estilos.css")


def _secreto(nombre: str, default: str = "") -> str:
    try:
        return str(st.secrets.get(nombre, default))
    except Exception:
        return os.getenv(nombre, default)


def _huella_sha256(archivo) -> str:
    return hashlib.sha256(archivo.getvalue()).hexdigest()


def _clave_procesamiento(categoria: str, huella: str) -> str:
    return ":".join(
        (categoria, huella, extraccion.MODEL_NAME, extraccion.PROMPT_VERSION)
    )


def _cargar_expediente_activo(forzar: bool = False) -> None:
    st.session_state.setdefault("procedimiento", "LPU (Licitación Pública)")
    st.session_state.setdefault("expediente_nombre", "Expediente principal")
    usuario = _secreto("APP_USER_ID", "usuario_local")
    llave = (
        usuario,
        st.session_state.expediente_nombre,
        st.session_state.procedimiento[:3],
    )
    if not forzar and st.session_state.get("estado_cargado") == llave:
        return

    st.session_state.expediente_id = None
    st.session_state.usar_neon = False
    if persistencia.disponible():
        try:
            expediente_id = persistencia.obtener_o_crear_expediente(
                st.session_state.expediente_nombre,
                st.session_state.procedimiento,
                usuario,
            )
            historial, procesados = persistencia.cargar_expediente(expediente_id)
            st.session_state.expediente_id = expediente_id
            st.session_state.usar_neon = True
        except Exception as exc:
            st.warning(
                "Neon está configurado, pero no fue posible abrir el expediente. "
                f"Se utilizará la caché local temporal. Detalle: {exc}"
            )
            historial, procesados = utilidades_ui.cargar_cache()
    else:
        historial, procesados = utilidades_ui.cargar_cache()

    st.session_state.historial = historial
    st.session_state.archivos_procesados = procesados
    st.session_state.estado_cargado = llave


_cargar_expediente_activo()


def _guardar_inicio(
    categoria: str,
    archivo,
    huella: str,
    clave: str,
) -> None:
    if st.session_state.usar_neon:
        persistencia.registrar_inicio(
            st.session_state.expediente_id,
            categoria,
            archivo.name,
            huella,
            clave,
            extraccion.MODEL_NAME,
            extraccion.PROMPT_VERSION,
        )


def _guardar_exito(clave: str, datos: list[dict], metadatos: dict) -> None:
    if st.session_state.usar_neon:
        persistencia.registrar_resultado(
            st.session_state.expediente_id,
            clave,
            datos,
            metadatos,
        )
    else:
        utilidades_ui.guardar_cache(
            st.session_state.historial,
            st.session_state.archivos_procesados,
        )


def _guardar_error(clave: str, mensaje: str) -> None:
    if st.session_state.usar_neon:
        persistencia.registrar_error(
            st.session_state.expediente_id,
            clave,
            mensaje,
        )


def procesar_lote_documentos(archivos, categoria, funcion_extraccion) -> dict:
    st.session_state.historial.setdefault(categoria, [])
    pendientes = []
    omitidos = 0

    for archivo in archivos:
        huella = _huella_sha256(archivo)
        clave = _clave_procesamiento(categoria, huella)
        if clave in st.session_state.archivos_procesados:
            omitidos += 1
        else:
            pendientes.append((archivo, huella, clave))

    resumen = {
        "seleccionados": len(archivos),
        "pendientes": len(pendientes),
        "exitos": 0,
        "errores": 0,
        "omitidos": omitidos,
    }
    if not pendientes:
        return resumen

    total = len(pendientes)
    barra = st.progress(0, text=f"Preparando {total} documento(s) de {categoria}...")

    for indice, (archivo, huella, clave) in enumerate(pendientes, start=1):
        barra.progress(
            (indice - 1) / total,
            text=f"🤖 Analizando ({indice}/{total}): {archivo.name}",
        )
        try:
            _guardar_inicio(categoria, archivo, huella, clave)
            resultado = funcion_extraccion(archivo)
            if resultado.estado != "OK":
                mensaje = "; ".join(resultado.errores) or "Error de extracción no especificado"
                _guardar_error(clave, mensaje)
                st.error(f"❌ {archivo.name}: {mensaje}")
                resumen["errores"] += 1
                continue

            datos = resultado.datos
            for registro in datos:
                registro["Archivo Origen"] = archivo.name

            # Guardar antes de marcar el archivo como procesado evita éxitos falsos.
            if st.session_state.usar_neon:
                _guardar_exito(clave, datos, resultado.metadatos)

            st.session_state.historial[categoria].extend(datos)
            st.session_state.archivos_procesados.add(clave)
            if not st.session_state.usar_neon:
                _guardar_exito(clave, datos, resultado.metadatos)
            resumen["exitos"] += 1
        except Exception as exc:
            mensaje = f"No fue posible guardar o procesar el documento: {exc}"
            try:
                _guardar_error(clave, mensaje)
            except Exception:
                pass
            st.error(f"❌ {archivo.name}: {mensaje}")
            resumen["errores"] += 1
        finally:
            barra.progress(
                indice / total,
                text=f"Procesados {indice} de {total} documento(s)",
            )

    barra.empty()
    return resumen


def _mostrar_resumen(resumen: dict) -> None:
    if resumen["exitos"]:
        st.success(f"✅ Documentos analizados correctamente: {resumen['exitos']}.")
    if resumen["errores"]:
        st.error(f"⚠️ Documentos con error: {resumen['errores']}.")
    if resumen["omitidos"]:
        st.info(
            f"ℹ️ Documentos omitidos porque ya tenían resultado vigente: "
            f"{resumen['omitidos']}."
        )


def main() -> None:
    estructura_expediente = {
        "PPP": {"key_raiz": "up_ppp", "nombre": "1_PPP (Planeación, Prog. y Presup.)"},
        "ADJ": {"key_raiz": "up_adj", "nombre": "2_ADJ (Adjudicación)"},
        "CNT": {"key_raiz": "up_cnt", "nombre": "3_CNT (Contratación)"},
        "EJE": {
            "subcarpetas": {
                "Estimaciones": {"key": "up_est", "func": extraccion.procesar_estimaciones},
                "Facturas": {"key": "up_fac", "func": extraccion.procesar_facturas},
                "Comprobantes de Pago": {"key": "up_com", "func": extraccion.procesar_comprobantes},
                "Pólizas": {"key": "up_pol", "func": extraccion.procesar_polizas},
            },
            "key_raiz": "up_eje",
            "nombre": "4_EJE (Ejecución)",
        },
        "ETR": {"key_raiz": "up_etr", "nombre": "5_ETR (Entrega Recepción)"},
    }
    mapa_funciones = {"CONTRATO": extraccion.procesar_contratos}
    archivos_subidos = {}

    with st.sidebar:
        st.header("📂 Expediente Unitario")
        st.caption(f"Activo: {st.session_state.expediente_nombre}")
        if st.session_state.usar_neon:
            st.success("Persistencia Neon activa")
        else:
            st.warning("Modo local temporal")

        if st.button("🔄 Recargar expediente", use_container_width=True):
            _cargar_expediente_activo(forzar=True)
            st.rerun()

        st.markdown("---")
        for etapa, config_etapa in estructura_expediente.items():
            with st.expander(f"📁 {config_etapa['nombre']}", expanded=False):
                st.markdown(f"**Documentos generales ({etapa})**")
                archivos_raiz = st.file_uploader(
                    f"Raíz {etapa}",
                    type=["pdf"],
                    accept_multiple_files=True,
                    key=config_etapa["key_raiz"],
                    label_visibility="collapsed",
                )
                if archivos_raiz:
                    archivos_subidos[config_etapa["key_raiz"]] = archivos_raiz
                    for archivo in archivos_raiz:
                        st.caption(f"📄 {archivo.name}")

                for subcategoria, config_sub in config_etapa.get("subcarpetas", {}).items():
                    st.markdown(f"**📂 {subcategoria}**")
                    archivos_sub = st.file_uploader(
                        subcategoria,
                        type=["pdf"],
                        accept_multiple_files=True,
                        key=config_sub["key"],
                        label_visibility="collapsed",
                    )
                    if archivos_sub:
                        archivos_subidos[subcategoria] = archivos_sub
                        for archivo in archivos_sub:
                            huella = _huella_sha256(archivo)
                            clave = _clave_procesamiento(subcategoria, huella)
                            estado = "✅" if clave in st.session_state.archivos_procesados else "⏳"
                            st.caption(f"{estado} {archivo.name}")

    opciones_nav = ["🏠 Inicio", "PPP", "ADJ", "CNT", "EJE", "ETR"]
    pagina_actual = st.radio(
        "Navegación",
        options=opciones_nav,
        horizontal=True,
        label_visibility="collapsed",
    )
    st.markdown("---")

    if pagina_actual == "🏠 Inicio":
        st.markdown("### Configuración del expediente")
        with st.form("form_expediente"):
            nombre = st.text_input(
                "Nombre del expediente",
                value=st.session_state.expediente_nombre,
            )
            opciones = [
                "DIR (Adjudicación Directa)",
                "LPU (Licitación Pública)",
                "LSI (Licitación Simplificada)",
            ]
            procedimiento = st.selectbox(
                "Tipo de procedimiento",
                opciones,
                index=["DIR", "LPU", "LSI"].index(st.session_state.procedimiento[:3]),
            )
            abrir = st.form_submit_button("Abrir o crear expediente", type="primary")
        if abrir:
            st.session_state.expediente_nombre = nombre.strip() or "Expediente principal"
            st.session_state.procedimiento = procedimiento
            _cargar_expediente_activo(forzar=True)
            st.rerun()
        st.info(
            "Suba los documentos desde el panel lateral. Los resultados se guardan "
            "por expediente y se vuelven a procesar cuando cambia el modelo o el prompt."
        )
        return

    if pagina_actual == "EJE":
        st.markdown("### Etapa: Ejecución - Análisis documental")
        disponibles = {}
        for subcategoria in estructura_expediente["EJE"]["subcarpetas"]:
            for archivo in archivos_subidos.get(subcategoria, []):
                disponibles[f"{archivo.name} (en {subcategoria})"] = (archivo, subcategoria)

        if disponibles:
            seleccionados = st.multiselect(
                "Seleccione los archivos a analizar:",
                options=list(disponibles),
            )
            if st.button("🚀 Procesar selección", type="primary") and seleccionados:
                acumulado = {"seleccionados": 0, "pendientes": 0, "exitos": 0, "errores": 0, "omitidos": 0}
                for nombre in seleccionados:
                    archivo, categoria = disponibles[nombre]
                    funcion = estructura_expediente["EJE"]["subcarpetas"][categoria]["func"]
                    parcial = procesar_lote_documentos([archivo], categoria, funcion)
                    for clave in acumulado:
                        acumulado[clave] += parcial[clave]
                _mostrar_resumen(acumulado)
        else:
            st.warning("No hay documentos cargados en las subcarpetas de ejecución.")

        resultados = {}
        for categoria in ["Estimaciones", "Facturas", "Comprobantes de Pago", "Pólizas"]:
            datos = st.session_state.historial.get(categoria, [])
            if not datos:
                continue
            if categoria == "Pólizas":
                df_dev, df_pag, xls = generador_excel.reporte_polizas(datos)
                resultados[categoria] = {"df_dev": df_dev, "df_pag": df_pag, "xls": xls}
            else:
                funcion = {
                    "Estimaciones": generador_excel.reporte_estimaciones,
                    "Facturas": generador_excel.reporte_facturas,
                    "Comprobantes de Pago": generador_excel.reporte_comprobantes,
                }[categoria]
                df, xls = funcion(datos)
                resultados[categoria] = {"df": df, "xls": xls}

        if resultados:
            tabs = st.tabs([f"📊 {nombre}" for nombre in resultados])
            for tab, (nombre, reporte) in zip(tabs, resultados.items()):
                with tab:
                    st.download_button(
                        f"📥 Descargar {nombre}",
                        data=reporte["xls"],
                        file_name=f"Reporte_{nombre}.xlsx",
                        key=f"btn_{nombre}",
                    )
                    if nombre == "Pólizas":
                        utilidades_ui.renderizar_tabla_html(reporte["df_dev"], "Pólizas Devengo")
                        utilidades_ui.renderizar_tabla_html(reporte["df_pag"], "Pólizas Pago")
                    else:
                        utilidades_ui.renderizar_tabla_html(reporte["df"], nombre)
        return

    st.markdown(f"### Etapa: {estructura_expediente[pagina_actual]['nombre']}")
    archivos_etapa = archivos_subidos.get(
        estructura_expediente[pagina_actual]["key_raiz"], []
    )
    if archivos_etapa:
        por_nombre = {archivo.name: archivo for archivo in archivos_etapa}
        seleccionados = st.multiselect(
            "Seleccione los archivos a clasificar y analizar:",
            options=list(por_nombre),
        )
        if st.button("🚀 Iniciar análisis inteligente", type="primary") and seleccionados:
            resumen = {"seleccionados": 0, "pendientes": 0, "exitos": 0, "errores": 0, "omitidos": 0}
            no_encontrados = 0
            sin_funcion = 0
            for nombre in seleccionados:
                concepto = utilidades_ui.consultar_diccionario(
                    nombre, st.session_state.procedimiento
                )
                if not concepto:
                    no_encontrados += 1
                    continue
                coincidencia = next(
                    ((clave, funcion) for clave, funcion in mapa_funciones.items() if clave in concepto),
                    None,
                )
                if not coincidencia:
                    sin_funcion += 1
                    st.warning(f"No hay extractor programado para: {concepto}.")
                    continue
                categoria, funcion = coincidencia
                parcial = procesar_lote_documentos([por_nombre[nombre]], categoria, funcion)
                for clave in resumen:
                    resumen[clave] += parcial[clave]

            _mostrar_resumen(resumen)
            if no_encontrados:
                st.warning(f"Archivos sin coincidencia en el diccionario: {no_encontrados}.")
            if sin_funcion:
                st.warning(f"Tipos documentales todavía sin extractor: {sin_funcion}.")
    else:
        st.warning(f"No hay documentos cargados en la carpeta de {pagina_actual}.")

    conceptos = []
    for concepto, datos in st.session_state.historial.items():
        if concepto in ["Estimaciones", "Facturas", "Comprobantes de Pago", "Pólizas"]:
            continue
        docs = [
            doc
            for doc in datos
            if pagina_actual in str(doc.get("Archivo Origen", "")).upper()
        ]
        if docs:
            conceptos.append((concepto, docs))

    if conceptos:
        tabs = st.tabs([f"📊 {concepto}" for concepto, _ in conceptos])
        for tab, (concepto, documentos) in zip(tabs, conceptos):
            with tab:
                if concepto == "CONTRATO":
                    for documento in documentos:
                        utilidades_ui.renderizar_reporte_contrato(documento)


if __name__ == "__main__":
    main()

