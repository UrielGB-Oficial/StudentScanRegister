# 📡 Sistema de Registro de Asistencia por Código de Barras

Sistema monolítico ligero y autónomo desarrollado para la gestión y registro de asistencia en laboratorios/talleres de cómputo. Diseñado para operar sobre **Raspberry Pi 3 (Headless)** mediante lectores de código de barras USB que leen credenciales institucionales.

---

## 🌟 Características Principales

* **Apertura de Sesión Dinámica:** El profesor escanea su credencial para entrar en *Modo Espera*. La sesión de la clase correspondiente se crea automáticamente en cuanto el **primer alumno** de dicha clase escanea su credencial.
* **Captura Hardware vía `evdev`:** El lector USB se intercepta directamente como dispositivo de entrada sin requerir pantalla, foco en ventana ni interfaz gráfica.
* **Sesión Diaria Tolerante:** Las sesiones son válidas durante todo el día calendario, permitiendo el registro de alumnos con retardos sin cortar la sesión.
* **Alta Masiva de Alumnos:** Carga rápida de listas de alumnos mediante archivos Excel (`.xlsx`).
* **Exportación de Reportes:** Generación y descarga de listas de asistencia consolidadas en Excel.
* **UI Administrativa Oscura Modernizada:** Interfaz Web receptiva construida con CSS vanilla en estilo *glassmorphism*, optimizada para consumo mínimo de recursos.
* **Servicios de Resiliencia en Linux:** Preparado para correr como demonios del sistema (`systemd`) con reinicio automático tras fallos de energía.

---

## 🏗️ Arquitectura del Sistema

El proyecto opera bajo un modelo desacoplado local donde el script del lector e interfaces administrativas convergen en un backend centralizado con FastAPI.

┌────────────────────────┐      evdev       ┌────────────────────┐
│ Lector USB Credenciales│ ───────────────> │ scanner/lector.py  │
└────────────────────────┘                  └─────────┬──────────┘
│ HTTP POST
▼
┌────────────────────────┐   HTTP / HTML    ┌────────────────────┐
│ Panel Admin (Navegador)│ <──────────────> │   FastAPI Server   │
└────────────────────────┘                  │  (uvicorn:8000)    │
└─────────┬──────────┘
│
▼
┌────────────────────┐
│ SQLite Database    │
│ (data/registro.db) │
└────────────────────┘

StudentScanRegister/
├── app/
│   ├── main.py              # Punto de entrada de FastAPI y middleware
│   ├── database.py          # Configuración de SQLite y engine SQLModel
│   ├── models.py            # Modelos de datos (Profesor, Clase, Alumno, Sesion, Asistencia)
│   ├── routers/
│   │   ├── asistencias.py   # Endpoint /api/scan, lógica de negocio y exportación Excel
│   │   ├── clases.py        # CRUD de Clases y Profesores
│   │   └── listado.py       # Carga masiva de alumnos y consulta de asistencia
│   ├── static/
│   │   └── style.css        # Estilos CSS globales (Dark glassmorphism)
│   └── templates/           # Plantillas Jinja2 (base, clases, alumnos, asistencia, etc.)
├── scanner/
│   └── lector.py            # Script daemon para interceptar hardware USB vía evdev
├── systemd/
│   ├── registro.service     # Servicio systemd para el servidor FastAPI
│   └── lector.service       # Servicio systemd para el script del lector
├── data/                    # Almacenamiento persistente de la base de datos SQLite
├── requirements.txt         # Dependencias Python del proyecto
└── README.md

┌──────────────┐       ┌──────────────┐       ┌──────────────┐
│   Profesor   │ 1 ── N│    Clase     │ 1 ── N│    Alumno    │
├──────────────┤       ├──────────────┤       ├──────────────┤
│ id           │       │ id           │       │ id           │
│ codigo (UNIQ)│       │ nombre       │       │ codigo (UNIQ)│
│ nombre       │       │ profesor_id  │       │ nombre       │
└──────────────┘       └──────┬───────┘       │ clase_id     │
                              │               └──────┬───────┘
                              │ 1                    │ 1
                              │                      │
                              ▼ N                    ▼ N
                       ┌──────────────┐       ┌──────────────┐
                       │    Sesion    │ 1 ── N│  Asistencia  │
                       ├──────────────┤       ├──────────────┤
                       │ id           │       │ id           │
                       │ clase_id     │       │ sesion_id    │
                       │ fecha        │       │ alumno_id    │
                       └──────────────┘       │ hora         │
                                              └──────────────┘

