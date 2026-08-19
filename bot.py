<<<<<<< Updated upstream
<<<<<<< Updated upstream
=======
from __future__ import annotations

>>>>>>> Stashed changes
import asyncio
import logging
import os
import random
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from io import BytesIO
from itertools import product
from typing import Final

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
<<<<<<< Updated upstream
=======
# ---------------------------------------------------------------------------
# Logging & Configuration
# ---------------------------------------------------------------------------

>>>>>>> Stashed changes
logging.basicConfig(
    format="%(asctime)s | %(levelname)-7s | %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("GmailDotBot")

BOT_TOKEN: Final[str] = os.environ.get("BOT_TOKEN", "")
PORT: Final[int] = int(os.environ.get("PORT", 10000))
MAX_INLINE_LENGTH: Final[int] = 14  # Max chars before prompting sampling/export


# ---------------------------------------------------------------------------
# Domain Logic
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class GmailAddress:
    canonical: str
    domain: str

    @property
    def full(self) -> str:
        return f"{self.canonical}@{self.domain}"

    @property
    def total_combinations(self) -> int:
        return 1 << (len(self.canonical) - 1)

    @classmethod
    def parse(cls, raw: str) -> GmailAddress | None:
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
        n = len(self.canonical)
        if n <= 1:
            return [self.full]

        options = [(c,) if i == 0 else (c, f".{c}") for i, c in enumerate(self.canonical)]
        total = self.total_combinations

        if sample_size and sample_size < total:
            chosen = set(random.sample(range(total), sample_size))
            return [
                f"{''.join(p)}@{self.domain}"
                for idx, p in enumerate(product(*options))
                if idx in chosen
            ]

        return [f"{''.join(p)}@{self.domain}" for p in product(*options)]


class RateLimiter:
    """Sliding-window per-user rate limiter."""

    def __init__(self, max_hits: int = 8, window_seconds: int = 60) -> None:
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


limiter = RateLimiter()


# ---------------------------------------------------------------------------
# UI Helpers & View
# ---------------------------------------------------------------------------

<<<<<<< Updated upstream
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
=======
def action_keyboard() -> InlineKeyboardMarkup:
>>>>>>> Stashed changes
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎲 20 Random", callback_data="act_random"),
            InlineKeyboardButton("🔢 Total Count", callback_data="act_count"),
        ],
        [
<<<<<<< Updated upstream
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
=======
            InlineKeyboardButton("📄 Export Full List (.txt)", callback_data="act_file"),
>>>>>>> Stashed changes
        ],
    ])


<<<<<<< Updated upstream
async def deliver_results(
    target,
    email: GmailAddress,
    items: list[str],
    as_file: bool = False,
) -> None:
    body = "\n".join(items)

    if as_file or len(body) > 3500:
        buf = BytesIO(body.encode("utf-8"))
        buf.name = f"{email.canonical}_variations.txt"
        await target.reply_document(
            document=buf,
            caption=(
                f"📂 *Export Complete*\n"
                f"• Address: `{email.full}`\n"
                f"• Output: `{len(items):,}` of `{email.total_combinations:,}` variations"
            ),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    text = (
        f"🎯 *Target:* `{email.full}`\n"
        f"📊 *Showing:* `{len(items):,}` / `{email.total_combinations:,}` variations\n\n"
        f"```\n{body}\n```"
    )
    await target.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=action_keyboard())


