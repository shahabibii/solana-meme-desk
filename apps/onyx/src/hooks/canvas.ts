import { useEffect, useRef, useState } from "react";
import { motionEnabled, subscribeMotion } from "../motion";

type Star = { x: number; y: number; r: number; s: number; a: number };

function useMotionFlag(): boolean {
  const [on, setOn] = useState(() => motionEnabled());
  useEffect(() => subscribeMotion(() => setOn(motionEnabled())), []);
  return on;
}

function usePageVisible(): boolean {
  const [vis, setVis] = useState(() => typeof document !== "undefined" && !document.hidden);
  useEffect(() => {
    const onVis = () => setVis(!document.hidden);
    document.addEventListener("visibilitychange", onVis);
    return () => document.removeEventListener("visibilitychange", onVis);
  }, []);
  return vis;
}

export function useStarfield(canvasRef: React.RefObject<HTMLCanvasElement | null>) {
  const motion = useMotionFlag();
  const visible = usePageVisible();
  const motionRef = useRef(motion);
  motionRef.current = motion;

  useEffect(() => {
    const sc = canvasRef.current;
    if (!sc) return;
    const sx = sc.getContext("2d");
    if (!sx) return;
    let stars: Star[] = [];
    let raf = 0;

    function init() {
      sc!.width = window.innerWidth;
      sc!.height = window.innerHeight;
      stars = [];
      for (let i = 0; i < 80; i++) {
        stars.push({
          x: Math.random() * sc!.width,
          y: Math.random() * sc!.height,
          r: Math.random() * 1.1 + 0.2,
          s: Math.random() * 0.12 + 0.02,
          a: Math.random() * 6,
        });
      }
      draw(false);
    }

    function draw(animate: boolean) {
      sx!.clearRect(0, 0, sc!.width, sc!.height);
      for (const st of stars) {
        if (animate) {
          st.y -= st.s;
          if (st.y < 0) st.y = sc!.height;
          st.a += 0.012;
        }
        sx!.globalAlpha = 0.22 + Math.sin(st.a) * 0.18;
        sx!.fillStyle = "#B09AD0";
        sx!.beginPath();
        sx!.arc(st.x, st.y, st.r, 0, 7);
        sx!.fill();
      }
      sx!.globalAlpha = 1;
    }

    init();
    const onResize = () => init();
    window.addEventListener("resize", onResize);

    function loop() {
      if (!visible) {
        raf = requestAnimationFrame(loop);
        return;
      }
      draw(motionRef.current);
      raf = requestAnimationFrame(loop);
    }
    raf = requestAnimationFrame(loop);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", onResize);
    };
  }, [canvasRef, visible]);
}

const N = 240;
const GA = Math.PI * (3 - Math.sqrt(5));
const PTS: [number, number, number][] = [];
for (let i = 0; i < N; i++) {
  const y = 1 - (i / (N - 1)) * 2;
  const r = Math.sqrt(1 - y * y);
  const t = GA * i;
  PTS.push([Math.cos(t) * r, y, Math.sin(t) * r]);
}

