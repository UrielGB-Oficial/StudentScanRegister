"""
routers/listado.py — Gestión de Alumnos, Subida Masiva de Excel y Matriz de Asistencia

Este router maneja:
  1. GET  /clases/{id}/alumnos          -> Lista de alumnos de la clase
  2. POST /clases/{id}/alumnos          -> Alta manual de un alumno
  3. POST /clases/{id}/alumnos/upload   -> Subida de archivo Excel para alta masiva
  4. POST /clases/{id}/alumnos/{alumno_id}/eliminar -> Eliminar un alumno
  5. GET  /clases/{id}/asistencia       -> Vista en navegador de la tabla de asistencia
"""

import io
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
import openpyxl
from sqlmodel import Session, select

from app.database import get_session
from app.models import Alumno, Asistencia, Clase, Sesion

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


# ─────────────────────────────────────────────────────────────
# 1. Ver lista de alumnos de una clase
# ─────────────────────────────────────────────────────────────
@router.get("/{clase_id}/alumnos")
def ver_alumnos(
    clase_id: int,
    request: Request,
    session: Session = Depends(get_session),
):
    clase = session.get(Clase, clase_id)
    if not clase:
        raise HTTPException(status_code=404, detail="Clase no encontrada")

    stmt_alumnos = select(Alumno).where(Alumno.clase_id == clase_id).order_by(Alumno.nombre_alumno)
    alumnos = session.exec(stmt_alumnos).all()

    return templates.TemplateResponse(
        "alumnos.html",
        {
            "request": request,
            "clase": clase,
            "alumnos": alumnos,
        },
    )


# ─────────────────────────────────────────────────────────────
# 2. Alta manual de un alumno (uno por uno)
# ─────────────────────────────────────────────────────────────
@router.post("/{clase_id}/alumnos")
def agregar_alumno_manual(
    clase_id: int,
    codigo_alumno: str = Form(...),
    nombre_alumno: str = Form(...),
    session: Session = Depends(get_session),
):
    codigo_limpio = codigo_alumno.strip()
    nombre_limpio = nombre_alumno.strip()

    # Verificamos si ya existe ese código
    stmt_existente = select(Alumno).where(Alumno.codigo_alumno == codigo_limpio)
    alumno_existente = session.exec(stmt_existente).first()

    if alumno_existente:
        # Si ya existe, actualizamos su nombre y lo reasignamos a esta clase
        alumno_existente.nombre_alumno = nombre_limpio
        alumno_existente.clase_id = clase_id
        session.add(alumno_existente)
    else:
        nuevo_alumno = Alumno(
            codigo_alumno=codigo_limpio,
            nombre_alumno=nombre_limpio,
            clase_id=clase_id,
        )
        session.add(nuevo_alumno)

    session.commit()
    return RedirectResponse(url=f"/clases/{clase_id}/alumnos", status_code=status.HTTP_303_SEE_OTHER)


