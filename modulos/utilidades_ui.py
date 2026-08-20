import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import json
import os
import hashlib
import html

from modulos.esquemas import DatosContrato


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
    
def renderizar_reporte_contrato(datos_completos, al_eliminar=None):
    """Renderiza el diseño exacto de Colab para los contratos dentro de Streamlit."""
    import pandas as pd
    
    # Extraemos las partes
    diccionario_datos = datos_completos.get('datos', {})
    texto_ia_conclusion = datos_completos.get('conclusion', '')
    procedimientos_ia = datos_completos.get('procedimientos', {'p1': '', 'p2': ''})
    nombre_archivo = datos_completos.get('Archivo Origen', 'Documento Desconocido')

    # --- 1. DATOS DE LA TABLA PRINCIPAL ---
    # PostgreSQL JSONB no conserva el orden de las llaves. La interfaz usa
    # siempre el orden declarado en el esquema oficial del contrato.
    orden_solicitado = [
        campo.alias or nombre
        for nombre, campo in DatosContrato.model_fields.items()
    ]
    conceptos = orden_solicitado + [
        concepto
        for concepto in diccionario_datos
        if concepto not in orden_solicitado
    ]
    df_datos = pd.DataFrame({
        "Concepto": conceptos,
        "Detalle": [diccionario_datos.get(concepto, "") for concepto in conceptos]
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
    documento_id = datos_completos.get("_documento_id")
    if al_eliminar and documento_id:
        with st.expander("Eliminar este análisis"):
            confirmar = st.checkbox(
                "Confirmo que deseo eliminar este análisis",
                key=f"confirmar_eliminar_legacy_{documento_id}",
            )
            if st.button("Eliminar análisis", key=f"eliminar_legacy_{documento_id}", disabled=not confirmar):
                al_eliminar(documento_id)
    st.markdown("<hr style='margin-top: 40px; margin-bottom: 40px;'>", unsafe_allow_html=True)


def renderizar_reporte_catalogo(analisis, al_eliminar=None):
    """Muestra una salida auditable y ordenada para cualquier tipo documental."""
    definicion = analisis.get("catalogo", {})
    identificacion = analisis.get("identificacion", {})
    nombre_archivo = html.escape(
        str(analisis.get("Archivo Origen", "Documento desconocido"))
    )
    nombre_documento = html.escape(
        str(definicion.get("nombre_documento", "Análisis documental"))
    )
    clave_catalogo = html.escape(str(definicion.get("clave_catalogo", "Sin clave")))

    st.markdown(
        f"""
        <div style="border-left:10px solid #FF5E12;padding:12px 20px;margin:25px 0 16px;
                    background:white;box-shadow:0 2px 5px #D6D6D6;border-radius:5px;">
            <h2 style="color:#00304F;margin:0;font-size:1.35rem;">{nombre_documento}</h2>
            <p style="margin:4px 0 0;color:#362D32;"><b>{clave_catalogo}</b> · {nombre_archivo}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if definicion.get("configuracion_preliminar"):
        estados = ", ".join(definicion.get("estados_preliminares", []))
        st.warning(
            "Este análisis utiliza campos o procedimientos todavía no aprobados "
            f"({estados}). El resultado es preliminar y requiere revisión humana."
        )

    corresponde = identificacion.get("corresponde", "INDETERMINADO")
    mensaje_identificacion = (
        f"Identificación del documento: {corresponde}. "
        f"{identificacion.get('justificacion', '')}"
    )
    if corresponde == "SI":
        st.success(mensaje_identificacion)
    elif corresponde == "NO":
        st.error(mensaje_identificacion)
    else:
        st.warning(mensaje_identificacion)

    paginas_identificacion = identificacion.get("paginas", [])
    if paginas_identificacion:
        st.caption(
            "Páginas utilizadas para identificar el documento: "
            + ", ".join(map(str, paginas_identificacion))
        )

    datos = analisis.get("datos_extraidos", [])
    if datos:
        st.markdown("#### Datos extraídos")
        df_datos = pd.DataFrame(
            [
                {
                    "Orden": dato.get("orden"),
                    "Campo": dato.get("etiqueta"),
                    "Valor": dato.get("valor"),
                    "Evidencia": dato.get("evidencia"),
                    "Página(s)": ", ".join(map(str, dato.get("paginas", []))) or "—",
                    "Confianza": dato.get("confianza"),
                }
                for dato in datos
            ]
        ).sort_values("Orden")
        tabla_datos = df_datos[["Campo", "Valor", "Evidencia", "Página(s)", "Confianza"]]
        estilo = tabla_datos.style.set_properties(**{
            "text-align": "left", "border": "1px solid #D6D6D6", "padding": "10px", "font-family": "Arial"
        }).set_table_styles([
            {"selector": "th", "props": [("background-color", "#00304F"), ("color", "white"), ("text-align", "center"), ("border-bottom", "4px solid #FF5E12")]},
            {"selector": "td.col0", "props": [("font-weight", "bold"), ("background-color", "#F8F9FA"), ("width", "280px")]},
        ]).hide(axis="index")
        st.markdown(estilo.to_html(), unsafe_allow_html=True)

    procedimientos = analisis.get("procedimientos", [])
    if procedimientos:
        st.markdown("#### Procedimientos de revisión")
        df_procedimientos = pd.DataFrame(
            [
                {
                    "Orden": procedimiento.get("orden"),
                    "Procedimiento": procedimiento.get("procedimiento"),
                    "Resultado": str(procedimiento.get("resultado", "")).replace("_", " "),
                    "Detalle": procedimiento.get("detalle"),
                    "Evidencia": procedimiento.get("evidencia"),
                    "Página(s)": ", ".join(
                        map(str, procedimiento.get("paginas", []))
                    ) or "—",
                    "Riesgo": procedimiento.get("riesgo_codigo"),
                    "Estado de la regla": procedimiento.get(
                        "estado_revision_procedimiento"
                    ),
                }
                for procedimiento in procedimientos
            ]
        ).sort_values("Orden")
        tabla_proc = df_procedimientos.drop(columns=["Orden"])
        estilo_proc = tabla_proc.style.set_properties(**{
            "text-align": "left", "border": "1px solid #D6D6D6", "padding": "10px", "font-family": "Arial"
        }).set_table_styles([
            {"selector": "th", "props": [("background-color", "#00304F"), ("color", "white"), ("text-align", "center"), ("border-bottom", "4px solid #FF5E12")]},
            {"selector": "td.col0", "props": [("font-weight", "bold"), ("width", "360px")]},
        ]).hide(axis="index")
        st.markdown(estilo_proc.to_html(), unsafe_allow_html=True)

    conclusion = html.escape(str(analisis.get("conclusion", "Sin conclusión disponible.")))
    st.markdown(
        f"""
        <table style="width:100%;border-collapse:collapse;margin-top:24px;font-family:Arial;">
          <thead><tr><th style="background:#00304F;color:white;padding:10px;border-bottom:4px solid #FF5E12;">CONCLUSIÓN DEL ANÁLISIS (IA)</th></tr></thead>
          <tbody><tr><td style="padding:18px;border:1px solid #D6D6D6;background:#FFF5F2;line-height:1.6;">{conclusion}</td></tr></tbody>
        </table>
        """,
        unsafe_allow_html=True,
    )

    fundamento = definicion.get("fundamento_normativo")
    if fundamento:
        st.caption(f"Referencia normativa del catálogo: {fundamento}")

    for advertencia in analisis.get("advertencias", []):
        st.warning(str(advertencia))

    documento_id = analisis.get("_documento_id")
    if al_eliminar and documento_id:
        clave_confirmacion = f"confirmar_eliminar_{documento_id}"
        with st.expander("Eliminar este análisis"):
            st.warning("El análisis dejará de mostrarse, pero se conservará una baja auditable en la base de datos.")
            confirmar = st.checkbox("Confirmo que deseo eliminar este análisis", key=clave_confirmacion)
            if st.button("Eliminar análisis", key=f"eliminar_{documento_id}", disabled=not confirmar):
                al_eliminar(documento_id)

    st.markdown("<hr style='margin:35px 0;'>", unsafe_allow_html=True)


def renderizar_conciliacion_expediente(
    conciliacion,
    etapa=None,
    al_analizar=None,
    al_ver_analisis=None,
    documentos_catalogo=None,
    archivos_existentes=None,
):
    """Muestra el control documental sin convertir pendientes en faltantes."""
    resultados = [
        resultado
        for resultado in conciliacion.resultados
        if etapa is None or resultado.documento.etapa == etapa
    ]
    if not resultados:
        st.info("No hay definiciones aprobadas del catálogo para mostrar.")
        return

    encontrados = sum(resultado.estado == "ENCONTRADO" for resultado in resultados)
    faltantes = sum(resultado.estado == "FALTANTE" for resultado in resultados)
    no_aplicables = sum(
        resultado.estado in {"NO_APLICABLE", "NO_REQUERIDO"}
        for resultado in resultados
    )
    pendientes = sum(resultado.estado == "PENDIENTE" for resultado in resultados)
    duplicados = sum(resultado.estado == "DUPLICADO" for resultado in resultados)

    columnas = st.columns(5)
    for columna, etiqueta, valor in zip(
        columnas,
        ["Encontrados", "Faltantes", "No aplicables", "Pendientes", "Duplicados"],
        [encontrados, faltantes, no_aplicables, pendientes, duplicados],
    ):
        columna.metric(etiqueta, valor)

    etiquetas_estado = {
        "ENCONTRADO": "✅ Encontrado",
        "FALTANTE": "❌ Faltante",
        "NO_APLICABLE": "➖ No aplicable",
        "NO_REQUERIDO": "➖ No requerido",
        "PENDIENTE": "⚠️ Pendiente de determinar",
        "DUPLICADO": "🔁 Duplicado",
    }
    etiquetas_aplicabilidad = {
        "APLICA": "Aplica",
        "NO_APLICA": "No aplica",
        "PENDIENTE": "Pendiente",
        "OPCIONAL": "Opcional",
    }
    etiquetas_ia = {
        "SIN_ANALIZAR": "⚪ Sin analizar",
        "PROCESANDO": "🔵 Procesando",
        "CUMPLE": "✅ Cumple",
        "NO_CUMPLE": "❌ No cumple",
        "REVISION_REQUERIDA": "⚠️ Revisión requerida",
        "ERROR": "🔴 Error",
    }
    tabla = pd.DataFrame(
        [
            {
                "Orden": resultado.documento.orden,
                "Etapa": resultado.documento.etapa,
                "Documento": resultado.documento.nombre,
                "Obligatoriedad": resultado.documento.obligatoriedad,
                "Aplicabilidad": etiquetas_aplicabilidad.get(
                    resultado.aplicabilidad,
                    resultado.aplicabilidad,
                ),
                "Estado": etiquetas_estado.get(resultado.estado, resultado.estado),
                "Archivos": ", ".join(
                    archivo.nombre for archivo in resultado.archivos
                ) or "—",
                "Procedimientos aplicables": "\n".join(
                    f"{item.orden}. {item.procedimiento}"
                    for item in resultado.documento.procedimientos
                ) or "Sin procedimientos configurados",
                "Resultado IA": etiquetas_ia.get(
                    resultado.resultado_ia,
                    resultado.resultado_ia,
                ),
                "Acciones": (
                    "Subir · Analizar · Ver análisis"
                    if resultado.archivos
                    else "Subir documento"
                ),
            }
            for resultado in resultados
        ]
    ).sort_values(["Orden"])
    st.dataframe(
        tabla.drop(columns=["Orden"]),
        hide_index=True,
        use_container_width=True,
    )

    if al_analizar or al_ver_analisis:
        st.markdown("#### Acciones del documento")
        por_clave = {
            item.documento.clave_catalogo: item for item in resultados
        }
        clave = st.selectbox(
            "Seleccione un documento",
            list(por_clave),
            format_func=lambda valor: (
                f"{por_clave[valor].documento.nombre} · "
                f"{etiquetas_estado.get(por_clave[valor].estado, por_clave[valor].estado)}"
            ),
            key=f"accion_documento_{etapa or 'TODAS'}",
        )
        seleccionado = por_clave[clave]
        documento = seleccionado.documento
        archivo_nuevo = st.file_uploader(
            "Subir o sustituir documento",
            type=list(documento.extensiones),
            accept_multiple_files=False,
            key=f"accion_upload_{documento.id}",
        )
        columnas_accion = st.columns(4)
        archivo_analisis = archivo_nuevo
        confirmar_inconsistencia = True
        if archivo_nuevo is not None:
            huella = hashlib.sha256(archivo_nuevo.getvalue()).hexdigest()
            duplicado = any(
                item.get("huella") == huella or item.get("nombre") == archivo_nuevo.name
                for item in (archivos_existentes or [])
            )
            if duplicado:
                st.info("Este documento ya está cargado en el expediente. Puede analizarlo sin volver a registrarlo.")
            if documentos_catalogo:
                from modulos import catalogo as catalogo_maestro

                detectado = catalogo_maestro.clasificar_archivo(archivo_nuevo.name, documentos_catalogo)
                if not detectado or detectado.clave_catalogo != documento.clave_catalogo:
                    nombre_detectado = detectado.nombre if detectado else "ningún código conocido"
                    st.warning(
                        f"El nombre del archivo no coincide con {documento.clave_catalogo} · {documento.nombre}. "
                        f"El sistema reconoce: {nombre_detectado}."
                    )
                    confirmar_inconsistencia = st.checkbox(
                        "Estoy seguro de que deseo analizarlo de todas formas",
                        key=f"confirmar_codigo_{documento.id}_{huella[:10]}",
                    )
        if al_analizar:
            etiqueta = (
                "Volver a analizar con IA"
                if seleccionado.resultado_ia not in {"SIN_ANALIZAR", "ERROR"}
                else "Analizar con IA"
            )
            if columnas_accion[0].button(
                etiqueta,
                key=f"analizar_{documento.id}",
                disabled=archivo_analisis is None or not confirmar_inconsistencia,
            ):
                al_analizar(archivo_analisis, documento)
        if al_ver_analisis and columnas_accion[1].button(
            "Ver análisis con IA",
            key=f"ver_analisis_{documento.id}",
            disabled=seleccionado.resultado_ia == "SIN_ANALIZAR",
        ):
            al_ver_analisis(documento)
        with columnas_accion[2].popover("Ver criterios"):
            st.write(documento.criterios_identificacion_ia or "Sin criterios registrados.")
            st.caption(documento.fundamento_normativo or "Sin fundamento registrado.")
        if columnas_accion[3].button(
            "Resolver duplicados",
            key=f"duplicados_{documento.id}",
            disabled=seleccionado.estado != "DUPLICADO",
        ):
            st.info(
                "Conserve el archivo correcto y retire los duplicados desde el panel lateral."
            )
        if archivo_nuevo is None:
            st.caption("Para analizar desde esta tabla, primero seleccione el PDF en 'Subir o sustituir documento'.")

    no_reconocidos = conciliacion.no_reconocidos
    if etapa is not None:
        no_reconocidos = tuple(
            archivo
            for archivo in no_reconocidos
            if archivo.nombre.upper().startswith(f"{etapa}_")
        )
    if no_reconocidos:
        st.warning(
            "Archivos todavía no conciliados con una definición aprobada: "
            + ", ".join(archivo.nombre for archivo in no_reconocidos)
        )
