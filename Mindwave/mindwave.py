"""
Connect to a MindWave Mobile 2 directly over a Bluetooth RFCOMM socket
(no COM port, no ThinkGear Connector).

Requirements:
    Python 3.9+ on Windows (uses the built-in socket.AF_BLUETOOTH)
    mindwave_reader.py in the same folder (reuses its packet parser)

Usage:
    python mindwave_rfcomm.py AA:BB:CC:DD:EE:FF
    python mindwave_rfcomm.py AA:BB:CC:DD:EE:FF --channel 1

Find the address in PowerShell:
    Get-PnpDevice -Class Bluetooth | Where-Object FriendlyName -like '*Mind*' |
        Select-Object FriendlyName, InstanceId
The 12 hex digits after DEV_ in the InstanceId are the address.
"""

import argparse
import socket
import sys
import time

from mindwave_reader import read_packets


class SocketAsSerial:
    """Minimal wrapper so the serial-based packet reader works on a socket."""

    def __init__(self, sock):
        self.sock = sock

    def read(self, n=1):
        buf = b""
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                raise ConnectionError("Headset closed the connection")
            buf += chunk
        return buf


def connect(address, channels):
    if not hasattr(socket, "AF_BLUETOOTH"):
        print("This Python build has no Bluetooth socket support. Use Python 3.9+ "
              "from python.org.")
        sys.exit(1)

    last_error = None
    for ch in channels:
        print(f"Trying RFCOMM channel {ch}...")
        sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM,
                             socket.BTPROTO_RFCOMM)
        sock.settimeout(10)
        try:
            sock.connect((address, ch))
            sock.settimeout(5)
            print(f"Connected on channel {ch}.")
            return sock
        except OSError as e:
            last_error = e
            print(f"  failed: {e}")
            sock.close()
    print(f"\nCould not connect. Last error: {last_error}")
    print("Check that the headset is on, paired with Windows, not connected to another "
          "device, and that the address is correct.")
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="MindWave RFCOMM reader")
    parser.add_argument("address", help="Bluetooth address, e.g. AA:BB:CC:DD:EE:FF")
    parser.add_argument("--channel", type=int, help="RFCOMM channel (default: try 1-5)")
    args = parser.parse_args()

    channels = [args.channel] if args.channel else [1, 2, 3, 4, 5]
    sock = connect(args.address, channels)
    reader = SocketAsSerial(sock)

    print("Reading data. Put the headset on. Ctrl+C to stop.\n")
    last_print = 0
    state = {"poor_signal": None, "attention": None, "meditation": None}

    try:
        for data in read_packets(reader):
            state.update({k: v for k, v in data.items() if k in state})
            if "blink" in data:
                print(f"** BLINK ({data['blink']}) **")
            now = time.time()
            if now - last_print >= 1.0 and state["attention"] is not None:
                sig = state["poor_signal"]
                quality = "good" if sig == 0 else f"poor ({sig})"
                print(f"signal={quality}  attention={state['attention']}  "
                      f"meditation={state['meditation']}")
                last_print = now
    except KeyboardInterrupt:
        print("\nStopped.")
    except (ConnectionError, OSError) as e:
        print(f"\nConnection lost: {e}")
    finally:
        sock.close()


if __name__ == "__main__":
    main()