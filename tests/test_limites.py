import json
import uuid

from fastapi.testclient import TestClient

from app.limites import Limitador
from app.main import crear_app


class Reloj:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def test_limite_por_ip_con_ventana_de_una_hora():
    reloj = Reloj()
    lim = Limitador(max_por_sesion=99, max_por_ip_hora=2, presupuesto_diario_usd=10, reloj=reloj)
    assert lim.verificar("1.1.1.1", 0) is None
    assert lim.verificar("1.1.1.1", 0) is None
    assert lim.verificar("1.1.1.1", 0) is not None
    assert lim.verificar("2.2.2.2", 0) is None  # otra IP no se ve afectada
    reloj.t = 3601
    assert lim.verificar("1.1.1.1", 0) is None


def test_limite_por_sesion():
    lim = Limitador(max_por_sesion=3, max_por_ip_hora=99, presupuesto_diario_usd=10)
    assert lim.verificar("ip", 2) is None
    assert "límite de mensajes" in lim.verificar("ip", 3)


def test_presupuesto_diario():
    lim = Limitador(max_por_sesion=99, max_por_ip_hora=99, presupuesto_diario_usd=0.05)
    lim.registrar_gasto(0.03)
    assert lim.verificar("ip", 0) is None
    lim.registrar_gasto(0.03)
    assert "límite de uso de hoy" in lim.verificar("ip", 0)


class AgenteConCosto:
    async def responder(self, sesion, texto):
        sesion.messages.append({"role": "user", "content": texto})
        sesion.uso.output_tokens += 1000  # US$ 0.02 a precio de salida
        yield {"tipo": "texto", "texto": "ok"}
        yield {"tipo": "fin", "uso": sesion.uso.a_dict()}


def _tipos(r) -> list[str]:
    return [json.loads(l[6:])["tipo"] for l in r.text.split("\n\n") if l.startswith("data: ")]


def test_la_api_aplica_el_presupuesto():
    lim = Limitador(max_por_sesion=99, max_por_ip_hora=99, presupuesto_diario_usd=0.03)
    cliente = TestClient(crear_app(AgenteConCosto(), demo=False, limitador=lim))
    cuerpo = {"sesion_id": str(uuid.uuid4()), "texto": "hola"}
    assert _tipos(cliente.post("/api/chat", json=cuerpo)) == ["texto", "fin"]
    assert _tipos(cliente.post("/api/chat", json=cuerpo)) == ["texto", "fin"]
    assert round(lim.gastado_hoy(), 2) == 0.04
    assert _tipos(cliente.post("/api/chat", json=cuerpo)) == ["error", "fin"]


def test_el_modo_demo_no_tiene_limites():
    lim = Limitador(max_por_sesion=1, max_por_ip_hora=1, presupuesto_diario_usd=0)
    cliente = TestClient(crear_app(demo=True, limitador=lim))
    sesion = str(uuid.uuid4())
    for i in range(3):
        tipos = _tipos(cliente.post("/api/chat", json={"sesion_id": sesion, "texto": f"m{i}"}))
        assert "error" not in tipos
