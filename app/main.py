# main.py — Punto de entrada del servidor
#
# Para arrancar el servidor, ejecutas:
#   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
#
# Desglose de ese comando:
#   uvicorn       = el programa que corre servidores FastAPI (como Tomcat para Java)
#   app.main      = busca el archivo app/main.py
#   :app          = dentro de ese archivo, usa la variable llamada 'app'
#   --reload      = reinicia solo cuando guardas un archivo (útil en desarrollo)
#   --host 0.0.0.0  = acepta conexiones desde CUALQUIER computadora en la red
#                     (sin esto, solo respondería a localhost — la Pi misma)
#   --port 8000   = número de puerto. Como un número de puerta en un edificio.

from contextlib import asynccontextmanager  # para el evento de arranque

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles  # para servir CSS, JS, imágenes
from fastapi.templating import Jinja2Templates  # para las plantillas HTML

from app.database import create_db_and_tables
from app.routers import asistencias, clases, listado


# ─────────────────────────────────────────────────────────────
# EVENTO DE ARRANQUE
# ─────────────────────────────────────────────────────────────
# @asynccontextmanager convierte esta función en un "gestor de ciclo de vida".
# FastAPI la llama automáticamente:
#   - El código ANTES del 'yield' corre cuando el servidor ARRANCA
#   - El código DESPUÉS del 'yield' correría cuando el servidor SE APAGA
#
# Es como el constructor de una clase Java, pero para el servidor entero.
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Esto corre UNA SOLA VEZ al arrancar el servidor.
    # Crea las tablas en registro.db si todavía no existen.
    # Si ya existen (segunda vez que arrancas), no hace nada — es seguro.
    create_db_and_tables()
    yield
    # (aquí iría código de limpieza al apagar, si lo necesitáramos)


# ─────────────────────────────────────────────────────────────
# LA APLICACIÓN FASTAPI
# ─────────────────────────────────────────────────────────────
# FastAPI() crea el servidor. Los parámetros son metadatos — aparecen
# en la documentación automática que FastAPI genera en /docs
#
# Pruébalo: cuando el servidor esté corriendo, abre http://localhost:8000/docs
# Verás TODOS tus endpoints documentados automáticamente. Esto no existía en PHP.
app = FastAPI(
    title="Sistema de Registro de Asistencia",
    description="Taller de Redes — Registro via lector de código de barras",
    version="1.0.0",
    lifespan=lifespan,  # le pasamos el gestor de arranque que definimos arriba
)


# ─────────────────────────────────────────────────────────────
# ARCHIVOS ESTÁTICOS (CSS, JS, imágenes)
# ─────────────────────────────────────────────────────────────
# Esto le dice a FastAPI: "si alguien pide una URL que empiece con /static,
# busca el archivo en la carpeta app/static/ y devuélvelo directamente."
#
# Ejemplo: <link href="/static/style.css"> en el HTML
#   → FastAPI busca app/static/style.css y lo envía al navegador
#
# Sin esto, el navegador diría "404 Not Found" al intentar cargar el CSS.
app.mount(
    "/static",              # prefijo de URL
    StaticFiles(directory="app/static"),  # carpeta en disco
    name="static",          # nombre interno (para referencias en plantillas)
)


# ─────────────────────────────────────────────────────────────
# PLANTILLAS HTML (Jinja2)
# ─────────────────────────────────────────────────────────────
# Jinja2 es el motor de plantillas. Piénsalo como el "<?php echo ?>" de PHP,
# pero más limpio y separado del código Python.
#
# En las plantillas HTML usarás sintaxis como:
#   {{ alumno.nombre_alumno }}     → imprime el nombre
#   {% for a in alumnos %}         → bucle
#   {% if sesion %}                → condicional
#
# 'templates' es un objeto que los routers usan para renderizar HTML.
# Se define aquí una vez y se importa donde se necesite.
templates = Jinja2Templates(directory="app/templates")


# ─────────────────────────────────────────────────────────────
# ROUTERS — Registro de rutas
# ─────────────────────────────────────────────────────────────
# Un router es un grupo de endpoints relacionados, definidos en un archivo aparte.
# Aquí los "conectamos" a la app principal.
#
# Analogía PHP: es como hacer require("clases.php") en el index.php,
# pero cada router trae sus propias URLs ya definidas.
#
# include_router(router, prefix=...) agrega un prefijo a todas las URLs del router.
# Ejemplo: si clases_router tiene GET "/", con prefix="/clases" queda GET "/clases"
#          si asistencias_router tiene POST "/scan", con prefix="/api" queda POST "/api/scan"

app.include_router(
    clases.router,
    prefix="/clases",   # todas las rutas de clases.py empezarán con /clases
    tags=["Clases"],    # etiqueta para agruparlas en /docs
)

app.include_router(
    listado.router,
    prefix="/clases",   # comparte prefijo con clases (ej. /clases/1/alumnos)
    tags=["Alumnos"],
)

app.include_router(
    asistencias.router,
    prefix="/api",      # el lector llama a /api/scan, /api/sesiones, etc.
    tags=["Asistencias / Lector"],
)


# ─────────────────────────────────────────────────────────────
# RUTA RAÍZ
# ─────────────────────────────────────────────────────────────
# Cuando alguien abre http://192.168.1.x:8000/ sin ninguna ruta,
# lo mandamos directamente a la lista de clases.
#
# RedirectResponse es como un "Location: clases.php" en PHP —
# le dice al navegador "ve a esta otra URL".
from fastapi.responses import RedirectResponse

@app.get("/", include_in_schema=False)  # include_in_schema=False lo oculta de /docs
def raiz():
    return RedirectResponse(url="/clases")
