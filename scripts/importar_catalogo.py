from __future__ import annotations

import argparse
import os
from pathlib import Path

from modulos.importador_catalogo import importar_catalogo, leer_y_validar_catalogo, resumen_json


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Valida e importa una versión del Catálogo Maestro ASEG en Neon."
    )
    parser.add_argument("archivo", type=Path, help="Ruta del archivo .xlsx")
    parser.add_argument(
        "--activar",
        action="store_true",
        help="Convierte la importación validada en la versión activa.",
    )
    parser.add_argument(
        "--solo-validar",
        action="store_true",
        help="No se conecta a la base de datos.",
    )
    args = parser.parse_args()

    resultado = leer_y_validar_catalogo(args.archivo)
    print(resumen_json(resultado))
    if not resultado.valido:
        return 2
    if args.solo_validar:
        return 0

    database_url = (
        os.getenv("DATABASE_URL_ADMIN", "").strip()
        or os.getenv("DATABASE_URL", "").strip()
    )
    if not database_url:
        print(
            "DATABASE_URL_ADMIN o DATABASE_URL no está configurada. "
            "Use --solo-validar o configure la conexión."
        )
        return 3

    importacion_id, ya_existente = importar_catalogo(
        resultado,
        args.archivo.name,
        database_url,
        activar=args.activar,
    )
    estado = "ya estaba activa" if ya_existente else "se importó correctamente"
    print(f"La importación {importacion_id} {estado}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
