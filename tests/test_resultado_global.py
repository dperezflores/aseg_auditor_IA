from __future__ import annotations

import unittest

from modulos.motor_catalogo import resultado_global


class ResultadoGlobalTest(unittest.TestCase):
    def test_no_cumple_domina_el_resultado(self):
        datos = [{
            "identificacion": {"corresponde": "SI"},
            "procedimientos": [
                {"resultado": "CUMPLE"},
                {"resultado": "NO_CUMPLE"},
            ],
        }]
        self.assertEqual(resultado_global(datos[0]), "NO_CUMPLE")

    def test_falta_de_evidencia_exige_revision(self):
        datos = [{
            "identificacion": {"corresponde": "SI"},
            "procedimientos": [{"resultado": "NO_DETERMINABLE"}],
        }]
        self.assertEqual(resultado_global(datos[0]), "REVISION_REQUERIDA")

    def test_cumple_y_no_aplica_es_cumple(self):
        datos = [{
            "identificacion": {"corresponde": "SI"},
            "procedimientos": [
                {"resultado": "CUMPLE"},
                {"resultado": "NO_APLICA"},
            ],
        }]
        self.assertEqual(resultado_global(datos[0]), "CUMPLE")


if __name__ == "__main__":
    unittest.main()
