from database import engine, Base
import models  # Carga la definición de tus modelos

print("Conectando a Render y creando tablas...")
# Esta línea crea las tablas físicas en PostgreSQL
Base.metadata.create_all(bind=engine)
print("¡Tablas creadas correctamente!")