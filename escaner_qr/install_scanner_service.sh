#!/bin/bash
# install_scanner_service.sh
# Instala la unidad systemd y el archivo de entorno (requiere sudo).

set -e

HERE=$(cd "$(dirname "$0")" && pwd)
UNIT_SRC="$HERE/ssr-scanner.service"
ENV_SRC="$HERE/ssr-scanner.env"

if [ ! -f "$UNIT_SRC" ] || [ ! -f "$ENV_SRC" ]; then
  echo "Faltan archivos en $HERE" >&2
  exit 1
fi

sudo cp "$UNIT_SRC" /etc/systemd/system/ssr-scanner@.service
sudo cp "$ENV_SRC" /etc/default/ssr-scanner.env
sudo chown root:root /etc/systemd/system/ssr-scanner@.service
sudo chmod 644 /etc/systemd/system/ssr-scanner@.service
sudo chown root:root /etc/default/ssr-scanner.env
sudo chmod 600 /etc/default/ssr-scanner.env

echo "Archivos copiados. Recuerda editar /etc/default/ssr-scanner.env con las rutas correctas y el usuario."
echo "Habilita el servicio (reemplaza <user> por tu usuario):"
echo "  sudo systemctl daemon-reload"
echo "  sudo systemctl enable --now ssr-scanner@<user>.service"
