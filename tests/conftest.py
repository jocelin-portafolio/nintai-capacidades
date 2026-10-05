"""Cliente falso de la Messages API para probar el bucle del agente sin red ni costo."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

GUION = json.loads((Path(__file__).resolve().parent.parent / "web" / "guion-demo.json").read_text("utf-8"))


@pytest.fixture
def mapa_valido() -> dict:
    return copy.deepcopy(GUION["mapa"])


def texto(t: str) -> SimpleNamespace:
    return SimpleNamespace(type="text", text=t)


def herramienta(entrada: dict, id_: str = "toolu_1", nombre: str = "guardar_mapa_capacidades"):
    return SimpleNamespace(type="tool_use", id=id_, name=nombre, input=entrada)


def respuesta(*bloques, stop_reason: str = "end_turn", entrada: int = 100, salida: int = 50):
    return SimpleNamespace(
        content=list(bloques),
        stop_reason=stop_reason,
        usage=SimpleNamespace(input_tokens=entrada, output_tokens=salida, cache_read_input_tokens=0),
    )


class _Stream:
    def __init__(self, final):
        self.final = final

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def __aiter__(self):
        return self._eventos()

    async def _eventos(self):
        for b in self.final.content:
            if b.type == "text":
                yield SimpleNamespace(type="text", text=b.text)
            elif b.type == "tool_use":
                yield SimpleNamespace(type="content_block_start", content_block=b)

    async def get_final_message(self):
        return self.final


class ClienteFalso:
    """Devuelve las respuestas en orden y guarda los parámetros de cada llamada."""

    def __init__(self, *respuestas):
        self.respuestas = list(respuestas)
        self.llamadas: list[dict] = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(stream=self._stream))

    def _stream(self, **kwargs):
        # Copia del historial en el momento de la llamada (el agente lo sigue modificando).
        self.llamadas.append({**kwargs, "messages": list(kwargs["messages"])})
        return _Stream(self.respuestas.pop(0))
