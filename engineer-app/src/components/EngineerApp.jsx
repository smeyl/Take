import { useState, useEffect, useRef } from "react";
import C from "../constants/colors";
import Knob from "./Knob";
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
  const [dots, setDots]             = useState({ companion: false, server: false, artist: false, reaper: false });
  const [streamQ, setStreamQ]       = useState("PCM 16");
  const [syncFmt, setSyncFmt]       = useState("WAV 24");
  const [btQ, setBtQ]               = useState("MP3 256");
  const [showDetails, setShowDetails] = useState(false);
  const [receivedTakes, setReceivedTakes] = useState([]);
  const [latencyMs, setLatencyMs]   = useState(null);
  const [bouncing, setBouncing]     = useState(false);
  const [levels, setLevels]         = useState({ l: -60, r: -60 });
  const [destTracks, setDestTracks] = useState([]);
  const [destTrack, setDestTrack]   = useState(0);
  const [punchActive, setPunchActive] = useState(false);
  // Set of track indices selected for the next bounce; initialised from destTracks.
  const [bounceTracks, setBounceTracks] = useState(new Set());
  const [autoSync, setAutoSync]         = useState(true);

  // Initialise bounce selection whenever the track list loads.
  useEffect(() => {
    if (destTracks.length > 0)
      setBounceTracks(new Set(destTracks.map(t => t.index)));
  }, [destTracks]);

  const sendCue = async (param, value) => {
    try {
      await fetch(`${RELAY}/cue/${param}/${value}`, { method: "POST" });
    } catch {}
  };

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
      await fetch(`${FILE_RECEIVER}/track/select/${index}`, { method: "POST" });
    } catch {}
  };

  const handleEndSession = async () => {
    if (!window.confirm("End session?")) return;
    try {
      await fetch(`${RELAY}/session/${sessionCode}`, { method: "DELETE" });
    } catch {}
    onBack();
  };

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

  // ── Polling ──────────────────────────────────────────────────────────────────
  useEffect(() => {
    const pollTransport = async () => {
      try {
        const r = await fetch(`${ARTIST}/status`);
        if (r.ok) {
          const data = await r.json();
          setRecording(data.recording);
          setTakeCount(data.take);
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
      let relayOk = false;
      try {
        const t0 = Date.now();
        const r = await fetch(`${RELAY}/session/${sessionCode}/status`);
        if (r.ok) {
          setLatencyMs(Date.now() - t0);
          relayOk = true;
          const data = await r.json();
          setDots(d => ({ ...d, companion: true, artist: Boolean(data.artist) }));
        }
      } catch {
        setDots(d => ({ ...d, companion: false, artist: false }));
      }

      let fileOk = false;
      try {
        await fetch(FILE_RECEIVER, { method: "GET", signal: AbortSignal.timeout(2000) });
        fileOk = true;  // any response (including 404/405) means server is up
      } catch {}
      setDots(d => ({ ...d, server: relayOk && fileOk }));

      try {
        const rr = await fetch(`${RELAY}/reaper/status`, { signal: AbortSignal.timeout(3000) });
        if (rr.ok) {
          const rd = await rr.json();
          setDots(d => ({ ...d, reaper: Boolean(rd.reachable) }));
        }
      } catch {
        setDots(d => ({ ...d, reaper: false }));
      }

      try {
        const rb = await fetch(`${BOUNCE}/bounce/status`);
        if (rb.ok) {
          const bd = await rb.json();
          setBouncing(bd.bouncing);
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

  useEffect(() => {
    fetch(`${FILE_RECEIVER}/tracks`)
      .then(r => r.ok ? r.json() : [])
      .then(data => { if (data.length) setDestTracks(data); })
      .catch(() => {});
  }, []);

  const takesScrollRef = useRef(null);
  useEffect(() => {
    if (takesScrollRef.current) {
      takesScrollRef.current.scrollTop = takesScrollRef.current.scrollHeight;
    }
  }, [takeCount]);

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

  const dotList = [
    [dots.companion ? "g" : "d", "Companion"],
    [dots.server    ? "g" : "d", "Server"],
    [dots.artist    ? "g" : "d", "Artist"],
    [dots.reaper    ? "g" : "d", "Reaper"],
  ];

  return (
    <div className="eng-shell">
      <div className="eng-wrap">
        {/* Header */}
        <div className="eng-hdr" style={{ WebkitAppRegion: "drag" }}>
          <div className="eng-logo">T<span>ake</span></div>
          {dotList.map(([dot, label]) => (
            <div key={label} className="eng-conn" style={{ WebkitAppRegion: "no-drag" }}><div className={`dot ${dot}`} />{label}</div>
          ))}
          <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 10, fontSize: 9 }}>
            {recording
              ? <><div className="dot r" /><span style={{ color: C.red }}>T{takeCount} recording</span></>
              : <span style={{ color: C.muted }}>{displayCode}</span>}
            <span style={{ color: showDetails ? C.blue : C.muted, cursor: "pointer", WebkitAppRegion: "no-drag" }} onClick={() => setShowDetails(d => !d)}>Details</span>
            <span
              onClick={handleEndSession}
              style={{ color: C.red, border: `1px solid #5c1a1a`, background: "#1a0808", borderRadius: 4, padding: "2px 7px", cursor: "pointer", WebkitAppRegion: "no-drag" }}
            >End session</span>
          </div>
        </div>

        <div className="eng-body">
          {/* Left col */}
          <div className="ecol" style={{ width: 210, flexShrink: 0 }}>
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
              <div className="sec-label">Transport</div>
              <div
                className={`ebtn ebtn-rec ${recording ? "on" : ""}`}
                style={{ width: "100%", textAlign: "center", marginBottom: 6 }}
                onClick={handleRec}
              >
                {recording ? "■ Stop" : "● Rec"}
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
              <div className="sec-label">Stream quality</div>
              <div className="pill-grp">{["PCM 16", "PCM 24", "Float 32"].map(q => <div key={q} className={`pill ${streamQ === q ? "on" : ""}`} onClick={() => handleStreamQ(q)}>{q}</div>)}</div>
              <div style={{ height: 8 }} />
              <div className="sec-label">Sync format</div>
              <div className="pill-grp">{["FLAC", "WAV 24", "WAV 32f"].map(f => <div key={f} className={`pill ${syncFmt === f ? "on" : ""}`} onClick={() => handleSyncFmt(f)}>{f}</div>)}</div>
              <div style={{ height: 8 }} />
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <span className="sec-label" style={{ marginBottom: 0 }}>Auto-sync</span>
                <div
                  className={`pill ${autoSync ? "on" : ""}`}
                  style={{ cursor: "pointer", minWidth: 30, textAlign: "center" }}
                  onClick={handleAutoSync}
                >{autoSync ? "On" : "Off"}</div>
              </div>
            </div>
          </div>

          {/* Middle col — cue mix */}
          <div className="ecol" style={{ flex: 1 }}>
            <div className="sec-label">Cue mix — artist headphones</div>
            <div style={{ fontSize: 9, color: C.muted, marginTop: -4 }}>Parameters sent live · artist can also adjust</div>

            {[
              { label: "REVERB",      color: C.purple, keys: [["Size", "rev"],       ["Mix", "revMix"]] },
              { label: "DELAY",       color: C.teal,   keys: [["Time", "del"],       ["Mix", "delMix"]] },
              { label: "COMPRESSION", color: C.amber,  keys: [["Threshold", "comp"]] },
            ].map(({ label, color, keys }) => (
              <div key={label}>
                <div className="group-label">
                  <div className="group-accent" style={{ background: color }} />
                  <div className="group-text" style={{ color }}>{label}</div>
                </div>
                <div className="knob-row" style={{ marginBottom: 12 }}>
                  {keys.map(([lbl, k]) => <Knob key={k} label={lbl} value={cue[k]} color={color} onChange={v => updateCue(k, v)} />)}
                </div>
              </div>
            ))}

            <div style={{ marginTop: "auto" }}>
              <div className="group-label">
                <div className="group-accent" style={{ background: C.green }} />
                <div className="group-text" style={{ color: C.green }}>CUE VOLUME</div>
              </div>
              <div style={{ display: "flex", justifyContent: "center" }}>
                <Knob label="Master" value={cue.vol} color={C.green} onChange={v => updateCue("vol", v)} />
              </div>
            </div>

            <div style={{ fontSize: 9, color: C.muted, background: C.raised, borderRadius: 4, padding: "6px 8px", border: `1px solid ${C.border}`, textAlign: "center" }}>
              Changes sync to artist · zero monitoring latency
            </div>
          </div>

          {/* Right col — backing track */}
          <div className="ecol" style={{ width: 190, flexShrink: 0 }}>
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
              <div style={{ color: C.body, marginBottom: 3 }}>{bouncing ? "Rendering in Reaper…" : "session_BT.mp3"}</div>
              <div style={{ color: bouncing ? C.amber : C.muted }}>{bouncing ? "In progress" : "Ready to send"}</div>
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

        {/* Footer */}
        <div className="eng-footer">
          <span className="back-btn" style={{ color: C.blue, cursor: "pointer", marginRight: "auto" }} onClick={onBack}>← Back</span>
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
