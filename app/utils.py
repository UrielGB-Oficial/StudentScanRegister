"""
utils.py — Funciones auxiliares para ciclos y procesamiento de archivos (XLSX, CSV)
"""

import csv
from datetime import date
import io
import openpyxl


def obtener_ciclo_actual() -> str:
    """
    Devuelve el ciclo actual en formato 'YYYYA' o 'YYYYB'.
    Enero a Junio  -> A
    Julio a Diciembre -> B
    Ejemplo: 2026B
    """
    hoy = date.today()
    periodo = "A" if hoy.month <= 6 else "B"
    return f"{hoy.year}{periodo}"


def normalizar_codigo(valor: any) -> str:
    """Limpia y normaliza el código de alumno."""
    if valor is None:
        return ""
    texto = str(valor).strip()
    # Si viene con decimal como 2181234.0, quitamos el .0
    if texto.endswith(".0"):
        texto = texto[:-2]
    return texto


def procesar_archivo_alumnos(contenido: bytes, filename: str) -> list[tuple[str, str]]:
    """
    Procesa un archivo .xlsx, .xlsm o .csv y devuelve una lista de tuplas:
    [(codigo_alumno, nombre_alumno), ...]
    """
    nombre_min = filename.lower().strip()
    alumnos: list[tuple[str, str]] = []

    if nombre_min.endswith((".xlsx", ".xlsm")):
        wb = openpyxl.load_workbook(filename=io.BytesIO(contenido), data_only=True)
        ws = wb.active

        col_codigo = 1
        col_nombre = 2

        # Detectar columnas por encabezado
        primera_fila = [str(cell.value or "").strip().lower() for cell in ws[1]]
        for idx, val in enumerate(primera_fila, start=1):
            if "cod" in val:
                col_codigo = idx
            elif "nom" in val or "alum" in val:
                col_nombre = idx

        for row in ws.iter_rows(min_row=2, values_only=False):
            val_cod = row[col_codigo - 1].value if len(row) >= col_codigo else None
            val_nom = row[col_nombre - 1].value if len(row) >= col_nombre else None

            cod_str = normalizar_codigo(val_cod)
            nom_str = str(val_nom or "").strip()

            if cod_str and nom_str:
                alumnos.append((cod_str, nom_str))

    elif nombre_min.endswith(".csv"):
        # Detectar codificación
        texto = None
        for encoding in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
            try:
                texto = contenido.decode(encoding)
                break
            except UnicodeDecodeError:
                continue

        if texto is None:
            raise ValueError("No se pudo decodificar el archivo CSV. Asegúrate de que esté en UTF-8 o ANSI.")

        # Detectar delimitador (habitualmente ';' en Excel en español o ',' estándar)
        lineas = [l for l in texto.splitlines() if l.strip()]
        if not lineas:
            return []

        muestra = "\n".join(lineas[:5])
        delimitador = ","
        try:
            dialect = csv.Sniffer().sniff(muestra, delimiters=[",", ";", "\t", "|"])
            delimitador = dialect.delimiter
        except Exception:
            # Fallback simple si sniffer falla
            if muestra.count(";") > muestra.count(","):
                delimitador = ";"

        reader = csv.reader(io.StringIO(texto), delimiter=delimitador)
        filas = list(reader)
        if not filas:
            return []

        # Revisamos si la primera fila es encabezado
        primera = [celda.strip().lower() for celda in filas[0]]
        tiene_encabezado = any("cod" in c or "nom" in c or "alum" in c for c in primera)

        col_cod = 0
        col_nom = 1
        fila_inicio = 0

        if tiene_encabezado:
            fila_inicio = 1
            for idx, val in enumerate(primera):
                if "cod" in val:
                    col_cod = idx
                elif "nom" in val or "alum" in val:
                    col_nom = idx

        for fila in filas[fila_inicio:]:
            if not fila:
                continue
            val_cod = fila[col_cod] if len(fila) > col_cod else ""
            val_nom = fila[col_nom] if len(fila) > col_nom else ""

            cod_str = normalizar_codigo(val_cod)
            nom_str = str(val_nom).strip()

            if cod_str and nom_str:
                alumnos.append((cod_str, nom_str))

    else:
        raise ValueError("Formato de archivo no soportado. Debe ser un archivo Excel (.xlsx, .xlsm) o CSV (.csv).")

    return alumnos
