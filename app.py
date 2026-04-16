import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import json
import os
from modulos import extraccion, generador_excel

st.set_page_config(page_title="ASEG - Auditoría", page_icon="🏗️", layout="wide", initial_sidebar_state="collapsed")

# ==========================================
# 💾 1. SISTEMA DE CACHÉ EN DISCO (PERSISTENCIA)
# ==========================================
ARCHIVO_CACHE = "cache_app.json"

def cargar_cache():
    if os.path.exists(ARCHIVO_CACHE):
        try:
            with open(ARCHIVO_CACHE, "r", encoding="utf-8") as f:
                datos = json.load(f)
                return datos["historial"], set(datos["archivos_procesados"])
        except: pass
    return {"Estimaciones": [], "Facturas": [], "Comprobantes": [], "Pólizas": []}, set()

def guardar_cache(historial, archivos_procesados):
    datos = {
        "historial": historial,
        "archivos_procesados": list(archivos_procesados)
    }
    with open(ARCHIVO_CACHE, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=4)

def limpiar_cache_y_memoria():
    if os.path.exists(ARCHIVO_CACHE):
        os.remove(ARCHIVO_CACHE)
    st.session_state.historial = {"Estimaciones": [], "Facturas": [], "Comprobantes": [], "Pólizas": []}
    st.session_state.archivos_procesados = set()
    st.rerun()

if "historial" not in st.session_state:
    hist, procesados = cargar_cache()
    st.session_state.historial = hist
    st.session_state.archivos_procesados = procesados

def cargar_css(archivo_css):
    try:
        with open(archivo_css, encoding="utf-8") as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
    except: pass
cargar_css("estilos.css")

def msg_ayuda(texto): 
    st.markdown(f"<p style='color:#362D32; font-size:13.5px; margin-bottom:10px;'>{texto}</p>", unsafe_allow_html=True)

