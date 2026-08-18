from __future__ import annotations

import unittest

from modulos.catalogo import DocumentoCatalogo, ProcedimientoCatalogo
from modulos.motor_catalogo import construir_prompt, normalizar_resultado


def convenio() -> DocumentoCatalogo:
    return DocumentoCatalogo(
        id="00000000-0000-0000-0000-000000000001",
        clave_catalogo="PPP_LPU_CNV",
        orden=1,
        procedimiento="LPU",
        etapa="PPP",
        tipo_documental="PPP_CNV",
        codigo_base="PPP_LPU_CNV",
        nombre="Convenios de colaboración y sus anexos",
        obligatoriedad="Condicional",
        condicion_aplicabilidad="Cuando exista colaboración institucional.",
        admite_multiples=False,
        patron_consecutivo=None,
        extensiones=("pdf",),
        version_catalogo="1.0",
        criterios_identificacion_ia="Identificar partes, objeto, vigencia y firmas.",
        datos_clave_a_validar="Partes; objeto; vigencia; firmas.",
        fundamento_normativo="Ley, artículos de referencia.",
        procedimientos=(
            ProcedimientoCatalogo(
                orden=1,
                procedimiento_id="PPP_CNV_P01",
                procedimiento="Verificar correspondencia con la obra",
                resultado_esperado=None,
                evidencia_requerida=None,
                riesgo_codigo="07_OBP_27",
            ),
        ),
    )


class MotorCatalogoTest(unittest.TestCase):
    def test_prompt_incluye_reglas_del_catalogo(self):
        prompt = construir_prompt(convenio())
        self.assertIn("PPP_LPU_CNV", prompt)
        self.assertIn("Identificar partes, objeto, vigencia y firmas", prompt)
        self.assertIn('"nombre_tecnico": "partes"', prompt)
        self.assertIn("PPP_CNV_P01", prompt)

    def test_normalizacion_impone_orden_y_completa_ausentes(self):
        resultado = normalizar_resultado(
            convenio(),
            {
                "identificacion": {
                    "corresponde": "SI",
                    "tipo_detectado": "Convenio",
                    "justificacion": "Se identificaron las partes y el objeto.",
                    "paginas": [2, "2", 0],
                },
                "datos_extraidos": [
                    {
                        "nombre_tecnico": "objeto",
                        "valor": "Ejecutar la obra",
                        "encontrado": True,
                        "evidencia": "Objeto localizado",
                        "paginas": [3],
                        "confianza": "Alta",
                    }
                ],
                "procedimientos": [],
                "conclusion": "Requiere revisión humana.",
                "advertencias": [],
            },
        )
        self.assertEqual(
            [dato["nombre_tecnico"] for dato in resultado["datos_extraidos"]],
            ["partes", "objeto", "vigencia", "firmas"],
        )
        self.assertEqual(resultado["datos_extraidos"][0]["encontrado"], False)
        self.assertEqual(resultado["datos_extraidos"][1]["valor"], "Ejecutar la obra")
        self.assertEqual(resultado["identificacion"]["paginas"], [2])
        self.assertEqual(
            resultado["procedimientos"][0]["resultado"],
            "NO_DETERMINABLE",
        )


if __name__ == "__main__":
    unittest.main()
