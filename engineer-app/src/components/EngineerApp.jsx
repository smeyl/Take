import { useState, useEffect, useRef } from "react";
import CueMix, { sendCue } from "./CueMix";
import { LogoMark, GearIcon, RefreshIcon, ChevronIcon, PopOutIcon, BackIcon } from "./icons";

const RELAY          = "http://localhost:5010";
const FILE_RECEIVER  = "http://localhost:5001";
// Transport (5004) and stream quality (5007) run on the artist's machine —
// the relay proxies these to the artist IP of the current session.
const ARTIST         = `${RELAY}/artist`;

const STREAM_Q_MAP = { "PCM16": "PCM16", "PCM24": "PCM24", "Float32": "Float32" };
const SYNC_FMT_MAP = { "FLAC": "FLAC", "WAV 24": "WAV24", "WAV 32f": "WAV32f" };
// Static estimates from the design reference — nothing measures per-quality
// latency yet, so these are placeholders, not live numbers.
const STREAM_Q_LATENCY = { "PCM16": "~9ms", "PCM24": "~14ms", "Float32": "~22ms" };

const TAKE_STATUS = {
  live:    { dot: "#f76464", color: "#f76464", label: "LIVE" },
  syncing: { dot: "#e7b23e", color: "#e7b23e", label: "SYNCING" },
  done:    { dot: "#2dd4bf", color: "#2dd4bf", label: null },  // label = file type
  pending: { dot: "#4d4d52", color: "#4d4d52", label: "PENDING" },
};

