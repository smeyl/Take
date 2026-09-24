import { useState, useEffect, useRef } from "react";
import C from "../constants/colors";
import CueMix, { sendCue } from "./CueMix";
import WaveCanvas from "./WaveCanvas";
import DetailsPanel from "./DetailsPanel";

const RELAY          = "http://localhost:5010";
const FILE_RECEIVER  = "http://localhost:5001";
const BOUNCE         = "http://localhost:5006";
// Transport (5004) and stream quality (5007) run on the artist's machine —
// the relay proxies these to the artist IP of the current session.
const ARTIST         = `${RELAY}/artist`;

export default function EngineerApp({ cue, setCue, sessionCode, onBack }) {
  const [recording, setRecording]   = useState(false);
  const [takeCount, setTakeCount]   = useState(0);
  const [dots, setDots]             = useState({ artist: false, reaper: false });
  // "main" | "settings" — Settings swaps the window content in place.
  const [view, setView]             = useState("main");
  // True while the cue knobs live in their own detached window.
  const [cuePopped, setCuePopped]   = useState(false);
  // Reconnect icon spinners, per connection row.
  const [rechecking, setRechecking] = useState({ daw: false, artist: false });
  const [streamQ, setStreamQ]       = useState("PCM 16");
  const [syncFmt, setSyncFmt]       = useState("WAV 24");
  const [btQ, setBtQ]               = useState("MP3 256");
  const [showDetails, setShowDetails] = useState(false);
  const [receivedTakes, setReceivedTakes] = useState([]);
  const [latencyMs, setLatencyMs]   = useState(null);
  const [bouncing, setBouncing]     = useState(false);
  // Last bounce as reported by the bounce server: { file, result } — file is
  // the real rendered filename (take_session.lua names each render uniquely).
  const [lastBounce, setLastBounce] = useState({ file: null, result: null });
  const [levels, setLevels]         = useState({ l: -60, r: -60 });
  const [destTracks, setDestTracks] = useState([]);
  const [destTrack, setDestTrack]   = useState(0);
  const [punchActive, setPunchActive] = useState(false);
  // Set of track indices selected for the next bounce; initialised from destTracks.
  const [bounceTracks, setBounceTracks] = useState(new Set());
  const [autoSync, setAutoSync]         = useState(true);
  // Pre-roll countdown before capture actually starts (null = not counting).
  // Sourced from transport.py so it mirrors the artist's 3-2-1 exactly.
  const [countdown, setCountdown]       = useState(null);
  const countdownRef                    = useRef(null);

  const stopCountdown = () => {
    if (countdownRef.current) { clearInterval(countdownRef.current); countdownRef.current = null; }
    setCountdown(null);
  };

  // Smooth local ticker seeded by the backend's countdown value. Guarded so the
  // click path and the status poll can both call it without double-starting.
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

  // Initialise bounce selection whenever the track list loads.
  useEffect(() => {
    if (destTracks.length > 0)
      setBounceTracks(new Set(destTracks.map(t => t.index)));
  }, [destTracks]);

  const updateCue = (k, v) => {
    setCue(c => ({ ...c, [k]: v }));
    sendCue(k, v);
  };

  // ── Transport actions ────────────────────────────────────────────────────────
  const handleRec = async () => {
    const endpoint = recording ? "stop" : "record";
    try {
      const r = await fetch(`${ARTIST}/${endpoint}`, { method: "POST" });
      if (r.ok) {
        const data = await r.json();
        setRecording(data.recording);
        if (data.take !== undefined) setTakeCount(data.take);
        // Start the countdown the instant we arm (zero poll latency for the
        // person who clicked); clear it when stopping or cancelling.
        if (endpoint === "record" && data.countdown) startCountdown(data.countdown);
        else if (endpoint === "stop") stopCountdown();
      }
    } catch {}
  };

  const handleBounceTrackToggle = async (index, checked) => {
    const updated = new Set(bounceTracks);
    if (checked) updated.add(index); else updated.delete(index);
    setBounceTracks(updated);
    try {
      await fetch(`${BOUNCE}/bounce/tracks`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tracks: [...updated] }),
      });
    } catch {}
  };

  const handleTrackSelect = async (index) => {
    setDestTrack(index);
    try {
      // Relay remembers the selection — Reaper is only touched when
      // recording starts (the record command arms this track).
      await fetch(`${RELAY}/track/select/${index}`, { method: "POST" });
    } catch {}
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

  const STREAM_Q_MAP = { "PCM 16": "PCM16", "PCM 24": "PCM24", "Float 32": "Float32" };

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

  const SYNC_FMT_MAP = { "FLAC": "FLAC", "WAV 24": "WAV24", "WAV 32f": "WAV32f" };

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

  const handlePunch = async () => {
    if (punchActive) {
      try {
        await fetch(`${RELAY}/punch`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ in: 0, out: 0, active: false }),
        });
      } catch {}
      setPunchActive(false);
    } else {
      let punchIn = 0;
      try {
        const r = await fetch(`${RELAY}/timecode`);
        if (r.ok) punchIn = (await r.json()).pos || 0;
      } catch {}
      const punchOut = punchIn + 8;
      try {
        await fetch(`${RELAY}/punch`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ in: punchIn, out: punchOut }),
        });
      } catch {}
      setPunchActive(true);
    }
  };

  const handleRTZ = async () => {
    try {
      await fetch(`${RELAY}/reaper/rtz`, { method: "POST" });
    } catch {}
  };

  const handleManualSync = async (name) => {
    try {
      await fetch(`${RELAY}/takes/${encodeURIComponent(name)}/swap`, { method: "POST" });
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

  const handleBounce = async () => {
    if (bouncing) return;
    setBouncing(true);
    try {
      await fetch(`${BOUNCE}/bounce`, { method: "POST" });
    } catch {
      setBouncing(false);
    }
  };

  // ── Connection checks ────────────────────────────────────────────────────────
  // Polled every 3s below. There is no active reconnect logic anywhere on the
  // engineer side — the artist re-heartbeats on its own and take_session.lua
  // is detected by its export file — so the reconnect icons re-run these
  // same checks immediately instead of waiting for the next poll.
  const checkArtist = async () => {
    try {
      const t0 = Date.now();
      const r = await fetch(`${RELAY}/session/${sessionCode}/status`);
      if (r.ok) {
        setLatencyMs(Date.now() - t0);
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

  // ── Polling ──────────────────────────────────────────────────────────────────
  useEffect(() => {
    const pollTransport = async () => {
      try {
        const r = await fetch(`${ARTIST}/status`);
        if (r.ok) {
          const data = await r.json();
          setRecording(data.recording);
          setTakeCount(data.take);
          // Backup path to the click handler: pick up an in-progress countdown
          // (e.g. after a reload) and clear it once capture is truly done.
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

    const pollSession = async () => {
      await Promise.all([checkArtist(), checkDaw()]);
      try {
        const rb = await fetch(`${BOUNCE}/bounce/status`);
        if (rb.ok) {
          const bd = await rb.json();
          setBouncing(bd.bouncing);
          setLastBounce({ file: bd.file || null, result: bd.result || null });
        }
      } catch {}
    };

    pollTransport();
    pollTakes();
    pollSession();
    const t1 = setInterval(pollTransport, 2000);
    const t2 = setInterval(pollTakes, 2000);
    const t3 = setInterval(pollSession, 3000);
    return () => { clearInterval(t1); clearInterval(t2); clearInterval(t3); };
  }, [sessionCode]);

  useEffect(() => {
    const poll = async () => {
      try {
        const r = await fetch(`${ARTIST}/levels`);
        if (r.ok) setLevels(await r.json());
      } catch {}
    };
    const id = setInterval(poll, 100);
    return () => clearInterval(id);
  }, []);

  // Track list for the destination dropdown and bounce checkboxes —
  // take_session.lua keeps the export current, so poll instead of fetching once.
  useEffect(() => {
    const pollTracks = () => {
      fetch(`${RELAY}/tracks`)
        .then(r => r.ok ? r.json() : [])
        .then(data => { if (data.length) setDestTracks(data); })
        .catch(() => {});
    };
    pollTracks();
    const id = setInterval(pollTracks, 5000);
    return () => clearInterval(id);
  }, []);

  const takesScrollRef = useRef(null);
  useEffect(() => {
    if (takesScrollRef.current) {
      takesScrollRef.current.scrollTop = takesScrollRef.current.scrollHeight;
    }
  }, [takeCount, view]);  // view: the list remounts when leaving Settings

  // ── Derived state ────────────────────────────────────────────────────────────
  const takes = Array.from({ length: takeCount }, (_, i) => {
    const n = i + 1;
    const isLive = recording && n === takeCount;
    const received = receivedTakes.find(t => t.name.startsWith(`T${n}_`));
    let status;
    if (isLive)         status = "live";
    else if (received)  status = received.status || "syncing";
    else                status = "pending"; // recorded, file not yet arrived
    return {
      id: received ? received.name.split("_")[0] : `T${n}`,
      s: status,
      name: received ? received.name : null,
    };
  });

  const lastFile = receivedTakes.length > 0 ? receivedTakes[receivedTakes.length - 1] : null;

  const displayCode = sessionCode
    ? `${sessionCode.slice(0, 2)} · ${sessionCode.slice(2, 4)} · ${sessionCode.slice(4, 6)}`
    : "";

  // The DAW row reports the Reaper take_session.lua liveness check, so it's
  // labelled "Reaper" until a real Pro Tools integration replaces that check.
  const artistStatus = countdown !== null ? ["r", `T${takeCount} in ${countdown}…`]
    : recording ? ["r", "Recording"]
    : dots.artist ? ["g", "Connected"]
    : ["d", "Not connected"];
  const dawStatus = !dots.reaper ? ["d", "Not running"]
    : recording ? ["r", "Recording"]
    : ["g", "Connected"];
  const connRows = [
    ["daw",    "Reaper",    dawStatus,    checkDaw,    "#2dd4bf"],
    ["artist", "Artist",    artistStatus, checkArtist, "#4f8fff"],
  ];

  return (
    <div className="eng-shell">
      <div className="eng-wrap">
        {/* Title bar */}
        <div className="eng-hdr" style={{ WebkitAppRegion: "drag" }}>
          {view === "settings" ? (
            <>
              <div className="icon-btn" style={{ WebkitAppRegion: "no-drag" }} title="Back" onClick={() => setView("main")}>←</div>
              <div className="eng-title">Settings</div>
            </>
          ) : (
            <>
              <div className="eng-logo">
                <svg width="26" height="18" viewBox="0 0 26 18" fill="none" aria-hidden="true">
                  <circle cx="9"  cy="9" r="7" stroke="#2dd4bf" strokeWidth="1.6" />
                  <circle cx="17" cy="9" r="7" stroke="#4f8fff" strokeWidth="1.6" />
                </svg>
                <div>T<span>ake</span></div>
              </div>
              <div className="icon-btn" style={{ WebkitAppRegion: "no-drag" }} title="Settings" onClick={() => setView("settings")}>⚙</div>
            </>
          )}
        </div>

        {view === "settings" ? (
          <div className="eng-body">
            <div className="ecol" style={{ flex: 1, gap: 14 }}>
              <div>
                <div className="sec-label">Stream quality</div>
                <div className="pill-grp">{["PCM 16", "PCM 24", "Float 32"].map(q => <div key={q} className={`pill ${streamQ === q ? "on" : ""}`} onClick={() => handleStreamQ(q)}>{q}</div>)}</div>
                <div style={{ height: 8 }} />
                <div className="sec-label">Sync format</div>
                <div className="pill-grp">{["FLAC", "WAV 24", "WAV 32f"].map(f => <div key={f} className={`pill ${syncFmt === f ? "on" : ""}`} onClick={() => handleSyncFmt(f)}>{f}</div>)}</div>
                <div style={{ height: 8 }} />
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <span className="sec-label" style={{ marginBottom: 0 }}>Auto-sync</span>
                  <div
                    className={`switch ${autoSync ? "on" : ""}`}
                    title={autoSync ? "On" : "Off"}
                    onClick={handleAutoSync}
                  />
                </div>
              </div>
            </div>
          </div>
        ) : (
          <>
            {/* Session code */}
            <div className="eng-code">
              <div className="sec-label" style={{ marginBottom: 2 }}>Session code</div>
              <div className="eng-code-val">{displayCode}</div>
            </div>

            <div className="eng-body">
              {/* Main column — connections, cue mix, takes */}
              <div className="ecol" style={{ flex: 1 }}>
                <div className="conn-rows">
                  {connRows.map(([key, label, [dot, status], check, accent]) => (
                    <div key={key} className="conn-row">
                      <span className="conn-row-name">{label}</span>
                      <div className={`dot ${dot}`} style={dot === "g" ? { background: accent, boxShadow: `0 0 6px ${accent}88` } : undefined} />
                      <span className="conn-row-status" style={{ color: dot === "g" ? accent : dot === "r" ? C.red : C.muted }}>{status}</span>
                      <div
                        className={`icon-btn sm ${rechecking[key] ? "spin" : ""}`}
                        title={`Re-check ${label} connection`}
                        onClick={() => !rechecking[key] && handleRecheck(key, check)}
                      >↻</div>
                    </div>
                  ))}
                </div>

                <div className="cue-sec">
                  <div className="cue-sec-hdr">
                    <div className="sec-label" style={{ marginBottom: 0 }}>Cue Mix</div>
                    {cuePopped
                      ? <span style={{ fontSize: 9, color: C.muted }}>In separate window</span>
                      : canPopOut && <div className="pill" onClick={handlePopOut}>Pop out ↗</div>}
                  </div>
                  {!cuePopped && <CueMix cue={cue} onChange={updateCue} />}
                </div>

                <div>
                  <div className="sec-label">Takes</div>
                  <div className="takes-scroll" ref={takesScrollRef}>
                    {takes.length === 0 && (
                      <div style={{ fontSize: 9, color: C.dim, fontStyle: "italic" }}>No takes yet</div>
                    )}
                    {takes.map(t => {
                      const color = t.s === "live" ? C.red : t.s === "syncing" ? C.amber : t.s === "done" ? C.green : C.muted;
                      return (
                        <div key={t.id} className={`take-row ${t.s === "live" ? "live" : ""}`}>
                          <div className="take-num" style={{ color }}>{t.id}</div>
                          <div className="take-wave">
                            <WaveCanvas
                              width={110} height={20}
                              color={color}
                              animated={t.s === "live"}
                              progress={1}
                            />
                          </div>
                          {t.s === "done"    && <div className="take-badge tb-wav">WAV</div>}
                          {t.s === "live"    && <div className="take-badge tb-live">LIVE</div>}
                          {t.s === "syncing" && (
                            !autoSync && t.name
                              ? <div
                                  className="take-badge tb-sync"
                                  style={{ cursor: "pointer" }}
                                  title="Place this take on the Reaper timeline"
                                  onClick={() => handleManualSync(t.name)}
                                >Sync now</div>
                              : <div className="take-badge tb-sync">SYNC</div>
                          )}
                          {t.s === "pending" && <div className="take-badge" style={{ color: C.muted, borderColor: C.dim, background: "transparent" }}>···</div>}
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>

              {/* Side column — existing session controls, unchanged */}
              <div className="ecol" style={{ width: 230, flexShrink: 0 }}>
                <div>
                  <div className="sec-label">Artist input</div>
                  {[["L", levels.l], ["R", levels.r]].map(([ch, db]) => {
                    const pct   = Math.max(0, (db + 60) / 60 * 100);
                    const color = db > -6 ? "#ff4f4f" : db > -12 ? "#ffb340" : "#3ddc84";
                    return (
                      <div key={ch}>
                        <div className="meter-lbl">
                          <span>{ch}</span>
                          <span style={{ color }}>{Math.round(db)}</span>
                        </div>
                        <div className="meter-bar">
                          <div className="meter-fill" style={{ width: `${pct}%`, background: color }} />
                        </div>
                      </div>
                    );
                  })}
                </div>
                <div>
                  <div className="sec-label">Transport</div>
                  {countdown !== null && (
                    <div
                      style={{
                        textAlign: "center", marginBottom: 6, padding: "6px 0 8px",
                        background: "#1a0808", border: `1px solid #5c1a1a`, borderRadius: 4,
                      }}
                    >
                      <div style={{ fontSize: 9, color: C.red, letterSpacing: "0.12em" }}>RECORDING IN</div>
                      <div style={{ fontSize: 34, fontWeight: 700, color: C.red, lineHeight: 1.05, fontVariantNumeric: "tabular-nums" }}>
                        {countdown}
                      </div>
                    </div>
                  )}
                  <div
                    className={`ebtn ebtn-rec ${recording ? "on" : ""}`}
                    style={{ width: "100%", textAlign: "center", marginBottom: 6 }}
                    onClick={handleRec}
                  >
                    {countdown !== null ? "■ Cancel" : recording ? "■ Stop" : "● Rec"}
                  </div>
                  <div style={{ display: "flex", gap: 6 }}>
                    <div
                      className={`ebtn ebtn-amber ${punchActive ? "on" : ""}`}
                      style={{ flex: 1, textAlign: "center" }}
                      onClick={handlePunch}
                    >{punchActive ? "⊡ Punch active" : "⊡ Punch in/out"}</div>
                    <div
                      className="ebtn ebtn-ghost"
                      style={{ width: 52, textAlign: "center", flexShrink: 0 }}
                      title="Return to zero — move the Reaper playhead to project start"
                      onClick={handleRTZ}
                    >⏮ RTZ</div>
                  </div>
                </div>
                <div>
                  <div className="sec-label">Destination track</div>
                  <select
                    value={destTrack}
                    onChange={e => handleTrackSelect(Number(e.target.value))}
                    style={{
                      width: "100%", background: C.raised, border: `1px solid ${C.border}`,
                      color: destTracks.length ? C.body : C.muted, borderRadius: 4,
                      padding: "4px 6px", fontSize: 9, fontFamily: "inherit", cursor: "pointer",
                    }}
                  >
                    {destTracks.length === 0
                      ? <option value={0}>No tracks — Reaper not connected</option>
                      : destTracks.map(t => (
                          <option key={t.index} value={t.index}>{t.name || `Track ${t.index + 1}`}</option>
                        ))
                    }
                  </select>
                </div>
                <div>
                  <div className="sec-label">Backing track</div>
                  <div style={{ fontSize: 9, color: C.muted, marginBottom: 4 }}>
                    {dots.reaper ? "Select Reaper tracks to include" : "Reaper not connected"}
                  </div>
                  <div className="track-check">
                    {destTracks.length === 0
                      ? <div style={{ fontSize: 9, color: C.dim, fontStyle: "italic" }}>
                          {dots.reaper ? "No tracks found" : "Connect Reaper to load tracks"}
                        </div>
                      : destTracks.map(t => (
                          <label key={t.index} className="track-item">
                            <input
                              type="checkbox"
                              checked={bounceTracks.has(t.index)}
                              onChange={e => handleBounceTrackToggle(t.index, e.target.checked)}
                              style={{ accentColor: C.blue }}
                            />
                            <span style={{ color: bounceTracks.has(t.index) ? C.body : C.muted }}>
                              {t.name || `Track ${t.index + 1}`}
                            </span>
                          </label>
                        ))
                    }
                  </div>
                  <div style={{ height: 8 }} />
                  <div className="sec-label">Bounce quality</div>
                  <div className="pill-grp" style={{ flexDirection: "column", gap: 4 }}>
                    {["MP3 128", "MP3 256", "WAV 24"].map(q => <div key={q} className={`pill ${btQ === q ? "on" : ""}`} onClick={() => setBtQ(q)} style={{ textAlign: "center" }}>{q}</div>)}
                  </div>
                  <div
                    className="ebtn ebtn-blue"
                    onClick={handleBounce}
                    style={{ marginTop: 6, opacity: bouncing ? 0.5 : 1, cursor: bouncing ? "default" : "pointer" }}
                  >
                    {bouncing ? "⟳ Bouncing..." : "↑ Bounce & send"}
                  </div>
                  <div className="swap-card">
                    <div style={{ color: C.body, marginBottom: 3 }}>
                      {bouncing ? "Rendering in Reaper…" : (lastBounce.file || "—")}
                    </div>
                    <div style={{ color: bouncing ? C.amber : lastBounce.result === "ok" ? C.green : lastBounce.result === "error" ? C.red : C.muted }}>
                      {bouncing ? "In progress"
                        : lastBounce.result === "ok" ? "✓ Sent to artist"
                        : lastBounce.result === "error" ? "Bounce failed"
                        : "No bounce yet"}
                    </div>
                  </div>
                </div>
                <div style={{ marginTop: "auto" }}>
                  <div className="sec-label">Last file swap</div>
                  <div className="swap-card">
                    {lastFile ? <>
                      <div style={{ color: C.body }}>{lastFile.name.split("_")[0]} — {new Date(lastFile.time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</div>
                      <div style={{ color: C.muted }}>{(lastFile.size / 1024 / 1024).toFixed(1)}MB · {syncFmt}</div>
                      <div style={{ color: C.green, marginTop: 2 }}>✓ Timeline updated</div>
                    </> : <>
                      <div style={{ color: C.body }}>—</div>
                      <div style={{ color: C.muted }}>No files yet</div>
                    </>}
                  </div>
                </div>
              </div>
            </div>
          </>
        )}

        {/* Footer */}
        <div className="eng-footer">
          <span className="back-btn" style={{ color: C.blue, cursor: "pointer", marginRight: 12 }} onClick={onBack}>← Back</span>
          <span
            onClick={handleEndSession}
            style={{ color: C.red, border: `1px solid #5c1a1a`, background: "#1a0808", borderRadius: 4, padding: "2px 7px", cursor: "pointer", marginRight: "auto" }}
          >End session</span>
          <span style={{ color: showDetails ? C.blue : C.muted, cursor: "pointer", marginRight: 12 }} onClick={() => setShowDetails(d => !d)}>Details</span>
          <span style={{ color: C.body, marginRight: 12 }}>{latencyMs !== null ? `${latencyMs}ms` : "—"}</span>
          <span style={{ marginRight: 4 }}>Format</span><span style={{ color: C.body, marginRight: 12 }}>{syncFmt}</span>
          <span style={{ marginRight: 4 }}>Stream</span><span style={{ color: C.body, marginRight: 12 }}>{streamQ}</span>
          <span style={{ marginRight: 4 }}>Takes</span><span style={{ color: C.body }}>{takeCount > 0 ? `T${takeCount}` : "—"}</span>
        </div>
      </div>
      {showDetails && <DetailsPanel onClose={() => setShowDetails(false)} sessionCode={sessionCode} />}
    </div>
  );
}
