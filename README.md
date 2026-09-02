# Sistema de Registro de Asistencia — Plan de Implementación

Sistema completo para registrar asistencia en un taller de redes vía lectores de código de barras sobre credenciales, corriendo en una Raspberry Pi 3 headless.

## Decisiones de diseño confirmadas

- **Un profesor puede tener múltiples clases.** Al escanear su credencial el sistema entra en **modo espera**; el primer alumno que llegue determina qué clase se abre automáticamente.
- **El script `lector.py` se comunica con el servidor via HTTP interno** (llamadas a `localhost`), manteniendo toda la lógica en FastAPI.
- **Una sesión es válida durante todo el día calendario** en que fue creada (no hay límite estricto de 2 horas). Así los alumnos que lleguen tarde pueden registrarse sin problema. Dos clases distintas (ej. Redes 1 y Redes 3) el mismo día **no se interfieren** porque cada alumno pertenece a una sola clase y el sistema busca la sesión de *su* clase específica.
- **Formato del Excel de alumnos:** dos columnas — `codigo` (número de control de 9 dígitos) y `nombre` (nombre completo). El profesor lo sube una vez al inicio del semestre desde la interfaz de administrador.

---

## Flujo completo del sistema

```
[Lector USB] → evdev → lector.py → HTTP POST localhost → FastAPI → SQLite
                                                              ↑
[Navegador admin] ────────────────────────────── HTTP → FastAPI (Jinja2)
```

**Flujo del profesor:**
1. Profesor escanea → `POST /api/scan` con su código de 9 dígitos.
2. El servidor identifica que es un profesor → responde `{"tipo": "profesor"}` y guarda en memoria (o BD) que ese profesor está en **modo espera** (sin sesión aún abierta).
3. El sistema espera a que llegue el **primer alumno** para determinar la clase.

**Flujo del alumno (cuando hay profesor en espera):**
1. Alumno escanea → `POST /api/scan`.
2. El servidor identifica al alumno y sabe a qué clase pertenece.
3. **¿El profesor en espera imparte esa clase?**
   - ✅ Sí → Abre sesión para esa clase **y** registra al alumno en un solo paso.
   - ❌ No → Rechaza con error (alumno no corresponde al profesor activo).
4. Siguientes alumnos escanean → se registran en la sesión ya abierta.
5. Si ya registró asistencia → actualiza `hora` (no duplica).

**Flujo del alumno (cuando ya hay sesión abierta):**
1. Alumno escanea → el servidor registra asistencia directamente en la sesión activa de su clase.

> [!NOTE]
> El **"modo espera"** del profesor se guarda como una fila temporal en una tabla `EstadoEspera` (o en memoria con un dict en FastAPI). Se limpia automáticamente al final del día o cuando el sistema se reinicia.

---

## Proposed Changes

### 1 — Modelos (`app/models.py`)

#### [MODIFY] [models.py](file:///c:/Users/Uriel/Desktop/Proyectitos/StudentScanRegister/app/models.py)

Reemplazar con los 5 modelos SQLModel definitivos:

- **`Profesor`** — `id`, `codigo` (str 9 dígitos, único), `nombre`
- **`Clase`** — `id`, `nombre`, `profesor_id` (FK → Profesor)
- **`Alumno`** — `id`, `codigo` (str 9 dígitos, único), `nombre`, `clase_id` (FK → Clase)
- **`Sesion`** — `id`, `clase_id` (FK → Clase), `fecha` (datetime, default=now)
- **`Asistencia`** — `id`, `sesion_id` (FK → Sesion), `alumno_id` (FK → Alumno), `hora` (time, default=now)
  - Restricción UNIQUE en `(sesion_id, alumno_id)` para evitar duplicados a nivel de BD.

---

### 2 — Base de datos (`app/database.py`)

#### [MODIFY] [database.py](file:///c:/Users/Uriel/Desktop/Proyectitos/StudentScanRegister/app/database.py)

