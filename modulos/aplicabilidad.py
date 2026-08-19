from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from modulos.catalogo import DocumentoCatalogo, clasificar_archivo


SI = "SI"
NO = "NO"
PENDIENTE = "PENDIENTE"


@dataclass(frozen=True)
class ArchivoExpediente:
    nombre: str
    huella: str = ""
    origen: str = "cargado"
    clave_catalogo: str = ""


@dataclass(frozen=True)
class ReglaAplicabilidad:
    campo: str
    valor_que_aplica: str = SI


@dataclass(frozen=True)
class ResultadoDocumento:
    documento: DocumentoCatalogo
    aplicabilidad: str
    estado: str
    archivos: tuple[ArchivoExpediente, ...]
    justificacion: str
    observacion: str = ""


@dataclass(frozen=True)
class ConciliacionExpediente:
    resultados: tuple[ResultadoDocumento, ...]
    no_reconocidos: tuple[ArchivoExpediente, ...]

    def contar(self, estado: str) -> int:
        return sum(resultado.estado == estado for resultado in self.resultados)


# Estas reglas usan identificadores estables del catálogo. Si un documento
# condicional no está registrado, permanece pendiente en lugar de inferirse.
REGLAS_POR_TIPO = {
    "PPP_CNV": ReglaAplicabilidad("requiere_convenio_colaboracion"),
    "PPP_EIA": ReglaAplicabilidad("requiere_estudio_impacto"),
    "PPP_ESP": ReglaAplicabilidad("requiere_especificaciones"),
    "CNT_ANT": ReglaAplicabilidad("otorga_anticipo"),
    "CNT_GAN": ReglaAplicabilidad("otorga_anticipo"),
    "CNT_CUM": ReglaAplicabilidad(
        "excepcion_garantia_cumplimiento",
        valor_que_aplica=NO,
    ),
}


def _valor_contexto(contexto: Mapping[str, str], campo: str) -> str:
    valor = str(contexto.get(campo, PENDIENTE)).strip().upper()
    return valor if valor in {SI, NO} else PENDIENTE


def evaluar_aplicabilidad(
    documento: DocumentoCatalogo,
    contexto: Mapping[str, str],
) -> tuple[str, str]:
    obligatoriedad = documento.obligatoriedad.strip().casefold()
    if obligatoriedad == "obligatorio":
        return "APLICA", "El catálogo lo define como obligatorio."
    if obligatoriedad == "no aplica":
        return "NO_APLICA", "El catálogo lo define expresamente como no aplicable."
    if obligatoriedad == "opcional":
        return "OPCIONAL", "El catálogo lo define como opcional."
    if obligatoriedad != "condicional":
        return (
            "PENDIENTE",
            "La obligatoriedad del catálogo todavía no permite determinar su aplicación.",
        )

    regla = REGLAS_POR_TIPO.get(documento.tipo_documental)
    if not regla:
        return (
            "PENDIENTE",
            "No existe una regla determinística aprobada para esta condición.",
        )

    valor = _valor_contexto(contexto, regla.campo)
    if valor == PENDIENTE:
        return (
            "PENDIENTE",
            "Falta responder un dato del expediente para evaluar la condición.",
        )
    if valor == regla.valor_que_aplica:
        return "APLICA", "La respuesta registrada en el expediente activa la condición."
    return "NO_APLICA", "La respuesta registrada en el expediente no activa la condición."


def _archivos_unicos(
    archivos: Iterable[ArchivoExpediente],
) -> tuple[ArchivoExpediente, ...]:
    unicos: dict[tuple[str, str], ArchivoExpediente] = {}
    for archivo in archivos:
        clave = (archivo.nombre.casefold(), archivo.huella)
        unicos.setdefault(clave, archivo)
    return tuple(unicos.values())


def conciliar_expediente(
    documentos: Iterable[DocumentoCatalogo],
    archivos: Iterable[ArchivoExpediente],
    contexto: Mapping[str, str],
) -> ConciliacionExpediente:
    definiciones = tuple(sorted(documentos, key=lambda item: item.orden))
    encontrados: dict[str, list[ArchivoExpediente]] = {
        documento.id: [] for documento in definiciones
    }
    por_clave = {
        documento.clave_catalogo: documento for documento in definiciones
    }
    no_reconocidos: list[ArchivoExpediente] = []

    for archivo in _archivos_unicos(archivos):
        documento = por_clave.get(archivo.clave_catalogo) or clasificar_archivo(
            archivo.nombre,
            definiciones,
        )
        if documento:
            encontrados[documento.id].append(archivo)
        else:
            no_reconocidos.append(archivo)

    resultados = []
    for documento in definiciones:
        coincidencias = tuple(encontrados[documento.id])
        aplicabilidad, justificacion = evaluar_aplicabilidad(documento, contexto)
        observacion = ""

        if aplicabilidad == "APLICA":
            if not coincidencias:
                estado = "FALTANTE"
            elif len(coincidencias) > 1 and not documento.admite_multiples:
                estado = "DUPLICADO"
                observacion = "El catálogo permite un solo archivo para este documento."
            else:
                estado = "ENCONTRADO"
        elif aplicabilidad == "NO_APLICA":
            estado = "NO_APLICABLE"
            if coincidencias:
                observacion = (
                    "Se cargó un archivo aunque la respuesta del expediente indica "
                    "que el documento no aplica; requiere revisión."
                )
        elif aplicabilidad == "OPCIONAL":
            estado = "ENCONTRADO" if coincidencias else "NO_REQUERIDO"
        else:
            estado = "PENDIENTE"
            if coincidencias:
                observacion = (
                    "El archivo está cargado, pero todavía falta determinar su aplicabilidad."
                )

        resultados.append(
            ResultadoDocumento(
                documento=documento,
                aplicabilidad=aplicabilidad,
                estado=estado,
                archivos=coincidencias,
                justificacion=justificacion,
                observacion=observacion,
            )
        )

    return ConciliacionExpediente(tuple(resultados), tuple(no_reconocidos))
