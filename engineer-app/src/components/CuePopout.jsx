import { useState, useEffect } from "react";
import CueMix, { sendCue } from "./CueMix";

const DEFAULT_CUE = { rev: 0, revMix: 0, del: 0, delMix: 0, comp: 0, vol: 100 };

// Root of the detached cue mix window (loaded at #cue-popout).
export default function CuePopout() {
  const [cue, setCue]       = useState(DEFAULT_CUE);
  const [pinned, setPinned] = useState(true);  // main.js opens the window on top

  useEffect(() => {
    window.take.getCue().then(c => { if (c) setCue(c); });
    return window.take.onCueChanged(setCue);
  }, []);

  const updateCue = (k, v) => {
    const next = { ...cue, [k]: v };
    setCue(next);
    sendCue(k, v);
    window.take.cueChanged(next);
  };

  const togglePinned = () => {
    const next = !pinned;
    setPinned(next);
    window.take.setCuePinned(next);
  };

  return (
    <div className="cue-pop">
      <div className="cue-pop-hdr" style={{ WebkitAppRegion: "drag" }}>
        <div className="cue-pop-title">Cue Mix</div>
        <div
          className={`pill ${pinned ? "on" : ""}`}
          style={{ WebkitAppRegion: "no-drag" }}
          title="Keep this window above other apps"
          onClick={togglePinned}
        >Pinned</div>
      </div>
      <div className="cue-pop-body">
        <div className="cue-pop-caption">→ sending to <span>artist</span></div>
        <CueMix cue={cue} onChange={updateCue} />
        {pinned && <div className="cue-pop-foot">Pinned — stays above Reaper</div>}
      </div>
    </div>
  );
}
