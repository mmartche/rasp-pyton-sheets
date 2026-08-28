import os
import json
from datetime import datetime
from flask import Flask, request, jsonify

from dotenv import load_dotenv
import gspread

load_dotenv()

# ------- Config -------
API_TOKEN = os.getenv("API_TOKEN")  # token secreto para autenticar o POST
DEFAULT_USER_ID = os.getenv("DEFAULT_USER_ID")  # Telegram user id p/ salvar por padrão
USERS_FILE = os.getenv("USERS_FILE", "users.json")  # mesmo do bot.py

if not API_TOKEN:
    raise RuntimeError("Missing API_TOKEN in .env")
if not DEFAULT_USER_ID:
    raise RuntimeError("Missing DEFAULT_USER_ID in .env")

# gspread via OAuth2 (usa token.json que você já tem)
gspread_client = gspread.oauth()

# ------- Helpers -------
def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    return {}

def get_user_sheet(user_id: str) -> str | None:
    users = load_users()
    info = users.get(user_id)
    return info["sheet_id"] if info else None

def normalize_amount(text: str) -> float:
    """
    Aceita '12,50' ou '12.50' e remove símbolos (R$, espaços, etc).
    """
    if text is None:
        raise ValueError("amount is required")
    clean = "".join(ch for ch in text if ch.isdigit() or ch in ",.-")
    # troca vírgula por ponto, mas mantém apenas o último ponto como decimal
    clean = clean.replace(",", ".")
    return float(clean)

def parse_date(text: str | None) -> str:
    """
    Retorna YYYY-MM-DD. Se não vier data, usa hoje.
    Aceita formatos comuns: 2025-08-24, 24/08/2025, 24-08-2025.
    """
    if not text:
        return datetime.now().strftime("%Y-%m-%d")

    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    # fallback: hoje
    return datetime.now().strftime("%Y-%m-%d")

# ------- Flask App -------
app = Flask(__name__)

@app.post("/api/expense")
def api_expense():
    # 1) Autenticação simples por header
    auth = request.headers.get("Authorization", "")
    if auth != f"Bearer {API_TOKEN}":
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    # 2) Payload
    data = request.get_json(silent=True) or {}
    # Você pode enviar: amount, category, description, date (opcional), user_id (opcional)
    # Se não mandar user_id, usa DEFAULT_USER_ID
    user_id = str(data.get("user_id") or DEFAULT_USER_ID)

    try:
        amount = normalize_amount(str(data.get("amount", "")))
    except Exception:
        return jsonify({"ok": False, "error": "invalid amount"}), 400

    category = (data.get("category") or "Other").strip()
    description = (data.get("description") or "").strip()
    date_str = parse_date(data.get("date"))

    # 3) Sheet do usuário
    sheet_id = get_user_sheet(user_id)
    if not sheet_id:
        return jsonify({"ok": False, "error": "user not registered"}), 404

    try:
        sh = gspread_client.open_by_key(sheet_id).sheet1
        # Grava como USER_ENTERED para não colocar ' na data/valor
        row = [date_str, category, amount, description]
        sh.append_row(row, value_input_option="USER_ENTERED")
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

    return jsonify({"ok": True, "saved": {"date": date_str, "category": category, "amount": amount, "description": description}}), 200

if __name__ == "__main__":
    # dev only; em produção use gunicorn (abaixo)
    app.run(host="0.0.0.0", port=int(os.getenv("API_PORT", "8080")), debug=False)
