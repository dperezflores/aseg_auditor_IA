import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import json
import os
import hashlib


# ==========================================
# 💾 SISTEMA DE CACHÉ EN DISCO
# ==========================================
ARCHIVO_CACHE = "cache_app.json"

def cargar_cache():
    historial_base = {
        "Estimaciones": [], 
        "Facturas": [], 
        "Comprobantes de Pago": [], 
        "Pólizas": []
    }
    archivos_procesados = set()

    if os.path.exists(ARCHIVO_CACHE):
        try:
            with open(ARCHIVO_CACHE, "r", encoding="utf-8") as f:
                datos = json.load(f)
                historial_cargado = datos.get("historial", {})
                archivos_procesados = set(datos.get("archivos_procesados", []))
                
                # MIGRACIÓN: Si el caché viejo dice "Comprobantes", lo reparamos
                if "Comprobantes" in historial_cargado:
                    historial_base["Comprobantes de Pago"] = historial_cargado.pop("Comprobantes")
                
                historial_base.update(historial_cargado)
        except: 
            pass
            
    return historial_base, archivos_procesados

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
    st.session_state.historial = {
        "Estimaciones": [], 
        "Facturas": [], 
        "Comprobantes de Pago": [], 
        "Pólizas": []
    }
    st.session_state.archivos_procesados = set()
    st.rerun()

def generar_huella_archivo(archivo_bytes):
    """Genera una huella digital única (MD5) basada en el contenido del archivo."""
    contenido = archivo_bytes.read()
    archivo_bytes.seek(0) # ⚠️ MUY IMPORTANTE: Regresar el "cursor" al inicio para que la IA pueda leer el PDF después
    return hashlib.md5(contenido).hexdigest()

# ==========================================
# 🎨 UTILIDADES VISUALES Y RENDERIZADO
# ==========================================
def cargar_css(archivo_css):
    try:
        with open(archivo_css, encoding="utf-8") as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
    except: pass

def msg_ayuda(texto): 
    st.markdown(f"<p style='color:#362D32; font-size:13.5px; margin-bottom:10px;'>{texto}</p>", unsafe_allow_html=True)

def renderizar_tabla_html(df, tipo_reporte):
    if df.empty: return

    # Mover "Archivo Origen" al final
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
        "Comprobantes de Pago": "Reporte Consolidado de Comprobantes de Pago",
        "Pólizas Devengo": "Análisis de Pólizas - DEVENGO",
        "Pólizas Pago": "Análisis de Pólizas - PAGO"
    }
    titulo_texto = titulos.get(tipo_reporte, f"Reporte de {tipo_reporte}")

    header_html = f"""
    <div style="padding: 1px 20px; margin-bottom: 15px; margin-top: 10px; background-color: white; border: 1px solid #EAEAEA; box-shadow: inset 8px 0 0 0 #FF5E12, 0 2px 5px rgba(0,0,0,0.05); border-radius: 0px; text-align: center;">
        <h2 style="color: #00304F; margin: 0; font-family: Arial, sans-serif; font-size: 0.8rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.5px;">{titulo_texto}</h2>
    </div>
    """
    st.markdown(header_html, unsafe_allow_html=True)

    html_completo = f"""
    <html>
    <head>
    <style>
        ::-webkit-scrollbar {{ width: 8px; height: 10px; }}
        ::-webkit-scrollbar-track {{ background: #f1f1f1; border-radius: 4px; }}
        ::-webkit-scrollbar-thumb {{ background: #c1c1c1; border-radius: 4px; }}
        ::-webkit-scrollbar-thumb:hover {{ background: #a8a8a8; }}
        body {{ font-family: Arial, sans-serif; margin: 0; padding: 0; background: transparent; }}
        .table-wrapper {{ max-height: 450px; overflow-y: auto; overflow-x: auto; border: 1px solid #D6D6D6; border-radius: 6px; box-shadow: 0 2px 6px rgba(0,0,0,0.05); }}
        table {{ width: 100%; border-collapse: collapse; font-size: 11px; text-align: center; white-space: nowrap; }}
        th {{ background-color: #00304F !important; color: white !important; padding: 10px; border-bottom: 4px solid #FF5E12 !important; text-transform: uppercase; position: sticky; top: 0; z-index: 10; }}
        td {{ padding: 10px; border: 1px solid #D6D6D6; text-align: center; }}
        tr:nth-child(even) {{ background-color: #F9F9F9; }}
    </style>
    </head>
    <body>
        <div class="table-wrapper">{html_table}</div>
    </body>
    </html>
    """
    # --- CÁLCULO DE ALTURA DINÁMICA ---
    # Calculamos cuántas filas hay en total (+1 por la cabecera azul oscura)
    filas_totales = len(df) + 1 
    
    # Asignamos ~40 píxeles por fila + 25px de margen inferior.
    # El 'min(480, ...)' asegura que si la tabla es gigante, no pase de 480px y active la barra de scroll.
    alto_dinamico = min(480, (filas_totales * 40) + 25)
    
    components.html(html_completo, height=alto_dinamico, scrolling=False)


