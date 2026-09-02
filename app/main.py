# main.py — Punto de entrada del servidor

# Para arrancar el servidor, ejecutas:
#   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000


from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.database import create_db_and_tables
from app.routers import asistencias, clases, listado


# ─────────────────────────────────────────────────────────────
# EVENTO DE ARRANQUE
# ─────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield


# ─────────────────────────────────────────────────────────────
# LA APLICACIÓN FASTAPI
# ─────────────────────────────────────────────────────────────
# FastAPI() crea el servidor. Los parámetros son metadatos — aparecen
# en la documentación automática que FastAPI genera en /docs
#
# Pruébalo: cuando el servidor esté corriendo, abre http://localhost:8000/docs
# Verás TODOS tus endpoints documentados automáticamente. Esto no existía en PHP.
app = FastAPI(
    title="Student Scan Register",
    description="Taller de Redes — Registro via lector de código de barras",
    version="1.0.0",
    lifespan=lifespan,
)


# ─────────────────────────────────────────────────────────────
# ARCHIVOS ESTÁTICOS (CSS, JS, imágenes)
# ─────────────────────────────────────────────────────────────
app.mount(
    "/static",
    StaticFiles(directory="app/static"),
    name="static",
)


# ─────────────────────────────────────────────────────────────
# PLANTILLAS HTML (Jinja2)
# ─────────────────────────────────────────────────────────────
templates = Jinja2Templates(directory="app/templates")


# ─────────────────────────────────────────────────────────────
# ROUTERS — Registro de rutas
# ─────────────────────────────────────────────────────────────
app.include_router(
    clases.router,
    prefix="/clases",
    tags=["Clases"],
)

app.include_router(
    listado.router,
    prefix="/clases",
    tags=["Alumnos"],
)

app.include_router(
    asistencias.router,
    prefix="/api",
    tags=["Asistencias / Lector"],
)


# ─────────────────────────────────────────────────────────────
# RUTA RAÍZ
# ─────────────────────────────────────────────────────────────
from fastapi.responses import RedirectResponse

@app.get("/", include_in_schema=False)
def raiz():
    return RedirectResponse(url="/clases")
