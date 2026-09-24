import { useEffect, useRef } from "react";

// size 42 = main window, 46 = cue mix popout (design reference values).
export default function Knob({ label, value, color, onChange, size = 42, showValue = false }) {
  const angle = -135 + (value / 100) * 270;
  const isDragging = useRef(false);
  const startY = useRef(0);
  const startVal = useRef(0);
  const onDown = (e) => { isDragging.current = true; startY.current = e.clientY; startVal.current = value; e.preventDefault(); };
  useEffect(() => {
    const onMove = (e) => { if (!isDragging.current) return; const dy = startY.current - e.clientY; onChange(Math.min(100, Math.max(0, Math.round(startVal.current + dy)))); };
    const onUp = () => { isDragging.current = false; };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => { window.removeEventListener("mousemove", onMove); window.removeEventListener("mouseup", onUp); };
  }, [onChange]);

  const large = size >= 46;
  return (
    <div className={`knob-wrap ${large ? "lg" : ""}`}>
      <div className="knob" style={{ width: size, height: size, borderColor: color }} onMouseDown={onDown}>
        <div
          className="knob-tick"
          style={{ top: large ? 6 : 5, height: large ? 14 : 13, background: color, transform: `translateX(-50%) rotate(${angle}deg)` }}
        />
      </div>
      <span className="knob-lbl">{label}</span>
      {showValue && <span className="knob-val">{value}</span>}
    </div>
  );
}
