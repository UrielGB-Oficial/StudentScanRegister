"""
routers/auth.py — Autenticación del Sistema (Un solo usuario: el profesor Horacio)

Como solo hay un usuario, las credenciales están fijas en una variable de entorno
o en este archivo directamente. No se necesita tabla de usuarios en la BD.

Rutas:
  GET  /login   -> Muestra el formulario de login
  POST /login   -> Valida credenciales y crea sesión
  GET  /logout  -> Cierra la sesión
"""

import os

from fastapi import APIRouter, Form, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# ─────────────────────────────────────────────────────────────
# Credenciales del único usuario del sistema
# El profesor puede cambiar la contraseña aquí directamente.
# ─────────────────────────────────────────────────────────────
USUARIO_VALIDO = os.getenv("APP_USUARIO", "horacio")     # o "2201852"
PASSWORD_VALIDA = os.getenv("APP_PASSWORD", "padawans2026")

# ─────────────────────────────────────────────────────────────
# Mostrar formulario de login
# ─────────────────────────────────────────────────────────────
@router.get("/login")
def mostrar_login(request: Request):
    # Si ya inició sesión, redirigir al dashboard
    if request.session.get("autenticado"):
        return RedirectResponse(url="/clases")
    return templates.TemplateResponse(request=request, name="login.html", context={"error": None})


# ─────────────────────────────────────────────────────────────
# Procesar login
# ─────────────────────────────────────────────────────────────
@router.post("/login")
def procesar_login(
    request: Request,
    usuario: str = Form(...),
    password: str = Form(...),
):
    # Comparamos en minúsculas para que no falle si el usuario
    # escribe "Horacio" en vez de "horacio"
    if usuario.strip().lower() == USUARIO_VALIDO.lower() and password == PASSWORD_VALIDA:
        request.session["autenticado"] = True
        return RedirectResponse(url="/clases", status_code=status.HTTP_303_SEE_OTHER)

    # Credenciales incorrectas — regresamos a login con mensaje de error
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"error": "Usuario o contraseña incorrectos. Inténtalo de nuevo."},
        status_code=status.HTTP_401_UNAUTHORIZED,
    )


# ─────────────────────────────────────────────────────────────
# Cerrar sesión
# ─────────────────────────────────────────────────────────────
@router.get("/logout")
def cerrar_sesion(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
