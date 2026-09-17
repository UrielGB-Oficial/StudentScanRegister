"""
utils.py — Funciones auxiliares para ciclos y procesamiento inteligente de archivos (XLSX, CSV)
Compatible con listas de asistencia universitarias (UdeG, SIIAU, formatos oficiales de 2, 3 o 4 columnas).
"""

import csv
from datetime import date
import io
import re
from typing import Any, Optional
import openpyxl


def obtener_ciclo_actual() -> str:
    """
    Devuelve el ciclo actual en formato 'YYYYA' o 'YYYYB'.
    Enero a Junio     -> A
    Julio a Diciembre -> B
    Ejemplo: 2026B
    """
    hoy = date.today()
    periodo = "A" if hoy.month <= 6 else "B"
    return f"{hoy.year}{periodo}"


def normalizar_codigo(valor: Any) -> str:
    """Limpia y normaliza el código de alumno."""
    if valor is None:
        return ""
    texto = str(valor).strip()
    # Si viene con decimal como 2181234.0, quitamos el .0
    if texto.endswith(".0"):
        texto = texto[:-2]
    return texto


# Expresión regular para líneas pegadas en una sola celda/columna (copiado de PDF o texto plano)
# Ejemplos: "01 223992884 ANGEL ANGEL ERIC EDUARDO ICOM" o "223992884 ANGEL ANGEL ERIC EDUARDO"
RE_LINEA_UNICA = re.compile(
    r"^\s*(?:\d{1,3}[\.\s\-\)]+)?(\d{7,11}|[A-Za-z0-9]{6,12})\s+([A-Za-zÁÉÍÓÚáéíóúÑñ\s\.\,\-]+?)(?:\s+[A-Z]{3,6})?\s*$"
)


def detectar_columnas_alumnos(filas: list[list[Any]]) -> tuple[int, int, int]:
    """
    Detecta automáticamente qué columna corresponde al Código y cuál al Nombre del Alumno.
    Soporta:
      - Listas oficiales tipo UdeG/SIIAU: [Consecutivo, Código, Nombre, Carrera]
      - Listas tradicionales de 2 columnas: [Código, Nombre] o [Nombre, Código]
      - Archivos con filas de encabezado (detecta encabezados explícitos)
      - Archivos sin encabezado (heurística por tipo de contenido)
    Devuelve: (indice_columna_codigo, indice_columna_nombre, fila_inicio)
    """
    if not filas:
        return 0, 1, 0

    # 1. Búsqueda de encabezados explícitos en las primeras 10 filas
    palabras_codigo = ("cod", "código", "codigo", "control", "matricula", "matrícula", "cuenta", "expediente", "id")
    palabras_nombre = ("nom", "nombre", "alumno", "estudiante", "apellidos")

    for idx_fila, fila in enumerate(filas[:10]):
        textos = [str(c or "").strip().lower() for c in fila]
        col_cod: Optional[int] = None
        col_nom: Optional[int] = None

        for idx_col, val in enumerate(textos):
            # Verificar código (excluyendo 'postal', 'barra')
            if any(k in val for k in palabras_codigo) and not any(k in val for k in ("postal", "barra")):
                col_cod = idx_col
            # Verificar nombre (excluyendo 'profesor', 'docente', 'código')
            elif any(k in val for k in palabras_nombre) and not any(k in val for k in ("profesor", "docente", "cod")):
                col_nom = idx_col

        if col_cod is not None and col_nom is not None and col_cod != col_nom:
            return col_cod, col_nom, idx_fila + 1

    # 2. Heurística basada en el contenido de las celdas
    max_cols = max(len(f) for f in filas) if filas else 0
    if max_cols < 2:
        return 0, 0, 0

    score_cod = [0] * max_cols
    score_nom = [0] * max_cols

    for fila in filas:
        for idx_col, celda in enumerate(fila):
            val = normalizar_codigo(celda)
            if not val:
                continue

            # Patrón de código de estudiante (7 a 11 dígitos, ej. 223992884)
            if re.match(r"^\d{7,11}$", val):
                score_cod[idx_col] += 5
            elif re.match(r"^[A-Za-z0-9]{6,12}$", val) and any(c.isdigit() for c in val):
                score_cod[idx_col] += 2

            # Patrón de nombre de alumno (texto con letras, espacios, sin dígitos)
            letras = re.findall(r"[A-Za-zÁÉÍÓÚáéíóúÑñ]", val)
            if len(letras) >= 5 and " " in val and not re.search(r"\d", val):
                score_nom[idx_col] += 5
            elif len(letras) >= 4 and not re.search(r"\d", val) and len(val) > 4:
                # Si no tiene espacios pero tiene letras (ej. nombres cortos o apellidos)
                score_nom[idx_col] += 1

    # Elegir la columna con mayor puntuación de código
    best_cod = max(range(max_cols), key=lambda i: score_cod[i])
    # Elegir la columna con mayor puntuación de nombre (distinta de best_cod)
    cols_resto = [i for i in range(max_cols) if i != best_cod]
    best_nom = max(cols_resto, key=lambda i: score_nom[i], default=1 if best_cod == 0 else 0)

    # Identificar la fila donde empiezan los datos reales
    fila_inicio = 0
    for idx, f in enumerate(filas):
        val_cod = normalizar_codigo(f[best_cod] if len(f) > best_cod else None)
        val_nom = str(f[best_nom] if len(f) > best_nom else "").strip()
        # Si la celda de código tiene dígitos o la de nombre tiene letras, aquí empieza
        if (re.match(r"^\d{6,11}$", val_cod) or re.search(r"[A-Za-z]", val_nom)) and not any(
            enc in val_cod.lower() or enc in val_nom.lower()
            for enc in ("código", "codigo", "nombre", "materia", "profesor", "universidad")
        ):
            fila_inicio = idx
            break

    return best_cod, best_nom, fila_inicio


