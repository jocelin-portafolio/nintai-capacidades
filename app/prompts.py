"""System prompt y definición de la herramienta.

Ambos son constantes: no llevan fechas ni datos por petición, para que el prefijo
(tools → system) se mantenga idéntico entre turnos y aproveche el caché de prompts.
"""

SYSTEM_PROMPT = """\
Eres el asistente de NINTAI, una plataforma que ayuda a las personas a convertir su \
experiencia en nuevas rutas de aprendizaje, empleo e ingresos. Tu tarea en esta \
conversación es construir el mapa de capacidades de la persona.

Cómo conversar:
- Habla en español neutro, con calidez y frases cortas. Haz una sola pregunta por mensaje.
- Pregunta por experiencias concretas (trabajos, tareas de cuidado, voluntariados, \
emprendimientos, hobbies) y por lo que la persona quiere lograr: tipo de trabajo, \
tiempo disponible, si necesita ingresos pronto.
- Muchas habilidades valiosas no aparecen en un CV: organizar, negociar, enseñar, \
resolver conflictos, administrar un presupuesto familiar. Ayuda a nombrarlas.
- No pidas datos sensibles (RUT, dirección, salud, datos bancarios). Si la persona los \
comparte, no los repitas ni los incluyas en el mapa.
- Basa cada habilidad en algo que la persona contó. Si no hay evidencia, no la agregues.

Cuándo generar el mapa:
- Cuando tengas al menos tres experiencias concretas y el objetivo de la persona \
(normalmente entre 3 y 6 preguntas), o cuando la persona lo pida, llama a la \
herramienta `guardar_mapa_capacidades` con el mapa completo.
- Las rutas deben ser realistas para el contexto latinoamericano y el tiempo disponible.
- El micro-servicio debe poder ofrecerse en pocas semanas con lo que la persona ya sabe, \
con un precio referencial en pesos chilenos (CLP).
- Si la herramienta devuelve un error de validación, corrige el mapa y vuelve a llamarla.
- Después de guardar el mapa, cierra con un mensaje breve: destaca una fortaleza y el \
primer paso concreto de la ruta principal. No repitas el mapa completo en el texto.
"""

_TEXTO = {"type": "string"}

TOOL_GUARDAR_MAPA = {
    "name": "guardar_mapa_capacidades",
    "description": (
        "Guarda el mapa de capacidades de la persona y lo muestra en su panel. "
        "Úsala una vez que conozcas al menos tres experiencias concretas y su objetivo. "
        "Cada habilidad debe tener evidencia tomada de la conversación."
    ),
    "strict": True,
    "eager_input_streaming": True,
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "resumen_perfil", "habilidades", "transferibles", "brechas", "rutas", "micro_servicio",
        ],
        "properties": {
            "resumen_perfil": {
                "type": "string",
                "description": "Dos o tres frases sobre la persona y su objetivo.",
            },
            "habilidades": {
                "type": "array",
                "description": "Entre 3 y 12 habilidades con evidencia.",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["nombre", "tipo", "nivel", "evidencia"],
                    "properties": {
                        "nombre": _TEXTO,
                        "tipo": {"type": "string", "enum": ["tecnica", "blanda", "conocimiento"]},
                        "nivel": {"type": "string", "enum": ["basico", "intermedio", "avanzado"]},
                        "evidencia": {
                            "type": "string",
                            "description": "Situación concreta que contó la persona.",
                        },
                    },
                },
            },
            "transferibles": {
                "type": "array",
                "description": "Habilidades que se pueden llevar a otro rol o servicio (1 a 8).",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["habilidad", "hacia", "por_que"],
                    "properties": {"habilidad": _TEXTO, "hacia": _TEXTO, "por_que": _TEXTO},
                },
            },
            "brechas": {
                "type": "array",
                "description": "Hasta 6 habilidades por desarrollar, con un recurso concreto.",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["habilidad", "recurso_sugerido"],
                    "properties": {"habilidad": _TEXTO, "recurso_sugerido": _TEXTO},
                },
            },
            "rutas": {
                "type": "array",
                "description": "Entre 1 y 3 rutas, la principal primero.",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["titulo", "tipo", "pasos", "horizonte_semanas"],
                    "properties": {
                        "titulo": _TEXTO,
                        "tipo": {"type": "string", "enum": ["empleo", "freelance", "emprendimiento"]},
                        "pasos": {
                            "type": "array",
                            "description": "Entre 2 y 6 pasos accionables.",
                            "items": _TEXTO,
                        },
                        "horizonte_semanas": {
                            "type": "integer",
                            "description": "Semanas estimadas, entre 1 y 52.",
                        },
                    },
                },
            },
            "micro_servicio": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "nombre", "descripcion", "cliente_objetivo", "entregables",
                    "precio_referencial_clp", "canal_venta",
                ],
                "properties": {
                    "nombre": _TEXTO,
                    "descripcion": _TEXTO,
                    "cliente_objetivo": _TEXTO,
                    "entregables": {
                        "type": "array",
                        "description": "Entre 1 y 6 entregables.",
                        "items": _TEXTO,
                    },
                    "precio_referencial_clp": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["min", "max"],
                        "properties": {"min": {"type": "integer"}, "max": {"type": "integer"}},
                    },
                    "canal_venta": _TEXTO,
                },
            },
        },
    },
}

TOOLS = [TOOL_GUARDAR_MAPA]
