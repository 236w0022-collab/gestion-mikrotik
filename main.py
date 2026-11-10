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

# 1. La portada raíz redirige al login
@app.get("/", response_class=HTMLResponse)
def root(request: Request):
    return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

# 2. Pantalla de login (muestra login.html)
@app.get("/login", response_class=HTMLResponse)
def show_login(request: Request):
    if request.cookies.get("session_user"):
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    
    # Sintaxis compatible: request, "nombre_plantilla.html", context_dict
    return templates.TemplateResponse(
        request,
        "login.html",
        {"error": None}
    )

# 3. Procesar el formulario de inicio de sesión
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

# 4. Panel administrativo protegido (muestra panelad.html)
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

# 5. Cerrar sesión
@app.get("/logout")
def logout():
    response = RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    response.delete_cookie(key="session_user")
    return response

# --- API REST DE CLIENTES (Para que panelad.html consuma datos) ---

@app.get("/api/clientes", response_model=List[schemas.ClienteResponse])
def obtener_clientes(db: Session = Depends(get_db)):
    return db.query(models.Cliente).all()

@app.post("/api/clientes", response_model=schemas.ClienteResponse)
def registrar_cliente(cliente: schemas.ClienteCreate, db: Session = Depends(get_db)):
    nuevo_cliente = models.Cliente(
        nombre=cliente.nombre,
        telefono=cliente.telefono,
        ip_estatica=cliente.ip_estatica,
        fecha_corte=cliente.fecha_corte,
        plan_id=cliente.plan_id
    )
    db.add(nuevo_cliente)
    db.commit()
    db.refresh(nuevo_cliente)
    return nuevo_cliente