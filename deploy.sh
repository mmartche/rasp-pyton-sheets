#!/bin/bash
set -e  # para o script se algo falhar

# Caminho do projeto
PROJECT_DIR="/home/martche/Projects/rasp-pyton-sheets"
VENV_DIR="$PROJECT_DIR/venv"

echo "➡️  Entrando na pasta do projeto..."
cd "$PROJECT_DIR"

echo "➡️  Atualizando código..."
git pull origin main

echo "➡️  Ativando ambiente virtual..."
source "$VENV_DIR/bin/activate"

echo "➡️  Instalando dependências..."
pip install -r requirements.txt

echo "➡️  Reiniciando serviço systemd..."
sudo systemctl restart telegram-bot

echo "✅ Deploy finalizado com sucesso!"
