import streamlit as st
from modulos import extraccion, generador_excel, utilidades_ui
import time

st.set_page_config(page_title="ASEG - Auditoría", page_icon="🏗️", layout="wide", initial_sidebar_state="expanded")

utilidades_ui.cargar_css("estilos.css")

if "historial" not in st.session_state:
    hist, procesados = utilidades_ui.cargar_cache()
    st.session_state.historial = hist
    st.session_state.archivos_procesados = procesados
    
if "procedimiento" not in st.session_state:
    st.session_state.procedimiento = "LPU (Licitación Pública)"

# ==========================================
# ⚙️ MOTOR DE PROCESAMIENTO
# ==========================================
def procesar_lote_documentos(archivos, categoria, funcion_extraccion):
    # Si la categoría (ej. "CONTRATO") es nueva, la creamos en el historial dinámicamente
    if categoria not in st.session_state.historial:
        st.session_state.historial[categoria] = []
        
    pendientes = []
    for f in archivos:
        huella_cruda = utilidades_ui.generar_huella_archivo(f)
        huella_carpeta = f"{categoria}_{huella_cruda}"
        if huella_carpeta not in st.session_state.archivos_procesados:
            pendientes.append((f, huella_carpeta))
    
    if not pendientes: 
        return 0, False 
    
    hubo_error = False 
    total = len(pendientes)
    
    # Inicializamos la barra en 0% con un mensaje de arranque
    bar = st.progress(0, text=f"🚀 Iniciando análisis de {total} documento(s) de {categoria}...")
    
    for i, (arch, huella_carpeta) in enumerate(pendientes):
        # 1. Calculamos el % exacto al iniciar este documento (Ej. 0, 33, 66)
        porcentaje_actual = int((i / total) * 100)
        
        # Actualizamos la barra y mostramos el NOMBRE del documento actual
        mensaje_analisis = f"🤖 Analizando IA ({i+1}/{total}): {arch.name}..."
        bar.progress(porcentaje_actual, text=mensaje_analisis)
        
        # --- EXTRACCIÓN DE IA ---
        datos = funcion_extraccion(arch)
        
        if datos and isinstance(datos, list) and "Error" in datos[0]:
            st.error(f"❌ Error de IA en '{arch.name}': {datos[0]['Error']}")
            hubo_error = True
            continue 

        for d in datos: d["Archivo Origen"] = arch.name
        
        st.session_state.historial[categoria].extend(datos)
        st.session_state.archivos_procesados.add(huella_carpeta) 
        utilidades_ui.guardar_cache(st.session_state.historial, st.session_state.archivos_procesados)
        
        # 2. Calculamos el % exacto al TERMINAR este documento
        porcentaje_exito = int(((i + 1) / total) * 100)
        
        # 🌟 ESTRATEGIA DE CADENCIA 🌟
        if i < total - 1:
            # Si NO es el último, llenamos la barra parcialmente e informamos de la pausa
            mensaje_pausa = f"✅ '{arch.name}' extraído. Pausa de seguridad de 5s..."
            bar.progress(porcentaje_exito, text=mensaje_pausa)
            time.sleep(5)
        else:
            # Si es el último, obligamos a la barra a llegar al 100%
            bar.progress(100, text=f"🎉 ¡Lote completado al 100%!")
            time.sleep(1) # Un segundo de pausa visual para que el usuario disfrute ver el 100%
            
    bar.empty() # Limpiamos la pantalla
    return total, hubo_error