- Crea el `engine` con SQLite en `../data/registro.db`.
- Función `create_db_and_tables()` que llama a `SQLModel.metadata.create_all()`.
- Función `get_session()` como dependencia de FastAPI (generador con `with Session(engine)`).

---

### 3 — API endpoints (`app/routers/`)

#### [MODIFY] [asistencias.py](file:///c:/Users/Uriel/Desktop/Proyectitos/StudentScanRegister/app/routers/asistencias.py)

Endpoint principal del lector + gestión de asistencias:

| Método | Ruta | Descripción |
|--------|------|-------------|
| `POST` | `/api/scan` | Recibe `{"codigo": "123456789"}`. Identifica si es profesor o alumno y actúa en consecuencia. |
| `POST` | `/api/sesiones` | Abre una nueva sesión `{"clase_id": 1}`. |
| `GET` | `/api/sesiones/activa/{clase_id}` | Consulta si hay sesión activa para una clase. |
| `GET` | `/api/asistencias/{clase_id}/excel` | Genera y descarga el Excel de asistencia. |

**Lógica del `POST /api/scan`:**
```
código recibido
  ├─ es Profesor
  │     └─ guarda "profesor en espera" → {"tipo": "profesor", "nombre": "..."}
  │
  ├─ es Alumno
  │     ├─ ¿hay profesor en espera?
  │     │     ├─ Sí → ¿el profesor imparte la clase del alumno?
  │     │     │         ├─ Sí → abre sesión + registra alumno → {"tipo": "alumno", "sesion_abierta": true, "ok": true}
  │     │     │         └─ No → {"tipo": "alumno", "ok": false, "error": "clase_incorrecta"}
  │     │     └─ No → busca sesión activa del día para la clase del alumno
  │     │                 ├─ hay sesión → registra asistencia → {"tipo": "alumno", "ok": true}
  │     │                 └─ no hay    → {"tipo": "alumno", "ok": false, "error": "sin_sesion"}
  │
  └─ desconocido → {"tipo": "desconocido"}
```

> [!IMPORTANT]
> El estado "profesor en espera" se guarda en un diccionario en memoria dentro de FastAPI (un simple `dict` a nivel de módulo). Es suficiente porque la Pi no se reinicia durante una clase. Se limpia al final del día o al reiniciar el servidor.

**Tabla extra que se añade a los modelos:** `EstadoEspera` con `profesor_id` y `timestamp`. Alternativa más simple: un `dict` en memoria dentro del router (sin tocar la BD). Se usará esta última por simplicidad.

#### [MODIFY] [clases.py](file:///c:/Users/Uriel/Desktop/Proyectitos/StudentScanRegister/app/routers/clases.py)

CRUD completo de clases, profesores y alumnos para la interfaz de administrador:

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/clases` | Página principal — lista de clases |
| `POST` | `/clases` | Crear clase |
| `GET` | `/clases/{id}/editar` | Formulario de edición |
| `PUT/POST` | `/clases/{id}` | Actualizar clase |
| `DELETE/POST` | `/clases/{id}/eliminar` | Eliminar clase |
| `GET` | `/profesores` | Lista de profesores |
| `POST` | `/profesores` | Crear profesor |
| `DELETE/POST` | `/profesores/{id}/eliminar` | Eliminar profesor |


#### [MODIFY] [listado.py](file:///c:/Users/Uriel/Desktop/Proyectitos/StudentScanRegister/app/routers/listado.py)

Alta masiva de alumnos vía Excel y visualización de asistencia:

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/clases/{id}/alumnos` | Página de alumnos de una clase |
| `POST` | `/clases/{id}/alumnos/upload` | Sube Excel con columnas `codigo` y `nombre` (primera hoja, fila 1 = encabezados) |
| `POST` | `/clases/{id}/alumnos` | Alta manual de un alumno |
| `DELETE/POST` | `/alumnos/{id}/eliminar` | Eliminar alumno |
| `GET` | `/clases/{id}/asistencia` | Página de vista de asistencia (tabla HTML) |

---

