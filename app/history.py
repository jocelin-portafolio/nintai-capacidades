"""Reglas para devolver al historial el contenido de una respuesta.

Con `fallbacks: "default"`, si el modelo principal declina a mitad de la respuesta, el
contenido trae un bloque `fallback` que marca el cambio de modelo. Antes de ese límite
solo se pueden reenviar los bloques de texto: los de razonamiento y de llamadas a
herramientas del intento declinado deben omitirse.
"""

from __future__ import annotations

from typing import Any

_OMITIR_ANTES_DEL_FALLBACK = {"thinking", "redacted_thinking", "tool_use", "server_tool_use"}


def _tipo(bloque: Any) -> str:
    return bloque["type"] if isinstance(bloque, dict) else bloque.type


def contenido_para_historial(contenido: list[Any]) -> list[Any]:
    """Devuelve los bloques que se pueden reenviar al API en el siguiente turno."""
    indices = [i for i, b in enumerate(contenido) if _tipo(b) == "fallback"]
    if not indices:
        return list(contenido)
    limite = indices[-1]
    antes = [b for b in contenido[:limite] if _tipo(b) not in _OMITIR_ANTES_DEL_FALLBACK]
    return antes + list(contenido[limite:])
