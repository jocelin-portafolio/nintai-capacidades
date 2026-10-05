"""API y servidor web del chatbot.

    uvicorn app.main:app --reload
"""

from __future__ import annotations

import os
import uuid
from collections import OrderedDict
from pathlib import Path
from typing import Protocol

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.agent import AgenteCapacidades, Sesion, a_sse

load_dotenv()

WEB = Path(__file__).resolve().parent.parent / "web"
MAX_SESIONES = 500


class Agente(Protocol):
    def responder(self, sesion: Sesion, texto: str): ...


def _modo_demo() -> bool:
    if os.environ.get("NINTAI_DEMO") == "1":
        return True
    return not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


class Mensaje(BaseModel):
    sesion_id: uuid.UUID
    texto: str = Field(min_length=1, max_length=4000)


def crear_app(agente: Agente | None = None, demo: bool | None = None) -> FastAPI:
    demo = _modo_demo() if demo is None else demo
    if agente is None:
        if demo:
            from app.demo import AgenteDemo

            agente = AgenteDemo()
        else:
            agente = AgenteCapacidades()

    app = FastAPI(title="NINTAI · Mapa de capacidades")
    # Sesiones en memoria (demo local). LRU simple para acotar el uso de memoria.
    sesiones: OrderedDict[uuid.UUID, Sesion] = OrderedDict()

    def obtener_sesion(sesion_id: uuid.UUID) -> Sesion:
        if sesion_id not in sesiones:
            sesiones[sesion_id] = Sesion()
            if len(sesiones) > MAX_SESIONES:
                sesiones.popitem(last=False)
        sesiones.move_to_end(sesion_id)
        return sesiones[sesion_id]

    @app.get("/api/estado")
    def estado() -> dict:
        return {"ok": True, "demo": demo}

    @app.post("/api/chat")
    async def chat(mensaje: Mensaje) -> StreamingResponse:
        sesion = obtener_sesion(mensaje.sesion_id)

        async def eventos():
            try:
                async for evento in agente.responder(sesion, mensaje.texto.strip()):
                    yield a_sse(evento)
            except Exception:  # noqa: BLE001 - el detalle queda en el log del servidor
                import logging

                logging.exception("Error en la conversación")
                yield a_sse({"tipo": "error", "mensaje": "Ocurrió un error. Intenta de nuevo."})
                yield a_sse({"tipo": "fin", "uso": sesion.uso.a_dict()})

        return StreamingResponse(eventos(), media_type="text/event-stream")

    @app.delete("/api/sesion/{sesion_id}")
    def borrar_sesion(sesion_id: uuid.UUID) -> dict:
        if sesiones.pop(sesion_id, None) is None:
            raise HTTPException(status_code=404, detail="Sesión no encontrada")
        return {"ok": True}

    @app.get("/")
    def inicio() -> FileResponse:
        return FileResponse(WEB / "index.html")

    app.mount("/", StaticFiles(directory=WEB), name="web")
    return app


app = crear_app()
