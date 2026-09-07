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

import io

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
import openpyxl
from sqlmodel import Session, select

from app.database import get_session
from app.dependencies import requiere_login
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
    _=Depends(requiere_login),
):
    # Consulta: SELECT * FROM clase
    clases = session.exec(select(Clase)).all()

    # Consulta: SELECT * FROM profesor
    profesores = session.exec(select(Profesor)).all()

    return templates.TemplateResponse(
        request=request,
        name="clases.html",
        context={
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
    _=Depends(requiere_login),
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
    _=Depends(requiere_login),
):
    profesor = session.get(Profesor, profesor_id)
    if not profesor:
        raise HTTPException(status_code=404, detail="Profesor no encontrado")

    stmt_clases = select(Clase).where(Clase.profesor_id == profesor_id)
    if session.exec(stmt_clases).first():
        raise HTTPException(
            status_code=400,
            detail="No se puede eliminar el profesor porque tiene clases asignadas.",
        )

    session.delete(profesor)
    session.commit()
    return RedirectResponse(url="/clases", status_code=status.HTTP_303_SEE_OTHER)


# ─────────────────────────────────────────────────────────────
# 7. Crear grupo + subir Excel en un solo paso
# ─────────────────────────────────────────────────────────────
@router.post("/nueva-con-excel")
async def crear_clase_con_excel(
    nombre_clase: str = Form(...),
    archivo: UploadFile = File(...),
    session: Session = Depends(get_session),
    _=Depends(requiere_login),
):
    # Buscar el profesor (solo hay uno)
    profesor = session.exec(select(Profesor)).first()
    if not profesor:
        raise HTTPException(status_code=400, detail="No hay ningún profesor registrado. Registra al profesor primero.")

    # Crear la clase
    nueva_clase = Clase(nombre_clase=nombre_clase.strip(), profesor_id=profesor.id)
    session.add(nueva_clase)
    session.commit()
    session.refresh(nueva_clase)

    # Leer el Excel y registrar alumnos
    contenido = await archivo.read()
    wb = openpyxl.load_workbook(filename=io.BytesIO(contenido), data_only=True)
    ws = wb.active

    col_codigo, col_nombre = 1, 2
    primera_fila = [str(cell.value or "").strip().lower() for cell in ws[1]]
    for idx, val in enumerate(primera_fila, start=1):
        if "cod" in val:
            col_codigo = idx
        elif "nom" in val or "alum" in val:
            col_nombre = idx

    for row in ws.iter_rows(min_row=2, values_only=False):
        val_cod = row[col_codigo - 1].value if len(row) >= col_codigo else None
        val_nom = row[col_nombre - 1].value if len(row) >= col_nombre else None
        if val_cod is None or val_nom is None:
            continue
        codigo_str = str(val_cod).strip()
        if codigo_str.endswith(".0"):
            codigo_str = codigo_str[:-2]
        nombre_str = str(val_nom).strip()
        if not codigo_str or not nombre_str:
            continue
        stmt = select(Alumno).where(Alumno.codigo_alumno == codigo_str)
        alumno_db = session.exec(stmt).first()
        if alumno_db:
            alumno_db.nombre_alumno = nombre_str
            alumno_db.clase_id = nueva_clase.id
            session.add(alumno_db)
        else:
            session.add(Alumno(codigo_alumno=codigo_str, nombre_alumno=nombre_str, clase_id=nueva_clase.id))

    session.commit()
    return RedirectResponse(url=f"/clases/{nueva_clase.id}/asistencia", status_code=status.HTTP_303_SEE_OTHER)