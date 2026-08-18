from __future__ import annotations

import os
import re
import time
from typing import Type

import streamlit as st
from google import genai
from google.genai import types
from pydantic import BaseModel, ValidationError

from modulos.esquemas import (
    Contrato,
    ListaComprobantes,
    ListaEstimaciones,
    ListaFacturas,
    ListaPolizas,
    ResultadoExtraccion,
)


PROMPT_VERSION = "2026-08-17-v1"
TAMANO_MAXIMO_PDF = 50 * 1024 * 1024


def _secreto(nombre: str, default: str = "") -> str:
    try:
        return str(st.secrets.get(nombre, default))
    except Exception:
        return os.getenv(nombre, default)


MODEL_NAME = _secreto("GEMINI_MODEL", "gemini-2.5-flash")


def _cliente() -> genai.Client:
    api_key = _secreto("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY no está configurada")
    return genai.Client(api_key=api_key)


def _segundos_reintento(error: Exception, intento: int) -> int:
    texto = str(error)
    coincidencia = re.search(r"retry(?:\s+in|\s+after)?\s+(\d+)", texto, re.IGNORECASE)
    if coincidencia:
        return min(120, int(coincidencia.group(1)) + 1)
    return min(120, 15 * (2**intento))


def _llamar_gemini(
    contenidos: list,
    esquema: Type[BaseModel],
    max_reintentos: int = 3,
):
    cliente = _cliente()
    for intento in range(max_reintentos):
        try:
            return cliente.models.generate_content(
                model=MODEL_NAME,
                contents=contenidos,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=esquema,
                    temperature=0.0,
                ),
            )
        except Exception as exc:
            texto = str(exc).lower()
            recuperable = any(
                marca in texto
                for marca in ("429", "quota", "resource_exhausted", "503", "unavailable")
            )
            if not recuperable or intento == max_reintentos - 1:
                raise
            espera = _segundos_reintento(exc, intento)
            st.warning(
                f"⏳ Servicio de IA temporalmente ocupado. "
                f"Nuevo intento en {espera}s ({intento + 1}/{max_reintentos})."
            )
            time.sleep(espera)
    raise RuntimeError("No fue posible completar la llamada a Gemini")


def _normalizar_respuesta(response, esquema: Type[BaseModel]) -> list[dict]:
    parsed = response.parsed
    if parsed is None:
        parsed = esquema.model_validate_json(response.text)
    elif not isinstance(parsed, BaseModel):
        parsed = esquema.model_validate(parsed)

    contenido = parsed.model_dump(by_alias=True, mode="json")
    return contenido if isinstance(contenido, list) else [contenido]


def _metadatos(response) -> dict:
    usage = getattr(response, "usage_metadata", None)
    if usage is None:
        consumo = {}
    elif hasattr(usage, "model_dump"):
        consumo = usage.model_dump(mode="json")
    else:
        consumo = {"detalle": str(usage)}
    return {
        "modelo": MODEL_NAME,
        "version_prompt": PROMPT_VERSION,
        "consumo": consumo,
    }


def procesar_documento(
    archivo_pdf,
    prompt: str,
    esquema: Type[BaseModel],
) -> ResultadoExtraccion:
    try:
        contenido = archivo_pdf.getvalue()
        if not contenido:
            raise ValueError("El archivo PDF está vacío")
        if len(contenido) > TAMANO_MAXIMO_PDF:
            raise ValueError("El PDF supera el límite de 50 MB admitido por Gemini")

        documento = types.Part.from_bytes(data=contenido, mime_type="application/pdf")
        response = _llamar_gemini([documento, prompt], esquema)
        datos = _normalizar_respuesta(response, esquema)
        return ResultadoExtraccion(
            estado="OK",
            datos=datos,
            metadatos=_metadatos(response),
        )
    except ValidationError as exc:
        return ResultadoExtraccion(
            estado="ERROR",
            errores=[f"La respuesta de IA no cumple el esquema: {exc}"],
            metadatos={"modelo": MODEL_NAME, "version_prompt": PROMPT_VERSION},
        )
    except Exception as exc:
        return ResultadoExtraccion(
            estado="ERROR",
            errores=[f"Fallo en IA: {exc}"],
            metadatos={"modelo": MODEL_NAME, "version_prompt": PROMPT_VERSION},
        )


