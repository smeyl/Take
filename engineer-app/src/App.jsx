import { useState, useEffect, useRef } from "react";

const C = {
  bg:      "#0a0a0b",
  surface: "#111113",
  raised:  "#18181c",
  border:  "#222228",
  dim:     "#3a3a45",
  muted:   "#5c5c6e",
  body:    "#a0a0b8",
  bright:  "#d4d4e8",
  white:   "#f0f0f8",
  blue:    "#4f8fff",
  green:   "#3ddc84",
  red:     "#ff4f4f",
  amber:   "#ffb340",
  teal:    "#2dd4bf",
  purple:  "#a78bfa",
};

const SONG = [
  { id:"intro",   label:"Intro",   bars:[1,8]   },
  { id:"verse1",  label:"Verse 1", bars:[9,16]  },
  { id:"chorus1", label:"Chorus",  bars:[17,24] },
  { id:"verse2",  label:"Verse 2", bars:[25,32] },
  { id:"chorus2", label:"Chorus",  bars:[33,40] },
  { id:"bridge",  label:"Bridge",  bars:[41,48] },
  { id:"outro",   label:"Outro",   bars:[49,56] },
];
const TOTAL_BARS = 56;
const PUNCH = { start:33, end:40 };

function getSectionAtBar(bar) { return SONG.find(s => bar >= s.bars[0] && bar <= s.bars[1]) || SONG[0]; }
function getSectionIdx(s) { return SONG.findIndex(x => x.id === s.id); }
function toWinPct(bar, winStart, winBars) { return ((bar - winStart) / winBars) * 100; }

