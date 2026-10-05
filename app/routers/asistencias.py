"""
routers/asistencias.py — Endpoint del Lector y Gestión de Asistencias

Este archivo contiene:
  1. POST /api/scan : Recibe los escaneos del lector físico (profesor o alumno).
  2. GET /api/asistencias/{clase_id}/excel : Descarga el reporte de asistencia en Excel.
"""

from datetime import date, datetime
import io
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from pydantic import BaseModel
from sqlmodel import Session, select

from app.database import get_session
from app.models import Alumno, Asistencia, Clase, Profesor, Sesion

# Creamos el Router. main.py lo conectará con prefijo "/api"
router = APIRouter()


# ─────────────────────────────────────────────────────────────
# 1. Esquema de datos para la petición del escáner
# ─────────────────────────────────────────────────────────────
class ScanRequest(BaseModel):
    """
    Define la estructura que el lector (o script lector.py, o navegador) envía por HTTP.
    Ejemplo de JSON: { "codigo": "218123456", "clase_id": 1 }
    """
    codigo: str
    clase_id: Optional[int] = None


# ─────────────────────────────────────────────────────────────
# 2. Estado en memoria: Profesor en espera
# ─────────────────────────────────────────────────────────────
profesor_en_espera: Optional[dict] = None


# ─────────────────────────────────────────────────────────────
# 3. Endpoint principal: POST /api/scan
# ─────────────────────────────────────────────────────────────
@router.post("/scan")
def procesar_escaneo(datos: ScanRequest, session: Session = Depends(get_session)):
    """
    Procesa el código leído por el lector de código de barras.
    Identifica automáticamente si es un Profesor o un Alumno y ejecuta la lógica.
    """
    global profesor_en_espera

    # Limpiar el código de espacios, retornos de carro (\r, \n) y caracteres no imprimibles
    raw_codigo = datos.codigo or ""
    codigo_limpio = "".join(c for c in raw_codigo if c.isprintable()).strip()
    codigo_sin_ceros = codigo_limpio.lstrip("0")
    hoy = date.today()
    hora_actual = datetime.now().time()

    print(f"\n[SCAN] Codigo recibido: '{codigo_limpio}' | raw: {repr(raw_codigo)} | clase_id: {datos.clase_id}")

    # ─────────────────────────────────────────────────────────
    # PASO A: ¿El código escaneado es de un PROFESOR?
    # ─────────────────────────────────────────────────────────
    stmt_profesor = select(Profesor).where(Profesor.codigo_profesor == codigo_limpio)
    profesor = session.exec(stmt_profesor).first()

    # Si no coincide exactamente, probar sin ceros a la izquierda
    if not profesor and codigo_sin_ceros and codigo_sin_ceros != codigo_limpio:
        stmt_profesor = select(Profesor).where(Profesor.codigo_profesor == codigo_sin_ceros)
        profesor = session.exec(stmt_profesor).first()

    if profesor:
        profesor_en_espera = {
            "profesor_id": profesor.id,
            "nombre": profesor.nombre_profesor,
            "fecha": hoy,
        }
        print(f"  [PROFESOR] Identificado: {profesor.nombre_profesor} (ID: {profesor.id})")

        # Si se envió clase_id desde la interfaz web, abrimos la sesión de esa clase de inmediato
        if datos.clase_id:
            clase_web = session.get(Clase, datos.clase_id)
            if clase_web and clase_web.profesor_id == profesor.id:
                stmt_ses = select(Sesion).where(Sesion.clase_id == datos.clase_id, Sesion.fecha == hoy)
                ses_activa = session.exec(stmt_ses).first()
                if not ses_activa:
                    ses_activa = Sesion(clase_id=datos.clase_id, fecha=hoy, hora_apertura=hora_actual)
                    session.add(ses_activa)
                    session.commit()
                    session.refresh(ses_activa)
                    print(f"  [SESION] Creada de inmediato para clase: {clase_web.nombre_clase}")

        return {
            "status": "ok",
            "tipo": "profesor",
            "nombre": profesor.nombre_profesor,
            "mensaje": f"Profesor {profesor.nombre_profesor} listo. Registro de asistencia abierto.",
        }

    # ─────────────────────────────────────────────────────────
    # PASO B: ¿El código escaneado es de un ALUMNO?
    # ─────────────────────────────────────────────────────────
    stmt_alumnos = select(Alumno).where(Alumno.codigo_alumno == codigo_limpio)
    alumnos_encontrados = session.exec(stmt_alumnos).all()

    if not alumnos_encontrados and codigo_sin_ceros and codigo_sin_ceros != codigo_limpio:
        stmt_alumnos = select(Alumno).where(Alumno.codigo_alumno == codigo_sin_ceros)
        alumnos_encontrados = session.exec(stmt_alumnos).all()

    if alumnos_encontrados:
        alumno_elegido: Optional[Alumno] = None
        sesion_hoy: Optional[Sesion] = None
        clase: Optional[Clase] = None

        # Si se especificó clase_id desde la página actual, priorizar la inscripción en esa clase
        if datos.clase_id:
            for al in alumnos_encontrados:
                if al.clase_id == datos.clase_id:
                    alumno_elegido = al
                    clase = session.get(Clase, al.clase_id)
                    break

        # 1. Si hay un profesor en espera hoy
        if profesor_en_espera and profesor_en_espera["fecha"] == hoy:
            if not alumno_elegido:
                for al in alumnos_encontrados:
                    c = session.get(Clase, al.clase_id)
                    if c and c.profesor_id == profesor_en_espera["profesor_id"]:
                        alumno_elegido = al
                        clase = c
                        break

            if not alumno_elegido:
                return {
                    "status": "error",
                    "tipo": "alumno",
                    "mensaje": f"El alumno no está en ninguna clase del profesor en espera ({profesor_en_espera['nombre']}).",
                }

            # Abrimos la sesión del día para esta clase si no existe
            stmt_sesion = select(Sesion).where(
                Sesion.clase_id == alumno_elegido.clase_id,
                Sesion.fecha == hoy,
            )
            sesion_hoy = session.exec(stmt_sesion).first()
            if not sesion_hoy:
                sesion_hoy = Sesion(clase_id=alumno_elegido.clase_id, fecha=hoy, hora_apertura=hora_actual)
                session.add(sesion_hoy)
                session.commit()
                session.refresh(sesion_hoy)

            # Limpiamos el modo espera del profesor porque la clase ya inició
            profesor_en_espera = None

        else:
            # 2. Si no hay profesor en espera en RAM, buscamos si hay una sesión ya abierta hoy
            if alumno_elegido:
                stmt_sesion = select(Sesion).where(
                    Sesion.clase_id == alumno_elegido.clase_id,
                    Sesion.fecha == hoy,
                )
                sesion_hoy = session.exec(stmt_sesion).first()

            if not sesion_hoy:
                for al in alumnos_encontrados:
                    stmt_sesion = select(Sesion).where(
                        Sesion.clase_id == al.clase_id,
                        Sesion.fecha == hoy,
                    )
                    s = session.exec(stmt_sesion).first()
                    if s:
                        alumno_elegido = al
                        sesion_hoy = s
                        clase = session.get(Clase, al.clase_id)
                        break

            # 3. Si aún no hay sesión hoy, pero el alumno pertenece a una clase del único profesor
            if not sesion_hoy:
                # Comprobar si hay un único profesor en el sistema
                profesor_unico = session.exec(select(Profesor)).first()
                if profesor_unico and alumno_elegido:
                    c = session.get(Clase, alumno_elegido.clase_id)
                    if c and c.profesor_id == profesor_unico.id:
                        # Auto-abrir sesión para facilitar pruebas y uso continuo
                        sesion_hoy = Sesion(clase_id=alumno_elegido.clase_id, fecha=hoy, hora_apertura=hora_actual)
                        session.add(sesion_hoy)
                        session.commit()
                        session.refresh(sesion_hoy)
                        clase = c
                        print(f"  [SESION] Abierta automaticamente para: {clase.nombre_clase}")

            if not sesion_hoy or not alumno_elegido:
                return {
                    "status": "error",
                    "tipo": "alumno",
                    "mensaje": "No hay sesión abierta hoy para este grupo. El profesor debe escanear su credencial primero o presionar 'Abrir registro de hoy'.",
                }

        # 4. Registrar o actualizar la asistencia del alumno
        stmt_asistencia = select(Asistencia).where(
            Asistencia.sesion_id == sesion_hoy.id,
            Asistencia.alumno_id == alumno_elegido.id,
        )
        asistencia_existente = session.exec(stmt_asistencia).first()

        if asistencia_existente:
            asistencia_existente.hora_llegada = hora_actual
            session.add(asistencia_existente)
            session.commit()
            print(f"  [OK] Asistencia actualizada: {alumno_elegido.nombre_alumno} ({hora_actual.strftime('%H:%M:%S')})")
            return {
                "status": "ok",
                "tipo": "alumno",
                "nombre": alumno_elegido.nombre_alumno,
                "clase": clase.nombre_clase if clase else "",
                "mensaje": f"Asistencia ya registrada. Hora actualizada a {hora_actual.strftime('%H:%M:%S')}.",
            }
        else:
            nueva_asistencia = Asistencia(
                sesion_id=sesion_hoy.id,
                alumno_id=alumno_elegido.id,
                hora_llegada=hora_actual,
            )
            session.add(nueva_asistencia)
            session.commit()
            print(f"  [OK] Asistencia registrada: {alumno_elegido.nombre_alumno} ({hora_actual.strftime('%H:%M:%S')})")
            return {
                "status": "ok",
                "tipo": "alumno",
                "nombre": alumno_elegido.nombre_alumno,
                "clase": clase.nombre_clase if clase else "",
                "mensaje": f"Asistencia registrada con éxito: {alumno_elegido.nombre_alumno}",
            }

    # ─────────────────────────────────────────────────────────
    # PASO C: El código no es ni de Profesor ni de Alumno
    # ─────────────────────────────────────────────────────────
    print(f"  [WARN] Codigo '{codigo_limpio}' no encontrado en profesores ni alumnos.")
    return {
        "status": "error",
        "tipo": "desconocido",
        "mensaje": f"El código '{codigo_limpio}' no está registrado en el sistema.",
    }


