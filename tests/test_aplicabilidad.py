from __future__ import annotations

import unittest

from modulos.aplicabilidad import (
    ArchivoExpediente,
    NO,
    PENDIENTE,
    SI,
    conciliar_expediente,
    evaluar_aplicabilidad,
)
from modulos.catalogo import DocumentoCatalogo


def documento(
    clave: str,
    tipo: str,
    obligatoriedad: str = "Condicional",
    multiples: bool = False,
) -> DocumentoCatalogo:
    return DocumentoCatalogo(
        id=clave,
        clave_catalogo=clave,
        orden=1,
        procedimiento="LPU",
        etapa=clave[:3],
        tipo_documental=tipo,
        codigo_base=clave,
        nombre=f"Documento {clave}",
        obligatoriedad=obligatoriedad,
        condicion_aplicabilidad="Condición de prueba",
        admite_multiples=multiples,
        patron_consecutivo=f"{clave[:-1]}{{n}}.pdf" if multiples else None,
        extensiones=("pdf",),
    )


class AplicabilidadTest(unittest.TestCase):
    def test_obligatorio_siempre_aplica(self):
        contrato = documento("CNT_LPU_CNT", "CNT_CNT", "Obligatorio")
        self.assertEqual(evaluar_aplicabilidad(contrato, {})[0], "APLICA")

    def test_condicional_pendiente_no_se_convierte_en_faltante(self):
        garantia = documento("CNT_LPU_GAN", "CNT_GAN")
        conciliacion = conciliar_expediente([garantia], [], {})
        self.assertEqual(conciliacion.resultados[0].aplicabilidad, "PENDIENTE")
        self.assertEqual(conciliacion.resultados[0].estado, "PENDIENTE")

    def test_anticipo_activa_factura_y_garantia(self):
        factura = documento("CNT_LPU_ANT_1", "CNT_ANT", multiples=True)
        garantia = documento("CNT_LPU_GAN", "CNT_GAN")
        for definicion in (factura, garantia):
            self.assertEqual(
                evaluar_aplicabilidad(definicion, {"otorga_anticipo": SI})[0],
                "APLICA",
            )
            self.assertEqual(
                evaluar_aplicabilidad(definicion, {"otorga_anticipo": NO})[0],
                "NO_APLICA",
            )

    def test_excepcion_invierte_garantia_cumplimiento(self):
        garantia = documento("CNT_LPU_CUM", "CNT_CUM")
        self.assertEqual(
            evaluar_aplicabilidad(
                garantia,
                {"excepcion_garantia_cumplimiento": SI},
            )[0],
            "NO_APLICA",
        )
        self.assertEqual(
            evaluar_aplicabilidad(
                garantia,
                {"excepcion_garantia_cumplimiento": NO},
            )[0],
            "APLICA",
        )

    def test_concilia_encontrado_faltante_duplicado_y_no_reconocido(self):
        contrato = documento("CNT_LPU_CNT", "CNT_CNT", "Obligatorio")
        presupuesto = documento("CNT_LPU_PTC", "CNT_PTC", "Obligatorio")
        archivos = [
            ArchivoExpediente("CNT_LPU_CNT.pdf", "a"),
            ArchivoExpediente("CNT_LPU_CNT_copia.pdf", "b"),
            ArchivoExpediente("archivo_sin_clave.pdf", "c"),
        ]
        conciliacion = conciliar_expediente(
            [contrato, presupuesto],
            archivos,
            {},
        )
        estados = {
            resultado.documento.clave_catalogo: resultado.estado
            for resultado in conciliacion.resultados
        }
        self.assertEqual(estados["CNT_LPU_CNT"], "DUPLICADO")
        self.assertEqual(estados["CNT_LPU_PTC"], "FALTANTE")
        self.assertEqual(
            [archivo.nombre for archivo in conciliacion.no_reconocidos],
            ["archivo_sin_clave.pdf"],
        )

    def test_archivo_guardado_puede_usar_clave_catalogo(self):
        contrato = documento("CNT_LPU_CNT", "CNT_CNT", "Obligatorio")
        archivo = ArchivoExpediente(
            "contrato firmado.pdf",
            "a",
            "guardado",
            clave_catalogo="CNT_LPU_CNT",
        )
        conciliacion = conciliar_expediente([contrato], [archivo], {})
        self.assertEqual(conciliacion.resultados[0].estado, "ENCONTRADO")

    def test_valores_invalidos_permanecen_pendientes(self):
        convenio = documento("PPP_LPU_CNV", "PPP_CNV")
        estado, _ = evaluar_aplicabilidad(
            convenio,
            {"requiere_convenio_colaboracion": "tal vez"},
        )
        self.assertEqual(estado, "PENDIENTE")
        self.assertEqual(PENDIENTE, "PENDIENTE")


if __name__ == "__main__":
    unittest.main()
