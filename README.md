# StudentScanRegister (SSR)

StudentScanRegister (SSR) es una aplicación web para seguimiento de asistencia estudiantil mediante escaneo de códigos QR generados automáticamente a partir de registros CSV. Construida con **Python**, **Flask**, y **JavaScript**, permite generación automática de QR, búsqueda rápida mediante tablas hash, y vigilancia en tiempo real de archivos nuevos.

## Características

✅ **Generación automática de QR** — Crea códigos QR con datos de alumnos (nombre, email, CRN, ID)  
✅ **Búsqueda O(1)** — Usa tablas hash SHA256 para evitar duplicados y búsquedas rápidas  
✅ **Vigilancia en tiempo real** — Detecta CSVs nuevos automáticamente (watchdog + polling)  
✅ **API REST** — Comunicación fácil con aplicaciones web/móviles  
✅ **Sin duplicados** — El sistema nunca regenera un QR si ya existe  
✅ **Multiarchivo** — Procesa múltiples CSVs manteniendo registro centralizado  

---

## Estructura del Proyecto

```
generador_qr/
├── src/
│   ├── tabla_hash.py          # Vigilancia y registro de archivos CSV
│   ├── generadorQr.py         # Generación de QR
│   ├── app.py                 # API REST con Flask
│   ├── data/
│   │   ├── input/             # CSVs a procesar (gitignored)
│   │   ├── output/
│   │   │   └── qr_images/     # Imágenes QR generadas (gitignored)
│   │   ├── registro_csv.json  # Tabla hash de CSVs (gitignored)
│   │   └── qr_registro.json   # Tabla hash de QRs (gitignored)
│   └── verificar_csv.py       # Validación de CSVs (opcional)
├── requerimientos.txt         # Dependencias Python
└── .venv/                     # Entorno virtual
```

---

## Instalación

### 1. Clonar el repositorio

```bash
git clone https://github.com/tuusuario/StudentScanRegister.git
cd StudentScanRegister
```

### 2. Crear entorno virtual (si no existe)

```bash
python3 -m venv generador_qr/.venv
source generador_qr/.venv/bin/activate  # En Windows: generador_qr\.venv\Scripts\activate
```

### 3. Instalar dependencias

```bash
pip install -r generador_qr/requerimientos.txt
```

Las dependencias incluyen:
- **pillow** — Manejo de imágenes
- **qrcode** — Generación de QR
- **watchdog** — Vigilancia de sistema de archivos
- **flask** — Servidor API REST
- **flask-cors** — Soporte CORS para solicitudes web

---

## Uso

### Opción 1: Escaneo Único (Ejecución Manual)

Procesa todos los CSVs en `generador_qr/src/data/input/` una sola vez:

```bash
cd generador_qr
python src/tabla_hash.py
```

**Salida esperada:**
```
[INFO] Ejecutando escaneo único...
[INFO] Tabla hash cargada con éxito desde el disco.
[INFO] Archivo nuevo detectado: 'CRN207735.csv'. Procesando...
[INFO] Se parseron 21 alumnos del CSV.
[INFO] QR generado: ANGEL_ANGEL_ERIC_EDUARDO_223992884.png
...
[INFO] Se generaron 21 QR nuevos.
```

### Opción 2: Vigilancia en Tiempo Real (Recomendado para Producción)

Monitorea `data/input/` continuamente. Cuando agregas un CSV, lo procesa automáticamente:

**Modo bloqueante (útil para pruebas):**
```bash
cd generador_qr
python src/tabla_hash.py --watch --block
```

**Modo no-bloqueante (correr en segundo plano):**
```bash
cd generador_qr
nohup python src/tabla_hash.py --watch > tabla_hash.log 2>&1 &
```

**Con systemd (producción):**
Crear `/etc/systemd/system/ssr-watcher.service`:
```ini
[Unit]
Description=StudentScanRegister QR Watcher
After=network.target

[Service]
Type=simple
User=tu_usuario
WorkingDirectory=/ruta/a/StudentScanRegister/generador_qr
ExecStart=/ruta/a/StudentScanRegister/generador_qr/.venv/bin/python src/tabla_hash.py --watch
Restart=always

[Install]
WantedBy=multi-user.target
```

Luego:
```bash
sudo systemctl daemon-reload
sudo systemctl start ssr-watcher
sudo systemctl enable ssr-watcher
```

### Opción 3: API REST (Para Aplicaciones Web)

