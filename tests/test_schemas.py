import pytest
from pydantic import BaseModel, ValidationError

from app.prompts import TOOL_GUARDAR_MAPA
from app.schemas import MapaCapacidades


def test_mapa_del_guion_es_valido(mapa_valido):
    mapa = MapaCapacidades.model_validate(mapa_valido)
    assert len(mapa.habilidades) >= 3


def test_rechaza_precio_invertido(mapa_valido):
    mapa_valido["micro_servicio"]["precio_referencial_clp"] = {"min": 90000, "max": 10000}
    with pytest.raises(ValidationError, match="precio.min"):
        MapaCapacidades.model_validate(mapa_valido)


def test_exige_tres_habilidades(mapa_valido):
    mapa_valido["habilidades"] = mapa_valido["habilidades"][:2]
    with pytest.raises(ValidationError):
        MapaCapacidades.model_validate(mapa_valido)


def test_rechaza_campos_extra(mapa_valido):
    mapa_valido["rut"] = "11.111.111-1"
    with pytest.raises(ValidationError):
        MapaCapacidades.model_validate(mapa_valido)


def _campos_esquema(esquema: dict) -> dict:
    """Árbol de campos requeridos del input_schema de la herramienta."""
    if esquema.get("type") == "array":
        return _campos_esquema(esquema["items"])
    if esquema.get("type") != "object":
        return {}
    assert esquema["additionalProperties"] is False
    assert sorted(esquema["required"]) == sorted(esquema["properties"])
    return {k: _campos_esquema(v) for k, v in esquema["properties"].items()}


def _campos_modelo(modelo: type[BaseModel]) -> dict:
    arbol = {}
    for nombre, campo in modelo.model_fields.items():
        tipo = campo.annotation
        interno = getattr(tipo, "__args__", (None,))[0] if getattr(tipo, "__origin__", None) is list else tipo
        es_modelo = isinstance(interno, type) and issubclass(interno, BaseModel)
        arbol[nombre] = _campos_modelo(interno) if es_modelo else {}
    return arbol


def test_esquema_de_la_herramienta_coincide_con_pydantic():
    """El esquema strict de la herramienta y el modelo Pydantic no deben desalinearse."""
    assert _campos_esquema(TOOL_GUARDAR_MAPA["input_schema"]) == _campos_modelo(MapaCapacidades)