export function useSphere(
  canvasRef: React.RefObject<HTMLCanvasElement | null>,
  active: boolean
) {
  const activeRef = useRef(active);
  activeRef.current = active;
  const motion = useMotionFlag();
  const visible = usePageVisible();
  const motionRef = useRef(motion);
  motionRef.current = motion;

  useEffect(() => {
    const sp = canvasRef.current;
    if (!sp) return;
    const spc = sp.getContext("2d");
    if (!spc) return;
    let ang = 0;
    let raf = 0;

    function render() {
      const W = (sp!.width = Math.max(1, sp!.offsetWidth) * 2);
      const H = (sp!.height = Math.max(1, sp!.offsetHeight) * 2);
      if (W < 4 || H < 4) return;
      const cx = W / 2;
      const cy = H / 2;
      const R = Math.min(W, H) * 0.42;
      const F = 3.2;
      spc!.clearRect(0, 0, W, H);
      if (motionRef.current) {
        ang += activeRef.current ? 0.007 : 0.0028;
      }
      const tilt = 0.35;
      for (const [px, py, pz] of PTS) {
        const x = px * Math.cos(ang) - pz * Math.sin(ang);
        const z = px * Math.sin(ang) + pz * Math.cos(ang);
        const y = py;
        const y2 = y * Math.cos(tilt) - z * Math.sin(tilt);
        const z2 = y * Math.sin(tilt) + z * Math.cos(tilt);
        const s = F / (F + z2);
        const X = cx + x * R * s;
        const Y = cy + y2 * R * s;
        const front = (1 - z2) / 2;
        spc!.globalAlpha = 0.12 + front * 0.5;
        spc!.fillStyle = front > 0.72 ? "#7BE8FF" : "#B09AD0";
        spc!.beginPath();
        spc!.arc(X, Y, (0.9 + front * 1.6) * s, 0, 7);
        spc!.fill();
      }
      spc!.globalAlpha = 0.16;
      spc!.strokeStyle = "#B09AD0";
      spc!.lineWidth = 1;
      for (let k = 0; k < 3; k++) {
        spc!.beginPath();
        spc!.ellipse(
          cx,
          cy,
          R * 0.98,
          R * (0.3 + k * 0.24),
          ang * (k % 2 ? 1 : -1) * 0.6 + k,
          0,
          7
        );
        spc!.stroke();
      }
      spc!.globalAlpha = 1;
    }

    function loop() {
      if (visible) render();
      raf = requestAnimationFrame(loop);
    }
    render();
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [canvasRef, visible]);
}

export function useWaveform(
  canvasRef: React.RefObject<HTMLCanvasElement | null>,
  active: boolean,
  color: string,
  idleFrac = 0.14
) {
  const activeRef = useRef(active);
  activeRef.current = active;
  const visible = usePageVisible();

  useEffect(() => {
    const cv = canvasRef.current;
    if (!cv) return;
    const c = cv.getContext("2d");
    if (!c) return;
    let raf = 0;

    function loop() {
      if (!visible) {
        raf = requestAnimationFrame(loop);
        return;
      }
      const W = (cv!.width = Math.max(1, cv!.offsetWidth) * 2);
      const H = (cv!.height = Math.max(1, cv!.offsetHeight) * 2);
      c!.clearRect(0, 0, W, H);
      const act = activeRef.current;
      const n = Math.floor(W / 12);
      for (let i = 0; i < n; i++) {
        const h = act
          ? (Math.sin(Date.now() / 85 + i * 0.8) * 0.5 + 0.5) * H * 0.85 + 2
          : H * idleFrac;
        c!.fillStyle = act ? color : "rgba(122,107,160,.5)";
        c!.fillRect(i * 12 + 2, (H - h) / 2, 7, h);
      }
      raf = requestAnimationFrame(loop);
    }
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [canvasRef, color, idleFrac, visible]);
}

export function useAgentWave(
  canvasRef: React.RefObject<HTMLCanvasElement | null>,
  running: boolean,
  seed: number
) {
  const runRef = useRef(running);
  runRef.current = running;
  const visible = usePageVisible();

  useEffect(() => {
    const cv = canvasRef.current;
    if (!cv) return;
    const c = cv.getContext("2d");
    if (!c) return;
    let raf = 0;

    function loop() {
      if (!visible) {
        raf = requestAnimationFrame(loop);
        return;
      }
      const W = (cv!.width = Math.max(1, cv!.offsetWidth) * 2);
      const H = (cv!.height = Math.max(1, cv!.offsetHeight) * 2);
      c!.clearRect(0, 0, W, H);
      const run = runRef.current;
      const bars = 22;
      for (let b = 0; b < bars; b++) {
        const h = run
          ? (Math.sin(Date.now() / 80 + b * 0.9 + seed) * 0.5 + 0.5) * H * 0.85 + 2
          : H * 0.12;
        c!.fillStyle = run ? "#7BE8FF" : "rgba(122,107,160,.5)";
        c!.fillRect(b * (W / bars) + 1, (H - h) / 2, W / bars - 3, h);
      }
      raf = requestAnimationFrame(loop);
    }
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [canvasRef, seed, visible]);
}

export function useEquityChart(
  canvasRef: React.RefObject<HTMLCanvasElement | null>,
  values: number[]
) {
  useEffect(() => {
    const cv = canvasRef.current;
    if (!cv) return;
    const c = cv.getContext("2d");
    if (!c) return;

    function draw() {
      const eq = values.length >= 2 ? values : [1, 1];
      const W = (cv!.width = Math.max(1, cv!.offsetWidth) * 2);
      const H = (cv!.height = Math.max(1, cv!.offsetHeight) * 2);
      const mn = Math.min(...eq);
      const mx = Math.max(...eq);
      const rg = mx - mn || 1;
      c!.clearRect(0, 0, W, H);
      c!.strokeStyle = "rgba(176,154,208,.07)";
      c!.lineWidth = 1;
      for (let g = 1; g < 4; g++) {
        c!.beginPath();
        c!.moveTo(0, (H * g) / 4);
        c!.lineTo(W, (H * g) / 4);
        c!.stroke();
      }
      const pt = (i: number): [number, number] => [
        (i / (eq.length - 1)) * W,
        H - ((eq[i] - mn) / rg) * (H * 0.78) - H * 0.11,
      ];
      for (let i = 0; i < eq.length; i += 6) {
        const [x, y] = pt(i);
        c!.fillStyle = "rgba(224,204,245,.5)";
        c!.beginPath();
        c!.arc(x, y, 2.4, 0, 7);
        c!.fill();
      }
      c!.beginPath();
      eq.forEach((_, i) => {
        const [x, y] = pt(i);
        if (i) c!.lineTo(x, y);
        else c!.moveTo(x, y);
      });
      c!.strokeStyle = "#B09AD0";
      c!.lineWidth = 2.6;
      c!.shadowColor = "#B09AD0";
      c!.shadowBlur = 12;
      c!.stroke();
      c!.lineTo(W, H);
      c!.lineTo(0, H);
      c!.closePath();
      const g2 = c!.createLinearGradient(0, 0, 0, H);
      g2.addColorStop(0, "rgba(176,154,208,.2)");
      g2.addColorStop(1, "transparent");
      c!.fillStyle = g2;
      c!.shadowBlur = 0;
      c!.fill();
      const [lx, ly] = pt(eq.length - 1);
      c!.beginPath();
      c!.arc(lx, ly, 5, 0, 7);
      c!.fillStyle = "#7BE8FF";
      c!.shadowColor = "#7BE8FF";
      c!.shadowBlur = 16;
      c!.fill();
      c!.shadowBlur = 0;
    }

    draw();
    const onResize = () => draw();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [canvasRef, values]);
}
