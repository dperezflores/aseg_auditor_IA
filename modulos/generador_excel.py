import pandas as pd
import io
import base64
import re


COLUMNAS_ESTIMACIONES = [
    "Numero de estimación",
    "Fecha de elaboración o de estimación",
    "De (Periodo de ejecución)",
    "Hasta (Periodo de ejecución)",
    "Importe sin IVA",
    "IVA",
    "Importe con IVA",
    "Importe de anticipo",
    "Amortización",
    "Deducciones",
    "Sancion",
    "Retencion",
    "Alcance neto",
    "Archivo Origen",
]

COLUMNAS_FACTURAS = [
    "Folio",
    "Descripción",
    "Fecha",
    "Monto total",
    "Archivo Origen",
]

COLUMNAS_COMPROBANTES = [
    "Número",
    "Fecha de pago",
    "Importe",
    "Cuenta bancaria emisora",
    "Clave de rastreo",
    "Institución emisora",
    "Institución receptora",
    "Cuenta beneficiaria",
    "Archivo Origen",
]

COLUMNAS_POLIZAS_DEVENGO = [
    "Numero de estimacion", "Cuenta contable del devengado", "Número (Devengo)",
    "Fecha (Devengo)", "Importe (Devengo)", "Fuente de financiamiento", "Archivo Origen",
]

COLUMNAS_POLIZAS_PAGO = [
    "Numero de estimacion", "Número (Pago)", "Fecha (Pago)", "Importe (Pago)", "Archivo Origen",
]


def _ordenar_columnas(df, columnas_esperadas):
    """Impone el orden institucional sin depender del orden de JSONB."""
    for columna in columnas_esperadas:
        if columna not in df.columns:
            df[columna] = None

    columnas_finales = ["Archivo Origen"]
    principales = [
        columna
        for columna in columnas_esperadas
        if columna not in columnas_finales
    ]
    finales_presentes = [
        columna for columna in columnas_finales if columna in df.columns
    ]
    # Los campos inesperados de una respuesta de IA no deben alterar el papel
    # de trabajo institucional. Se conservan en el análisis original, pero no
    # se agregan como columnas nuevas al reporte consolidado.
    return df[principales + finales_presentes].copy()

def _limpiar_numeros(df, columnas):
    for col in columnas:
        if col in df.columns:
            df[col] = df[col].astype(str).replace(r'[\$,]', '', regex=True)
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    return df

def _limpiar_fechas(df):
    cols_fecha = [c for c in df.columns if "Fecha" in c or "Periodo" in c]
    for col in cols_fecha:
        df[col] = pd.to_datetime(df[col], errors='coerce')
    return df


def _orden_natural(valor):
    numeros = re.findall(r"\d+", str(valor or ""))
    return int(numeros[-1]) if numeros else 10**9


def _ordenar_por_fecha(df, fecha, consecutivo=None):
    if df.empty or fecha not in df.columns:
        return df.reset_index(drop=True)
    columnas = [fecha]
    if consecutivo and consecutivo in df.columns:
        df = df.copy()
        df["__orden_natural"] = df[consecutivo].map(_orden_natural)
        columnas.append("__orden_natural")
    df = df.sort_values(columnas, ascending=True, na_position="last", kind="stable")
    return df.drop(columns=["__orden_natural"], errors="ignore").reset_index(drop=True)