Inicia el servidor Flask en puerto 5000:

```bash
cd generador_qr/src
python app.py
```

**Salida esperada:**
```
[INFO] Iniciando API en http://localhost:5000
 * Running on http://0.0.0.0:5000
```

---

## API REST Endpoints

### 1. Verificar Estado
```http
GET /health
```
**Response:**
```json
{"status": "ok", "mensaje": "API de QR funcionando"}
```

### 2. Obtener Lista de Alumnos
```http
GET /api/alumnos
```
**Response:**
```json
{
  "total": 21,
  "alumnos": [
    {
      "hash": "f3b3c9ad2aed...",
      "nombre": "ANGEL_ANGEL_ERIC_EDUARDO_223992884",
      "qr_url": "/api/qr/imagen/f3b3c9ad2aed..."
    }
  ]
}
```

### 3. Descargar Imagen del QR
```http
GET /api/qr/imagen/{hash}
```
Retorna la imagen PNG del QR.

**Ejemplo:**
```http
GET /api/qr/imagen/f3b3c9ad2aed0f23da563cce2aa8e9bccac5b5533b752cdb3fd75389371d68b8
```

### 4. Buscar QR por Nombre
```http
GET /api/qr/nombre/{nombre}
```
**Ejemplo:**
```http
GET /api/qr/nombre/ANGEL
```

**Response:**
```json
{
  "total": 1,
  "resultados": [
    {
      "hash": "f3b3c9ad2aed...",
      "nombre": "ANGEL_ANGEL_ERIC_EDUARDO_223992884",
      "imagen_url": "/api/qr/imagen/f3b3c9ad2aed..."
    }
  ]
}
```

### 5. Procesar CSV (Upload)
```http
POST /api/procesar
Content-Type: multipart/form-data

archivo: <archivo.csv>
```

**Response:**
```json
{
  "mensaje": "CSV procesado exitosamente",
  "archivo": "CRN207735.csv"
}
```

### 6. Obtener Estadísticas
```http
GET /api/estadisticas
```

**Response:**
```json
{
  "archivos_csv": 1,
  "qr_total": 21
}
```

---

## Integración en Otra Aplicación Web

### Ejemplo 1: HTML + JavaScript Vanilla

```html
<!DOCTYPE html>
<html>
<head>
    <title>Búsqueda de QR</title>
</head>
<body>
    <h1>Búsqueda de QR Estudiantil</h1>
    
    <input type="text" id="busqueda" placeholder="Buscar alumno...">
    <button onclick="buscarQR()">Buscar</button>
    
    <div id="resultados"></div>

    <script>
        const API_URL = 'http://localhost:5000';

        async function buscarQR() {
            const nombre = document.getElementById('busqueda').value;
            if (!nombre) return;

            try {
                const res = await fetch(`${API_URL}/api/qr/nombre/${nombre}`);
                const data = await res.json();
                
                let html = `<h3>Resultados: ${data.total}</h3>`;
                data.resultados.forEach(qr => {
                    html += `
                        <div>
                            <p><strong>${qr.nombre}</strong></p>
                            <img src="${API_URL}${qr.imagen_url}" width="200">
                            <a href="${API_URL}${qr.imagen_url}" download>Descargar</a>
                        </div>
                    `;
                });
                document.getElementById('resultados').innerHTML = html;
            } catch (e) {
                alert('Error: ' + e.message);
            }
        }

        // Cargar todos al abrir
        window.onload = async () => {
            const res = await fetch(`${API_URL}/api/alumnos`);
            const data = await res.json();
            console.log(`Total de alumnos: ${data.total}`);
        };
    </script>
</body>
</html>
```

### Ejemplo 2: React

```jsx
import { useState, useEffect } from 'react';

const API_URL = 'http://localhost:5000';

export default function QRBuscador() {
    const [alumnos, setAlumnos] = useState([]);
    const [busqueda, setBusqueda] = useState('');
    const [resultados, setResultados] = useState([]);

    useEffect(() => {
        fetch(`${API_URL}/api/alumnos`)
            .then(r => r.json())
            .then(data => setAlumnos(data.alumnos));
    }, []);

    const buscar = async (nombre) => {
        if (!nombre) {
            setResultados(alumnos);
            return;
        }
        
        const res = await fetch(`${API_URL}/api/qr/nombre/${nombre}`);
        const data = await res.json();
        setResultados(data.resultados);
    };

    return (
        <div>
            <h1>Búsqueda de QR</h1>
            <input
                type="text"
                placeholder="Buscar alumno..."
                onChange={(e) => {
                    setBusqueda(e.target.value);
                    buscar(e.target.value);
                }}
            />
            <div>
                {resultados.map(qr => (
                    <div key={qr.hash}>
                        <h3>{qr.nombre}</h3>
                        <img src={`${API_URL}${qr.imagen_url}`} width="200" />
                    </div>
                ))}
            </div>
        </div>
    );
}
```

