from typing import Literal, Tuple, Deque, Dict, Any, Callable, Coroutine, Union, Optional
from collections import deque, defaultdict
import os
import re
import time
import random
import logging
import threading
from io import BytesIO
from http.server import BaseHTTPRequestHandler, HTTPServer
import functools  # For lru_cache

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# --- Configuration & Constants ---
# Using a dedicated class for configuration
class Config:
    """Centralized configuration for the bot."""
    BOT_TOKEN: str = os.environ.get("BOT_TOKEN", "") # Ensure BOT_TOKEN is retrieved safely
    PORT: int = int(os.environ.get("PORT", 10000))

    MAX_LOCAL_LENGTH: int = 15  # Max local part length for full listing
    RATE_LIMIT_MAX: int = 8
    RATE_LIMIT_WINDOW: int = 60  # seconds

    # Callback data constants for inline keyboard buttons
    CALLBACK_RANDOM: str = "random"
    CALLBACK_COUNT: str = "count"
    CALLBACK_FILE: str = "file"

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Type Aliases for Clarity ---
EmailParts = Tuple[str, str]  # (canonical_local_part, domain)
TelegramUpdate = Update
ApplicationContext = ContextTypes.DEFAULT_TYPE
# Generic type for methods that can reply to a message or query's message
ReplyTarget = Union[TelegramUpdate.Message, TelegramUpdate.CallbackQuery]

# --- Rate Limiting ---
class RateLimiter:
    """Manages per-user rate limiting."""
    def __init__(self, max_requests: int, window_seconds: int):
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._request_log: Dict[int, Deque[float]] = defaultdict(deque)

    def is_rate_limited(self, user_id: int) -> bool:
        """
        Checks if a user is rate-limited. If not, records the current request.
        """
        now = time.time()
        log = self._request_log[user_id]
        
        # Remove old requests from the log
        while log and now - log[0] > self._window_seconds:
            log.popleft()
        
        # Check if current number of requests exceeds the limit
        if len(log) >= self._max_requests:
            return True
        
        # Add current request timestamp
        log.append(now)
        return False

# Instantiate the rate limiter globally
rate_limiter = RateLimiter(Config.RATE_LIMIT_MAX, Config.RATE_LIMIT_WINDOW)

# --- Core Logic ---

def extract_local_and_domain(email: str) -> Optional[EmailParts]:
    """
    Extracts the canonical local part and domain for a Gmail address.
    Returns (canonical_local_part, domain) or None if not a plausible Gmail address.
    """
    email_cleaned = email.strip().lower()
    if "@" not in email_cleaned:
        return None

    # Use rpartition to safely split only on the last '@'
    local_part_raw, _, domain_raw = email_cleaned.rpartition("@")
    
    # Ensure domain doesn't end with a dot, for robustness
    domain = domain_raw.removesuffix(".") 

    if domain not in ("gmail.com", "googlemail.com"):
        return None

    # Gmail ignores everything after a "+" and ignores dots entirely.
    local_part_no_plus = local_part_raw.split("+")[0]
    canonical = local_part_no_plus.replace(".", "").removesuffix(".") # Remove trailing dots after replacements

    if not canonical or not canonical.isalnum():
        return None

    return canonical, domain

@functools.lru_cache(maxsize=128)  # Cache results for common canonical parts
def generate_dot_variations(canonical: str) -> list[str]:
    """
    Generates all possible dot variations for a canonical Gmail local part.
    Gmail allows dots anywhere except the very beginning, end, or two consecutive.
    This function generates variations by inserting dots in the *gaps* between characters.
    """
    n = len(canonical)
    if n <= 1:
        return [canonical]

    variations = []
    # A bitmask of length (n - 1) determines dot placement.
    # Each bit corresponds to a gap between two characters.
    for mask in range(2 ** (n - 1)):
        chars: list[str] = [canonical[0]]
        for i in range(1, n):
            # If the i-th bit (from right, corresponding to (i-1)-th gap) is set
            if mask & (1 << (i - 1)):
                chars.append(".")
            chars.append(canonical[i])
        variations.append("".join(chars))
    return variations

