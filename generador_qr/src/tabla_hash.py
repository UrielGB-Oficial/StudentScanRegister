import json
import os
import hashlib

# Ruta de guardado de la tabla hash
ARCHIVO_HASHES = "/data/registro_csv.json"
CARPETA_ENTRADA = "/data/input"

def inicializar_tabla_hash():
    if os.path.exists(ARCHIVO_HASHES):
        with open(ARCHIVO_HASHES, 'r', encoding='utf-8') as f:
            tabla_hash = json.load(f)
            print("[INFO] Tabla hash cargada con éxito desde el disco.")
            return tabla_hash
    else:
        print("[INFO] No se encontró un registro previo. Creé la tabla hash.")
        return {}

def guardar_tabla_hash(tabla):
    with open(ARCHIVO_HASHES, 'w', encoding='utf-8') as f:
        json.dump(tabla, f, indent=4, ensure_ascii=False)
    print("[OK] Tabla hash guardada en el disco.")

def calcular_hash_real(ruta_archivo):
    hasher = hashlib.sha256()

    try:
        with open(ruta_archivo, 'rb') as f:
            while chunk := f.read(8192):
                hasher.update(chunk)
        return hasher.hexdigest()
    except IOError as e:
        print(f"[ERROR] No se pudo leer el archivo {ruta_archivo}: {e}")
        return None

def procesar_carpeta_csv():
    os.makedirs(CARPETA_ENTRADA, exist_ok=True)

    # inicializar la tabla hash
    tabla_hash = inicializar_tabla_hash()
    hubo_cambios = False

    print(f"\nEscaneando archivos en '{CARPETA_ENTRADA}'...")
    archivos = [f for f in os.listdir(CARPETA_ENTRADA) if f.endswith('.csv')]

    if not archivos:
        print("No se encontraron archivos .csv para procesar.")
        return

    for archivo in archivos:
        ruta_completa = os.path.join(CARPETA_ENTRADA, archivo)

        # Calcular el hash real del archivo analizado
        hash_archivo = calcular_hash_real(ruta_completa)
        if not hash_archivo:
            continue

        # Buscar el has en la tabla (Búsqueda instantánea 0(1))
        if hash_archivo in tabla_hash:
            # El nombre ya existe en el registro histórico
            nombre_original = tabla_hash[hash_archivo]
            print(f"[-] Ignorado: '{archivo}' ya fue procesado antes (registrado como '{nombre_original}').")
        else:
            print(f"[+] Archivo nuevo detectado: '{archivo}'.")
            print()

            # TODO: Aquí irá la lógica de generación de Qr.
            print(f"    Procesando contenido de {archivo}...")

            # ---------------------------------------------------------------

            # Insertar el nuevo elemento en la tabla hash
            tabla_hash[hash_archivo] = archivo
            hubo_cambios = True

    if hubo_cambios:
        print()
        guardar_tabla_hash(tabla_hash)
    else:
        print("\n[INFO] El escaneo terminó. No se encontraron archivos nuevos.")
