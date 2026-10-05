from app.history import contenido_para_historial


def test_sin_fallback_no_cambia_nada():
    contenido = [{"type": "thinking"}, {"type": "text"}, {"type": "tool_use"}]
    assert contenido_para_historial(contenido) == contenido


def test_omite_bloques_internos_antes_del_fallback():
    contenido = [
        {"type": "thinking", "id": 1},
        {"type": "text", "id": 2},
        {"type": "tool_use", "id": 3},
        {"type": "fallback", "id": 4},
        {"type": "thinking", "id": 5},
        {"type": "text", "id": 6},
    ]
    assert [b["id"] for b in contenido_para_historial(contenido)] == [2, 4, 5, 6]


def test_usa_el_ultimo_fallback_como_limite():
    contenido = [
        {"type": "fallback", "id": 1},
        {"type": "tool_use", "id": 2},
        {"type": "fallback", "id": 3},
        {"type": "tool_use", "id": 4},
    ]
    assert [b["id"] for b in contenido_para_historial(contenido)] == [1, 3, 4]
