import { useState, useEffect, useRef } from "react";
import { LogoMark, RefreshIcon } from "./icons";

const RELAY = "http://localhost:5010";

// The engineer's start screen: the session code to give the artist, the
// address they also need over the internet (the code alone only finds this
// machine on the same network), and Start.
// Shown at launch and after End Session. The engineer backend follows
// whichever session is current, so "Generate new code" is safe at any time.
export default function SessionScreen({ onStart }) {
  const [rawCode, setRawCode] = useState(null);  // null=polling, ""=error, "XXXXXX"=found
  const [engineerIP, setEngineerIP] = useState("");
  // Addresses the artist can type if discovery can't find this machine:
  // [{kind: "tailscale"|"lan", ip}], Tailscale first.
  const [addresses, setAddresses] = useState([]);
  const [creating, setCreating] = useState(false);
  const pollRef = useRef(null);

  const stopPolling = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  // Apply a relay session response ({code, engineer_ip}) to the UI.
  const applySession = (data) => {
    setRawCode(data?.code ?? "");
    if (data?.engineer_ip) setEngineerIP(data.engineer_ip);
    if (Array.isArray(data?.addresses)) setAddresses(data.addresses);
  };

  // Start a new session on the relay (it replaces the current one). The
  // relay maps a loopback ip to its own LAN IP and returns it, so it can be
  // shown to the artist.
  const requestNewCode = async () => {
    try {
      const r = await fetch(`${RELAY}/session/new`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ip: "127.0.0.1" }),
      });
      return r.ok ? await r.json() : null;
    } catch {
      return null;
    }
  };

  useEffect(() => {
    const poll = async () => {
      try {
        const r = await fetch(`${RELAY}/session/current`);
        if (r.ok) {
          // The backend's session (or the one before End Session) — reuse it.
          applySession(await r.json());
          stopPolling();
          return;
        }
        if (r.status === 404) {
          // Relay is up but has no session (e.g. after End Session) — start one.
          stopPolling();
          setCreating(true);
          try {
            applySession(await requestNewCode());
          } finally {
            setCreating(false);
          }
        }
        // any other status — keep polling silently
      } catch {
        // relay not up yet — keep polling silently
      }
    };

    poll();
    pollRef.current = setInterval(poll, 2000);
    return stopPolling;
  }, []);

  const createNewCode = async () => {
    stopPolling();
    setCreating(true);
    try {
      applySession(await requestNewCode());
    } finally {
      setCreating(false);
    }
  };

  const isLoading = rawCode === null || creating;
  const displayCode = rawCode
    ? `${rawCode.slice(0, 2)} · ${rawCode.slice(2, 4)} · ${rawCode.slice(4, 6)}`
    : isLoading ? "·· · ·· · ··" : "—";

  return (
    <div className="start">
      <div className="hdr start-hdr">
        <div className="logo">
          <LogoMark />
          <span className="logo-word">TAKE</span>
        </div>
        <span className="start-role">Engineer</span>
      </div>

      <div className="start-body">
        <div className="start-code-block">
          <span className="code-label">Session code</span>
          <span className={`start-code ${rawCode ? "" : "start-code-empty"}`}>{displayCode}</span>
          <button
            className="popout-btn start-new"
            onClick={createNewCode}
            disabled={creating || rawCode === null}
          >
            <span className={creating ? "spin" : ""} style={{ display: "flex" }}>
              <RefreshIcon size={10} color="#8a8a90" />
            </span>
            Generate new code
          </button>
        </div>

        <p className="start-help">
          Give the artist this code. On the same network, their Take app finds you with it.
        </p>
        {(addresses.length > 0 || engineerIP) && (
          <div className="start-addrs">
            <p className="start-help start-addr">Over the internet the code isn't enough — they also enter your address:</p>
            {(addresses.length ? addresses : [{ kind: "lan", ip: engineerIP }]).map(a => (
              <p key={a.ip} className="start-help start-addr">
                {a.kind === "tailscale" ? "Over the internet (Tailscale)" : "On the same network"}{" "}
                <span className="start-ip">{a.ip}</span>
              </p>
            ))}
          </div>
        )}

        <div className="start-status">
          {rawCode === null && !creating && (
            <span style={{ color: "#6b6b70" }}>Waiting for the Take backend to start…</span>
          )}
          {rawCode === "" && (
            <span style={{ color: "#e7b23e" }}>Relay unreachable — start relay.py first</span>
          )}
        </div>
      </div>

      <div className="start-foot">
        <button
          className="start-btn"
          disabled={!rawCode}
          onClick={() => {
            // Design reference: main-window.html is 380x640.
            window.resizeTo(380, 640);
            window.moveTo(screen.width / 2 - 190, screen.height / 2 - 320);
            onStart(rawCode);
          }}
        >
          Start session
        </button>
      </div>
    </div>
  );
}
