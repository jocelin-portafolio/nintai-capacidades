"""Agente de demostración sin IA.

Reproduce `web/guion-demo.json` para mostrar el flujo completo sin clave de API.
Se activa con `NINTAI_DEMO=1` o automáticamente si no hay credenciales.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from pathlib import Path

from app.agent import Evento, Sesion
from app.schemas import MapaCapacidades

GUION = json.loads(
    (Path(__file__).resolve().parent.parent / "web" / "guion-demo.json").read_text(encoding="utf-8")
)
# El guion se valida al importar: si alguien lo edita mal, falla en el arranque.
MAPA_DEMO = MapaCapacidades.model_validate(GUION["mapa"])


class AgenteDemo:
    async def responder(self, sesion: Sesion, texto: str) -> AsyncIterator[Evento]:
        sesion.messages.append({"role": "user", "content": texto})
        turnos_usuario = sum(m["role"] == "user" for m in sesion.messages)
        turno = GUION["turnos"][min(turnos_usuario, len(GUION["turnos"])) - 1]
        if turno.get("generando"):
            yield {"tipo": "generando_mapa"}
            await asyncio.sleep(0.4)
            sesion.mapa = MAPA_DEMO
            yield {"tipo": "mapa", "mapa": MAPA_DEMO.model_dump()}
        for palabra in turno["asistente"].split(" "):
            yield {"tipo": "texto", "texto": palabra + " "}
            await asyncio.sleep(0.02)
        sesion.messages.append({"role": "assistant", "content": turno["asistente"]})
        yield {"tipo": "fin", "uso": sesion.uso.a_dict(), "demo": True}
