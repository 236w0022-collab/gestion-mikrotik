from database import engine, Base
from sqlalchemy import text

# 1. Crear la estructura de las tablas mediante SQL directo
with engine.connect() as conn:
    # Tabla Usuarios
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        );
    """))

    # Tabla Planes
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS planes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            velocidad_subida TEXT NOT NULL,
            velocidad_bajada TEXT NOT NULL
        );
    """))

    # Tabla Clientes
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            telefono TEXT,
            ip_estatica TEXT UNIQUE NOT NULL,
            fecha_corte DATE,
            estado TEXT DEFAULT 'Activo',
            plan_id INTEGER,
            FOREIGN KEY (plan_id) REFERENCES planes(id)
        );
    """))

    # 2. Insertar planes de prueba si la tabla está vacía
    res = conn.execute(text("SELECT COUNT(*) FROM planes")).scalar()
    if res == 0:
        conn.execute(text("""
            INSERT INTO planes (nombre, velocidad_subida, velocidad_bajada) 
            VALUES 
            ('Plan Básico 5M', '2.5M', '5M'),
	    ('Plan NORMAL 10M', '5M', '10M'),
            ('Plan PLATINO 15M', '7.5M', '15M'),
            ('Plan GOLDEN 20M', '10M', '20M');
        """))

    conn.commit()

print("¡Base de datos local SQLite creada e inicializada con éxito!")