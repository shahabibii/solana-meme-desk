/** Desk motion preference — Windows often sets prefers-reduced-motion via OS "Animation effects". */

const KEY = "onyx_motion";
const EVT = "onyx-motion-change";

export type MotionPref = "auto" | "on" | "off";

export function getMotionPref(): MotionPref {
  try {
    const v = localStorage.getItem(KEY);
    if (v === "on" || v === "off") return v;
  } catch {
    /* ignore */
  }
  return "auto";
}

export function osPrefersReducedMotion(): boolean {
  if (typeof window === "undefined") return false;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/** True when sphere / logo / atmosphere should animate. */
export function motionEnabled(): boolean {
  const pref = getMotionPref();
  if (pref === "on") return true;
  if (pref === "off") return false;
  return !osPrefersReducedMotion();
}

export function setMotionPref(pref: MotionPref): void {
  try {
    if (pref === "auto") localStorage.removeItem(KEY);
    else localStorage.setItem(KEY, pref);
  } catch {
    /* ignore */
  }
  applyMotionClass();
  window.dispatchEvent(new Event(EVT));
}

export function applyMotionClass(): void {
  document.documentElement.classList.toggle("onyx-motion", motionEnabled());
  document.documentElement.classList.toggle("onyx-still", !motionEnabled());
}

export function subscribeMotion(cb: () => void): () => void {
  const onChange = () => cb();
  window.addEventListener(EVT, onChange);
  const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
  mq.addEventListener?.("change", onChange);
  return () => {
    window.removeEventListener(EVT, onChange);
    mq.removeEventListener?.("change", onChange);
  };
}