[ Código Escaneado ]
                                       │
                             ¿El código pertenece a...?
                                       │
                 ┌─────────────────────┴─────────────────────┐
                 ▼                                           ▼
            [ PROFESOR ]                                 [ ALUMNO ]
                 │                                           │
    Setea "Profesor en Espera"             ¿Hay un "Profesor en Espera"?
    en memoria RAM del backend                               │
                 │                         ┌─────────────────┴─────────────────┐
                 ▼                         ▼                                   ▼
          Responde OK (200)             [ SÍ ]                              [ NO ]
                                           │                                   │
                           ¿El profesor enseña su clase?         ¿Existe una sesión creada hoy
                                           │                     para la clase de este alumno?
                                   ┌───────┴───────┐                           │
                                   ▼               ▼                   ┌───────┴───────┐
                                [ SÍ ]          [ NO ]                 ▼               ▼
                                   │               │                [ SÍ ]          [ NO ]
                            Crea Sesión Hoy    Error (400)             │               │
                           + Asistencia 1er    Clase no        Registra/Actualiza  Error (400)
                                Alumno         corresponde        Asistencia       Sin sesión

# Clonar el repositorio
git clone https://github.com/UrielGB-Oficial/StudentScanRegister.git
cd StudentScanRegister

# Crear entorno virtual
python3 -m venv venv
source venv/bin/activate

# Instalación de paquetes
pip install --upgrade pip
pip install -r requirements.txt

# Ejecutar en terminal
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Requiere permisos de superusuario para leer dispositivos /dev/input/
sudo ./venv/bin/python scanner/lector.py

# Services
[Unit]
Description=Servidor Backend de Registro de Asistencia (FastAPI)
After=network.target

[Service]
User=pi
WorkingDirectory=/opt/StudentScanRegister
ExecStart=/opt/StudentScanRegister/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target

# Lector
[Unit]
Description=Demonio Lector de Código de Barras USB
After=registro.service
Requires=registro.service

[Service]
User=root
WorkingDirectory=/opt/StudentScanRegister
ExecStart=/opt/StudentScanRegister/venv/bin/python scanner/lector.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target

# Reload services
sudo systemctl daemon-reload

# Enable auto-start services
sudo systemctl enable registro.service
sudo systemctl enable lector.service

# Start services
sudo systemctl start registro.service
sudo systemctl start lector.service

# Status
sudo systemctl status registro.service
sudo systemctl status lector.service

# Ver estado del servidor Web
sudo systemctl status registro.service

# Ver registros en tiempo real del lector de credenciales
sudo journalctl -u lector.service -f

# Para realizar la carga masiva de alumnos a una clase desde el panel administrativo, prepare un archivo .xlsx en la primera hoja con el siguiente formato exacto en los encabezados de la fila 

#   codigo   |   nombre          
219304859    | Juan Pérez López
219304860    | María Elena García

⚠️ Importante: La columna codigo debe ser tratada como formato Texto en Excel para prevenir que la pérdida de ceros a la izquierda afecte a números de control institucionales.

🔌 Referencia de la API HTTP
Método	Ruta	Descripción	Payload / Params
POST	/api/scan	Procesa código escaneado	{"codigo": "219304859"}
POST	/api/sesiones	Abre sesión manual para una clase	{"clase_id": 1}
GET	/api/sesiones/activa/{clase_id}	Consulta sesión del día	N/A
GET	/api/asistencias/{clase_id}/excel	Descarga reporte acumulado de asistencias	N/A
POST	/clases/{id}/alumnos/upload	Carga masiva de lista de alumnos	multipart/form-data
