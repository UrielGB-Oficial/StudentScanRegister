"""
routers/listado.py — Gestión de Alumnos, Subida Masiva (Excel / CSV) y Matriz de Asistencia

Este router maneja:
  1. GET  /clases/{id}/alumnos          -> Lista de alumnos de la clase
  2. POST /clases/{id}/alumnos          -> Alta manual de un alumno
  3. POST /clases/{id}/alumnos/upload   -> Subida de archivo Excel (.xlsx, .xlsm) o CSV (.csv)
  4. POST /clases/{id}/alumnos/{alumno_id}/eliminar -> Eliminar un alumno
  5. GET  /clases/{id}/asistencia       -> Vista en navegador de la tabla de asistencia
"""

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.database import get_session
from app.models import GRADOS_VALIDOS, Alumno, Asistencia, Clase, Sesion
from app.utils import obtener_ciclo_actual, procesar_archivo_alumnos

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
        request=request,
        name="alumnos.html",
        context={
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

    stmt_existente = select(Alumno).where(Alumno.codigo_alumno == codigo_limpio)
    alumno_existente = session.exec(stmt_existente).first()

    if alumno_existente:
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
# 3. Subida masiva de alumnos mediante archivo (.xlsx, .xlsm, .csv)
# ─────────────────────────────────────────────────────────────
@router.post("/{clase_id}/alumnos/upload")
async def subir_excel_alumnos(
    clase_id: int,
    archivo: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    """
    Procesa un archivo .xlsx, .xlsm o .csv y registra a los alumnos en la clase.
    """
    contenido = await archivo.read()
    try:
        lista_alumnos = procesar_archivo_alumnos(contenido, archivo.filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    for codigo_str, nombre_str in lista_alumnos:
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
        request=request,
        name="asistencia.html",
        context={
            "clase": clase,
            "sesiones": sesiones,
            "filas": filas_asistencia,
            "alumnos_total": len(alumnos),
            "grados": GRADOS_VALIDOS,
            "ciclo_actual": obtener_ciclo_actual(),
        },
    )