# ─────────────────────────────────────────────────────────────
# 4. Abrir sesión del día manualmente desde la interfaz web
# ─────────────────────────────────────────────────────────────
@router.post("/sesiones/{clase_id}/abrir")
def abrir_sesion_manualmente(clase_id: int, session: Session = Depends(get_session)):
    """
    Permite abrir la sesión de hoy para una clase desde un botón en la interfaz web,
    sin requerir obligatoriamente el escaneo previo de la credencial del profesor.
    """
    clase = session.get(Clase, clase_id)
    if not clase:
        raise HTTPException(status_code=404, detail="Clase no encontrada")

    hoy = date.today()
    hora_actual = datetime.now().time()

    stmt = select(Sesion).where(Sesion.clase_id == clase_id, Sesion.fecha == hoy)
    sesion_hoy = session.exec(stmt).first()

    if not sesion_hoy:
        sesion_hoy = Sesion(clase_id=clase_id, fecha=hoy, hora_apertura=hora_actual)
        session.add(sesion_hoy)
        session.commit()
        session.refresh(sesion_hoy)
        mensaje = f"Sesión abierta exitosamente para {clase.nombre_clase}."
    else:
        mensaje = f"La sesión de hoy ya estaba abierta para {clase.nombre_clase}."

    return {
        "status": "ok",
        "sesion_id": sesion_hoy.id,
        "fecha": str(sesion_hoy.fecha),
        "hora_apertura": sesion_hoy.hora_apertura.strftime("%H:%M:%S") if sesion_hoy.hora_apertura else None,
        "mensaje": mensaje,
    }