def reporte_estimaciones(datos):
    df = pd.DataFrame(datos)
    df = _limpiar_numeros(df, ["Importe sin IVA", "IVA", "Importe con IVA", "Importe de anticipo", "Amortización", "Deducciones", "Sancion", "Retencion"])
    df = _limpiar_fechas(df)
    
    if "Importe con IVA" in df.columns:
        df["Alcance neto"] = df["Importe con IVA"] - df.get("Amortización",0) - df.get("Deducciones",0) - df.get("Sancion",0) - df.get("Retencion",0)
    
    df = _ordenar_por_fecha(df, "Fecha de elaboración o de estimación", "Numero de estimación")
    df = df.map(lambda x: x.upper() if isinstance(x, str) else x)
    df = _ordenar_columnas(df, COLUMNAS_ESTIMACIONES)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter', datetime_format='dd-mmm-yyyy') as writer:
        df.to_excel(writer, index=False, sheet_name='Estimaciones')
        worksheet = writer.sheets['Estimaciones']
        f_moneda = writer.book.add_format({'num_format': '"$"#,##0.00'})
        f_fecha = writer.book.add_format({'num_format': '[$-es-MX]dd-mmm-yyyy;@'})
        
        for i, col in enumerate(df.columns):
            if col in ["Importe sin IVA", "IVA", "Importe con IVA", "Importe de anticipo", "Amortización", "Deducciones", "Sancion", "Retencion", "Alcance neto"]:
                worksheet.set_column(i, i, 16, f_moneda)
            elif "Fecha" in col or "Periodo" in col:
                worksheet.set_column(i, i, 16, f_fecha)
            else:
                worksheet.set_column(i, i, 20)
    
    return df, output.getvalue()

def reporte_facturas(datos):
    df = pd.DataFrame(datos)
    df = _limpiar_numeros(df, ["Monto total"])
    df = _limpiar_fechas(df)
    df = _ordenar_por_fecha(df, "Fecha", "Folio")
    total_monto = df["Monto total"].sum()
    
    if 'Orden de estimacion' in df.columns:
        df = df.drop(columns=['Orden de estimacion'])
    df = df.map(lambda x: x.upper() if isinstance(x, str) else x)
    df = _ordenar_columnas(df, COLUMNAS_FACTURAS)

    fila_total = {col: "" for col in df.columns}
    fila_total["Descripción"] = "TOTAL CONSOLIDADO"
    fila_total["Monto total"] = total_monto
    df_web = pd.concat([df, pd.DataFrame([fila_total])], ignore_index=True)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter', datetime_format='dd-mmm-yyyy') as writer:
        df.to_excel(writer, index=False, sheet_name='Facturas')
        worksheet = writer.sheets['Facturas']
        f_moneda = writer.book.add_format({'num_format': '"$"#,##0.00'})
        f_total = writer.book.add_format({'bold': True, 'bg_color': '#F2F2F2', 'num_format': '"$"#,##0.00', 'top': 2})
        f_label = writer.book.add_format({'bold': True, 'bg_color': '#F2F2F2', 'align': 'right', 'top': 2})
        
        for i, col in enumerate(df.columns):
            worksheet.set_column(i, i, 20)
            if col == "Monto total":
                worksheet.set_column(i, i, 20, f_moneda)
        
        worksheet.write(len(df) + 1, df.columns.get_loc("Monto total") - 1, "TOTAL:", f_label)
        worksheet.write(len(df) + 1, df.columns.get_loc("Monto total"), total_monto, f_total)
        
    return df_web, output.getvalue()

def reporte_comprobantes(datos):
    df = pd.DataFrame(datos)
    df = _limpiar_numeros(df, ["Importe"])
    df = _limpiar_fechas(df)
    df = _ordenar_por_fecha(df, "Fecha de pago", "Número")
    df = df.map(lambda x: x.upper() if isinstance(x, str) else x)
    df = _ordenar_columnas(df, COLUMNAS_COMPROBANTES)
    
    total_importe = df["Importe"].sum()
    fila_total = {col: "" for col in df.columns}
    fila_total["Número"] = "TOTAL CONSOLIDADO"
    fila_total["Importe"] = total_importe
    df_web = pd.concat([df, pd.DataFrame([fila_total])], ignore_index=True)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter', datetime_format='dd-mmm-yyyy') as writer:
        df.to_excel(writer, index=False, sheet_name='Comprobantes')
        worksheet = writer.sheets['Comprobantes']
        f_cont = writer.book.add_format({'num_format': '_-$* #,##0.00_-;-$* #,##0.00_-;_-$* "-"??_-;_-@_-'})
        f_fecha = writer.book.add_format({'num_format': '[$-es-MX]dd-mmm-yyyy;@'})
        f_total = writer.book.add_format({'bold': True, 'bg_color': '#FF5E12', 'font_color': 'white', 'num_format': '_-$* #,##0.00_-;-$* #,##0.00_-;_-$* "-"??_-;_-@_-'})

        for i, col in enumerate(df.columns):
            if col == "Importe":
                worksheet.set_column(i, i, 16, f_cont)
                worksheet.write(len(df)+1, i, total_importe, f_total)
            elif "Fecha" in col:
                worksheet.set_column(i, i, 16, f_fecha)
            else:
                worksheet.set_column(i, i, 20)
                if col == "Número":
                    worksheet.write(len(df)+1, i, "TOTAL CONSOLIDADO", f_total)
                    
    return df_web, output.getvalue()

