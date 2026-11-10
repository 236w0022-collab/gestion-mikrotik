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

class ClienteCreate(ClienteBase):
    pass

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
        