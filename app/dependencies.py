"""
dependencies.py — Dependencias compartidas entre routers

Aquí definimos la función que protege las rutas del panel de administración.
Si el usuario no ha iniciado sesión, lo redirigimos al login.

Concepto: En PHP harías esto al inicio de cada archivo:
  if (!isset($_SESSION['autenticado'])) { header('Location: login.php'); exit; }

Aquí lo hacemos una sola vez y lo reutilizamos con Depends(requiere_login).
"""

from fastapi import Depends, Request
from fastapi.responses import RedirectResponse


def requiere_login(request: Request):
    """
    Dependencia que verifica si el usuario tiene sesión activa.
    Se usa como parámetro en los endpoints que deben estar protegidos.

    Uso en un endpoint:
        @router.get("/")
        def mi_vista(request: Request, _=Depends(requiere_login)):
            ...
    """
    if not request.session.get("autenticado"):
        # La clase RedirectResponse aquí sería ignorada si se devuelve desde Depends,
        # así que lanzamos una excepción personalizada
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            headers={"Location": "/login"},
        )
