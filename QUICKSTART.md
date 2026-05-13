# 🚀 Inicio Rápido - StudentScanRegister

## 1. Instalación (5 minutos)

```bash
# Clonar repo
git clone https://github.com/tuusuario/StudentScanRegister.git
cd StudentScanRegister

# Crear entorno virtual
python3 -m venv generador_qr/.venv
source generador_qr/.venv/bin/activate  # Windows: generador_qr\.venv\Scripts\activate

# Instalar dependencias
pip install -r generador_qr/requerimientos.txt
```

## 2. Procesar tu Primer CSV (3 minutos)

### Paso 1: Preparar CSV
Coloca tu archivo CSV en:
```
generador_qr/src/data/input/mi_archivo.csv
```

El CSV debe tener estas columnas:
- `Name` — Nombre del alumno
- `E-mail 1 - Value` — Email
- `Subject` o `Group Membership` — CRN
- `Notes` — ID estudiantil

### Paso 2: Procesar
```bash
cd generador_qr
python src/tabla_hash.py
```

**Resultado:**
- ✅ 21 QR generados en `src/data/output/qr_images/`
- ✅ `qr_registro.json` creado (tabla hash de QR)
- ✅ `registro_csv.json` creado (tabla hash de CSV)

## 3. Usar la API REST (1 minuto)

### Iniciar servidor
```bash
cd generador_qr/src
python app.py
```

### Probar en el navegador
```
http://localhost:5000/health
```

Deberías ver:
```json
{"status": "ok", "mensaje": "API de QR funcionando"}
```

## 4. Interfaz Web (Súper Fácil)

Abre en tu navegador:
```
file:///ruta/a/StudentScanRegister/generador_qr/src/ejemplo.html
```

O accede vía HTTP si tienes un servidor web.

---

## Comandos Esenciales

### Escaneo único
```bash
python generador_qr/src/tabla_hash.py
```

### Vigilancia en tiempo real
```bash
python generador_qr/src/tabla_hash.py --watch --block
```

### API REST
```bash
cd generador_qr/src && python app.py
```

### Limpiar y regenerar todo
```bash
cd generador_qr/src/data
rm -f qr_registro.json registro_csv.json
echo '{}' > qr_registro.json
echo '{}' > registro_csv.json
cd ../../.. && python generador_qr/src/tabla_hash.py
```

---

## Ejemplos Rápidos con curl

### Ver todos los alumnos
```bash
curl http://localhost:5000/api/alumnos
```

### Buscar por nombre
```bash
curl http://localhost:5000/api/qr/nombre/ANGEL
```

### Descargar QR
```bash
curl http://localhost:5000/api/qr/imagen/f3b3c9ad2aed0f23da563cce2aa8e9bccac5b5533b752cdb3fd75389371d68b8 -o qr.png
```

### Subir nuevo CSV
```bash
curl -F "archivo=@nuevo_archivo.csv" http://localhost:5000/api/procesar
```

---

## Estructura de Carpetas Después de Procesar

```
generador_qr/
├── src/
│   ├── tabla_hash.py              # Sistema de vigilancia
│   ├── generadorQr.py             # Generador de QR
│   ├── app.py                     # API REST (nuevo)
│   ├── ejemplo.html               # Interfaz web (nuevo)
│   └── data/
│       ├── input/
│       │   └── CRN207735.csv      # Tu archivo CSV
│       ├── output/
│       │   └── qr_images/         # 21 imágenes PNG
│       ├── registro_csv.json      # Hash del CSV
│       └── qr_registro.json       # Hash de QRs
└── requerimientos.txt
```

---

## FAQ Rápidas

**P: ¿Se regeneran los QR si cargo el mismo CSV?**  
R: No. El sistema detecta que ya fue procesado.

**P: ¿Cómo busco un alumno específico?**  
R: Usa `/api/qr/nombre/{nombre}` en la API o la interfaz web.

**P: ¿Dónde están los QR generados?**  
R: En `generador_qr/src/data/output/qr_images/`

**P: ¿Cómo hago que se procesen CSVs automáticamente?**  
R: Usa `python src/tabla_hash.py --watch` para vigilancia continua.

**P: ¿Puedo usar esto en producción?**  
R: Sí. Ver README.md para configurar con systemd.

---

## Próximos Pasos

1. Lee [README.md](README.md) para documentación completa
2. Integra la API en tu aplicación web (ver ejemplos en README)
3. Configura vigilancia automática si lo necesitas
4. Considera usar systemd para ejecutar en segundo plano (producción)

---

¡Listo! Ahora tienes un sistema de QR funcional. 🎉
