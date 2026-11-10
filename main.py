import os
from fastapi import FastAPI, Depends, Form, Request, status, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import List

import models
import schemas
from database import engine, get_db

# Crear tablas en PostgreSQL automáticamente si no existen
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Panel WISP - Red Comunitaria Josefinas")

# Configurar directorio de plantillas HTML
templates = Jinja2Templates(directory="templates")

# --- RUTAS DE NAVEGACIÓN Y ACCESO ---

@app.get("/", response_class=HTMLResponse)
def root(request: Request):
    return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

@app.get("/login", response_class=HTMLResponse)
def show_login(request: Request):
    if request.cookies.get("session_user"):
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    
    return templates.TemplateResponse(
        request,
        "login.html",
        {"error": None}
    )

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
    
    return templates.TemplateResponse(
        request,
        "panelad.html",
        {"usuario": session_user}
    )

@app.get("/logout")
def logout():
    response = RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    response.delete_cookie(key="session_user")
    return response

# --- API REST DE PLANES ---

@app.get("/api/planes", response_model=List[schemas.PlanResponse])
def obtener_planes(db: Session = Depends(get_db)):
    return db.query(models.Plan).order_by(models.Plan.id).all()

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