import os
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

# Crear tablas nuevas si no existen
models.Base.metadata.create_all(bind=engine)

# Agregar columna zona_id a clientes existentes en PostgreSQL sin perder datos
with engine.connect() as conn:
    try:
        conn.execute(text("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS zona_id INTEGER REFERENCES zonas(id);"))
        conn.commit()
    except Exception:
        pass

app = FastAPI(title="Panel WISP - CASZARY TELECOMUNICACIONES")

os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# --- MODELOS PYDANTIC ADICIONALES ---

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
    # Desvincular clientes de esa zona antes de borrarla
    db.query(models.Cliente).filter(models.Cliente.zona_id == zona_id).update({"zona_id": None})
    db.delete(zona)
    db.commit()
    return {"mensaje": "Zona eliminada"}


# --- ENDPOINT DE SINCRONIZACIÓN DIRECTA PARA MIKROTIK (/tool fetch) ---

@app.get("/api/zonas/{zona_id}/script.rsc", response_class=PlainTextResponse)
def generar_script_mikrotik(zona_id: int, db: Session = Depends(get_db)):
    """Genera comandos nativos de RouterOS solo para los clientes de la zona indicada."""
    zona = db.query(models.Zona).filter(models.Zona.id == zona_id).first()
    if not zona:
        return "# Error: Zona no encontrada\n"

    clientes = db.query(models.Cliente).filter(models.Cliente.zona_id == zona_id).all()
    planes = {p.id: p for p in db.query(models.Plan).all()}

    lineas = [
        f"# Sincronizacion automatica CASZARY - Zona: {zona.nombre}",
        '/queue simple remove [find comment="WISP_AUTO"]',
        '/ip firewall address-list remove [find list="morosos" comment="WISP_AUTO"]',
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
        else:
            lineas.append(
                f'/ip firewall address-list add list="morosos" address="{ip}" comment="WISP_AUTO"'
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