const css = `
  @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@300;400;500&family=Syne:wght@700;800&display=swap');
  *,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
  body{background:${C.bg};color:${C.body};font-family:'DM Mono','Courier New',monospace}
  ::-webkit-scrollbar{width:4px}
  ::-webkit-scrollbar-track{background:${C.bg}}
  ::-webkit-scrollbar-thumb{background:${C.dim};border-radius:2px}
  .root{min-height:100vh;display:flex;flex-direction:column}
  .nav{display:flex;align-items:center;padding:0 24px;border-bottom:1px solid ${C.border};background:${C.surface};position:sticky;top:0;z-index:100}
  .nav-logo{font-family:'Syne',sans-serif;font-weight:800;font-size:17px;color:${C.white};padding:18px 0;margin-right:28px;letter-spacing:-0.5px}
  .nav-logo span{color:${C.blue}}
  .nav-tab{padding:0 18px;height:56px;display:flex;align-items:center;font-size:10px;letter-spacing:0.1em;text-transform:uppercase;font-weight:500;color:${C.muted};cursor:pointer;border-bottom:2px solid transparent;transition:all 0.15s;user-select:none}
  .nav-tab:hover{color:${C.body}}
  .nav-tab.active{color:${C.white};border-bottom-color:${C.blue}}
  .sim-btn{margin-left:auto;padding:6px 16px;border-radius:5px;font-size:10px;cursor:pointer;font-family:inherit;font-weight:500;transition:all 0.15s;user-select:none}
  .app-shell{flex:1;display:flex;align-items:flex-start;justify-content:center;padding:28px 24px 60px;gap:20px;flex-wrap:wrap}

  /* primitives */
  .dot{width:7px;height:7px;border-radius:50%;flex-shrink:0}
  .dot.g{background:${C.green};box-shadow:0 0 6px ${C.green}88}
  .dot.r{background:${C.red}}
  .dot.a{background:${C.amber};box-shadow:0 0 6px ${C.amber}77}
  .dot.b{background:${C.blue};box-shadow:0 0 6px ${C.blue}77}
  .dot.d{background:${C.dim}}
  .sec-label{font-size:9px;letter-spacing:0.12em;text-transform:uppercase;color:${C.muted};font-weight:500;margin-bottom:6px}
  .toggle{width:30px;height:17px;background:${C.dim};border-radius:9px;cursor:pointer;position:relative;transition:background 0.2s;flex-shrink:0}
  .toggle.on{background:${C.blue}}
  .toggle::after{content:'';position:absolute;top:3px;left:3px;width:11px;height:11px;border-radius:50%;background:white;transition:transform 0.2s}
  .toggle.on::after{transform:translateX(13px)}
  .tog-row{display:flex;align-items:center;justify-content:space-between;font-size:11px;color:${C.body}}
  .pill-grp{display:flex;gap:4px}
  .pill{padding:3px 9px;border-radius:10px;border:1px solid ${C.border};font-size:9px;cursor:pointer;color:${C.muted};transition:all 0.15s;user-select:none}
  .pill.on{background:${C.blue}22;border-color:${C.blue};color:${C.blue}}
  .meter-bar{height:5px;background:${C.raised};border-radius:3px;overflow:hidden;margin-bottom:4px}
  .meter-fill{height:100%;border-radius:3px;background:linear-gradient(90deg,${C.green},${C.amber})}
  .meter-lbl{display:flex;justify-content:space-between;font-size:9px;color:${C.muted};margin-bottom:2px}

  /* ── TRACK WINDOW ── */
  .tw{border:1px solid ${C.border};border-radius:6px;overflow:hidden;background:${C.raised}}
  .tw-secs{display:flex;height:28px;border-bottom:1px solid ${C.border}}
  .tw-sec{display:flex;align-items:center;justify-content:center;border-right:1px solid ${C.border};overflow:hidden;flex:1}
  .tw-sec:last-child{border-right:none}
  .tw-sec-lbl{font-size:9px;font-weight:500;letter-spacing:0.04em;white-space:nowrap;padding:0 8px}
  .tw-wave{position:relative;height:52px;overflow:hidden}
  .tw-punch{position:absolute;top:0;bottom:0;background:${C.red}18;border-left:1.5px solid ${C.red}66;border-right:1.5px solid ${C.red}66;pointer-events:none;z-index:2}
  .tw-punch-lbl{position:absolute;top:4px;font-size:8px;color:${C.red};font-weight:500;z-index:3;white-space:nowrap}
  .tw-ph{position:absolute;top:0;bottom:0;width:1.5px;z-index:4;pointer-events:none}
  .tw-ph::before{content:'';position:absolute;top:0;left:-4px;border-left:4px solid transparent;border-right:4px solid transparent;border-top:6px solid ${C.blue}}
  .tw-ruler{height:14px;border-top:1px solid ${C.border};background:${C.bg};position:relative;overflow:hidden}
  .tw-tick{position:absolute;display:flex;flex-direction:column;align-items:center}
  .tw-tick-line{width:0.5px;height:4px;background:${C.dim}}
  .tw-tick-txt{font-size:7px;color:${C.dim};margin-top:1px;white-space:nowrap}

  /* ── ROLE SELECT ── */
  .role-wrap{width:400px;background:${C.surface};border:1px solid ${C.border};border-radius:12px;overflow:hidden;display:flex;flex-direction:column;align-items:center;padding:48px 32px 32px}
  .role-title{font-family:'Syne',sans-serif;font-weight:800;font-size:52px;color:${C.white};letter-spacing:-1px;margin-bottom:8px}
  .role-title span{color:${C.blue}}
  .role-sub{font-size:11px;color:${C.muted};letter-spacing:0.08em;margin-bottom:40px}
  .role-input{width:100%;background:${C.raised};border:1px solid ${C.border};border-radius:6px;padding:10px 14px;font-size:11px;color:${C.bright};font-family:inherit;outline:none;margin-bottom:16px;letter-spacing:0.05em}
  .role-input::placeholder{color:${C.dim}}
  .role-input:focus{border-color:${C.blue}55}
  .role-btns{display:flex;gap:10px;width:100%}
  .role-btn{flex:1;padding:11px;border-radius:6px;font-size:11px;font-weight:500;font-family:inherit;cursor:pointer;border:none;letter-spacing:0.05em;transition:all 0.15s}
  .role-btn.artist{background:${C.green};color:#04342C}
  .role-btn.artist:hover{background:#4fe896}
  .role-btn.engineer{background:${C.blue};color:white}
  .role-btn.engineer:hover{background:#6fa8ff}

  /* ── ARTIST APP ── */
  .artist-wrap{width:390px;background:${C.surface};border:1px solid ${C.border};border-radius:12px;overflow:hidden;display:flex;flex-direction:column}
  .artist-hdr{background:${C.bg};border-bottom:1px solid ${C.border};padding:11px 16px;display:flex;align-items:center;justify-content:space-between}
  .artist-logo{font-family:'Syne',sans-serif;font-weight:800;font-size:16px;color:${C.white};letter-spacing:-0.3px}
  .artist-logo span{color:${C.blue}}
  .artist-code{font-size:9px;font-family:'DM Mono',monospace;color:${C.dim};letter-spacing:0.1em;background:${C.raised};padding:3px 8px;border-radius:4px;border:1px solid ${C.border}}
  .artist-body{padding:14px 16px;display:flex;flex-direction:column;gap:12px;flex:1}
  .conn-strip{display:flex;gap:12px;align-items:center;justify-content:center}
  .conn-item{display:flex;align-items:center;gap:5px;font-size:9px;color:${C.muted}}
  .input-sel{background:${C.raised};border:1px solid ${C.border};border-radius:5px;padding:7px 10px;font-size:10px;color:${C.bright};display:flex;justify-content:space-between;align-items:center;cursor:pointer}
  .ring-wrap{display:flex;justify-content:center;padding:6px 0}
  .ring{width:132px;height:132px;border-radius:50%;border:3px solid ${C.border};display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;transition:all 0.3s}
  .ring.ready{border-color:${C.blue};box-shadow:0 0 20px ${C.blue}33}
  .ring.rec{border-color:${C.red};box-shadow:0 0 32px ${C.red}44,inset 0 0 24px ${C.red}11;animation:rpulse 1.5s ease-in-out infinite}
  @keyframes rpulse{0%,100%{box-shadow:0 0 32px ${C.red}44,inset 0 0 24px ${C.red}11}50%{box-shadow:0 0 48px ${C.red}66,inset 0 0 36px ${C.red}22}}
  .ring-status{font-family:'Syne',sans-serif;font-size:10px;font-weight:700;letter-spacing:0.12em;text-transform:uppercase}
  .ring-num{font-size:34px;font-weight:300;color:${C.white};line-height:1}
  .ring-sub{font-size:9px;color:${C.muted}}
  .section-now{border:1px solid ${C.border};border-radius:6px;padding:10px 14px;display:flex;align-items:center;justify-content:space-between;background:${C.raised}}
  .section-now-name{font-family:'Syne',sans-serif;font-size:16px;font-weight:700}
  .section-now-bars{font-size:9px;color:${C.muted};margin-top:2px}
  .section-right{display:flex;flex-direction:column;align-items:flex-end;gap:3px;font-size:9px;color:${C.muted}}
  .cue-panel{background:${C.raised};border:1px solid ${C.border};border-radius:6px;padding:10px 12px}
  .cue-title{font-size:9px;letter-spacing:0.1em;text-transform:uppercase;color:${C.muted};margin-bottom:10px;display:flex;justify-content:space-between}
  .cue-row{display:flex;justify-content:space-around}
  .cue-knob{display:flex;flex-direction:column;align-items:center;gap:3px}
  .cue-ring{width:32px;height:32px;border-radius:50%;border:1.5px solid ${C.dim};position:relative;background:${C.bg};cursor:ns-resize}
  .cue-tick{position:absolute;width:2px;height:10px;border-radius:1px;top:4px;transform-origin:bottom center;left:calc(50% - 1px)}
  .cue-lbl{font-size:7px;color:${C.muted};text-align:center}
  .cue-val{font-size:8px;font-weight:500;text-align:center}
  .backing-bar{background:${C.raised};border:1px solid ${C.border};border-radius:6px;padding:8px 10px;display:flex;align-items:center;justify-content:space-between}
  .artist-footer{background:${C.bg};border-top:1px solid ${C.border};padding:7px 16px;display:flex;gap:0;font-size:9px;color:${C.muted};align-items:center}
  .footer-sep{margin:0 10px;color:${C.dim}}
  .footer-val{color:${C.body}}
  .back-btn{font-size:9px;color:${C.blue};cursor:pointer;margin-right:auto}

  /* ── ENGINEER APP ── */
  .eng-wrap{background:${C.surface};border:1px solid ${C.border};border-radius:12px;overflow:hidden;display:flex;flex-direction:column;font-size:11px}
  .eng-hdr{display:flex;align-items:center;border-bottom:1px solid ${C.border};background:${C.bg};padding:0 16px;height:44px;gap:14px}
  .eng-logo{font-family:'Syne',sans-serif;font-weight:800;font-size:15px;color:${C.white};letter-spacing:-0.3px;margin-right:auto}
  .eng-logo span{color:${C.blue}}
  .eng-conn{display:flex;align-items:center;gap:5px;font-size:9px;color:${C.muted}}
  .eng-body{display:flex;flex:1}
  .ecol{padding:12px 14px;border-right:1px solid ${C.border};display:flex;flex-direction:column;gap:10px}
  .ecol:last-child{border-right:none}
  .ebtn{padding:8px 12px;border-radius:5px;border:1px solid ${C.border};cursor:pointer;font-family:inherit;font-size:10px;font-weight:500;text-align:center;transition:all 0.15s;user-select:none}
  .ebtn-rec{background:${C.red}22;border-color:${C.red}55;color:${C.red}}
  .ebtn-rec.on{background:${C.red};color:white}
  .ebtn-ghost{background:${C.raised};color:${C.body}}
  .ebtn-amber{background:${C.amber}18;border-color:${C.amber}44;color:${C.amber}}
  .ebtn-blue{background:${C.blue}18;border-color:${C.blue}44;color:${C.blue};width:100%;display:block}
  .take-row{display:flex;align-items:center;gap:8px;padding:6px 8px;background:${C.raised};border:1px solid ${C.border};border-radius:5px}
  .take-row.live{border-color:${C.red}44;background:${C.red}08}
  .take-num{font-size:12px;font-weight:500;min-width:22px}
  .take-wave{flex:1;height:20px;background:${C.border};border-radius:3px;overflow:hidden}
  .take-badge{font-size:8px;padding:2px 7px;border-radius:9px;font-weight:500;border:1px solid}
  .tb-wav{background:${C.green}15;color:${C.green};border-color:${C.green}44}
  .tb-live{background:${C.red}15;color:${C.red};border-color:${C.red}44}
  .tb-sync{background:${C.amber}15;color:${C.amber};border-color:${C.amber}44}
  .knob-wrap{display:flex;flex-direction:column;align-items:center;gap:3px}
  .knob{width:36px;height:36px;border-radius:50%;background:${C.bg};border:2px solid ${C.dim};position:relative;cursor:ns-resize}
  .knob-tick{position:absolute;width:2px;height:12px;border-radius:1px;top:4px;transform-origin:bottom center;left:calc(50% - 1px)}
  .knob-lbl{font-size:8px;color:${C.muted};text-align:center}
  .knob-val{font-size:9px;font-weight:500;text-align:center}
  .knob-row{display:flex;justify-content:space-around;gap:4px}
  .group-label{display:flex;align-items:center;gap:6px;margin-bottom:4px}
  .group-accent{width:2px;height:12px;border-radius:1px;flex-shrink:0}
  .group-text{font-size:8px;letter-spacing:0.1em;text-transform:uppercase;font-weight:500}
  .eq-wrap{display:flex;gap:10px;align-items:flex-end}
  .eq-band{display:flex;flex-direction:column;align-items:center;gap:4px;flex:1}
  .eq-slider{writing-mode:vertical-lr;direction:rtl;width:4px;height:44px;-webkit-appearance:none;appearance:none;background:${C.dim};border-radius:2px;cursor:pointer}
  .eq-slider::-webkit-slider-thumb{-webkit-appearance:none;width:10px;height:10px;border-radius:50%;background:${C.blue};box-shadow:0 0 5px ${C.blue}88}
  .eq-freq{font-size:8px;color:${C.muted}}
  .sync-box{background:${C.raised};border:1px solid ${C.border};border-radius:5px;padding:8px 10px;display:flex;flex-direction:column;gap:5px}
  .sync-row{display:flex;align-items:center;justify-content:space-between;padding:3px 0;border-bottom:1px solid ${C.border};font-size:10px;color:${C.body}}
  .sync-row:last-child{border-bottom:none}
  .sync-now{width:100%;padding:6px;border-radius:5px;border:1px solid ${C.blue}44;background:${C.blue}11;color:${C.blue};font-size:9px;font-weight:500;font-family:inherit;cursor:pointer;text-align:center}
  .track-check{display:flex;flex-direction:column;gap:6px}
  .track-item{display:flex;align-items:center;gap:7px;font-size:10px;cursor:pointer}
  .swap-card{background:${C.raised};border:1px solid ${C.border};border-radius:5px;padding:8px 10px;font-size:9px}
  .eng-footer{background:${C.bg};border-top:1px solid ${C.border};padding:6px 16px;display:flex;gap:0;font-size:9px;color:${C.muted};align-items:center}

  /* ── DETAILS PANEL ── */
  .details-wrap{width:300px;background:${C.surface};border:1px solid ${C.border};border-left:none;border-radius:0 12px 12px 0;overflow:hidden;display:flex;flex-direction:column;font-size:11px}
  .details-hdr{background:${C.bg};border-bottom:1px solid ${C.border};padding:12px 16px;display:flex;align-items:center;justify-content:space-between}
  .details-title{font-family:'Syne',sans-serif;font-weight:700;font-size:13px;color:${C.white}}
  .details-close{width:24px;height:24px;border-radius:5px;background:${C.raised};border:1px solid ${C.border};display:flex;align-items:center;justify-content:center;cursor:pointer;font-size:11px;color:${C.muted}}
  .details-body{padding:14px;display:flex;flex-direction:column;gap:12px;flex:1}
  .conn-grid{display:grid;grid-template-columns:1fr 1fr;gap:5px}
  .conn-tile{background:${C.raised};border:1px solid ${C.border};border-radius:5px;padding:7px 10px;display:flex;align-items:center;gap:7px}
  .conn-name{font-size:9px;color:${C.muted};flex:1}
  .conn-ok{font-size:9px;color:${C.green};font-weight:500}
  .log-box{background:${C.bg};border:1px solid ${C.border};border-radius:5px;padding:8px;display:flex;flex-direction:column;gap:4px;max-height:140px;overflow-y:auto}
  .log-line{display:flex;gap:8px;font-size:9px;line-height:1.5}
  .log-time{color:${C.dim};flex-shrink:0}
  .log-msg{color:${C.body}}
  .log-msg.ok{color:${C.green};opacity:0.8}
  .log-msg.info{color:${C.blue};opacity:0.8}
  .log-msg.warn{color:${C.amber};opacity:0.8}
  .bw-grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:5px}
  .bw-tile{background:${C.raised};border:1px solid ${C.border};border-radius:5px;padding:8px;display:flex;flex-direction:column;gap:2px}
  .bw-lbl{font-size:8px;color:${C.muted};text-transform:uppercase;letter-spacing:0.08em}
  .bw-val{font-size:13px;font-weight:500;color:${C.white}}
  .bw-unit{font-size:9px;color:${C.muted}}
`;

