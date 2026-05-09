import C from "../constants/colors";

export default function DetailsPanel({ onClose, recording }) {
  const logs = [
    { t: "14:51:03", msg: "Session started — A7·F2·K9", cls: "info" },
    { t: "14:51:09", msg: "Artist app connected", cls: "ok" },
    { t: "14:53:22", msg: "Backing track sent (8.2MB)", cls: "info" },
    { t: "14:55:58", msg: "T4 sync complete — swap 0.4s", cls: "ok" },
    { t: "14:56:20", msg: "Recording started — T5", cls: "" },
    ...(recording ? [{ t: "14:56:52", msg: "T5 recording — 0:32 elapsed", cls: "warn" }] : []),
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
            {[["Plugin link", true], ["Relay server", true], ["Artist app", true], ["Reaper API", true], ["BlackHole 2ch", true], ["File watcher", true]].map(([name, ok]) => (
              <div key={name} className="conn-tile">
                <div className={`dot ${ok ? "g" : "r"}`} />
                <div className="conn-name">{name}</div>
                <div className="conn-ok">{ok ? "OK" : "ERR"}</div>
              </div>
            ))}
          </div>
        </div>
        <div>
          <div className="sec-label" style={{ marginBottom: 8 }}>Activity</div>
          <div className="log-box">
            {logs.map((l, i) => <div key={i} className="log-line"><span className="log-time">{l.t}</span><span className={`log-msg ${l.cls}`}>{l.msg}</span></div>)}
          </div>
        </div>
        <div>
          <div className="sec-label" style={{ marginBottom: 8 }}>Bandwidth</div>
          <div className="bw-grid">
            <div className="bw-tile"><div className="bw-lbl">Stream Up</div><div><span className="bw-val">0.8</span> <span className="bw-unit">Mbps</span></div></div>
            <div className="bw-tile"><div className="bw-lbl">Stream Dn</div><div><span className="bw-val">0.4</span> <span className="bw-unit">Mbps</span></div></div>
            <div className="bw-tile"><div className="bw-lbl">Total</div><div><span className="bw-val">214</span> <span className="bw-unit">MB</span></div></div>
          </div>
        </div>
      </div>
    </div>
  );
}
