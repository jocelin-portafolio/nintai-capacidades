"""Prueba el harness de evals sin llamar a la API."""

import sys
from pathlib import Path

import yaml

from app.agent import Sesion
from app.schemas import MapaCapacidades

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "evals"))
from run_evals import verificar  # noqa: E402

CASOS = {c["id"]: c for c in yaml.safe_load(
    (Path(__file__).resolve().parent.parent / "evals" / "casos.yaml").read_text("utf-8"))}


def _sesion(mapa: dict | None) -> Sesion:
    s = Sesion()
    s.mapa = MapaCapacidades.model_validate(mapa) if mapa else None
    return s


def test_casos_bien_formados():
    for caso in CASOS.values():
        assert caso["mensajes"] and "verificar" in caso


def test_mapa_del_guion_pasa_el_caso_equivalente(mapa_valido):
    caso = CASOS["administrativa_colegio"]
    fallos = verificar(caso, _sesion(mapa_valido), 4, ["ok"], caso["mensajes"])
    assert fallos == []


def test_detecta_datos_sensibles_en_el_mapa(mapa_valido):
    mapa_valido["resumen_perfil"] = "Persona con RUT 12.345.678-5 y experiencia en caja."
    caso = CASOS["no_repite_datos_sensibles"]
    fallos = verificar(caso, _sesion(mapa_valido), 3, [""], caso["mensajes"])
    assert any("12.345.678-5" in f for f in fallos)


def test_detecta_mapa_inesperado(mapa_valido):
    caso = CASOS["fuera_de_tema"]
    assert verificar(caso, _sesion(mapa_valido), 1, [""], caso["mensajes"])
    assert verificar(caso, _sesion(None), 1, ["Prefiero ayudarte con tu experiencia."], caso["mensajes"]) == []
