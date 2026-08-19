import asyncio
import os
import random
from collections import defaultdict, deque
from io import BytesIO
from itertools import product
import logging
import time
from typing import Optional, Tuple, List

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Configuration ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
PORT = int(os.environ.get("PORT", 10000))
MAX_LOCAL_LENGTH = 15  # 2^(15-1) = 16,384 combinations ceiling before forcing sampling


# --- Utility Classes & Functions ---

class RateLimiter:
    """Sliding-window per-user rate limiter."""
    def __init__(self, max_requests: int = 8, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window = window_seconds
        self.history = defaultdict(deque)

    def is_limited(self, user_id: int) -> bool:
        now = time.time()
        user_queue = self.history[user_id]
        while user_queue and now - user_queue[0] > self.window:
            user_queue.popleft()
        if len(user_queue) >= self.max_requests:
            return True
        user_queue.append(now)
        return False


limiter = RateLimiter()


def parse_gmail(email: str) -> Optional[Tuple[str, str]]:
    """Validates and extracts canonical local part and domain."""
    email = email.strip().lower().rstrip(".")
    if "@" not in email:
        return None
    
    local, _, domain = email.partition("@")
    if domain not in ("gmail.com", "googlemail.com"):
        return None

    # Gmail strips everything after '+' and ignores dots entirely
    canonical = local.split("+")[0].replace(".", "")
    if not canonical or not canonical.isalnum():
        return None

    return canonical, domain


def generate_variations(canonical: str, sample_size: Optional[int] = None) -> List[str]:
    """Generates all or sample dot permutations using Cartesian product."""
    n = len(canonical)
    if n <= 1:
        return [canonical]

    # Interleave character possibilities: [('r',), ('i', '.i'), ('t', '.t'), ...]
    options = [(c,) if i == 0 else (c, f".{c}") for i, c in enumerate(canonical)]
    total = 1 << (n - 1)

    if sample_size and sample_size < total:
        # Sample random indices to avoid generating full cartesian product
        indices = set(random.sample(range(total), sample_size))
        return [
            "".join(prod) 
            for idx, prod in enumerate(product(*options)) 
            if idx in indices
        ]

    return ["".join(prod) for prod in product(*options)]


def get_action_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎲 20 Random", callback_data="btn_random"),
            InlineKeyboardButton("#️⃣ Total Count", callback_data="btn_count"),
        ],
        [
            InlineKeyboardButton("📄 Export Full List (.txt)", callback_data="btn_file"),
        ],
    ])


async def deliver_results(
    target, 
    canonical: str, 
    domain: str, 
    items: List[str], 
    force_file: bool = False
):
    """Handles formatted text delivery or text document attachment."""
    total_combinations = 1 << (len(canonical) - 1)
    full_addresses = [f"{v}@{domain}" for v in items]
    content = "\n".join(full_addresses)
    
    header = (
        f"📧 *Target:* `{canonical}@{domain}`\n"
        f"🔢 *Displaying:* `{len(items):,}` of `{total_combinations:,}` total variations\n\n"
    )

    if force_file or len(content) > 3500:
        file_buffer = BytesIO(content.encode("utf-8"))
        file_buffer.name = f"{canonical}_gmail_variations.txt"
        await target.reply_document(
            document=file_buffer,
            caption=f"📁 Export generated for `{canonical}@{domain}` ({len(items):,} addresses).",
            parse_mode=ParseMode.MARKDOWN,
        )
    else:
        message = f"{header}```\n{content}\n```"
        await target.reply_text(
            message, 
            parse_mode=ParseMode.MARKDOWN, 
            reply_markup=get_action_keyboard()
        )


# --- Handlers ---

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *Gmail Dot Trick Generator*\n\n"
        "Send any Gmail address directly, or use the commands below:\n"
        "• `/dots <email>` — Generate all dot permutations\n"
        "• `/random <email> [n]` — Get `n` random samples\n"
        "• `/count <email>` — Calculate total permutations\n"
        "• `/tag <email> <label>` — Generate a clean `+tag` alias\n"
        "• `/about` — Technical explanation",
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💡 *How this works*\n\n"
        "Gmail standard routing ignores `.` (dots) in usernames and ignores "
        "any suffix after `+`. All variations resolve directly to the primary inbox.\n\n"
        "Useful for:\n"
        "• Creating distinct platform signups\n"
        "• Organizing automated inbox filters\n"
        "• Tracking third-party data tracking",
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_dots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❗ Usage: `/dots username@gmail.com`", parse_mode=ParseMode.MARKDOWN)
        return
    await route_email_processing(update.message, context, context.args[0])


