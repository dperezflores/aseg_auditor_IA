from __future__ import annotations

import unittest

from modulos.catalogo import DocumentoCatalogo, clasificar_archivo, extensiones_por_etapa


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


if __name__ == "__main__":
    unittest.main()

