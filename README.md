# MTG Signal Bot

A Signal messenger bot that looks up Magic: The Gathering card information using the Scryfall API, mirroring the syntax of the official Scryfall Discord/Slack bots.

## Syntax

Wrap card names in `[[double brackets]]` anywhere in a message, or use the `.` shorthand for quick mobile lookups.

| Syntax                  | Response                                                      |
| ----------------------- | ------------------------------------------------------------- |
| `[[Card Name]]`         | Oracle text, mana cost, type line, set info + image |
| `[[!Card Name]]`        | Full card image                                               |
| `[[?Card Name]]`        | Oracle rulings                                                |
| `[[#Card Name]]`        | Format legalities                                             |
| `[[$Card Name]]`        | Prices (USD, EUR, TIX)                                        |
| `[[Card Name\|SET]]`    | Specific set printing, e.g. `[[Jace\|WWK]]`                   |
| `[[Card Name\|SET\|N]]` | Specific set + collector number                               |

Multiple `[[cards]]` in one message are all handled. Fuzzy matching and partial names work the same way as Scryfall's own bot.

### Mobile shorthand

Send a message starting with `.` to look up a single card without brackets:

| Syntax             | Equivalent              |
| ------------------ | ----------------------- |
| `.Card Name`       | `[[Card Name]]`         |
| `.!Card Name`      | `[[!Card Name]]`        |
| `.Card Name\|SET`  | `[[Card Name\|SET]]`    |

### Help

Send `/help` to the bot in a direct message to see available commands.

## Requirements

- Docker and Docker Compose
- A phone number for the bot (a spare SIM or VoIP number from Telnyx, Twilio, etc.)

## Setup

### 1. Clone and configure

```bash
git clone https://github.com/jimsug/mtg-signal-bot
cd mtg-signal-bot
cp .env.example .env
```

Edit `.env` (see `.env.example` for all options):

```env
BOT_PHONE_NUMBER=+61400000000   # E.164 format
LOG_LEVEL=INFO

# Optional - enable the admin panel
OWNER_PHONE_NUMBER=+61400000000
ADMIN_SECRET_KEY=               # python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 2. Link or register the bot's phone number with Signal

Start signal-cli-rest-api on its own first:

```bash
docker compose up signal-cli-rest-api
```

#### Option A: Link an already-registered number

If the phone number is already registered on another Signal device (e.g. your phone), you can link signal-cli as a secondary device:

```bash
# Generate a linking URI (returns a tsdevice:// URI and a QR code path)
curl -X GET "http://localhost:8080/v1/qrcodelink?device_name=mtg-signal-bot" --output qr.png
```

Open `qr.png` and scan it from your Signal app (Settings > Linked Devices > Link New Device). Once linked, signal-cli will sync contacts and groups.

#### Option B: Register a new number

If you have a dedicated phone number for the bot:

```bash
# Get captcha token from https://signalcaptchas.org/registration/generate.html
# (look for the signalcaptcha:// redirect in your browser dev tools)

curl -X POST "http://localhost:8080/v1/register/+61400000000" \
  -H "Content-Type: application/json" \
  -d '{"captcha": "YOUR_CAPTCHA_TOKEN", "use_voice": false}'

# Then verify with the SMS code you receive
curl -X POST "http://localhost:8080/v1/register/+61400000000/verify/123456"
```

### 3. Start the bot

```bash
docker compose up -d
```

### 4. Add the bot to a Signal group

Add the bot's phone number to any Signal group the same way you'd add a contact. The bot will respond to `[[card name]]` lookups from any group it's in, and from direct messages.

## Development

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run tests
pytest tests/ -v

# Run locally (signal-cli-rest-api still needs to be running in Docker)
SIGNAL_SERVICE=localhost:8080 BOT_PHONE_NUMBER=+61400000000 python -m bot.main
```

## Admin Panel

An optional web-based admin panel for monitoring usage and managing the bot. Enabled when `OWNER_PHONE_NUMBER` is set.

**Authentication:** Enter your phone number to receive a 6-digit TOTP code via Signal. The panel gives no indication whether the number was correct — it always says "code sent if registered". Sessions last 30 minutes.

**Features:**

- **Dashboard** — Lookups today, cache size, currently suspicious users
- **Usage log** — Paginated log of all card lookups, filterable by user UUID
- **Ban management** — Ban/unban users by UUID (banned users are silently ignored)
- **Cache management** — Search and purge individual cache entries or the entire cache
- **Suspicious usage alerts** — Users exceeding 20 lookups in 5 minutes trigger a Signal message to the owner (30-minute cooldown per user)

**Configuration:**

| Variable | Default | Description |
| --- | --- | --- |
| `OWNER_PHONE_NUMBER` | _(none)_ | Owner's phone number (enables admin panel + alerts) |
| `ADMIN_SECRET_KEY` | `change-me-in-production` | Secret for session cookie signing |
| `ADMIN_PORT` | `8081` | Port for the admin web server |
| `ADMIN_BASE_PATH` | _(none)_ | URL prefix, e.g. `/admin` for reverse proxy setups |

The panel is designed to sit behind Tailscale, a Cloudflare Tunnel, or similar — it listens on all interfaces but relies on your network layer for access control.

## Project Structure

```
mtg-signal-bot/
├── bot/
│   ├── alerts.py       # Suspicious usage alerting via Signal
│   ├── command.py       # signalbot Command - main message handler
│   ├── formatter.py     # Formats Scryfall data into Signal messages
│   ├── main.py          # Entry point, wires up bot + admin server
│   ├── parser.py        # Parses [[card name]] syntax from messages
│   └── scryfall.py      # Scryfall API client with caching
├── admin/
│   ├── app.py           # FastAPI application factory
│   ├── auth.py          # TOTP-over-Signal authentication
│   ├── routes.py        # Admin panel routes
│   └── templates/       # Jinja2 HTML templates
├── db/
│   ├── cache.py         # SQLite cache layer (24-hour TTL)
│   └── usage.py         # Usage tracking and ban management
├── tests/
│   ├── formatter_test.py
│   ├── parser_test.py
│   └── usage_test.py
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

## Caching

Card data is cached in SQLite for 24 hours, matching Scryfall's own update cadence. The cache lives at `/app/data/cache.db` inside the container (mounted from `./data/` on the host). Expired entries are purged automatically once per hour.

## Attribution

Card data provided by [Scryfall](https://scryfall.com). Per Scryfall's API usage policy, this bot identifies itself with a custom `User-Agent` header and respects the 10 requests/second rate limit.
