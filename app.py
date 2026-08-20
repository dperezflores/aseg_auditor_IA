from __future__ import annotations

import hashlib
import json
import os

import streamlit as st

from modulos import (
    aplicabilidad,
    catalogo,
    extraccion,
    generador_excel,
    persistencia,
    permisos,
    ui_admin_catalogo,
    utilidades_ui,
)


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
    cache = st.session_state.setdefault("huellas_archivos", {})
    identidad = (
        str(getattr(archivo, "file_id", "")),
        str(getattr(archivo, "name", "")),
        int(getattr(archivo, "size", 0) or 0),
    )
    if identidad not in cache:
        cache[identidad] = hashlib.sha256(archivo.getvalue()).hexdigest()
    return cache[identidad]


@st.cache_data(show_spinner=False)
def _generar_reporte_ejecucion(categoria: str, datos_json: str):
    datos = json.loads(datos_json)
    if categoria == "Pólizas":
        return generador_excel.reporte_polizas(datos)
    funcion = {
        "Estimaciones": generador_excel.reporte_estimaciones,
        "Facturas": generador_excel.reporte_facturas,
        "Comprobantes de Pago": generador_excel.reporte_comprobantes,
    }[categoria]
    return funcion(datos)


def _archivos_para_conciliar(archivos_subidos) -> list[aplicabilidad.ArchivoExpediente]:
    archivos = [
        aplicabilidad.ArchivoExpediente(
            nombre=registro.get("nombre", ""),
            huella=registro.get("huella", ""),
            origen=registro.get("origen", "guardado"),
            clave_catalogo=registro.get("clave_catalogo") or "",
        )
        for registro in st.session_state.get("archivos_guardados", [])
        if registro.get("nombre")
    ]
    for grupo in archivos_subidos.values():
        for archivo in grupo:
            archivos.append(
                aplicabilidad.ArchivoExpediente(
                    nombre=archivo.name,
                    huella=_huella_sha256(archivo),
                    origen="cargado",
                )
            )
    return archivos


def _registros_archivos_actuales(archivos_subidos) -> list[dict]:
    registros = list(st.session_state.get("archivos_guardados", []))
    for grupo in archivos_subidos.values():
        for archivo in grupo:
            registros.append({"nombre": archivo.name, "huella": _huella_sha256(archivo)})
    return registros


def _contexto_automatico(archivos) -> dict:
    tipos_presentes = {
        archivo.clave_catalogo
        for archivo in archivos
        if archivo.clave_catalogo
    }
    campos: dict[str, dict] = {}
    for categoria, analisis_listado in st.session_state.get("historial", {}).items():
        for analisis in analisis_listado:
            if not isinstance(analisis, dict):
                continue
            tipo = analisis.get("catalogo", {}).get("tipo_documental") or categoria
            for dato in analisis.get("datos_extraidos", []):
                if dato.get("encontrado"):
                    campos.setdefault(tipo, {})[dato.get("nombre_tecnico")] = dato.get("valor")
            if analisis.get("catalogo", {}).get("clave_catalogo"):
                tipos_presentes.add(tipo)
    return {
        "documentos_presentes": tipos_presentes,
        "campos_extraidos": campos,
        "resultados_ia": st.session_state.get("resultados_ia", {}),
    }


def _version_prompt(
    documento_catalogo: catalogo.DocumentoCatalogo | None = None,
) -> str:
    if not documento_catalogo:
        return extraccion.PROMPT_VERSION
    return ":".join(
        (extraccion.PROMPT_VERSION, documento_catalogo.firma_configuracion)
    )


def _clave_procesamiento(
    categoria: str,
    huella: str,
    documento_catalogo: catalogo.DocumentoCatalogo | None = None,
) -> str:
    return ":".join(
        (categoria, huella, extraccion.MODEL_NAME, _version_prompt(documento_catalogo))
    )


