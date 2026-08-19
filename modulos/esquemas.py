from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel


class ModeloASEG(BaseModel):
    # Gemini generateContent no admite `additionalProperties` dentro de
    # `response_schema`. Pydantic lo agrega al usar `extra="forbid"`.
    model_config = ConfigDict(populate_by_name=True)


class Estimacion(ModeloASEG):
    numero_estimacion: str = Field(alias="Numero de estimación")
    fecha_elaboracion: str = Field(alias="Fecha de elaboración o de estimación")
    periodo_de: str = Field(alias="De (Periodo de ejecución)")
    periodo_hasta: str = Field(alias="Hasta (Periodo de ejecución)")
    importe_sin_iva: float = Field(alias="Importe sin IVA", default=0.0)
    iva: float = Field(alias="IVA", default=0.0)
    importe_con_iva: float = Field(alias="Importe con IVA", default=0.0)
    importe_anticipo: float = Field(alias="Importe de anticipo", default=0.0)
    amortizacion: float = Field(alias="Amortización", default=0.0)
    deducciones: float = Field(alias="Deducciones", default=0.0)
    sancion: float = Field(alias="Sancion", default=0.0)
    retencion: float = Field(alias="Retencion", default=0.0)


class ListaEstimaciones(RootModel[list[Estimacion]]):
    pass


class Factura(ModeloASEG):
    folio: str = Field(alias="Folio")
    descripcion: str = Field(alias="Descripción")
    fecha: str = Field(alias="Fecha")
    monto_total: float = Field(alias="Monto total", default=0.0)
    orden_estimacion: int = Field(alias="Orden de estimacion", default=99)


class ListaFacturas(RootModel[list[Factura]]):
    pass


class ComprobantePago(ModeloASEG):
    numero: str = Field(alias="Número")
    fecha_pago: str = Field(alias="Fecha de pago")
    importe: float = Field(alias="Importe", default=0.0)
    cuenta_emisora: str = Field(alias="Cuenta bancaria emisora")
    clave_rastreo: str = Field(alias="Clave de rastreo")
    institucion_emisora: str = Field(alias="Institución emisora")
    institucion_receptora: str = Field(alias="Institución receptora")
    cuenta_beneficiaria: str = Field(alias="Cuenta beneficiaria")


class ListaComprobantes(RootModel[list[ComprobantePago]]):
    pass


class Poliza(ModeloASEG):
    tipo: Literal["DEVENGO", "PAGO"] = Field(alias="Tipo de poliza")
    cuenta_contable: str = Field(alias="Cuenta contable")
    numero_estimacion: str = Field(alias="Numero de estimacion")
    numero_poliza: str = Field(alias="Numero de poliza")
    fecha: str = Field(alias="Fecha")
    importe: float = Field(alias="Importe", default=0.0)
    fuente_financiamiento: str = Field(alias="Fuente de financiamiento")


class ListaPolizas(RootModel[list[Poliza]]):
    pass


class DatosContrato(ModeloASEG):
    numero_contrato: str = Field(alias="Número de contrato")
    descripcion_obra: str = Field(alias="Descripción de la obra o servicio")
    tipo_contrato: str = Field(alias="Tipo de contrato")
    contratista: str = Field(alias="Contratista (Nombre o razón social)")
    registro_puc: str = Field(alias="Número de registro PUC")
    representante_legal: str = Field(alias="Representante legal")
    modalidad_adjudicacion: str = Field(alias="Modalidad de adjudicación")
    deducciones_retenciones: str = Field(alias="Deducciones y/o retenciones")
    monto_contrato: str = Field(alias="Monto del contrato")
    fecha_inicio: str = Field(alias="Fecha de inicio contractual")
    fecha_termino: str = Field(alias="Fecha de término contractual")
    fecha_firma: str = Field(alias="Fecha de firma de contrato")
    anticipo: str = Field(alias="Anticipo")
    forma_lugar_pago: str = Field(alias="Forma y lugar de pago")
    plazo_estimaciones: str = Field(alias="Plazo de entrega de estimaciones")
    fecha_corte_estimaciones: str = Field(alias="Fecha de corte de estimaciones")
    fuente_financiamiento: str = Field(alias="Fuente de financiamiento")
    participantes: str = Field(alias="Personas que participan en el contrato")


class ProcedimientosContrato(ModeloASEG):
    p1: str
    p2: str


class Contrato(ModeloASEG):
    datos: DatosContrato
    conclusion: str
    procedimientos: ProcedimientosContrato


class IdentificacionCatalogo(ModeloASEG):
    corresponde: Literal["SI", "NO", "INDETERMINADO"]
    tipo_detectado: str
    justificacion: str
    paginas: list[int] = Field(default_factory=list)


class DatoCatalogoIA(ModeloASEG):
    nombre_tecnico: str
    valor: str
    encontrado: bool
    evidencia: str
    paginas: list[int] = Field(default_factory=list)
    confianza: Literal["Alta", "Media", "Baja"]


class ProcedimientoCatalogoIA(ModeloASEG):
    procedimiento_id: str
    resultado: Literal["CUMPLE", "NO_CUMPLE", "NO_DETERMINABLE", "NO_APLICA"]
    detalle: str
    evidencia: str
    paginas: list[int] = Field(default_factory=list)


class AnalisisDocumentoCatalogo(ModeloASEG):
    identificacion: IdentificacionCatalogo
    datos_extraidos: list[DatoCatalogoIA] = Field(default_factory=list)
    procedimientos: list[ProcedimientoCatalogoIA] = Field(default_factory=list)
    conclusion: str
    advertencias: list[str] = Field(default_factory=list)


class ResultadoExtraccion(ModeloASEG):
    estado: Literal["OK", "ERROR"]
    datos: list[dict[str, Any]] = Field(default_factory=list)
    errores: list[str] = Field(default_factory=list)
    advertencias: list[str] = Field(default_factory=list)
    metadatos: dict[str, Any] = Field(default_factory=dict)
