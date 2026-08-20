from __future__ import annotations

import io
import unittest

import pandas as pd

from modulos.generador_excel import (
    COLUMNAS_COMPROBANTES,
    COLUMNAS_ESTIMACIONES,
    COLUMNAS_FACTURAS,
    COLUMNAS_POLIZAS_DEVENGO,
    COLUMNAS_POLIZAS_PAGO,
    reporte_comprobantes,
    reporte_estimaciones,
    reporte_facturas,
    reporte_polizas,
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

    def test_facturas_y_comprobantes_ordenan_columnas_y_fechas(self):
        facturas, _ = reporte_facturas([
            {"Monto total": 2, "Fecha": "2026-02-02", "Folio": "F2", "Descripción": "B", "Archivo Origen": "2.pdf"},
            {"Archivo Origen": "1.pdf", "Descripción": "A", "Folio": "F1", "Fecha": "2026-01-01", "Monto total": 1},
        ])
        self.assertEqual(list(facturas.columns), COLUMNAS_FACTURAS)
        self.assertEqual(list(facturas["Folio"][:2]), ["F1", "F2"])

        comprobantes, _ = reporte_comprobantes([
            {"Importe": 2, "Fecha de pago": "2026-03-02", "Número": "2"},
            {"Número": "1", "Fecha de pago": "2026-03-01", "Importe": 1},
        ])
        self.assertEqual(list(comprobantes.columns), COLUMNAS_COMPROBANTES)
        self.assertEqual(list(comprobantes["Número"][:2]), ["1", "2"])

    def test_polizas_imponen_orden_y_fecha_ascendente(self):
        datos = [
            {"Tipo de poliza": "DEVENGO", "Fecha": "2026-02-01", "Numero de estimacion": "EST 2", "Importe": 2},
            {"Importe": 1, "Numero de estimacion": "EST 1", "Fecha": "2026-01-01", "Tipo de poliza": "DEVENGO"},
            {"Tipo de poliza": "PAGO", "Fecha": "2026-02-03", "Numero de estimacion": "EST 2", "Importe": 2},
            {"Tipo de poliza": "PAGO", "Fecha": "2026-01-03", "Numero de estimacion": "EST 1", "Importe": 1},
        ]
        devengo, pago, _ = reporte_polizas(datos)
        self.assertEqual(list(devengo.columns), COLUMNAS_POLIZAS_DEVENGO)
        self.assertEqual(list(pago.columns), COLUMNAS_POLIZAS_PAGO)
        self.assertEqual(list(devengo["Numero de estimacion"][:2]), ["EST 1", "EST 2"])
        self.assertEqual(list(pago["Numero de estimacion"][:2]), ["EST 1", "EST 2"])


if __name__ == "__main__":
    unittest.main()