# ---------------------------------------------------------------------------
# Bot Handlers
# ---------------------------------------------------------------------------

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "✨ *Gmail Dot Generator Bot*\n\n"
        "Send any Gmail address to get its dot permutations.\n\n"
        "*Commands:*\n"
        "• `/dots <email>` — Generate dot combinations\n"
        "• `/random <email> [n]` — Get random samples (default 20)\n"
        "• `/count <email>` — Get total permutations count\n"
        "• `/tag <email> <label>` — Generate a `+tag` alias\n"
        "• `/about` — How Gmail routing works"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def cmd_about(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "💡 *How Gmail Routing Works*\n\n"
        "Gmail ignores two components in usernames:\n"
        "1. **Dots (`.`):** `j.o.h.n@gmail.com` delivers to `john@gmail.com`.\n"
        "2. **Plus signs (`+`):** `john+news@gmail.com` delivers to `john@gmail.com`.\n\n"
        "Use these variants to filter incoming mail or create distinct platform logins."
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def cmd_count(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("❗ Usage: `/count user@gmail.com`", parse_mode=ParseMode.MARKDOWN)
        return

    email = GmailAddress.parse(context.args[0])
    if not email:
        await update.message.reply_text("⚠️ Invalid Gmail address.")
        return

    await update.message.reply_text(
        f"🔢 `{email.full}` has *{email.total_combinations:,}* possible dot combinations.",
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


<<<<<<< Updated upstream
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
=======
async def cmd_random(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("❗ Usage: `/random user@gmail.com [count]`", parse_mode=ParseMode.MARKDOWN)
        return

    email = GmailAddress.parse(context.args[0])
    if not email:
        await update.message.reply_text("⚠️ Invalid Gmail address.")
>>>>>>> Stashed changes
        return

    count = 20
    if len(context.args) > 1 and context.args[1].isdigit():
        count = max(1, min(int(context.args[1]), 250))

    results = email.generate_variations(sample_size=count)
    await deliver_results(update.message, email, results)


async def cmd_tag(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) < 2:
        await update.message.reply_text("❗ Usage: `/tag user@gmail.com label`", parse_mode=ParseMode.MARKDOWN)
        return

    email = GmailAddress.parse(context.args[0])
    if not email:
        await update.message.reply_text("⚠️ Invalid Gmail address.")
        return

    tag = "".join(c for c in context.args[1] if c.isalnum() or c in "-_")
    if not tag:
        await update.message.reply_text("⚠️ Tags can only contain alphanumeric characters, hyphens, or underscores.")
        return

    await update.message.reply_text(
<<<<<<< Updated upstream
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
=======
        f"🏷️ *Tagged Address:*\n`{email.canonical}+{tag}@{email.domain}`",
>>>>>>> Stashed changes
        parse_mode=ParseMode.MARKDOWN,
    )


<<<<<<< Updated upstream
<<<<<<< Updated upstream
async def route_email_processing(message, context: ContextTypes.DEFAULT_TYPE, raw_text: str):
=======
async def handle_address_flow(message, context: ContextTypes.DEFAULT_TYPE, raw_text: str) -> None:
>>>>>>> Stashed changes
    if limiter.is_limited(message.from_user.id):
        await message.reply_text("⏳ Rate limit exceeded (8 requests / min). Please wait a moment.")
        return

    email = GmailAddress.parse(raw_text)
    if not email:
        await message.reply_text("⚠️ Please send a valid `@gmail.com` or `@googlemail.com` address.")
        return

    context.user_data["active_email"] = email

    if len(email.canonical) > MAX_INLINE_LENGTH:
        await message.reply_text(
            f"ℹ️ `{email.full}` has *{email.total_combinations:,}* combinations.\n"
            "That exceeds inline chat limits. Choose an option:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=action_keyboard(),
        )
        return

    results = email.generate_variations()
    await deliver_results(message, email, results)


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
            await deliver_results(query.message, email, results)
        case "act_count":
            await query.message.reply_text(
                f"🔢 `{email.full}` produces *{email.total_combinations:,}* unique variations.",
                parse_mode=ParseMode.MARKDOWN,
            )
        case "act_file":
            results = email.generate_variations()
            await deliver_results(query.message, email, results, as_file=True)


# ---------------------------------------------------------------------------
# Health Server (Native Async)
# ---------------------------------------------------------------------------

<<<<<<< Updated upstream
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
=======
async def health_check_handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    await reader.read(512)
    writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 2\r\n\r\nOK")
>>>>>>> Stashed changes
    await writer.drain()
    writer.close()
    await writer.wait_closed()


<<<<<<< Updated upstream
<<<<<<< Updated upstream
async def start_health_server(port: int):
    server = await asyncio.start_server(handle_health_check, "0.0.0.0", port)
    logger.info(f"Health check endpoint active on port {port}")
    return server
=======
# ---------------------------------------------------------------------------
# Application Entrypoint
# ---------------------------------------------------------------------------
>>>>>>> Stashed changes

def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("Environment variable BOT_TOKEN is required.")

    app = Application.builder().token(BOT_TOKEN).build()

    # Handlers
    app.add_handler(CommandHandler(["start", "help"], cmd_start))
    app.add_handler(CommandHandler("about", cmd_about))
    app.add_handler(CommandHandler("dots", lambda u, c: handle_address_flow(u.message, c, c.args[0]) if c.args else u.message.reply_text("❗ Usage: `/dots user@gmail.com`", parse_mode=ParseMode.MARKDOWN)))
    app.add_handler(CommandHandler("count", cmd_count))
    app.add_handler(CommandHandler("random", cmd_random))
    app.add_handler(CommandHandler("tag", cmd_tag))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: handle_address_flow(u.message, c, u.message.text)))

    # Start non-blocking health server directly on the main event loop
    async def post_init(_: Application) -> None:
        await asyncio.start_server(health_check_handler, "0.0.0.0", PORT)
        logger.info("Health probe listening on port %d", PORT)

    app.post_init = post_init

<<<<<<< Updated upstream
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
=======
    logger.info("Bot starting in polling mode...")
>>>>>>> Stashed changes
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()