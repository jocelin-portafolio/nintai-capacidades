"""Límites de uso para un despliegue público.

Protegen la clave de API de abusos: mensajes por sesión, mensajes por IP en una
ventana de una hora y un presupuesto diario global en dólares. Todo vive en memoria,
suficiente para una sola instancia (el plan gratuito de Render, por ejemplo).
"""

from __future__ import annotations

import os
import time
from collections import defaultdict, deque
from datetime import UTC, datetime


def _float(nombre: str, defecto: float) -> float:
    try:
        return float(os.environ.get(nombre, defecto))
    except ValueError:
        return defecto


class Limitador:
    def __init__(
        self,
        max_por_sesion: int | None = None,
        max_por_ip_hora: int | None = None,
        presupuesto_diario_usd: float | None = None,
        reloj=time.monotonic,
    ) -> None:
        self.max_por_sesion = max_por_sesion or int(_float("NINTAI_MAX_MENSAJES_SESION", 20))
        self.max_por_ip_hora = max_por_ip_hora or int(_float("NINTAI_MAX_MENSAJES_IP_HORA", 40))
        self.presupuesto = (
            presupuesto_diario_usd
            if presupuesto_diario_usd is not None
            else _float("NINTAI_PRESUPUESTO_DIARIO_USD", 2.0)
        )
        self._reloj = reloj
        self._por_ip: dict[str, deque[float]] = defaultdict(deque)
        self._dia = self._hoy()
        self._gastado = 0.0

    @staticmethod
    def _hoy() -> str:
        return datetime.now(UTC).strftime("%Y-%m-%d")

    def gastado_hoy(self) -> float:
        if self._hoy() != self._dia:
            self._dia, self._gastado = self._hoy(), 0.0
        return self._gastado

    def verificar(self, ip: str, mensajes_sesion: int) -> str | None:
        """Devuelve un mensaje para la persona si debe rechazarse, o None si puede seguir."""
        if self.gastado_hoy() >= self.presupuesto:
            return "La demo alcanzó su límite de uso de hoy. Vuelve mañana o prueba el modo demo."
        if mensajes_sesion >= self.max_por_sesion:
            return "Esta conversación llegó a su límite de mensajes. Empieza una nueva."
        ahora = self._reloj()
        ventana = self._por_ip[ip]
        while ventana and ahora - ventana[0] > 3600:
            ventana.popleft()
        if len(ventana) >= self.max_por_ip_hora:
            return "Enviaste muchos mensajes en poco tiempo. Intenta de nuevo en un rato."
        ventana.append(ahora)
        return None

    def registrar_gasto(self, usd: float) -> None:
        self.gastado_hoy()
        self._gastado += max(usd, 0.0)
