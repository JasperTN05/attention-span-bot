"""
Reading Focus Bot – Telegram Bot
Unterscheidet zwischen /lesen (privat, entspannt) und /lernen (aktives Lernen mit Spaced Repetition).
"""

import os
import json
import asyncio
from datetime import datetime, timedelta, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters, ConversationHandler
)
from storage import Storage

# Conversation states
WAITING_RECALL = "waiting_recall"
WAITING_TOPIC = "waiting_topic"

# Spaced Repetition Intervalle (in Tagen)
SR_INTERVALS = [1, 3, 7, 14, 30]

storage = Storage()


# ─────────────────────────────────────────────
# /start
# ─────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "👋 *Reading Focus Bot*\n\n"
        "Ich helfe dir beim konzentrierten Lesen und Lernen.\n\n"
        "*Befehle:*\n"
        "📖 `/lesen [Minuten]` – Fokus-Timer (entspannt, kein Recall)\n"
        "🧠 `/lernen [Minuten]` – Lern-Timer (mit Active Recall + Spaced Repetition)\n"
        "📊 `/stats` – Deine Lernstatistiken\n"
        "🔁 `/wiederholungen` – Fällige Wiederholungen anzeigen\n"
        "❌ `/stop` – Aktuellen Timer abbrechen\n\n"
        "_Tipp: `/lernen 25` startet einen 25-Minuten Lern-Timer_"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


# ─────────────────────────────────────────────
# /lesen – reiner Timer, kein Recall
# ─────────────────────────────────────────────
async def lesen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    minutes = _parse_minutes(context.args, default=20)

    await update.message.reply_text(
        f"📖 *Lese-Timer gestartet: {minutes} Minuten*\n\n"
        f"Viel Spaß beim Lesen! Ich melde mich wenn die Zeit um ist.\n"
        f"_(Kein Druck – beim Lesen geht es ums Genießen)_",
        parse_mode="Markdown"
    )

    # Timer als Job planen
    context.job_queue.run_once(
        lesen_timer_done,
        when=minutes * 60,
        data={"user_id": user_id, "minutes": minutes, "chat_id": update.effective_chat.id},
        name=f"lesen_{user_id}"
    )

    storage.set_active_session(user_id, {
        "mode": "lesen",
        "started": datetime.now(timezone.utc).isoformat(),
        "minutes": minutes,
        "chat_id": update.effective_chat.id
    })


async def lesen_timer_done(context: ContextTypes.DEFAULT_TYPE):
    data = context.job.data
    await context.bot.send_message(
        chat_id=data["chat_id"],
        text=(
            f"⏱ *{data['minutes']} Minuten Lesen geschafft!*\n\n"
            f"Super! Gönn dir eine kurze Pause. 🎉\n"
            f"Noch eine Runde? `/lesen {data['minutes']}`"
        ),
        parse_mode="Markdown"
    )
    storage.clear_active_session(data["user_id"])


# ─────────────────────────────────────────────
# /lernen – Timer + Active Recall + Spaced Rep
# ─────────────────────────────────────────────
async def lernen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    minutes = _parse_minutes(context.args, default=25)

    # Thema abfragen
    context.user_data["lernen_minutes"] = minutes
    context.user_data["lernen_chat_id"] = update.effective_chat.id
    context.user_data["state"] = WAITING_TOPIC

    await update.message.reply_text(
        f"🧠 *Lern-Timer: {minutes} Minuten*\n\n"
        f"Was ist das *Thema* oder der Abschnitt den du lernst?\n",
        parse_mode="Markdown"
    )


