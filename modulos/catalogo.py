from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class DocumentoCatalogo:
    id: str
    clave_catalogo: str
    orden: int
    procedimiento: str
    etapa: str
    tipo_documental: str
    codigo_base: str
    nombre: str
    obligatoriedad: str
    condicion_aplicabilidad: str
    admite_multiples: bool
    patron_consecutivo: str | None
    extensiones: tuple[str, ...]


def desde_fila(fila) -> DocumentoCatalogo:
    extensiones = tuple(
        sorted({str(extension).lower().lstrip(".") for extension in (fila[12] or [])})
    ) or ("pdf",)
    return DocumentoCatalogo(
        id=str(fila[0]),
        clave_catalogo=fila[1],
        orden=int(fila[2]),
        procedimiento=fila[3],
        etapa=fila[4],
        tipo_documental=fila[5],
        codigo_base=fila[6],
        nombre=fila[7],
        obligatoriedad=fila[8],
        condicion_aplicabilidad=fila[9],
        admite_multiples=bool(fila[10]),
        patron_consecutivo=fila[11],
        extensiones=extensiones,
    )


def _expresion_documento(documento: DocumentoCatalogo) -> re.Pattern[str]:
    patron = documento.patron_consecutivo or documento.codigo_base
    patron = Path(patron).stem.upper()
    expresion = re.escape(patron).replace(r"\{N\}", r"\d+")
    return re.compile(rf"(?:^|[^A-Z0-9]){expresion}(?:$|[^A-Z0-9])")


def clasificar_archivo(
    nombre_archivo: str,
    documentos: Iterable[DocumentoCatalogo],
) -> DocumentoCatalogo | None:
    nombre = Path(nombre_archivo).stem.upper()
    candidatos = sorted(
        documentos,
        key=lambda documento: len(documento.codigo_base),
        reverse=True,
    )
    for documento in candidatos:
        if _expresion_documento(documento).search(nombre):
            return documento
    return None


def extensiones_por_etapa(
    documentos: Iterable[DocumentoCatalogo],
    etapa: str,
) -> list[str]:
    return sorted(
        {
            extension
            for documento in documentos
            if documento.etapa == etapa
            for extension in documento.extensiones
        }
    ) or ["pdf"]

