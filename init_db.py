from database import engine, Base
import models  # Importa las definiciones de tus tablas

def init_db():
    print("Conectando a PostgreSQL en Render y creando tablas...")
    Base.metadata.create_all(bind=engine)
    print("¡Tablas creadas exitosamente!")

if __name__ == "__main__":
    init_db()