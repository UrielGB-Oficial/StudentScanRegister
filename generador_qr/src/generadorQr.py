import csv
import json
import hashlib
import logging
from pathlib import Path
import qrcode

MODULE_DIR = Path(__file__).resolve().parent
DATA_DIR = MODULE_DIR / "data"
OUTPUT_DIR = DATA_DIR / "output" / "qr_images"
QR_REGISTRO = DATA_DIR / "qr_registro.json"

# Asegurar que el directorio de salida existas
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')


def inicializar_qr_registro():
    if not QR_REGISTRO.exists():
        logging.info("Creando registro de QR vacío.")
        QR_REGISTRO.write_text(json.dumps({}, ensure_ascii=False, indent=4), encoding='utf-8')
        return {}
    try:
        with QR_REGISTRO.open('r', encoding='utf-8-sig') as f:
            return json.load(f)
    except Exception:
        return {}


def guardar_qr_registro(registro):
    try:
        with QR_REGISTRO.open('w', encoding='utf-8') as f:
            json.dump(registro, f, indent=4, ensure_ascii=False)
    except Exception as e:
        logging.error(f"Error guardando registro: {e}")


def parsear_csv(ruta_csv):
    alumnos = []
    try:
        with open(ruta_csv, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            # Normalizar nombres de columnas (quitar espacios y caracteres raros)
            columnas = {name.strip(): name for name in reader.fieldnames} if reader.fieldnames else {}
            
            for row in reader:
                # Mapeo flexible de columnas para manejar cambios en encabezados
                nombre = row.get(columnas.get('Name', 'Name'), '').strip()
                email = row.get(columnas.get('Email1Value', 'Email1Value'), '').strip()
                # Si falló la anterior, probar con el nombre original o variaciones
                if not email:
                    email = row.get('E-mail 1 - Value', '').strip()
                
                crn = row.get(columnas.get('GroupMembership', 'GroupMembership'), '').strip()
                if not crn:
                    crn = row.get('Group Membership', '').strip()
                
                id_alumno = row.get(columnas.get('Notes', 'Notes'), '').strip()
                
                if nombre and (email or id_alumno):
                    alumnos.append({
                        'nombre': nombre,
                        'email': email,
                        'crn': crn,
                        'id': id_alumno
                    })
    except Exception as e:
        logging.error(f"Error leyendo CSV: {e}")
    
    logging.info(f"Se parseron {len(alumnos)} alumnos del CSV.")
    return alumnos


def generar_qr(alumno, registro_qr):
    contenido = json.dumps(alumno, ensure_ascii=False)
    hash_contenido = hashlib.sha256(contenido.encode('utf-8')).hexdigest()

    if hash_contenido in registro_qr:
        return None, None

    nombre_limpio = "".join([c for c in alumno['nombre'] if c.isalnum() or c in (' ', '_')]).replace(' ', '_')
    nombre_archivo = f"{nombre_limpio}_{alumno['id']}.png"
    ruta_qr = OUTPUT_DIR / nombre_archivo

    try:
        img = qrcode.make(contenido)
        img.save(str(ruta_qr))
        logging.info(f"QR generado: {nombre_archivo}")
        return hash_contenido, str(ruta_qr)
    except Exception as e:
        logging.error(f"Error generando QR: {e}")
        return None, None


def procesar(ruta_csv):
    alumnos = parsear_csv(ruta_csv)
    if not alumnos:
        logging.warning("No se encontraron alumnos.")
        return

    registro = inicializar_qr_registro()
    nuevos = 0
    for a in alumnos:
        h, r = generar_qr(a, registro)
        if h:
            registro[h] = r
            nuevos += 1
    
    if nuevos > 0:
        guardar_qr_registro(registro)
        logging.info(f"Se generaron {nuevos} QR nuevos.")

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        procesar(sys.argv[1])