def _cargar_expediente_activo(forzar: bool = False) -> str | None:
    st.session_state.setdefault("procedimiento", "LPU (Licitación Pública)")
    st.session_state.setdefault("expediente_nombre", "Expediente principal")
    usuario = _secreto("APP_USER_ID", "usuario_local")
    expediente_seleccionado = st.session_state.get("expediente_id")
    llave = (usuario, expediente_seleccionado, st.session_state.expediente_nombre)
    if not forzar and st.session_state.get("estado_cargado") == llave:
        return None

    st.session_state.usar_neon = False
    datos_aplicabilidad = {}
    archivos_guardados = []
    resultados_ia = {}
    accion = "local"
    if persistencia.disponible():
        try:
            if expediente_seleccionado:
                info = persistencia.abrir_expediente(expediente_seleccionado, usuario)
                expediente_id, creado = info["id"], False
                st.session_state.expediente_nombre = info["nombre"]
                st.session_state.procedimiento = {
                    "DIR": "DIR (Adjudicación Directa)",
                    "LPU": "LPU (Licitación Pública)",
                    "LSI": "LSI (Licitación Simplificada)",
                }.get(info["procedimiento"], info["procedimiento"])
            else:
                expediente_id, creado = persistencia.obtener_o_crear_expediente(
                    st.session_state.expediente_nombre,
                    st.session_state.procedimiento,
                    usuario,
                )
            historial, procesados = persistencia.cargar_expediente(expediente_id)
            datos_aplicabilidad, archivos_guardados = (
                persistencia.cargar_control_expediente(expediente_id)
            )
            resultados_ia = persistencia.cargar_resultados_requisitos(expediente_id)
            st.session_state.expediente_id = expediente_id
            st.session_state.usar_neon = True
            st.session_state.documentos_catalogo = persistencia.cargar_catalogo_expediente(
                expediente_id, st.session_state.procedimiento
            )
            accion = "creado" if creado else "abierto"
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
    st.session_state.datos_aplicabilidad = datos_aplicabilidad
    st.session_state.archivos_guardados = archivos_guardados
    st.session_state.resultados_ia = resultados_ia
    st.session_state.estado_cargado = (
        usuario, st.session_state.get("expediente_id"), st.session_state.expediente_nombre
    )
    return accion