export default function EngineerApp({ cue, setCue, sessionCode, onBack }) {
  const [recording, setRecording]   = useState(false);
  const [takeCount, setTakeCount]   = useState(0);
  const [dots, setDots]             = useState({ artist: false, reaper: false });
  // "main" | "settings" — Settings swaps the window content in place.
  const [view, setView]             = useState("main");
  // True while the cue knobs live in their own detached window.
  const [cuePopped, setCuePopped]   = useState(false);
  const [cueOpen, setCueOpen]       = useState(true);  // chevron collapse
  // Reconnect icon spinners, per connection row.
  const [rechecking, setRechecking] = useState({ daw: false, artist: false });
  const [streamQ, setStreamQ]       = useState("PCM16");
  const [syncFmt, setSyncFmt]       = useState("WAV 24");
  const [receivedTakes, setReceivedTakes] = useState([]);
  const [tracks, setTracks]         = useState([]);
  const [autoSync, setAutoSync]     = useState(true);
  // Pre-roll countdown before capture actually starts (null = not counting).
  // Sourced from transport.py so it mirrors the artist's 3-2-1 exactly.
  const [countdown, setCountdown]   = useState(null);
  const countdownRef                = useRef(null);
  // Track name each take was recorded on, captured the first time it's seen.
  const takeTrackNames              = useRef({});

  const stopCountdown = () => {
    if (countdownRef.current) { clearInterval(countdownRef.current); countdownRef.current = null; }
    setCountdown(null);
  };

  // Smooth local ticker seeded by the backend's countdown value. Guarded so the
  // status poll can call it repeatedly without double-starting.
  const startCountdown = (seconds) => {
    if (countdownRef.current || !seconds) return;
    setCountdown(seconds);
    countdownRef.current = setInterval(() => {
      setCountdown((c) => {
        if (c === null || c <= 1) {
          clearInterval(countdownRef.current);
          countdownRef.current = null;
          return null;
        }
        return c - 1;
      });
    }, 1000);
  };

  useEffect(() => stopCountdown, []);  // clear the interval on unmount

  const updateCue = (k, v) => {
    setCue(c => ({ ...c, [k]: v }));
    sendCue(k, v);
  };

  const handleEndSession = async () => {
    if (!window.confirm("End session?")) return;
    try {
      await fetch(`${RELAY}/session/${sessionCode}`, { method: "DELETE" });
    } catch {}
    onBack();
  };

  // ── Cue mix pop-out ──────────────────────────────────────────────────────────
  // window.take is the Electron preload bridge (absent in a plain browser).
  const canPopOut = Boolean(window.take);

  const handlePopOut = () => {
    window.take.openCuePopout(cue);
    setCuePopped(true);
  };

  useEffect(() => {
    if (!window.take) return;
    const offChanged = window.take.onCueChanged(setCue);
    const offClosed  = window.take.onCuePopoutClosed(() => setCuePopped(false));
    return () => {
      offChanged();
      offClosed();
      window.take.closeCuePopout();  // leaving the session closes the popout too
    };
  }, []);

  // ── Settings ─────────────────────────────────────────────────────────────────
  const handleStreamQ = async (label) => {
    setStreamQ(label);
    try {
      await fetch(`${ARTIST}/stream-quality`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ quality: STREAM_Q_MAP[label] }),
      });
    } catch {}
  };

  const handleSyncFmt = async (label) => {
    setSyncFmt(label);
    try {
      await fetch(`${FILE_RECEIVER}/sync-format`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ format: SYNC_FMT_MAP[label] }),
      });
    } catch {}
  };

  const handleAutoSync = async () => {
    const next = !autoSync;
    setAutoSync(next);
    try {
      await fetch(`${RELAY}/auto-sync`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: next }),
      });
    } catch {}
  };

  const handleManualSync = async (name) => {
    try {
      await fetch(`${RELAY}/takes/${encodeURIComponent(name)}/swap`, { method: "POST" });
    } catch {}
  };

  // ── Connection checks ────────────────────────────────────────────────────────
  // Polled every 3s below. There is no active reconnect logic anywhere on the
  // engineer side — the artist re-heartbeats on its own and take_session.lua
  // is detected by its export file — so the reconnect icons re-run these
  // same checks immediately instead of waiting for the next poll.
  const checkArtist = async () => {
    try {
      const r = await fetch(`${RELAY}/session/${sessionCode}/status`);
      if (r.ok) {
        const data = await r.json();
        setDots(d => ({ ...d, artist: Boolean(data.artist) }));
      }
    } catch {
      setDots(d => ({ ...d, artist: false }));
    }
  };

  const checkDaw = async () => {
    try {
      const rr = await fetch(`${RELAY}/reaper/status`, { signal: AbortSignal.timeout(3000) });
      if (rr.ok) {
        const rd = await rr.json();
        setDots(d => ({ ...d, reaper: Boolean(rd.reachable) }));
      }
    } catch {
      setDots(d => ({ ...d, reaper: false }));
    }
  };

  const handleRecheck = async (key, check) => {
    setRechecking(r => ({ ...r, [key]: true }));
    // Minimum spin so the click visibly registers even on an instant reply.
    await Promise.all([check(), new Promise(res => setTimeout(res, 500))]);
    setRechecking(r => ({ ...r, [key]: false }));
  };

  const handleRecheckAll = () => Promise.all([
    handleRecheck("daw", checkDaw),
    handleRecheck("artist", checkArtist),
  ]);

  // ── Polling ──────────────────────────────────────────────────────────────────
  useEffect(() => {
    const pollTransport = async () => {
      try {
        const r = await fetch(`${ARTIST}/status`);
        if (r.ok) {
          const data = await r.json();
          setRecording(data.recording);
          setTakeCount(data.take);
          // Pick up an in-progress countdown and clear it once capture is done.
          if (data.countdown > 0) startCountdown(data.countdown);
          else if (!data.recording) stopCountdown();
        }
      } catch {}
    };

    const pollTakes = async () => {
      try {
        const r = await fetch(`${FILE_RECEIVER}/takes`);
        if (r.ok) setReceivedTakes(await r.json());
      } catch {}
    };

    const pollSession = () => Promise.all([checkArtist(), checkDaw()]);

    pollTransport();
    pollTakes();
    pollSession();
    const t1 = setInterval(pollTransport, 2000);
    const t2 = setInterval(pollTakes, 2000);
    const t3 = setInterval(pollSession, 3000);
    return () => { clearInterval(t1); clearInterval(t2); clearInterval(t3); };
  }, [sessionCode]);

  // Reaper track list with arm state (kept current by take_session.lua) — used
  // for the armed-track readout and to name takes.
  useEffect(() => {
    const pollTracks = () => {
      fetch(`${RELAY}/tracks`)
        .then(r => r.ok ? r.json() : [])
        .then(data => { if (data.length) setTracks(data); })
        .catch(() => {});
    };
    pollTracks();
    const id = setInterval(pollTracks, 5000);
    return () => clearInterval(id);
  }, []);

  // ── Derived state ────────────────────────────────────────────────────────────
  // Reaper records onto whichever track the engineer armed, and the swap
  // follows the first armed one (take_session.lua), so name takes after it.
  // Names are display-only; files keep their T<n>_ names.
  const armedTracks = tracks.filter(t => t.armed);
  const recordTrackName = armedTracks[0]?.name || null;
  const perTrackCount = {};
  const takes = Array.from({ length: takeCount }, (_, i) => {
    const n = i + 1;
    if (!takeTrackNames.current[n] && recordTrackName) takeTrackNames.current[n] = recordTrackName;
    const trackName = takeTrackNames.current[n];
    let name = `T${n}`;
    if (trackName) {
      perTrackCount[trackName] = (perTrackCount[trackName] || 0) + 1;
      name = `${trackName}_${String(perTrackCount[trackName]).padStart(2, "0")}`;
    }
    const isLive = recording && n === takeCount;
    const received = receivedTakes.find(t => t.name.startsWith(`T${n}_`));
    let status;
    if (isLive)         status = "live";
    else if (received)  status = received.status || "syncing";
    else                status = "pending"; // recorded, file not yet arrived
    const ext = received ? received.name.split(".").pop().toUpperCase() : null;
    return { n, name, s: status, file: received ? received.name : null, ext };
  }).reverse();  // newest first

  const displayCode = sessionCode
    ? `${sessionCode.slice(0, 2)} · ${sessionCode.slice(2, 4)} · ${sessionCode.slice(4, 6)}`
    : "";

  const artistStatus = countdown !== null ? [true, `Starting in ${countdown}…`]
    : recording ? [true, "Recording"]
    : dots.artist ? [true, "Connected"]
    : [false, "Not connected"];
  const dawStatus = !dots.reaper ? [false, "Not running"]
    : recording ? [true, "Recording"]
    : [true, "Connected"];
  // The DAW row reports the Reaper take_session.lua liveness check, so it's
  // labelled "Reaper" until a real Pro Tools integration replaces that check.
  const connRows = [
    ["daw",    "Reaper", dawStatus,    checkDaw,    "#2dd4bf"],
    ["artist", "Artist", artistStatus, checkArtist, "#4f8fff"],
  ];

  if (view === "settings") {
    return (
      <div className="win">
        <div className="hdr hdr-settings" style={{ WebkitAppRegion: "drag" }}>
          <button className="hdr-btn" style={{ WebkitAppRegion: "no-drag" }} aria-label="Back to session" onClick={() => setView("main")}>
            <BackIcon />
          </button>
          <span className="hdr-title">Settings</span>
        </div>

        <div className="set-body">
          <fieldset className="set-group" style={{ gap: 9 }}>
            <legend className="set-legend">Recording format</legend>
            <div className="seg-row">
              {Object.keys(SYNC_FMT_MAP).map(f => (
                <button key={f} className={`seg ${syncFmt === f ? "on-teal" : ""}`} onClick={() => handleSyncFmt(f)}>{f}</button>
              ))}
            </div>
          </fieldset>

          <fieldset className="set-group" style={{ gap: 6 }}>
            <legend className="set-legend">Stream quality</legend>
            <div className="seg-row">
              {Object.keys(STREAM_Q_MAP).map(q => (
                <button key={q} className={`seg ${streamQ === q ? "on-blue" : ""}`} onClick={() => handleStreamQ(q)}>{q}</button>
              ))}
            </div>
            <div className="seg-row">
              {Object.keys(STREAM_Q_MAP).map(q => (
                <span key={q} className="seg-note" style={{ color: streamQ === q ? "#4f8fff" : "#4d4d52" }}>{STREAM_Q_LATENCY[q]}</span>
              ))}
            </div>
            <span className="set-hint">Estimated round-trip time to the artist — same measurement regardless of which option is selected</span>
          </fieldset>

          <div className="set-toggle-row">
            <div className="set-toggle-text">
              <span className="set-toggle-title">Auto-sync takes</span>
              <span className="set-toggle-sub">Swap the lossless file in automatically</span>
            </div>
            <div className={`switch ${autoSync ? "on" : ""}`} title={autoSync ? "On" : "Off"} onClick={handleAutoSync} />
          </div>
        </div>

        <div className="foot">
          <button className="foot-btn" onClick={handleRecheckAll}>
            <span className={rechecking.daw || rechecking.artist ? "spin" : ""} style={{ display: "flex" }}>
              <RefreshIcon size={13} color="#d4d4d6" />
            </span>
            Reconnect all
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="win">
      {/* Title bar */}
      <div className="hdr" style={{ WebkitAppRegion: "drag" }}>
        <div className="logo">
          <LogoMark />
          <span className="logo-word">TAKE</span>
        </div>
        <button className="hdr-btn" style={{ WebkitAppRegion: "no-drag" }} aria-label="Settings" onClick={() => setView("settings")}>
          <GearIcon />
        </button>
      </div>

      {/* Session code */}
      <div className="code-block">
        <span className="code-label">Session code</span>
        <span className="code-val">{displayCode}</span>
      </div>

      {/* Connections */}
      <div className="conn-block">
        {connRows.map(([key, label, [on, status], check, accent]) => (
          <div key={key} className="conn-row">
            <div className="conn-left">
              <span className="conn-name">{label}</span>
              {key === "daw" && dots.reaper && (
                <span className="conn-armed" title="Track armed in Reaper — takes record here">
                  {armedTracks.length === 0
                    ? "no track armed"
                    : armedTracks[0].name + (armedTracks.length > 1 ? ` +${armedTracks.length - 1}` : "")}
                </span>
              )}
            </div>
            <div className="conn-right">
              <div className="conn-state">
                <div className="conn-dot" style={{ background: on ? accent : "#4d4d52" }} />
                <span className="conn-status" style={{ color: on ? accent : "#4d4d52" }}>{status}</span>
              </div>
              <button
                className={`recon-btn ${rechecking[key] ? "spin" : ""}`}
                aria-label={`Reconnect ${label}`}
                onClick={() => !rechecking[key] && handleRecheck(key, check)}
              >
                <RefreshIcon />
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Cue mix */}
      <div className="cue-block">
        <div className="cue-hdr">
          <button
            className="cue-toggle"
            aria-expanded={cueOpen && !cuePopped}
            onClick={() => setCueOpen(o => !o)}
            disabled={cuePopped}
          >
            <span className="cue-chev" style={{ transform: cueOpen && !cuePopped ? "none" : "rotate(-90deg)" }}><ChevronIcon /></span>
            <span className="sect-label">Cue mix</span>
          </button>
          {cuePopped
            ? <span className="cue-away">In separate window</span>
            : canPopOut && (
                <button className="popout-btn" aria-label="Detach Cue Mix into its own window" onClick={handlePopOut}>
                  <PopOutIcon />
                  Pop out
                </button>
              )}
        </div>
        {!cuePopped && cueOpen && <CueMix cue={cue} onChange={updateCue} />}
      </div>

      {/* Takes */}
      <div className="takes-block">
        <div className="takes-hdr"><span className="sect-label">Takes</span></div>
        <div className="takes-list">
          {takes.length === 0 && <div className="take-empty">No takes yet</div>}
          {takes.map(t => {
            const st = TAKE_STATUS[t.s] || TAKE_STATUS.syncing;
            const manual = t.s === "syncing" && !autoSync && t.file;
            return (
              <div key={t.n} className="take-row">
                <div className="take-left">
                  <div className="take-dot" style={{ background: st.dot }} />
                  <span className="take-name" style={{ color: t.s === "live" ? "#e8e8ea" : "#c4c4c8" }}>{t.name}</span>
                </div>
                {manual
                  ? <button
                      className="take-status take-sync"
                      style={{ color: st.color }}
                      title="Place this take on the Reaper timeline"
                      onClick={() => handleManualSync(t.file)}
                    >SYNC NOW</button>
                  : <span className="take-status" style={{ color: st.color }}>{st.label || t.ext}</span>}
              </div>
            );
          })}
        </div>
      </div>

      <div className="foot">
        <button className="foot-btn" style={{ fontWeight: 500 }} onClick={handleEndSession}>End Session</button>
      </div>
    </div>
  );
}
