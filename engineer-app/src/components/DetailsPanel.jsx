import { useState, useEffect } from "react";
import C from "../constants/colors";

const RELAY         = "http://localhost:5010";
const FILE_RECEIVER = "http://localhost:5001";
const TRANSPORT     = `${RELAY}/artist`;  // proxied to the artist's machine

function fmtSize(bytes) {
  if (bytes >= 1024 * 1024) return (bytes / 1024 / 1024).toFixed(1) + " MB";
  return Math.round(bytes / 1024) + " KB";
}

function fmtTime(ts) {
  const d = new Date(ts);
  if (isNaN(d)) return "--:--:--";
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });
}

export default function DetailsPanel({ onClose, sessionCode }) {
  const [conns, setConns] = useState({
    relay: false, file: false, artist: false,
    reaper: false, transport: false,
  });
  const [takes, setTakes] = useState([]);

  useEffect(() => {
    const poll = async () => {
      // Relay: any 200 from /session/active
      let relay = false;
      try {
        const r = await fetch(`${RELAY}/session/active`, { signal: AbortSignal.timeout(2000) });
        relay = r.ok;
      } catch {}

      // File receiver: any HTTP response means it's up
      let file = false;
      try {
        await fetch(FILE_RECEIVER, { signal: AbortSignal.timeout(2000) });
        file = true;
      } catch {}

      // Artist: present field in session status
      let artist = false;
      if (sessionCode) {
        try {
          const r = await fetch(`${RELAY}/session/${sessionCode}/status`, { signal: AbortSignal.timeout(2000) });
          if (r.ok) artist = Boolean((await r.json()).artist);
        } catch {}
      }

      // Reaper: reachable field
      let reaper = false;
      try {
        const r = await fetch(`${RELAY}/reaper/status`, { signal: AbortSignal.timeout(2000) });
        if (r.ok) reaper = Boolean((await r.json()).reachable);
      } catch {}

      // Transport: must be 2xx — the relay proxy returns 404/502 when the
      // artist isn't connected, which would otherwise read as "up"
      let transport = false;
      try {
        const r = await fetch(`${TRANSPORT}/status`, { signal: AbortSignal.timeout(2000) });
        transport = r.ok;
      } catch {}

      setConns({ relay, file, artist, reaper, transport });

      // Takes for activity log + bandwidth totals
      try {
        const r = await fetch(`${FILE_RECEIVER}/takes`, { signal: AbortSignal.timeout(2000) });
        if (r.ok) setTakes(await r.json());
      } catch {}
    };

    poll();
    const id = setInterval(poll, 3000);
    return () => clearInterval(id);
  }, [sessionCode]);

  // Newest 20 entries at top
  const activityLog = takes
    .slice(-20)
    .reverse()
    .map(t => ({
      time: fmtTime(t.time),
      msg:  `${t.name} received — ${fmtSize(t.size)}`,
    }));

  const totalMB = (takes.reduce((s, t) => s + (t.size || 0), 0) / 1024 / 1024).toFixed(1);

  const connRows = [
    ["Relay",     conns.relay],
    ["File recv", conns.file],
    ["Artist",    conns.artist],
    ["Reaper",    conns.reaper],
    ["Transport", conns.transport],
  ];

  return (
    <div className="details-wrap">
      <div className="details-hdr">
        <div className="details-title">Details</div>
        <div className="details-close" onClick={onClose}>×</div>
      </div>
      <div className="details-body">

        <div>
          <div className="sec-label" style={{ marginBottom: 8 }}>Connections</div>
          <div className="conn-grid">
            {connRows.map(([name, ok]) => (
              <div key={name} className="conn-tile">
                <div className={`dot ${ok ? "g" : "d"}`} />
                <div className="conn-name">{name}</div>
                <div className="conn-ok" style={{ color: ok ? C.green : C.dim }}>
                  {ok ? "OK" : "—"}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div>
          <div className="sec-label" style={{ marginBottom: 8 }}>Activity</div>
          <div className="log-box">
            {activityLog.length === 0
              ? <div className="log-line">
                  <span className="log-msg" style={{ color: C.dim }}>No activity yet</span>
                </div>
              : activityLog.map((l, i) => (
                  <div key={i} className="log-line">
                    <span className="log-time">{l.time}</span>
                    <span className="log-msg">{l.msg}</span>
                  </div>
                ))
            }
          </div>
        </div>

        <div>
          <div className="sec-label" style={{ marginBottom: 8 }}>Bandwidth</div>
          <div className="bw-grid">
            <div className="bw-tile">
              <div className="bw-lbl">Stream Up</div>
              <div><span className="bw-val">—</span></div>
            </div>
            <div className="bw-tile">
              <div className="bw-lbl">Stream Dn</div>
              <div><span className="bw-val">—</span></div>
            </div>
            <div className="bw-tile">
              <div className="bw-lbl">Total rcvd</div>
              <div><span className="bw-val">{totalMB}</span> <span className="bw-unit">MB</span></div>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
