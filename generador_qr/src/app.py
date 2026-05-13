import json
import logging
from pathlib import Path
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
from generadorQr import procesar as procesar_csv, inicializar_qr_registro
from tabla_hash import escanear_carpeta_once, inicializar_tabla_hash

# Configuración
MODULE_DIR = Path(__file__).resolve().parent
DATA_DIR = MODULE_DIR / "data"
OUTPUT_DIR = DATA_DIR / "output" / "qr_images"
QR_REGISTRO = DATA_DIR / "qr_registro.json"
CARPETA_ENTRADA = DATA_DIR / "input"

app = Flask(__name__)
CORS(app)

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


def cargar_qr_registro():
    """Carga el registro de QR desde JSON."""
    if QR_REGISTRO.exists():
        try:
            with QR_REGISTRO.open('r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}


@app.route('/health', methods=['GET'])
def health_check():
    """Verifica que la API está funcionando."""
    return jsonify({"status": "ok", "mensaje": "API de QR funcionando"})


@app.route('/api/alumnos', methods=['GET'])
def obtener_alumnos():
    """Retorna lista de todos los alumnos con sus QR."""
    try:
        registro = cargar_qr_registro()
        alumnos = []
        
        for hash_contenido, ruta_qr in registro.items():
            nombre_archivo = Path(ruta_qr).stem
            alumnos.append({
                "hash": hash_contenido,
                "nombre": nombre_archivo,
                "qr_url": f"/api/qr/imagen/{hash_contenido}"
            })
        
        return jsonify({"total": len(alumnos), "alumnos": alumnos})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/qr/imagen/<hash_contenido>', methods=['GET'])
def descargar_qr(hash_contenido):
    """Descarga la imagen del QR."""
    try:
        registro = cargar_qr_registro()
        
        if hash_contenido not in registro:
            return jsonify({"error": "QR no encontrado"}), 404
        
        ruta_qr = Path(registro[hash_contenido])
        
        if not ruta_qr.exists():
            return jsonify({"error": "Archivo no existe"}), 404
        
        return send_file(str(ruta_qr), mimetype='image/png')
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/qr/nombre/<nombre>', methods=['GET'])
def obtener_qr_por_nombre(nombre):
    """Busca QR por nombre de alumno."""
    try:
        registro = cargar_qr_registro()
        resultados = []
        
        nombre_lower = nombre.lower()
        for hash_contenido, ruta_qr in registro.items():
            nombre_archivo = Path(ruta_qr).stem.lower()
            if nombre_lower in nombre_archivo:
                resultados.append({
                    "hash": hash_contenido,
                    "nombre": Path(ruta_qr).stem,
                    "imagen_url": f"/api/qr/imagen/{hash_contenido}"
                })
        
        return jsonify({"total": len(resultados), "resultados": resultados})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/procesar', methods=['POST'])
def procesar_csv_upload():
    """Procesa un archivo CSV cargado por la web."""
    try:
        if 'archivo' not in request.files:
            return jsonify({"error": "No se proporcionó archivo"}), 400
        
        archivo = request.files['archivo']
        
        if not archivo.filename.endswith('.csv'):
            return jsonify({"error": "El archivo debe ser CSV"}), 400
        
        ruta_temp = CARPETA_ENTRADA / archivo.filename
        CARPETA_ENTRADA.mkdir(parents=True, exist_ok=True)
        archivo.save(str(ruta_temp))
        
        procesar_csv(str(ruta_temp))
        escanear_carpeta_once()
        
        return jsonify({"mensaje": "CSV procesado exitosamente"}), 201
    
    except Exception as e:
        logger.error(f"Error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/estadisticas', methods=['GET'])
def obtener_estadisticas():
    """Retorna estadísticas del sistema."""
    try:
        tabla_csv = inicializar_tabla_hash()
        registro_qr = cargar_qr_registro()
        
        return jsonify({
            "archivos_csv": len(tabla_csv),
            "qr_total": len(registro_qr)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    logger.info("Iniciando API en http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)
