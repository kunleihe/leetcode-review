import os
from dotenv import load_dotenv

load_dotenv()

LEETCODE_SESSION = os.environ.get("LEETCODE_SESSION")  # None if unset
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "leetcode.db")
PORT = 5001
INITIAL_SYNC_LIMIT = int(os.environ.get("INITIAL_SYNC_LIMIT", 200))
