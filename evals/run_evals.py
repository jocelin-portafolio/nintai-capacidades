"""Evalúa el agente real contra evals/casos.yaml.

    python evals/run_evals.py            # todos los casos
    python evals/run_evals.py cuidadora  # solo los casos cuyo id contiene "cuidadora"

Llama a la API de Claude: cuesta dinero y no es determinista. El resumen queda en
evals/resultados/ultimo.json.
"""

from __future__ import annotations

import asyncio
import json
import re
import statistics
import sys
import time
from pathlib import Path

import yaml
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.agent import AgenteCapacidades, Sesion  # noqa: E402

RAIZ = Path(__file__).resolve().parent
PALABRA = re.compile(r"[a-záéíóúñ]{5,}")


def _texto_mapa(mapa: dict) -> str:
    partes = [json.dumps(mapa["transferibles"]), json.dumps(mapa["rutas"]), json.dumps(mapa["micro_servicio"])]
    return " ".join(partes).lower()


def verificar(caso: dict, sesion: Sesion, turnos: int, respuestas: list[str], usuario: list[str]) -> list[str]:
    v = caso.get("verificar", {})
    fallos: list[str] = []
    mapa = sesion.mapa.model_dump() if sesion.mapa else None

    if "mapa_generado" in v and bool(mapa) != v["mapa_generado"]:
        fallos.append(f"mapa_generado: se esperaba {v['mapa_generado']}")
    if "max_turnos" in v and mapa and turnos > v["max_turnos"]:
        fallos.append(f"max_turnos: {turnos} > {v['max_turnos']}")
    if mapa:
        if len(mapa["habilidades"]) < v.get("min_habilidades", 0):
            fallos.append(f"min_habilidades: {len(mapa['habilidades'])}")
        claves = v.get("palabras_clave")
        if claves and not any(c.lower() in _texto_mapa(mapa) for c in claves):
            fallos.append(f"palabras_clave: ninguna de {claves}")
        if "precio_clp" in v:
            lo, hi = v["precio_clp"]
            p = mapa["micro_servicio"]["precio_referencial_clp"]
            if not (lo <= p["min"] <= p["max"] <= hi):
                fallos.append(f"precio_clp: {p} fuera de [{lo}, {hi}]")
        if "evidencia_anclada" in v:
            vocab = set(PALABRA.findall(" ".join(usuario).lower()))
            ancladas = sum(bool(set(PALABRA.findall(h["evidencia"].lower())) & vocab) for h in mapa["habilidades"])
            fraccion = ancladas / len(mapa["habilidades"])
            if fraccion < v["evidencia_anclada"]:
                fallos.append(f"evidencia_anclada: {fraccion:.0%}")
    todo = (json.dumps(mapa, ensure_ascii=False) if mapa else "") + " ".join(respuestas)
    for prohibido in v.get("no_debe_aparecer", []):
        if prohibido in todo:
            fallos.append(f"no_debe_aparecer: {prohibido}")
    return fallos


async def correr_caso(agente: AgenteCapacidades, caso: dict) -> dict:
    sesion = Sesion()
    respuestas: list[str] = []
    enviados: list[str] = []
    errores: list[str] = []
    mensajes = list(caso["mensajes"])
    if caso.get("cierre"):
        mensajes.append(caso["cierre"])

    inicio = time.perf_counter()
    for mensaje in mensajes:
        enviados.append(mensaje)
        texto = []
        async for ev in agente.responder(sesion, mensaje):
            if ev["tipo"] == "texto":
                texto.append(ev["texto"])
            elif ev["tipo"] == "error":
                errores.append(ev["mensaje"])
        respuestas.append("".join(texto))
        if sesion.mapa:
            break
    latencia = time.perf_counter() - inicio

    fallos = verificar(caso, sesion, len(enviados), respuestas, enviados) + [f"error: {e}" for e in errores]
    return {
        "id": caso["id"],
        "ok": not fallos,
        "fallos": fallos,
        "turnos": len(enviados),
        "latencia_s": round(latencia, 2),
        "costo_usd": round(sesion.uso.costo_usd, 5),
        "tokens": sesion.uso.a_dict(),
        "conversacion": [{"usuario": u, "asistente": a} for u, a in zip(enviados, respuestas, strict=True)],
        "mapa": sesion.mapa.model_dump() if sesion.mapa else None,
    }


async def main() -> None:
    load_dotenv()
    filtro = sys.argv[1] if len(sys.argv) > 1 else ""
    casos = [c for c in yaml.safe_load((RAIZ / "casos.yaml").read_text("utf-8")) if filtro in c["id"]]
    agente = AgenteCapacidades()

    resultados = []
    for caso in casos:
        r = await correr_caso(agente, caso)
        estado = "OK  " if r["ok"] else "FALLA"
        print(f"{estado} {r['id']:<28} {r['turnos']} turnos  {r['latencia_s']:>6}s  US$ {r['costo_usd']:.4f}")
        for f in r["fallos"]:
            print(f"      - {f}")
        resultados.append(r)

    latencias = sorted(r["latencia_s"] for r in resultados)
    resumen = {
        "casos": len(resultados),
        "exitos": sum(r["ok"] for r in resultados),
        "tasa_exito": round(sum(r["ok"] for r in resultados) / max(len(resultados), 1), 3),
        "latencia_p50_s": statistics.median(latencias) if latencias else None,
        "latencia_p95_s": latencias[min(len(latencias) - 1, int(0.95 * len(latencias)))] if latencias else None,
        "costo_medio_usd": round(statistics.mean(r["costo_usd"] for r in resultados), 5) if resultados else None,
        "costo_total_usd": round(sum(r["costo_usd"] for r in resultados), 5),
    }
    print("\n" + json.dumps(resumen, indent=2, ensure_ascii=False))

    salida = RAIZ / "resultados"
    salida.mkdir(exist_ok=True)
    (salida / "ultimo.json").write_text(
        json.dumps({"resumen": resumen, "casos": resultados}, indent=2, ensure_ascii=False), "utf-8"
    )
    sys.exit(0 if resumen["exitos"] == resumen["casos"] else 1)


if __name__ == "__main__":
    asyncio.run(main())
