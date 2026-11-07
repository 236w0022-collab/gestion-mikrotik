import routeros_api
from fastapi import HTTPException

# Configuración de conexión a MikroTik
MIKROTIK_HOST = "179.238.61.100"
MIKROTIK_PORT = 8728
MIKROTIK_USER = "admin"
MIKROTIK_PASS = "Castro100"


def obtener_conexion_mikrotik():
  """Abre y retorna una conexión activa a la API de MikroTik."""
  try:
    connection = routeros_api.RouterOsApiPool(
        MIKROTIK_HOST,
        username=MIKROTIK_USER,
        password=MIKROTIK_PASS,
        port=MIKROTIK_PORT,
        plaintext_login=True,
    )
    api = connection.get_api()
    return connection, api
  except Exception as e:
    raise HTTPException(
        status_code=500,
        detail=(
            f"Error MikroTik: No se pudo conectar a"
            f" {MIKROTIK_HOST}:{MIKROTIK_PORT}. Detalle: {str(e)}"
        ),
    )


def aplicar_limite_velocidad(
    api, ip_cliente: str, nombre_cliente: str, subida: str, bajada: str
):
  """Crea o actualiza el límite de velocidad en MikroTik (Simple Queue)"""
  queues = api.get_resource('/queue/simple')
  existente = queues.get(target=f'{ip_cliente}/32')
  max_limit = f'{subida}/{bajada}'
  nombre_queue = f"Cliente_{nombre_cliente.replace(' ', '_')}"

  if existente:
    queues.set(id=existente[0]['id'], max_limit=max_limit, name=nombre_queue)
  else:
    queues.add(name=nombre_queue, target=f'{ip_cliente}/32', max_limit=max_limit)


def remover_queue_mikrotik(api, ip_cliente: str):
  """Elimina la cola simple asociada a la IP del cliente"""
  try:
    queues = api.get_resource('/queue/simple')
    existente = queues.get(target=f'{ip_cliente}/32')
    if existente:
      queues.remove(id=existente[0]['id'])
  except Exception:
    pass