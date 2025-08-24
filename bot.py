import os
import json
import telebot
import gspread
from googleapiclient.discovery import build
from datetime import datetime
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
from google.oauth2.credentials import Credentials
from telebot import types
from dotenv import load_dotenv

# =======================
# CONFIG
# =======================
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TEMPLATE_SHEET_ID = os.getenv("TEMPLATE_SHEET_ID")

bot = telebot.TeleBot(TELEGRAM_TOKEN)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# Carrega credenciais salvas pelo auth_setup.py
creds = Credentials.from_authorized_user_file("token.json", SCOPES)

# GSpread client
gspread_client = gspread.authorize(creds)

CATEGORIES = ["Food", "Transport", "Entertainment", "Other"]

# =======================
# USER DATA PERSISTENCE
# =======================
USER_FILE = "users.json"
user_data = {}

def load_users():
    global user_data
    if os.path.exists(USER_FILE):
        with open(USER_FILE, "r") as f:
            user_data = json.load(f)
    else:
        user_data = {}

def save_users():
    with open(USER_FILE, "w") as f:
        json.dump(user_data, f, indent=2)

# =======================
# MENU
# =======================
def show_main_menu(chat_id):
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    markup.add(
        KeyboardButton("➕ Add Expense")
    )
    markup.add(
        KeyboardButton("📊 Quick Report"),
        KeyboardButton("📅 Full Report"),
        KeyboardButton("📄 Help")
    )
    bot.send_message(chat_id, "Choose an option:", reply_markup=markup)

# =======================
# SHEETS FUNCTIONS
# =======================
def create_user_sheet(username):
    drive_service = build("drive", "v3", credentials=creds)
    new_file = {
        "name": f"Expenses_{username}",
        "mimeType": "application/vnd.google-apps.spreadsheet"
    }
    copied = drive_service.files().copy(
        fileId=TEMPLATE_SHEET_ID, body=new_file
    ).execute()

    return copied["id"]

def add_expense(user_id, category, amount, date=None):
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")
    
    sheet_id = user_data[user_id]["sheet_id"]
    sheet = gspread_client.open_by_key(sheet_id).sheet1
    sheet.append_row([date, category, amount])

def get_report(user_id, period="month"):
    sheet_id = user_data[user_id]["sheet_id"]
    sheet = gspread_client.open_by_key(sheet_id)
    ws = sheet.sheet1
    records = ws.get_all_records()

    now = datetime.now()
    filtered = []
    totals_by_category = {}
    report_lines = [f"-- REPORT --"]

    for row in records:
        try:
            row_date = datetime.strptime(row["Date"], "%Y-%m-%d")
            amount = float(row["Amount"])
            category = row["Category"]
        except Exception:
            continue

        if period == "month" and row_date.month == now.month and row_date.year == now.year:
            filtered.append(row)
            totals_by_category[category] = totals_by_category.get(category, 0) + amount
        elif period == "year" and row_date.year == now.year:
            filtered.append(row)
            totals_by_category[category] = totals_by_category.get(category, 0) + amount
        elif period == "all":
            filtered.append(row)
            totals_by_category[category] = totals_by_category.get(category, 0) + amount

    if not filtered:
        return "📊 No records found for this period."

    if period == "month" and row_date.month == now.month and row_date.year == now.year:
        report_lines.append(f"({period}) [ {row_date.month}/{row_date.year} ]")
    elif period == "year" and row_date.year == now.year:
        report_lines.append(f"({period}) [ {row_date.year} ]")

    total_sum = 0
    for cat, total in totals_by_category.items():
        report_lines.append(f"- {cat}: {total:.2f}")
        total_sum += total

    report_lines.append(f"\n💰 Total: {total_sum:.2f}")

    return "\n".join(report_lines)
    # return total, filtered

def process_category_step(message, user_id):
    category = message.text
    # if category not in CATEGORIES:
    #     bot.reply_to(message, "❌ Invalid category. Try /add again or /back.")
    #     return

    msg = bot.send_message(message.chat.id, "Enter the amount:")
    bot.register_next_step_handler(msg, process_amount_step, user_id, category)

def process_amount_step(message, user_id, category):
    try:
        amount = float(message.text)
    except ValueError:
        bot.reply_to(message, "❌ Invalid number. Try /add again or /back.")
        return

    add_expense(user_id, category, amount)
    bot.reply_to(message, f"✅ Added {amount} to {category}.")
    show_main_menu(message.chat.id)

# =======================
# HANDLERS
# =======================
@bot.message_handler(commands=["start", "back"])
def welcome(message):
    user_id = str(message.from_user.id)
    if user_id not in user_data:
        bot.reply_to(message, "👋 Welcome! Use /register to create your personal expense sheet.")
        return

    username = message.from_user.username or f"{user_id}"
    bot.reply_to(message, "👋 Welcome! user: "+username)
    show_main_menu(message.chat.id)

@bot.message_handler(func=lambda m: m.text == "♻️ Back")
def back_button(message):
    welcome(message)