# ==========================================
# 🎨 2. RENDERIZADO VISUAL PERFECTO
# ==========================================
def renderizar_tabla_html(df, tipo_reporte):
    # MOVER "ARCHIVO ORIGEN" AL FINAL
    if "Archivo Origen" in df.columns:
        columnas = [c for c in df.columns if c != "Archivo Origen"] + ["Archivo Origen"]
        df = df[columnas].copy()

    meses = {1:'ene', 2:'feb', 3:'mar', 4:'abr', 5:'may', 6:'jun', 7:'jul', 8:'ago', 9:'sep', 10:'oct', 11:'nov', 12:'dic'}
    def fmt_fec(d):
        if pd.isnull(d) or not hasattr(d, 'year') or d.year <= 1900: return ''
        return f"{d.day:02d}-{meses[d.month]}-{d.year}"

    cols_moneda = [c for c in df.columns if c in ["Importe sin IVA", "IVA", "Importe con IVA", "Importe de anticipo", "Amortización", "Deducciones", "Sancion", "Retencion", "Alcance neto", "Monto total", "Importe", "Importe (Devengo)", "Importe (Pago)"]]
    cols_fecha = [c for c in df.columns if "Fecha" in c or "Periodo" in c]

    formatos = {col: "${:,.2f}" for col in cols_moneda}
    for col in cols_fecha: formatos[col] = fmt_fec

    def highlight_total(row):
        is_total = any(str(val) in ["TOTAL CONSOLIDADO", "TOTAL"] for val in row.values)
        if is_total: return ['font-weight: bold; background-color: #F2F2F2 !important; color: black !important;'] * len(row)
        return [''] * len(row)

    styler = df.style.apply(highlight_total, axis=1).format(formatos, na_rep="").hide(axis='index')
    html_table = styler.to_html()

    titulos = {
        "Estimaciones": "Reporte Consolidado de Estimaciones",
        "Facturas": "Reporte de Facturas",
        "Comprobantes": "Reporte Consolidado de Comprobantes de Pago",
        "Pólizas Devengo": "Análisis de Pólizas (Criterio: Cuenta Mayor y Pago en Bancos) - DEVENGO",
        "Pólizas Pago": "Análisis de Pólizas (Criterio: Cuenta Mayor y Pago en Bancos) - PAGO"
    }
    titulo_texto = titulos.get(tipo_reporte, "Reporte Consolidado")

    # TÍTULO FUERA DEL IFRAME
    header_html = f"""
    <div style="border-left: 10px solid #FF5E12; padding: 10px 20px; margin-bottom: 10px; margin-top: 10px; background-color: white; box-shadow: 0 2px 5px rgba(0,0,0,0.05); border: 1px solid #EAEAEA; border-radius: 4px;">
        <h2 style="color: #00304F; margin: 0; font-family: Arial; font-size: 1.4rem; font-weight: bold;">ASEG - AUDITORÍA DE OBRA PÚBLICA</h2>
        <p style="color: #362D32; margin: 0; font-weight: bold; font-family: Arial; font-size: 13px;">{titulo_texto}</p>
    </div>
    """
    st.markdown(header_html, unsafe_allow_html=True)

    # CONTENEDOR CON BORDE Y BARRAS DE DESPLAZAMIENTO (Sin hover en las filas)
    html_completo = f"""
    <html>
    <head>
    <style>
        ::-webkit-scrollbar {{ width: 8px; height: 10px; }}
        ::-webkit-scrollbar-track {{ background: #f1f1f1; border-radius: 4px; }}
        ::-webkit-scrollbar-thumb {{ background: #c1c1c1; border-radius: 4px; }}
        ::-webkit-scrollbar-thumb:hover {{ background: #a8a8a8; }}

        body {{ font-family: Arial, sans-serif; margin: 0; padding: 0; background: transparent; }}
        
        .table-wrapper {{
            max-height: 450px;       
            overflow-y: auto;
            overflow-x: auto;        
            border: 1px solid #D6D6D6; 
            border-radius: 6px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.05);
        }}

        table {{ width: 100%; border-collapse: collapse; font-size: 11px; text-align: center; white-space: nowrap; }}
        th {{ background-color: #00304F !important; color: white !important; padding: 10px; border-bottom: 4px solid #FF5E12 !important; text-transform: uppercase; position: sticky; top: 0; z-index: 10; }}
        td {{ padding: 10px; border: 1px solid #D6D6D6; text-align: center; }}
        tr:nth-child(even) {{ background-color: #F9F9F9; }}
    </style>
    </head>
    <body>
        <div class="table-wrapper">
            {html_table}
        </div>
    </body>
    </html>
    """
    components.html(html_completo, height=480, scrolling=False)

st.markdown("""
<div class='header-propio'>
    🏗️ ASEG | Sistema Inteligente de Extracción
</div>

<style>
.header-propio{
position:fixed;
top:0;
left:0;
right:0;
height:70px;
background:#00304F;
color:white;
font-size:38px;
font-weight:700;
display:flex;
align-items:center;
padding-left:70px;
z-index:99999;
border-bottom:5px solid #FF5E12;
}
</style>
""", unsafe_allow_html=True)


