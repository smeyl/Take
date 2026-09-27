"""How far ahead of the engineer's timecode the artist's backing track plays,
so the artist's live vocal reaches the DAW in time with the DAW's playback.

The artist hears the backing late by one network leg (the timecode's trip)
plus however late the engineer's timecode is itself; their voice then takes
the return leg — artist input latency, a stream packet, the other network
leg, the engineer's stream receiver, and the DAW's input. The backing track
is advanced by the sum. The artist's own output latency isn't part of it:
backing_player places the track by when its audio reaches the output.

Worked out once when playback starts and held for the whole pass: Take can't
see the DAW's playhead to correct against, and changing the advance while
the track plays would make it jump.
"""
import collections

# Network round trips (seconds) timed by the artist's heartbeat. The lowest
# recent one is used: queueing only ever adds delay, never removes it.
_rtts = collections.deque(maxlen=6)

# Set by transport.py when its audio streams open.
artist = {"input_latency": None, "packet": None}

# From the relay, refreshed with every heartbeat: the engineer's stream
# receiver delay and the DAW input offset (TAKE_DAW_INPUT_OFFSET_MS), in ms.
engineer = {"receiver_ms": None, "daw_input_offset_ms": None}


def reset():
    """Forget the network and engineer figures — a new session (maybe over a
    different path, to a different engineer) or none. The artist's own audio
    figures stay."""
    _rtts.clear()
    for key in engineer:
        engineer[key] = None


def add_rtt(seconds):
    _rtts.append(seconds)


def update_engineer(figures):
    for key in engineer:
        if isinstance(figures, dict) and figures.get(key) is not None:
            engineer[key] = float(figures[key])


def advance():
    """(seconds, {term: ms}) — the advance and what it's made of. Terms not
    known yet (no heartbeat back, audio not open) count as 0 and are listed
    under "missing"."""
    terms = {
        "network": min(_rtts) * 1000 if _rtts else None,
        "input": artist["input_latency"] * 1000 if artist["input_latency"] is not None else None,
        "packet": artist["packet"] * 1000 if artist["packet"] is not None else None,
        "receiver": engineer["receiver_ms"],
        "daw_input": engineer["daw_input_offset_ms"],
    }
    missing = [k for k, v in terms.items() if v is None]
    terms = {k: round(v or 0.0, 1) for k, v in terms.items()}
    if missing:
        terms["missing"] = missing
    total = sum(v for k, v in terms.items() if k != "missing")
    return total / 1000.0, terms
