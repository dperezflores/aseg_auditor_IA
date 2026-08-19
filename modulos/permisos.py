from __future__ import annotations

import os
from dataclasses import dataclass

import streamlit as st


ADMIN_GENERAL = "ADMIN_GENERAL"
ADMIN_CATALOGO = "ADMIN_CATALOGO"
APROBADOR_CATALOGO = "APROBADOR_CATALOGO"


def _secreto(nombre: str, default: str = "") -> str:
    try:
        return str(st.secrets.get(nombre, default))
    except Exception:
        return os.getenv(nombre, default)


def administradores_iniciales() -> set[str]:
    return {
        valor.strip()
        for valor in _secreto("APP_ADMIN_IDS", "").split(",")
        if valor.strip()
    }


@dataclass(frozen=True)
class AccesoUsuario:
    usuario_externo: str
    roles: frozenset[str]

    def tiene(self, *roles: str) -> bool:
        return bool(self.roles.intersection(roles))

    @property
    def administra_catalogo(self) -> bool:
        return self.tiene(ADMIN_GENERAL, ADMIN_CATALOGO, APROBADOR_CATALOGO)

    @property
    def publica_catalogo(self) -> bool:
        return self.tiene(ADMIN_GENERAL, APROBADOR_CATALOGO)


def acceso_actual(usuario_externo: str) -> AccesoUsuario:
    roles: set[str] = set()
    if usuario_externo in administradores_iniciales():
        roles.add(ADMIN_GENERAL)

    try:
        from modulos import persistencia

        if persistencia.disponible():
            roles.update(persistencia.cargar_roles_usuario(usuario_externo))
    except Exception:
        # El secreto de arranque sigue permitiendo administrar durante el
        # primer despliegue o una migración pendiente.
        pass
    return AccesoUsuario(usuario_externo, frozenset(roles))
