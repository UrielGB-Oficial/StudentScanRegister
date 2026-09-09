# models.py — Tablas de la base de datos

from datetime import date, time
from typing import Optional

from sqlmodel import Field, Relationship, SQLModel


# ─────────────────────────────────────────────
# PROFESOR
# ─────────────────────────────────────────────
class Profesor(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    codigo_profesor: str = Field(max_length=20, unique=True, index=True)
    nombre_profesor: str = Field(max_length=64)
    clases: list["Clase"] = Relationship(back_populates="profesor")


GRADOS_VALIDOS = ["1ro", "2do", "3ro", "4to", "5to", "6to", "7mo", "8vo", "9no"]


# ─────────────────────────────────────────────
# CLASE
# ─────────────────────────────────────────────
class Clase(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    nombre_clase: str = Field(max_length=100)
    grado: Optional[str] = Field(default=None, max_length=10)
    ciclo: Optional[str] = Field(default=None, max_length=20)
    profesor_id: int = Field(foreign_key="profesor.id")
    profesor: Optional[Profesor] = Relationship(back_populates="clases")
    alumnos: list["Alumno"] = Relationship(back_populates="clase")
    sesiones: list["Sesion"] = Relationship(back_populates="clase")



# ─────────────────────────────────────────────
# ALUMNO
# ─────────────────────────────────────────────
class Alumno(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    codigo_alumno: str = Field(max_length=9, unique=True, index=True)
    nombre_alumno: str = Field(max_length=64)
    clase_id: int = Field(foreign_key="clase.id")
    clase: Optional[Clase] = Relationship(back_populates="alumnos")
    asistencias: list["Asistencia"] = Relationship(back_populates="alumno")


# ─────────────────────────────────────────────
# SESION
# ─────────────────────────────────────────────
class Sesion(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    clase_id: int = Field(foreign_key="clase.id")
    fecha: date = Field(default_factory=date.today)
    clase: Optional[Clase] = Relationship(back_populates="sesiones")
    asistencias: list["Asistencia"] = Relationship(back_populates="sesion")


# ─────────────────────────────────────────────
# ASISTENCIA
# ─────────────────────────────────────────────
class Asistencia(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    sesion_id: int = Field(foreign_key="sesion.id")
    alumno_id: int = Field(foreign_key="alumno.id")
    hora_llegada: time = Field()
    sesion: Optional[Sesion] = Relationship(back_populates="asistencias")
    alumno: Optional[Alumno] = Relationship(back_populates="asistencias")
