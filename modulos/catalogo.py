from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class CampoCatalogo:
    orden: int
    nombre_tecnico: str
    etiqueta: str
    tipo_dato: str
    obligatorio: bool
    instruccion: str
    estado_revision: str = "Pendiente"


@dataclass(frozen=True)
class ProcedimientoCatalogo:
    orden: int
    procedimiento_id: str
    procedimiento: str
    resultado_esperado: str | None
    evidencia_requerida: str | None
    riesgo_codigo: str
    estado_revision: str = "Pendiente"


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
    version_catalogo: str = ""
    criterios_identificacion_ia: str = ""
    datos_clave_a_validar: str = ""
    fundamento_normativo: str = ""
    campos: tuple[CampoCatalogo, ...] = ()
    procedimientos: tuple[ProcedimientoCatalogo, ...] = ()

    @property
    def firma_configuracion(self) -> str:
        contenido = {
            "clave": self.clave_catalogo,
            "version": self.version_catalogo,
            "criterios": self.criterios_identificacion_ia,
            "datos_clave": self.datos_clave_a_validar,
            "fundamento": self.fundamento_normativo,
            "campos": [campo.__dict__ for campo in self.campos],
            "procedimientos": [procedimiento.__dict__ for procedimiento in self.procedimientos],
        }
        serializado = json.dumps(contenido, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(serializado.encode("utf-8")).hexdigest()[:16]


def _campo_desde_json(datos: dict) -> CampoCatalogo:
    return CampoCatalogo(
        orden=int(datos["orden"]),
        nombre_tecnico=str(datos["nombre_tecnico"]),
        etiqueta=str(datos["etiqueta"]),
        tipo_dato=str(datos["tipo_dato"]),
        obligatorio=bool(datos["obligatorio"]),
        instruccion=str(datos.get("instruccion") or ""),
        estado_revision=str(datos.get("estado_revision") or "Pendiente"),
    )


def _procedimiento_desde_json(datos: dict) -> ProcedimientoCatalogo:
    return ProcedimientoCatalogo(
        orden=int(datos["orden"]),
        procedimiento_id=str(datos["procedimiento_id"]),
        procedimiento=str(datos["procedimiento"]),
        resultado_esperado=datos.get("resultado_esperado"),
        evidencia_requerida=datos.get("evidencia_requerida"),
        riesgo_codigo=str(datos.get("riesgo_codigo") or "Sin riesgo"),
        estado_revision=str(datos.get("estado_revision") or "Pendiente"),
    )


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
        version_catalogo=str(fila[13]) if len(fila) > 13 else "",
        criterios_identificacion_ia=str(fila[14] or "") if len(fila) > 14 else "",
        datos_clave_a_validar=str(fila[15] or "") if len(fila) > 15 else "",
        fundamento_normativo=str(fila[16] or "") if len(fila) > 16 else "",
        campos=tuple(
            _campo_desde_json(datos)
            for datos in (fila[17] or [])
        ) if len(fila) > 17 else (),
        procedimientos=tuple(
            _procedimiento_desde_json(datos)
            for datos in (fila[18] or [])
        ) if len(fila) > 18 else (),
    )


def _nombre_tecnico(etiqueta: str, orden: int) -> str:
    texto = unicodedata.normalize("NFKD", etiqueta)
    texto = "".join(caracter for caracter in texto if not unicodedata.combining(caracter))
    texto = re.sub(r"[^a-zA-Z0-9]+", "_", texto).strip("_").lower()
    return texto or f"dato_{orden}"


def campos_operativos(documento: DocumentoCatalogo) -> tuple[CampoCatalogo, ...]:
    """Usa campos formales o deriva una lista estable desde los datos clave."""
    if documento.campos:
        return tuple(sorted(documento.campos, key=lambda campo: campo.orden))

    etiquetas = [
        parte.strip(" .")
        for parte in re.split(r"[;\n]+", documento.datos_clave_a_validar)
        if parte.strip(" .")
    ]
    return tuple(
        CampoCatalogo(
            orden=orden,
            nombre_tecnico=_nombre_tecnico(etiqueta, orden),
            etiqueta=etiqueta,
            tipo_dato="Texto",
            obligatorio=False,
            instruccion=(
                "Localizar el dato en el documento y reportar evidencia y página; "
                "si no se encuentra, indicarlo expresamente."
            ),
            estado_revision="Derivado",
        )
        for orden, etiqueta in enumerate(etiquetas, start=1)
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
