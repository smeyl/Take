"""What Take needs from a DAW — the one module the rest of the backend imports
instead of reaching into a specific DAW integration.

Every function here delegates to the active implementation module: Pro Tools
(pro_tools.py, via PTSL). reaper.py (take_session.lua) is the legacy
implementation of the same functions, kept for reference.
"""
import pro_tools as _impl

NAME = _impl.NAME  # shown in logs and the engineer app, e.g. "Pro Tools"


# ── Liveness ──────────────────────────────────────────────────────────────────

def alive():
    """True if the DAW can be read and controlled right now (Pro Tools: PTSL
    answers and a session is open; Reaper: take_session.lua is reporting)."""
    return _impl.alive()


def stream_device():
    """Name of the virtual audio output device the artist's live mic stream is
    played into, so the DAW can monitor and record it (matched exactly, else
    as a substring)."""
    return _impl.stream_device()


# ── Transport and session state (read) ────────────────────────────────────────

def get_transport():
    """(position_seconds, playing). Paused counts as not playing. (0.0, False)
    when unknown — callers treat that as stopped."""
    return _impl.get_transport()


def get_cursor():
    """The engineer's cursor / edit position (seconds) — mirrored live on the
    artist's backing track. None when the DAW doesn't report one."""
    return _impl.get_cursor()


def is_recording():
    """True while the DAW's own transport is recording. record_watcher.py
    follows this to start and stop the artist's capture."""
    return _impl.is_recording()


def get_tracks():
    """Tracks as [{"index": int, "name": str, "armed": bool}, ...]; [] when
    unknown."""
    return _impl.get_tracks()


def get_markers():
    """Markers as [{"name": str, "position": seconds}, ...]; [] when unknown."""
    return _impl.get_markers()


# ── Transport commands ────────────────────────────────────────────────────────

def start_recording(track=0, capture_pos=None):
    """Sent when the artist's lossless capture actually begins (after the
    countdown). If the DAW is recording (the engineer pressed Record in the
    DAW), note where the capture begins so place_take() can line the file up.
    capture_pos is the backing-track position (seconds, = timeline position)
    the artist heard at the file's first sample, when their backing track was
    playing; an implementation should prefer it to its own estimate.
    If the DAW isn't recording, an implementation may start it (Reaper arms
    `track` and records) or decline (Pro Tools); returns False when it didn't
    act."""
    return _impl.start_recording(track, capture_pos)


def stop_recording():
    """Sent when the artist's capture ends. Stops the DAW only if it is still
    recording."""
    return _impl.stop_recording()


def return_to_zero():
    """Move the playhead to the project start."""
    return _impl.return_to_zero()


# ── Takes ─────────────────────────────────────────────────────────────────────

def place_take(filepath, fallback_track=0):
    """Put a received lossless take on the DAW timeline.

    Replaces the live-streamed recording of the same take at the position the
    capture began (known from start_recording()). With no such position — no
    recording this session, or already used — inserts the file on
    `fallback_track` at the edit cursor instead.

    Returns "swapped", "inserted", or "not_running" (DAW companion down; the
    file was not placed)."""
    return _impl.place_take(filepath, fallback_track)


# ── Backing-track bounce ──────────────────────────────────────────────────────

def start_bounce(selected_tracks=None):
    """Render the project's master mix to a new file. selected_tracks: track
    indices to include (others muted for the render); None/empty = all."""
    return _impl.start_bounce(selected_tracks)


def bounce_signalled():
    """True once the render requested by start_bounce() has finished."""
    return _impl.bounce_signalled()


def bounce_output_path():
    """Path of the finished render, or None until bounce_signalled()."""
    return _impl.bounce_output_path()
