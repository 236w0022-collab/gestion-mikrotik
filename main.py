import os
from datetime import date
from pathlib import Path
import bcrypt

from database import get_db
from fastapi import Depends, FastAPI, Form, Header, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

app = FastAPI(
    title="Sistema de Gestión WISP / Comunidad",
    description="Panel de Control para Empleados",
    version="1.5.0",
)

SECRET_KEY = "tu_clave_secreta_super_segura_mikrotik"
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

# Token de seguridad para comunicación Render <-> Agente Ubuntu
AGENT_TOKEN = os.getenv("AGENT_TOKEN", "MI_CLAVE_SUPER_SECRETA_123")

BASE_DIR = Path(__file__).resolve().parent

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


# --- FUNCIONES DE AUTENTICACIÓN ---
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


def verificar_agent_token(x_agent_token: str = Header(...)):
    if x_agent_token != AGENT_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de agente inválido o no autorizado",
        )


# --- RUTAS DE LOGIN Y DASHBOARD ---
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


# --- RUTAS DE GESTIÓN DE CLIENTES (ENCOLAN ÓRDENES PARA EL AGENTE) ---

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

    try:
        # 1. Guardar cliente en BD
        query_cliente = text("""
            INSERT INTO clientes (nombre, telefono, ip_estatica, fecha_corte, estado, plan_id)
            VALUES (:nombre, :telefono, :ip_estatica, :fecha_corte, 'Activo', :plan_id)
        """)
        db.execute(
            query_cliente,
            {
                "nombre": cliente.nombre,
                "telefono": cliente.telefono,
                "ip_estatica": cliente.ip_estatica,
                "fecha_corte": cliente.fecha_corte,
                "plan_id": cliente.plan_id,
            },
        )

        # 2. Encolar orden de límite de velocidad para el agente local
        query_orden = text("""
            INSERT INTO ordenes_agente (cliente_ip, accion, estado, velocidad_subida, velocidad_bajada)
            VALUES (:ip, 'LIMITE_VELOCIDAD', 'PENDIENTE', :subida, :bajada)
        """)
        db.execute(
            query_orden,
            {
                "ip": cliente.ip_estatica,
                "subida": plan["velocidad_subida"],
                "bajada": plan["velocidad_bajada"],
            },
        )
        db.commit()

        return {
            "resultado": "Éxito",
            "mensaje": f"Cliente {cliente.nombre} registrado. Orden enviada al agente.",
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
        db.execute(text("SELECT * FROM clientes WHERE id = :id"), {"id": cliente_id})
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

    try:
        # Actualizar datos del cliente
        query = text(
            "UPDATE clientes SET plan_id = :plan_id, fecha_corte = :fecha WHERE id = :id"
        )
        db.execute(query, {"plan_id": plan_id, "fecha": fecha_corte, "id": cliente_id})

        # Encolar orden de cambio de velocidad
        query_orden = text("""
            INSERT INTO ordenes_agente (cliente_ip, accion, estado, velocidad_subida, velocidad_bajada)
            VALUES (:ip, 'LIMITE_VELOCIDAD', 'PENDIENTE', :subida, :bajada)
        """)
        db.execute(
            query_orden,
            {
                "ip": cliente["ip_estatica"],
                "subida": plan["velocidad_subida"],
                "bajada": plan["velocidad_bajada"],
            },
        )
        db.commit()

        return {
            "resultado": "Éxito",
            "mensaje": f"Cliente {cliente['nombre']} actualizado. Cambio encolado para MikroTik.",
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
        # Encolar orden de remoción de Queue
        query_orden = text("""
            INSERT INTO ordenes_agente (cliente_ip, accion, estado)
            VALUES (:ip, 'ELIMINAR_QUEUE', 'PENDIENTE')
        """)
        db.execute(query_orden, {"ip": ip_cliente})

        # Eliminar cliente de la BD
        db.execute(text("DELETE FROM clientes WHERE id = :id"), {"id": cliente_id})
        db.commit()

        return {"resultado": "Éxito", "mensaje": "Cliente eliminado y orden enviada al agente."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error en BD: {str(e)}")


@app.post("/clientes/cortar")
def cortar_servicio(
    ip_cliente: str, request: Request, db: Session = Depends(get_db)
):
    if not obtener_usuario_actual(request):
        raise HTTPException(status_code=401, detail="No autorizado")

    try:
        # 1. Encolar orden de corte para el agente local
        query_orden = text("""
            INSERT INTO ordenes_agente (cliente_ip, accion, estado)
            VALUES (:ip, 'CORTE', 'PENDIENTE')
        """)
        db.execute(query_orden, {"ip": ip_cliente})

        # 2. Actualizar estado local en BD
        query_cliente = text(
            "UPDATE clientes SET estado = 'Suspendido' WHERE ip_estatica = :ip"
        )
        db.execute(query_cliente, {"ip": ip_cliente})
        db.commit()

        return {
            "resultado": "Éxito",
            "mensaje": f"Orden de suspensión registrada para {ip_cliente}",
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

    try:
        # 1. Encolar orden de reconexión para el agente local
        query_orden = text("""
            INSERT INTO ordenes_agente (cliente_ip, accion, estado)
            VALUES (:ip, 'RECONEXION', 'PENDIENTE')
        """)
        db.execute(query_orden, {"ip": ip_cliente})

        # 2. Actualizar estado local en BD
        query_cliente = text(
            "UPDATE clientes SET estado = 'Activo' WHERE ip_estatica = :ip"
        )
        db.execute(query_cliente, {"ip": ip_cliente})
        db.commit()

        return {
            "resultado": "Éxito",
            "mensaje": f"Orden de reactivación registrada para {ip_cliente}",
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error en BD: {str(e)}")


# --- ENDPOINTS EXCLUSIVOS PARA LA COMUNICACIÓN CON TU AGENTE LOCAL UBUNTU ---

@app.get("/api/agente/ordenes-pendientes", dependencies=[Depends(verificar_agent_token)])
def obtener_ordenes_pendientes(db: Session = Depends(get_db)):
    query = text("""
        SELECT id, cliente_ip, accion, velocidad_subida, velocidad_bajada 
        FROM ordenes_agente 
        WHERE estado = 'PENDIENTE'
        ORDER BY id ASC
    """)
    ordenes = db.execute(query).mappings().all()
    return [dict(orden) for orden in ordenes]


@app.post("/api/agente/confirmar-orden", dependencies=[Depends(verificar_agent_token)])
def confirmar_orden(datos: dict, db: Session = Depends(get_db)):
    orden_id = datos.get("orden_id")
    if not orden_id:
        raise HTTPException(status_code=400, detail="Falta el orden_id")

    try:
        query = text("""
            UPDATE ordenes_agente 
            SET estado = 'PROCESADO' 
            WHERE id = :id
        """)
        db.execute(query, {"id": orden_id})
        db.commit()
        return {"resultado": "Éxito", "mensaje": f"Orden #{orden_id} completada"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error en BD: {str(e)}")