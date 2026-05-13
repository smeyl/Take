import curses
import socket
import threading

TARGET_IP = "127.0.0.1"  # change for real network testing
PORT = 5003

params = ["reverb", "delay", "compression", "volume"]
values = {"reverb": 0, "delay": 0, "compression": 0, "volume": 100}

transport_status = {"recording": False, "take": 0}
transport_callbacks = {"record": None, "stop": None, "status": None}


def send(sock, name, value):
    sock.sendto(f"{name}:{value}".encode(), (TARGET_IP, PORT))


def _call_transport(key):
    cb = transport_callbacks.get(key)
    if cb:
        threading.Thread(target=cb, daemon=True).start()


def draw(stdscr, selected):
    stdscr.clear()
    rec = transport_status["recording"]
    take = transport_status["take"]
    rec_str = f"● REC  T{take}" if rec else "○ stopped"

    stdscr.addstr(0, 0, f"Take — Cue Sender  →  {TARGET_IP}:{PORT}", curses.A_BOLD)
    stdscr.addstr(1, 0, f"  {rec_str}")
    stdscr.addstr(2, 0, "")

    for i, name in enumerate(params):
        v = values[name]
        bar = "#" * (v // 10) + "." * (10 - v // 10)
        row = f"  {name.capitalize():<14}  {v:>3}  [{bar}]"
        if i == selected:
            stdscr.addstr(3 + i, 0, ">")
            stdscr.addstr(3 + i, 1, row[1:], curses.A_REVERSE)
        else:
            stdscr.addstr(3 + i, 0, row)

    stdscr.addstr(8, 0, "")
    stdscr.addstr(9, 0, "  up/down: select    +/-: adjust    r: record    s: stop    q: quit")
    stdscr.refresh()


def main(stdscr):
    curses.curs_set(0)
    stdscr.keypad(True)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    selected = 0

    while True:
        draw(stdscr, selected)
        key = stdscr.getch()

        if key == curses.KEY_UP:
            selected = (selected - 1) % len(params)
        elif key == curses.KEY_DOWN:
            selected = (selected + 1) % len(params)
        elif key in (ord("+"), ord("=")):
            name = params[selected]
            values[name] = min(100, values[name] + 1)
            send(sock, name, values[name])
        elif key == ord("-"):
            name = params[selected]
            values[name] = max(0, values[name] - 1)
            send(sock, name, values[name])
        elif key == ord("r"):
            _call_transport("record")
        elif key == ord("s"):
            _call_transport("stop")
        elif key in (ord("q"), ord("Q"), 27):
            break

    sock.close()


if __name__ == "__main__":
    try:
        curses.wrapper(main)
    except KeyboardInterrupt:
        pass
