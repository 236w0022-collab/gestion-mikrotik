from pydantic import BaseModel
from datetime import date

class ClienteCreate(BaseModel):
    nombre: str
    telefono: str | None = None
    ip_estatica: str
    fecha_corte: date
    plan_id: int