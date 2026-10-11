"""Expose the local app privately through Tailscale Serve."""

import argparse
import ipaddress
import json
from pathlib import Path
import shutil
import subprocess
import sys
from urllib.error import URLError
from urllib.request import urlopen

import config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--off", action="store_true", help="Disable mobile access")
    args = parser.parse_args()

    executable = shutil.which("tailscale")
    if not executable:
        bundled = Path("/Applications/Tailscale.app/Contents/MacOS/Tailscale")
        if bundled.is_file():
            executable = str(bundled)
    if not executable:
        print("Install Tailscale: https://tailscale.com/download/mac", file=sys.stderr)
        print("Open it, sign in, then run this command again.", file=sys.stderr)
        return 1

    try:
        if args.off:
            subprocess.run(
                [executable, "serve", f"--tcp={config.PORT}", "off"],
                check=True,
                timeout=30,
            )
            print("Mobile access disabled. Local access is unchanged.")
            return 0

        result = subprocess.run(
            [executable, "status", "--json"],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
        status = json.loads(result.stdout)
        if status.get("BackendState") != "Running":
            print("Open Tailscale, sign in and connect, then retry.", file=sys.stderr)
            return 1
        ipv4 = next(
            (ip for ip in status.get("TailscaleIPs", [])
             if ipaddress.ip_address(ip).version == 4),
            None,
        )
        if not ipv4:
            print("No Tailscale IPv4 address found. Reconnect and retry.", file=sys.stderr)
            return 1

        local_url = f"http://127.0.0.1:{config.PORT}"
        with urlopen(local_url, timeout=5):
            pass
        subprocess.run(
            [executable, "serve", "--bg", f"--tcp={config.PORT}",
             f"tcp://127.0.0.1:{config.PORT}"],
            check=True,
            timeout=30,
        )
        print(f"Phone URL: http://{ipv4}:{config.PORT}")
        print("Connect your phone to Tailscale using the same account.")
        print("Keep this computer awake, with Tailscale and the app running.")
        return 0
    except URLError:
        print("The app is not reachable. Start it with: uv run python app.py", file=sys.stderr)
    except subprocess.CalledProcessError as exc:
        print("Tailscale command failed. Check that the app is connected.", file=sys.stderr)
        if exc.stderr:
            print(exc.stderr.strip(), file=sys.stderr)
    except subprocess.TimeoutExpired:
        print("Tailscale timed out. Check the app and retry.", file=sys.stderr)
    except (OSError, ValueError) as exc:
        print(f"Unable to configure mobile access: {exc}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