### 4 — Servidor principal (`app/main.py`)

#### [MODIFY] [main.py](file:///c:/Users/Uriel/Desktop/Proyectitos/StudentScanRegister/app/main.py)

- Inicializa la app FastAPI con título y descripción.
- Monta `StaticFiles` en `/static`.
- Configura `Jinja2Templates` apuntando a `templates/`.
- Registra los 3 routers.
- En `startup`: llama a `create_db_and_tables()`.
- Ruta raíz `/` redirige a `/clases`.

---

### 5 — Interfaz de administrador (`app/templates/` + `app/static/`)

Diseño oscuro moderno con glassmorphism, usando CSS vanilla y JS mínimo. Sin frameworks de frontend.

#### [NEW] Archivos de plantillas

| Archivo | Contenido |
|---------|-----------|
| `base.html` | Layout base con nav, head, fuentes Google (Inter), CSS global |
| `clases.html` | Lista de clases + modal para crear/editar |
| `profesores.html` | Lista de profesores + formulario inline |
| `alumnos.html` | Lista de alumnos de una clase + botón de subir Excel |
| `asistencia.html` | Tabla de asistencia (alumnos × sesiones) con celda ✓/— |

#### [NEW] `app/static/style.css`

Tokens de diseño:
- Paleta oscura: `#0a0e1a` (fondo), `#111827` (cards), `#6366f1` (acento índigo)
- Glassmorphism en cards y modales
- Animaciones de entrada suaves (`fade-in`, `slide-up`)
- Tabla de asistencia con sticky headers

---

### 6 — Script del lector (`scanner/lector.py`)

#### [MODIFY] [lector.py](file:///c:/Users/Uriel/Desktop/Proyectitos/StudentScanRegister/scanner/lector.py)

- Usa `evdev` para leer el lector USB como dispositivo de entrada (no como teclado del sistema).
- Detecta el dispositivo automáticamente buscando un input device que contenga "barcode" o "scanner" en su nombre; con fallback a listado manual.
- Acumula caracteres hasta recibir `KEY_ENTER` (código completo).
- `POST http://localhost:8000/api/scan` con el código.
- **Sin menú de selección** — el script simplemente reenvía todos los códigos al servidor y muestra en consola la respuesta:
  - `[PROFESOR]  Juan Pérez — esperando primer alumno...`
  - `[SESIÓN ABIERTA]  Redes I — 09:15 AM`
  - `[ASISTENCIA]  María López ✓`
  - `[ERROR]  Alumno no corresponde al profesor activo`
  - `[ERROR]  No hay sesión activa para esta clase`
- Imprime mensajes claros en consola para cada evento.

> [!NOTE]
> `evdev` solo funciona en Linux. El script tiene un bloque `try/import` con mensaje claro si se corre en Windows (para desarrollo).

---

### 7 — Archivos de infraestructura

#### [NEW] `systemd/registro.service`

Unidad systemd para el servidor FastAPI (con `uvicorn`). Restart automático.

#### [NEW] `systemd/lector.service`

Unidad systemd para el script `lector.py`. Restart automático. Depende de `registro.service`.

#### [NEW] `README.md` (actualizar)

Instrucciones de instalación en la Pi, activación de los servicios systemd, y uso del sistema.

---

## Verification Plan

### Automated
- `python -c "from app.models import *; print('models OK')"` — verifica imports.
- `uvicorn app.main:app --reload` — verifica que el servidor arranca sin errores.
- Curl manual a `/api/scan`, `/api/sesiones`, y descarga del Excel.

### Manual
- Crear un profesor y clase desde la UI, subir Excel de alumnos, simular scans via curl, verificar tabla de asistencia y descarga de Excel.

---

## ✅ Todas las preguntas resueltas — listo para implementar

- **Duración de sesión:** Definida como "sesión diaria" (cualquier registro en la fecha actual cuenta como asistencia).
- **Formato Excel:** Columnas `codigo` (tipo texto/string para conservar ceros a la izquierda) y `nombre`.
S