// ── Waveform ─────────────────────────────────────────────────────────────────
function WaveCanvas({ width=200, height=40, color=C.blue, animated=false, progress=1 }) {
  const ref = useRef();
  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    canvas.width = width; canvas.height = height;
    const bars = Math.floor(width / 3);
    let frame, t = 0;
    const draw = () => {
      ctx.clearRect(0, 0, width, height);
      const mid = height / 2;
      for (let i = 0; i < bars; i++) {
        const x = i * 3;
        const phase = animated ? Math.sin(i * 0.28 + t) * 0.6 + 0.4 : Math.abs(Math.sin(i * 0.43 + i * 0.11)) * 0.8 + 0.2;
        const amp = phase * (mid * 0.85) + 1;
        ctx.fillStyle = (x / width) < progress ? color + "bb" : C.dim;
        ctx.fillRect(x, mid - amp, 2, amp * 2);
      }
      if (animated) { t += 0.05; frame = requestAnimationFrame(draw); }
    };
    draw();
    return () => cancelAnimationFrame(frame);
  }, [width, height, color, animated, progress]);
  return <canvas ref={ref} style={{ display:"block", width:"100%", height }} />;
}

// ── Knob ──────────────────────────────────────────────────────────────────────
function Knob({ label, value, color, onChange, small=false }) {
  const angle = -135 + (value / 100) * 270;
  const isDragging = useRef(false);
  const startY = useRef(0);
  const startVal = useRef(0);
  const onDown = (e) => { isDragging.current=true; startY.current=e.clientY; startVal.current=value; e.preventDefault(); };
  useEffect(() => {
    const onMove = (e) => { if (!isDragging.current) return; const dy = startY.current - e.clientY; onChange(Math.min(100, Math.max(0, Math.round(startVal.current + dy)))); };
    const onUp = () => { isDragging.current = false; };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => { window.removeEventListener("mousemove", onMove); window.removeEventListener("mouseup", onUp); };
  }, [onChange]);

  if (small) return (
    <div className="cue-knob">
      <div className="cue-ring" style={{ borderColor: color + "55" }} onMouseDown={onDown}>
        <div className="cue-tick" style={{ transform:`rotate(${angle}deg)`, background:color }} />
      </div>
      <div className="cue-lbl">{label}</div>
      <div className="cue-val" style={{ color }}>{value}%</div>
    </div>
  );
  return (
    <div className="knob-wrap">
      <div className="knob" style={{ borderColor: color + "55" }} onMouseDown={onDown}>
        <div className="knob-tick" style={{ transform:`rotate(${angle}deg)`, background:color }} />
      </div>
      <div className="knob-lbl">{label}</div>
      <div className="knob-val" style={{ color }}>{value}%</div>
    </div>
  );
}