def _guardar_inicio(
    categoria: str,
    archivo,
    huella: str,
    clave: str,
    documento_catalogo: catalogo.DocumentoCatalogo | None = None,
) -> None:
    if st.session_state.usar_neon:
        persistencia.registrar_inicio(
            st.session_state.expediente_id,
            categoria,
            archivo.name,
            huella,
            clave,
            extraccion.MODEL_NAME,
            _version_prompt(documento_catalogo),
            documento_catalogo.id if documento_catalogo else None,
            documento_catalogo.clave_catalogo if documento_catalogo else None,
            documento_catalogo.tipo_documental if documento_catalogo else None,
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


def procesar_lote_documentos(
    archivos,
    categoria,
    funcion_extraccion,
    documento_catalogo: catalogo.DocumentoCatalogo | None = None,
) -> dict:
    st.session_state.historial.setdefault(categoria, [])
    pendientes = []
    omitidos = 0

    for archivo in archivos:
        huella = _huella_sha256(archivo)
        clave = _clave_procesamiento(categoria, huella, documento_catalogo)
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
            _guardar_inicio(categoria, archivo, huella, clave, documento_catalogo)
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
    usuario_actual = _secreto("APP_USER_ID", "usuario_local")
    st.session_state.setdefault("procedimiento", "LPU (Licitación Pública)")
    st.session_state.setdefault("expediente_nombre", "")
    st.session_state.setdefault("expediente_id", None)
    st.session_state.setdefault("usar_neon", False)
    st.session_state.setdefault("documentos_catalogo", [])
    st.session_state.setdefault("historial", {k: [] for k in persistencia.HISTORIAL_BASE})
    st.session_state.setdefault("archivos_procesados", set())
    st.session_state.setdefault("archivos_guardados", [])
    st.session_state.setdefault("datos_aplicabilidad", {})
    st.session_state.setdefault("resultados_ia", {})
    if st.session_state.get("acceso_usuario_id") != usuario_actual:
        st.session_state.acceso_usuario = permisos.acceso_actual(usuario_actual)
        st.session_state.acceso_usuario_id = usuario_actual
    acceso = st.session_state.acceso_usuario
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
    mapa_funciones = {
        "CONTRATO": extraccion.procesar_contratos,
        "CNT_CNT": extraccion.procesar_contratos,
    }
    archivos_subidos = {}
    documentos_catalogo = st.session_state.get("documentos_catalogo", [])

    if not st.session_state.expediente_id:
        st.markdown("### Expedientes")
        st.caption("Abra un expediente existente o cree uno nuevo. El procedimiento queda guardado con el expediente.")
        if persistencia.disponible():
            try:
                expedientes = persistencia.listar_expedientes(usuario_actual)
            except Exception as exc:
                st.error(f"No fue posible consultar los expedientes: {exc}")
                expedientes = []
            if expedientes:
                etiquetas = {
                    e["id"]: f'{e["nombre"]} · {e["procedimiento"]} · actualizado {e["actualizado_en"]:%d/%m/%Y %H:%M}'
                    for e in expedientes
                }
                with st.form("abrir_expediente_existente"):
                    elegido = st.selectbox("Expediente existente", list(etiquetas), format_func=etiquetas.get)
                    abrir_existente = st.form_submit_button("Abrir expediente", type="primary")
                if abrir_existente:
                    st.session_state.expediente_id = elegido
                    _cargar_expediente_activo(forzar=True)
                    st.session_state.mensaje_expediente = ("success", "Expediente abierto correctamente.")
                    st.rerun()
            else:
                st.info("Todavía no hay expedientes guardados para esta cuenta.")
            with st.expander("➕ Crear expediente"):
                with st.form("crear_expediente_nuevo"):
                    nombre_nuevo = st.text_input("Nombre del expediente")
                    procedimiento_nuevo = st.selectbox("Tipo de procedimiento", [
                        "DIR (Adjudicación Directa)", "LPU (Licitación Pública)", "LSI (Licitación Simplificada)"
                    ])
                    crear_nuevo = st.form_submit_button("Crear y abrir expediente", type="primary")
                if crear_nuevo:
                    if not nombre_nuevo.strip():
                        st.error("Indique el nombre del expediente.")
                    else:
                        st.session_state.expediente_nombre = nombre_nuevo.strip()
                        st.session_state.procedimiento = procedimiento_nuevo
                        st.session_state.expediente_id = None
                        accion = _cargar_expediente_activo(forzar=True)
                        st.session_state.mensaje_expediente = (
                            "success" if accion == "creado" else "info",
                            "Expediente creado y abierto correctamente." if accion == "creado" else "Ese nombre ya existía; se abrió el expediente guardado.",
                        )
                        st.rerun()
        else:
            st.warning("Configure DATABASE_URL para listar y recordar expedientes.")
        if acceso.administra_catalogo:
            st.markdown("---")
            if st.button("⚙️ Abrir administración del catálogo"):
                st.session_state.mostrar_catalogo_sin_expediente = True
            if st.session_state.get("mostrar_catalogo_sin_expediente"):
                ui_admin_catalogo.renderizar(usuario_actual, acceso.publica_catalogo)
        return

    with st.sidebar:
        st.header("📂 Expediente Unitario")
        st.caption(f"Activo: {st.session_state.expediente_nombre}")
        if st.session_state.usar_neon:
            st.success("Persistencia Neon activa")
            if documentos_catalogo:
                st.caption(
                    f"Catálogo maestro: {len(documentos_catalogo)} documento(s) "
                    "aprobado(s) para este procedimiento."
                )
            else:
                st.caption("Catálogo maestro sin definiciones aprobadas para este procedimiento.")
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
                    type=catalogo.extensiones_por_etapa(documentos_catalogo, etapa),
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

    conciliacion = aplicabilidad.conciliar_expediente(
        documentos_catalogo,
        (archivos_control := _archivos_para_conciliar(archivos_subidos)),
        _contexto_automatico(archivos_control),
    )

    def analizar_desde_validacion(archivo, documento) -> None:
        huella = _huella_sha256(archivo)
        ya_registrado = any(
            item.get("huella") == huella or item.get("nombre") == archivo.name
            for item in st.session_state.get("archivos_guardados", [])
        )
        if st.session_state.usar_neon and not ya_registrado:
            persistencia.registrar_archivo_cargado(
                st.session_state.expediente_id,
                documento.etapa,
                archivo.name,
                huella,
                getattr(archivo, "type", None),
                getattr(archivo, "size", None),
                documento.clave_catalogo,
                usuario_actual,
            )
        resumen = procesar_lote_documentos(
            [archivo],
            documento.tipo_documental,
            lambda item: extraccion.procesar_con_catalogo(item, documento),
            documento,
        )
        _mostrar_resumen(resumen)
        if resumen["exitos"]:
            _cargar_expediente_activo(forzar=True)
            st.session_state.destino_pagina = documento.etapa
            st.rerun()

    def ver_analisis_desde_validacion(documento) -> None:
        st.session_state.destino_pagina = documento.etapa
        st.rerun()

    def eliminar_analisis(documento_id: str) -> None:
        persistencia.eliminar_analisis(
            st.session_state.expediente_id, documento_id, usuario_actual
        )
        st.session_state.archivos_procesados = {
            clave for clave in st.session_state.archivos_procesados
            if not any(
                analisis.get("_documento_id") == documento_id
                and analisis.get("_clave_procesamiento") == clave
                for lista in st.session_state.historial.values()
                for analisis in lista if isinstance(analisis, dict)
            )
        }
        _cargar_expediente_activo(forzar=True)
        st.session_state.mensaje_analisis = "Análisis eliminado de la vista y registrado en la bitácora."
        st.rerun()
    with st.sidebar:
        st.markdown("---")
        st.markdown("#### Control de integración")
        st.caption(
            f"Encontrados: {conciliacion.contar('ENCONTRADO')} · "
            f"Faltantes: {conciliacion.contar('FALTANTE')} · "
            f"No aplicables: {conciliacion.contar('NO_APLICABLE')} · "
            f"Pendientes: {conciliacion.contar('PENDIENTE')}"
        )

    opciones_nav = ["🏠 Inicio", "PPP", "ADJ", "CNT", "EJE", "ETR"]
    if acceso.administra_catalogo:
        opciones_nav.append("⚙️ Catálogo")
    destino = st.session_state.pop("destino_pagina", None)
    if destino in opciones_nav:
        st.session_state["pagina_actual"] = destino
    pagina_actual = st.radio(
        "Navegación",
        options=opciones_nav,
        horizontal=True,
        label_visibility="collapsed",
        key="pagina_actual",
    )
    st.markdown("---")

    if pagina_actual == "🏠 Inicio":
        st.markdown("### Expediente activo")
        mensaje_expediente = st.session_state.pop("mensaje_expediente", None)
        if mensaje_expediente:
            nivel, mensaje = mensaje_expediente
            if nivel == "success":
                st.success(mensaje)
            elif nivel == "info":
                st.info(mensaje)
            else:
                st.warning(mensaje)

        c1, c2, c3 = st.columns([3, 2, 1])
        c1.text_input("Nombre", value=st.session_state.expediente_nombre, disabled=True)
        c2.text_input("Procedimiento", value=st.session_state.procedimiento, disabled=True)
        if c3.button("Cambiar expediente", use_container_width=True):
            st.session_state.expediente_id = None
            st.session_state.estado_cargado = None
            st.session_state.documentos_catalogo = []
            st.rerun()
        st.info(
            "Suba los documentos desde el panel lateral. Los resultados se guardan "
            "por expediente y se vuelven a procesar cuando cambia el modelo o el prompt."
        )
        st.markdown("### Validación del expediente")
        st.caption(
            "La lista y su aplicabilidad se calculan automáticamente con la versión "
            "del catálogo asignada al expediente."
        )
        utilidades_ui.renderizar_conciliacion_expediente(
            conciliacion,
            al_analizar=analizar_desde_validacion,
            al_ver_analisis=ver_analisis_desde_validacion,
            documentos_catalogo=documentos_catalogo,
            archivos_existentes=_registros_archivos_actuales(archivos_subidos),
        )
        return

    if pagina_actual == "⚙️ Catálogo":
        ui_admin_catalogo.renderizar(usuario_actual, acceso.publica_catalogo)
        return

    if pagina_actual == "EJE":
        st.markdown("### Etapa: Ejecución - Análisis documental")
        utilidades_ui.renderizar_conciliacion_expediente(conciliacion, "EJE")
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
                    huella = _huella_sha256(archivo)
                    ya_registrado = any(
                        item.get("huella") == huella or item.get("nombre") == archivo.name
                        for item in st.session_state.get("archivos_guardados", [])
                    )
                    if st.session_state.usar_neon and not ya_registrado:
                        definicion = catalogo.clasificar_archivo(
                            archivo.name, (d for d in documentos_catalogo if d.etapa == "EJE")
                        )
                        persistencia.registrar_archivo_cargado(
                            st.session_state.expediente_id, "EJE", archivo.name, huella,
                            getattr(archivo, "type", None), getattr(archivo, "size", None),
                            definicion.clave_catalogo if definicion else None, usuario_actual,
                        )
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
                df_dev, df_pag, xls = _generar_reporte_ejecucion(
                    categoria, json.dumps(datos, ensure_ascii=False, sort_keys=True, default=str)
                )
                resultados[categoria] = {"df_dev": df_dev, "df_pag": df_pag, "xls": xls}
            else:
                df, xls = _generar_reporte_ejecucion(
                    categoria, json.dumps(datos, ensure_ascii=False, sort_keys=True, default=str)
                )
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
    utilidades_ui.renderizar_conciliacion_expediente(
        conciliacion,
        pagina_actual,
        al_analizar=analizar_desde_validacion,
        al_ver_analisis=ver_analisis_desde_validacion,
        documentos_catalogo=documentos_catalogo,
        archivos_existentes=_registros_archivos_actuales(archivos_subidos),
    )
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
                documento_catalogo = catalogo.clasificar_archivo(
                    nombre,
                    (
                        documento
                        for documento in documentos_catalogo
                        if documento.etapa == pagina_actual
                    ),
                )
                concepto = (
                    documento_catalogo.tipo_documental
                    if documento_catalogo
                    else utilidades_ui.consultar_diccionario(
                        nombre, st.session_state.procedimiento
                    )
                )
                if not concepto:
                    no_encontrados += 1
                    continue
                if documento_catalogo:
                    coincidencia = (
                        documento_catalogo.tipo_documental,
                        lambda archivo, definicion=documento_catalogo: (
                            extraccion.procesar_con_catalogo(archivo, definicion)
                        ),
                    )
                else:
                    coincidencia = (
                        (concepto, mapa_funciones[concepto])
                        if concepto in mapa_funciones
                        else next(
                            (
                                (clave, funcion)
                                for clave, funcion in mapa_funciones.items()
                                if clave in concepto
                            ),
                            None,
                        )
                    )
                if not coincidencia:
                    sin_funcion += 1
                    st.warning(
                        f"El archivo fue reconocido por la clasificación anterior "
                        f"como {concepto}, pero no existe una definición aprobada "
                        f"del catálogo para {st.session_state.procedimiento[:3]} "
                        f"en esta etapa."
                    )
                    continue
                categoria, funcion = coincidencia
                archivo_actual = por_nombre[nombre]
                huella_actual = _huella_sha256(archivo_actual)
                ya_registrado = any(
                    item.get("huella") == huella_actual or item.get("nombre") == archivo_actual.name
                    for item in st.session_state.get("archivos_guardados", [])
                )
                if st.session_state.usar_neon and not ya_registrado:
                    persistencia.registrar_archivo_cargado(
                        st.session_state.expediente_id, pagina_actual, archivo_actual.name,
                        huella_actual, getattr(archivo_actual, "type", None),
                        getattr(archivo_actual, "size", None),
                        documento_catalogo.clave_catalogo if documento_catalogo else None,
                        usuario_actual,
                    )
                parcial = procesar_lote_documentos(
                    [archivo_actual],
                    categoria,
                    funcion,
                    documento_catalogo,
                )
                for clave in resumen:
                    resumen[clave] += parcial[clave]

            _mostrar_resumen(resumen)
            if no_encontrados:
                st.warning(f"Archivos sin coincidencia en el diccionario: {no_encontrados}.")
            if sin_funcion:
                st.warning(
                    "Archivos reconocidos únicamente por la clasificación anterior "
                    f"y no analizados: {sin_funcion}."
                )
    else:
        st.warning(f"No hay documentos cargados en la carpeta de {pagina_actual}.")

    conceptos = []
    archivos_catalogados = {
        str(doc.get("Archivo Origen", ""))
        for concepto, datos in st.session_state.historial.items()
        if concepto not in {"CONTRATO", "Estimaciones", "Facturas", "Comprobantes de Pago", "Pólizas"}
        for doc in datos
        if isinstance(doc, dict) and "datos_extraidos" in doc
    }
    for concepto, datos in st.session_state.historial.items():
        if concepto in ["Estimaciones", "Facturas", "Comprobantes de Pago", "Pólizas"]:
            continue
        docs = (
            datos
            if concepto.startswith(f"{pagina_actual}_")
            else [
                doc
                for doc in datos
                if pagina_actual in str(doc.get("Archivo Origen", "")).upper()
            ]
        )
        if concepto == "CONTRATO":
            docs = [doc for doc in docs if str(doc.get("Archivo Origen", "")) not in archivos_catalogados]
        if docs:
            conceptos.append((concepto, docs))

    if conceptos:
        tabs = st.tabs([f"📊 {concepto}" for concepto, _ in conceptos])
        for tab, (concepto, documentos) in zip(tabs, conceptos):
            with tab:
                for documento in documentos:
                    if "datos_extraidos" in documento:
                        utilidades_ui.renderizar_reporte_catalogo(documento, eliminar_analisis)
                    elif concepto in {"CONTRATO", "CNT_CNT"}:
                        utilidades_ui.renderizar_reporte_contrato(documento, eliminar_analisis)


if __name__ == "__main__":
    main()
