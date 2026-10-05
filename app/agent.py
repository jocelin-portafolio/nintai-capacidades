"""Agente conversacional que construye el mapa de capacidades.

Bucle manual sobre la Messages API con streaming: el texto llega al navegador token a
token y, cuando el modelo llama a `guardar_mapa_capacidades`, el mapa se valida con
Pydantic antes de mostrarse. Si la validación falla, el error vuelve al modelo como
`tool_result` con `is_error` para que lo corrija.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

import anthropic
from pydantic import ValidationError

from app.history import contenido_para_historial
from app.prompts import SYSTEM_PROMPT, TOOLS
from app.schemas import MapaCapacidades

MODEL = os.environ.get("NINTAI_MODEL", "claude-opus-5-5")
EFFORT = os.environ.get("NINTAI_EFFORT", "medium")
# USD por millón de tokens (Claude Opus 5.5). Actualiza si cambias de modelo.
PRECIO_INPUT, PRECIO_OUTPUT, PRECIO_CACHE_READ = 4.0, 20.0, 0.20
FALLBACK_BETA = "server-side-fallback-2026-07-01"
MAX_PASOS = 4          # turnos del modelo por mensaje del usuario
MAX_REINTENTOS_JSON = 2

Evento = dict[str, Any]


@dataclass
class Uso:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    latencia_s: float = 0.0

    @property
    def costo_usd(self) -> float:
        return (
            self.input_tokens * PRECIO_INPUT
            + self.output_tokens * PRECIO_OUTPUT
            + self.cache_read_tokens * PRECIO_CACHE_READ
        ) / 1e6

    def sumar(self, usage: Any) -> None:
        self.input_tokens += usage.input_tokens or 0
        self.output_tokens += usage.output_tokens or 0
        self.cache_read_tokens += getattr(usage, "cache_read_input_tokens", 0) or 0

    def a_dict(self) -> dict[str, Any]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "latencia_s": round(self.latencia_s, 2),
            "costo_usd": round(self.costo_usd, 5),
        }


@dataclass
class Sesion:
    """Estado de una conversación. El historial solo crece (append-only)."""

    messages: list[dict[str, Any]] = field(default_factory=list)
    mapa: MapaCapacidades | None = None
    uso: Uso = field(default_factory=Uso)


def _validar_mapa(entrada: Any) -> tuple[MapaCapacidades | None, str | None]:
    if not isinstance(entrada, dict):
        return None, "La entrada de la herramienta no es un objeto JSON."
    try:
        return MapaCapacidades.model_validate(entrada), None
    except ValidationError as e:
        errores = "; ".join(
            f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in e.errors()
        )
        return None, f"Mapa inválido, corrígelo y vuelve a llamar la herramienta. {errores}"


class AgenteCapacidades:
    def __init__(self, client: anthropic.AsyncAnthropic | None = None) -> None:
        self.client = client or anthropic.AsyncAnthropic()

    async def responder(self, sesion: Sesion, texto: str) -> AsyncIterator[Evento]:
        """Procesa un mensaje del usuario y emite eventos para la interfaz."""
        inicio_turno = len(sesion.messages)
        sesion.messages.append({"role": "user", "content": texto})
        inicio = time.perf_counter()
        reintentos_json = 0
        pasos = 0

        while pasos < MAX_PASOS:
            try:
                async with self.client.beta.messages.stream(
                    model=MODEL,
                    max_tokens=16000,
                    betas=[FALLBACK_BETA],
                    fallbacks="default",
                    thinking={"type": "adaptive"},
                    output_config={"effort": EFFORT},
                    cache_control={"type": "ephemeral"},
                    system=SYSTEM_PROMPT,
                    tools=TOOLS,
                    messages=sesion.messages,
                ) as stream:
                    async for evento in stream:
                        if evento.type == "text":
                            yield {"tipo": "texto", "texto": evento.text}
                        elif (
                            evento.type == "content_block_start"
                            and evento.content_block.type == "tool_use"
                        ):
                            yield {"tipo": "generando_mapa"}
                    respuesta = await stream.get_final_message()
            except ValueError:
                # JSON de herramienta imposible de parsear: no hay tool_use completo que
                # responder, así que se repite el turno (con tope).
                reintentos_json += 1
                if reintentos_json > MAX_REINTENTOS_JSON:
                    yield {"tipo": "error", "mensaje": "No pude generar el mapa. Intenta de nuevo."}
                    break
                continue

            pasos += 1
            sesion.uso.sumar(respuesta.usage)

            if respuesta.stop_reason == "refusal":
                # Se descarta todo el intercambio (y el texto parcial ya mostrado) para que
                # la persona pueda reformular. Solo se recorta la cola: el prefijo enviado
                # en turnos anteriores no cambia.
                del sesion.messages[inicio_turno:]
                yield {
                    "tipo": "error",
                    "descartar": True,
                    "mensaje": "No puedo ayudar con ese mensaje. ¿Puedes contarlo de otra forma?",
                }
                break

            contenido = contenido_para_historial(respuesta.content)
            sesion.messages.append({"role": "assistant", "content": contenido})

            llamadas = [b for b in contenido if b.type == "tool_use"]
            if not llamadas:
                break

            resultados = []
            for bloque in llamadas:
                if respuesta.stop_reason == "max_tokens":
                    mapa, error = None, "La respuesta se cortó antes de terminar el mapa."
                elif bloque.name != "guardar_mapa_capacidades":
                    mapa, error = None, f"Herramienta desconocida: {bloque.name}"
                else:
                    mapa, error = _validar_mapa(bloque.input)

                if mapa is not None:
                    sesion.mapa = mapa
                    yield {"tipo": "mapa", "mapa": mapa.model_dump()}
                    resultados.append({
                        "type": "tool_result",
                        "tool_use_id": bloque.id,
                        "content": "Mapa guardado y visible en el panel de la persona.",
                    })
                else:
                    resultados.append({
                        "type": "tool_result",
                        "tool_use_id": bloque.id,
                        "is_error": True,
                        "content": error or "Error desconocido.",
                    })
            sesion.messages.append({"role": "user", "content": resultados})

        sesion.uso.latencia_s += time.perf_counter() - inicio
        yield {"tipo": "fin", "uso": sesion.uso.a_dict()}


def a_sse(evento: Evento) -> str:
    """Serializa un evento como Server-Sent Event."""
    return f"data: {json.dumps(evento, ensure_ascii=False)}\n\n"
