# database.py — Conexión a la base de datos SQLite

from pathlib import Path
from sqlmodel import Session, SQLModel, create_engine

# ─────────────────────────────────────────────
# Ruta del archivo de base de datos
# ─────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent
DATABASE_URL = f"sqlite:///{BASE_DIR / 'data' / 'registro.db'}"

# ─────────────────────────────────────────────
# Motor de base de datos
# ─────────────────────────────────────────────
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)


# ─────────────────────────────────────────────
# Crear tablas
# ─────────────────────────────────────────────
def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)
    from app.models import Profesor
    from sqlmodel import select

    with Session(engine) as session:
        profesor = session.exec(select(Profesor)).first()
        if not profesor:
            session.add(Profesor(codigo_profesor="2201852", nombre_profesor="Horacio"))
            session.commit()


# ─────────────────────────────────────────────
# Sesión de base de datos (para los endpoints)
# ─────────────────────────────────────────────
def get_session():
    with Session(engine) as session:
        yield session