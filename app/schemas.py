"""Modelo de datos del mapa de capacidades.

El esquema JSON de la herramienta se genera a mano (ver `prompts.py`) para cumplir las
reglas de `strict: true`; este módulo valida lo que el modelo devuelve antes de usarlo.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Habilidad(_Base):
    nombre: str = Field(min_length=2)
    tipo: Literal["tecnica", "blanda", "conocimiento"]
    nivel: Literal["basico", "intermedio", "avanzado"]
    evidencia: str = Field(min_length=5, description="Situación concreta contada por la persona.")


class Transferible(_Base):
    habilidad: str
    hacia: str = Field(description="Rol, área o tipo de servicio donde se puede aplicar.")
    por_que: str


class Brecha(_Base):
    habilidad: str
    recurso_sugerido: str


class Ruta(_Base):
    titulo: str
    tipo: Literal["empleo", "freelance", "emprendimiento"]
    pasos: list[str] = Field(min_length=2, max_length=6)
    horizonte_semanas: int = Field(ge=1, le=52)


class Precio(_Base):
    min: int = Field(ge=0)
    max: int = Field(ge=0)

    @model_validator(mode="after")
    def _rango(self) -> Precio:
        if self.min > self.max:
            raise ValueError("precio.min no puede ser mayor que precio.max")
        return self


class MicroServicio(_Base):
    nombre: str
    descripcion: str
    cliente_objetivo: str
    entregables: list[str] = Field(min_length=1, max_length=6)
    precio_referencial_clp: Precio
    canal_venta: str


class MapaCapacidades(_Base):
    resumen_perfil: str = Field(min_length=10)
    habilidades: list[Habilidad] = Field(min_length=3, max_length=12)
    transferibles: list[Transferible] = Field(min_length=1, max_length=8)
    brechas: list[Brecha] = Field(max_length=6)
    rutas: list[Ruta] = Field(min_length=1, max_length=3)
    micro_servicio: MicroServicio
