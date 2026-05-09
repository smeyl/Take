import { useState } from "react";
import "./styles/global.css";
import SessionScreen from "./components/SessionScreen";
import EngineerApp from "./components/EngineerApp";

export default function App() {
  const [screen, setScreen] = useState("session");
  const [sessionCode, setSessionCode] = useState("");
  const [recording, setRecording] = useState(false);
  const [cue, setCue] = useState({ rev: 72, revMix: 38, del: 50, delMix: 22, comp: 55, ratio: 40, vol: 78 });

  return (
    <div className="root">
      <div className="app-shell">
        {screen === "session" && (
          <SessionScreen onStart={code => { setSessionCode(code); setScreen("engineer"); }} />
        )}
        {screen === "engineer" && (
          <EngineerApp recording={recording} setRecording={setRecording} cue={cue} setCue={setCue} sessionCode={sessionCode} onBack={() => setScreen("session")} />
        )}
      </div>
    </div>
  );
}
