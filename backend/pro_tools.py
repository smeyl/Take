"""Pro Tools implementation of the DAW interface in daw.py — import daw, not this.

Pro Tools is driven through PTSL (Pro Tools Scripting Library, gRPC on
localhost:31416) via py-ptsl. PTSL is request/response only — there is no
exported state like Reaper's take_session.lua files — so the few facts that
must cross Take's processes (when recording started, where the artist's
capture began) are kept in small /tmp files written here.

Behaviour verified against Pro Tools 2026.4 (PTSL 2026, py-ptsl 601.1.0):
  * "recording" is GetTransportState == TS_TransportRecording only;
    GetTransportArmed (the record button) reads back unreliably, so it is
    never used.
  * PTSL has no playhead read. While rolling, the position is estimated from
    where the transport started (the timeline selection's in point, which
    stays put while playing/recording) plus elapsed wall time.
  * SpotClipsByID needs the position in SpotLocationData.location; the older
    location_value field fails with PT_UnknownError (location).
"""
import glob
import json
import os
import socket
import threading
import time

import grpc
import ptsl
from ptsl import PTSL_pb2 as pt
from ptsl import ops
from ptsl.errors import CommandError
from ptsl.ops import Operation

NAME = "Pro Tools"

PTSL_HOST, PTSL_PORT = "127.0.0.1", 31416
RECORD_FILE  = "/tmp/take_pt_record.json"   # where/when the current recording started
CAPTURE_FILE = "/tmp/take_pt_capture.json"  # where the artist's capture began (for the swap)
STALE_AFTER  = 3600   # seconds — older record/capture info is from a dead session
ALIVE_CACHE  = 1.0    # seconds — record_watcher asks alive() every 50 ms
STATE_CACHE  = 0.03   # seconds — timecode and record_watcher share transport reads

RECORDING_STATES = {"TS_TransportRecording", "TS_TransportRecordingHalfSpeed"}
PLAYING_STATES   = RECORDING_STATES | {"TS_TransportPlaying", "TS_TransportPlayingHalfSpeed"}
SHUFFLE_MODES    = {pt.EMO_Shuffle, pt.EMO_ShuffleSnapToGridAbsolute, pt.EMO_ShuffleSnapToGridRelative}
TIMELINE_TYPES   = {pt.TT_Audio, pt.TT_Aux, pt.TT_Instrument, pt.TT_Midi}


# py-ptsl 601.1.0 doesn't wrap these commands; its Operation base class builds
# any command from the class name (the same way it defines CId_Clear).
class CId_ImportAudioToClipList(Operation):
    pass


class CId_SpotClipsByID(Operation):
    pass


class CId_GetExportMixSourceList(Operation):
    pass


# ── Connection ────────────────────────────────────────────────────────────────

_lock = threading.RLock()   # one PTSL conversation at a time per process
_engine = None


def _port_open():
    try:
        with socket.create_connection((PTSL_HOST, PTSL_PORT), timeout=0.3):
            return True
    except OSError:
        return False


def _eng():
    """The shared Engine, (re)connecting if needed. Raises when Pro Tools
    isn't reachable."""
    global _engine
    if _engine is None:
        if not _port_open():
            raise ConnectionError("Pro Tools (PTSL) is not running")
        _engine = ptsl.Engine(company_name="Take", application_name="Take",
                              address=f"localhost:{PTSL_PORT}")
    return _engine


def _call(fn, default=None):
    """Run fn(engine) under the lock. Connection loss resets the engine so the
    next call reconnects; any PTSL error returns `default`."""
    global _engine
    with _lock:
        try:
            return fn(_eng())
        except grpc.RpcError:
            _engine = None
            return default
        except (CommandError, ConnectionError):
            return default


def _write_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f)
    os.replace(tmp, path)


def _read_fresh_json(path):
    try:
        if time.time() - os.path.getmtime(path) > STALE_AFTER:
            os.remove(path)
            return None
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


# ── Liveness ──────────────────────────────────────────────────────────────────

_alive = {"t": 0.0, "value": False}


def alive():
    """PTSL answers and a session is open (nothing Take does works without
    one). Cached briefly — this is polled at 20 Hz."""
    now = time.time()
    if now - _alive["t"] < ALIVE_CACHE:
        return _alive["value"]
    value = _port_open() and _call(lambda e: bool(e.session_name()), False)
    _alive.update(t=now, value=bool(value))
    return _alive["value"]


# ── Transport and session state ───────────────────────────────────────────────

_state = {"t": 0.0, "value": None}
_roll = {"playing": False, "t0": 0.0, "in_sec": 0.0, "read_t": 0.0}  # this process's play estimate
STOPPED_REREAD = 0.5  # seconds between selection reads while stopped
_was_recording = {"value": False}


