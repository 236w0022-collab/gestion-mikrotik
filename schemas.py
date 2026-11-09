from pydantic import BaseModel
from datetime import date
from typing import Optional

# Esquemas para Cliente
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

# Esquemas para Usuario
class UserBase(BaseModel):
    username: str

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: int

    class Config:
        from_attributes = True
        