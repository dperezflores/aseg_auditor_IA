from __future__ import annotations

import unittest
from types import SimpleNamespace

from modulos.aplicabilidad import resolver_archivo_disponible


class ArchivoDisponibleTest(unittest.TestCase):
    def test_recupera_archivo_por_huella_aunque_el_nombre_cambie(self):
        esperado = object()
        conciliados = [SimpleNamespace(nombre="contrato.pdf", huella="abc123")]
        disponibles = [
            {"nombre": "otro-nombre.pdf", "huella": "abc123", "archivo": esperado}
        ]

        self.assertIs(
            resolver_archivo_disponible(conciliados, disponibles),
            esperado,
        )

    def test_usa_nombre_como_respaldo_si_el_registro_no_tiene_huella(self):
        esperado = object()
        conciliados = [SimpleNamespace(nombre="CNT_DIR_CNT.PDF", huella="")]
        disponibles = [
            {"nombre": "cnt_dir_cnt.pdf", "huella": "nueva", "archivo": esperado}
        ]

        self.assertIs(
            resolver_archivo_disponible(conciliados, disponibles),
            esperado,
        )

    def test_no_reutiliza_un_archivo_distinto(self):
        conciliados = [SimpleNamespace(nombre="contrato.pdf", huella="abc123")]
        disponibles = [
            {"nombre": "garantia.pdf", "huella": "xyz789", "archivo": object()}
        ]

        self.assertIsNone(
            resolver_archivo_disponible(conciliados, disponibles)
        )


if __name__ == "__main__":
    unittest.main()
