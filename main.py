import os
from datetime import datetime, timedelta
from fastapi import FastAPI, Depends, Form, Request, status, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional
from pydantic import BaseModel

import models
import schemas
from database import engine, get_db

models.Base.metadata.create_all(bind=engine)

# Agregar columna zona_id y tabla ping_requests con commit asegurado
with engine.begin() as conn:
    conn.execute(text("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS zona_id INTEGER;"))
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS ping_requests (
            id SERIAL PRIMARY KEY,
            cliente_id INTEGER,
            zona_id INTEGER,
            ip_objetivo VARCHAR,
            estado VARCHAR DEFAULT 'pendiente',
            resultado TEXT DEFAULT ''
        );
    """))

app = FastAPI(title="Panel WISP - CASZARY TELECOMUNICACIONES")

os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# --- MODELOS PYDANTIC ---

class PlanCreateOrUpdate(BaseModel):
    nombre: str
    velocidad_subida: str
    velocidad_bajada: str


class AdminCreate(BaseModel):
    username: str
    password: str


class ZonaCreate(BaseModel):
    nombre: str
    descripcion: Optional[str] = ""


# --- RUTAS DE NAVEGACIÓN Y ACCESO ---

@app.get("/", response_class=HTMLResponse)
def root(request: Request):
    return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)


@app.get("/login", response_class=HTMLResponse)
def show_login(request: Request):
    if request.cookies.get("session_user"):
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse(request, "login.html", {"error": None})


@app.post("/login", response_class=HTMLResponse)
def process_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user or user.password_hash != password:
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": "Usuario o contraseña incorrectos"},
            status_code=status.HTTP_401_UNAUTHORIZED
        )
    response = RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    response.set_cookie(key="session_user", value=user.username, httponly=True)
    return response


@app.get("/dashboard", response_class=HTMLResponse)
def show_dashboard(request: Request):
    session_user = request.cookies.get("session_user")
    if not session_user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse(request, "panelad.html", {"usuario": session_user})


@app.get("/logout")
def logout():
    response = RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    response.delete_cookie(key="session_user")
    return response


# --- PANTALLAS DE AVISO PARA EL CLIENTE (REDIRECCIÓN MIKROTIK) ---

@app.get("/aviso-pago", response_class=HTMLResponse)
def pantalla_aviso_pago():
    return """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Recordatorio de Pago - CASZARY TELECOMUNICACIONES</title>
        <style>
            body { font-family: Arial, sans-serif; background: #141414; color: #fff; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; padding: 15px; }
            .box { background: #fff; color: #141414; max-width: 480px; padding: 30px; border-radius: 10px; border-top: 8px solid #f59e0b; text-align: center; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }
            h2 { color: #d97706; margin-top: 10px; }
            p { font-size: 16px; line-height: 1.5; }
            .btn { display: inline-block; margin-top: 20px; padding: 12px 24px; background: #141414; color: #fff; text-decoration: none; border-radius: 6px; font-weight: bold; }
        </style>
    </head>
    <body>
        <div class="box">
            <img src="/static/logo_caszary.jpg" alt="CASZARY" style="max-width: 180px;">
            <h2>⚠️ Recordatorio de Próximo Corte</h2>
            <p>Estimado cliente, le informamos que <strong>su fecha de corte está muy próxima</strong>.</p>
            <p>Por favor realice su pago a tiempo para evitar la suspensión automática de su servicio de internet.</p>
            <p style="font-size: 14px; color: #555;">Si ya realizó su pago, haga caso omiso a este aviso.</p>
            <a href="http://google.com" class="btn">Entendido, continuar navegando</a>
        </div>
    </body>
    </html>
    """


@app.get("/servicio-cortado", response_class=HTMLResponse)
def pantalla_servicio_cortado():
    return """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Servicio Suspendido - CASZARY TELECOMUNICACIONES</title>
        <style>
            body { font-family: Arial, sans-serif; background: #141414; color: #fff; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; padding: 15px; }
            .box { background: #fff; color: #141414; max-width: 480px; padding: 30px; border-radius: 10px; border-top: 8px solid #D91E2A; text-align: center; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }
            h2 { color: #D91E2A; margin-top: 10px; }
            p { font-size: 16px; line-height: 1.5; }
            .badge { background: #D91E2A; color: #fff; padding: 8px 16px; border-radius: 5px; font-weight: bold; display: inline-block; margin-top: 10px; }
        </style>
    </head>
    <body>
        <div class="box">
            <img src="/static/logo_caszary.jpg" alt="CASZARY" style="max-width: 180px;">
            <h2>🚫 Servicio Suspendido por Falta de Pago</h2>
            <p>Estimado cliente, su servicio de internet ha sido <strong>cortado temporalmente</strong> debido a que presenta un saldo vencido.</p>
            <p>Para reactivar su conexión de inmediato, por favor comuníquese con administración y envíe su comprobante de pago.</p>
            <div class="badge">CASZARY TELECOMUNICACIONES</div>
        </div>
    </body>
    </html>
    """


# --- API DE PRUEBA DE PING REMOTO AL MÓDEM DEL CLIENTE ---

@app.post("/api/clientes/{cliente_id}/ping")
def solicitar_ping_cliente(cliente_id: int, db: Session = Depends(get_db)):
    cliente = db.query(models.Cliente).filter(models.Cliente.id == cliente_id).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    if not cliente.zona_id:
        raise HTTPException(status_code=400, detail="Este cliente no tiene una Zona / MikroTik asignada")

    db.execute(text("DELETE FROM ping_requests WHERE cliente_id = :cid"), {"cid": cliente_id})
    res = db.execute(
        text("INSERT INTO ping_requests (cliente_id, zona_id, ip_objetivo, estado) VALUES (:cid, :zid, :ip, 'pendiente') RETURNING id"),
        {"cid": cliente.id, "zid": cliente.zona_id, "ip": cliente.ip_estatica.strip()}
    )
    ping_id = res.fetchone()[0]
    db.commit()
    return {"ping_id": ping_id, "estado": "pendiente", "ip": cliente.ip_estatica}


@app.get("/api/ping/{ping_id}")
def consultar_estado_ping(ping_id: int, db: Session = Depends(get_db)):
    row = db.execute(text("SELECT estado, resultado, ip_objetivo FROM ping_requests WHERE id = :pid"), {"pid": ping_id}).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Solicitud de ping no encontrada")
    return {"estado": row[0], "resultado": row[1], "ip": row[2]}


@app.get("/api/ping/{ping_id}/reportar", response_class=PlainTextResponse)
def reportar_resultado_ping(ping_id: int, recibidos: int = 0, db: Session = Depends(get_db)):
    if recibidos > 0:
        estado = "exitoso"
        resultado = f"✅ Ping exitoso ({recibidos}/4 paquetes recibidos). El módem tiene conexión."
    else:
        estado = "fallido"
        resultado = "❌ Sin respuesta (0/4 paquetes recibidos). El módem está apagado o sin enlace."

    db.execute(
        text("UPDATE ping_requests SET estado = :est, resultado = :res WHERE id = :pid"),
        {"est": estado, "res": resultado, "pid": ping_id}
    )
    db.commit()
    return "OK"


# --- API REST DE ZONAS / MIKROTIKS ---

@app.get("/api/zonas")
def obtener_zonas(db: Session = Depends(get_db)):
    zonas = db.query(models.Zona).order_by(models.Zona.id).all()
    return [{"id": z.id, "nombre": z.nombre, "descripcion": z.descripcion or ""} for z in zonas]


@app.post("/api/zonas")
def crear_zona(datos: ZonaCreate, db: Session = Depends(get_db)):
    existente = db.query(models.Zona).filter(models.Zona.nombre == datos.nombre).first()
    if existente:
        raise HTTPException(status_code=400, detail="Ya existe una zona con ese nombre")
    nueva = models.Zona(nombre=datos.nombre, descripcion=datos.descripcion)
    db.add(nueva)
    db.commit()
    db.refresh(nueva)
    return {"id": nueva.id, "nombre": nueva.nombre, "descripcion": nueva.descripcion}


@app.delete("/api/zonas/{zona_id}")
def eliminar_zona(zona_id: int, db: Session = Depends(get_db)):
    zona = db.query(models.Zona).filter(models.Zona.id == zona_id).first()
    if not zona:
        raise HTTPException(status_code=404, detail="Zona no encontrada")
    db.query(models.Cliente).filter(models.Cliente.zona_id == zona_id).update({"zona_id": None})
    db.delete(zona)
    db.commit()
    return {"mensaje": "Zona eliminada"}


# --- SCRIPT DINÁMICO PARA MIKROTIK (VELOCIDADES, CORTES, AVISOS Y PING) ---

@app.get("/api/zonas/{zona_id}/script.rsc", response_class=PlainTextResponse)
def generar_script_mikrotik(zona_id: int, request: Request, db: Session = Depends(get_db)):
    zona = db.query(models.Zona).filter(models.Zona.id == zona_id).first()
    if not zona:
        return "# Error: Zona no encontrada\n"

    base_url = str(request.base_url).rstrip("/")
    clientes = db.query(models.Cliente).filter(models.Cliente.zona_id == zona_id).all()
    planes = {p.id: p for p in db.query(models.Plan).all()}

    hoy = datetime.now().date()
    limite_aviso = hoy + timedelta(days=3)

    lineas = [
        f"# Sincronizacion automatica CASZARY - Zona: {zona.nombre}",
        '/queue simple remove [find comment="WISP_AUTO"]',
        '/ip firewall address-list remove [find list="morosos" comment="WISP_AUTO"]',
        '/ip firewall address-list remove [find list="aviso_pago" comment="WISP_AUTO"]',
    ]

    for c in clientes:
        ip = c.ip_estatica.strip()
        nombre_limpio = c.nombre.replace('"', '').replace(' ', '_')
        if c.activo:
            plan = planes.get(c.plan_id)
            subida = str(plan.velocidad_subida).strip() if plan else "5"
            bajada = str(plan.velocidad_bajada).strip() if plan else "10"
            if subida.isdigit():
                subida += "M"
            if bajada.isdigit():
                bajada += "M"
            lineas.append(
                f'/queue simple add name="Cliente_{nombre_limpio}_{c.id}" target="{ip}/32" max-limit="{subida}/{bajada}" comment="WISP_AUTO"'
            )
            try:
                f_corte = datetime.strptime(str(c.fecha_corte), "%Y-%m-%d").date()
                if hoy <= f_corte <= limite_aviso:
                    lineas.append(
                        f'/ip firewall address-list add list="aviso_pago" address="{ip}" comment="WISP_AUTO"'
                    )
            except Exception:
                pass
        else:
            lineas.append(
                f'/ip firewall address-list add list="morosos" address="{ip}" comment="WISP_AUTO"'
            )

    pings_pendientes = db.execute(
        text("SELECT id, ip_objetivo FROM ping_requests WHERE zona_id = :zid AND estado = 'pendiente'"),
        {"zid": zona_id}
    ).fetchall()

    for p in pings_pendientes:
        pid, ip_obj = p[0], p[1]
        lineas.append(
            f':local rx [/ping {ip_obj} count=4]; /tool fetch url="{base_url}/api/ping/{pid}/reportar?recibidos=$rx" keep-result=no;'
        )

    return "\n".join(lineas) + "\n"


# --- API REST DE PLANES ---

@app.get("/api/planes", response_model=List[schemas.PlanResponse])
def obtener_planes(db: Session = Depends(get_db)):
    return db.query(models.Plan).order_by(models.Plan.id).all()


@app.post("/api/planes")
def crear_plan(datos: PlanCreateOrUpdate, db: Session = Depends(get_db)):
    nuevo_plan = models.Plan(
        nombre=datos.nombre,
        velocidad_subida=datos.velocidad_subida,
        velocidad_bajada=datos.velocidad_bajada
    )
    db.add(nuevo_plan)
    db.commit()
    db.refresh(nuevo_plan)
    return {"mensaje": "Plan creado correctamente", "id": nuevo_plan.id}


@app.put("/api/planes/{plan_id}")
def actualizar_plan(plan_id: int, datos: PlanCreateOrUpdate, db: Session = Depends(get_db)):
    plan = db.query(models.Plan).filter(models.Plan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan no encontrado")
    plan.nombre = datos.nombre
    plan.velocidad_subida = datos.velocidad_subida
    plan.velocidad_bajada = datos.velocidad_bajada
    db.commit()
    return {"mensaje": "Plan actualizado correctamente"}


# --- API REST DE CLIENTES ---

@app.get("/api/clientes", response_model=List[schemas.ClienteResponse])
def obtener_clientes(db: Session = Depends(get_db)):
    return db.query(models.Cliente).order_by(models.Cliente.id).all()


@app.post("/api/clientes", response_model=schemas.ClienteResponse)
def registrar_cliente(cliente: schemas.ClienteCreate, db: Session = Depends(get_db)):
    nuevo_cliente = models.Cliente(
        nombre=cliente.nombre,
        telefono=cliente.telefono,
        ip_estatica=cliente.ip_estatica,
        fecha_corte=cliente.fecha_corte,
        plan_id=cliente.plan_id,
        zona_id=cliente.zona_id,
        activo=True
    )
    db.add(nuevo_cliente)
    db.commit()
    db.refresh(nuevo_cliente)
    return nuevo_cliente


@app.put("/api/clientes/{cliente_id}", response_model=schemas.ClienteResponse)
def editar_cliente(cliente_id: int, cliente_data: schemas.ClienteUpdate, db: Session = Depends(get_db)):
    cliente = db.query(models.Cliente).filter(models.Cliente.id == cliente_id).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    
    update_data = cliente_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(cliente, key, value)
    
    db.commit()
    db.refresh(cliente)
    return cliente


@app.patch("/api/clientes/{cliente_id}/estado", response_model=schemas.ClienteResponse)
def cambiar_estado_cliente(cliente_id: int, db: Session = Depends(get_db)):
    cliente = db.query(models.Cliente).filter(models.Cliente.id == cliente_id).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    
    cliente.activo = not cliente.activo
    db.commit()
    db.refresh(cliente)
    return cliente


@app.delete("/api/clientes/{cliente_id}")
def eliminar_cliente(cliente_id: int, db: Session = Depends(get_db)):
    cliente = db.query(models.Cliente).filter(models.Cliente.id == cliente_id).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    
    db.delete(cliente)
    db.commit()
    return {"mensaje": "Cliente eliminado correctamente"}


# --- API REST DE ADMINISTRADORES ---

@app.get("/api/administradores")
def listar_administradores(db: Session = Depends(get_db)):
    usuarios = db.query(models.User).order_by(models.User.id).all()
    return [{"id": u.id, "username": u.username} for u in usuarios]


@app.post("/api/administradores")
def crear_administrador(admin: AdminCreate, db: Session = Depends(get_db)):
    existente = db.query(models.User).filter(models.User.username == admin.username).first()
    if existente:
        raise HTTPException(status_code=400, detail="El usuario ya existe")
    
    nuevo = models.User(username=admin.username, password_hash=admin.password)
    db.add(nuevo)
    db.commit()
    return {"mensaje": "Administrador creado"}