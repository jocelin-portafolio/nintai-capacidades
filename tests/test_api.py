import json
import uuid

from fastapi.testclient import TestClient

from app.main import crear_app


class AgenteEco:
    async def responder(self, sesion, texto):
        sesion.messages.append({"role": "user", "content": texto})
        yield {"tipo": "texto", "texto": f"eco: {texto}"}
        yield {"tipo": "fin", "uso": sesion.uso.a_dict()}


def _sse(cuerpo: str) -> list[dict]:
    return [json.loads(l[6:]) for l in cuerpo.split("\n\n") if l.startswith("data: ")]


def test_estado_informa_el_modo():
    cliente = TestClient(crear_app(AgenteEco(), demo=True))
    assert cliente.get("/api/estado").json() == {"ok": True, "demo": True}


def test_chat_transmite_eventos_sse():
    cliente = TestClient(crear_app(AgenteEco(), demo=False))
    r = cliente.post("/api/chat", json={"sesion_id": str(uuid.uuid4()), "texto": "hola"})
    assert r.headers["content-type"].startswith("text/event-stream")
    assert _sse(r.text)[0] == {"tipo": "texto", "texto": "eco: hola"}


def test_valida_la_entrada():
    cliente = TestClient(crear_app(AgenteEco(), demo=False))
    assert cliente.post("/api/chat", json={"sesion_id": "no-es-uuid", "texto": "x"}).status_code == 422
    assert cliente.post("/api/chat", json={"sesion_id": str(uuid.uuid4()), "texto": ""}).status_code == 422
    largo = "a" * 4001
    assert cliente.post("/api/chat", json={"sesion_id": str(uuid.uuid4()), "texto": largo}).status_code == 422


def test_errores_del_agente_no_rompen_el_stream():
    class AgenteRoto:
        async def responder(self, sesion, texto):
            raise RuntimeError("boom")
            yield  # pragma: no cover

    cliente = TestClient(crear_app(AgenteRoto(), demo=False))
    eventos = _sse(cliente.post("/api/chat", json={"sesion_id": str(uuid.uuid4()), "texto": "hola"}).text)
    assert [e["tipo"] for e in eventos] == ["error", "fin"]
    assert "boom" not in eventos[0]["mensaje"]


def test_demo_del_servidor_entrega_el_mapa():
    cliente = TestClient(crear_app(demo=True))
    sesion = str(uuid.uuid4())
    tipos = []
    for i in range(4):
        r = cliente.post("/api/chat", json={"sesion_id": sesion, "texto": f"m{i}"})
        tipos.append([e["tipo"] for e in _sse(r.text)])
    assert all("mapa" not in t for t in tipos[:3])
    assert "mapa" in tipos[3]


def test_sirve_la_interfaz():
    cliente = TestClient(crear_app(AgenteEco(), demo=True))
    assert "NINTAI" in cliente.get("/").text
    assert cliente.get("/guion-demo.json").status_code == 200