def procesar_estimaciones(archivo_pdf) -> ResultadoExtraccion:
    prompt = """
    Actúa como auditor de obra pública. Localiza todas las carátulas de estimación
    contenidas en el PDF y extrae un registro por cada una.

    Reglas:
    - Conserva el número de estimación exactamente como aparece.
    - Usa fechas en formato YYYY-MM-DD; si no existe una fecha usa 1900-01-01.
    - Importe de anticipo es el total otorgado para el contrato.
    - Amortización es únicamente el descuento aplicado en esa estimación.
    - No repitas un mismo importe entre deducciones, sanción y retención.
    - Si no aparece el importe con IVA, calcúlalo como importe sin IVA más IVA.
    - Para importes inexistentes utiliza 0.0.
    """
    return procesar_documento(archivo_pdf, prompt, ListaEstimaciones)


def procesar_facturas(archivo_pdf) -> ResultadoExtraccion:
    prompt = """
    Actúa como auditor de obra pública. Localiza todas las facturas o CFDI del PDF
    y extrae un registro por comprobante.

    Usa el UUID como folio, fechas YYYY-MM-DD y montos numéricos con IVA incluido.
    Para el orden de estimación usa el número identificado; usa 0 para anticipo y
    99 cuando el documento no permita determinarlo.
    """
    return procesar_documento(archivo_pdf, prompt, ListaFacturas)


def procesar_comprobantes(archivo_pdf) -> ResultadoExtraccion:
    prompt = """
    Actúa como auditor de obra pública y analista financiero. Localiza todos los
    comprobantes de pago, transferencias, cheques o SPEI del PDF.

    Extrae fecha efectiva de pago, importe, cuenta emisora, clave de rastreo,
    instituciones emisora y receptora y cuenta beneficiaria. Usa YYYY-MM-DD para
    fechas, 1900-01-01 si no existe, N/A para texto ausente y 0.0 para importes
    inexistentes.
    """
    return procesar_documento(archivo_pdf, prompt, ListaComprobantes)


def procesar_polizas(archivo_pdf) -> ResultadoExtraccion:
    prompt = """
    Actúa como auditor de obra pública y contador. Analiza todas las pólizas del
    PDF y clasifica cada registro como DEVENGO o PAGO.

    Para DEVENGO evita duplicar importes entre cuentas transitorias terminadas en
    09 y cuentas definitivas terminadas en 00. Prefiere la cuenta 00; usa la 09
    solamente cuando no exista la 00 e indícalo en el texto de la cuenta. Conserva
    registros separados cuando existan fondos distintos.

    Para PAGO toma el importe de la salida de bancos cuya cuenta inicia en 1112.
    Conserva ceros iniciales del número de póliza. Obtén el número de estimación de
    la referencia y usa NO INDICA cuando esté vacío. Usa fechas YYYY-MM-DD.
    """
    return procesar_documento(archivo_pdf, prompt, ListaPolizas)


def procesar_contratos(archivo_pdf) -> ResultadoExtraccion:
    prompt = """
    Actúa como auditor de obra pública con experiencia legal y técnica. Analiza el
    contrato completo y extrae los datos contractuales solicitados por el esquema.

    Si un dato no se menciona o no es legible usa No detectado en el documento.
    En la conclusión resume la congruencia general sin afirmar irregularidades que
    no estén demostradas. En p1 evalúa si están las firmas de todas las partes. En
    p2 evalúa si el documento identifica la legislación aplicable de acuerdo con
    su objeto y fuente de financiamiento. Usa OK únicamente cuando la evidencia del
    documento sea suficiente; en caso contrario explica brevemente la carencia.
    """
    return procesar_documento(archivo_pdf, prompt, Contrato)