def reporte_polizas(datos):
    df_raw = pd.DataFrame(datos)
    
    # 1. Blindaje contra columnas faltantes
    cols_esperadas = ["Tipo de poliza", "Cuenta contable", "Numero de estimacion", "Numero de poliza", "Fecha", "Importe", "Fuente de financiamiento"]
    for col in cols_esperadas:
        if col not in df_raw.columns:
            df_raw[col] = ""

    df_raw['Tipo de poliza'] = df_raw['Tipo de poliza'].astype(str).str.upper().str.strip()

    df_dev = df_raw[df_raw['Tipo de poliza'].str.contains('DEVENGO', na=False)].copy()
    df_pag = df_raw[df_raw['Tipo de poliza'].str.contains('PAGO', na=False)].copy()

    df_dev = df_dev.rename(columns={'Cuenta contable': 'Cuenta contable del devengado', 'Numero de poliza': 'Número (Devengo)', 'Fecha': 'Fecha (Devengo)', 'Importe': 'Importe (Devengo)'})
    df_dev = _ordenar_columnas(df_dev, COLUMNAS_POLIZAS_DEVENGO)
    
    df_pag = df_pag.rename(columns={'Numero de poliza': 'Número (Pago)', 'Fecha': 'Fecha (Pago)', 'Importe': 'Importe (Pago)'})
    df_pag = _ordenar_columnas(df_pag, COLUMNAS_POLIZAS_PAGO)

    df_dev = _limpiar_numeros(df_dev, ['Importe (Devengo)'])
    df_dev = _limpiar_fechas(df_dev)
    df_pag = _limpiar_numeros(df_pag, ['Importe (Pago)'])
    df_pag = _limpiar_fechas(df_pag)

    if not df_dev.empty:
        df_dev = _ordenar_por_fecha(df_dev, "Fecha (Devengo)", "Numero de estimacion")
        t_dev = df_dev['Importe (Devengo)'].sum()
        fila = {c: '' for c in df_dev.columns}
        fila['Número (Devengo)'] = 'TOTAL'
        fila['Importe (Devengo)'] = t_dev
        df_dev = pd.concat([df_dev, pd.DataFrame([fila])], ignore_index=True)

    if not df_pag.empty:
        df_pag = _ordenar_por_fecha(df_pag, "Fecha (Pago)", "Numero de estimacion")
        t_pag = df_pag['Importe (Pago)'].sum()
        fila = {c: '' for c in df_pag.columns}
        fila['Número (Pago)'] = 'TOTAL'
        fila['Importe (Pago)'] = t_pag
        df_pag = pd.concat([df_pag, pd.DataFrame([fila])], ignore_index=True)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter', datetime_format='dd-mmm-yyyy') as writer:
        df_dev.to_excel(writer, index=False, sheet_name='Devengo')
        df_pag.to_excel(writer, index=False, sheet_name='Pago')
        f_moneda = writer.book.add_format({'num_format': '"$"#,##0.00'})
        f_fecha = writer.book.add_format({'num_format': '[$-es-MX]dd-mmm-yyyy;@'})

        for sheet, df, imp_col, fec_col in [('Devengo', df_dev, 'Importe (Devengo)', 'Fecha (Devengo)'), ('Pago', df_pag, 'Importe (Pago)', 'Fecha (Pago)')]:
            if df.empty: continue
            ws = writer.sheets[sheet]
            for i, col in enumerate(df.columns):
                if col == imp_col: ws.set_column(i, i, 18, f_moneda)
                elif col == fec_col: ws.set_column(i, i, 16, f_fecha)
                else: ws.set_column(i, i, 25)

    return df_dev, df_pag, output.getvalue()
