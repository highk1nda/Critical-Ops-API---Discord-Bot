# ============================================================
# Discord IDs
# ============================================================

STATUS_CHANNEL_ID = 1477285735655538709
ADMIN_ROLE_ID = 1372986279159005265
UKRY_ROLE_ID = 1407487106271412274
REACTION_MESSAGE_ID = 1477285069432422483

# Emoji → role ID mapping for reaction roles
ROLE_MAP = {
    "⚔": 1436468159061168231,
    "♾": 1411844893705240686,
    "☢": UKRY_ROLE_ID,
}

# ============================================================
# API
# ============================================================

API_URL = "https://1-60-0.prod.copsapi.criticalforce.fi/api/public/profile"
API_TIMEOUT = 10

# ============================================================
# Bot behavior
# ============================================================

COMMAND_PREFIX = "syr"
LOG_FILE = "discord.log"
SYRNYK_RESPONSE_CHANCE = 0.10
VIEW_TIMEOUT = 120

# ============================================================
# Smurf detection thresholds & weights
# ============================================================

SMURF_KILLS_LOW = 1000
SMURF_KILLS_HIGH = 3000
SMURF_GAMES_LOW = 300
SMURF_GAMES_HIGH = 600
SMURF_KD_THRESHOLD = 1.3
SMURF_WINRATE_THRESHOLD = 65.0

SMURF_WEIGHT_KILLS = 40
SMURF_WEIGHT_GAMES = 30
SMURF_WEIGHT_KD = 20
SMURF_WEIGHT_WINRATE = 10

# ============================================================
# Status embed
# ============================================================

STATUS_TIMEZONE = "Europe/Berlin"
STATUS_FOOTER = "Timezone: Europe/Berlin mala"
STATUS_STARTED_TITLE = "🟢 Bot Started"
STATUS_STARTED_DESC = "The bot is online fellas"
STATUS_STOPPED_TITLE = "🔴 Bot Stopped"
STATUS_STOPPED_DESC = "The bot has been shut down.🥺"

# ============================================================
# Strings
# ============================================================

EMBED_FOOTER = "cwazy stats bot"
MSG_NOT_ADMIN = "You are not admin."
MSG_SHUTTING_DOWN = "Shutting down..."
MSG_PROFILE_NOT_FOUND = "Profile not found."
MSG_APPROVED = "Approved. Role assigned."
MSG_DECLINED = "Declined."
