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
STATE_CACHE  = 0.005  # seconds — timecode and record_watcher share transport reads
# Deadline for the reads Take polls (transport, selection, session). py-ptsl
# sends every call with no gRPC deadline, and a modal dialog in Pro Tools can
# leave a call unanswered indefinitely — which would freeze the timecode, the
# record watcher and the cursor mirror behind the shared lock. A read
# normally answers in ~4 ms.
READ_TIMEOUT = 1.0    # seconds
# Where the artist's live stream is played so Pro Tools can record it. PTSL
# can't report the Playback Engine or track inputs, so this is configured.
# It must NOT be Pro Tools' Playback Engine device itself: Pro Tools takes that
# device over and audio other apps send to it never arrives (verified with
# Audio Bridge 16). Audio Bridge 2-A passes other apps' audio through to its
# inputs; Pro Tools records it when its Playback Engine includes 2-A (e.g. an
# aggregate device).
STREAM_DEVICE = os.environ.get("TAKE_STREAM_DEVICE", "Pro Tools Audio Bridge 2-A")

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


class _DeadlineStub:
    """py-ptsl's gRPC stub, with an optional deadline on each request (it
    sets none). `timeout` is set by _call, under the lock, per call."""

    def __init__(self, stub):
        self._stub = stub
        self.timeout = None

    def SendGrpcRequest(self, request):
        return self._stub.SendGrpcRequest(request, timeout=self.timeout)

    def __getattr__(self, name):
        return getattr(self._stub, name)


def _eng():
    """The shared Engine, (re)connecting if needed. Raises when Pro Tools
    isn't reachable."""
    global _engine
    if _engine is None:
        if not _port_open():
            raise ConnectionError("Pro Tools (PTSL) is not running")
        _engine = ptsl.Engine(company_name="Take", application_name="Take",
                              address=f"localhost:{PTSL_PORT}")
        _engine.client.raw_client = _DeadlineStub(_engine.client.raw_client)
    return _engine


def _call(fn, default=None, timeout=None):
    """Run fn(engine) under the lock, each PTSL request in it limited to
    `timeout` seconds (None = no limit, for long edits and imports).
    Connection loss resets the engine so the next call reconnects; a timeout
    doesn't (Pro Tools is busy, not gone). Any PTSL error returns `default`."""
    global _engine
    with _lock:
        stub = None
        try:
            e = _eng()
            stub = e.client.raw_client
            stub.timeout = timeout
            return fn(e)
        except grpc.RpcError as x:
            if x.code() != grpc.StatusCode.DEADLINE_EXCEEDED:
                _engine = None
            return default
        except (CommandError, ConnectionError):
            return default
        finally:
            if stub is not None:
                stub.timeout = None


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

def stream_device():
    return STREAM_DEVICE


_alive = {"t": 0.0, "value": False}


def alive():
    """PTSL answers and a session is open (nothing Take does works without
    one). Cached briefly — this is polled at 20 Hz."""
    now = time.time()
    if now - _alive["t"] < ALIVE_CACHE:
        return _alive["value"]
    value = _port_open() and _call(lambda e: bool(e.session_name()), False, READ_TIMEOUT)
    _alive.update(t=now, value=bool(value))
    return _alive["value"]


# ── Transport and session state ───────────────────────────────────────────────

# t: when the read was issued; read_at: midpoint of the call, when the
# reported state was current; prev_read_at: the read before that.
_state = {"t": 0.0, "value": None, "read_at": 0.0, "prev_read_at": 0.0}
_roll = {"playing": False, "t0": 0.0, "in_sec": 0.0}  # this process's play estimate
CURSOR_REREAD = 0.2   # seconds between reads of the engineer's cursor (selection)
_cursor = {"sec": None, "read_t": 0.0}
_was_recording = {"value": False}


def _transport_state():
    now = time.time()
    if now - _state["t"] >= STATE_CACHE:
        value = _call(lambda e: e.transport_state(), None, READ_TIMEOUT)
        _state.update(t=now, value=value, prev_read_at=_state["read_at"],
                      read_at=(now + time.time()) / 2)
    return _state["value"]


def _sample_rate(e):
    return e.session_sample_rate() or 48000


def _selection_in_samples(e):
    return int(e.get_timeline_selection(pt.TLType_Samples)[0])


def _selection_in_seconds(default):
    return _call(lambda e: _selection_in_samples(e) / _sample_rate(e), default, READ_TIMEOUT)


