"""
scanner/lector.py — Script del Lector de Código de Barras USB

Este script corre en segundo plano en la máquina (Raspberry Pi o VM Linux).
Captura los datos del lector de código de barras USB (dongle 2.4 GHz) y los
envía por HTTP al servidor FastAPI (POST /api/scan).

Compatibilidad dual:
  1. Linux (Producción en Raspberry/VM):
     Usa la librería `evdev` para leer directamente el dispositivo USB en /dev/input/.
     Toma posesión exclusiva (device.grab()) para que los dígitos no se escriban
     en la consola del sistema.
  2. Windows / Modo Pruebas (Desarrollo):
     Si no está en Linux o no existe `evdev`, entra en modo simulación por consola,
     permitiéndote escribir o escanear códigos directamente en la terminal.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request

# ─────────────────────────────────────────────────────────────
# Configuración
# ─────────────────────────────────────────────────────────────
API_URL = os.getenv("API_URL", "http://localhost:8000/api/scan")


def enviar_escaneo(codigo: str) -> dict:
    """
    Envía el código escaneado al servidor FastAPI mediante una petición HTTP POST.
    Retorna el diccionario con la respuesta JSON del servidor.
    """
    payload = json.dumps({"codigo": codigo.strip()}).encode("utf-8")
    req = urllib.request.Request(
        API_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            datos = json.loads(response.read().decode("utf-8"))
            return datos
    except urllib.error.URLError as e:
        return {
            "status": "error",
            "tipo": "red",
            "mensaje": f"No se pudo conectar con el servidor en {API_URL}: {e.reason}",
        }
    except Exception as e:
        return {
            "status": "error",
            "tipo": "desconocido",
            "mensaje": f"Error inesperado al contactar al servidor: {e}",
        }


def mostrar_resultado(respuesta: dict, codigo: str):
    """
    Imprime en consola el resultado con formato claro y legible.
    """
    status = respuesta.get("status", "error")
    tipo = respuesta.get("tipo", "desconocido")
    mensaje = respuesta.get("mensaje", "")
    hora_str = time.strftime("%H:%M:%S")

    print("─" * 60)
    print(f"[{hora_str}] Código recibido: {codigo}")

    if status == "ok":
        if tipo == "profesor":
            nombre = respuesta.get("nombre", "")
            print(f"  👨‍🏫 [PROFESOR LISTO] {nombre}")
            print(f"     {mensaje}")
        elif tipo == "alumno":
            nombre = respuesta.get("nombre", "")
            clase = respuesta.get("clase", "")
            print(f"  ✅ [ASISTENCIA REGISTRADA] {nombre} ({clase})")
            print(f"     {mensaje}")
    else:
        print(f"  ⚠️  [ATENCIÓN / ERROR] ({tipo})")
        print(f"     {mensaje}")

    print("─" * 60)


# ─────────────────────────────────────────────────────────────
# Modo Linux con evdev (Producción)
# ─────────────────────────────────────────────────────────────
def ejecutar_modo_evdev():
    import evdev
    from evdev import ecodes

    print("\n🔍 Buscando dispositivo lector USB en /dev/input...")
    dispositivos = [evdev.InputDevice(path) for path in evdev.list_devices()]

    if not dispositivos:
        print("❌ Error: No se detectaron dispositivos de entrada en /dev/input.")
        print("   Verifica que el dongle USB 2.4 GHz esté conectado.")
        sys.exit(1)

    # Intentamos encontrar el lector por palabras clave comunes en su nombre
    lector = None
    palabras_clave = ["barcode", "scanner", "reader", "wireless", "dongle", "keyboard"]

    for dev in dispositivos:
        nombre_lower = dev.name.lower()
        if any(p in nombre_lower for p in palabras_clave):
            lector = dev
            break

    # Si no hubo coincidencia con los nombres, usamos el primer dispositivo disponible
    if not lector:
        lector = dispositivos[0]

    print(f"✅ Conectado a: {lector.name} ({lector.path})")

    # Mapeo de códigos de teclas evdev a caracteres normales
    MAPA_TECLAS = {
        ecodes.KEY_0: "0", ecodes.KEY_1: "1", ecodes.KEY_2: "2",
        ecodes.KEY_3: "3", ecodes.KEY_4: "4", ecodes.KEY_5: "5",
        ecodes.KEY_6: "6", ecodes.KEY_7: "7", ecodes.KEY_8: "8",
        ecodes.KEY_9: "9",
        ecodes.KEY_KP0: "0", ecodes.KEY_KP1: "1", ecodes.KEY_KP2: "2",
        ecodes.KEY_KP3: "3", ecodes.KEY_KP4: "4", ecodes.KEY_KP5: "5",
        ecodes.KEY_KP6: "6", ecodes.KEY_KP7: "7", ecodes.KEY_KP8: "8",
        ecodes.KEY_KP9: "9",
        ecodes.KEY_A: "A", ecodes.KEY_B: "B", ecodes.KEY_C: "C",
        ecodes.KEY_D: "D", ecodes.KEY_E: "E", ecodes.KEY_F: "F",
        ecodes.KEY_G: "G", ecodes.KEY_H: "H", ecodes.KEY_I: "I",
        ecodes.KEY_J: "J", ecodes.KEY_K: "K", ecodes.KEY_L: "L",
        ecodes.KEY_M: "M", ecodes.KEY_N: "N", ecodes.KEY_O: "O",
        ecodes.KEY_P: "P", ecodes.KEY_Q: "Q", ecodes.KEY_R: "R",
        ecodes.KEY_S: "S", ecodes.KEY_T: "T", ecodes.KEY_U: "U",
        ecodes.KEY_V: "V", ecodes.KEY_W: "W", ecodes.KEY_X: "X",
        ecodes.KEY_Y: "Y", ecodes.KEY_Z: "Z",
    }

    try:
        # Tomamos posesión exclusiva del dispositivo para que los números
        # no se escriban en la consola/terminal del sistema operativo
        lector.grab()
        print("🎯 Lector listo y escuchando. Esperando escaneos...\n")

        buffer_codigo = []

        for evento in lector.read_loop():
            # Solo nos interesan los eventos de pulsación de tecla (value == 1 es presionado)
            if evento.type == ecodes.EV_KEY and evento.value == 1:
                # Si se presiona ENTER, el lector terminó de enviar el código completo
                if evento.code in (ecodes.KEY_ENTER, ecodes.KEY_KPENTER):
                    codigo_completo = "".join(buffer_codigo).strip()
                    buffer_codigo.clear()

                    if codigo_completo:
                        res = enviar_escaneo(codigo_completo)
                        mostrar_resultado(res, codigo_completo)

                # Si es una tecla reconocida, la acumulamos
                elif evento.code in MAPA_TECLAS:
                    buffer_codigo.append(MAPA_TECLAS[evento.code])

    except KeyboardInterrupt:
        print("\nDeteniendo lector...")
    finally:
        try:
            lector.ungrab()
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────
# Modo Simulación / Consola (Windows o Pruebas)
# ─────────────────────────────────────────────────────────────
def ejecutar_modo_simulacion():
    print("=" * 60)
    print("  MODO SIMULADOR DE ESCÁNER (Entorno sin evdev / Windows)")
    print(f"  Enviando peticiones a: {API_URL}")
    print("  Escribe un código y presiona ENTER (o escanea si tu lector")
    print("  funciona como teclado en esta ventana).")
    print("  Presiona Ctrl+C para salir.")
    print("=" * 60)

    try:
        while True:
            codigo = input("\n[Escanear código] > ").strip()
            if not codigo:
                continue

            res = enviar_escaneo(codigo)
            mostrar_resultado(res, codigo)

    except KeyboardInterrupt:
        print("\nSimulador detenido. ¡Hasta luego!")


# ─────────────────────────────────────────────────────────────
# Punto de entrada
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Verificamos si estamos en Linux y tenemos evdev disponible
    es_linux = sys.platform.startswith("linux")

    if es_linux:
        try:
            import evdev
            ejecutar_modo_evdev()
        except ImportError:
            print("⚠️  Advertencia: 'evdev' no está instalado en este entorno Linux.")
            print("   Instálalo con: pip install evdev")
            print("   Iniciando en modo simulación de consola temporalmente...\n")
            ejecutar_modo_simulacion()
    else:
        # En Windows o macOS
        ejecutar_modo_simulacion()
