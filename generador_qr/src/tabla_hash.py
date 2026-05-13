import json
import os
import hashlib
import time
import threading
import logging
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

MODULE_DIR = Path(__file__).resolve().parent
DATA_DIR = MODULE_DIR / "data"
ARCHIVO_HASHES = DATA_DIR / "registro_csv.json"
CARPETA_ENTRADA = DATA_DIR / "input"

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

def inicializar_tabla_hash():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not ARCHIVO_HASHES.exists():
        logging.info("No se encontró un registro previo. Creando tabla hash vacía.")
        ARCHIVO_HASHES.write_text(json.dumps({}, ensure_ascii=False, indent=4), encoding='utf-8')
        return {}

    try:
        with ARCHIVO_HASHES.open('r', encoding='utf-8') as f:
            tabla_hash = json.load(f)
            logging.info("Tabla hash cargada con éxito desde el disco.")
            return tabla_hash
    except (json.JSONDecodeError, IOError) as e:
        logging.error(f"Error leyendo {ARCHIVO_HASHES}: {e}. Reemplazando por tabla vacía.")
        return {}

def guardar_tabla_hash(tabla):
    try:
        with ARCHIVO_HASHES.open('w', encoding='utf-8') as f:
            json.dump(tabla, f, indent=4, ensure_ascii=False)
        logging.info(f"Tabla hash guardada en {ARCHIVO_HASHES}.")
    except IOError as e:
        logging.error(f"No se pudo guardar la tabla en {ARCHIVO_HASHES}: {e}")

def calcular_hash_real(ruta_archivo):
    hasher = hashlib.sha256()
    try:
        with open(ruta_archivo, 'rb') as f:
            while chunk := f.read(8192):
                hasher.update(chunk)
        return hasher.hexdigest()
    except IOError as e:
        logging.error(f"No se pudo leer el archivo {ruta_archivo}: {e}")
        return None

def procesar_archivo(ruta_completa, tabla_hash=None, guardar=True):
    if tabla_hash is None:
        tabla_hash = inicializar_tabla_hash()

    hash_archivo = calcular_hash_real(ruta_completa)
    if not hash_archivo:
        return False

    archivo = os.path.basename(ruta_completa)
    if hash_archivo in tabla_hash:
        nombre_original = tabla_hash[hash_archivo]
        logging.info(f"Ignorado: '{archivo}' ya fue procesado antes (registrado como '{nombre_original}').")
        return False

    logging.info(f"Archivo nuevo detectado: '{archivo}'. Procesando...")
    # Integración con generación de QR
    try:
        from generadorQr import procesar_csv_y_generar_qrs
        qrs_generados = procesar_csv_y_generar_qrs(ruta_completa)
        logging.info(f"Generación de QR completada: {qrs_generados} QR nuevos.")
    except Exception as e:
        logging.warning(f"No se pudo generar QR para '{archivo}': {e}. Continuando con registro...")

    tabla_hash[hash_archivo] = archivo
    if guardar:
        guardar_tabla_hash(tabla_hash)
    return True

def escanear_carpeta_once():
    CARPETA_ENTRADA.mkdir(parents=True, exist_ok=True)
    tabla_hash = inicializar_tabla_hash()
    archivos = [p for p in CARPETA_ENTRADA.iterdir() if p.suffix.lower() == '.csv' and p.is_file()]
    if not archivos:
        logging.info("No se encontraron archivos .csv para procesar.")
        return

    cambios = False
    for p in archivos:
        if procesar_archivo(str(p), tabla_hash=tabla_hash, guardar=False):
            cambios = True

    if cambios:
        guardar_tabla_hash(tabla_hash)
    else:
        logging.info("El escaneo terminó. No se encontraron archivos nuevos.")

class _PollingWatcher(threading.Thread):
    def __init__(self, interval=3):
        super().__init__(daemon=True)
        self.interval = interval
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def run(self):
        logging.info(f"Iniciando polling en {CARPETA_ENTRADA} cada {self.interval}s")
        while not self._stop.is_set():
            try:
                escanear_carpeta_once()
            except Exception as e:
                logging.error(f"Error durante polling: {e}")
            time.sleep(self.interval)

def start_watcher(blocking=False, use_watchdog=True):
    """Inicia vigilancia en tiempo real. Si `use_watchdog` es True intenta usar watchdog, si falla usa polling."""
    try:
        if use_watchdog:
            class CsvHandler(FileSystemEventHandler):
                def on_created(self, event):
                    if not event.is_directory and event.src_path.lower().endswith('.csv'):
                        logging.info(f"Evento: creado {event.src_path}")
                        try:
                            procesar_archivo(event.src_path)
                        except Exception as e:
                            logging.error(f"Error procesando archivo nuevo: {e}")

                def on_moved(self, event):
                    # si un archivo se mueve dentro de la carpeta
                    if not event.is_directory and event.dest_path.lower().endswith('.csv'):
                        logging.info(f"Evento: movido a {event.dest_path}")
                        try:
                            procesar_archivo(event.dest_path)
                        except Exception as e:
                            logging.error(f"Error procesando archivo movido: {e}")

            CARPETA_ENTRADA.mkdir(parents=True, exist_ok=True)
            observer = Observer()
            handler = CsvHandler()
            observer.schedule(handler, str(CARPETA_ENTRADA), recursive=False)
            observer.start()
            logging.info("Watcher activo (watchdog).")
            if blocking:
                try:
                    while True:
                        time.sleep(1)
                except KeyboardInterrupt:
                    observer.stop()
                observer.join()
            else:
                return observer

    except Exception as e:
        logging.warning(f"watchdog no disponible o falló ({e}); usando fallback por polling.")

    # Fallback: polling en hilo daemon
    poller = _PollingWatcher()
    poller.start()
    if blocking:
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            poller.stop()
    else:
        return poller

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Escanea y vigila carpeta de CSV para generar un registro por hash.')
    parser.add_argument('--watch', action='store_true', help='Iniciar vigilancia en tiempo real (no bloqueante por defecto).')
    parser.add_argument('--block', action='store_true', help='Si se usa --watch, bloquear el proceso (útil para pruebas).')
    args = parser.parse_args()

    if args.watch:
        logging.info('Iniciando modo vigilancia...')
        start_watcher(blocking=args.block)
    else:
        logging.info('Ejecutando escaneo único...')
        escanear_carpeta_once()
