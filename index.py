import telebot
import gspread
import json
import os
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from collections import defaultdict
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# ==== CONFIGURATION ====
TELEGRAM_TOKEN = '8104853286:AAGAtRTUcvom5rprRPQhj2BlFKXZOXCr7Oo'
bot = telebot.TeleBot(TELEGRAM_TOKEN)

# ==== Load user configuration ====
if os.path.exists('users_config.json'):
    with open('users_config.json', 'r') as f:
        USERS_CONFIG = json.load(f)
else:
    USERS_CONFIG = {}

# ==== Function: get user sheet ====

def get_user_sheet(user_id):
    """Return the Google Sheet object for the given user_id."""
    user_id_str = str(user_id)
    if user_id_str not in USERS_CONFIG:
        return None, "User not registered. Use /register to start."

    config = USERS_CONFIG[user_id_str]
    creds_file = config['credentials_file']
    spreadsheet_id = config['spreadsheet_id']

    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name(creds_file, scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(spreadsheet_id).sheet1
        return sheet, None
    except Exception as e:
        return None, f"Error accessing your sheet: {e}"

# ==== Command: /start ====

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "Hello! 👋\nUse /register to register your account.\n\nTo register expenses:\n/expense amount category description\n\nTo get your monthly report:\n/report")

# ==== Command: /register ====

@bot.message_handler(commands=['register'])
def register_user(message):
    user_id = str(message.from_user.id)
    username = message.from_user.username

    if user_id in USERS_CONFIG:
        bot.reply_to(message, "✅ You are already registered.")
        return

    msg = bot.reply_to(message, "Please send your Google Spreadsheet ID to link your account.")
    bot.register_next_step_handler(msg, process_spreadsheet_id, user_id, username)

def process_spreadsheet_id(message, user_id, username):
    spreadsheet_id = message.text.strip()

    # Use a default credentials file for all users
    default_credentials_file = 'credentials.json'

    # Load existing config
    if os.path.exists('users_config.json'):
        with open('users_config.json', 'r') as f:
            users_config = json.load(f)
    else:
        users_config = {}

    # Add the new user
    users_config[user_id] = {
        "credentials_file": default_credentials_file,
        "spreadsheet_id": spreadsheet_id
    }

    # Save back to file
    with open('users_config.json', 'w') as f:
        json.dump(users_config, f, indent=4)

    # Update global variable
    global USERS_CONFIG
    USERS_CONFIG = users_config

    bot.reply_to(message, f"✅ Registration completed!\nYour data is now linked to Spreadsheet ID:\n{spreadsheet_id}")

# ==== Command: /expense ====

@bot.message_handler(commands=['expense'])
def register_expense(message):
    user_id = message.from_user.id
    sheet, error = get_user_sheet(user_id)
    if error:
        bot.reply_to(message, error)
        return

    try:
        parts = message.text.split(maxsplit=3)
        if len(parts) < 4:
            bot.reply_to(message, "❌ Incorrect format. Use:\n/expense amount category description")
            return
        
        amount = float(parts[1].replace(',', '.'))
        category = parts[2]
        description = parts[3]
        date = datetime.now().strftime("%d/%m/%Y")
        username = message.from_user.username

        # Append to user-specific Google Sheet
        sheet.append_row([date, amount, category, description, str(user_id), username])

        bot.reply_to(message, f"✅ Expense of R${amount:.2f} registered in *{category}*.", parse_mode="Markdown")

    except Exception as e:
        bot.reply_to(message, f"❌ Error registering expense: {e}")

# ==== Command: /report ====

@bot.message_handler(commands=['report'])
def report(message):
    user_id = message.from_user.id
    sheet, error = get_user_sheet(user_id)
    if error:
        bot.reply_to(message, error)
        return

    try:
        records = sheet.get_all_records()

        current_month = datetime.now().strftime("%m/%Y")
        total_month = 0
        category_totals = defaultdict(float)

        for r in records:
            if str(r['User_ID']) == str(user_id):
                record_date = datetime.strptime(r['Data'], "%d/%m/%Y")
                record_month = record_date.strftime("%m/%Y")
                if record_month == current_month:
                    value = float(r['Valor'])
                    total_month += value
                    category_totals[r['Categoria']] += value

        response = f"📊 *Report for this month ({current_month}):*\nTotal: R${total_month:.2f}\n"
        for cat, val in category_totals.items():
            response += f"- {cat}: R${val:.2f}\n"

        bot.reply_to(message, response, parse_mode="Markdown")

    except Exception as e:
        bot.reply_to(message, f"❌ Error generating report: {e}")

# ==== START BOT ====
print("🤖 Bot is running...")
bot.polling()
