from datetime import datetime
import os

from database import Base, engine, get_db
from fastapi import Depends, FastAPI, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import models
from sqlalchemy.orm import Session

# 1. Crear automáticamente las tablas en PostgreSQL si no existen al iniciar
Base.metadata.create_all(bind=engine)

app = FastAPI(title="WISP Management Panel")

# Configurar archivos estáticos y plantillas
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

TOKEN_AGENTE_SECRETO = os.getenv("AGENT_TOKEN", "MI_CLAVE_SUPER_SECRETA_123")


# ==========================================
# RUTAS PARA EL PANEL WEB (USUARIOS)
# ==========================================


@app.get("/", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db)):
  # Redirigir a login o cargar panel principal
  clientes = db.query(models.Cliente).all() if hasattr(models, "Cliente") else []

  # Sintaxis corregida compatible con todas las versiones de FastAPI / Starlette
  return templates.TemplateResponse(
      request=request, name="index.html", context={"clientes": clientes}
  )


# Ejemplo de ruta para suspender servicio (Encolar orden)
@app.post("/clientes/{cliente_id}/suspender")
def suspender_cliente(cliente_id: int, db: Session = Depends(get_db)):
  cliente = (
      db.query(models.Cliente).filter(models.Cliente.id == cliente_id).first()
  )
  if not cliente:
    raise HTTPException(status_code=404, detail="Cliente no encontrado")

  # Cambiar estado del cliente
  cliente.estado = "SUSPENDIDO"

  # Crear orden pendiente para el agente local
  nueva_orden = models.OrdenAgente(
      cliente_ip=cliente.ip, accion="SUSPENDER", estado="PENDIENTE"
  )
  db.add(nueva_orden)
  db.commit()

  return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)


# Ejemplo de ruta para reactivar servicio (Encolar orden)
@app.post("/clientes/{cliente_id}/reactivar")
def reactivar_cliente(cliente_id: int, db: Session = Depends(get_db)):
  cliente = (
      db.query(models.Cliente).filter(models.Cliente.id == cliente_id).first()
  )
  if not cliente:
    raise HTTPException(status_code=404, detail="Cliente no encontrado")

  cliente.estado = "ACTIVO"

  # Crear orden pendiente para el agente local
  nueva_orden = models.OrdenAgente(
      cliente_ip=cliente.ip,
      accion="REACTIVAR",
      velocidad_subida=(
          cliente.plan.subida if hasattr(cliente, "plan") else "5M"
      ),
      velocidad_bajada=(
          cliente.plan.bajada if hasattr(cliente, "plan") else "10M"
      ),
      estado="PENDIENTE",
  )
  db.add(nueva_orden)
  db.commit()

  return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)


# ==========================================
# ENDPOINTS PARA EL AGENTE LOCAL (UBUNTU)
# ==========================================


@app.get("/api/agente/ordenes-pendientes")
def obtener_ordenes_pendientes(token: str, db: Session = Depends(get_db)):
  if token != TOKEN_AGENTE_SECRETO:
    raise HTTPException(status_code=401, detail="Token no válido")

  ordenes = (
      db.query(models.OrdenAgente)
      .filter(models.OrdenAgente.estado == "PENDIENTE")
      .all()
  )

  resultado = []
  for o in ordenes:
    resultado.append({
        "id": o.id,
        "cliente_ip": o.cliente_ip,
        "accion": o.accion,
        "velocidad_subida": o.velocidad_subida,
        "velocidad_bajada": o.velocidad_bajada,
    })
  return resultado


@app.post("/api/agente/confirmar-orden/{orden_id}")
def confirmar_orden(orden_id: int, token: str, db: Session = Depends(get_db)):
  if token != TOKEN_AGENTE_SECRETO:
    raise HTTPException(status_code=401, detail="Token no válido")

  orden = (
      db.query(models.OrdenAgente)
      .filter(models.OrdenAgente.id == orden_id)
      .first()
  )
  if not orden:
    raise HTTPException(status_code=404, detail="Orden no encontrada")

  orden.estado = "PROCESADO"
  db.commit()
  return {"status": "ok", "message": f"Orden {orden_id} marcada como procesada"}