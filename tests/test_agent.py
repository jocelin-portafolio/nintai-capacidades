from app.agent import AgenteCapacidades, Sesion
from tests.conftest import ClienteFalso, herramienta, respuesta, texto


async def _eventos(agente, sesion, mensaje):
    return [e async for e in agente.responder(sesion, mensaje)]


async def test_turno_de_texto():
    cliente = ClienteFalso(respuesta(texto("¿A qué te has dedicado?")))
    sesion = Sesion()
    eventos = await _eventos(AgenteCapacidades(cliente), sesion, "Hola")

    assert [e["tipo"] for e in eventos] == ["texto", "fin"]
    assert [m["role"] for m in sesion.messages] == ["user", "assistant"]
    assert eventos[-1]["uso"]["output_tokens"] == 50


async def test_parametros_de_la_peticion():
    cliente = ClienteFalso(respuesta(texto("ok")))
    await _eventos(AgenteCapacidades(cliente), Sesion(), "Hola")
    params = cliente.llamadas[0]

    assert params["model"] == "claude-opus-5-5"
    assert params["fallbacks"] == "default"
    assert params["betas"] == ["server-side-fallback-2026-07-01"]
    assert params["thinking"] == {"type": "adaptive"}
    assert params["cache_control"] == {"type": "ephemeral"}
    assert "tool_choice" not in params  # Opus 5.5 no admite tool_choice forzado


async def test_mapa_valido_se_emite_y_se_responde_la_herramienta(mapa_valido):
    cliente = ClienteFalso(
        respuesta(herramienta(mapa_valido), stop_reason="tool_use"),
        respuesta(texto("Listo, tu mapa está en el panel.")),
    )
    sesion = Sesion()
    eventos = await _eventos(AgenteCapacidades(cliente), sesion, "Genera mi mapa")

    tipos = [e["tipo"] for e in eventos]
    assert tipos == ["generando_mapa", "mapa", "texto", "fin"]
    assert sesion.mapa is not None
    resultado = sesion.messages[2]["content"][0]
    assert resultado["tool_use_id"] == "toolu_1" and "is_error" not in resultado


async def test_mapa_invalido_vuelve_al_modelo_como_error(mapa_valido):
    malo = {**mapa_valido, "habilidades": mapa_valido["habilidades"][:1]}
    cliente = ClienteFalso(
        respuesta(herramienta(malo, "toolu_a"), stop_reason="tool_use"),
        respuesta(herramienta(mapa_valido, "toolu_b"), stop_reason="tool_use"),
        respuesta(texto("Corregido.")),
    )
    sesion = Sesion()
    eventos = await _eventos(AgenteCapacidades(cliente), sesion, "Genera mi mapa")

    primer_resultado = sesion.messages[2]["content"][0]
    assert primer_resultado["is_error"] is True
    assert "habilidades" in primer_resultado["content"]
    assert sum(e["tipo"] == "mapa" for e in eventos) == 1


async def test_rechazo_descarta_el_intercambio():
    cliente = ClienteFalso(respuesta(texto("Hola")), respuesta(texto("parcial"), stop_reason="refusal"))
    agente = AgenteCapacidades(cliente)
    sesion = Sesion()
    await _eventos(agente, sesion, "Hola")
    eventos = await _eventos(agente, sesion, "mensaje problemático")

    assert eventos[-2] == {
        "tipo": "error", "descartar": True,
        "mensaje": "No puedo ayudar con ese mensaje. ¿Puedes contarlo de otra forma?",
    }
    assert len(sesion.messages) == 2  # solo queda el primer intercambio


async def test_corte_por_max_tokens_no_usa_el_mapa(mapa_valido):
    cliente = ClienteFalso(
        respuesta(herramienta(mapa_valido), stop_reason="max_tokens"),
        respuesta(texto("Lo intento de nuevo.")),
    )
    sesion = Sesion()
    eventos = await _eventos(AgenteCapacidades(cliente), sesion, "Genera mi mapa")

    assert not any(e["tipo"] == "mapa" for e in eventos)
    assert sesion.messages[2]["content"][0]["is_error"] is True


async def test_el_historial_solo_crece(mapa_valido):
    cliente = ClienteFalso(
        respuesta(texto("Pregunta 1")),
        respuesta(herramienta(mapa_valido), stop_reason="tool_use"),
        respuesta(texto("Listo")),
    )
    agente = AgenteCapacidades(cliente)
    sesion = Sesion()
    await _eventos(agente, sesion, "Hola")
    await _eventos(agente, sesion, "Trabajé en un colegio")

    previos = [ll["messages"] for ll in cliente.llamadas]
    for anterior, siguiente in zip(previos, previos[1:], strict=False):
        assert siguiente[: len(anterior)] == anterior
