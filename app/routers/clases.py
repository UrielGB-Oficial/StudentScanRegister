"""
routers/clases.py — Gestión de Clases y Profesores (Panel de Administración)

Este router maneja:
  1. GET  /clases                     -> Muestra la página principal con la lista de clases y profesores
  2. POST /clases                     -> Crea una nueva clase
  3. POST /clases/{clase_id}/editar   -> Actualiza el nombre o profesor de una clase
  4. POST /clases/{clase_id}/eliminar -> Elimina una clase y sus datos asociados
  5. POST /clases/profesores          -> Da de alta un profesor
  6. POST /clases/profesores/{id}/eliminar -> Elimina un profesor
"""

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.database import get_session
from app.models import Alumno, Asistencia, Clase, Profesor, Sesion

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


# ─────────────────────────────────────────────────────────────
# 1. Vista Principal: Listado de Clases y Profesores
# ─────────────────────────────────────────────────────────────
@router.get("")
@router.get("/")
def listar_clases(
    request: Request,
    session: Session = Depends(get_session),
):
    # Consulta: SELECT * FROM clase
    clases = session.exec(select(Clase)).all()

    # Consulta: SELECT * FROM profesor
    profesores = session.exec(select(Profesor)).all()

    return templates.TemplateResponse(
        "clases.html",
        {
            "request": request,
            "clases": clases,
            "profesores": profesores,
        },
    )


# ─────────────────────────────────────────────────────────────
# 2. Crear una nueva Clase
# ─────────────────────────────────────────────────────────────
@router.post("")
@router.post("/")
def crear_clase(
    nombre_clase: str = Form(...),
    profesor_id: int = Form(...),
    session: Session = Depends(get_session),
):
    nueva_clase = Clase(
        nombre_clase=nombre_clase.strip(),
        profesor_id=profesor_id,
    )
    session.add(nueva_clase)
    session.commit()

    # Redirigimos al usuario de regreso a la lista de clases (código HTTP 303: See Other)
    return RedirectResponse(url="/clases", status_code=status.HTTP_303_SEE_OTHER)


# ─────────────────────────────────────────────────────────────
# 3. Editar una Clase existente
# ─────────────────────────────────────────────────────────────
@router.post("/{clase_id}/editar")
def editar_clase(
    clase_id: int,
    nombre_clase: str = Form(...),
    profesor_id: int = Form(...),
    session: Session = Depends(get_session),
):
    clase = session.get(Clase, clase_id)
    if not clase:
        raise HTTPException(status_code=404, detail="Clase no encontrada")

    clase.nombre_clase = nombre_clase.strip()
    clase.profesor_id = profesor_id
    session.add(clase)
    session.commit()

    return RedirectResponse(url="/clases", status_code=status.HTTP_303_SEE_OTHER)


# ─────────────────────────────────────────────────────────────
# 4. Eliminar una Clase
# ─────────────────────────────────────────────────────────────
@router.post("/{clase_id}/eliminar")
def eliminar_clase(
    clase_id: int,
    session: Session = Depends(get_session),
):
    clase = session.get(Clase, clase_id)
    if not clase:
        raise HTTPException(status_code=404, detail="Clase no encontrada")

    # 1. Eliminar asistencias de las sesiones de esta clase
    stmt_sesiones = select(Sesion).where(Sesion.clase_id == clase_id)
    sesiones = session.exec(stmt_sesiones).all()
    for s in sesiones:
        stmt_asistencias = select(Asistencia).where(Asistencia.sesion_id == s.id)
        for a in session.exec(stmt_asistencias).all():
            session.delete(a)
        session.delete(s)

    # 2. Eliminar alumnos de esta clase
    stmt_alumnos = select(Alumno).where(Alumno.clase_id == clase_id)
    for al in session.exec(stmt_alumnos).all():
        session.delete(al)

    # 3. Eliminar la clase
    session.delete(clase)
    session.commit()

    return RedirectResponse(url="/clases", status_code=status.HTTP_303_SEE_OTHER)


# ─────────────────────────────────────────────────────────────
# 5. Crear un Profesor
# ─────────────────────────────────────────────────────────────
@router.post("/profesores")
def crear_profesor(
    codigo_profesor: str = Form(...),
    nombre_profesor: str = Form(...),
    session: Session = Depends(get_session),
):
    codigo_limpio = codigo_profesor.strip()

    # Verificamos que no exista un profesor con el mismo código
    stmt_existente = select(Profesor).where(Profesor.codigo_profesor == codigo_limpio)
    if session.exec(stmt_existente).first():
        raise HTTPException(status_code=400, detail="Ya existe un profesor con ese código.")

    nuevo_profesor = Profesor(
        codigo_profesor=codigo_limpio,
        nombre_profesor=nombre_profesor.strip(),
    )
    session.add(nuevo_profesor)
    session.commit()

    return RedirectResponse(url="/clases", status_code=status.HTTP_303_SEE_OTHER)


# ─────────────────────────────────────────────────────────────
# 6. Eliminar un Profesor
# ─────────────────────────────────────────────────────────────
@router.post("/profesores/{profesor_id}/eliminar")
def eliminar_profesor(
    profesor_id: int,
    session: Session = Depends(get_session),
):
    profesor = session.get(Profesor, profesor_id)
    if not profesor:
        raise HTTPException(status_code=404, detail="Profesor no encontrado")

    # Si el profesor tiene clases asignadas, no permitimos borrarlo directamente
    stmt_clases = select(Clase).where(Clase.profesor_id == profesor_id)
    if session.exec(stmt_clases).first():
        raise HTTPException(
            status_code=400,
            detail="No se puede eliminar el profesor porque tiene clases asignadas. Reasigna o elimina las clases primero.",
        )

    session.delete(profesor)
    session.commit()

    return RedirectResponse(url="/clases", status_code=status.HTTP_303_SEE_OTHER)