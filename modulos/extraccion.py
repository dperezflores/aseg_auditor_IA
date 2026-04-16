import google.generativeai as genai
import json
import streamlit as st
import time

if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

MODEL_NAME = "models/gemini-flash-latest"
modelo = genai.GenerativeModel(model_name=MODEL_NAME)

def procesar_documento_ram(archivo_pdf, prompt):
    """Envía el PDF en RAM a Gemini con el prompt especificado."""
    try:
        documento = [{"mime_type": "application/pdf", "data": archivo_pdf.getvalue()}]
        response = modelo.generate_content([documento[0], prompt])
        
        json_clean = response.text.replace('```json', '').replace('```', '').strip()
        datos_ia = json.loads(json_clean)
        
        if isinstance(datos_ia, list):
            return datos_ia
        return [datos_ia]
    except Exception as e:
        return [{"Error": f"Fallo en IA: {str(e)}"}]

def procesar_estimaciones(archivo_pdf):
    prompt = """
    Actúa como un Auditor de Obra Pública experto.
    Busca la carátula de la estimación dentro de TODO el documento adjunto.
    Una vez que la(s) encuentres, extrae los datos y responde ÚNICAMENTE en formato JSON.
    Si un dato numérico no existe, pon 0.0.
    Para las fechas usa SIEMPRE el formato YYYY-MM-DD.
    Si no hay fecha, pon "1900-01-01".

    IMPORTANTE: Si encuentras MÁS DE UNA carátula de estimación en el mismo documento, devuelve un ARREGLO (lista) de objetos JSON. Si solo hay una, devuelve un solo objeto JSON.

    REGLAS ESTRICTAS DE EXTRACCIÓN:
    1. "Numero de estimación": Extrae el valor EXACTAMENTE tal como aparece (ejemplo: '3 (TRES) NORMAL').
    2. PERIODO DE EJECUCIÓN:
       - Para el campo "De", busca en el documento etiquetas como 'PERIODO DEL', 'DE:', o 'DEL:'.
       - Para el campo "Hasta", busca etiquetas como 'AL:' o 'HASTA:'.
       - Convierte nombres de meses a su número correspondiente (01, 02, etc.).
    3. DIFERENCIA ENTRE ANTICIPO Y AMORTIZACIÓN (¡MUY IMPORTANTE!):
       - "Amortización": Es el descuento que se hace en ESTA estimación. Búscalo en la sección de montos a pagar bajo conceptos como "AMORTIZACION ANTICIPO" o "Amortizado".
       - "Importe de anticipo": Es el MONTO TOTAL DEL ANTICIPO otorgado para todo el contrato. NUNCA pongas aquí el valor de la amortización. Si no encuentras el monto total, pon 0.0.
    4. EXCLUSIÓN DE MONTOS: NUNCA repitas el mismo monto en Deducciones, Sancion o Retencion.
       - Si dice "Sanción", ponlo SOLO en "Sancion".
       - Si dice "Retención", ponlo SOLO en "Retencion".
       - "Deducciones" solo se usa para descuentos que no entren en las otras categorías.

    ESTRUCTURA JSON ESPERADA (Por cada estimación encontrada):
    {
      "Numero de estimación": "...",
      "Fecha de elaboración o de estimación": "YYYY-MM-DD",
      "De (Periodo de ejecución)": "YYYY-MM-DD",
      "Hasta (Periodo de ejecución)": "YYYY-MM-DD",
      "Importe sin IVA": 0.0,
      "IVA": 0.0,
      "Importe con IVA": 0.0,
      "Importe de anticipo": 0.0,
      "Amortización": 0.0,
      "Deducciones": 0.0,
      "Sancion": 0.0,
      "Retencion": 0.0
    }
    IMPORTANTE: Si el 'Importe con IVA' no aparece, súmalo tú (Sin IVA + IVA).
    """
    return procesar_documento_ram(archivo_pdf, prompt)

def procesar_facturas(archivo_pdf):
    prompt = """
    Actúa como un Auditor de obra pública.
    Busca TODAS las facturas o CFDIs dentro del documento PDF adjunto.
    Por cada factura que encuentres, extrae:
    1. Número de factura (Folio Fiscal/UUID).
    2. Descripción (Concepto de la factura, ej. Anticipo, Estimación 01, etc.).
    3. Fecha de emisión (Formato YYYY-MM-DD). Si no hay fecha, pon "1900-01-01".
    4. Monto Total (con IVA incluido, solo números, sin el signo $).
    5. Número de Estimación (Si la descripción dice 'Estimación 05', extrae el número 5. Si es 'Anticipo', pon 0. Si no hay, pon 99).

    IMPORTANTE: Si encuentras MÁS DE UNA factura en el documento, devuelve un ARREGLO (lista) de objetos JSON. Si solo hay una, devuelve un solo objeto JSON.

    Devuelve SOLO formato JSON con estas llaves exactas por cada factura:
    {
      "Folio": "",
      "Descripción": "",
      "Fecha": "YYYY-MM-DD",
      "Monto total": 0.0,
      "Orden de estimacion": 0
    }
    """
    return procesar_documento_ram(archivo_pdf, prompt)

