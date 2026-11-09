import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# 1. Lee la URL de la base de datos desde las variables de entorno de Render.
# Si no existe (en tu PC local), usa la base SQLite por defecto.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./sql_app.db")

# Ajuste de compatibilidad para URLs de Render (que a veces empiezan con postgres://)
if DATABASE_URL.startswith("postgres://"):
  DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# 2. Configurar motor según el tipo de BD
if DATABASE_URL.startswith("sqlite"):
  engine = create_engine(
      DATABASE_URL, connect_args={"check_same_thread": False}
  )
else:
  engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
  db = SessionLocal()
  try:
    yield db
  finally:
    db.close()