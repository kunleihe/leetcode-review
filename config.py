import os

LEETCODE_SESSION = os.environ.get("LEETCODE_SESSION")  # None if unset
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "leetcode.db")
PORT = 5000
