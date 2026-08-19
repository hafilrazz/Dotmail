<<<<<<< Updated upstream
import asyncio
import os
import random
from collections import defaultdict, deque
from io import BytesIO
from itertools import product
import logging
import time
from typing import Optional, Tuple, List

=======
from __future__ import annotations

import asyncio
import logging
import os
import random
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from io import BytesIO
from itertools import product
from typing import AsyncIterator, Final

>>>>>>> Stashed changes
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

<<<<<<< Updated upstream
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
=======
# ---------------------------------------------------------------------------
# Configuration & Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    format="%(asctime)s | %(levelname)-7s | %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("GmailDotBot")

BOT_TOKEN: Final[str] = os.environ.get("BOT_TOKEN", "")
PORT: Final[int] = int(os.environ.get("PORT", 10000))
MAX_INLINE_LENGTH: Final[int] = 14  # Max local-part length for inline output


# ---------------------------------------------------------------------------
# Domain Models & Core Engine
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class GmailAddress:
    canonical: str
    domain: str

    @property
    def full_address(self) -> str:
        return f"{self.canonical}@{self.domain}"

    @property
    def total_combinations(self) -> int:
        return 1 << (len(self.canonical) - 1)

    @classmethod
    def parse(cls, raw: str) -> GmailAddress | None:
        """Parses, normalizes, and validates a Gmail address."""
        raw = raw.strip().lower().rstrip(".")
        if "@" not in raw:
            return None

        local, _, domain = raw.partition("@")
        if domain not in ("gmail.com", "googlemail.com"):
            return None

        canonical = local.split("+")[0].replace(".", "")
        if not canonical or not canonical.isalnum():
            return None

        return cls(canonical=canonical, domain=domain)

    def generate_variations(self, sample_size: int | None = None) -> list[str]:
        """Generates dot variations via cartesian product."""
        n = len(self.canonical)
        if n <= 1:
            return [self.full_address]

        options = [(c,) if i == 0 else (c, f".{c}") for i, c in enumerate(self.canonical)]
        total = self.total_combinations

        if sample_size and sample_size < total:
            chosen_indices = set(random.sample(range(total), sample_size))
            return [
                f"{''.join(p)}@{self.domain}"
                for idx, p in enumerate(product(*options))
                if idx in chosen_indices
            ]

        return [f"{''.join(p)}@{self.domain}" for p in product(*options)]


# ---------------------------------------------------------------------------
# Rate Limiter
# ---------------------------------------------------------------------------

class UserRateLimiter:
    """Sliding-window rate limiter per Telegram user."""

    def __init__(self, max_hits: int = 6, window_seconds: int = 60) -> None:
        self.max_hits = max_hits
        self.window = window_seconds
        self.history: defaultdict[int, deque[float]] = defaultdict(deque)

    def is_limited(self, user_id: int) -> bool:
        now = time.monotonic()
        q = self.history[user_id]
        while q and now - q[0] > self.window:
            q.popleft()
        if len(q) >= self.max_hits:
            return True
        q.append(now)
        return False


rate_limiter = UserRateLimiter()
>>>>>>> Stashed changes

    # Interleave character possibilities: [('r',), ('i', '.i'), ('t', '.t'), ...]
    options = [(c,) if i == 0 else (c, f".{c}") for i, c in enumerate(canonical)]
    total = 1 << (n - 1)

<<<<<<< Updated upstream
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
=======
# ---------------------------------------------------------------------------
# UI Components & Keyboards
# ---------------------------------------------------------------------------

def main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎲 20 Random", callback_data="act_random"),
            InlineKeyboardButton("🔢 Total Count", callback_data="act_count"),
        ],
        [
            InlineKeyboardButton("📄 Export to .txt File", callback_data="act_file"),
>>>>>>> Stashed changes
        ],
    ])


<<<<<<< Updated upstream
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
=======
async def reply_with_results(
    target: Update | ContextTypes.DEFAULT_TYPE,
    email: GmailAddress,
    items: list[str],
    as_document: bool = False,
) -> None:
    """Delivers output cleanly as formatted Markdown or a text document."""
    total = email.total_combinations
    body = "\n".join(items)

    if as_document or len(body) > 3500:
        buffer = BytesIO(body.encode("utf-8"))
        buffer.name = f"{email.canonical}_variations.txt"
        await target.reply_document(
            document=buffer,
            caption=(
                f"📂 *Export Complete*\n"
                f"• Target: `{email.full_address}`\n"
                f"• Variations: `{len(items):,}` of `{total:,}`"
            ),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    text = (
        f"🎯 *Target:* `{email.full_address}`\n"
        f"📊 *Showing:* `{len(items):,}` / `{total:,}` variations\n\n"
        f"```\n{body}\n```"
    )
    await target.reply_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_keyboard(),
    )


# ---------------------------------------------------------------------------
# Command & Query Handlers
# ---------------------------------------------------------------------------

async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = (
        "✨ *Gmail Dot Variation Assistant*\n\n"
        "Send me any Gmail address to generate all equivalent inbox variations.\n\n"
        "*Quick Commands:*\n"
        "• `/dots <email>` — Get all dot combinations\n"
        "• `/random <email> [n]` — Get `n` random samples\n"
        "• `/count <email>` — Count total combinations\n"
        "• `/tag <email> <label>` — Generate clean `+tag` alias\n"
        "• `/about` — Why this works"
>>>>>>> Stashed changes
    )
    await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)