def _transport_state():
    now = time.time()
    if now - _state["t"] >= STATE_CACHE:
        _state.update(t=now, value=_call(lambda e: e.transport_state()))
    return _state["value"]


def _sample_rate(e):
    return e.session_sample_rate() or 48000


def _selection_in_samples(e):
    return int(e.get_timeline_selection(pt.TLType_Samples)[0])


def get_transport():
    """(position_seconds, playing). PTSL can't read the playhead: while
    rolling, the position is the start point plus elapsed time (loops,
    pre-roll and scrubbing aren't followed); when stopped, it's the timeline
    selection's in point."""
    state = _transport_state()
    if state is None:
        return 0.0, False
    playing = state in PLAYING_STATES
    if playing and not _roll["playing"]:
        in_sec = _call(lambda e: _selection_in_samples(e) / _sample_rate(e), 0.0)
        _roll.update(playing=True, t0=time.time(), in_sec=in_sec)
    elif not playing:
        _roll["playing"] = False
        if time.time() - _roll["read_t"] >= STOPPED_REREAD:
            _roll["read_t"] = time.time()
            _roll["in_sec"] = _call(lambda e: _selection_in_samples(e) / _sample_rate(e),
                                    _roll["in_sec"])
    if playing:
        return _roll["in_sec"] + (time.time() - _roll["t0"]), True
    return _roll["in_sec"], False


def is_recording():
    """True only in TS_TransportRecording (IsCued/IsStopping are transitional).
    When recording is first seen, note where and when it started — the relay
    process needs that to place the artist's capture."""
    recording = _transport_state() in RECORDING_STATES
    if recording and not _was_recording["value"]:
        seen_at = _state["t"]  # when the Recording state was read, not after the reads below
        info = _call(lambda e: {"rec_in": _selection_in_samples(e),
                                "sr": _sample_rate(e)})
        if info:
            info["t"] = seen_at
            _write_json(RECORD_FILE, info)
    _was_recording["value"] = recording
    return recording


def get_tracks():
    """[{index, name, armed}] for timeline tracks (audio, aux, instrument,
    MIDI). index is 0-based in session order; Pro Tools addresses tracks by
    name, so names are what the rest of this module uses."""
    tracks = _call(lambda e: e.track_list(), []) or []
    return [{"index": t.index - 1, "name": t.name,
             "armed": bool(t.track_attributes.is_record_enabled)}
            for t in tracks if t.type in TIMELINE_TYPES]


def _first_armed_track():
    return next((t["name"] for t in get_tracks() if t["armed"]), None)


def get_markers():
    """Markers (memory locations with a marker time property) as
    [{name, position_seconds}]."""
    def read(e):
        sr = _sample_rate(e)
        out = []
        for m in e.get_memory_locations():
            if m.time_properties != pt.TP_Marker:
                continue
            try:
                out.append({"name": m.name, "position": round(int(m.start_time) / sr, 3)})
            except ValueError:
                pass  # not a sample count — see get_markers note in the report
        return out
    return _call(read, []) or []


# ── Transport commands ────────────────────────────────────────────────────────

def start_recording(track=0):
    """The artist's capture just began. If Pro Tools is recording (the
    engineer pressed Record), work out where on the timeline that is and save
    it for place_take(). Take doesn't start Pro Tools recording itself: the
    record button's state can't be read reliably, so toggling it blind could
    turn it off instead."""
    if _transport_state() not in RECORDING_STATES:
        print("Pro Tools isn't recording — press Record in Pro Tools; "
              "Take follows it but doesn't start it.", flush=True)
        return False
    rec = _read_fresh_json(RECORD_FILE)
    if not rec:
        print("Pro Tools is recording but its start wasn't seen (is the "
              "engineer backend running?) — the take can't be placed in sync.",
              flush=True)
        return False
    capture_start = rec["rec_in"] + round((time.time() - rec["t"]) * rec["sr"])
    track_name = _first_armed_track()
    if track_name is None:
        tracks = get_tracks()
        track_name = next((t["name"] for t in tracks if t["index"] == track), None)
    _write_json(CAPTURE_FILE, {"track": track_name, "capture_start": capture_start,
                               "rec_in": rec["rec_in"], "sr": rec["sr"]})
    print(f"[capture] artist capture began at sample {capture_start} "
          f"({capture_start / rec['sr']:.3f} s) on '{track_name}'", flush=True)
    return True


def stop_recording():
    """Stop Pro Tools only if it's still recording (normally the engineer
    already stopped it and this arrives afterwards)."""
    if _transport_state() in RECORDING_STATES:
        _call(lambda e: e.toggle_play_state())
    return True