@st.cache_data
def consultar_diccionario(nombre_archivo, procedimiento, ruta_excel="configuracion/diccionario_documentos.xlsx"):
    """Busca el código en el nombre del archivo y devuelve el Concepto desde el Excel."""
    if not os.path.exists(ruta_excel):
        st.error(f"❌ No se encontró el archivo de diccionario en: {ruta_excel}")
        return None
        
    try:
        hoja = procedimiento[:3] 
        df = pd.read_excel(ruta_excel, sheet_name=hoja)
        
        # --- MAGIA ANTIFALLOS PARA LAS COLUMNAS ---
        # 1. Quitamos espacios invisibles al inicio y al final (ej. "Código " -> "Código")
        df.columns = df.columns.str.strip()
        
        # 2. Creamos una lista virtual de columnas en MAYÚSCULAS y SIN ACENTOS solo para buscar
        columnas_buscar = df.columns.str.upper().str.replace('Ó', 'O')
        
        # 3. Comprobamos si existen usando nuestra lista virtual segura
        if 'CODIGO' not in columnas_buscar or 'CONCEPTO' not in columnas_buscar:
            # Si falla, le mostramos al usuario exactamente qué está leyendo Python para poder corregirlo
            st.error(f"❌ Revisar nombres de columnas en hoja '{hoja}'. Python detectó exactamente esto: {list(df.columns)}")
            return None
            
        # 4. Si las encontró, recuperamos el nombre real que tienen en el Excel
        col_codigo = df.columns[columnas_buscar == 'CODIGO'][0]
        col_concepto = df.columns[columnas_buscar == 'CONCEPTO'][0]
            
        # --- BÚSQUEDA DEL ARCHIVO ---
        for _, fila in df.iterrows():
            codigo = str(fila[col_codigo]).strip()
            if codigo and codigo != "nan" and codigo in nombre_archivo:
                return str(fila[col_concepto]).strip().upper() # Devuelve ej: "CONTRATO"
                
        return None # Si no encontró ningún código coincidente
    except Exception as e:
        st.error(f"❌ Error al intentar leer la hoja '{hoja}' del Excel: {e}")
        return None
    
def renderizar_reporte_contrato(datos_completos):
    """Renderiza el diseño exacto de Colab para los contratos dentro de Streamlit."""
    import pandas as pd
    
    # Extraemos las partes
    diccionario_datos = datos_completos.get('datos', {})
    texto_ia_conclusion = datos_completos.get('conclusion', '')
    procedimientos_ia = datos_completos.get('procedimientos', {'p1': '', 'p2': ''})
    nombre_archivo = datos_completos.get('Archivo Origen', 'Documento Desconocido')

    # --- 1. DATOS DE LA TABLA PRINCIPAL ---
    df_datos = pd.DataFrame({
        "Concepto": list(diccionario_datos.keys()),
        "Detalle": list(diccionario_datos.values())
    })

    # --- 2. DATOS DE LA CONCLUSIÓN ---
    df_conclusion = pd.DataFrame({"CONCLUSIÓN DEL ANÁLISIS (IA)": [texto_ia_conclusion]})

    # --- 3. DATOS DE PROCEDIMIENTO ---
    df_proc = pd.DataFrame({
        "Procedimiento": [
            "1. Verificar que el documento este firmado por todas las partes.",
            "2. Verificar que se haya formulado con la legislación aplicable de acuerdo a su objeto y fuente de financiamiento."
        ],
        "Detalle": [procedimientos_ia.get('p1',''), procedimientos_ia.get('p2','')]
    })

    # --- ESTILOS EXACTOS DE COLAB ---
    estilo_tabla = df_datos.style.set_properties(**{
        'text-align': 'left', 'border': '1px solid #D6D6D6', 'padding': '10px', 'font-family': 'Arial'
    }).set_table_styles([
        {'selector': 'th', 'props': [('background-color', '#00304F'), ('color', 'white'), ('text-align', 'center'), ('border-bottom', '4px solid #FF5E12')]},
        {'selector': 'td.col0', 'props': [('font-weight', 'bold'), ('background-color', '#F8F9FA'), ('width', '350px')]}
    ]).hide(axis='index')

    estilo_conclusion = df_conclusion.style.set_properties(**{
        'text-align': 'justify', 'padding': '20px', 'font-family': 'Arial', 'line-height': '1.6', 'background-color': '#FFF5F2'
    }).set_table_styles([
        {'selector': 'th', 'props': [('background-color', '#00304F'), ('color', 'white'), ('text-align', 'center'), ('border-bottom', '4px solid #FF5E12'), ('font-size', '16px')]}
    ]).hide(axis='index')

    def resaltar_resultado(val):
        color = '#28a745' if val == 'OK' else '#dc3545'
        weight = 'bold'
        return f'color: {color}; font-weight: {weight};'

    # Usamos .map en lugar de .applymap para versiones modernas de Pandas, pero funciona igual
    estilo_proc = df_proc.style.set_properties(**{
        'text-align': 'left', 'border': '1px solid #D6D6D6', 'padding': '10px', 'font-family': 'Arial'
    }).set_table_styles([
        {'selector': 'th', 'props': [('background-color', '#00304F'), ('color', 'white'), ('text-align', 'center'), ('border-bottom', '4px solid #FF5E12')]},
        {'selector': 'td.col0', 'props': [('font-weight', 'bold'), ('width', '450px')]}
    ]).map(resaltar_resultado, subset=['Detalle']).hide(axis='index')

    # --- 5. RENDERIZADO EN STREAMLIT ---
    header_html = f"""
    <div style="border-left: 10px solid #FF5E12; padding: 10px 20px; margin-bottom: 20px; margin-top: 30px; background-color: white; box-shadow: 0 2px 5px #D6D6D6; border-radius: 5px;">
        <h2 style="color: #00304F; margin: 0; font-size: 1.5rem;">ASEG - Auditoría de Obra Pública</h2>
        <p style="color: #362D32; margin: 0; font-weight: bold;">Análisis de contrato: <span style="color: #FF5E12;">{nombre_archivo}</span></p>
    </div>
    """
    
    st.markdown(header_html, unsafe_allow_html=True)
    st.markdown(estilo_tabla.to_html(), unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(estilo_conclusion.to_html(), unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(estilo_proc.to_html(), unsafe_allow_html=True)
    st.markdown("<hr style='margin-top: 40px; margin-bottom: 40px;'>", unsafe_allow_html=True)