<<<<<<< Updated upstream
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
=======
async def handle_about(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "💡 *How Gmail Routing Works*\n\n"
        "Gmail ignores two key things in usernames:\n"
        "1. **Dots (`.`):** `john.doe@gmail.com` and `j.o.h.n.d.o.e@gmail.com` route to `johndoe@gmail.com`.\n"
        "2. **Plus-Tags (`+`):** Anything after `+` is ignored for routing.\n\n"
        "Great for filtering subscriptions, debugging signups, and segmenting newsletters."
>>>>>>> Stashed changes
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


<<<<<<< Updated upstream
async def cmd_dots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❗ Usage: `/dots username@gmail.com`", parse_mode=ParseMode.MARKDOWN)
        return
    await route_email_processing(update.message, context, context.args[0])
=======
async def handle_count(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Usage: `/count user@gmail.com`", parse_mode=ParseMode.MARKDOWN)
        return
>>>>>>> Stashed changes

    email = GmailAddress.parse(context.args[0])
    if not email:
        await update.message.reply_text("⚠️ Invalid Gmail address provided.")
        return

<<<<<<< Updated upstream
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
=======
    await update.message.reply_text(
        f"🔢 `{email.full_address}` has *{email.total_combinations:,}* possible dot combinations.",
>>>>>>> Stashed changes
        parse_mode=ParseMode.MARKDOWN,
    )


<<<<<<< Updated upstream
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
=======
async def handle_random(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Usage: `/random user@gmail.com [count]`", parse_mode=ParseMode.MARKDOWN)
        return

    email = GmailAddress.parse(context.args[0])
    if not email:
        await update.message.reply_text("⚠️ Invalid Gmail address provided.")
        return

    count = 20
    if len(context.args) > 1 and context.args[1].isdigit():
        count = max(1, min(int(context.args[1]), 250))

    results = email.generate_variations(sample_size=count)
    await reply_with_results(update.message, email, results)


async def handle_tag(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) < 2:
        await update.message.reply_text("Usage: `/tag user@gmail.com label`", parse_mode=ParseMode.MARKDOWN)
        return

    email = GmailAddress.parse(context.args[0])
    if not email:
        await update.message.reply_text("⚠️ Invalid Gmail address provided.")
        return

    tag = "".join(c for c in context.args[1] if c.isalnum() or c in "-_")
    if not tag:
        await update.message.reply_text("⚠️ Tag must contain alphanumeric characters, hyphens, or underscores.")
        return

    await update.message.reply_text(
        f"🏷️ *Tagged Address:*\n`{email.canonical}+{tag}@{email.domain}`",
>>>>>>> Stashed changes
        parse_mode=ParseMode.MARKDOWN,
    )


<<<<<<< Updated upstream
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
=======
async def process_email_flow(message, context: ContextTypes.DEFAULT_TYPE, raw_input: str) -> None:
    if rate_limiter.is_limited(message.from_user.id):
        await message.reply_text("⏳ Please slow down. Rate limit: 6 requests per minute.")
        return

    email = GmailAddress.parse(raw_input)
    if not email:
        await message.reply_text("⚠️ Please send a valid `@gmail.com` or `@googlemail.com` address.")
        return

    context.user_data["active_email"] = email

    # Handle combinatoric explosions cleanly
    if len(email.canonical) > MAX_INLINE_LENGTH:
        await message.reply_text(
            f"ℹ️ `{email.full_address}` produces *{email.total_combinations:,}* combinations.\n"
            "Listing all inline would exceed Telegram message size limits. Choose an action:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_keyboard(),
        )
        return

    results = email.generate_variations()
    await reply_with_results(message, email, results)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message and update.message.text:
        await process_email_flow(update.message, context, update.message.text)


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    email: GmailAddress | None = context.user_data.get("active_email")
    if not email:
        await query.message.reply_text("⚠️ Session expired. Please send your address again.")
        return

    match query.data:
        case "act_random":
            results = email.generate_variations(sample_size=20)
            await reply_with_results(query.message, email, results)
        case "act_count":
            await query.message.reply_text(
                f"🔢 `{email.full_address}` has *{email.total_combinations:,}* possible dot combinations.",
                parse_mode=ParseMode.MARKDOWN,
            )
        case "act_file":
            results = email.generate_variations()
            await reply_with_results(query.message, email, results, as_document=True)


# ---------------------------------------------------------------------------
# Asynchronous Health Check Server (Render/PaaS Ready)
# ---------------------------------------------------------------------------

async def run_health_server(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    await reader.read(512)
>>>>>>> Stashed changes
    response = b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 2\r\n\r\nOK"
    writer.write(response)
    await writer.drain()
    writer.close()
    await writer.wait_closed()


<<<<<<< Updated upstream
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
=======
# ---------------------------------------------------------------------------
# Application Lifecycle
# ---------------------------------------------------------------------------

def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("Environment variable 'BOT_TOKEN' is required.")

    app = Application.builder().token(BOT_TOKEN).build()

    # Route registrations
    app.add_handler(CommandHandler(["start", "help"], handle_start))
    app.add_handler(CommandHandler("about", handle_about))
    app.add_handler(CommandHandler("dots", lambda u, c: process_email_flow(u.message, c, c.args[0]) if c.args else u.message.reply_text("Usage: `/dots user@gmail.com`", parse_mode=ParseMode.MARKDOWN)))
    app.add_handler(CommandHandler("count", handle_count))
    app.add_handler(CommandHandler("random", handle_random))
    app.add_handler(CommandHandler("tag", handle_tag))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    async def on_startup(application: Application) -> None:
        await asyncio.start_server(run_health_server, "0.0.0.0", PORT)
        logger.info(f"Health check probe active on port {PORT}")

    app.post_init = on_startup

    logger.info("Bot starting in polling mode...")
>>>>>>> Stashed changes
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()