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

CATEGORIES = ["Food", "Transport", "Entertainment", "Emergency", "Other"]

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
        KeyboardButton("➕ Add Expense"),
        KeyboardButton("🗑 Remove Expense")
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
        date = datetime.now().strftime("%Y/%m/%d")
    
    sheet_id = user_data[user_id]["sheet_id"]
    sheet = gspread_client.open_by_key(sheet_id).sheet1
    sheet.append_row([date, category, amount],
                     value_input_option="USER_ENTERED"
                     )

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
            row_date = datetime.strptime(row["Date"], "%Y/%m/%d")
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
    if message.text == "❌ Cancel":
        welcome(message)
        return

    category = message.text
    # if category not in CATEGORIES:
    #     bot.reply_to(message, "❌ Invalid category. Try /add again or /back.")
    #     return

    msg = bot.send_message(message.chat.id, "Enter the amount:")
    bot.register_next_step_handler(msg, process_amount_step, user_id, category)

def process_amount_step(message, user_id, category):
    if message.text == "❌ Cancel":
        bot.send_message(message.chat.id, "Cancelled! Back to main menu ⬇️")
        show_main_menu(message)
        return

    try:
        amount_text = message.text.replace(",", ".")
        amount = float(amount_text)
    except ValueError:
        bot.reply_to(message, "❌ Invalid number. Please enter a number (e.g. 12.5 or 12,5). Or Try /add again or /back.")
        return

    add_expense(user_id, category, amount)
    bot.reply_to(message, f"✅ Added {amount} to {category}.")
    show_main_menu(message.chat.id)

def get_last_expenses(user_id, limit=5):
    sheet_id = user_data[user_id]["sheet_id"]
    sheet = gspread_client.open_by_key(sheet_id).sheet1
    records = sheet.get_all_records()

    if not records:
        return None, "📭 No expenses found."

    last_records = records[-limit:]
    return last_records, None

def remove_expense(user_id, row_index):
    sheet_id = user_data[user_id]["sheet_id"]
    sheet = gspread_client.open_by_key(sheet_id).sheet1
    records = sheet.get_all_records()

    if row_index < 0 or row_index >= len(records):
        return "⚠️ Invalid record number."

    sheet.delete_rows(row_index + 2)
    return "🗑 Expense removed successfully!"

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
            KeyboardButton("❌ Cancel")
        )
        msg = bot.send_message(message.chat.id, "Select a category:", reply_markup=markup)
        bot.register_next_step_handler(msg, process_category_step, user_id)
        return

    try:
        amount_text = parts[1].replace(",", ".")
        amount = float(amount_text)
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

@bot.message_handler(commands=["remove"])
def choose_expense_to_remove(message):
    user_id = str(message.from_user.id)
    if user_id not in user_data:
        bot.reply_to(message, "⚠️ You must /register first.")
        return

    last_records, error = get_last_expenses(user_id)

    if error:
        bot.reply_to(message, error)
        return

    markup = types.InlineKeyboardMarkup()
    for i, row in enumerate(last_records):

        row_date = datetime.strptime(row["Date"], "%Y/%m/%d")

        label = f"{row_date.day}/{row_date.month} - {row['Category']} - $ {row['Amount']:.2f}"
        markup.add(types.InlineKeyboardButton(
            text=label, callback_data=f"remove:{len(last_records) - i}"
        ))
    markup.add(
        types.InlineKeyboardButton("❌ Cancel", callback_data="cancel")
    )

    bot.send_message(
        message.chat.id,
        "🗑 Select the expense you want to remove:",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("remove:") or call.data == "cancel")
def handle_remove_callback(call):
    user_id = str(call.from_user.id)
    if user_id not in user_data:
        bot.reply_to(call, "⚠️ You must /register first.")
        return

    if call.data == "cancel":
        bot.answer_callback_query(call.id, "Cancelled ❌")
        bot.send_message(call.message.chat.id, "Back to main menu ⬇️")
        show_main_menu(call.message)
        return

    index = int(call.data.split(":")[1])
    sheet_id = user_data[user_id]["sheet_id"]
    sheet = gspread_client.open_by_key(sheet_id).sheet1
    total_records = len(sheet.get_all_records())

    row_index = total_records - index  # converte para índice real
    result = remove_expense(user_id, row_index)

    bot.answer_callback_query(call.id, result)
    bot.send_message(call.message.chat.id, result)

@bot.message_handler(func=lambda m: m.text == "🗑 Remove Expense")
def choose_expense_to_remove_button(message):
    choose_expense_to_remove(message)

# =======================
# FALLBACK HANDLER
# =======================
@bot.message_handler(func=lambda m: True, content_types=["text"])
def fallback(message):
    known_options = [
        "➕ Add Expense",
        "📊 Quick Report",
        "📅 Full Report",
        "🗑 Remove Expense",
        "♻️ Re-register",
        "♻️ Back",
        "📄 Help"
    ]
    if message.text not in known_options and not message.text.startswith("/"):
        bot.reply_to(message, "❌ Option not recognized. Please use Use:\n"
        "/add - Add an expense\n"
        "/remove - Remove an expense\n"
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
