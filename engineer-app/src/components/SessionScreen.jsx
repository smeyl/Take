import { useState } from "react";
import C from "../constants/colors";

function generateCode() {
  const L = () => String.fromCharCode(65 + Math.floor(Math.random() * 26));
  const D = () => Math.floor(Math.random() * 10);
  return `${L()}${D()} · ${L()}${D()} · ${L()}${D()}`;
}

export default function SessionScreen({ onStart }) {
  const [code, setCode] = useState(generateCode);

  return (
    <div style={{
      width: "100%",
      height: "100%",
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      background: C.bg,
    }}>
      <div style={{ width: 320, display: "flex", flexDirection: "column", alignItems: "center" }}>
        <div className="role-title">T<span>ake</span></div>
        <div className="role-sub" style={{ marginBottom: 32 }}>Engineer</div>

        <div style={{
          width: "100%",
          background: C.raised,
          border: `1px solid ${C.border}`,
          borderRadius: 6,
          padding: "20px 24px 16px",
          textAlign: "center",
          marginBottom: 16,
        }}>
          <div style={{
            fontFamily: "'DM Mono', 'Courier New', monospace",
            fontSize: 24,
            letterSpacing: "0.14em",
            color: C.bright,
            marginBottom: 12,
          }}>
            {code}
          </div>
          <span
            style={{ fontSize: 10, color: C.blue, cursor: "pointer", letterSpacing: "0.05em", userSelect: "none" }}
            onClick={() => setCode(generateCode())}
          >
            Generate new code
          </span>
        </div>

        <button className="role-btn engineer" style={{ width: "100%" }} onClick={() => {
          window.resizeTo(960, 760);
          window.moveTo(
            screen.width / 2 - 480,
            screen.height / 2 - 380
          );
          onStart(code);
        }}>Start session</button>
      </div>
    </div>
  );
}