### Ejemplo 3: Subir CSV desde la Web

```html
<form id="formulario-csv">
    <input type="file" id="archivo-csv" accept=".csv" required>
    <button type="submit">Procesar CSV</button>
</form>

<script>
    document.getElementById('formulario-csv').onsubmit = async (e) => {
        e.preventDefault();
        
        const formData = new FormData();
        formData.append('archivo', document.getElementById('archivo-csv').files[0]);
        
        const res = await fetch('http://localhost:5000/api/procesar', {
            method: 'POST',
            body: formData
        });
        
        const data = await res.json();
        alert(data.mensaje);
        location.reload();
    };
</script>
```

---

## Cómo Funciona el Sistema

### 1. **Tabla Hash de CSVs** (`registro_csv.json`)
```json
{
    "94619655d62f7c53bbe6eb5e869510cc5bc68335eb736810b6e6a856f0d032dd": "CRN207735.csv"
}
```
- **Key:** Hash SHA256 del contenido del archivo CSV
- **Value:** Nombre del archivo
- **Propósito:** Detectar si el CSV cambió (para regenerar QR si es necesario)

### 2. **Tabla Hash de QRs** (`qr_registro.json`)
```json
{
    "f3b3c9ad2aed0f23da563cce2aa8e9bccac5b5533b752cdb3fd75389371d68b8": "/path/to/ANGEL_ANGEL_ERIC_EDUARDO_223992884.png",
    "fee16026f24d9ae7858d88c77746b75b05c26025ac785bf78c043ee236e5500f": "/path/to/BARRON_TORRES_ANA_PAULA_216609749.png"
}
```
- **Key:** Hash SHA256 del contenido JSON del alumno
- **Value:** Ruta a la imagen PNG del QR
- **Propósito:** Búsqueda O(1) sin regenerar duplicados

---

## Escáner USB (Raspberry Pi) — Instalación y despliegue

Este proyecto incluye un componente para leer un lector USB que emula teclado y registrar asistencias en la Raspberry Pi usando SQLite y reintentos automáticos.

Archivos relevantes:
- `escaner_qr/src/escaner.py` — script que lee el lector (stdin), valida contra la API de QRs y guarda filas en `escaner_qr/data/scanner.db`.
- `escaner_qr/requerimientos.txt` — dependencias `pip` necesarias para el script (ej. `requests`).
- `escaner_qr/ssr-scanner.env` — ejemplo de variables de entorno para el servicio (editar antes de usar).
- `escaner_qr/ssr-scanner.service` — unidad `systemd` (instanciable: `ssr-scanner@<user>.service`).
- `escaner_qr/install_scanner_service.sh` — helper para copiar la unidad y el env a `/etc`.

Pasos rápidos (en la Pi)

1) Crear virtualenv e instalar dependencias:
```bash
cd /home/Cristhian/Dev/StudentScanRegister/escaner_qr
python3 -m venv .venv
source .venv/bin/activate
pip install -r requerimientos.txt
```

2) Editar variables de entorno de ejemplo (`escaner_qr/ssr-scanner.env`) y ajustarlas a tu entorno (rutas, usuario, APIs).

3) Instalar la unidad systemd (requiere sudo):
```bash
cd /home/Cristhian/Dev/StudentScanRegister/escaner_qr
chmod +x install_scanner_service.sh
sudo ./install_scanner_service.sh
# Edita /etc/default/ssr-scanner.env con valores correctos
sudo systemctl daemon-reload
sudo systemctl enable --now ssr-scanner@<user>.service
sudo journalctl -u ssr-scanner@<user>.service -f
```

4) Probar manualmente sin systemd (útil para debugging):
```bash
source .venv/bin/activate
python src/escaner.py
# Pon el foco en la terminal y escanea con el lector USB
```

