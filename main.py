from datetime import date
from pathlib import Path
import bcrypt

from database import get_db
from fastapi import Depends, FastAPI, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from mikrotik import (
    aplicar_limite_velocidad,
    obtener_conexion_mikrotik,
    remover_queue_mikrotik,
)
from models import ClienteCreate
from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

app = FastAPI(
    title="Sistema de Gestión WISP / Comunidad",
    description="Panel de Control para Empleados",
    version="1.4.0",
)

SECRET_KEY = "tu_clave_secreta_super_segura_mikrotik"
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

BASE_DIR = Path(__file__).resolve().parent

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


def hash_password(password: str) -> str:
  pwd_bytes = password.encode("utf-8")
  salt = bcrypt.gensalt()
  return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
  password_byte_enc = plain_password.encode("utf-8")
  hashed_password_bytes = hashed_password.encode("utf-8")
  return bcrypt.checkpw(password_byte_enc, hashed_password_bytes)


def obtener_usuario_actual(request: Request):
  return request.session.get("user")


@app.get("/login", response_class=HTMLResponse)
def vista_login(request: Request):
  if obtener_usuario_actual(request):
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
  return templates.TemplateResponse(
      request=request, name="login.html", context={"error": None}
  )


@app.post("/login")
def procesar_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
  query = text("SELECT * FROM usuarios WHERE username = :user")
  usuario = db.execute(query, {"user": username}).mappings().first()

  if not usuario and username == "admin" and password == "admin123":
    hash_pwd = hash_password("admin123")
    db.execute(
        text("INSERT INTO usuarios (username, password_hash) VALUES (:u, :p)"),
        {"u": "admin", "p": hash_pwd},
    )
    db.commit()
    usuario = db.execute(query, {"user": username}).mappings().first()

  if not usuario or not verify_password(password, usuario["password_hash"]):
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"error": "Usuario o contraseña incorrectos"},
    )

  request.session["user"] = usuario["username"]
  return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/logout")
def cerrar_sesion(request: Request):
  request.session.clear()
  return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
  usuario = obtener_usuario_actual(request)
  if not usuario:
    return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

  query_clientes = text("""
        SELECT c.*, p.nombre AS nombre_plan, p.velocidad_bajada 
        FROM clientes c 
        LEFT JOIN planes p ON c.plan_id = p.id 
        ORDER BY c.id DESC
    """)
  clientes = db.execute(query_clientes).mappings().all()
  planes = (
      db.execute(text("SELECT * FROM planes ORDER BY id ASC")).mappings().all()
  )

  return templates.TemplateResponse(
      request=request,
      name="index.html",
      context={"clientes": clientes, "planes": planes, "usuario": usuario},
  )


@app.post("/clientes/registrar")
def registrar_cliente(
    cliente: ClienteCreate, request: Request, db: Session = Depends(get_db)
):
  if not obtener_usuario_actual(request):
    raise HTTPException(status_code=401, detail="No autorizado")

  plan = (
      db.execute(
          text("SELECT * FROM planes WHERE id = :id"), {"id": cliente.plan_id}
      )
      .mappings()
      .first()
  )
  if not plan:
    raise HTTPException(status_code=404, detail="El plan seleccionado no existe.")

  connection, api = obtener_conexion_mikrotik()
  try:
    aplicar_limite_velocidad(
        api,
        cliente.ip_estatica,
        cliente.nombre,
        plan["velocidad_subida"],
        plan["velocidad_bajada"],
    )
  except Exception as e:
    raise HTTPException(
        status_code=400, detail=f"Error al asignar límite en MikroTik: {str(e)}"
    )
  finally:
    connection.disconnect()

  try:
    query = text("""
            INSERT INTO clientes (nombre, telefono, ip_estatica, fecha_corte, estado, plan_id)
            VALUES (:nombre, :telefono, :ip_estatica, :fecha_corte, 'Activo', :plan_id)
        """)
    db.execute(
        query,
        {
            "nombre": cliente.nombre,
            "telefono": cliente.telefono,
            "ip_estatica": cliente.ip_estatica,
            "fecha_corte": cliente.fecha_corte,
            "plan_id": cliente.plan_id,
        },
    )
    db.commit()
    return {
        "resultado": "Éxito",
        "mensaje": f"Cliente {cliente.nombre} asignado a {plan['nombre']}",
    }
  except Exception as e:
    db.rollback()
    raise HTTPException(status_code=400, detail=str(e))


