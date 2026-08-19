<<<<<<< Updated upstream
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
=======
import os
import re
import time
>>>>>>> Stashed changes
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

<<<<<<< Updated upstream
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
=======
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
>>>>>>> Stashed changes
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
<<<<<<< Updated upstream

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
=======
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


>>>>>>> Stashed changes
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
<<<<<<< Updated upstream
        await update.message.reply_text("❗ Usage: `/random username@gmail.com [count]`", parse_mode=ParseMode.MARKDOWN)
=======
async def cmd_random(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("❗ Usage: `/random user@gmail.com [count]`", parse_mode=ParseMode.MARKDOWN)
=======
        await update.message.reply_text("Usage: /dots ritsu@gmail.com")
>>>>>>> Stashed changes
        return
    await process_email(update.message, context, context.args[0])

<<<<<<< Updated upstream
    email = GmailAddress.parse(context.args[0])
    if not email:
        await update.message.reply_text("⚠️ Invalid Gmail address.")
>>>>>>> Stashed changes
=======

async def count_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /count ritsu@gmail.com")
>>>>>>> Stashed changes
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

<<<<<<< Updated upstream
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
=======

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
>>>>>>> Stashed changes
    if not tag:
        await update.message.reply_text("Tag must contain letters, numbers, - or _.")
        return
    await update.message.reply_text(
<<<<<<< Updated upstream
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
=======
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
>>>>>>> Stashed changes
        return
    canonical, domain = last

<<<<<<< Updated upstream
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
=======
    if is_rate_limited(query.from_user.id):
        await query.message.reply_text(
            f"Slow down a bit — max {RATE_LIMIT_MAX} requests per "
            f"{RATE_LIMIT_WINDOW} seconds."
>>>>>>> Stashed changes
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

<<<<<<< Updated upstream
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
=======
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

    threading.Thread(target=run_health_server, daemon=True).start()
>>>>>>> Stashed changes

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

<<<<<<< Updated upstream
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
=======
    logger.info("Bot starting (polling mode)...")
>>>>>>> Stashed changes
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()