import os
import re
import time
import random
import logging
import threading
from io import BytesIO
from collections import defaultdict, deque
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
PORT = int(os.environ.get("PORT", 10000))

# 2^(MAX_LOCAL_LENGTH-1) combinations is the ceiling we'll actually list out.
# Above this, Gmail usernames get long enough that the combo count explodes
# (e.g. 20 chars -> 524,288 combos), so we just report the total instead.
MAX_LOCAL_LENGTH = 15

# Basic per-user rate limiting: at most RATE_LIMIT_MAX requests per use
# RATE_LIMIT_WINDOW seconds. Keeps one user from hammering the free instance.
RATE_LIMIT_MAX = 8
RATE_LIMIT_WINDOW = 60
_request_log = defaultdict(deque)

# Pre-compile regex for /tag command to avoid recompilation on every call
TAG_SANITIZE_REGEX = re.compile(r"[^A-Za-z0-9_-]")


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def extract_local_and_domain(email: str):
    """Return (canonical_local_part, domain) for a gmail.com/googlemail.com
    address, or None if the input isn't a plausible Gmail address."""
    email = email.strip().lower().rstrip(".")
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


def build_variation_from_mask(canonical: str, mask: int) -> str:
    """Build a single dot-variation from a canonical string and a bitmask.
    Each bit represents whether to insert a dot at that position."""
    chars = [canonical[0]]
    for i in range(1, len(canonical)):
        if mask & (1 << (i - 1)):
            chars.append(".")
        chars.append(canonical[i])
    return "".join(chars)


def generate_dot_variations(canonical: str):
    """All ways to insert dots between characters of canonical (Gmail forbids
    a dot as the very first/last character or two dots in a row, so we only
    ever toggle a single dot per gap between letters)."""
    n = len(canonical)
    if n <= 1:
        return [canonical]
    variations = []
    for mask in range(2 ** (n - 1)):
        variations.append(build_variation_from_mask(canonical, mask))
    return variations


def is_rate_limited(user_id: int) -> bool:
    now = time.time()
    log = _request_log[user_id]
    while log and now - log[0] > RATE_LIMIT_WINDOW:
        log.popleft()
    if len(log) >= RATE_LIMIT_MAX:
        return True
    log.append(now)
    return False


def result_keyboard(canonical: str, domain: str) -> InlineKeyboardMarkup:
    # callback_data is capped at 64 bytes by Telegram, so we keep it short
    # and rely on context.user_data (set alongside) to hold the full email.
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🎲 Random 20", callback_data="random"),
                InlineKeyboardButton("#️⃣ Count only", callback_data="count"),
            ],
            [
                InlineKeyboardButton("📄 Full list as file", callback_data="file"),
            ],
        ]
    )


async def send_full_list(update_or_query, canonical: str, domain: str, as_file: bool = None):
    """Shared renderer used by /dots, plain text input, and the 'file' button."""
    variations = generate_dot_variations(canonical)
    full_list = [f"{v}@{domain}" for v in variations]
    header = f"Found {len(full_list)} dot variation(s) for {canonical}@{domain}:\n\n"
    body = "\n".join(full_list)
    message = header + f"```\n{body}\n```"

    send_as_file = as_file if as_file is not None else len(message) > 4000

    if send_as_file:
        buf = BytesIO(body.encode("utf-8"))
        buf.name = f"{canonical}_dot_variations.txt"
        await update_or_query.reply_document(
            document=buf, caption=header.strip() + "\n\n@ritsurex"
        )
    else:
        await update_or_query.reply_text(
            message, parse_mode="Markdown", reply_markup=result_keyboard(canonical, domain)
        )


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hi! Send me a Gmail address (e.g. ritsu@gmail.com) and I'll list every "
        "dot-variation of it — Gmail treats them all as the same inbox.\n\n"
        "Send /help to see all commands."
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "*Commands*\n"
        "/dots <email> — list every dot variation\n"
        "/count <email> — just the total number of combinations\n"
        "/random <email> [n] — n random variations (default 20)\n"
        "/tag <email> <label> — build a +tag address, e.g. `+shopping`\n"
        "/about — what this bot does and why it works\n\n"
        f"You can also just paste a Gmail address directly. Usernames longer "
        f"than {MAX_LOCAL_LENGTH} characters get a count instead of a full "
        "list, since the combinations explode.",
        parse_mode="Markdown",
    )


async def about_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Gmail ignores dots in the part of an address before the @, so "
        "ri.tsu@gmail.com and ritsu@gmail.com deliver to the same inbox. "
        "This bot lists those equivalent addresses — handy for setting up "
        "inbox filters or seeing which variant a signup form accepted. It "
        "doesn't store the emails you send it."
    )


