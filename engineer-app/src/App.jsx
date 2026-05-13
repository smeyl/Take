import { useState } from "react";
import "./styles/global.css";
import SessionScreen from "./components/SessionScreen";
import EngineerApp from "./components/EngineerApp";

export default function App() {
  const [screen, setScreen] = useState("session");
  const [sessionCode, setSessionCode] = useState("");
  const [cue, setCue] = useState({ rev: 0, revMix: 0, del: 0, delMix: 0, comp: 0, vol: 100 });

  return (
    <div className="root">
      <div className="app-shell">
        {screen === "session" && (
          <SessionScreen onStart={code => { setSessionCode(code); setScreen("engineer"); }} />
        )}
        {screen === "engineer" && (
          <EngineerApp cue={cue} setCue={setCue} sessionCode={sessionCode} onBack={() => setScreen("session")} />
        )}
      </div>
    </div>
  );
}
