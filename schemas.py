from pydantic import BaseModel
from typing import Optional, Union
from datetime import date

class PlanResponse(BaseModel):
    id: int
    nombre: str
    velocidad_subida: Union[str, int]
    velocidad_bajada: Union[str, int]

    class Config:
        from_attributes = True

class ClienteCreate(BaseModel):
    nombre: str
    telefono: str
    ip_estatica: str
    fecha_corte: Union[str, date]
    plan_id: int
    zona_id: Optional[int] = None
    activo: bool = True

class ClienteUpdate(BaseModel):
    nombre: Optional[str] = None
    telefono: Optional[str] = None
    ip_estatica: Optional[str] = None
    fecha_corte: Optional[Union[str, date]] = None
    plan_id: Optional[int] = None
    zona_id: Optional[int] = None

class ClienteResponse(BaseModel):
    id: int
    nombre: str
    telefono: str
    ip_estatica: str
    fecha_corte: Union[str, date]
    activo: bool
    plan_id: int
    zona_id: Optional[int] = None

    class Config:
        from_attributes = True