def return_to_zero():
    """No RTZ command in PTSL — put the timeline selection at the session start."""
    _call(lambda e: e.set_timeline_selection(in_time="0", out_time="0",
                                             location_type=pt.TLType_Samples))
    return True


# ── Takes ─────────────────────────────────────────────────────────────────────

def _track_clips(e, track_name):
    """[(start, end)] in samples for a track, from the session-text EDL."""
    b = e.export_session_as_text()
    b.include_track_edls()
    b.time_type("samples")
    clips, in_track = set(), False
    for line in b.export_string().splitlines():
        if line.startswith("TRACK NAME:"):
            in_track = line.split("\t", 1)[-1].strip() == track_name
            continue
        cols = [c.strip() for c in line.split("\t")]
        if in_track and len(cols) >= 5 and cols[0].isdigit() and cols[1].isdigit():
            clips.add((int(cols[3]), int(cols[4])))
    return sorted(clips)


def _import(e, filepath):
    """Import into the clip list, converting to the session's sample rate and
    format (the artist records 44.1 kHz; CopyAudio refuses a rate mismatch).
    Returns the new clip ids."""
    imp = CId_ImportAudioToClipList(file_list=[filepath], audio_operations=pt.ConvertAudio)
    e.client.run(imp)
    fails = [f"{f.file_path}: {f.failure_message}" for f in imp.response.failure_list]
    ids = [c for entry in imp.response.file_list
           for f in entry.destination_file_list for c in f.clip_id_list]
    if not ids:
        raise RuntimeError(f"import produced no clip ({'; '.join(fails) or 'no reason given'})")
    return ids


def _spot(e, ids, track_name, position):
    e.client.run(CId_SpotClipsByID(
        src_clips=ids, dst_track_name=track_name,
        dst_location_data=pt.SpotLocationData(
            location_type=pt.SLType_Start,
            location=pt.TimelineLocation(location=str(position), time_type=pt.TLType_Samples))))


def _swap(e, filepath, track_name, capture_start):
    """Clear the streamed recording that contains capture_start (its full
    extent), then spot the lossless file at capture_start. The file is
    imported first, so a failed import never leaves the streamed take
    cleared with nothing in its place."""
    filename = os.path.basename(filepath)
    ids = _import(e, filepath)
    streamed = next(((s, en) for s, en in _track_clips(e, track_name)
                     if s <= capture_start < en), None)
    mode = e.get_edit_mode().current_setting
    if mode in SHUFFLE_MODES:
        # Clear in Shuffle pulls every later clip left — do it in Slip, then restore.
        e.set_edit_mode(pt.EMO_Slip)
    try:
        if streamed is None:
            print(f"[sync] no streamed clip at sample {capture_start} on "
                  f"'{track_name}' — placing {filename} without clearing", flush=True)
        else:
            e.select_tracks_by_name([track_name])
            e.set_timeline_selection(in_time=str(streamed[0]), out_time=str(streamed[1]),
                                     location_type=pt.TLType_Samples)
            got = tuple(int(x) for x in e.get_edit_selection(pt.TLType_Samples))
            if got == streamed:
                e.clear()
                print(f"[sync] cleared streamed take {streamed[0]}–{streamed[1]} "
                      f"on '{track_name}'", flush=True)
            else:
                # Timeline and edit selection aren't linked — Clear would hit
                # whatever the edit selection is. Leave the streamed clip.
                print(f"[sync] edit selection {got} ≠ requested {streamed} "
                      f"(Link Timeline and Edit Selection off?) — not clearing; "
                      f"{filename} will sit on top of the streamed take", flush=True)
        _spot(e, ids, track_name, capture_start)
        print(f"[sync] swapped {filename} in at sample {capture_start} on "
              f"'{track_name}'", flush=True)
    finally:
        if mode in SHUFFLE_MODES:
            e.set_edit_mode(mode)