# ─────────────────────────────────────────────────────────────
# 3. Subida masiva de alumnos mediante archivo Excel (.xlsx)
# ─────────────────────────────────────────────────────────────
@router.post("/{clase_id}/alumnos/upload")
async def subir_excel_alumnos(
    clase_id: int,
    archivo: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    """
    Lee un archivo Excel con las columnas:
      - Columna A o con encabezado 'codigo' / 'código': Código del alumno
      - Columna B o con encabezado 'nombre': Nombre del alumno
    """
    if not archivo.filename.endswith((".xlsx", ".xlsm")):
        raise HTTPException(status_code=400, detail="El archivo debe ser formato Excel (.xlsx)")

    contenido = await archivo.read()
    wb = openpyxl.load_workbook(filename=io.BytesIO(contenido), data_only=True)
    ws = wb.active

    # Detectar qué columnas corresponden a código y nombre
    col_codigo = 1
    col_nombre = 2

    primera_fila = [str(cell.value or "").strip().lower() for cell in ws[1]]
    for idx, val in enumerate(primera_fila, start=1):
        if "cod" in val:
            col_codigo = idx
        elif "nom" in val or "alum" in val:
            col_nombre = idx

    # Leemos las filas a partir de la fila 2 (saltando los encabezados)
    for row in ws.iter_rows(min_row=2, values_only=False):
        val_cod = row[col_codigo - 1].value if len(row) >= col_codigo else None
        val_nom = row[col_nombre - 1].value if len(row) >= col_nombre else None

        if val_cod is None or val_nom is None:
            continue

        codigo_str = str(val_cod).strip()
        # Si el Excel leyó un número decimal (ej. 2181234.0), quitamos el .0
        if codigo_str.endswith(".0"):
            codigo_str = codigo_str[:-2]

        nombre_str = str(val_nom).strip()

        if not codigo_str or not nombre_str:
            continue

        # Buscamos si ya existe el alumno para actualizar o crear nuevo
        stmt = select(Alumno).where(Alumno.codigo_alumno == codigo_str)
        alumno_db = session.exec(stmt).first()

        if alumno_db:
            alumno_db.nombre_alumno = nombre_str
            alumno_db.clase_id = clase_id
            session.add(alumno_db)
        else:
            nuevo = Alumno(
                codigo_alumno=codigo_str,
                nombre_alumno=nombre_str,
                clase_id=clase_id,
            )
            session.add(nuevo)

    session.commit()
    return RedirectResponse(url=f"/clases/{clase_id}/alumnos", status_code=status.HTTP_303_SEE_OTHER)


# ─────────────────────────────────────────────────────────────
# 4. Eliminar un Alumno
# ─────────────────────────────────────────────────────────────
@router.post("/{clase_id}/alumnos/{alumno_id}/eliminar")
def eliminar_alumno(
    clase_id: int,
    alumno_id: int,
    session: Session = Depends(get_session),
):
    alumno = session.get(Alumno, alumno_id)
    if alumno:
        # Borramos sus asistencias primero
        stmt_asistencias = select(Asistencia).where(Asistencia.alumno_id == alumno_id)
        for a in session.exec(stmt_asistencias).all():
            session.delete(a)
        session.delete(alumno)
        session.commit()

    return RedirectResponse(url=f"/clases/{clase_id}/alumnos", status_code=status.HTTP_303_SEE_OTHER)


# ─────────────────────────────────────────────────────────────
# 5. Vista de Asistencias (Matriz en pantalla)
# ─────────────────────────────────────────────────────────────
@router.get("/{clase_id}/asistencia")
def ver_matriz_asistencia(
    clase_id: int,
    request: Request,
    session: Session = Depends(get_session),
):
    clase = session.get(Clase, clase_id)
    if not clase:
        raise HTTPException(status_code=404, detail="Clase no encontrada")

    # Alumnos de la clase
    stmt_alumnos = select(Alumno).where(Alumno.clase_id == clase_id).order_by(Alumno.nombre_alumno)
    alumnos = session.exec(stmt_alumnos).all()

    # Sesiones impartidas
    stmt_sesiones = select(Sesion).where(Sesion.clase_id == clase_id).order_by(Sesion.fecha)
    sesiones = session.exec(stmt_sesiones).all()

    # Mapa de asistencias (sesion_id, alumno_id)
    ids_sesiones = [s.id for s in sesiones if s.id is not None]
    asistencias_map = set()
    if ids_sesiones:
        stmt_asistencias = select(Asistencia).where(Asistencia.sesion_id.in_(ids_sesiones))
        for a in session.exec(stmt_asistencias).all():
            asistencias_map.add((a.sesion_id, a.alumno_id))

    # Construimos la estructura de datos para la plantilla HTML
    filas_asistencia = []
    for al in alumnos:
        presente_en = []
        total = 0
        for s in sesiones:
            asistio = (s.id, al.id) in asistencias_map
            presente_en.append(asistio)
            if asistio:
                total += 1
        filas_asistencia.append({
            "alumno": al,
            "sesiones_asistidas": presente_en,
            "total": total,
        })

    return templates.TemplateResponse(
        "asistencia.html",
        {
            "request": request,
            "clase": clase,
            "sesiones": sesiones,
            "filas": filas_asistencia,
        },
    )