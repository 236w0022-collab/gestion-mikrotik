from pydantic import BaseModel
from datetime import date
from typing import Optional

# --- Esquemas de Planes ---
class PlanBase(BaseModel):
    nombre: str
    velocidad_bajada: int
    velocidad_subida: int

class PlanResponse(PlanBase):
    id: int

    class Config:
        from_attributes = True

# --- Esquemas de Clientes ---
class ClienteBase(BaseModel):
    nombre: str
    telefono: Optional[str] = None
    ip_estatica: str
    fecha_corte: date
    plan_id: int
    activo: Optional[bool] = True

class ClienteCreate(ClienteBase):
    pass

class ClienteUpdate(BaseModel):
    nombre: Optional[str] = None
    telefono: Optional[str] = None
    ip_estatica: Optional[str] = None
    fecha_corte: Optional[date] = None
    plan_id: Optional[int] = None
    activo: Optional[bool] = None

class ClienteResponse(ClienteBase):
    id: int

    class Config:
        from_attributes = True

# --- Esquemas de Usuarios ---
class UserBase(BaseModel):
    username: str

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: int

    class Config:
        from_attributes = True
        