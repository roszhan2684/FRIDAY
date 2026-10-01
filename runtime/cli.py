"""FRIDAY CLI — test commands without voice or the Swift app.

Usage:
  python -m runtime.cli "open spotify"
  python -m runtime.cli "morning mode"
  python -m runtime.cli "open my resume"
  python -m runtime.cli --listen          # stream live events from running runtime
"""
from __future__ import annotations
import argparse
import asyncio
import json
import sys
import httpx
import websockets  # type: ignore


BASE = "http://127.0.0.1:7700"


async def send_command(text: str) -> None:
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            resp = await client.post(f"{BASE}/command", json={"text": text, "source": "cli"})
            resp.raise_for_status()
            data = resp.json()
            print(f"\nTranscript : {data['transcript']}")
            print(f"Tool       : {data['tool_called']}")
            print(f"Response   : {data['spoken_response']}")
            print(f"Success    : {data['success']}")
            if data.get("output"):
                print(f"Output     : {data['output']}")
            if data.get("error"):
                print(f"Error      : {data['error']}")
        except httpx.ConnectError:
            print("ERROR: FRIDAY runtime is not running. Start it with: bash scripts/start.sh")
            sys.exit(1)


async def live_listen() -> None:
    uri = "ws://127.0.0.1:7700/ws"
    print(f"Connecting to {uri} — press Ctrl+C to stop\n")
    try:
        async with websockets.connect(uri) as ws:
            print("Connected. Streaming events...\n")
            async for message in ws:
                try:
                    event = json.loads(message)
                    etype = event.get("type", "?")
                    payload = event.get("payload", {})
                    print(f"[{etype}] {json.dumps(payload)}")
                except Exception:
                    print(f"RAW: {message}")
    except ConnectionRefusedError:
        print("ERROR: FRIDAY runtime is not running. Start it with: bash scripts/start.sh")


async def check_health() -> None:
    async with httpx.AsyncClient(timeout=5) as client:
        try:
            resp = await client.get(f"{BASE}/health")
            data = resp.json()
            print(f"Status : {data['status']}")
            print(f"State  : {data['state']}")
            print(f"Clients: {data['clients']}")
        except httpx.ConnectError:
            print("ERROR: Runtime not running.")


def main() -> None:
    parser = argparse.ArgumentParser(description="FRIDAY CLI")
    parser.add_argument("command", nargs="?", help="Command to send (e.g. 'open spotify')")
    parser.add_argument("--listen", action="store_true", help="Stream live events")
    parser.add_argument("--health", action="store_true", help="Check runtime health")
    args = parser.parse_args()

    if args.listen:
        asyncio.run(live_listen())
    elif args.health:
        asyncio.run(check_health())
    elif args.command:
        asyncio.run(send_command(args.command))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
