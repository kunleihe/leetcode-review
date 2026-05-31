import argparse
import os
import shutil
import subprocess
import sys
import textwrap

PLIST_LABEL = "com.leetcode-review"
PLIST_PATH = os.path.expanduser(f"~/Library/LaunchAgents/{PLIST_LABEL}.plist")


def install():
    project_dir = os.path.dirname(os.path.abspath(__file__))
    app_path = os.path.join(project_dir, "app.py")
    log_dir = os.path.expanduser("~/Library/Logs/leetcode-review")
    os.makedirs(log_dir, exist_ok=True)

    uv = shutil.which("uv") or os.path.expanduser("~/.local/bin/uv")
    if not os.path.exists(uv):
        print("Error: uv not found. Install: curl -LsSf https://astral.sh/uv/install.sh | sh")
        sys.exit(1)

    if not os.path.exists(app_path):
        print(f"Error: app.py not found at {app_path}")
        sys.exit(1)

    plist = textwrap.dedent(f"""\
        <?xml version="1.0" encoding="UTF-8"?>
        <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
          "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
        <plist version="1.0">
        <dict>
          <key>Label</key>
          <string>{PLIST_LABEL}</string>
          <key>ProgramArguments</key>
          <array>
            <string>{uv}</string>
            <string>run</string>
            <string>python</string>
            <string>{app_path}</string>
          </array>
          <key>WorkingDirectory</key>
          <string>{project_dir}</string>
          <key>RunAtLoad</key>
          <true/>
          <key>KeepAlive</key>
          <true/>
          <key>StandardOutPath</key>
          <string>{log_dir}/stdout.log</string>
          <key>StandardErrorPath</key>
          <string>{log_dir}/stderr.log</string>
        </dict>
        </plist>
    """)

    try:
        with open(PLIST_PATH, "w") as f:
            f.write(plist)
    except OSError as e:
        print(f"Error writing plist: {e}")
        sys.exit(1)

    try:
        subprocess.run(["launchctl", "load", PLIST_PATH], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error loading LaunchAgent (exit {e.returncode}). Try: launchctl load {PLIST_PATH}")
        sys.exit(1)
    print("Installed. Flask will auto-start on login.")
    print(f"  Open: http://127.0.0.1:5000")
    print(f"  Logs: {log_dir}/")


def uninstall():
    if os.path.exists(PLIST_PATH):
        subprocess.run(["launchctl", "unload", PLIST_PATH], capture_output=True)
        os.remove(PLIST_PATH)
        print("Uninstalled.")
    else:
        print("Not installed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LeetCode Review LaunchAgent installer")
    parser.add_argument("--uninstall", action="store_true", help="Remove the LaunchAgent")
    args = parser.parse_args()
    uninstall() if args.uninstall else install()
