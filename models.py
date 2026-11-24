from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password_hash = Column(String)

class Zona(Base):
    __tablename__ = "zonas"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, unique=True, index=True)
    descripcion = Column(String, nullable=True)

class Plan(Base):
    __tablename__ = "planes"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String)
    velocidad_subida = Column(String)
    velocidad_bajada = Column(String)

class Cliente(Base):
    __tablename__ = "clientes"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String)
    telefono = Column(String)
    ip_estatica = Column(String)
    fecha_corte = Column(String)
    activo = Column(Boolean, default=True)
    plan_id = Column(Integer, ForeignKey("planes.id"))
    zona_id = Column(Integer, ForeignKey("zonas.id"), nullable=True)