def procesar_archivo_alumnos(contenido: bytes, filename: str) -> list[tuple[str, str]]:
    """
    Procesa un archivo .xlsx, .xlsm o .csv y devuelve una lista de tuplas:
    [(codigo_alumno, nombre_alumno), ...]
    Acepta:
      - Formato oficial UdeG / SIIAU: [Consecutivo, Código, Nombre, Carrera]
      - Formatos de 2 columnas: [Código, Nombre] o [Nombre, Código]
      - Formato de 1 columna con texto pegado: "01 223992884 ANGEL ANGEL ERIC EDUARDO"
    """
    nombre_min = filename.lower().strip()
    filas_crudas: list[list[Any]] = []

    if nombre_min.endswith((".xlsx", ".xlsm")):
        wb = openpyxl.load_workbook(filename=io.BytesIO(contenido), data_only=True)
        ws = wb.active
        for row in ws.iter_rows(values_only=True):
            fila = [c for c in row]
            if any(c is not None and str(c).strip() != "" for c in fila):
                filas_crudas.append(fila)

    elif nombre_min.endswith(".csv"):
        texto = None
        for encoding in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
            try:
                texto = contenido.decode(encoding)
                break
            except UnicodeDecodeError:
                continue

        if texto is None:
            raise ValueError("No se pudo decodificar el archivo CSV. Asegúrate de que esté en UTF-8 o ANSI.")

        lineas = [l for l in texto.splitlines() if l.strip()]
        if not lineas:
            return []

        muestra = "\n".join(lineas[:5])
        delimitador = ","
        try:
            dialect = csv.Sniffer().sniff(muestra, delimiters=[",", ";", "\t", "|"])
            delimitador = dialect.delimiter
        except Exception:
            if muestra.count(";") > muestra.count(","):
                delimitador = ";"
            elif muestra.count("\t") > muestra.count(","):
                delimitador = "\t"

        reader = csv.reader(io.StringIO(texto), delimiter=delimitador)
        for fila in reader:
            if any(c.strip() != "" for c in fila):
                filas_crudas.append(fila)

    else:
        raise ValueError("Formato no soportado. Debe ser un archivo Excel (.xlsx, .xlsm) o CSV (.csv).")

    if not filas_crudas:
        return []

    # Detectar columnas de Código y Nombre
    col_cod, col_nom, fila_inicio = detectar_columnas_alumnos(filas_crudas)

    alumnos: list[tuple[str, str]] = []
    codigos_vistos: set[str] = set()

    for fila in filas_crudas[fila_inicio:]:
        val_cod = normalizar_codigo(fila[col_cod] if len(fila) > col_cod else "")
        val_nom = str(fila[col_nom] if len(fila) > col_nom else "").strip()

        # ── CASO A: Fila de una sola celda o texto completo copiado de PDF ──
        # Ej: "01 223992884 ANGEL ANGEL ERIC EDUARDO ICOM"
        texto_fila_completa = " ".join(str(c or "").strip() for c in fila if c is not None)
        match_linea = RE_LINEA_UNICA.match(texto_fila_completa)
        if match_linea and (col_cod == col_nom or not val_cod or not val_nom or re.match(r"^\d{1,3}$", val_cod)):
            val_cod = match_linea.group(1).strip()
            val_nom = match_linea.group(2).strip()

        # ── CASO B: Protección de seguridad si las columnas quedaron corridas o invertidas ──
        # Si 'val_cod' es un consecutivo de lista (ej: "1", "01") y 'val_nom' es el código universitario (ej: "223992884")
        if re.match(r"^\d{1,3}$", val_cod) and re.match(r"^\d{7,11}$", val_nom):
            codigo_real = val_nom
            # Buscar en el resto de celdas de la fila la que contenga el nombre real
            nombre_real = ""
            for idx_c, celda in enumerate(fila):
                val_c = str(celda or "").strip()
                if idx_c not in (col_cod, col_nom) and any(c.isalpha() for c in val_c) and len(val_c) >= 5:
                    nombre_real = val_c
                    break
            if nombre_real:
                val_cod = codigo_real
                val_nom = nombre_real

        # Si 'val_nom' parece código (7-11 dígitos) y 'val_cod' parece nombre (tiene letras y espacios)
        elif re.match(r"^\d{7,11}$", val_nom) and any(c.isalpha() for c in val_cod):
            val_cod, val_nom = val_nom, val_cod

        # Filtrar encabezados residuales
        if any(h in val_cod.lower() for h in ("cod", "código", "codigo", "nrc", "clave")):
            continue
        if any(h in val_nom.lower() for h in ("nombre", "alumno", "estudiante", "materia", "profesor")):
            continue

        # Limpiar caracteres sobrantes en el nombre
        val_nom = re.sub(r"\s+", " ", val_nom).strip()

        if val_cod and val_nom and val_cod not in codigos_vistos:
            codigos_vistos.add(val_cod)
            alumnos.append((val_cod, val_nom))

    return alumnos