async def handle_topic_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Empfängt das Thema und startet den Timer."""
    user_id = update.effective_user.id
    topic = update.message.text.strip()
    minutes = context.user_data.get("lernen_minutes", 25)
    chat_id = context.user_data.get("lernen_chat_id")

    context.user_data["state"] = None
    context.user_data["current_topic"] = topic

    await update.message.reply_text(
        f"✅ Thema gespeichert: *{topic}*\n\n"
        f"⏳ Timer läuft – {minutes} Minuten fokussiertes Lernen!\n"
        f"Ich melde mich danach für einen kurzen Recall. 💪",
        parse_mode="Markdown"
    )

    context.job_queue.run_once(
        lernen_timer_done,
        when=minutes * 60,
        data={
            "user_id": user_id,
            "chat_id": chat_id,
            "topic": topic,
            "minutes": minutes
        },
        name=f"lernen_{user_id}"
    )

    storage.set_active_session(user_id, {
        "mode": "lernen",
        "topic": topic,
        "started": datetime.now(timezone.utc).isoformat(),
        "minutes": minutes,
        "chat_id": chat_id
    })


async def lernen_timer_done(context: ContextTypes.DEFAULT_TYPE):
    data = context.job.data
    user_id = data["user_id"]

    # Recall-State setzen (wird in handle_message verarbeitet)
    # Wir speichern pending recall in storage
    storage.set_pending_recall(user_id, {
        "topic": data["topic"],
        "chat_id": data["chat_id"],
        "minutes": data["minutes"],
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

    await context.bot.send_message(
        chat_id=data["chat_id"],
        text=(
            f"⏱ *{data['minutes']} Minuten vorbei!*\n\n"
            f"📝 *Active Recall – ohne nachzuschauen:*\n"
            f"Thema war: _{data['topic']}_\n\n"
            f"Schreib in *2-3 Sätzen* was du gerade gelernt hast.\n"
            f"_(Einfach antworten – kein Perfektionismus nötig)_"
        ),
        parse_mode="Markdown"
    )


async def handle_recall_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Speichert Recall-Antwort und plant Spaced Repetition."""
    user_id = update.effective_user.id
    recall_text = update.message.text.strip()
    pending = storage.get_pending_recall(user_id)

    if not pending:
        return False  # Kein ausstehender Recall

    topic = pending["topic"]
    now = datetime.now(timezone.utc)

    # Eintrag in Lernhistorie speichern
    entry = {
        "topic": topic,
        "recall": recall_text,
        "learned_at": now.isoformat(),
        "review_count": 0,
        "next_review": (now + timedelta(days=SR_INTERVALS[0])).isoformat(),
        "minutes": pending.get("minutes", 25)
    }
    entry_id = storage.add_learning_entry(user_id, entry)

    storage.clear_pending_recall(user_id)
    storage.clear_active_session(user_id)

    next_review_date = (now + timedelta(days=SR_INTERVALS[0])).strftime("%d.%m.%Y")

    keyboard = [[
        InlineKeyboardButton("➕ Noch eine Runde", callback_data=f"more_{pending['minutes']}"),
        InlineKeyboardButton("📊 Stats", callback_data="stats")
    ]]

    await update.message.reply_text(
        f"✅ *Gespeichert!*\n\n"
        f"Thema: _{topic}_\n"
        f"🔁 Nächste Wiederholung: *{next_review_date}*\n\n"
        f"Gut gemacht! Spaced Repetition macht den Unterschied. 🧠",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return True


# ─────────────────────────────────────────────
# Allgemeiner Message Handler (State Machine)
# ─────────────────────────────────────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    state = context.user_data.get("state")

    # Thema-Eingabe erwartet?
    if state == WAITING_TOPIC:
        await handle_topic_input(update, context)
        return

    # Recall erwartet?
    if storage.get_pending_recall(user_id):
        handled = await handle_recall_input(update, context)
        if handled:
            return

    # Sonst ignorieren / Hilfe
    await update.message.reply_text(
        "Nutze `/lesen` oder `/lernen` um zu starten. /start für alle Befehle.",
        parse_mode="Markdown"
    )


# ─────────────────────────────────────────────
# /wiederholungen – fällige Reviews
# ─────────────────────────────────────────────
async def wiederholungen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    due = storage.get_due_reviews(user_id)

    if not due:
        await update.message.reply_text(
            "🎉 Keine fälligen Wiederholungen!\n\n"
            "Starte eine neue Session mit `/lernen`.",
            parse_mode="Markdown"
        )
        return

    text = f"🔁 *{len(due)} Wiederholung(en) fällig:*\n\n"
    for i, (entry_id, entry) in enumerate(due[:5], 1):  # max 5 anzeigen
        learned_date = datetime.fromisoformat(entry["learned_at"]).strftime("%d.%m.")
        text += f"*{i}.* _{entry['topic']}_ (gelernt: {learned_date})\n"

    text += "\nSchreibe zum Wiederholen was du noch weißt – ich starte dann den Recall:"

    keyboard = [[
        InlineKeyboardButton(f"🔁 Review starten", callback_data=f"review_0")
    ]]

    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    # Ersten fälligen Review als pending setzen
    context.user_data["due_reviews"] = [(eid, e) for eid, e in due[:5]]
    context.user_data["review_index"] = 0


# ─────────────────────────────────────────────
# /stats
# ─────────────────────────────────────────────
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = storage.get_stats(user_id)

    text = (
        f"📊 *Deine Statistiken*\n\n"
        f"📖 Lese-Sessions: {data['lesen_sessions']}\n"
        f"🧠 Lern-Sessions: {data['lernen_sessions']}\n"
        f"⏱ Gesamt-Lernzeit: {data['total_minutes']} Minuten\n"
        f"📝 Gespeicherte Themen: {data['total_entries']}\n"
        f"🔁 Abgeschlossene Reviews: {data['completed_reviews']}\n"
        f"📅 Fällige Wiederholungen: {data['due_reviews']}\n"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


# ─────────────────────────────────────────────
# /stop – Timer abbrechen
# ─────────────────────────────────────────────
async def stop_timer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    session = storage.get_active_session(user_id)

    # Jobs cancellen
    for job_name in [f"lesen_{user_id}", f"lernen_{user_id}"]:
        jobs = context.job_queue.get_jobs_by_name(job_name)
        for job in jobs:
            job.schedule_removal()

    storage.clear_active_session(user_id)
    storage.clear_pending_recall(user_id)
    context.user_data["state"] = None

    mode = session.get("mode", "Timer") if session else "Timer"
    await update.message.reply_text(
        f"❌ {mode.capitalize()}-Session abgebrochen.\n\n"
        f"Neue Session mit `/lesen` oder `/lernen` starten.",
        parse_mode="Markdown"
    )


# ─────────────────────────────────────────────
# Callback Handler (Buttons)
# ─────────────────────────────────────────────
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    data = query.data

    if data.startswith("more_"):
        minutes = int(data.split("_")[1])
        context.args = [str(minutes)]
        context.user_data["lernen_minutes"] = minutes
        context.user_data["lernen_chat_id"] = update.effective_chat.id
        context.user_data["state"] = WAITING_TOPIC
        await query.edit_message_text(
            f"🧠 Neue Lern-Session: {minutes} Minuten\n\nWas ist dein Thema?",
            parse_mode="Markdown"
        )

    elif data == "stats":
        data_stats = storage.get_stats(user_id)
        await query.edit_message_text(
            f"📊 *Stats*\n"
            f"🧠 Sessions: {data_stats['lernen_sessions']} | "
            f"⏱ {data_stats['total_minutes']} min | "
            f"🔁 {data_stats['due_reviews']} fällig",
            parse_mode="Markdown"
        )

    elif data.startswith("review_"):
        due = context.user_data.get("due_reviews", [])
        idx = context.user_data.get("review_index", 0)
        if idx < len(due):
            entry_id, entry = due[idx]
            context.user_data["current_review"] = (entry_id, entry)
            context.user_data["state"] = "waiting_review"
            await query.edit_message_text(
                f"🔁 *Review #{idx+1}*\n\n"
                f"Thema: _{entry['topic']}_\n\n"
                f"Was erinnerst du dich noch? (2-3 Sätze reichen)",
                parse_mode="Markdown"
            )


# ─────────────────────────────────────────────
# Scheduled: Erinnerungen prüfen (via Job Queue)
# ─────────────────────────────────────────────
async def check_reminders(context: ContextTypes.DEFAULT_TYPE):
    """Läuft regelmäßig und schickt fällige Wiederholungs-Pings."""
    all_users = storage.get_all_users()
    for user_id in all_users:
        session = storage.get_active_session(user_id)
        if not session:
            continue
        chat_id = session.get("chat_id")
        due = storage.get_due_reviews(user_id)
        if due and chat_id:
            await context.bot.send_message(
                chat_id=chat_id,
                text=(
                    f"🔁 Du hast *{len(due)} fällige Wiederholung(en)*!\n"
                    f"Nutze /wiederholungen um sie anzugehen."
                ),
                parse_mode="Markdown"
            )


# ─────────────────────────────────────────────
# Hilfsfunktionen
# ─────────────────────────────────────────────
def _parse_minutes(args, default=20):
    try:
        return max(1, min(int(args[0]), 180)) if args else default
    except (ValueError, IndexError):
        return default


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────
def main():
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    app = Application.builder().token(token).build()

    # Handler registrieren
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("lesen", lesen))
    app.add_handler(CommandHandler("lernen", lernen))
    app.add_handler(CommandHandler("wiederholungen", wiederholungen))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("stop", stop_timer))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Täglich Erinnerungen prüfen (alle 12h)
    app.job_queue.run_repeating(check_reminders, interval=43200, first=60)

    print("Bot läuft...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
