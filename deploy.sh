#!/bin/bash
set -e

SERVER="ubuntu@54.95.105.90"
APP_NAME="webanalizar"
SERVER_DIR="/opt/apps/webanalizar"
SERVICE_NAME="webanalizar"

echo "==> Archiving..."
tar czf /tmp/${APP_NAME}-build.tar.gz \
  --exclude='__pycache__' \
  --exclude='data/technologies' \
  --exclude='data/categories.json' \
  --exclude='*.csv' \
  --exclude='.git' \
  --exclude='.claude' \
  --exclude='infra' \
  app/ static/ requirements.txt run.py

echo "==> Uploading..."
scp /tmp/${APP_NAME}-build.tar.gz ${SERVER}:/tmp/

echo "==> Deploying..."
ssh ${SERVER} "sudo -u deploy bash -c '
  cd ${SERVER_DIR} &&
  tar xzf /tmp/${APP_NAME}-build.tar.gz &&
  ${SERVER_DIR}/venv/bin/pip install -r requirements.txt -q
' && sudo systemctl restart ${SERVICE_NAME}"

echo "==> Verifying..."
ssh ${SERVER} "systemctl is-active ${SERVICE_NAME}"

rm -f /tmp/${APP_NAME}-build.tar.gz
echo "==> Done"
