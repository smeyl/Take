import { useState } from "react";

export default function RoleSelect({ onEngineer }) {
  const [code, setCode] = useState("");
  return (
    <div className="role-wrap">
      <div className="role-title">T<span>ake</span></div>
      <div className="role-sub">Remote recording session</div>
      <input className="role-input" placeholder="Session code — e.g. A7 · F2 · K9" value={code} onChange={e => setCode(e.target.value)} />
      <div className="role-btns">
        <button className="role-btn engineer" onClick={onEngineer}>Join as Engineer</button>
      </div>
    </div>
  );
}