# ─────────────────────────────────────────────────────────────
# 4. Endpoint: Descarga de Excel de Asistencias
# ─────────────────────────────────────────────────────────────
@router.get("/asistencias/{clase_id}/excel")
def descargar_excel_asistencias(clase_id: int, session: Session = Depends(get_session)):
    """
    Genera y descarga un archivo Excel (.xlsx) con la matriz de asistencia:
      - Filas: Alumnos de la clase (código y nombre)
      - Columnas: Fechas de las sesiones impartidas
      - Celdas: '✓' si asistió o '—' si faltó
    """
    clase = session.get(Clase, clase_id)
    if not clase:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clase no encontrada")

    # Obtenemos los alumnos de la clase ordenados alfabéticamente
    stmt_alumnos = select(Alumno).where(Alumno.clase_id == clase_id).order_by(Alumno.nombre_alumno)
    alumnos = session.exec(stmt_alumnos).all()

    # Obtenemos todas las sesiones registradas para esta clase ordenadas por fecha
    stmt_sesiones = select(Sesion).where(Sesion.clase_id == clase_id).order_by(Sesion.fecha)
    sesiones = session.exec(stmt_sesiones).all()

    # Obtenemos todos los registros de asistencias para las sesiones de esta clase
    ids_sesiones = [s.id for s in sesiones if s.id is not None]
    asistencias_map = set()  # Guardará tuplas (sesion_id, alumno_id) para búsqueda rápida

    if ids_sesiones:
        stmt_asistencias = select(Asistencia).where(Asistencia.sesion_id.in_(ids_sesiones))
        for a in session.exec(stmt_asistencias).all():
            asistencias_map.add((a.sesion_id, a.alumno_id))

    # Creamos el libro de Excel con openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Lista de Asistencia"

    # Estilos visuales para el Excel
    header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True)
    center_align = Alignment(horizontal="center", vertical="center")

    # Encabezados: Código, Nombre de Alumno, y luego cada Fecha
    headers = ["Código", "Nombre del Alumno"]
    for sesion in sesiones:
        headers.append(sesion.fecha.strftime("%d/%m/%Y"))
    headers.append("Total Asistencias")

    ws.append(headers)

    # Aplicamos estilo a la fila de encabezados
    for col_num in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_num)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center_align

    # Llenamos los datos de cada alumno
    for alumno in alumnos:
        fila = [alumno.codigo_alumno, alumno.nombre_alumno]
        total_alumno = 0

        for sesion in sesiones:
            if (sesion.id, alumno.id) in asistencias_map:
                fila.append("✓")
                total_alumno += 1
            else:
                fila.append("—")

        fila.append(total_alumno)
        ws.append(fila)

    # Ajustamos el ancho de las columnas automáticamente
    for col in ws.columns:
        max_len = max(len(str(cell.value or "")) for cell in col)
        col_letter = openpyxl.utils.get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 3, 12)

    # Guardamos el archivo en memoria (sin guardarlo en disco físico)
    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)

    nombre_archivo = f"Asistencia_{clase.nombre_clase.replace(' ', '_')}_{date.today()}.xlsx"

    # Enviamos el archivo como descarga al navegador
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{nombre_archivo}"'},
    )