Comportamiento y buenas prácticas
- El script guarda cada escaneo en `escaner_qr/data/scanner.db` (tabla `scans`) y marca si fue enviado (`sent`).
- Si el `ATTENDANCE_API` no está disponible, el script reintenta enviar filas pendientes periódicamente.
- Asegúrate de que el lector envíe un `Enter` tras cada escaneo (modo teclado HID por defecto).
- Revisa los logs via `journalctl` cuando el servicio esté activo.

Comandos útiles
- Ver últimas filas de la base de datos:
```bash
sqlite3 /home/Cristhian/Dev/StudentScanRegister/escaner_qr/data/scanner.db "SELECT id,date,qr_hash,nombre,sent FROM scans ORDER BY id DESC LIMIT 10;"
```
- Ver logs en tiempo real:
```bash
sudo journalctl -u ssr-scanner@<user>.service -f
```

Si quieres, puedo añadir copias de seguridad automáticas del `scanner.db` y rotación de logs.

### 3. **Contenido del QR**
Cada QR contiene un JSON con datos del alumno:
```json
{
    "nombre": "ANGEL ANGEL ERIC EDUARDO",
    "email": "eric.angel9288@alumnos.udg.mx",
    "crn": "CRN207735",
    "id": "223992884"
}
```

### 4. **Flujo de Vigilancia**
1. Sistema monitorea `data/input/` cada 3 segundos (watchdog o polling)
2. Detecta CSV nuevo
3. Parsea CSV y extrae datos de alumnos
4. Para cada alumno:
   - Genera contenido JSON
   - Calcula hash SHA256
   - **Si hash existe en `qr_registro.json`**: salta (evita duplicado)
   - **Si es nuevo**: genera imagen PNG y registra en tabla hash
5. Actualiza `registro_csv.json` para marcar CSV como procesado

---

## Estructura de CSV Requerida

El CSV debe contener estas columnas (adaptable en `generadorQr.py`):
- `Name` — Nombre completo del alumno
- `E-mail 1 - Value` — Email del alumno
- `Group Membership` o `Subject` — CRN (ej: CRN207735)
- `Notes` — ID estudiantil

**Ejemplo de CSV válido:**
```csv
Name,E-mail 1 - Value,Subject,Notes
"ANGEL ANGEL ERIC EDUARDO",eric.angel9288@alumnos.udg.mx,CRN207735,223992884
"BARRON TORRES ANA PAULA",ana.barron0974@alumnos.udg.mx,CRN207735,216609749
```

---

## Troubleshooting

### Error: "cannot import name 'procesar'" en tabla_hash.py
**Solución:** Asegúrate de que `generadorQr.py` esté en el mismo directorio (`src/`) y tiene la función `procesar(ruta_csv)`.

### Los QR no se generan
**Solución:** Verifica que:
1. El CSV está en `generador_qr/src/data/input/`
2. El CSV tiene el formato correcto
3. Los permisos de escritura existen en `generador_qr/src/data/output/`

### API no conecta desde el navegador
**Solución:** Asegúrate de que:
1. Flask está corriendo: `python src/app.py`
2. CORS está habilitado (ya está en `app.py`)
3. Usa `http://localhost:5000` (no `https`)

### Limpiar registros y regenerar todo
```bash
cd generador_qr/src/data
rm -f qr_registro.json registro_csv.json
echo '{}' > qr_registro.json
echo '{}' > registro_csv.json
cd ../../..
python generador_qr/src/tabla_hash.py
```

---

## Requisitos del Sistema

- **Python 3.8+**
- **Sistema operativo:** Linux, macOS, Windows
- **Espacio en disco:** Mínimo 100MB (depende de cantidad de CSVs)
- **RAM:** 256MB mínimo
- **Permisos:** Lectura/escritura en carpeta del proyecto

---

## Performance

| Métrica | Valor |
|---------|-------|
| Búsqueda por hash | O(1) |
| Generación de QR | ~100ms por alumno |
| Detección de duplicados | O(1) |
| Vigilancia en tiempo real | Latencia <500ms |
| Capacidad máxima de QR | Ilimitada (solo limitado por disco) |

---

## Licencia

MIT License - Ver LICENSE.md para más detalles

---

## Contacto y Soporte

Para reportar bugs o sugerir mejoras, abre un issue en el repositorio.

**Autor:** Cristhian  
**Email:** cristhian.ramirez9292@alumnos.udg.mx 
**GitHub:** https://github.com/tuusuario/StudentScanRegister
