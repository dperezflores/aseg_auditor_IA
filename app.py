import streamlit as st
from modulos import extraccion, generador_excel, utilidades_ui

st.set_page_config(page_title="ASEG - Auditoría", page_icon="🏗️", layout="wide", initial_sidebar_state="collapsed")

# 1. Cargar Estilos y Caché
utilidades_ui.cargar_css("estilos.css")

if "historial" not in st.session_state:
    hist, procesados = utilidades_ui.cargar_cache()
    st.session_state.historial = hist
    st.session_state.archivos_procesados = procesados

# ==========================================
# ⚙️ MOTOR DE PROCESAMIENTO
# ==========================================
def procesar_lote_documentos(archivos, categoria, funcion_extraccion):
    pendientes = []
    for f in archivos:
        huella_cruda = utilidades_ui.generar_huella_archivo(f)
        huella_carpeta = f"{categoria}_{huella_cruda}"
        
        if huella_carpeta not in st.session_state.archivos_procesados:
            pendientes.append((f, huella_carpeta))
    
    if not pendientes: 
        return 0, False # Retorna 0 procesados y Falso (0 errores)
    
    hubo_error = False # Variable para rastrear si la API falló
    bar = st.progress(0, text=f"Procesando {categoria}...")
    
    for i, (arch, huella_carpeta) in enumerate(pendientes):
        datos = funcion_extraccion(arch)
        
        # --- 🛡️ ESCUDO ANTI-ERRORES DE API ---
        if datos and isinstance(datos, list) and "Error" in datos[0]:
            st.error(f"❌ Error de IA/API en el archivo '{arch.name}': {datos[0]['Error']}")
            hubo_error = True
            continue 
        # --------------------------------------

        for d in datos: d["Archivo Origen"] = arch.name
        
        st.session_state.historial[categoria].extend(datos)
        st.session_state.archivos_procesados.add(huella_carpeta) 
        utilidades_ui.guardar_cache(st.session_state.historial, st.session_state.archivos_procesados)
        bar.progress((i+1)/len(pendientes))
        
    bar.empty() 
    return len(pendientes), hubo_error