# ─────────────────────────────────────────────────────────────
# 5. Togglear asistencia de un alumno en una sesión
# ─────────────────────────────────────────────────────────────
class ToggleAsistenciaRequest(BaseModel):
    sesion_id: int
    alumno_id: int

@router.post("/asistencias/toggle")
def toggle_asistencia(datos: ToggleAsistenciaRequest, session: Session = Depends(get_session)):
    """
    Alterna el estado de asistencia de un alumno en una sesión.
    Si existe el registro, lo elimina (ausentarse). Si no existe, lo crea (marcar presente).
    """
    stmt = select(Asistencia).where(
        Asistencia.sesion_id == datos.sesion_id,
        Asistencia.alumno_id == datos.alumno_id,
    )
    existente = session.exec(stmt).first()

    if existente:
        session.delete(existente)
        session.commit()
        return {"status": "ok", "asistio": False, "mensaje": "Asistencia eliminada"}
    else:
        from datetime import datetime
        nueva = Asistencia(
            sesion_id=datos.sesion_id,
            alumno_id=datos.alumno_id,
            hora_llegada=datetime.now().time(),
        )
        session.add(nueva)
        session.commit()
        return {"status": "ok", "asistio": True, "mensaje": "Asistencia registrada"}


# ─────────────────────────────────────────────────────────────
# 6. Agregar una nueva sesión (columna de fecha) a una clase
# ─────────────────────────────────────────────────────────────
class NuevaSesionRequest(BaseModel):
    clase_id: int
    fecha: Optional[str] = None  # Formato YYYY-MM-DD o None para fecha de hoy

