import { useState, useEffect } from "react";
import CueMix, { sendCue } from "./CueMix";
import { StarIcon } from "./icons";

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
        <span className="cue-pop-title">Cue Mix</span>
        <button
          className={`pin-btn ${pinned ? "on" : ""}`}
          style={{ WebkitAppRegion: "no-drag" }}
          aria-label="Pin on top so Reaper can't cover it"
          aria-pressed={pinned}
          onClick={togglePinned}
        >
          <StarIcon color={pinned ? "#2dd4bf" : "#8a8a90"} />
          Pinned
        </button>
      </div>
      <div className="cue-pop-caption">→ sending to <span>artist</span></div>
      <CueMix cue={cue} onChange={updateCue} variant="popout" />
      {pinned && (
        <div className="cue-pop-foot">
          <p>Pinned — stays above Reaper</p>
        </div>
      )}
    </div>
  );
}
