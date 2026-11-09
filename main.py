from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

import models
import schemas
from database import engine, get_db

# Crea las tablas automáticamente si no existen
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Mi Proyecto Mikrotik / WISP API")

@app.get("/")
def read_root():
    return {"status": "ok", "message": "API conectada a PostgreSQL exitosamente"}

# --- ENDPOINTS DE CLIENTES ---

@app.post("/clientes/", response_model=schemas.ClienteResponse, status_code=status.HTTP_201_CREATED)
def crear_cliente(cliente: schemas.ClienteCreate, db: Session = Depends(get_db)):
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

@app.get("/clientes/", response_model=List[schemas.ClienteResponse])
def listar_clientes(db: Session = Depends(get_db)):
    return db.query(models.Cliente).all()

# --- ENDPOINTS DE USUARIOS ---

@app.post("/users/", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
def crear_usuario(usuario: schemas.UserCreate, db: Session = Depends(get_db)):
    usuario_existente = db.query(models.User).filter(models.User.username == usuario.username).first()
    if usuario_existente:
        raise HTTPException(status_code=400, detail="El nombre de usuario ya está registrado")
    
    nuevo_usuario = models.User(
        username=usuario.username,
        password_hash=usuario.password  # En producción se recomienda usar hash (bcrypt)
    )
    db.add(nuevo_usuario)
    db.commit()
    db.refresh(nuevo_usuario)
    return nuevo_usuario