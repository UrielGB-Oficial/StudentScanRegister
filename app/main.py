# main.py — Punto de entrada del servidor

# Para arrancar el servidor, ejecutas:
#   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000


import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.database import create_db_and_tables
from app.routers import asistencias, clases, listado
from app.routers import auth


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

# SessionMiddleware habilita request.session (como $_SESSION en PHP).
# secret_key se usa para firmar/cifrar la cookie — cámbiala en producción.
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET", "cambia-esta-clave-en-produccion"),
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

# Router de autenticación (login/logout) — sin prefijo
app.include_router(
    auth.router,
    tags=["Autenticación"],
)


# ─────────────────────────────────────────────────────────────
# RUTA RAÍZ
# ─────────────────────────────────────────────────────────────
from fastapi.responses import RedirectResponse

@app.get("/", include_in_schema=False)
def raiz():
    return RedirectResponse(url="/clases")