def main():
    # ==========================================
    # BARRA LATERAL
    # ==========================================
    with st.sidebar:
        st.header("📂 Carpetas de Trabajo")
        msg_ayuda("Despliegue una carpeta para cargar sus documentos.")
        
        if st.button("🗑️ Limpiar Memoria y Caché", use_container_width=True):
            limpiar_cache_y_memoria()
            
        st.markdown("---")

        with st.expander("📂 Estimaciones", expanded=False):
            archivos_est = st.file_uploader("Estimaciones", type=["pdf"], accept_multiple_files=True, key="up_est", label_visibility="collapsed")
            if archivos_est:
                for f in archivos_est: 
                    estatus = "✅ Listo" if f.name in st.session_state.archivos_procesados else "⏳ Pendiente"
                    st.markdown(f"<span style='color:#00304F; font-size:12px;'>📄 {f.name} ({estatus})</span>", unsafe_allow_html=True)

        with st.expander("📂 Facturas", expanded=False):
            archivos_fac = st.file_uploader("Facturas", type=["pdf"], accept_multiple_files=True, key="up_fac", label_visibility="collapsed")
            if archivos_fac:
                for f in archivos_fac: 
                    estatus = "✅ Listo" if f.name in st.session_state.archivos_procesados else "⏳ Pendiente"
                    st.markdown(f"<span style='color:#00304F; font-size:12px;'>📄 {f.name} ({estatus})</span>", unsafe_allow_html=True)

        with st.expander("📂 Comprobantes de Pago", expanded=False):
            archivos_com = st.file_uploader("Comprobantes", type=["pdf"], accept_multiple_files=True, key="up_com", label_visibility="collapsed")
            if archivos_com:
                for f in archivos_com: 
                    estatus = "✅ Listo" if f.name in st.session_state.archivos_procesados else "⏳ Pendiente"
                    st.markdown(f"<span style='color:#00304F; font-size:12px;'>📄 {f.name} ({estatus})</span>", unsafe_allow_html=True)

        with st.expander("📂 Pólizas", expanded=False):
            archivos_pol = st.file_uploader("Pólizas", type=["pdf"], accept_multiple_files=True, key="up_pol", label_visibility="collapsed")
            if archivos_pol:
                for f in archivos_pol: 
                    estatus = "✅ Listo" if f.name in st.session_state.archivos_procesados else "⏳ Pendiente"
                    st.markdown(f"<span style='color:#00304F; font-size:12px;'>📄 {f.name} ({estatus})</span>", unsafe_allow_html=True)

    # ==========================================
    # VISTA PRINCIPAL
    # ==========================================
    st.markdown("## Bienvenido al Sistema Inteligente de Extracción")
    st.info("💡 **El Progreso se Autoguarda:** Si cierras o refrescas la página (F5), no perderás los datos extraídos gracias a la Caché Inteligente. Si deseas detener la extracción, presiona la 'X' en la esquina superior derecha o recarga la página; el sistema recordará todo lo que analizó hasta ese segundo.")

    opciones = ["Estimaciones", "Facturas", "Comprobantes de Pago", "Pólizas"]
    carpetas_sel = st.multiselect("Seleccione la(s) carpeta(s) a procesar (solo analizará los documentos nuevos):", options=opciones)

    if st.button("🚀 Procesar Documentos Pendientes", type="primary"):
        if not carpetas_sel:
            st.warning("⚠️ Seleccione al menos una carpeta.")
        else:
            with st.spinner("🤖 Analizando documentos... Guardando en caché en tiempo real."):
                
                if "Estimaciones" in carpetas_sel and archivos_est:
                    pendientes = [f for f in archivos_est if f.name not in st.session_state.archivos_procesados]
                    if pendientes:
                        bar = st.progress(0, text="Procesando Estimaciones...")
                        for i, arch in enumerate(pendientes):
                            datos = extraccion.procesar_estimaciones(arch)
                            for d in datos: d["Archivo Origen"] = arch.name
                            st.session_state.historial["Estimaciones"].extend(datos)
                            st.session_state.archivos_procesados.add(arch.name)
                            guardar_cache(st.session_state.historial, st.session_state.archivos_procesados)
                            bar.progress((i+1)/len(pendientes))

                if "Facturas" in carpetas_sel and archivos_fac:
                    pendientes = [f for f in archivos_fac if f.name not in st.session_state.archivos_procesados]
                    if pendientes:
                        bar = st.progress(0, text="Procesando Facturas...")
                        for i, arch in enumerate(pendientes):
                            datos = extraccion.procesar_facturas(arch)
                            for d in datos: d["Archivo Origen"] = arch.name
                            st.session_state.historial["Facturas"].extend(datos)
                            st.session_state.archivos_procesados.add(arch.name)
                            guardar_cache(st.session_state.historial, st.session_state.archivos_procesados)
                            bar.progress((i+1)/len(pendientes))

                if "Comprobantes de Pago" in carpetas_sel and archivos_com:
                    pendientes = [f for f in archivos_com if f.name not in st.session_state.archivos_procesados]
                    if pendientes:
                        bar = st.progress(0, text="Procesando Comprobantes...")
                        for i, arch in enumerate(pendientes):
                            datos = extraccion.procesar_comprobantes(arch)
                            for d in datos: d["Archivo Origen"] = arch.name
                            st.session_state.historial["Comprobantes"].extend(datos)
                            st.session_state.archivos_procesados.add(arch.name)
                            guardar_cache(st.session_state.historial, st.session_state.archivos_procesados)
                            bar.progress((i+1)/len(pendientes))

                if "Pólizas" in carpetas_sel and archivos_pol:
                    pendientes = [f for f in archivos_pol if f.name not in st.session_state.archivos_procesados]
                    if pendientes:
                        bar = st.progress(0, text="Procesando Pólizas...")
                        for i, arch in enumerate(pendientes):
                            datos = extraccion.procesar_polizas(arch)
                            for d in datos: d["Archivo Origen"] = arch.name
                            st.session_state.historial["Pólizas"].extend(datos)
                            st.session_state.archivos_procesados.add(arch.name)
                            guardar_cache(st.session_state.historial, st.session_state.archivos_procesados)
                            bar.progress((i+1)/len(pendientes))
                            
            st.success("✅ ¡Procesamiento completado y respaldado en disco!")

    # ==========================================
    # RENDERIZADO CONSTANTE DE RESULTADOS
    # ==========================================
    resultados_activos = {}
    
    if st.session_state.historial["Estimaciones"]:
        df_est, xls_est = generador_excel.reporte_estimaciones(st.session_state.historial["Estimaciones"])
        resultados_activos["Estimaciones"] = {"df": df_est, "xls": xls_est}
        
    if st.session_state.historial["Facturas"]:
        df_fac, xls_fac = generador_excel.reporte_facturas(st.session_state.historial["Facturas"])
        resultados_activos["Facturas"] = {"df": df_fac, "xls": xls_fac}
        
    if st.session_state.historial["Comprobantes"]:
        df_com, xls_com = generador_excel.reporte_comprobantes(st.session_state.historial["Comprobantes"])
        resultados_activos["Comprobantes"] = {"df": df_com, "xls": xls_com}
        
    if st.session_state.historial["Pólizas"]:
        df_dev, df_pag, xls_pol = generador_excel.reporte_polizas(st.session_state.historial["Pólizas"])
        resultados_activos["Pólizas"] = {"df_dev": df_dev, "df_pag": df_pag, "xls": xls_pol}

    if resultados_activos:
        st.markdown("---")
        tabs_names = [k for k in resultados_activos.keys()]
        tabs_objetos = st.tabs([f"📊 {t}" for t in tabs_names])
        
        # --- SOLUCIÓN: BOTÓN DE DESCARGA EN LA PARTE SUPERIOR DE LA PESTAÑA ---
        for i, nombre in enumerate(tabs_names):
            with tabs_objetos[i]:
                # Espaciado sutil
                st.markdown("<br>", unsafe_allow_html=True)
                
                # El botón se renderiza ANTES de la tabla
                st.download_button(
                    label=f"📥 Descargar {nombre} en Excel", 
                    data=resultados_activos[nombre]["xls"], 
                    file_name=f"Reporte_{nombre}_ASEG.xlsx", 
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 
                    key=f"btn_top_{nombre}"
                )
                
                if nombre == "Pólizas":
                    renderizar_tabla_html(resultados_activos[nombre]["df_dev"], "Pólizas Devengo")
                    renderizar_tabla_html(resultados_activos[nombre]["df_pag"], "Pólizas Pago")
                else:
                    renderizar_tabla_html(resultados_activos[nombre]["df"], nombre)

if __name__ == "__main__":
    main()