@app.post("/clientes/modificar/{cliente_id}")
def modificar_cliente(
    cliente_id: int,
    plan_id: int,
    fecha_corte: date,
    request: Request,
    db: Session = Depends(get_db),
):
  if not obtener_usuario_actual(request):
    raise HTTPException(status_code=401, detail="No autorizado")

  cliente = (
      db.execute(
          text("SELECT * FROM clientes WHERE id = :id"), {"id": cliente_id}
      )
      .mappings()
      .first()
  )
  if not cliente:
    raise HTTPException(status_code=404, detail="Cliente no encontrado")

  plan = (
      db.execute(text("SELECT * FROM planes WHERE id = :id"), {"id": plan_id})
      .mappings()
      .first()
  )
  if not plan:
    raise HTTPException(status_code=404, detail="El plan no existe")

  connection, api = obtener_conexion_mikrotik()
  try:
    aplicar_limite_velocidad(
        api,
        cliente["ip_estatica"],
        cliente["nombre"],
        plan["velocidad_subida"],
        plan["velocidad_bajada"],
    )
  except Exception as e:
    raise HTTPException(
        status_code=400, detail=f"Error al actualizar MikroTik: {str(e)}"
    )
  finally:
    connection.disconnect()

  try:
    query = text(
        "UPDATE clientes SET plan_id = :plan_id, fecha_corte = :fecha WHERE id"
        " = :id"
    )
    db.execute(
        query, {"plan_id": plan_id, "fecha": fecha_corte, "id": cliente_id}
    )
    db.commit()
    return {
        "resultado": "Éxito",
        "mensaje": f"Cliente {cliente['nombre']} actualizado correctamente.",
    }
  except Exception as e:
    db.rollback()
    raise HTTPException(status_code=500, detail=f"Error en BD: {str(e)}")


@app.delete("/clientes/eliminar/{cliente_id}")
def eliminar_cliente(
    cliente_id: int,
    ip_cliente: str,
    request: Request,
    db: Session = Depends(get_db),
):
  if not obtener_usuario_actual(request):
    raise HTTPException(status_code=401, detail="No autorizado")

  try:
    connection, api = obtener_conexion_mikrotik()
    remover_queue_mikrotik(api, ip_cliente)
    connection.disconnect()
  except Exception:
    pass

  try:
    db.execute(text("DELETE FROM clientes WHERE id = :id"), {"id": cliente_id})
    db.commit()
    return {"resultado": "Éxito", "mensaje": "Cliente eliminado correctamente."}
  except Exception as e:
    db.rollback()
    raise HTTPException(status_code=500, detail=f"Error en BD: {str(e)}")


@app.post("/clientes/cortar")
def cortar_servicio(
    ip_cliente: str, request: Request, db: Session = Depends(get_db)
):
  if not obtener_usuario_actual(request):
    raise HTTPException(status_code=401, detail="No autorizado")

  connection, api = obtener_conexion_mikrotik()
  try:
    address_list = api.get_resource("/ip/firewall/address-list")
    existentes = address_list.get(list="Clientes_Morosos", address=ip_cliente)
    if not existentes:
      address_list.add(
          list="Clientes_Morosos",
          address=ip_cliente,
          comment="Cortado desde Panel Web",
      )

    try:
      connections = api.get_resource("/ip/firewall/connection")
      conexiones_cliente = connections.get(src_address=ip_cliente)
      for conn in conexiones_cliente:
        connections.remove(id=conn["id"])
    except Exception:
      pass
  except Exception as e:
    raise HTTPException(
        status_code=400, detail=f"Error en MikroTik: {str(e)}"
    )
  finally:
    connection.disconnect()

  try:
    query = text(
        "UPDATE clientes SET estado = 'Suspendido' WHERE ip_estatica = :ip"
    )
    db.execute(query, {"ip": ip_cliente})
    db.commit()
    return {
        "resultado": "Éxito",
        "mensaje": f"Servicio suspendido para {ip_cliente}",
    }
  except Exception as e:
    db.rollback()
    raise HTTPException(status_code=500, detail=f"Error en BD: {str(e)}")


@app.post("/clientes/reactivar")
def reactivar_servicio(
    ip_cliente: str, request: Request, db: Session = Depends(get_db)
):
  if not obtener_usuario_actual(request):
    raise HTTPException(status_code=401, detail="No autorizado")

  connection, api = obtener_conexion_mikrotik()
  try:
    address_list = api.get_resource("/ip/firewall/address-list")
    registros = address_list.get(list="Clientes_Morosos", address=ip_cliente)

    if registros:
      address_list.remove(id=registros[0]["id"])
  except Exception as e:
    raise HTTPException(
        status_code=400, detail=f"Error al desbloquear en MikroTik: {str(e)}"
    )
  finally:
    connection.disconnect()

  try:
    query = text(
        "UPDATE clientes SET estado = 'Activo' WHERE ip_estatica = :ip"
    )
    db.execute(query, {"ip": ip_cliente})
    db.commit()
    return {
        "resultado": "Éxito",
        "mensaje": f"Servicio reactivado correctamente para {ip_cliente}",
    }
  except Exception as e:
    db.rollback()
    raise HTTPException(status_code=500, detail=f"Error en BD: {str(e)}")