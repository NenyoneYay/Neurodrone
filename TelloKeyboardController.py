import threading
import socket
import time
import cv2
import keyboard

locaddr = ('', 9000)
tello_address = ('192.168.10.1', 8889)

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(locaddr)

def send(cmd):
    sock.sendto(cmd.encode("utf-8"), tello_address)

def recv():
    while True:
        try:
            data, server = sock.recvfrom(1518)
            print(data.decode("utf-8"))
        except Exception:
            print('\nExit . . .\n')
            break

stop_video = threading.Event()
videoThread = None


def show_video():
    cap = cv2.VideoCapture("udp://0.0.0.0:11111", cv2.CAP_FFMPEG)

    while not stop_video.is_set():
        if not cap.grab():
            continue
        ret, frame = cap.retrieve()
        if ret:
            cv2.imshow("Tello", frame)
        cv2.waitKey(1)

    cap.release()
    cv2.destroyAllWindows()
    send("streamoff")

recvThread = threading.Thread(target=recv, daemon=True)
recvThread.start()

send("command")

SLOW = 20
FAST = 60

speed = 40
TURNSPEED = 80

is_flying = False

space_was_down = False
v_was_down = False
speedup_was_down = False
speeddown_was_down = False

send_battery_time = 0

while True:
    try:
        # Takeoff / land: once per press
        space_down = keyboard.is_pressed("space")
        if space_down and not space_was_down:
            if is_flying:
                send("land")
                is_flying = False
            else:
                send("takeoff")
                is_flying = True
        space_was_down = space_down

        # V on the keyboard toggles the video stream and opens the opencv thread
        v_down = keyboard.is_pressed("v")
        if v_down and not v_was_down:
            if videoThread is None or not videoThread.is_alive():
                send("streamon")
                stop_video.clear()
                videoThread = threading.Thread(target=show_video, daemon=True)
                videoThread.start()
            else:
                stop_video.set()
        v_was_down = v_down

         # > on the keyboard makes the drone go faster
        speedup_down = keyboard.is_pressed(">")
        if speedup_down and not speedup_was_down:
            speed += 5
            if speed > FAST:
                speed = FAST
            print(speed)
        speedup_was_down = speedup_down

         # < on the keyboard makes the drone go slower
        speeddown_down = keyboard.is_pressed("<")
        if speeddown_down and not speeddown_was_down:
            speed -= 5
            if speed < SLOW:




                speed = SLOW    
            print(speed)
        speeddown_was_down = speeddown_down

        # Movement: velocities, 0 when no key is held
        lr = (keyboard.is_pressed("d") - keyboard.is_pressed("a")) * speed                      #Left/Right: D - A * Speed => 0-0 * Speed || 1-0 * Speed || 0-1 * Speed || 1-1 * Speed
        fb = (keyboard.is_pressed("w") - keyboard.is_pressed("s")) * speed                      #Forward/Back
        ud = (keyboard.is_pressed("up") - keyboard.is_pressed("down")) * speed                  #Up/Down
        yaw = (keyboard.is_pressed("right") - keyboard.is_pressed("left")) * TURNSPEED          #Yaw

        send(f"rc {lr} {fb} {ud} {yaw}")

        # Send the battery status every ten seconds
        if send_battery_time > 100:
            send("battery?")
            send_battery_time = 0
        else:
            send_battery_time += 1

        time.sleep(0.1)

    except KeyboardInterrupt:
        print('\n . . .\n')
        send("land")
        stop_video.set()
        if videoThread is not None:
            videoThread.join(timeout=3)  # lets streamoff get sent first
        sock.close()
        break