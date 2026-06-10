import { useState, useEffect, useRef } from "react";
import C from "../constants/colors";

const RELAY = "http://localhost:5010";

export default function SessionScreen({ onStart }) {
  const [rawCode, setRawCode] = useState(null);  // null=polling, ""=error, "XXXXXX"=found
  const [creating, setCreating] = useState(false);
  const pollRef = useRef(null);

  const stopPolling = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  useEffect(() => {
    const poll = async () => {
      try {
        const r = await fetch(`${RELAY}/session/active`);
        if (r.ok) {
          const data = await r.json();
          setRawCode(data.code);
          stopPolling();
        }
        // 404 = no active session yet — keep polling silently
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
      // No ip in the body — the relay substitutes its own LAN IP, which is
      // correct because the relay always runs on the engineer's machine.
      const r = await fetch(`${RELAY}/session/new`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      setRawCode(r.ok ? (await r.json()).code : "");
    } catch {
      setRawCode("");
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
          <div style={{
            fontFamily: "'DM Mono', 'Courier New', monospace",
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

        <div style={{ fontSize: 10, marginBottom: 8, textAlign: "center", minHeight: 16 }}>
          {rawCode === null && !creating && (
            <span style={{ color: C.muted }}>Waiting for dev_engineer.sh to start…</span>
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
            window.resizeTo(960, 760);
            window.moveTo(screen.width / 2 - 480, screen.height / 2 - 380);
            onStart(rawCode);
          }}
        >
          Start session
        </button>
      </div>
    </div>
  );
}
