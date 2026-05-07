import curses
import socket

TARGET_IP = "127.0.0.1"  # change for real network testing
PORT = 5003

params = ["reverb", "delay", "compression", "volume"]
values = {"reverb": 0, "delay": 0, "compression": 0, "volume": 100}


def send(sock, name, value):
    sock.sendto(f"{name}:{value}".encode(), (TARGET_IP, PORT))


def draw(stdscr, selected):
    stdscr.clear()
    stdscr.addstr(0, 0, f"Take — Cue Sender  →  {TARGET_IP}:{PORT}", curses.A_BOLD)
    stdscr.addstr(1, 0, "")

    for i, name in enumerate(params):
        v = values[name]
        bar = "#" * (v // 10) + "." * (10 - v // 10)
        row = f"  {name.capitalize():<14}  {v:>3}  [{bar}]"
        if i == selected:
            stdscr.addstr(2 + i, 0, ">")
            stdscr.addstr(2 + i, 1, row[1:], curses.A_REVERSE)
        else:
            stdscr.addstr(2 + i, 0, row)

    stdscr.addstr(7, 0, "")
    stdscr.addstr(8, 0, "  up/down: select    +/-: adjust    q: quit")
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
        elif key in (ord("q"), ord("Q"), 27):
            break

    sock.close()


if __name__ == "__main__":
    try:
        curses.wrapper(main)
    except KeyboardInterrupt:
        pass
