import pandas as pd
import io
import base64

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

def reporte_estimaciones(datos):
    df = pd.DataFrame(datos)
    df = _limpiar_numeros(df, ["Importe sin IVA", "IVA", "Importe con IVA", "Importe de anticipo", "Amortización", "Deducciones", "Sancion", "Retencion"])
    df = _limpiar_fechas(df)
    
    if "Importe con IVA" in df.columns:
        df["Alcance neto"] = df["Importe con IVA"] - df.get("Amortización",0) - df.get("Deducciones",0) - df.get("Sancion",0) - df.get("Retencion",0)
    
    df = df.sort_values(by="Fecha de elaboración o de estimación", na_position='first').reset_index(drop=True)
    df = df.map(lambda x: x.upper() if isinstance(x, str) else x)

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
    df = df.sort_values(by="Fecha", na_position='first').reset_index(drop=True)
    total_monto = df["Monto total"].sum()
    
    if 'Orden de estimacion' in df.columns:
        df = df.drop(columns=['Orden de estimacion'])
    df = df.map(lambda x: x.upper() if isinstance(x, str) else x)

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
    df = df.sort_values(by="Fecha de pago", na_position='first').reset_index(drop=True)
    df = df.map(lambda x: x.upper() if isinstance(x, str) else x)
    
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
    if 'Tipo de poliza' in df_raw.columns:
        df_raw['Tipo de poliza'] = df_raw['Tipo de poliza'].astype(str).str.upper().str.strip()
    else:
        df_raw['Tipo de poliza'] = ""

    df_dev = df_raw[df_raw['Tipo de poliza'].str.contains('DEVENGO')].copy()
    df_pag = df_raw[df_raw['Tipo de poliza'].str.contains('PAGO')].copy()

    df_dev = df_dev.rename(columns={'Cuenta contable': 'Cuenta contable del devengado', 'Numero de poliza': 'Número (Devengo)', 'Fecha': 'Fecha (Devengo)', 'Importe': 'Importe (Devengo)'})
    if not df_dev.empty: df_dev = df_dev[['Numero de estimacion', 'Cuenta contable del devengado', 'Número (Devengo)', 'Fecha (Devengo)', 'Importe (Devengo)', 'Fuente de financiamiento']]
    
    df_pag = df_pag.rename(columns={'Numero de poliza': 'Número (Pago)', 'Fecha': 'Fecha (Pago)', 'Importe': 'Importe (Pago)'})
    if not df_pag.empty: df_pag = df_pag[['Numero de estimacion', 'Número (Pago)', 'Fecha (Pago)', 'Importe (Pago)']]

    df_dev = _limpiar_numeros(df_dev, ['Importe (Devengo)'])
    df_dev = _limpiar_fechas(df_dev)
    df_pag = _limpiar_numeros(df_pag, ['Importe (Pago)'])
    df_pag = _limpiar_fechas(df_pag)

    if not df_dev.empty:
        df_dev = df_dev.sort_values(by=['Fecha (Devengo)', 'Numero de estimacion']).reset_index(drop=True)
        t_dev = df_dev['Importe (Devengo)'].sum()
        fila = {c: '' for c in df_dev.columns}
        fila['Número (Devengo)'] = 'TOTAL'
        fila['Importe (Devengo)'] = t_dev
        df_dev = pd.concat([df_dev, pd.DataFrame([fila])], ignore_index=True)

    if not df_pag.empty:
        df_pag = df_pag.sort_values(by=['Fecha (Pago)', 'Numero de estimacion']).reset_index(drop=True)
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