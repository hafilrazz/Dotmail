# Gmail Dot-Variation Telegram Bot

Gmail ignores dots in the part of an address before the `@`, so
`john.doe@gmail.com`, `johndoe@gmail.com`, and `jo.hndoe@gmail.com` all
deliver to the exact same inbox. This bot takes a Gmail address and lists
every valid dot-variation of it.

## How it works

- Send `/start` for instructions.
- Send any Gmail address (e.g. `john.doe@gmail.com`).
- The bot strips existing dots, then generates every way dots can be
  re-inserted between the letters (Gmail never allows a dot as the first or
  last character, or two dots in a row).
- For very long usernames (>15 characters) the combination count explodes
  (2^14 and up), so the bot just reports the total instead of listing them
  all.
- If the list is long, it's sent as a `.txt` file instead of a giant message.

## 1. Create the bot with BotFather

1. Open Telegram, message [@BotFather](https://t.me/BotFather).
2. Send `/newbot` and follow the prompts.
3. Copy the API token it gives you (looks like `123456789:AAExample...`).

## 2. Run it locally (optional)

```bash
pip install -r requirements.txt
export BOT_TOKEN="your-token-here"
python bot.py
```

## 3. Deploy to Render

**Option A — using the included blueprint**
1. Push this folder to a GitHub repo.
2. In Render, click **New > Blueprint**, point it at the repo (it will pick
   up `render.yaml` automatically).
3. When prompted, set the `BOT_TOKEN` environment variable to your token
   from BotFather.
4. Deploy. Render will run `pip install -r requirements.txt` then
   `python bot.py`.

**Option B — manual setup**
1. Push this folder to a GitHub repo.
2. In Render, click **New > Web Service**, connect the repo.
3. Environment: `Python 3`.
4. Build command: `pip install -r requirements.txt`
5. Start command: `python bot.py`
6. Add an environment variable `BOT_TOKEN` with your token.
7. Deploy.

The bot runs in polling mode (no public webhook URL needed) and opens a
minimal HTTP server on `$PORT` just to satisfy Render's health checks for
web services.

## Notes

- Free Render web services spin down after inactivity and take a few
  seconds to wake back up on the next request/poll — that's normal on the
  free tier.
- Only use this on addresses you own or have permission to test — dot
  variations all land in the same inbox, so it's mainly useful for things
  like organizing filters or checking which variant a signup form accepted.
