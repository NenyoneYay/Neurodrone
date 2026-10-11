from pymindwave2 import MindWaveMobile2, HeadsetDataEvent
import time

headset = MindWaveMobile2()
if not headset.start(n_tries=5, timeout=30):
    raise SystemExit("No connection — is TGC running and headset paired?")

def on_data(event: HeadsetDataEvent):
    print(event.data)

headset.on_data(on_data)
while True:
    time.sleep(1)