@router.post("/sesiones/agregar")
def agregar_sesion(datos: NuevaSesionRequest, session: Session = Depends(get_session)):
    """
    Crea una nueva sesión para la clase indicada. Si no se proporciona fecha, usa hoy.
    """
    from datetime import date as date_type, datetime

    if datos.fecha:
        try:
            fecha_obj = date_type.fromisoformat(datos.fecha)
        except ValueError:
            raise HTTPException(status_code=400, detail="Formato de fecha inválido. Use YYYY-MM-DD.")
    else:
        fecha_obj = date_type.today()

    clase = session.get(Clase, datos.clase_id)
    if not clase:
        raise HTTPException(status_code=404, detail="Clase no encontrada")

    # Verificar que no exista ya una sesión en esa fecha para esta clase
    stmt = select(Sesion).where(Sesion.clase_id == datos.clase_id, Sesion.fecha == fecha_obj)
    existente = session.exec(stmt).first()
    if existente:
        return {"status": "ok", "sesion_id": existente.id, "fecha": str(existente.fecha), "nueva": False}

    nueva_sesion = Sesion(clase_id=datos.clase_id, fecha=fecha_obj, hora_apertura=datetime.now().time())
    session.add(nueva_sesion)
    session.commit()
    session.refresh(nueva_sesion)

    return {"status": "ok", "sesion_id": nueva_sesion.id, "fecha": str(nueva_sesion.fecha), "nueva": True}


# ─────────────────────────────────────────────────────────────
# 7. Editar la fecha de una sesión existente
# ─────────────────────────────────────────────────────────────
class EditarSesionRequest(BaseModel):
    fecha: str  # Formato YYYY-MM-DD

@router.post("/sesiones/{sesion_id}/editar")
def editar_sesion(sesion_id: int, datos: EditarSesionRequest, session: Session = Depends(get_session)):
    """
    Cambia la fecha de una sesión existente.
    """
    from datetime import date as date_type

    sesion = session.get(Sesion, sesion_id)
    if not sesion:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")

    try:
        nueva_fecha = date_type.fromisoformat(datos.fecha)
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato de fecha inválido. Use YYYY-MM-DD.")

    # Verificar que no haya otra sesión con la misma fecha en esta clase
    stmt = select(Sesion).where(
        Sesion.clase_id == sesion.clase_id,
        Sesion.fecha == nueva_fecha,
        Sesion.id != sesion_id,
    )
    if session.exec(stmt).first():
        raise HTTPException(status_code=400, detail=f"Ya existe una sesión el {datos.fecha} en esta clase.")

    sesion.fecha = nueva_fecha
    session.add(sesion)
    session.commit()

    return {"status": "ok", "sesion_id": sesion_id, "fecha": str(nueva_fecha)}


# ─────────────────────────────────────────────────────────────
# 8. Eliminar una sesión y todas sus asistencias
# ─────────────────────────────────────────────────────────────
@router.delete("/sesiones/{sesion_id}")
def eliminar_sesion(sesion_id: int, session: Session = Depends(get_session)):
    """
    Elimina una sesión y todos los registros de asistencia asociados.
    """
    sesion = session.get(Sesion, sesion_id)
    if not sesion:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")

    # Eliminar asistencias de esa sesión primero
    stmt_asistencias = select(Asistencia).where(Asistencia.sesion_id == sesion_id)
    for a in session.exec(stmt_asistencias).all():
        session.delete(a)

    session.delete(sesion)
    session.commit()

    return {"status": "ok", "mensaje": f"Sesión del {sesion.fecha} eliminada correctamente."}