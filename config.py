import os
from dotenv import load_dotenv

load_dotenv()


def get_leetcode_session():
    # Re-read .env each call so cookie updates take effect without restart
    load_dotenv(override=True)
    return os.environ.get("LEETCODE_SESSION")  # None if unset
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "leetcode.db")
PORT = 5001
INITIAL_SYNC_LIMIT = int(os.environ.get("INITIAL_SYNC_LIMIT", 200))