def main():
    config_archivos = {
        "Estimaciones": {"key": "up_est", "func": extraccion.procesar_estimaciones},
        "Facturas": {"key": "up_fac", "func": extraccion.procesar_facturas},
        "Comprobantes de Pago": {"key": "up_com", "func": extraccion.procesar_comprobantes},
        "Pólizas": {"key": "up_pol", "func": extraccion.procesar_polizas}
    }
    
    archivos_subidos = {}

    # ==========================================
    # BARRA LATERAL
    # ==========================================
    with st.sidebar:
        st.header("📂 Carpetas de Trabajo")
        utilidades_ui.msg_ayuda("Despliegue una carpeta para cargar sus documentos.")
        
        if st.button("🗑️ Limpiar Memoria y Caché", use_container_width=True):
            utilidades_ui.limpiar_cache_y_memoria()
            
        st.markdown("---")

        for categoria, config in config_archivos.items():
            with st.expander(f"📂 {categoria}", expanded=False):
                archivos = st.file_uploader(categoria, type=["pdf"], accept_multiple_files=True, key=config["key"], label_visibility="collapsed")
                archivos_subidos[categoria] = archivos
                
                if archivos:
                    for f in archivos: 
                        huella_cruda = utilidades_ui.generar_huella_archivo(f)
                        huella_carpeta = f"{categoria}_{huella_cruda}"
                        
                        estatus = "✅ Listo" if huella_carpeta in st.session_state.archivos_procesados else "⏳ Pendiente"
                        st.markdown(f"<span style='color:#00304F; font-size:12px;'>📄 {f.name} ({estatus})</span>", unsafe_allow_html=True)

    # ==========================================
    # VISTA PRINCIPAL
    # ==========================================
    st.markdown("## Bienvenido al Sistema Inteligente de Extracción")
    
    # --- NUEVA GUÍA PASO A PASO PARA EL USUARIO ---
    st.info("""
    **⚙️ Instrucciones de Uso:**
    1. **📂 Cargar Archivos:** Sube tus documentos PDF en las carpetas correspondientes del panel lateral izquierdo.
    2. **✅ Seleccionar:** Elige en el menú de abajo qué carpetas deseas que la IA analice.
    3. **🚀 Procesar:** Haz clic en "Procesar Documentos Pendientes" para iniciar la extracción de datos.
    4. **📊 Descargar:** Revisa las tablas generadas y descarga tus reportes en formato Excel.
    
    *💡 **Nota:** Tu progreso se autoguarda. Si refrescas la página no perderás los documentos ya analizados.*
    """)
    # ----------------------------------------------
    opciones = list(config_archivos.keys())
    carpetas_sel = st.multiselect("Seleccione la(s) carpeta(s) a procesar:", options=opciones)

    # ==========================================
    # BOTÓN DE PROCESAMIENTO (LA LÓGICA SILENCIOSA)
    # ==========================================
    if st.button("🚀 Procesar Documentos Pendientes", type="primary"):
        if not carpetas_sel:
            st.warning("⚠️ Seleccione al menos una carpeta.")
        else:
            carpetas_vacias = [cat for cat in carpetas_sel if not archivos_subidos.get(cat)]
            
            if carpetas_vacias:
                st.warning(f"⚠️ No hay documentos cargados en: **{', '.join(carpetas_vacias)}**. Por favor, suba archivos a esas carpetas o desmárquelas.")
            else:
                zona_mensajes = st.empty()
                
                carpetas_procesadas = []
                carpetas_omitidas = []
                carpetas_con_error = []
                
                with st.spinner("🤖 Analizando documentos... Guardando en caché en tiempo real."):
                    for categoria in carpetas_sel:
                        procesados, hubo_error = procesar_lote_documentos(archivos_subidos[categoria], categoria, config_archivos[categoria]["func"])
                        
                        if hubo_error:
                            carpetas_con_error.append(categoria)
                        elif procesados == 0:
                            carpetas_omitidas.append(categoria)
                        else:
                            carpetas_procesadas.append(categoria)
                
                # RESULTADOS CONDICIONADOS
                with zona_mensajes.container():
                    if carpetas_procesadas:
                        st.success(f"✅ ¡Procesamiento completado con éxito para: **{', '.join(carpetas_procesadas)}**!")
                        
                    if carpetas_con_error:
                        st.error(f"⚠️ El proceso finalizó, pero hubo errores de conexión con la IA en: **{', '.join(carpetas_con_error)}**. Revise los mensajes rojos arriba.")
                        
                    if carpetas_omitidas and not carpetas_procesadas and not carpetas_con_error:
                        st.info("ℹ️ Todos los documentos seleccionados ya estaban en la memoria. No se analizó nada nuevo para ahorrar API.")

    # ==========================================
    # RENDERIZADO DE RESULTADOS
    # ==========================================
    resultados_activos = {}
    
    if st.session_state.historial["Estimaciones"]:
        df, xls = generador_excel.reporte_estimaciones(st.session_state.historial["Estimaciones"])
        resultados_activos["Estimaciones"] = {"df": df, "xls": xls}
        
    if st.session_state.historial["Facturas"]:
        df, xls = generador_excel.reporte_facturas(st.session_state.historial["Facturas"])
        resultados_activos["Facturas"] = {"df": df, "xls": xls}
        
    if st.session_state.historial["Comprobantes de Pago"]:
        df, xls = generador_excel.reporte_comprobantes(st.session_state.historial["Comprobantes de Pago"])
        resultados_activos["Comprobantes de Pago"] = {"df": df, "xls": xls}
        
    if st.session_state.historial["Pólizas"]:
        df_dev, df_pag, xls = generador_excel.reporte_polizas(st.session_state.historial["Pólizas"])
        resultados_activos["Pólizas"] = {"df_dev": df_dev, "df_pag": df_pag, "xls": xls}

    if resultados_activos:
        st.markdown("---")
        tabs_names = list(resultados_activos.keys())
        tabs_objetos = st.tabs([f"📊 {t}" for t in tabs_names])
        
        for i, nombre in enumerate(tabs_names):
            with tabs_objetos[i]:
                st.markdown("<br>", unsafe_allow_html=True)
                st.download_button(
                    label=f"📥 Descargar {nombre} en Excel", 
                    data=resultados_activos[nombre]["xls"], 
                    file_name=f"Reporte_{nombre.replace(' ', '_')}_ASEG.xlsx", 
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 
                    key=f"btn_top_{nombre}"
                )
                
                if nombre == "Pólizas":
                    utilidades_ui.renderizar_tabla_html(resultados_activos[nombre]["df_dev"], "Pólizas Devengo")
                    utilidades_ui.renderizar_tabla_html(resultados_activos[nombre]["df_pag"], "Pólizas Pago")
                else:
                    utilidades_ui.renderizar_tabla_html(resultados_activos[nombre]["df"], nombre)

if __name__ == "__main__":
    main()