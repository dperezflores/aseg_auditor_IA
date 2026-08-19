from __future__ import annotations

import io
import unittest

import pandas as pd

from modulos.generador_excel import (
    COLUMNAS_ESTIMACIONES,
    reporte_estimaciones,
)


class GeneradorExcelTest(unittest.TestCase):
    def test_estimaciones_mantienen_orden_aunque_json_llegue_desordenado(self):
        estimacion_desordenada = {
            "IVA": 160.0,
            "Sancion": 0.0,
            "Retencion": 10.0,
            "Deducciones": 20.0,
            "Amortización": 100.0,
            "Importe con IVA": 1160.0,
            "Importe sin IVA": 1000.0,
            "Importe de anticipo": 300.0,
            "Numero de estimación": "EST. 2",
            "De (Periodo de ejecución)": "2026-02-01",
            "Hasta (Periodo de ejecución)": "2026-02-28",
            "Fecha de elaboración o de estimación": "2026-03-05",
            "Archivo Origen": "EJE_LPU_EST_2.pdf",
        }
        estimacion_otro_orden = {
            "Numero de estimación": "EST. 1",
            "Fecha de elaboración o de estimación": "2026-02-05",
            "De (Periodo de ejecución)": "2026-01-01",
            "Hasta (Periodo de ejecución)": "2026-01-31",
            "Importe sin IVA": 500.0,
            "IVA": 80.0,
            "Importe con IVA": 580.0,
            "Importe de anticipo": 300.0,
            "Amortización": 50.0,
            "Deducciones": 10.0,
            "Sancion": 0.0,
            "Retencion": 5.0,
            "Archivo Origen": "EJE_LPU_EST_1.pdf",
        }

        tabla, archivo_excel = reporte_estimaciones(
            [estimacion_desordenada, estimacion_otro_orden]
        )

        self.assertEqual(list(tabla.columns), COLUMNAS_ESTIMACIONES)
        self.assertEqual(
            list(pd.read_excel(io.BytesIO(archivo_excel)).columns),
            COLUMNAS_ESTIMACIONES,
        )
        self.assertEqual(
            list(tabla["Numero de estimación"]),
            ["EST. 1", "EST. 2"],
        )


if __name__ == "__main__":
    unittest.main()