// ── Track window ──────────────────────────────────────────────────────────────
function TrackWindow({ playhead }) {
  const currentBar = Math.round(1 + playhead * (TOTAL_BARS - 1));
  const currentIdx = getSectionIdx(getSectionAtBar(currentBar));
  const startIdx = Math.max(0, currentIdx - 1);
  const endIdx = Math.min(SONG.length - 1, currentIdx + 1);
  const vis = SONG.slice(startIdx, endIdx + 1);
  const winStart = vis[0].bars[0];
  const winEnd = vis[vis.length - 1].bars[1];
  const winBars = winEnd - winStart + 1;
  const phPct = Math.max(0, Math.min(100, toWinPct(currentBar, winStart, winBars)));
  const pIn = PUNCH.start <= winEnd && PUNCH.end >= winStart;
  const pL = toWinPct(Math.max(PUNCH.start, winStart), winStart, winBars);
  const pR = toWinPct(Math.min(PUNCH.end + 1, winEnd + 1), winStart, winBars);
  return (
    <div className="tw">
      <div className="tw-secs">
        {vis.map(s => {
          const w = (s.bars[1] - s.bars[0] + 1) / winBars * 100;
          const isCur = s.id === getSectionAtBar(currentBar).id;
          return (
            <div key={s.id} className="tw-sec" style={{ width:`${w}%`, background: isCur ? C.blue+"18" : C.raised, borderColor:C.border }}>
              <span className="tw-sec-lbl" style={{ color: isCur ? C.blue : C.muted, fontWeight: isCur ? 600 : 400 }}>{s.label}</span>
            </div>
          );
        })}
      </div>
      <div className="tw-wave">
        <WaveCanvas width={700} height={52} color={C.teal} progress={phPct / 100} />
        <div style={{ position:"absolute", top:0, bottom:0, left:0, width:`${phPct}%`, background:"rgba(45,212,191,0.07)", pointerEvents:"none", zIndex:1 }} />
        {pIn && <>
          <div className="tw-punch" style={{ left:`${pL}%`, width:`${pR-pL}%` }} />
          <div className="tw-punch-lbl" style={{ left:`${pL+(pR-pL)/2}%`, transform:"translateX(-50%)" }}>● REC ZONE</div>
        </>}
        <div className="tw-ph" style={{ left:`${phPct}%`, background:C.blue, boxShadow:`0 0 5px ${C.blue}` }} />
      </div>
      <div className="tw-ruler">
        {vis.map((s,i) => {
          const pct = toWinPct(s.bars[0], winStart, winBars);
          const mins = Math.floor((s.bars[0]-1)*2/60);
          const secs = String((s.bars[0]-1)*2%60).padStart(2,"0");
          return <div key={i} className="tw-tick" style={{ left:`${pct}%` }}><div className="tw-tick-line" /><div className="tw-tick-txt">{mins}:{secs}</div></div>;
        })}
      </div>
    </div>
  );
}

