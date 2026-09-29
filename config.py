import os

TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))

DATA_DIR = os.environ.get("DATA_DIR", os.path.dirname(__file__))
STATE_FILE = os.path.join(DATA_DIR, "state.json")

REDIS_URL = os.environ.get("REDIS_URL", "")
