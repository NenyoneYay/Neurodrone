"""
MindWave Mobile 2 reader (Windows, classic Bluetooth serial port).

Setup:
    pip install pyserial

Usage:
    python mindwave_reader.py              # auto-detect the Bluetooth COM port
    python mindwave_reader.py COM5         # specify the outgoing COM port
    python mindwave_reader.py COM5 --raw   # also print raw EEG samples (512 Hz, noisy)

Close ThinkGear Connector and PuTTY first. Only one program can hold the port.
"""

import argparse
import struct
import sys
import time

import serial
import serial.tools.list_ports

BAUD = 57600
SYNC = 0xAA

BAND_NAMES = ["delta", "theta", "low_alpha", "high_alpha",
              "low_beta", "high_beta", "low_gamma", "mid_gamma"]


def find_port():
    """Try to find the MindWave's Bluetooth serial port automatically."""
    candidates = []
    for p in serial.tools.list_ports.comports():
        desc = (p.description or "").lower()
        hwid = (p.hwid or "").lower()
        if "bluetooth" in desc or "bthenum" in hwid:
            candidates.append(p.device)
    return candidates


def parse_payload(payload, show_raw=False):
    """Parse a ThinkGear payload and return a dict of values found."""
    data = {}
    i = 0
    while i < len(payload):
        # Skip extended code bytes
        while i < len(payload) and payload[i] == 0x55:
            i += 1
        if i >= len(payload):
            break

        code = payload[i]
        i += 1

        if code < 0x80:
            # Single-byte value
            if i >= len(payload):
                break
            value = payload[i]
            i += 1
            if code == 0x02:
                data["poor_signal"] = value      # 0 = good, 200 = no contact
            elif code == 0x04:
                data["attention"] = value        # 0-100
            elif code == 0x05:
                data["meditation"] = value       # 0-100
            elif code == 0x16:
                data["blink"] = value            # 0-255
        else:
            # Multi-byte value: next byte is the length
            if i >= len(payload):
                break
            vlen = payload[i]
            i += 1
            value = payload[i:i + vlen]
            i += vlen
            if code == 0x80 and vlen == 2 and show_raw:
                data["raw"] = struct.unpack(">h", bytes(value))[0]
            elif code == 0x83 and vlen == 24:
                bands = {}
                for n, name in enumerate(BAND_NAMES):
                    b = value[n * 3:n * 3 + 3]
                    bands[name] = (b[0] << 16) | (b[1] << 8) | b[2]
                data["bands"] = bands
    return data


def read_packets(ser, show_raw=False):
    """Generator that yields parsed data dicts from the serial stream."""
    while True:
        # Look for two sync bytes
        if ser.read(1) != bytes([SYNC]):
            continue
        if ser.read(1) != bytes([SYNC]):
            continue

        # Packet length (must be < 170; 170 would be another sync byte)
        plen_b = ser.read(1)
        if not plen_b:
            continue
        plen = plen_b[0]
        while plen == SYNC:
            plen_b = ser.read(1)
            if not plen_b:
                break
            plen = plen_b[0]
        if plen > 169:
            continue

        payload = ser.read(plen)
        chk_b = ser.read(1)
        if len(payload) != plen or not chk_b:
            continue

        checksum = (~sum(payload)) & 0xFF
        if checksum != chk_b[0]:
            continue  # corrupted packet, skip it

        data = parse_payload(payload, show_raw)
        if data:
            yield data


def main():
    parser = argparse.ArgumentParser(description="MindWave Mobile 2 reader")
    parser.add_argument("port", nargs="?", help="COM port, e.g. COM5 (optional)")
    parser.add_argument("--raw", action="store_true", help="print raw EEG samples")
    args = parser.parse_args()

    port = args.port
    if not port:
        found = find_port()
        if not found:
            print("No Bluetooth COM port found. Pair the headset first, then check the "
                  "Outgoing port under Bluetooth settings > COM Ports and pass it in "
                  "(e.g. python mindwave_reader.py COM5).")
            sys.exit(1)
        print("Bluetooth COM ports found:", ", ".join(found))
        port = found[0]
        print(f"Trying {port}. If that's wrong, pass the port explicitly.")

    print(f"Opening {port} at {BAUD} baud...")
    try:
        ser = serial.Serial(port, BAUD, timeout=2)
    except serial.SerialException as e:
        print(f"Could not open {port}: {e}")
        print("Make sure the headset is on and paired, the port number is the OUTGOING "
              "one, and ThinkGear Connector / PuTTY are closed.")
        sys.exit(1)

    print("Connected. Put the headset on (sensor on forehead, clip on ear). Ctrl+C to stop.\n")

    last_print = 0
    state = {"poor_signal": None, "attention": None, "meditation": None}

    try:
        for data in read_packets(ser, show_raw=args.raw):
            if "raw" in data:
                print("raw:", data["raw"])
                continue

            state.update({k: v for k, v in data.items() if k in state})

            if "blink" in data:
                print(f"** BLINK (strength {data['blink']}) **")

            if "bands" in data:
                bands = data["bands"]
                print("EEG bands: " + "  ".join(f"{k}={v}" for k, v in bands.items()))

            # Print the eSense summary about once a second
            now = time.time()
            if now - last_print >= 1.0 and state["attention"] is not None:
                sig = state["poor_signal"]
                quality = "good" if sig == 0 else f"poor ({sig})"
                print(f"signal={quality}  attention={state['attention']}  "
                      f"meditation={state['meditation']}")
                last_print = now

    except KeyboardInterrupt:
        print("\nStopped.")
    except serial.SerialException as e:
        print(f"\nSerial connection lost: {e}")
    finally:
        ser.close()


if __name__ == "__main__":
    main()