// ── Role Select ───────────────────────────────────────────────────────────────
function RoleSelect({ onArtist, onEngineer }) {
  const [code, setCode] = useState("");
  return (
    <div className="role-wrap">
      <div className="role-title">T<span>ake</span></div>
      <div className="role-sub">Remote recording session</div>
      <input className="role-input" placeholder="Session code — e.g. A7 · F2 · K9" value={code} onChange={e => setCode(e.target.value)} />
      <div className="role-btns">
        <button className="role-btn artist" onClick={onArtist}>Join as Artist</button>
        <button className="role-btn engineer" onClick={onEngineer}>Join as Engineer</button>
      </div>
    </div>
  );
}

// ── Details Panel ─────────────────────────────────────────────────────────────
function DetailsPanel({ onClose, recording }) {
  const logs = [
    { t:"14:51:03", msg:"Session started — A7·F2·K9", cls:"info" },
    { t:"14:51:09", msg:"Artist app connected", cls:"ok" },
    { t:"14:53:22", msg:"Backing track sent (8.2MB)", cls:"info" },
    { t:"14:55:58", msg:"T4 sync complete — swap 0.4s", cls:"ok" },
    { t:"14:56:20", msg:"Recording started — T5", cls:"" },
    ...(recording ? [{ t:"14:56:52", msg:"T5 recording — 0:32 elapsed", cls:"warn" }] : []),
  ];
  return (
    <div className="details-wrap">
      <div className="details-hdr">
        <div className="details-title">Details</div>
        <div className="details-close" onClick={onClose}>×</div>
      </div>
      <div className="details-body">
        <div>
          <div className="sec-label" style={{ marginBottom:8 }}>Connections</div>
          <div className="conn-grid">
            {[["Plugin link",true],["Relay server",true],["Artist app",true],["Reaper API",true],["BlackHole 2ch",true],["File watcher",true]].map(([name,ok]) => (
              <div key={name} className="conn-tile">
                <div className={`dot ${ok?"g":"r"}`} />
                <div className="conn-name">{name}</div>
                <div className="conn-ok">{ok?"OK":"ERR"}</div>
              </div>
            ))}
          </div>
        </div>
        <div>
          <div className="sec-label" style={{ marginBottom:8 }}>Activity</div>
          <div className="log-box">
            {logs.map((l,i) => <div key={i} className="log-line"><span className="log-time">{l.t}</span><span className={`log-msg ${l.cls}`}>{l.msg}</span></div>)}
          </div>
        </div>
        <div>
          <div className="sec-label" style={{ marginBottom:8 }}>Bandwidth</div>
          <div className="bw-grid">
            <div className="bw-tile"><div className="bw-lbl">Stream Up</div><div><span className="bw-val">0.8</span> <span className="bw-unit">Mbps</span></div></div>
            <div className="bw-tile"><div className="bw-lbl">Stream Dn</div><div><span className="bw-val">0.4</span> <span className="bw-unit">Mbps</span></div></div>
            <div className="bw-tile"><div className="bw-lbl">Total</div><div><span className="bw-val">214</span> <span className="bw-unit">MB</span></div></div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Artist App ────────────────────────────────────────────────────────────────
function ArtistApp({ recording, playhead, cue, setCue, onBack }) {
  const [hearMix, setHearMix] = useState(true);
  const [showDetails, setShowDetails] = useState(false);
  const currentBar = Math.round(1 + playhead * (TOTAL_BARS - 1));
  const cur = getSectionAtBar(currentBar);
  const next = SONG[getSectionIdx(cur) + 1] || null;
  const barsLeft = cur.bars[1] - currentBar;

  return (
    <div style={{ display:"flex" }}>
      <div className="artist-wrap">
        <div className="artist-hdr">
          <div className="artist-logo">T<span>ake</span></div>
          <div className="artist-code">A7 · F2 · K9</div>
        </div>
        <div className="artist-body">
          {/* Connection strip */}
          <div className="conn-strip">
            <div className="conn-item"><div className="dot g" />Companion</div>
            <div className="conn-item"><div className="dot g" />Server</div>
            <div className="conn-item"><div className="dot d" />Engineer</div>
          </div>
          {/* Input */}
          <div>
            <div className="sec-label">Input</div>
            <div className="input-sel"><span style={{ fontSize:10, color:C.bright }}>Focusrite 2i2 — Input 1 (Mono)</span><span style={{ color:C.muted }}>▾</span></div>
          </div>
          {/* Meters */}
          <div>
            <div className="meter-lbl"><span>L</span><span style={{ color:C.green }}>–12 dBFS</span></div>
            <div className="meter-bar"><div className="meter-fill" style={{ width:"68%" }} /></div>
            <div className="meter-lbl"><span>R</span><span style={{ color:C.green }}>–14 dBFS</span></div>
            <div className="meter-bar"><div className="meter-fill" style={{ width:"61%" }} /></div>
          </div>
          {/* Ring */}
          <div className="ring-wrap">
            <div className={`ring ${recording?"rec":"ready"}`}>
              <div className="ring-status" style={{ color: recording?C.red:C.blue }}>{recording?"● rec":"ready"}</div>
              <div className="ring-num">T5</div>
              <div className="ring-sub">{recording?"0:32 elapsed":"Awaiting record"}</div>
            </div>
          </div>
          {/* Track window */}
          <div>
            <div className="sec-label" style={{ display:"flex", justifyContent:"space-between" }}>
              <span>Backing track</span>
              <span style={{ color:C.dim, fontSize:8 }}>Engineer controlled</span>
            </div>
            <TrackWindow playhead={playhead} />
          </div>
          {/* Section now */}
          <div className="section-now" style={{ borderColor: recording ? C.red+"33" : C.border }}>
            <div>
              <div style={{ fontSize:8, color:C.muted, letterSpacing:"0.1em", textTransform:"uppercase", marginBottom:3 }}>Now</div>
              <div className="section-now-name" style={{ color:C.blue }}>{cur.label}</div>
              <div className="section-now-bars">Bars {cur.bars[0]}–{cur.bars[1]}</div>
            </div>
            <div className="section-right">
              {next && <><span>Next: {next.label}</span><span style={{ color:C.amber }}>~{barsLeft*2}s</span></>}
              {recording && <span style={{ color:C.red, fontWeight:500 }}>● Recording</span>}
            </div>
          </div>
          {/* Cue mix */}
          <div className="cue-panel">
            <div className="cue-title">
              <span>Cue mix</span>
              <span style={{ color:C.dim, fontSize:8 }}>Drag to adjust</span>
            </div>
            <div className="cue-row">
              {[
                { k:"rev",    label:"Reverb",  color:C.purple },
                { k:"revMix", label:"Rev mix", color:C.purple },
                { k:"del",    label:"Delay",   color:C.teal   },
                { k:"delMix", label:"Del mix", color:C.teal   },
                { k:"comp",   label:"Comp",    color:C.amber  },
                { k:"vol",    label:"Cue vol", color:C.green  },
              ].map(({ k, label, color }) => (
                <Knob key={k} label={label} value={cue[k]} color={color} small onChange={v => setCue(c => ({ ...c, [k]:v }))} />
              ))}
            </div>
          </div>
          {/* Toggles */}
          <div style={{ display:"flex", flexDirection:"column", gap:8 }}>
            <div className="tog-row"><span>Hear engineer mix</span><div className={`toggle ${hearMix?"on":""}`} onClick={() => setHearMix(h=>!h)} /></div>
            <div className="tog-row"><span style={{ color:C.muted }}>Engineer controls record</span><div style={{ display:"flex", alignItems:"center", gap:5 }}><div className="dot g" /><span style={{ fontSize:9, color:C.green }}>Active</span></div></div>
          </div>
          {/* Backing status */}
          <div className="backing-bar">
            <div><div style={{ fontSize:10, color:C.body, fontWeight:500 }}>session_BT_v3_mix.mp3</div><div style={{ fontSize:9, color:C.muted, marginTop:1 }}>From engineer · 3m ago</div></div>
            <div style={{ fontSize:9, color:C.green, fontWeight:500 }}>✓ Ready</div>
          </div>
        </div>
        {/* Footer */}
        <div className="artist-footer">
          <span className="back-btn" onClick={onBack}>← Back</span>
          <span className="footer-val">22ms</span><span className="footer-sep">|</span>
          <span>Take</span><span className="footer-val" style={{ marginLeft:4 }}>T5</span><span className="footer-sep">|</span>
          <span>Stream</span><span className="footer-val" style={{ marginLeft:4 }}>AAC 256</span>
          <span style={{ marginLeft:"auto", cursor:"pointer", color: showDetails?C.blue:C.muted, fontSize:9 }} onClick={() => setShowDetails(d=>!d)}>Details</span>
        </div>
      </div>
      {showDetails && <DetailsPanel onClose={() => setShowDetails(false)} recording={recording} />}
    </div>
  );
}

// ── Engineer App ──────────────────────────────────────────────────────────────
function EngineerApp({ recording, setRecording, cue, setCue, onBack }) {
  const [streamQ, setStreamQ] = useState("AAC 256");
  const [syncFmt, setSyncFmt] = useState("WAV 24");
  const [autoSync, setAutoSync] = useState(true);
  const [placeTimeline, setPlaceTimeline] = useState(true);
  const [notifySync, setNotifySync] = useState(false);
  const [tracks, setTracks] = useState({ drums:true, bass:true, keys:true });
  const [btQ, setBtQ] = useState("MP3 256");
  const [btSent, setBtSent] = useState(true);
  const [showDetails, setShowDetails] = useState(false);

  const updateCue = (k, v) => setCue(c => ({ ...c, [k]:v }));
  const takes = [
    { id:"T1", s:"done" }, { id:"T2", s:"done" }, { id:"T3", s:"done" },
    { id:"T4", s:"syncing", pct:72 }, { id:"T5", s: recording?"live":"idle" },
  ];

  return (
    <div style={{ display:"flex" }}>
      <div className="eng-wrap" style={{ width: showDetails ? "auto" : "auto" }}>
        {/* Header */}
        <div className="eng-hdr">
          <div className="eng-logo">T<span>ake</span></div>
          {[["g","Companion"],["g","Server"],["g","Artist"],["d","Reaper"]].map(([dot,label]) => (
            <div key={label} className="eng-conn"><div className={`dot ${dot}`} />{label}</div>
          ))}
          <div style={{ marginLeft:"auto", display:"flex", alignItems:"center", gap:10, fontSize:9 }}>
            {recording
              ? <><div className="dot r" /><span style={{ color:C.red }}>T5 recording — 0:32</span></>
              : <span style={{ color:C.muted }}>A7 · F2 · K9</span>}
            <span style={{ color: showDetails?C.blue:C.muted, cursor:"pointer" }} onClick={() => setShowDetails(d=>!d)}>Details</span>
          </div>
        </div>

        <div className="eng-body">
          {/* Left col */}
          <div className="ecol" style={{ width:210, flexShrink:0 }}>
            <div>
              <div className="sec-label">Artist input</div>
              <div className="meter-lbl"><span>L</span><span style={{ color:C.green }}>–12</span></div>
              <div className="meter-bar"><div className="meter-fill" style={{ width:"68%" }} /></div>
              <div className="meter-lbl"><span>R</span><span style={{ color:C.green }}>–14</span></div>
              <div className="meter-bar"><div className="meter-fill" style={{ width:"61%" }} /></div>
            </div>
            <div>
              <div className="sec-label">Takes</div>
              <div style={{ display:"flex", flexDirection:"column", gap:4 }}>
                {takes.map(t => (
                  <div key={t.id} className={`take-row ${t.s==="live"?"live":""}`}>
                    <div className="take-num" style={{ color: t.s==="live"?C.red:t.s==="syncing"?C.amber:t.s==="done"?C.green:C.dim }}>{t.id}</div>
                    <div className="take-wave">{t.s!=="idle" && <WaveCanvas width={110} height={20} color={t.s==="live"?C.red:t.s==="done"?C.green:C.amber} animated={t.s==="live"} progress={t.s==="syncing"?t.pct/100:1} />}</div>
                    {t.s==="done" && <div className="take-badge tb-wav">WAV</div>}
                    {t.s==="live" && <div className="take-badge tb-live">LIVE</div>}
                    {t.s==="syncing" && <div className="take-badge tb-sync">{t.pct}%</div>}
                  </div>
                ))}
              </div>
            </div>
            <div>
              <div className="sec-label">Transport</div>
              <div style={{ display:"flex", gap:6, marginBottom:6 }}>
                <div className={`ebtn ebtn-rec ${recording?"on":""}`} style={{ flex:1 }} onClick={() => setRecording(r=>!r)}>{recording?"■ Stop":"● Rec"}</div>
                <div className="ebtn ebtn-ghost" style={{ flex:1 }}>↩ RTZ</div>
              </div>
              <div className="ebtn ebtn-amber" style={{ width:"100%", textAlign:"center" }}>⊡ Punch in/out</div>
            </div>
            <div>
              <div className="sec-label">Sync</div>
              <div className="sync-box">
                <div className="sync-row"><span>Auto-sync lossless</span><div className={`toggle ${autoSync?"on":""}`} onClick={() => setAutoSync(a=>!a)} /></div>
                <div className="sync-row"><span>Place on timeline</span><div className={`toggle ${placeTimeline?"on":""}`} onClick={() => setPlaceTimeline(p=>!p)} /></div>
                <div className="sync-row"><span>Notify on sync</span><div className={`toggle ${notifySync?"on":""}`} onClick={() => setNotifySync(n=>!n)} /></div>
              </div>
              <div style={{ height:6 }} />
              <div className="sec-label">Stream quality</div>
              <div className="pill-grp">{["AAC 128","AAC 256","FLAC"].map(q => <div key={q} className={`pill ${streamQ===q?"on":""}`} onClick={() => setStreamQ(q)}>{q}</div>)}</div>
              <div style={{ height:6 }} />
              <div className="sec-label">Sync format</div>
              <div className="pill-grp">{["FLAC","WAV 24","WAV 32f"].map(f => <div key={f} className={`pill ${syncFmt===f?"on":""}`} onClick={() => setSyncFmt(f)}>{f}</div>)}</div>
              <div style={{ height:6 }} />
              <div className="sync-now" style={{ opacity: autoSync?0.4:1, cursor:autoSync?"default":"pointer" }}>
                {autoSync ? "Auto-sync enabled" : "Sync T5 now"}
              </div>
            </div>
          </div>

          {/* Middle col — cue mix */}
          <div className="ecol" style={{ flex:1 }}>
            <div className="sec-label">Cue mix — artist headphones</div>
            <div style={{ fontSize:9, color:C.muted, marginTop:-4 }}>Parameters sent live · artist can also adjust</div>

            {[
              { label:"REVERB", color:C.purple, keys:[["Size","rev"],["Mix","revMix"]] },
              { label:"DELAY",  color:C.teal,   keys:[["Time","del"],["Mix","delMix"]] },
              { label:"COMPRESSION", color:C.amber, keys:[["Threshold","comp"],["Ratio","ratio"]] },
            ].map(({ label, color, keys }) => (
              <div key={label}>
                <div className="group-label">
                  <div className="group-accent" style={{ background:color }} />
                  <div className="group-text" style={{ color }}>{label}</div>
                </div>
                <div className="knob-row" style={{ marginBottom:12 }}>
                  {keys.map(([lbl, k]) => <Knob key={k} label={lbl} value={cue[k]} color={color} onChange={v => updateCue(k,v)} />)}
                </div>
              </div>
            ))}

            <div>
              <div className="group-label">
                <div className="group-accent" style={{ background:C.blue }} />
                <div className="group-text" style={{ color:C.blue }}>4-BAND EQ</div>
              </div>
              <div className="eq-wrap">
                {[{f:"80Hz",v:55},{f:"400Hz",v:48},{f:"2kHz",v:70},{f:"8kHz",v:65}].map(b => (
                  <div key={b.f} className="eq-band">
                    <input className="eq-slider" type="range" min={0} max={100} defaultValue={b.v} />
                    <div className="eq-freq">{b.f}</div>
                  </div>
                ))}
              </div>
            </div>

            <div style={{ marginTop:"auto" }}>
              <div className="group-label">
                <div className="group-accent" style={{ background:C.green }} />
                <div className="group-text" style={{ color:C.green }}>CUE VOLUME</div>
              </div>
              <div style={{ display:"flex", justifyContent:"center" }}>
                <Knob label="Master" value={cue.vol} color={C.green} onChange={v => updateCue("vol",v)} />
              </div>
            </div>

            <div style={{ fontSize:9, color:C.muted, background:C.raised, borderRadius:4, padding:"6px 8px", border:`1px solid ${C.border}`, textAlign:"center" }}>
              Changes sync to artist · zero monitoring latency
            </div>
          </div>

          {/* Right col — backing track */}
          <div className="ecol" style={{ width:190, flexShrink:0 }}>
            <div className="sec-label">Backing track</div>
            <div style={{ fontSize:9, color:C.muted, marginBottom:4 }}>Select Reaper tracks</div>
            <div className="track-check">
              {[["drums","01 — Drums"],["bass","02 — Bass"],["keys","03 — Keys"]].map(([k,name]) => (
                <label key={k} className="track-item">
                  <input type="checkbox" checked={tracks[k]} onChange={e => setTracks(t=>({...t,[k]:e.target.checked}))} style={{ accentColor:C.blue }} />
                  <span style={{ color: tracks[k]?C.body:C.muted }}>{name}</span>
                </label>
              ))}
              <div style={{ fontSize:9, color:C.dim, fontStyle:"italic" }}>Loaded from Reaper</div>
            </div>
            <div style={{ height:8 }} />
            <div className="sec-label">Bounce quality</div>
            <div className="pill-grp" style={{ flexDirection:"column", gap:4 }}>
              {["MP3 128","MP3 256","WAV 24"].map(q => <div key={q} className={`pill ${btQ===q?"on":""}`} onClick={() => setBtQ(q)} style={{ textAlign:"center" }}>{q}</div>)}
            </div>
            <div className="ebtn ebtn-blue" onClick={() => setBtSent(false)} style={{ marginTop:6 }}>
              {btSent ? "↑ Send to artist" : "Sending..."}
            </div>
            <div className="swap-card">
              <div style={{ color:C.body, marginBottom:3 }}>session_BT_v3.mp3</div>
              <div style={{ color:C.muted, marginBottom:3 }}>Sent 14:32 · 8.2MB</div>
              <div style={{ color: btSent?C.green:C.amber }}>{btSent?"✓ Artist confirmed":"Transferring..."}</div>
            </div>
            <div style={{ marginTop:"auto" }}>
              <div className="sec-label">Last file swap</div>
              <div className="swap-card">
                <div style={{ color:C.body }}>T4 — 14:55:58</div>
                <div style={{ color:C.muted }}>0.4s · {syncFmt}</div>
                <div style={{ color:C.green, marginTop:2 }}>✓ Timeline updated</div>
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="eng-footer">
          <span className="back-btn" style={{ color:C.blue, cursor:"pointer", marginRight:"auto" }} onClick={onBack}>← Back</span>
          <span style={{ color:C.body, marginRight:12 }}>22ms</span>
          <span style={{ marginRight:4 }}>Format</span><span style={{ color:C.body, marginRight:12 }}>{syncFmt}</span>
          <span style={{ marginRight:4 }}>Stream</span><span style={{ color:C.body, marginRight:12 }}>{streamQ}</span>
          <span style={{ marginRight:4 }}>Takes</span><span style={{ color:C.body }}>T5</span>
        </div>
      </div>
      {showDetails && <DetailsPanel onClose={() => setShowDetails(false)} recording={recording} />}
    </div>
  );
}

// ── Root ──────────────────────────────────────────────────────────────────────
export default function App() {
  const [screen, setScreen] = useState("role");
  const [recording, setRecording] = useState(false);
  const [playhead, setPlayhead] = useState(0.56);
  const [cue, setCue] = useState({ rev:72, revMix:38, del:50, delMix:22, comp:55, ratio:40, vol:78 });

  const tabs = [
    { id:"role",     label:"Role select" },
    { id:"artist",   label:"Artist app"  },
    { id:"engineer", label:"Engineer app" },
  ];

  useEffect(() => {
    if (!recording) return;
    const id = setInterval(() => setPlayhead(p => { const n = p + 0.002; return n >= 1 ? 0 : n; }), 100);
    return () => clearInterval(id);
  }, [recording]);

  return (
    <>
      <style>{css}</style>
      <div className="root">
        <div className="nav">
          <div className="nav-logo">T<span>ake</span></div>
          {tabs.map(t => <div key={t.id} className={`nav-tab ${screen===t.id?"active":""}`} onClick={() => setScreen(t.id)}>{t.label}</div>)}
          <div
            className="sim-btn"
            onClick={() => setRecording(r=>!r)}
            style={{ background:recording?C.red+"22":C.raised, border:`1px solid ${recording?C.red+"55":C.border}`, color:recording?C.red:C.body }}
          >
            {recording ? "■ Stop" : "● Simulate recording"}
          </div>
        </div>
        <div className="app-shell">
          {screen==="role"     && <RoleSelect onArtist={() => setScreen("artist")} onEngineer={() => setScreen("engineer")} />}
          {screen==="artist"   && <ArtistApp recording={recording} playhead={playhead} cue={cue} setCue={setCue} onBack={() => setScreen("role")} />}
          {screen==="engineer" && <EngineerApp recording={recording} setRecording={setRecording} cue={cue} setCue={setCue} onBack={() => setScreen("role")} />}
        </div>
      </div>
    </>
  );
}