def procesar_comprobantes(archivo_pdf):
    prompt = """
    Actúa como un Auditor de Obra Pública y Analista Financiero experto.
    Busca comprobantes de pago, transferencias, cheques o SPEI dentro de TODO el documento adjunto.
    Una vez que lo(s) encuentres, extrae los datos y responde ÚNICAMENTE en formato JSON.
    Si un dato de texto no existe, pon "N/A".
    Si un dato numérico (como el Importe) no existe, pon 0.0.
    Para las fechas usa SIEMPRE el formato YYYY-MM-DD. Si no hay fecha, pon "1900-01-01".
    IMPORTANTE: Si encuentras MÁS DE UN comprobante de pago en el mismo documento, devuelve un ARREGLO (lista) de objetos JSON.

    REGLAS ESTRICTAS DE EXTRACCIÓN:
    1. "Número": Extrae la referencia numérica, el número de transferencia o una breve descripción que identifique el pago.
    2. "Fecha de pago": La fecha en la que se realizó o autorizó la transacción.
    3. "Importe": El monto total monetario de la transferencia o pago. (Solo el número, sin el símbolo de peso).
    4. "Cuenta bancaria emisora": La cuenta de donde sale el dinero.
    5. "Clave de rastreo": Identificador alfanumérico que suele venir en los SPEI o transferencias.
    6. "Institución emisora": El banco de origen (ej. BBVA MEXICO, BANAMEX).
    7. "Institución receptora": El banco destino (ej. BANORTE, SANTANDER).
    8. "Cuenta beneficiaria": La cuenta CLABE, tarjeta o número de cuenta que recibe el pago.
    
    ESTRUCTURA JSON ESPERADA (Por cada comprobante encontrado):
    {
      "Número": "...",
      "Fecha de pago": "YYYY-MM-DD",
      "Importe": 0.0,
      "Cuenta bancaria emisora": "...",
      "Clave de rastreo": "...",
      "Institución emisora": "...",
      "Institución receptora": "...",
      "Cuenta beneficiaria": "..."
    }
    """
    return procesar_documento_ram(archivo_pdf, prompt)

def procesar_polizas(archivo_pdf):
    prompt = """
    Actúa como un Auditor de Obra Pública y Contador experto. Analiza el documento PDF adjunto, el cual puede contener múltiples pólizas contables.
    Extrae los datos requeridos y clasifícalos como "DEVENGO" o "PAGO".

    REGLAS TÉCNICAS DE EXTRACCIÓN Y FILTRADO:
    1. SI ES DEVENGO:
       - REGLA ANTI-DUPLICADOS (CRÍTICA): ¡Nunca reportes el mismo importe dos veces! Si en el PDF encuentras que una misma cantidad de dinero pasa por una cuenta transitoria (terminación '09') y en otra póliza se reclasifica a una cuenta definitiva (terminación '00'), DEBES IGNORAR POR COMPLETO la póliza de la cuenta '09'.
       - PLAN A (El Ideal): Extrae SOLAMENTE los datos de la póliza donde aparece la "Cuenta contable" definitiva (terminada en '00').
       - PLAN B (Fallback): ÚNICAMENTE si confirmas que la cuenta '00' NO EXISTE en todo el PDF, entonces extrae los datos de la cuenta puente (terminada en '09') y escribe su valor así: "1235461409 (Sin cuenta 00)".
       - MULTIPLES FONDOS: Es muy común que una estimación se pague con diferentes "Fondos". Si hay varios importes distintos con su respectiva cuenta '00', extrae cada uno como un registro separado.
       - FUENTE DE FINANCIAMIENTO: Extrae la clave numérica de la columna "Fondo" (ej. 2525821100).
    2. SI ES PAGO:
       - El "Importe" debe ser estrictamente el valor de la fila que sale de BANCOS (Cuenta que inicia con 1112...). IGNORA los pasivos.
    3. NUMERO DE POLIZA: Extrae el "No. Documento" EXACTAMENTE como aparece impreso en la hoja que elegiste, respetando todos los ceros a la izquierda (ej. 3000001565).
    4. NUMERO DE ESTIMACION: Busca el texto de "Referencia:". Si está en blanco, devuelve la palabra "NO INDICA".
    5. FECHA: Extrae la "Fecha Contab." en formato YYYY-MM-DD.

    ESTRUCTURA JSON OBLIGATORIA (LISTA):
    [
      {
        "Tipo de poliza": "...",
        "Cuenta contable": "...",
        "Numero de estimacion": "...",
        "Numero de poliza": "...",
        "Fecha": "YYYY-MM-DD",
        "Importe": 0.0,
        "Fuente de financiamiento": "..."
      }
    ]
    """
    return procesar_documento_ram(archivo_pdf, prompt)