def get_cursor():
    """The engineer's cursor: the timeline selection's in point (seconds),
    re-read every 0.2 s whether or not the transport is rolling. None until
    the first read succeeds."""
    now = time.time()
    if now - _cursor["read_t"] >= CURSOR_REREAD:
        _cursor["read_t"] = now
        sec = _selection_in_seconds(None)
        if sec is not None:
            _cursor["sec"] = sec
    return _cursor["sec"]


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
        # Pro Tools started somewhere between the last read that said stopped
        # and this one: take the midpoint (±half a poll — 5 ms at timecode's
        # 10 ms polling). Stamped from the reads, not after the selection
        # read below, which takes another few ms.
        prev, now_read = _state["prev_read_at"], _state["read_at"]
        started = (prev + now_read) / 2 if 0 < now_read - prev <= 0.05 else now_read
        in_sec = _selection_in_seconds(_roll["in_sec"])
        _roll.update(playing=True, t0=started, in_sec=in_sec)
    elif not playing:
        _roll["playing"] = False
        cursor = get_cursor()   # stopped: the timecode position is the cursor
        if cursor is not None:
            _roll["in_sec"] = cursor
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
                                "sr": _sample_rate(e)}, None, READ_TIMEOUT)
        if info:
            info["t"] = seen_at
            _write_json(RECORD_FILE, info)
    _was_recording["value"] = recording
    return recording


def get_tracks():
    """[{index, name, armed}] for timeline tracks (audio, aux, instrument,
    MIDI). index is 0-based in session order; Pro Tools addresses tracks by
    name, so names are what the rest of this module uses."""
    tracks = _call(lambda e: e.track_list(), [], READ_TIMEOUT) or []
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
    return _call(read, [], READ_TIMEOUT) or []


# ── Transport commands ────────────────────────────────────────────────────────

def start_recording(track=0, capture_pos=None):
    """The artist's capture just began. If Pro Tools is recording (the
    engineer pressed Record), work out where on the timeline that is and save
    it for place_take(). capture_pos (seconds), when the artist's backing
    track was playing, is where they were in it at the file's first sample —
    where the take belongs. Without it, fall back to Pro Tools' position now,
    which is late by the round trip plus the audio latencies on both ends. Take doesn't start Pro Tools recording itself: the
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
    estimate = rec["rec_in"] + round((time.time() - rec["t"]) * rec["sr"])
    if capture_pos is not None:
        capture_start = round(capture_pos * rec["sr"])
        print(f"[capture] artist heard {capture_pos:.3f} s as capture began; "
              f"Pro Tools was at {estimate / rec['sr']:.3f} s "
              f"({(estimate - capture_start) / rec['sr'] * 1000:+.0f} ms)", flush=True)
    else:
        capture_start = estimate
        print("[capture] no backing-track position from the artist — using "
              "Pro Tools' position (late by the round trip)", flush=True)
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
    """Import into the clip list and return the new clip ids. Pro Tools only
    accepts CopyAudio for a file already in the session's format and only
    ConvertAudio for one that isn't (the artist records at their audio
    device's rate), answering the wrong one with "No audio files were
    imported" — so try both. That same
    error also came back intermittently for files that import fine moments
    later, so the pair is tried twice, half a second apart."""
    errors = []
    for attempt, operation in enumerate((pt.CopyAudio, pt.ConvertAudio) * 2):
        if attempt == 2:
            time.sleep(0.5)
        imp = CId_ImportAudioToClipList(file_list=[filepath], audio_operations=operation)
        try:
            e.client.run(imp)
        except CommandError as x:
            errors.append(str(x).splitlines()[0])
            continue
        ids = [c for entry in imp.response.file_list
               for f in entry.destination_file_list for c in f.clip_id_list]
        if ids:
            return ids
        errors += [f"{f.file_path}: {f.failure_message}" for f in imp.response.failure_list]
    raise RuntimeError(f"import produced no clip ({'; '.join(errors) or 'no reason given'})")


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
    """Export the main output mix as MP3 (256 kbps CBR) in /tmp, in the
    background. The MP3 encoding options must be passed explicitly: without
    them Pro Tools opens its MP3 settings dialog and the export waits on it
    (then fails with "Failed to procede with bounce"). Tracks not
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
        e.client.run(ops.CId_ExportMix(
            file_name=name, file_type=pt.EMFType_MP3,
            mix_source_list=[pt.EM_SourceInfo(source_type=pt.EMSType_Output,
                                              name=src.response.source_list[0])],
            audio_info=pt.EM_AudioInfo(export_format=pt.EF_Interleaved,
                                       delivery_format=pt.EM_DF_SingleFile),
            audio_encoding_options=pt.AudioEncodingOptions(
                encoding_options_mp3=pt.MP3EncodingOptions(
                    bit_rate=pt.MP3EOCBRate_256kbps, quality=pt.MP3EOQuality_Highest)),
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