async def cmd_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❗ Usage: `/count username@gmail.com`", parse_mode=ParseMode.MARKDOWN)
        return
    
    parsed = parse_gmail(context.args[0])
    if not parsed:
        await update.message.reply_text("⚠️ Please provide a valid `@gmail.com` address.")
        return

    canonical, domain = parsed
    total = 1 << (len(canonical) - 1)
    await update.message.reply_text(
        f"📊 `{canonical}@{domain}` has *{total:,}* possible dot combinations.",
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_random(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❗ Usage: `/random username@gmail.com [count]`", parse_mode=ParseMode.MARKDOWN)
        return

    parsed = parse_gmail(context.args[0])
    if not parsed:
        await update.message.reply_text("⚠️ Please provide a valid `@gmail.com` address.")
        return

    canonical, domain = parsed
    count = 20
    if len(context.args) > 1 and context.args[1].isdigit():
        count = max(1, min(int(context.args[1]), 200))

    variations = generate_variations(canonical, sample_size=count)
    await deliver_results(update.message, canonical, domain, variations)


async def cmd_tag(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("❗ Usage: `/tag username@gmail.com label`", parse_mode=ParseMode.MARKDOWN)
        return

    parsed = parse_gmail(context.args[0])
    if not parsed:
        await update.message.reply_text("⚠️ Please provide a valid `@gmail.com` address.")
        return

    canonical, domain = parsed
    clean_tag = "".join(c for c in context.args[1] if c.isalnum() or c in "-_")
    if not clean_tag:
        await update.message.reply_text("⚠️ Tags can only contain alphanumeric characters, hyphens, and underscores.")
        return

    await update.message.reply_text(
        f"🏷️ *Tagged Alias:*\n`{canonical}+{clean_tag}@{domain}`",
        parse_mode=ParseMode.MARKDOWN,
    )


async def route_email_processing(message, context: ContextTypes.DEFAULT_TYPE, raw_text: str):
    if limiter.is_limited(message.from_user.id):
        await message.reply_text("⏳ Rate limit exceeded. Please wait a minute before making more requests.")
        return

    parsed = parse_gmail(raw_text)
    if not parsed:
        await message.reply_text("⚠️ That doesn't look like a valid `@gmail.com` address.")
        return

    canonical, domain = parsed
    context.user_data["active_email"] = (canonical, domain)
    length = len(canonical)
    total = 1 << (length - 1)

    if length > MAX_LOCAL_LENGTH:
        await message.reply_text(
            f"ℹ️ `{canonical}@{domain}` contains {length} characters (*{total:,}* combinations).\n"
            "Listing all variations exceeds payload limits. Use the buttons below:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_action_keyboard(),
        )
        return

    variations = generate_variations(canonical)
    await deliver_results(message, canonical, domain, variations)


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await route_email_processing(update.message, context, update.message.text)


async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    cached = context.user_data.get("active_email")
    if not cached:
        await query.message.reply_text("⚠️ Session expired. Please send the Gmail address again.")
        return

    canonical, domain = cached
    action = query.data

    if action == "btn_random":
        variations = generate_variations(canonical, sample_size=20)
        await deliver_results(query.message, canonical, domain, variations)
    elif action == "btn_count":
        total = 1 << (len(canonical) - 1)
        await query.message.reply_text(
            f"📊 `{canonical}@{domain}` produces *{total:,}* unique aliases.",
            parse_mode=ParseMode.MARKDOWN,
        )
    elif action == "btn_file":
        variations = generate_variations(canonical)
        await deliver_results(query.message, canonical, domain, variations, force_file=True)


# --- Native Async Health Check Server ---

async def handle_health_check(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    await reader.read(1024)
    response = b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 2\r\n\r\nOK"
    writer.write(response)
    await writer.drain()
    writer.close()
    await writer.wait_closed()


async def start_health_server(port: int):
    server = await asyncio.start_server(handle_health_check, "0.0.0.0", port)
    logger.info(f"Health check endpoint active on port {port}")
    return server


# --- App Bootstrapper ---

def main():
    if not BOT_TOKEN:
        raise RuntimeError("CRITICAL: Set the 'BOT_TOKEN' environment variable.")

    app = Application.builder().token(BOT_TOKEN).build()

    # Register Handlers
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_start))
    app.add_handler(CommandHandler("about", cmd_about))
    app.add_handler(CommandHandler("dots", cmd_dots))
    app.add_handler(CommandHandler("count", cmd_count))
    app.add_handler(CommandHandler("random", cmd_random))
    app.add_handler(CommandHandler("tag", cmd_tag))
    app.add_handler(CallbackQueryHandler(handle_callback_query))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

    # Initialize async health server on the event loop before polling starts
    async def post_init(application: Application):
        await start_health_server(PORT)

    app.post_init = post_init

    logger.info("Bot initialized. Starting polling...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()