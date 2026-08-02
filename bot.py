import os
import re
import logging
import threading
from io import BytesIO
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
PORT = int(os.environ.get("PORT", 10000))

# 2^(MAX_LOCAL_LENGTH-1) combinations is the ceiling we'll actually list out.
# Above this, Gmail usernames get long enough that the combo count explodes
# (e.g. 20 chars -> 524,288 combos), so we just report the total instead.
MAX_LOCAL_LENGTH = 15


def extract_local_and_domain(email: str):
    """Return (canonical_local_part, domain) for a gmail.com/googlemail.com
    address, or None if the input isn't a plausible Gmail address."""
    email = email.strip().lower()
    if "@" not in email:
        return None
    local, _, domain = email.partition("@")
    if domain not in ("gmail.com", "googlemail.com"):
        return None
    # Gmail ignores everything after a "+" and ignores dots entirely.
    local = local.split("+")[0]
    canonical = local.replace(".", "")
    if not canonical or not canonical.isalnum():
        return None
    return canonical, domain


def generate_dot_variations(canonical: str):
    """All ways to insert dots between characters of canonical (Gmail forbids
    a dot as the very first or last character, so we only vary the gaps
    between letters)."""
    n = len(canonical)
    if n <= 1:
        return [canonical]
    variations = []
    for mask in range(2 ** (n - 1)):
        chars = [canonical[0]]
        for i in range(1, n):
            if mask & (1 << (i - 1)):
                chars.append(".")
            chars.append(canonical[i])
        variations.append("".join(chars))
    return variations


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hi! Send me a Gmail address (e.g. john.doe@gmail.com) and I'll list every "
        "dot-variation of it — Gmail treats them all as the same inbox.\n\n"
        f"Note: for usernames longer than {MAX_LOCAL_LENGTH} characters I'll only "
        "give you the total count, since the full list gets huge."
    )


async def handle_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    result = extract_local_and_domain(text)
    if not result:
        await update.message.reply_text(
            "That doesn't look like a valid Gmail address. Try something like "
            "john.doe@gmail.com."
        )
        return

    canonical, domain = result
    total = 2 ** (len(canonical) - 1)

    if len(canonical) > MAX_LOCAL_LENGTH:
        await update.message.reply_text(
            f"'{canonical}@{domain}' has {len(canonical)} characters, which means "
            f"{total:,} possible dot combinations — too many to list here."
        )
        return

    variations = generate_dot_variations(canonical)
    full_list = [f"{v}@{domain}" for v in variations]

    header = f"Found {len(full_list)} dot variation(s) for {canonical}@{domain}:\n\n"
    body = "\n".join(full_list)
    message = header + body

    # Telegram messages are capped at 4096 characters; send as a file instead
    # of splitting into several messages when the list is long.
    if len(message) > 4000:
        buf = BytesIO(body.encode("utf-8"))
        buf.name = f"{canonical}_dot_variations.txt"
        await update.message.reply_document(document=buf, caption=header)
    else:
        await update.message.reply_text(message)


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        pass  # keep the console quiet


def run_health_server():
    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    server.serve_forever()


def main():
    if not BOT_TOKEN:
        raise RuntimeError("Set the BOT_TOKEN environment variable to your Telegram bot token.")

    # Render's "Web Service" type expects something listening on $PORT.
    # This tiny server just answers health checks while the bot polls
    # Telegram in the background.
    threading.Thread(target=run_health_server, daemon=True).start()

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_email))

    logger.info("Bot starting (polling mode)...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
