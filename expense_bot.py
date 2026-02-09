import os
import sqlite3
import csv
from datetime import datetime, timedelta

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
    ContextTypes,
    filters
)

# =========================
# SET TOKEN DI SINI
# =========================


import os
TOKEN = os.getenv("8595195808:AAE_z5NEMOw5qppTQ0jRqtYqRT_4evpYpSE")


DB_NAME = "expenses.db"


# =========================
# DATABASE
# =========================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            category TEXT,
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()


def add_expense(user_id, amount, category):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO expenses (user_id, amount, category, created_at)
        VALUES (?, ?, ?, ?)
    """, (user_id, amount, category, datetime.now().isoformat()))
    conn.commit()
    conn.close()


def get_expenses(user_id, start_date=None):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    if start_date:
        cur.execute("""
            SELECT id, amount, category, created_at
            FROM expenses
            WHERE user_id = ? AND created_at >= ?
            ORDER BY created_at DESC
        """, (user_id, start_date.isoformat()))
    else:
        cur.execute("""
            SELECT id, amount, category, created_at
            FROM expenses
            WHERE user_id = ?
            ORDER BY created_at DESC
        """, (user_id,))

    rows = cur.fetchall()
    conn.close()
    return rows


def delete_last_expense(user_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
        SELECT id, amount, category
        FROM expenses
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 1
    """, (user_id,))
    row = cur.fetchone()

    if row:
        expense_id = row[0]
        cur.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
        conn.commit()
        conn.close()
        return row
    else:
        conn.close()
        return None


# =========================
# HELPERS
# =========================
def format_expense_list(rows, title="Expenses"):
    if not rows:
        return f"📭 {title}: Tiada rekod."

    text = f"📌 {title}\n\n"
    total = 0

    for _, amount, category, created_at in rows:
        date_obj = datetime.fromisoformat(created_at)
        date_str = date_obj.strftime("%d %b %Y %I:%M %p")
        text += f"• RM{amount:.2f} - {category} ({date_str})\n"
        total += amount

    text += f"\n💰 Total: RM{total:.2f}"
    return text


def parse_expense_message(msg: str):
    msg = msg.strip().lower()

    # Accept: rm12 makan / rm12.50 makan
    if msg.startswith("rm"):
        msg = msg[2:].strip()

    parts = msg.split()

    if len(parts) < 2:
        return None

    try:
        amount = float(parts[0])
    except:
        return None

    category = " ".join(parts[1:])
    return amount, category


# =========================
# COMMANDS
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Hai! Aku Expense Tracker Bot.\n\n"
        "Cara guna:\n"
        "• rm12 makan\n"
        "• rm5 air\n"
        "• rm80 minyak\n\n"
        "Commands:\n"
        "/today - hari ini\n"
        "/week - 7 hari\n"
        "/month - 30 hari\n"
        "/summary - ikut kategori\n"
        "/undo - delete last\n"
        "/export - download CSV"
    )


async def today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    rows = get_expenses(user_id, start_date)
    await update.message.reply_text(format_expense_list(rows, "Expenses Today"))


async def week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    start_date = datetime.now() - timedelta(days=7)
    rows = get_expenses(user_id, start_date)
    await update.message.reply_text(format_expense_list(rows, "Expenses Last 7 Days"))


async def month(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    start_date = datetime.now() - timedelta(days=30)
    rows = get_expenses(user_id, start_date)
    await update.message.reply_text(format_expense_list(rows, "Expenses Last 30 Days"))


async def summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    rows = get_expenses(user_id)

    if not rows:
        await update.message.reply_text("📭 Tiada rekod untuk summary.")
        return

    summary_map = {}
    total = 0

    for _, amount, category, _ in rows:
        summary_map[category] = summary_map.get(category, 0) + amount
        total += amount

    text = "📊 Summary ikut kategori:\n\n"
    for cat, amt in sorted(summary_map.items(), key=lambda x: x[1], reverse=True):
        text += f"• {cat}: RM{amt:.2f}\n"

    text += f"\n💰 Total semua: RM{total:.2f}"
    await update.message.reply_text(text)


async def undo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    deleted = delete_last_expense(user_id)

    if not deleted:
        await update.message.reply_text("❌ Takde rekod nak delete.")
        return

    _, amount, category = deleted
    await update.message.reply_text(f"🗑️ Deleted last: RM{amount:.2f} - {category}")


async def export_csv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    rows = get_expenses(user_id)

    if not rows:
        await update.message.reply_text("📭 Tiada data untuk export.")
        return

    filename = f"expenses_{user_id}.csv"

    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "amount", "category", "created_at"])
        for row in rows:
            writer.writerow(row)

    await update.message.reply_document(document=open(filename, "rb"))


# =========================
# MESSAGE HANDLER
# =========================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    msg = update.message.text

    parsed = parse_expense_message(msg)
    if not parsed:
        return

    amount, category = parsed
    add_expense(user_id, amount, category)

    await update.message.reply_text(
        f"✅ Saved: RM{amount:.2f} ({category})"
    )


# =========================
# MAIN
# =========================
def main():
    if TOKEN == "TOKEN_KAU_SINI" or not TOKEN.strip():
        print("❌ ERROR: Kau belum letak TOKEN betul dalam code.")
        return

    init_db()

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("today", today))
    app.add_handler(CommandHandler("week", week))
    app.add_handler(CommandHandler("month", month))
    app.add_handler(CommandHandler("summary", summary))
    app.add_handler(CommandHandler("undo", undo))
    app.add_handler(CommandHandler("export", export_csv))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("✅ Expense bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