def place_take(filepath, fallback_track=0):
    """Swap the lossless take in for the streamed recording at the position
    the capture began; with no capture info, spot it on fallback_track at the
    timeline selection. Returns "swapped", "inserted" or "not_running"."""
    filename = os.path.basename(filepath)
    if not alive():
        print(f"[sync] Pro Tools (PTSL) not reachable or no session open — "
              f"{filename} NOT placed. Open the session and use Sync now.", flush=True)
        return "not_running"
    cap = _read_fresh_json(CAPTURE_FILE)
    try:
        os.remove(CAPTURE_FILE)  # consume: a later, unrelated file must not reuse it
    except OSError:
        pass
    if cap and cap.get("track"):
        print(f"[sync] swap info: '{cap['track']}', sample {cap['capture_start']} "
              f"(from {CAPTURE_FILE})", flush=True)
        try:
            with _lock:
                _swap(_eng(), filepath, cap["track"], cap["capture_start"])
            return "swapped"
        except Exception as e:
            print(f"[sync] swap failed ({e}) — falling back to insert", flush=True)
    else:
        print(f"[sync] no swap info ({CAPTURE_FILE} missing — no recording this "
              f"session, or already consumed) — falling back to insert", flush=True)

    tracks = get_tracks()
    track_name = next((t["name"] for t in tracks if t["index"] == fallback_track), None)
    if track_name is None:
        print(f"[sync] no track {fallback_track} in the session — {filename} NOT placed",
              flush=True)
        return "not_running"
    try:
        with _lock:
            e = _eng()
            _spot(e, _import(e, filepath), track_name, _selection_in_samples(e))
        print(f"[sync] inserted {filename} on '{track_name}' at the timeline selection",
              flush=True)
        return "inserted"
    except Exception as e:
        print(f"[sync] insert failed ({e}) — {filename} NOT placed", flush=True)
        return "not_running"


# ── Backing-track bounce ──────────────────────────────────────────────────────

_bounce = {"done": False, "path": None}


def start_bounce(selected_tracks=None):
    """Export the main output mix as 24-bit WAV in /tmp, in the background.
    (MP3 export fails through PTSL on Pro Tools 2026.4 — "Failed to procede
    with bounce" plus an error dialog — so it's WAV.) Tracks not
    in selected_tracks (0-based indices) are muted for the export and
    restored afterwards, as take_session.lua does for Reaper."""
    _bounce.update(done=False, path=None)
    threading.Thread(target=_do_bounce, args=(selected_tracks,), daemon=True).start()
    return True


def _do_bounce(selected_tracks):
    name = time.strftime("session_BT_%Y%m%d_%H%M%S")
    muted = []
    # A separate connection: ExportMix blocks until the bounce finishes, and
    # the shared one must stay free for the record watcher and timecode.
    e = None
    try:
        e = ptsl.Engine(company_name="Take", application_name="Take bounce",
                        address=f"localhost:{PTSL_PORT}")
        tracks = [t for t in e.track_list() if t.type in TIMELINE_TYPES]
        if selected_tracks:
            keep = {int(i) for i in selected_tracks}
            muted = [t.name for t in tracks
                     if t.index - 1 not in keep and not t.track_attributes.is_muted]
            if muted:
                e.set_track_mute_state(muted, True)
        end = max((en for t in tracks for _, en in _track_clips(e, t.name)), default=0)
        if end <= 0:
            raise RuntimeError("the session has no clips to bounce")
        src = CId_GetExportMixSourceList(type=pt.EMSType_Output)
        e.client.run(src)
        if not src.response or not src.response.source_list:
            raise RuntimeError("no output to bounce from")
        rate = {44100: pt.SR_44100, 48000: pt.SR_48000, 88200: pt.SR_88200,
                96000: pt.SR_96000, 176400: pt.SR_176400, 192000: pt.SR_192000}.get(_sample_rate(e), pt.SR_48000)
        e.client.run(ops.CId_ExportMix(
            file_name=name, file_type=pt.EMFType_WAV,
            mix_source_list=[pt.EM_SourceInfo(source_type=pt.EMSType_Output,
                                              name=src.response.source_list[0])],
            audio_info=pt.EM_AudioInfo(export_format=pt.EF_Interleaved,
                                       delivery_format=pt.EM_DF_SingleFile,
                                       compression_type=pt.CT_PCM, bit_depth=pt.Bit24,
                                       sample_rate=rate),
            # Real path with a trailing slash (/tmp is a symlink).
            location_info=pt.EM_LocationInfo(file_destination=pt.EM_FD_Directory,
                                             directory=os.path.realpath("/tmp") + "/",
                                             import_after_bounce=pt.TB_False),
            offline_bounce=pt.TB_True,
            start_time=pt.TimelineLocation(location="0", time_type=pt.TLType_Samples),
            end_time=pt.TimelineLocation(location=str(end), time_type=pt.TLType_Samples)))
        found = sorted(glob.glob(os.path.join(os.path.realpath("/tmp"), name + "*")))
        _bounce["path"] = found[0] if found else None
        if not found:
            print(f"Bounce: ExportMix finished but /tmp/{name}* wasn't written", flush=True)
    except Exception as x:
        print(f"Bounce: Pro Tools export failed — {x}", flush=True)
    finally:
        if e is not None:
            try:
                if muted:
                    e.set_track_mute_state(muted, False)
            finally:
                e.close()
        _bounce["done"] = True


def bounce_signalled():
    return _bounce["done"]


def bounce_output_path():
    return _bounce["path"]
