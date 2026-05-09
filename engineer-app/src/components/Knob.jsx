import { useEffect, useRef } from "react";

export default function Knob({ label, value, color, onChange }) {
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

  return (
    <div className="knob-wrap">
      <div className="knob" style={{ borderColor: color + "55" }} onMouseDown={onDown}>
        <div className="knob-tick" style={{ transform: `rotate(${angle}deg)`, background: color }} />
      </div>
      <div className="knob-lbl">{label}</div>
      <div className="knob-val" style={{ color }}>{value}%</div>
    </div>
  );
}