@bot.message_handler(commands=["help"])
def help_command(message):
    user_id = str(message.from_user.id)
    if user_id not in user_data:
        bot.reply_to(message, "👋 Welcome! Use /register to create your personal expense sheet.")
        return

    bot.reply_to(message, "👋 Shortchut:\n"
        "/add <amount> <category>\n\n"
        "    /add 9 Food \n\n\n"
        "👋 Or use commands:\n"
        "/start - See your account details\n"
        "/register - Register your account or Renew your data\n"
        "/add - Add an expense\n"
        "/report - Show monthly/yearly report \n"
        "/help - Show all commands \n"
        "or choose the buttons bellow.")
    show_main_menu(message.chat.id)

@bot.message_handler(func=lambda m: m.text == "📄 Help")
def help_button(message):
    help_command(message)

@bot.message_handler(commands=["register"])
def register_user(message):
    user_id = str(message.from_user.id)
    username = message.from_user.username or f"user{user_id}"

    sheet_id = create_user_sheet(username)
    user_data[user_id] = {"username": username, "sheet_id": sheet_id}
    save_users()

    bot.reply_to(message, f"✅ Registered! Your sheet is ready: https://docs.google.com/spreadsheets/d/{sheet_id}")
    show_main_menu(message.chat.id)

@bot.message_handler(commands=["add"])
def add_expense_command(message):
    """
    /add <amount> <category>
    Example: /add 9 Food
    """
    user_id = str(message.from_user.id)
    if user_id not in user_data:
        bot.reply_to(message, "⚠️ You are not registered. Use /register first.")
        return

    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
        for c in CATEGORIES:
            markup.add(c)

        markup.add(
            KeyboardButton("♻️ Back")
        )
        msg = bot.send_message(message.chat.id, "Select a category:", reply_markup=markup)
        bot.register_next_step_handler(msg, process_category_step, user_id)
        return
    
    if message.text == "➕ Add Expense":
        markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
        for c in CATEGORIES:
            markup.add(c)

        markup.add(
            KeyboardButton("♻️ Back")
        )
        msg = bot.send_message(message.chat.id, "Select a category:", reply_markup=markup)
        bot.register_next_step_handler(msg, process_category_step, user_id)
        return

    try:
        amount = float(parts[1])
        category = parts[2]
    except ValueError:
        bot.reply_to(message, "Amount must be a number.")
        show_main_menu(message.chat.id)
        return

    add_expense(user_id, category, amount)
    bot.send_message(message.chat.id, f"✅ Added {amount} to category {category}.")
    show_main_menu(message.chat.id)

@bot.message_handler(func=lambda m: m.text == "➕ Add Expense")
def add_expense_button(message):
    add_expense_command(message)

@bot.message_handler(commands=["full_report"])
def sheet_link_command(message):
    user_id = str(message.from_user.id)
    if user_id not in user_data:
        bot.reply_to(message, "⚠️ You are not registered. Use /register first.")
        return

    sheet_id = user_data[user_id]["sheet_id"]
    bot.reply_to(message, f"📄 Here is your full report: https://docs.google.com/spreadsheets/d/{sheet_id}")
    show_main_menu(message.chat.id)

@bot.message_handler(func=lambda m: m.text == "📅 Full Report")
def sheet_link_button(message):
    sheet_link_command(message)

@bot.message_handler(commands=["report"])
def report_command(message):
    user_id = str(message.from_user.id)
    if user_id not in user_data:
        bot.reply_to(message, "⚠️ You must /register first.")
        return

    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    markup.add("Month", "Year", "All")
    markup.add(
        KeyboardButton("♻️ Back")
    )
    msg = bot.send_message(message.chat.id, "Which report?", reply_markup=markup)
    bot.register_next_step_handler(msg, process_report_step, user_id)

@bot.message_handler(func=lambda m: m.text == "📊 Quick Report")
def report_button(message):
    report_command(message)

def process_report_step(message, user_id):
    choice = message.text.lower()
    if choice not in ["month", "year", "all"]:
        bot.reply_to(message, "❌ Invalid choice. Use /report again or /back.")
        return

    user_id = str(message.from_user.id)
    report = get_report(user_id, period=choice)
    bot.reply_to(message, f"{report}")
    show_main_menu(message.chat.id)

@bot.message_handler(func=lambda m: m.text == "♻️ Re-register")
def re_register_button(message):
    register_user(message)

# =======================
# FALLBACK HANDLER
# =======================
@bot.message_handler(func=lambda m: True, content_types=["text"])
def fallback(message):
    known_options = [
        "➕ Add Expense",
        "📊 Quick Report",
        "📅 Full Report",
        "♻️ Re-register",
        "♻️ Back",
        "📄 Help"
    ]
    if message.text not in known_options and not message.text.startswith("/"):
        bot.reply_to(message, "❌ Option not recognized. Please use Use:\n"
        "/add - Add an expense\n"
        "/report - Show monthly/yearly report \n"
        "/help - Show all commands \n"
        "or use the buttons bellow.")
        show_main_menu(message.chat.id)

# =======================
# START BOT
# =======================
if __name__ == "__main__":
    load_users()
    print("🤖 Bot is running...")
    bot.infinity_polling()
