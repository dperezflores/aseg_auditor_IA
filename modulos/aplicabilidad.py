from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from modulos.catalogo import DocumentoCatalogo, ReglaCatalogo, clasificar_archivo


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
class ResultadoDocumento:
    documento: DocumentoCatalogo
    aplicabilidad: str
    estado: str
    archivos: tuple[ArchivoExpediente, ...]
    justificacion: str
    observacion: str = ""
    resultado_ia: str = "SIN_ANALIZAR"


@dataclass(frozen=True)
class ConciliacionExpediente:
    resultados: tuple[ResultadoDocumento, ...]
    no_reconocidos: tuple[ArchivoExpediente, ...]

    def contar(self, estado: str) -> int:
        return sum(resultado.estado == estado for resultado in self.resultados)


def _normalizar(valor):
    if isinstance(valor, str):
        return valor.strip().casefold()
    return valor


def _valor_regla(regla: ReglaCatalogo, contexto: Mapping):
    if regla.fuente == "VALOR_FIJO":
        return True, True
    if regla.fuente == "DOCUMENTO_PRESENTE":
        presentes = contexto.get("documentos_presentes", set())
        return regla.fuente_tipo_documental in presentes, True

    campos = contexto.get("campos_extraidos", {})
    por_tipo = campos.get(regla.fuente_tipo_documental or "", {})
    if regla.fuente_campo in por_tipo:
        return por_tipo[regla.fuente_campo], True
    if regla.fuente_campo in campos:
        return campos[regla.fuente_campo], True
    return None, False


def _comparar(valor, operador: str, esperado) -> bool:
    if operador == "EXISTE":
        return valor not in (None, "", [], {})
    if operador == "NO_EXISTE":
        return valor in (None, "", [], {})
    if operador == "IGUAL":
        return _normalizar(valor) == _normalizar(esperado)
    if operador == "DISTINTO":
        return _normalizar(valor) != _normalizar(esperado)
    if operador == "CONTIENE":
        return _normalizar(str(esperado)) in _normalizar(str(valor))
    try:
        numero, referencia = float(valor), float(esperado)
    except (TypeError, ValueError):
        return False
    return numero > referencia if operador == "MAYOR_QUE" else numero < referencia


def _evaluar_regla(regla: ReglaCatalogo, contexto: Mapping) -> tuple[str, str]:
    if regla.tipo_regla == "SIEMPRE":
        return "APLICA", regla.justificacion or "La regla aprobada indica que siempre aplica."
    if regla.tipo_regla == "NO_APLICA":
        return "NO_APLICA", regla.justificacion or "La regla aprobada indica que no aplica."

    valor, disponible = _valor_regla(regla, contexto)
    if not disponible:
        return regla.resultado_sin_dato, (
            regla.justificacion
            or "Todavía no existe información suficiente para resolver la regla."
        )
    cumple = _comparar(valor, regla.operador, regla.valor_esperado)
    return (
        regla.resultado_verdadero if cumple else regla.resultado_falso,
        regla.justificacion or "Resultado calculado con una regla aprobada del catálogo.",
    )


def evaluar_aplicabilidad(
    documento: DocumentoCatalogo,
    contexto: Mapping,
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

    if not documento.reglas_aplicabilidad:
        return (
            "PENDIENTE",
            "No existe una regla determinística aprobada para esta condición.",
        )

    evaluadas = [_evaluar_regla(regla, contexto) for regla in documento.reglas_aplicabilidad]
    detalles = " ".join(dict.fromkeys(detalle for _, detalle in evaluadas))
    estados = {estado for estado, _ in evaluadas}
    if "NO_APLICA" in estados:
        return "NO_APLICA", detalles
    if estados == {"APLICA"}:
        return "APLICA", detalles
    return "PENDIENTE", detalles


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
    contexto: Mapping,
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

    contexto_evaluacion = dict(contexto)
    contexto_evaluacion["documentos_presentes"] = set(
        contexto.get("documentos_presentes", set())
    ).union(
        documento.tipo_documental
        for documento in definiciones
        if encontrados[documento.id]
    )

    resultados = []
    for documento in definiciones:
        coincidencias = tuple(encontrados[documento.id])
        aplicabilidad, justificacion = evaluar_aplicabilidad(
            documento,
            contexto_evaluacion,
        )
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
                resultado_ia=str(
                    contexto.get("resultados_ia", {}).get(
                        documento.clave_catalogo,
                        "SIN_ANALIZAR",
                    )
                ),
            )
        )

    return ConciliacionExpediente(tuple(resultados), tuple(no_reconocidos))