# --- Telegram Bot UI Helpers ---

def get_result_keyboard() -> InlineKeyboardMarkup:
    """
    Returns an InlineKeyboardMarkup for action selection on email variations.
    callback_data is kept short to comply with Telegram's 64-byte limit.
    """
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🎲 Random 20", callback_data=Config.CALLBACK_RANDOM),
                InlineKeyboardButton("#️⃣ Count only", callback_data=Config.CALLBACK_COUNT),
            ],
            [
                InlineKeyboardButton("📄 Full list as file", callback_data=Config.CALLBACK_FILE),
            ],
        ]
    )

async def _send_response(
    reply_target: ReplyTarget,
    text: Optional[str] = None,
    document_data: Optional[BytesIO] = None,
    document_filename: Optional[str] = None,
    caption: Optional[str] = None,
    parse_mode: Optional[str] = None,
    reply_markup: Optional[InlineKeyboardMarkup] = None
) -> None:
    """
    Helper to send a message as text or as a file, handling whether the target
    is a Message or a CallbackQuery.
    """
    # Determine the actual object to call reply methods on
    message_obj = reply_target.message if hasattr(reply_target, 'message') else reply_target # type: ignore

    if document_data and document_filename:
        await message_obj.reply_document(
            document=document_data,
            filename=document_filename,
            caption=caption,
            parse_mode=parse_mode
        )
    elif text:
        await message_obj.reply_text(
            text,
            parse_mode=parse_mode,
            reply_markup=reply_markup
        )
    else:
        logger.warning(f"Attempted to send empty response to {reply_target}")


async def send_full_list(
    reply_target: ReplyTarget,
    canonical: str,
    domain: str,
    as_file: Optional[bool] = None
) -> None:
    """
    Generates and sends the full list of dot variations, either as text or a file.
    """
    variations = generate_dot_variations(canonical)
    full_list = [f"{v}@{domain}" for v in variations]
    header = f"Found {len(full_list)} dot variation(s) for `{canonical}@{domain}`:"
    body = "\n".join(full_list)

    message_text = f"{header}\n\n```\n{body}\n```"
    send_as_file = as_file if as_file is not None else len(message_text) > 4000

    if send_as_file:
        buf = BytesIO(body.encode("utf-8"))
        buf.name = f"{canonical}_dot_variations.txt"
        await _send_response(
            reply_target,
            document_data=buf,
            document_filename=buf.name,
            caption=f"{header.strip()}\n\n@ritsurex"
        )
    else:
        await _send_response(
            reply_target,
            text=message_text,
            parse_mode="Markdown",
            reply_markup=get_result_keyboard()
        )


async def send_random_sample(
    reply_target: ReplyTarget,
    canonical: str,
    domain: str,
    n: int
) -> None:
    """Sends a random sample of dot variations."""
    total = 2 ** (len(canonical) - 1)
    
    if len(canonical) <= 1:
        sample_variations = [canonical]
    else:
        n = min(n, total)  # Ensure we don't ask for more samples than available
        masks = random.sample(range(total), n)
        sample_variations = []
        for mask in masks:
            chars = [canonical[0]]
            for i in range(1, len(canonical)):
                if mask & (1 << (i - 1)):
                    chars.append(".")
                chars.append(canonical[i])
            sample_variations.append("".join(chars))

    full_list = [f"{v}@{domain}" for v in sample_variations]
    body = "\n".join(full_list)
    
    header = (
        f"{len(full_list)} random variation(s) out of {total:,} total for "
        f"`{canonical}@{domain}`:"
    )
    # Random sample is usually short enough for text message
    await _send_response(
        reply_target,
        text=f"{header}\n\n```\n{body}\n```",
        parse_mode="Markdown"
    )


