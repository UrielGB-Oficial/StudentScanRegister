# database.py — Conexión a la base de datos SQLite

from collections.abc import Generator
from pathlib import Path

# pyrefly: ignore [missing-import]
from sqlmodel import Session, SQLModel, create_engine, select

# ─────────────────────────────────────────────
# Ruta del archivo de base de datos
# ─────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"

# Aseguramos que la carpeta data exista para evitar OperationalError de SQLite
DATA_DIR.mkdir(parents=True, exist_ok=True)

# as_posix() convierte barras invertidas de Windows a / para SQLite URL estándar
DATABASE_URL = f"sqlite:///{(DATA_DIR / 'registro.db').as_posix()}"

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
    # 1. Importamos modelos para que SQLModel registre sus tablas en metadata
    from app.models import Profesor

    # 2. Crea las tablas si no existen
    SQLModel.metadata.create_all(engine)

    # 3. Migración automática de columnas para bases de datos existentes
    with engine.connect() as conn:
        cursor = conn.connection.cursor()
        columnas_clase = [col[1] for col in cursor.execute("PRAGMA table_info(clase)").fetchall()]
        if columnas_clase:
            if "grado" not in columnas_clase:
                cursor.execute("ALTER TABLE clase ADD COLUMN grado VARCHAR(10)")
            if "ciclo" not in columnas_clase:
                cursor.execute("ALTER TABLE clase ADD COLUMN ciclo VARCHAR(20)")
            conn.connection.commit()

    # 4. Semilla inicial: Horacio como profesor único por defecto
    with Session(engine) as session:
        profesor = session.exec(select(Profesor)).first()
        if not profesor:
            session.add(Profesor(codigo_profesor="2201852", nombre_profesor="Horacio"))
            session.commit()


# ─────────────────────────────────────────────
# Sesión de base de datos (para los endpoints)
# ─────────────────────────────────────────────
def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session