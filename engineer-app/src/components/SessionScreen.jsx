import { useState, useEffect, useRef } from "react";
import C from "../constants/colors";

const RELAY = "http://localhost:5010";

export default function SessionScreen({ onStart }) {
  const [rawCode, setRawCode] = useState(null);  // null=polling, ""=error, "XXXXXX"=found
  const [engineerIP, setEngineerIP] = useState("");
  const [creating, setCreating] = useState(false);
  const pollRef = useRef(null);

  const stopPolling = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  // Apply a relay session response ({code, engineer_ip}) to the UI. The artist
  // needs both the code and the engineer's IP to join, so we surface both.
  const applySession = (data) => {
    setRawCode(data?.code ?? "");
    if (data?.engineer_ip) setEngineerIP(data.engineer_ip);
  };

  // Register a new session with the relay. Returns {code, engineer_ip} or null.
  // The relay maps a loopback ip to its own LAN IP, so sending 127.0.0.1 is
  // safe and keeps two-machine sessions working — and it hands that resolved
  // LAN IP back so we can show it to the artist.
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
        const r = await fetch(`${RELAY}/session/active`);
        if (r.ok) {
          // A session is already registered with the relay — reuse it.
          applySession(await r.json());
          stopPolling();
          return;
        }
        if (r.status === 404) {
          // Relay is up but has no active session — register one now.
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
    : isLoading ? "· · · · · ·" : "— — —";

  return (
    <div style={{
      width: "100%", height: "100%",
      display: "flex", flexDirection: "column",
      alignItems: "center", justifyContent: "center",
      background: C.bg,
    }}>
      <div style={{ width: 320, display: "flex", flexDirection: "column", alignItems: "center" }}>
        <div className="role-title">T<span>ake</span></div>
        <div className="role-sub" style={{ marginBottom: 32 }}>Engineer</div>

        <div style={{
          width: "100%", background: C.raised,
          border: `1px solid ${C.border}`, borderRadius: 6,
          padding: "20px 24px 16px", textAlign: "center", marginBottom: 16,
        }}>
          <div style={{ fontSize: 9, color: C.muted, letterSpacing: "0.08em", marginBottom: 4 }}>
            SESSION CODE
          </div>
          <div style={{
            fontFamily: "'IBM Plex Mono', monospace",
            fontSize: 24, letterSpacing: "0.14em",
            color: rawCode ? C.bright : C.muted,
            marginBottom: 12,
          }}>
            {displayCode}
          </div>
          <span
            style={{
              fontSize: 10, color: creating ? C.muted : C.blue,
              cursor: creating ? "default" : "pointer",
              letterSpacing: "0.05em", userSelect: "none",
            }}
            onClick={creating ? undefined : createNewCode}
          >
            Generate new code
          </span>
        </div>

        <div style={{ fontSize: 10, color: C.muted, textAlign: "center", marginBottom: 16, lineHeight: 1.5 }}>
          Give the artist the session code — they'll find you on the network automatically.
        </div>

        {/* Relay IP kept as small debug info — the artist no longer needs it
            unless discovery is blocked and they fall back to manual entry. */}
        {engineerIP && (
          <div style={{
            fontFamily: "'IBM Plex Mono', monospace",
            fontSize: 9, color: C.dim, textAlign: "center",
            marginBottom: 16, userSelect: "text",
          }}>
            relay {engineerIP}
          </div>
        )}

        <div style={{ fontSize: 10, marginBottom: 8, textAlign: "center", minHeight: 16 }}>
          {rawCode === null && !creating && (
            <span style={{ color: C.muted }}>Waiting for the Take backend to start…</span>
          )}
          {rawCode === "" && (
            <span style={{ color: C.amber }}>Relay unreachable — start relay.py first</span>
          )}
        </div>

        <button
          className="role-btn engineer"
          style={{ width: "100%", opacity: rawCode ? 1 : 0.4 }}
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