def main():
    # ==========================================
    # 🏗️ ESTRUCTURA DEL EXPEDIENTE 
    # ==========================================
    estructura_expediente = {
        "PPP": {"key_raiz": "up_ppp", "nombre": "1_PPP (Planeación, Prog. y Presup.)"},
        "ADJ": {"key_raiz": "up_adj", "nombre": "2_ADJ (Adjudicación)"},
        "CNT": {"key_raiz": "up_cnt", "nombre": "3_CNT (Contratación)"},
        "EJE": {
            "subcarpetas": {
                "Estimaciones": {"key": "up_est", "func": extraccion.procesar_estimaciones},
                "Facturas": {"key": "up_fac", "func": extraccion.procesar_facturas},
                "Comprobantes de Pago": {"key": "up_com", "func": extraccion.procesar_comprobantes},
                "Pólizas": {"key": "up_pol", "func": extraccion.procesar_polizas}
            },
            "key_raiz": "up_eje", "nombre": "4_EJE (Ejecución)"
        },
        "ETR": {"key_raiz": "up_etr", "nombre": "5_ETR (Entrega Recepción)"}
    }
    
    # 🧠 MAPA DE FUNCIONES (El "Cerebro" del Diccionario)
    # Aquí uniremos el Concepto del Excel con la función de Python correspondiente
    mapa_funciones_inteligentes = {
        "CONTRATO": extraccion.procesar_contratos,
        # "ACTA DE FALLO": extraccion.procesar_acta_fallo, <-- Así agregaremos los demás después
    }

    archivos_subidos = {} 

    # ==========================================
    # 🗄️ BARRA LATERAL 
    # ==========================================
    with st.sidebar:
        st.header("📂 Expediente Unitario")
        utilidades_ui.msg_ayuda("Cargue aquí todos los documentos de la obra.")
        
        if st.button("🗑️ Limpiar Memoria y Caché", use_container_width=True):
            utilidades_ui.limpiar_cache_y_memoria()
            
        st.markdown("---")

        for etapa, config_etapa in estructura_expediente.items():
            with st.expander(f"📁 {config_etapa['nombre']}", expanded=False):
                st.markdown(f"**Documentos Generales ({etapa})**") 
                archivos_raiz = st.file_uploader(f"Raíz {etapa}", type=["pdf"], accept_multiple_files=True, key=config_etapa["key_raiz"], label_visibility="collapsed")
                
                if archivos_raiz:
                    archivos_subidos[config_etapa["key_raiz"]] = archivos_raiz # Guardamos en memoria global
                    for f in archivos_raiz:
                        st.markdown(f"<span style='color:#00304F; font-size:12px;'>📄 {f.name}</span>", unsafe_allow_html=True)

                if "subcarpetas" in config_etapa:
                    st.markdown("---")
                    st.markdown("**Análisis Específicos:**")
                    for subcategoria, config_sub in config_etapa["subcarpetas"].items():
                        st.markdown(f"<p style='margin-bottom: 2px; font-weight: 600; font-size: 14px; color: #00304F;'>📂 {subcategoria}</p>", unsafe_allow_html=True)
                        archivos_sub = st.file_uploader(subcategoria, type=["pdf"], accept_multiple_files=True, key=config_sub["key"], label_visibility="collapsed")
                        
                        if archivos_sub:
                            archivos_subidos[subcategoria] = archivos_sub 
                            for f in archivos_sub: 
                                estatus = "✅" if f"{subcategoria}_{utilidades_ui.generar_huella_archivo(f)}" in st.session_state.archivos_procesados else "⏳"
                                st.markdown(f"<span style='color:#00304F; font-size:12px; margin-left: 15px;'>📄 {f.name} ({estatus})</span>", unsafe_allow_html=True)
                        st.markdown("<br>", unsafe_allow_html=True)

    # ==========================================
    # 🧭 TOP BAR 
    # ==========================================
    opciones_nav = ["🏠 Inicio", "PPP", "ADJ", "CNT", "EJE", "ETR"]
    pagina_actual = st.radio("Navegación", options=opciones_nav, horizontal=True, label_visibility="collapsed")
    st.markdown("---")

    # ==========================================
    # 💻 VISTA PRINCIPAL
    # ==========================================
    
    if pagina_actual == "🏠 Inicio":
        st.markdown("### Configuración del Expediente")
        st.session_state.procedimiento = st.selectbox(
            "📍 Seleccione el Tipo de Procedimiento de la Obra:",
            ["DIR (Adjudicación Directa)", "LPU (Licitación Pública)", "LSI (Licitación Simplificada)"],
            index=["DIR", "LPU", "LSI"].index(st.session_state.procedimiento[:3]) if st.session_state.procedimiento else 1
        )
        st.info("💡 **Recordatorio:** Suba sus archivos en el panel lateral. El sistema identificará automáticamente el tipo de documento basándose en la codificación del nombre y el procedimiento seleccionado.")

    # ------------------ PÁGINA: EJE (Subcarpetas manuales) ------------------
    elif pagina_actual == "EJE":
        st.markdown("### Etapa: Ejecución - Análisis Documental")
        
        # Filtramos solo los archivos subidos a las subcarpetas de EJE
        archivos_disponibles_eje = {}
        for sub in estructura_expediente["EJE"]["subcarpetas"]:
            if archivos_subidos.get(sub):
                for f in archivos_subidos[sub]:
                    archivos_disponibles_eje[f"{f.name} (en {sub})"] = (f, sub) # Guardamos el objeto archivo y a qué subcarpeta pertenece

        if archivos_disponibles_eje:
            seleccionados_nombres = st.multiselect("📄 Seleccione los archivos a analizar:", options=list(archivos_disponibles_eje.keys()))
            
            if st.button("🚀 Procesar Selección", type="primary") and seleccionados_nombres:
                zona_mensajes = st.empty()
                procesados_total, con_error_total = 0, 0
                
                with st.spinner("🤖 Analizando documentos..."):
                    for nombre in seleccionados_nombres:
                        archivo, categoria = archivos_disponibles_eje[nombre]
                        func_extraccion = estructura_expediente["EJE"]["subcarpetas"][categoria]["func"]
                        
                        procesados, hubo_error = procesar_lote_documentos([archivo], categoria, func_extraccion)
                        procesados_total += procesados
                        con_error_total += 1 if hubo_error else 0
                
                with zona_mensajes.container():
                    if procesados_total > 0: st.success(f"✅ ¡Se procesaron {procesados_total} documento(s) con éxito!")
                    if con_error_total > 0: st.error("⚠️ Hubo errores con la conexión de IA en algunos documentos.")
                    if procesados_total == 0 and con_error_total == 0: st.info("ℹ️ Todos los documentos seleccionados ya estaban analizados previamente.")
        else:
            st.warning("⚠️ No hay documentos cargados en las subcarpetas de Ejecución (Panel lateral).")

        # RENDERIZADO DE TABLAS EJE (Igual que antes)
        resultados_activos = {}
        for cat in ["Estimaciones", "Facturas", "Comprobantes de Pago", "Pólizas"]:
            if st.session_state.historial.get(cat):
                if cat == "Pólizas":
                    df_dev, df_pag, xls = generador_excel.reporte_polizas(st.session_state.historial[cat])
                    resultados_activos[cat] = {"df_dev": df_dev, "df_pag": df_pag, "xls": xls}
                elif cat == "Estimaciones":
                    df, xls = generador_excel.reporte_estimaciones(st.session_state.historial[cat])
                    resultados_activos[cat] = {"df": df, "xls": xls}
                elif cat == "Facturas":
                    df, xls = generador_excel.reporte_facturas(st.session_state.historial[cat])
                    resultados_activos[cat] = {"df": df, "xls": xls}
                elif cat == "Comprobantes de Pago":
                    df, xls = generador_excel.reporte_comprobantes(st.session_state.historial[cat])
                    resultados_activos[cat] = {"df": df, "xls": xls}

        if resultados_activos:
            st.markdown("---")
            tabs_names = list(resultados_activos.keys())
            tabs_objetos = st.tabs([f"📊 {t}" for t in tabs_names])
            for i, nombre in enumerate(tabs_names):
                with tabs_objetos[i]:
                    st.download_button(f"📥 Descargar {nombre}", data=resultados_activos[nombre]["xls"], file_name=f"Reporte_{nombre}.xlsx", key=f"btn_{nombre}")
                    if nombre == "Pólizas":
                        utilidades_ui.renderizar_tabla_html(resultados_activos[nombre]["df_dev"], "Pólizas Devengo")
                        utilidades_ui.renderizar_tabla_html(resultados_activos[nombre]["df_pag"], "Pólizas Pago")
                    else:
                        utilidades_ui.renderizar_tabla_html(resultados_activos[nombre]["df"], nombre)

    # ------------------ PÁGINAS: PPP, ADJ, CNT, ETR (Cerebro Inteligente) ------------------
    else:
        st.markdown(f"### Etapa: {estructura_expediente[pagina_actual]['nombre']}")
        
        key_raiz = estructura_expediente[pagina_actual]["key_raiz"]
        archivos_etapa = archivos_subidos.get(key_raiz, [])
        
        if archivos_etapa:
            # Diccionario para encontrar fácilmente el objeto archivo por su nombre
            dict_archivos = {f.name: f for f in archivos_etapa}
            seleccionados_nombres = st.multiselect("📄 Seleccione los archivos a clasificar y analizar:", options=list(dict_archivos.keys()))
            
            if st.button("🚀 Iniciar Análisis Inteligente", type="primary") and seleccionados_nombres:
                zona_mensajes = st.empty()
                exitos, omitidos, no_encontrados, sin_funcion = 0, 0, 0, 0
                
                with st.spinner(f"🤖 Consultando diccionario y extrayendo datos para {len(seleccionados_nombres)} archivo(s)..."):
                    for nombre in seleccionados_nombres:
                        archivo = dict_archivos[nombre]
                        
                        # 1. Consultamos el Excel
                        concepto = utilidades_ui.consultar_diccionario(nombre, st.session_state.procedimiento)
                        
                        if not concepto:
                            no_encontrados += 1
                            continue
                            
                        # 2. Buscador Flexible (Fuzzy Match)
                        func_extraccion = None
                        concepto_agrupador = None # Para que todos los contratos se vayan a la misma pestaña
                        
                        # Recorremos nuestro mapa buscando coincidencias parciales
                        for palabra_clave, funcion in mapa_funciones_inteligentes.items():
                            if palabra_clave in concepto: # Ej: ¿"CONTRATO" está dentro de "LOS CONTRATOS DE OBRA"?
                                func_extraccion = funcion
                                concepto_agrupador = palabra_clave 
                                break
                        
                        if not func_extraccion:
                            st.error(f"🛑 No hay IA programada para: '{concepto}'.")
                            sin_funcion += 1
                            continue
                            
                        # 3. Procesamos (usamos el concepto_agrupador para crear una sola pestaña limpia)
                        procesados, hubo_error = procesar_lote_documentos([archivo], concepto_agrupador, func_extraccion)
                            
        

                # Resumen de operaciones
                with zona_mensajes.container():
                    if exitos > 0: st.success(f"✅ ¡Se analizaron y clasificaron {exitos} documento(s) exitosamente!")
                    if no_encontrados > 0: st.warning(f"⚠️ {no_encontrados} archivo(s) no coincidieron con ningún código del Excel.")
                    if sin_funcion > 0: st.warning(f"🚧 {sin_funcion} archivo(s) fueron identificados, pero su módulo de IA aún está en desarrollo.")
                    if omitidos > 0 and exitos == 0: st.info("ℹ️ Los documentos seleccionados ya estaban en la memoria.")

        else:
            st.warning(f"⚠️ No hay documentos cargados en la carpeta de {pagina_actual}.")
            
        # ==========================================
        # RENDERIZAR TABLAS DINÁMICAS (Historial Permanente)
        # ==========================================
        # ⚠️ IMPORTANTE: Este bloque ahora está FUERA del 'if archivos_etapa', 
        # por lo que se mostrará el historial aunque el usuario borre los archivos del panel lateral.
        
        # 1. Filtramos conceptos: Mostrar los que pertenezcan a esta página basándonos en la nomenclatura (ej. "CNT")
        conceptos_de_esta_pagina = []
        for c in st.session_state.historial.keys():
            if c not in ["Estimaciones", "Facturas", "Comprobantes de Pago", "Pólizas"] and st.session_state.historial[c]:
                
                # Buscamos si el nombre del archivo origen contiene la clave de la página actual (ej. "CNT" o "ETR")
                docs_aqui = [doc for doc in st.session_state.historial[c] if pagina_actual in str(doc.get('Archivo Origen', '')).upper()]
                
                if docs_aqui:
                    conceptos_de_esta_pagina.append(c)
        
        # 2. Renderizar la UI
        if conceptos_de_esta_pagina:
            st.markdown("---")
            tabs_objetos = st.tabs([f"📊 {c}" for c in conceptos_de_esta_pagina])
            
            for i, concepto in enumerate(conceptos_de_esta_pagina):
                with tabs_objetos[i]:
                    # Filtramos de nuevo para pintar solo los documentos correctos en la pestaña correcta
                    docs_a_mostrar = [doc for doc in st.session_state.historial[concepto] if pagina_actual in str(doc.get('Archivo Origen', '')).upper()]
                    
                    if concepto == "CONTRATO":
                        for documento in docs_a_mostrar:
                            utilidades_ui.renderizar_reporte_contrato(documento)
                    else:
                        import pandas as pd
                        df_temp = pd.DataFrame(docs_a_mostrar)
                        utilidades_ui.renderizar_tabla_html(df_temp, concepto)

if __name__ == "__main__":
    main()