async def dots_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /dots ritsu@gmail.com")
        return
    await process_email(update.message, context, context.args[0])


async def count_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /count ritsu@gmail.com")
        return
    result = extract_local_and_domain(context.args[0])
    if not result:
        await update.message.reply_text("That doesn't look like a valid Gmail address.")
        return
    canonical, domain = result
    total = 2 ** (len(canonical) - 1)
    await update.message.reply_text(
        f"'{canonical}@{domain}' has {total:,} possible dot combination(s)."
    )


async def random_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /random ritsu@gmail.com [count]")
        return
    result = extract_local_and_domain(context.args[0])
    if not result:
        await update.message.reply_text("That doesn't look like a valid Gmail address.")
        return
    canonical, domain = result
    n = 20
    if len(context.args) > 1 and context.args[1].isdigit():
        n = max(1, min(int(context.args[1]), 200))
    await send_random_sample(update.message, canonical, domain, n)


async def tag_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /tag ritsu@gmail.com shopping")
        return
    result = extract_local_and_domain(context.args[0])
    if not result:
        await update.message.reply_text("That doesn't look like a valid Gmail address.")
        return
    canonical, domain = result
    tag = TAG_SANITIZE_REGEX.sub("", context.args[1])
    if not tag:
        await update.message.reply_text("Tag must contain letters, numbers, - or _.")
        return
    await update.message.reply_text(
        f"Tagged address: `{canonical}+{tag}@{domain}`\n\n"
        "Mail sent to this still lands in your normal inbox — use it to set "
        "up a filter (e.g. auto-label anything to this address).",
        parse_mode="Markdown",
    )


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

async def process_email(message, context: ContextTypes.DEFAULT_TYPE, text: str):
    if is_rate_limited(message.from_user.id):
        await message.reply_text(
            f"Slow down a bit — max {RATE_LIMIT_MAX} requests per "
            f"{RATE_LIMIT_WINDOW} seconds."
        )
        return

    result = extract_local_and_domain(text)
    if not result:
        await message.reply_text(
            "That doesn't look like a valid Gmail address. Try something like "
            "ritsu@gmail.com."
        )
        return

    canonical, domain = result
    total = 2 ** (len(canonical) - 1)
    context.user_data["last"] = (canonical, domain)

    if len(canonical) > MAX_LOCAL_LENGTH:
        await message.reply_text(
            f"'{canonical}@{domain}' has {len(canonical)} characters, which means "
            f"{total:,} possible dot combinations — too many to list here. "
            "Try /random or /count instead."
        )
        return

    await send_full_list(message, canonical, domain)


async def send_random_sample(message, canonical: str, domain: str, n: int):
    total = 2 ** (len(canonical) - 1)
    if len(canonical) <= 1:
        sample = [canonical]
    else:
        n = min(n, total)
        masks = random.sample(range(total), n)
        sample = [build_variation_from_mask(canonical, mask) for mask in masks]

    full_list = [f"{v}@{domain}" for v in sample]
    body = "\n".join(full_list)
    await message.reply_text(
        f"{len(full_list)} random variation(s) out of {total:,} total for "
        f"{canonical}@{domain}:\n\n```\n{body}\n```",
        parse_mode="Markdown",
    )


async def handle_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await process_email(update.message, context, update.message.text)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    last = context.user_data.get("last")
    if not last:
        await query.message.reply_text("Send me a Gmail address first.")
        return
    canonical, domain = last

    if is_rate_limited(query.from_user.id):
        await query.message.reply_text(
            f"Slow down a bit — max {RATE_LIMIT_MAX} requests per "
            f"{RATE_LIMIT_WINDOW} seconds."
        )
        return

    if query.data == "random":
        await send_random_sample(query.message, canonical, domain, 20)
    elif query.data == "count":
        total = 2 ** (len(canonical) - 1)
        await query.message.reply_text(
            f"'{canonical}@{domain}' has {total:,} possible dot combination(s)."
        )
    elif query.data == "file":
        await send_full_list(query.message, canonical, domain, as_file=True)


# ---------------------------------------------------------------------------
# Health check server (Render web-service port requirement) + entrypoint
# ---------------------------------------------------------------------------

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
        raise RuntimeError("Set the BOT_TOKEN environment variable for your Telegram bot token.")

    threading.Thread(target=run_health_server, daemon=True).start()

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("about", about_cmd))
    app.add_handler(CommandHandler("dots", dots_cmd))
    app.add_handler(CommandHandler("count", count_cmd))
    app.add_handler(CommandHandler("random", random_cmd))
    app.add_handler(CommandHandler("tag", tag_cmd))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_email))

    logger.info("Bot starting (polling mode)...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()