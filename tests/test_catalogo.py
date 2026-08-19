from __future__ import annotations

import unittest

from modulos.catalogo import (
    DocumentoCatalogo,
    clasificar_archivo,
    campos_operativos,
    desde_fila,
    extensiones_por_etapa,
)


def documento(
    clave: str,
    codigo: str,
    patron: str | None = None,
    extensiones: tuple[str, ...] = ("pdf",),
) -> DocumentoCatalogo:
    return DocumentoCatalogo(
        id="00000000-0000-0000-0000-000000000001",
        clave_catalogo=clave,
        orden=1,
        procedimiento="LPU",
        etapa=clave[:3],
        tipo_documental="_".join((clave[:3], clave.split("_")[2])),
        codigo_base=codigo,
        nombre="Documento de prueba",
        obligatoriedad="Obligatorio",
        condicion_aplicabilidad="Siempre",
        admite_multiples=patron is not None,
        patron_consecutivo=patron,
        extensiones=extensiones,
    )


class CatalogoTest(unittest.TestCase):
    def test_clasifica_codigo_simple(self):
        contrato = documento("CNT_LPU_CNT", "CNT_LPU_CNT")
        self.assertEqual(
            clasificar_archivo("CNT_LPU_CNT.pdf", [contrato]),
            contrato,
        )

    def test_clasifica_patron_consecutivo_con_extension_heredada(self):
        estimacion = documento(
            "EJE_LPU_EST_1",
            "EJE_LPU_EST_1",
            "EJE_LPU_EST_{n}.pdf",
        )
        self.assertEqual(
            clasificar_archivo("EJE_LPU_EST_17_revision.pdf", [estimacion]),
            estimacion,
        )

    def test_no_clasifica_coincidencia_parcial(self):
        contrato = documento("CNT_LPU_CNT", "CNT_LPU_CNT")
        self.assertIsNone(clasificar_archivo("XCNT_LPU_CNTB.pdf", [contrato]))

    def test_extensiones_unicas_por_etapa(self):
        documentos = [
            documento("CNT_LPU_CNT", "CNT_LPU_CNT", extensiones=("pdf", "docx")),
            documento("CNT_LPU_PTC", "CNT_LPU_PTC", extensiones=("pdf",)),
        ]
        self.assertEqual(extensiones_por_etapa(documentos, "CNT"), ["docx", "pdf"])

    def test_deriva_campos_desde_datos_clave(self):
        convenio = documento("PPP_LPU_CNV", "PPP_LPU_CNV")
        convenio = DocumentoCatalogo(
            **{
                **convenio.__dict__,
                "datos_clave_a_validar": "Partes; objeto; firmas.",
            }
        )
        campos = campos_operativos(convenio)
        self.assertEqual(
            [campo.nombre_tecnico for campo in campos],
            ["partes", "objeto", "firmas"],
        )
        self.assertEqual([campo.orden for campo in campos], [1, 2, 3])

    def test_desde_fila_carga_campos_y_procedimientos(self):
        fila = (
            "id", "CNT_LPU_CNT", 25, "LPU", "CNT", "CNT_CNT",
            "CNT_LPU_CNT", "Contrato", "Obligatorio", "Siempre", False,
            None, ["pdf"], "1.0", "Reconocer contrato", "Número; monto",
            "Ley aplicable",
            [
                {
                    "orden": 1,
                    "nombre_tecnico": "numero",
                    "etiqueta": "Número",
                    "tipo_dato": "Texto",
                    "obligatorio": True,
                    "instruccion": "Extraer el número",
                    "estado_revision": "Pendiente",
                }
            ],
            [
                {
                    "orden": 1,
                    "procedimiento_id": "CNT_CNT_P01",
                    "procedimiento": "Verificar correspondencia",
                    "resultado_esperado": None,
                    "evidencia_requerida": None,
                    "riesgo_codigo": "07_OBP_13",
                    "estado_revision": "Pendiente",
                }
            ],
        )
        definicion = desde_fila(fila)
        self.assertEqual(definicion.campos[0].nombre_tecnico, "numero")
        self.assertEqual(
            definicion.procedimientos[0].procedimiento_id,
            "CNT_CNT_P01",
        )


if __name__ == "__main__":
    unittest.main()