async def process_email_request(
    reply_target: ReplyTarget,
    context: ApplicationContext,
    email_text: str,
    action: Literal["full", "count", "random", "tag"] = "full",
    random_count: int = 20,
    tag_label: Optional[str] = None
) -> None:
    """
    Centralized function to process an email request, handling rate limiting,
    email parsing, and dispatching to appropriate send functions.
    """
    user_id = reply_target.from_user.id # type: ignore

    if rate_limiter.is_rate_limited(user_id):
        await _send_response(
            reply_target,
            text=f"Slow down a bit — max {Config.RATE_LIMIT_MAX} requests per "
                 f"{Config.RATE_LIMIT_WINDOW} seconds."
        )
        return

    result = extract_local_and_domain(email_text)
    if not result:
        await _send_response(
            reply_target,
            text="That doesn't look like a valid Gmail address. Try something like "
                 "ritsu@gmail.com."
        )
        return

    canonical, domain = result
    total_combinations = 2 ** (len(canonical) - 1)
    context.user_data["last"] = (canonical, domain)  # Store for button handlers

    # Handle commands based on 'action'
    if action == "count":
        await _send_response(
            reply_target,
            text=f"`{canonical}@{domain}` has {total_combinations:,} possible dot combination(s).",
            parse_mode="Markdown"
        )
        return
    elif action == "tag":
        if not tag_label:
            logger.warning("Tag action requested without a tag_label.")
            return # Should not happen if tag_cmd is called correctly

        cleaned_tag = re.sub(r"[^A-Za-z0-9_-]", "", tag_label)
        if not cleaned_tag:
            await _send_response(
                reply_target,
                text="Tag must contain letters, numbers, - or _."
            )
            return

        await _send_response(
            reply_target,
            text=f"Tagged address: `{canonical}+{cleaned_tag}@{domain}`\n\n"
                 "Mail sent to this still lands in your normal inbox — use it to set "
                 "up a filter (e.g. auto-label anything to this address).",
            parse_mode="Markdown",
        )
        return
    
    # Default to full list or random if specific action not handled above
    if len(canonical) > Config.MAX_LOCAL_LENGTH:
        await _send_response(
            reply_target,
            text=f"`{canonical}@{domain}` has {len(canonical)} characters, which means "
                 f"{total_combinations:,} possible dot combinations — too many to list here. "
                 "Try /random or /count instead.",
            parse_mode="Markdown"
        )
        return

    if action == "random":
        await send_random_sample(reply_target, canonical, domain, random_count)
    else:  # action == "full"
        await send_full_list(reply_target, canonical, domain)


# --- Telegram Command Handlers ---

async def start_command(update: TelegramUpdate, context: ApplicationContext) -> None:
    """Handles the /start command."""
    await update.message.reply_text(
        "Hi! Send me a Gmail address (e.g. `ritsu@gmail.com`) and I'll list every "
        "dot-variation of it — Gmail treats them all as the same inbox.\n\n"
        "Send /help to see all commands.",
        parse_mode="Markdown"
    )

async def help_command(update: TelegramUpdate, context: ApplicationContext) -> None:
    """Handles the /help command."""
    await update.message.reply_text(
        "*Commands*\n"
        "`/dots <email>` — list every dot variation\n"
        "`/count <email>` — just the total number of combinations\n"
        "`/random <email> [n]` — n random variations (default 20)\n"
        "`/tag <email> <label>` — build a +tag address, e.g. `+shopping`\n"
        "`/about` — what this bot does and why it works\n\n"
        "You can also just paste a Gmail address directly. Usernames longer "
        f"than {Config.MAX_LOCAL_LENGTH} characters get a count instead of a full "
        "list, since the combinations explode.",
        parse_mode="Markdown",
    )

async def about_command(update: TelegramUpdate, context: ApplicationContext) -> None:
    """Handles the /about command."""
    await update.message.reply_text(
        "Gmail ignores dots in the part of an address before the @, so "
        "ri.tsu@gmail.com and ritsu@gmail.com deliver to the same inbox. "
        "This bot lists those equivalent addresses — handy for setting up "
        "inbox filters or seeing which variant a signup form accepted. It "
        "doesn't store the emails you send it."
    )

async def dots_command(update: TelegramUpdate, context: ApplicationContext) -> None:
    """Handles the /dots command."""
    if not context.args:
        await update.message.reply_text("Usage: `/dots ritsu@gmail.com`", parse_mode="Markdown")
        return
    await process_email_request(update.message, context, context.args[0], action="full")

