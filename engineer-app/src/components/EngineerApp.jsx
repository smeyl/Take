import { useState, useEffect } from "react";
import C from "../constants/colors";
import Knob from "./Knob";
import WaveCanvas from "./WaveCanvas";
import DetailsPanel from "./DetailsPanel";

const RELAY         = "http://localhost:5010";
const TRANSPORT     = "http://localhost:5004";
const FILE_RECEIVER = "http://localhost:5001";

export default function EngineerApp({ cue, setCue, sessionCode, onBack }) {
  const [recording, setRecording]   = useState(false);
  const [takeCount, setTakeCount]   = useState(0);
  const [dots, setDots]             = useState({ companion: false, server: false, artist: false, reaper: false });
  const [streamQ, setStreamQ]       = useState("AAC 256");
  const [syncFmt, setSyncFmt]       = useState("WAV 24");
  const [autoSync, setAutoSync]     = useState(true);
  const [placeTimeline, setPlaceTimeline] = useState(true);
  const [notifySync, setNotifySync] = useState(false);
  const [tracks, setTracks]         = useState({ drums: true, bass: true, keys: true });
  const [btQ, setBtQ]               = useState("MP3 256");
  const [btSent, setBtSent]         = useState(true);
  const [showDetails, setShowDetails] = useState(false);

  const updateCue = (k, v) => setCue(c => ({ ...c, [k]: v }));

  // ── Transport actions ────────────────────────────────────────────────────────
  const handleRec = async () => {
    const endpoint = recording ? "stop" : "record";
    try {
      const r = await fetch(`${TRANSPORT}/${endpoint}`, { method: "POST" });
      if (r.ok) {
        const data = await r.json();
        setRecording(data.recording);
        if (data.take !== undefined) setTakeCount(data.take);
      }
    } catch {}
  };

  const handleRTZ = async () => {
    try {
      const r = await fetch(`${TRANSPORT}/stop`, { method: "POST" });
      if (r.ok) {
        const data = await r.json();
        setRecording(data.recording);
      }
    } catch {}
  };

  // ── Polling ──────────────────────────────────────────────────────────────────
  useEffect(() => {
    const pollTransport = async () => {
      try {
        const r = await fetch(`${TRANSPORT}/status`);
        if (r.ok) {
          const data = await r.json();
          setRecording(data.recording);
          setTakeCount(data.take);
        }
      } catch {}
    };

    const pollSession = async () => {
      let relayOk = false;
      try {
        const r = await fetch(`${RELAY}/session/${sessionCode}/status`);
        if (r.ok) {
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
    };

    pollTransport();
    pollSession();
    const t1 = setInterval(pollTransport, 2000);
    const t2 = setInterval(pollSession, 3000);
    return () => { clearInterval(t1); clearInterval(t2); };
  }, [sessionCode]);

  // ── Derived state ────────────────────────────────────────────────────────────
  const takes = takeCount === 0 ? [] : Array.from({ length: takeCount }, (_, i) => {
    const n = i + 1;
    return { id: `T${n}`, s: n === takeCount && recording ? "live" : "done" };
  });

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
        <div className="eng-hdr">
          <div className="eng-logo">T<span>ake</span></div>
          {dotList.map(([dot, label]) => (
            <div key={label} className="eng-conn"><div className={`dot ${dot}`} />{label}</div>
          ))}
          <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 10, fontSize: 9 }}>
            {recording
              ? <><div className="dot r" /><span style={{ color: C.red }}>T{takeCount} recording</span></>
              : <span style={{ color: C.muted }}>{displayCode}</span>}
            <span style={{ color: showDetails ? C.blue : C.muted, cursor: "pointer" }} onClick={() => setShowDetails(d => !d)}>Details</span>
          </div>
        </div>

        <div className="eng-body">
          {/* Left col */}
          <div className="ecol" style={{ width: 210, flexShrink: 0 }}>
            <div>
              <div className="sec-label">Artist input</div>
              <div className="meter-lbl"><span>L</span><span style={{ color: C.green }}>–12</span></div>
              <div className="meter-bar"><div className="meter-fill" style={{ width: "68%" }} /></div>
              <div className="meter-lbl"><span>R</span><span style={{ color: C.green }}>–14</span></div>
              <div className="meter-bar"><div className="meter-fill" style={{ width: "61%" }} /></div>
            </div>
            <div>
              <div className="sec-label">Takes</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                {takes.length === 0 && (
                  <div style={{ fontSize: 9, color: C.dim, fontStyle: "italic" }}>No takes yet</div>
                )}
                {takes.map(t => (
                  <div key={t.id} className={`take-row ${t.s === "live" ? "live" : ""}`}>
                    <div className="take-num" style={{ color: t.s === "live" ? C.red : C.green }}>{t.id}</div>
                    <div className="take-wave">
                      <WaveCanvas
                        width={110} height={20}
                        color={t.s === "live" ? C.red : C.green}
                        animated={t.s === "live"}
                        progress={1}
                      />
                    </div>
                    {t.s === "done" && <div className="take-badge tb-wav">WAV</div>}
                    {t.s === "live" && <div className="take-badge tb-live">LIVE</div>}
                  </div>
                ))}
              </div>
            </div>
            <div>
              <div className="sec-label">Transport</div>
              <div style={{ display: "flex", gap: 6, marginBottom: 6 }}>
                <div className={`ebtn ebtn-rec ${recording ? "on" : ""}`} style={{ flex: 1 }} onClick={handleRec}>
                  {recording ? "■ Stop" : "● Rec"}
                </div>
                <div className="ebtn ebtn-ghost" style={{ flex: 1 }} onClick={handleRTZ}>↩ RTZ</div>
              </div>
              <div className="ebtn ebtn-amber" style={{ width: "100%", textAlign: "center" }}>⊡ Punch in/out</div>
            </div>
            <div>
              <div className="sec-label">Sync</div>
              <div className="sync-box">
                <div className="sync-row"><span>Auto-sync lossless</span><div className={`toggle ${autoSync ? "on" : ""}`} onClick={() => setAutoSync(a => !a)} /></div>
                <div className="sync-row"><span>Place on timeline</span><div className={`toggle ${placeTimeline ? "on" : ""}`} onClick={() => setPlaceTimeline(p => !p)} /></div>
                <div className="sync-row"><span>Notify on sync</span><div className={`toggle ${notifySync ? "on" : ""}`} onClick={() => setNotifySync(n => !n)} /></div>
              </div>
              <div style={{ height: 6 }} />
              <div className="sec-label">Stream quality</div>
              <div className="pill-grp">{["AAC 128", "AAC 256", "FLAC"].map(q => <div key={q} className={`pill ${streamQ === q ? "on" : ""}`} onClick={() => setStreamQ(q)}>{q}</div>)}</div>
              <div style={{ height: 6 }} />
              <div className="sec-label">Sync format</div>
              <div className="pill-grp">{["FLAC", "WAV 24", "WAV 32f"].map(f => <div key={f} className={`pill ${syncFmt === f ? "on" : ""}`} onClick={() => setSyncFmt(f)}>{f}</div>)}</div>
              <div style={{ height: 6 }} />
              <div className="sync-now" style={{ opacity: autoSync ? 0.4 : 1, cursor: autoSync ? "default" : "pointer" }}>
                {autoSync ? "Auto-sync enabled" : takeCount > 0 ? `Sync T${takeCount} now` : "No take to sync"}
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
              { label: "COMPRESSION", color: C.amber,  keys: [["Threshold", "comp"], ["Ratio", "ratio"]] },
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

            <div>
              <div className="group-label">
                <div className="group-accent" style={{ background: C.blue }} />
                <div className="group-text" style={{ color: C.blue }}>4-BAND EQ</div>
              </div>
              <div className="eq-wrap">
                {[{ f: "80Hz", v: 55 }, { f: "400Hz", v: 48 }, { f: "2kHz", v: 70 }, { f: "8kHz", v: 65 }].map(b => (
                  <div key={b.f} className="eq-band">
                    <input className="eq-slider" type="range" min={0} max={100} defaultValue={b.v} />
                    <div className="eq-freq">{b.f}</div>
                  </div>
                ))}
              </div>
            </div>

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
            <div style={{ fontSize: 9, color: C.muted, marginBottom: 4 }}>Select Reaper tracks</div>
            <div className="track-check">
              {[["drums", "01 — Drums"], ["bass", "02 — Bass"], ["keys", "03 — Keys"]].map(([k, name]) => (
                <label key={k} className="track-item">
                  <input type="checkbox" checked={tracks[k]} onChange={e => setTracks(t => ({ ...t, [k]: e.target.checked }))} style={{ accentColor: C.blue }} />
                  <span style={{ color: tracks[k] ? C.body : C.muted }}>{name}</span>
                </label>
              ))}
              <div style={{ fontSize: 9, color: C.dim, fontStyle: "italic" }}>
                {dots.reaper ? "Loaded from Reaper" : "Reaper not connected"}
              </div>
            </div>
            <div style={{ height: 8 }} />
            <div className="sec-label">Bounce quality</div>
            <div className="pill-grp" style={{ flexDirection: "column", gap: 4 }}>
              {["MP3 128", "MP3 256", "WAV 24"].map(q => <div key={q} className={`pill ${btQ === q ? "on" : ""}`} onClick={() => setBtQ(q)} style={{ textAlign: "center" }}>{q}</div>)}
            </div>
            <div className="ebtn ebtn-blue" onClick={() => setBtSent(false)} style={{ marginTop: 6 }}>
              {btSent ? "↑ Send to artist" : "Sending..."}
            </div>
            <div className="swap-card">
              <div style={{ color: C.body, marginBottom: 3 }}>session_BT_v3.mp3</div>
              <div style={{ color: C.muted, marginBottom: 3 }}>Sent 14:32 · 8.2MB</div>
              <div style={{ color: btSent ? C.green : C.amber }}>{btSent ? "✓ Artist confirmed" : "Transferring..."}</div>
            </div>
            <div style={{ marginTop: "auto" }}>
              <div className="sec-label">Last file swap</div>
              <div className="swap-card">
                <div style={{ color: C.body }}>{takeCount > 0 ? `T${takeCount} — just now` : "—"}</div>
                <div style={{ color: C.muted }}>0.4s · {syncFmt}</div>
                <div style={{ color: C.green, marginTop: 2 }}>{takeCount > 0 ? "✓ Timeline updated" : ""}</div>
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="eng-footer">
          <span className="back-btn" style={{ color: C.blue, cursor: "pointer", marginRight: "auto" }} onClick={onBack}>← Back</span>
          <span style={{ color: C.body, marginRight: 12 }}>22ms</span>
          <span style={{ marginRight: 4 }}>Format</span><span style={{ color: C.body, marginRight: 12 }}>{syncFmt}</span>
          <span style={{ marginRight: 4 }}>Stream</span><span style={{ color: C.body, marginRight: 12 }}>{streamQ}</span>
          <span style={{ marginRight: 4 }}>Takes</span><span style={{ color: C.body }}>{takeCount > 0 ? `T${takeCount}` : "—"}</span>
        </div>
      </div>
      {showDetails && <DetailsPanel onClose={() => setShowDetails(false)} recording={recording} />}
    </div>
  );
}