async def count_command(update: TelegramUpdate, context: ApplicationContext) -> None:
    """Handles the /count command."""
    if not context.args:
        await update.message.reply_text("Usage: `/count ritsu@gmail.com`", parse_mode="Markdown")
        return
    await process_email_request(update.message, context, context.args[0], action="count")

async def random_command(update: TelegramUpdate, context: ApplicationContext) -> None:
    """Handles the /random command."""
    if not context.args:
        await update.message.reply_text("Usage: `/random ritsu@gmail.com [count]`", parse_mode="Markdown")
        return
    
    random_n = 20
    if len(context.args) > 1 and context.args[1].isdigit():
        random_n = max(1, min(int(context.args[1]), 200))
    
    await process_email_request(update.message, context, context.args[0], action="random", random_count=random_n)

async def tag_command(update: TelegramUpdate, context: ApplicationContext) -> None:
    """Handles the /tag command."""
    if len(context.args) < 2:
        await update.message.reply_text("Usage: `/tag ritsu@gmail.com shopping`", parse_mode="Markdown")
        return
    await process_email_request(update.message, context, context.args[0], action="tag", tag_label=context.args[1])


async def handle_plain_email_message(update: TelegramUpdate, context: ApplicationContext) -> None:
    """Handles plain text messages that look like emails."""
    if update.message and update.message.text:
        await process_email_request(update.message, context, update.message.text, action="full")


async def button_callback_handler(update: TelegramUpdate, context: ApplicationContext) -> None:
    """Handles inline keyboard button presses."""
    query = update.callback_query
    if query is None:
        return

    await query.answer()  # Acknowledge the query immediately

    last_email_parts = context.user_data.get("last")
    if not last_email_parts:
        await query.message.reply_text("Please send a Gmail address first to use these buttons.")
        return
    
    canonical, domain = last_email_parts
    email_address = f"{canonical}@{domain}"

    # Use the centralized rate limiter, which is now part of process_email_request
    # We pass the email_address to process_email_request to ensure canonicalization happens again
    # or just use the canonical/domain directly. Re-passing the address is safer.
    if query.data == Config.CALLBACK_RANDOM:
        await process_email_request(query, context, email_address, action="random", random_count=20)
    elif query.data == Config.CALLBACK_COUNT:
        await process_email_request(query, context, email_address, action="count")
    elif query.data == Config.CALLBACK_FILE:
        await send_full_list(query, canonical, domain, as_file=True)
    else:
        logger.warning(f"Unknown callback_data: {query.data}")
        await query.message.reply_text("An unknown action was requested.")


# --- Health check server + entrypoint ---

class HealthHandler(BaseHTTPRequestHandler):
    """Simple HTTP server for health checks."""
    def do_GET(self) -> None:
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args) -> None:
        """Suppresses default HTTP server logging."""
        pass


def run_health_server() -> None:
    """Runs a simple HTTP server in a separate thread for health checks."""
    logger.info(f"Starting health check server on port {Config.PORT}")
    server = HTTPServer(("0.0.0.0", Config.PORT), HealthHandler)
    server.serve_forever()


def main() -> None:
    """Main function to set up and run the Telegram bot."""
    if not Config.BOT_TOKEN:
        logger.error("BOT_TOKEN environment variable not set. Exiting.")
        raise RuntimeError("Set the BOT_TOKEN environment variable to your Telegram bot token.")

    threading.Thread(target=run_health_server, daemon=True).start()

    app = Application.builder().token(Config.BOT_TOKEN).build()

    # Register handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("about", about_command))
    app.add_handler(CommandHandler("dots", dots_command))
    app.add_handler(CommandHandler("count", count_command))
    app.add_handler(CommandHandler("random", random_command))
    app.add_handler(CommandHandler("tag", tag_command))
    app.add_handler(CallbackQueryHandler(button_callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_plain_email_message))

    logger.info("Bot starting (polling mode)...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
