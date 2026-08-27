import { fetchVoiceConfig, synthesizeSpeech, type VoiceConfig } from "./api";

/** Browser speech helpers — Maisie (ElevenLabs) with browser fallback. */

export type VoiceSupport = {
  listen: boolean;
  speak: boolean;
};

type RecognitionLike = {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start: () => void;
  stop: () => void;
  abort: () => void;
  onresult: ((ev: Event) => void) | null;
  onerror: ((ev: Event) => void) | null;
  onend: (() => void) | null;
};

let voiceConfig: VoiceConfig | null = null;
let currentAudio: HTMLAudioElement | null = null;
let speakGeneration = 0;

function getRecognitionCtor(): (new () => RecognitionLike) | null {
  const w = window as Window & {
    SpeechRecognition?: new () => RecognitionLike;
    webkitSpeechRecognition?: new () => RecognitionLike;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

export function voiceSupport(): VoiceSupport {
  return {
    listen: Boolean(getRecognitionCtor()),
    speak: typeof window !== "undefined",
  };
}

export async function loadVoiceConfig(): Promise<VoiceConfig> {
  if (voiceConfig) return voiceConfig;
  voiceConfig = await fetchVoiceConfig();
  return voiceConfig;
}

export function getVoiceLabel(): string {
  return voiceConfig?.label ?? "Maisie — friendly casual neighbor";
}

function stopPlayback(): void {
  speakGeneration += 1;
  if (currentAudio) {
    currentAudio.pause();
    currentAudio.src = "";
    currentAudio = null;
  }
  if ("speechSynthesis" in window) {
    window.speechSynthesis.cancel();
  }
}

function stripMarkdownForSpeech(text: string): string {
  return text
    .replace(/\*\*?/g, "")
    .replace(/`+/g, "")
    .replace(/#{1,6}\s*/g, "")
    .replace(/\n+/g, ". ")
    .trim();
}

function pickBrowserVoice(voices: SpeechSynthesisVoice[]): SpeechSynthesisVoice | null {
  const rank = (v: SpeechSynthesisVoice): number => {
    const n = `${v.name} ${v.lang}`;
    if (/maisie/i.test(n)) return 100;
    if (/Google UK English Female/i.test(n)) return 95;
    if (/Microsoft (Sonia|Hazel|Susan)/i.test(n)) return 90;
    if (/Karen|Moira|Tessa|Fiona|Serena/i.test(n)) return 85;
    if (/Samantha|Victoria|Kathy|Allison|Ava|Zoe/i.test(n) && /en/i.test(v.lang)) return 80;
    if (/female|woman/i.test(n) && /^en(-|_|$)/i.test(v.lang)) return 70;
    if (/^en-GB|^en-AU|^en-IE/i.test(v.lang) && !/male|daniel|david|arthur|george/i.test(n))
      return 60;
    if (/^en/i.test(v.lang) && !/male|daniel|david|arthur|alex|fred|jorge/i.test(n)) return 40;
    return 0;
  };
  const scored = voices
    .map((v) => ({ v, s: rank(v) }))
    .filter((x) => x.s > 0)
    .sort((a, b) => b.s - a.s);
  return scored[0]?.v ?? null;
}

function speakBrowser(clean: string, onEnd?: () => void): void {
  if (!("speechSynthesis" in window)) {
    onEnd?.();
    return;
  }
  const speakNow = () => {
    const u = new SpeechSynthesisUtterance(clean);
    u.rate = 0.94;
    u.pitch = 1.08;
    u.lang = "en-GB";
    const preferred = pickBrowserVoice(window.speechSynthesis.getVoices());
    if (preferred) {
      u.voice = preferred;
      u.lang = preferred.lang || "en-GB";
    }
    u.onend = () => onEnd?.();
    u.onerror = () => onEnd?.();
    window.speechSynthesis.speak(u);
  };

  const voices = window.speechSynthesis.getVoices();
  if (!voices.length) {
    window.speechSynthesis.onvoiceschanged = () => {
      window.speechSynthesis.onvoiceschanged = null;
      speakNow();
    };
    window.setTimeout(speakNow, 250);
    return;
  }
  speakNow();
}

async function playAudioBlob(blob: Blob, generation: number): Promise<void> {
  const url = URL.createObjectURL(blob);
  const audio = new Audio(url);
  currentAudio = audio;
  await new Promise<void>((resolve, reject) => {
    audio.onended = () => resolve();
    audio.onerror = () => reject(new Error("audio playback failed"));
    void audio.play().catch(reject);
  }).finally(() => {
    URL.revokeObjectURL(url);
    if (speakGeneration === generation && currentAudio === audio) {
      currentAudio = null;
    }
  });
}

export function speakText(
  text: string,
  enabled: boolean,
  opts?: { onStart?: () => void; onEnd?: () => void }
): void {
  void speakTextAsync(text, enabled, opts);
}

async function speakTextAsync(
  text: string,
  enabled: boolean,
  opts?: { onStart?: () => void; onEnd?: () => void }
): Promise<void> {
  if (!enabled || !text.trim()) return;

  const clean = stripMarkdownForSpeech(text).slice(0, 520);
  if (!clean) return;

  stopPlayback();
  const generation = speakGeneration;
  opts?.onStart?.();

  const finish = () => {
    if (generation === speakGeneration) opts?.onEnd?.();
  };

  const config = voiceConfig ?? (await loadVoiceConfig());
  if (config.active) {
    try {
      const blob = await synthesizeSpeech(clean);
      if (generation !== speakGeneration) return;
      await playAudioBlob(blob, generation);
      finish();
      return;
    } catch {
      if (generation !== speakGeneration) return;
    }
  }

  if (generation !== speakGeneration) return;
  speakBrowser(clean, finish);
}

export async function playVoicePreview(): Promise<void> {
  const config = voiceConfig ?? (await loadVoiceConfig());
  stopPlayback();
  const generation = speakGeneration;
  const audio = new Audio(config.preview_url);
  currentAudio = audio;
  await audio.play().catch(() => undefined);
  audio.onended = () => {
    if (speakGeneration === generation) currentAudio = null;
  };
}

export function startListening(opts: {
  onInterim?: (text: string) => void;
  onFinal: (text: string) => void;
  onError: (message: string) => void;
  onEnd: () => void;
}): { stop: () => void } | null {
  const Ctor = getRecognitionCtor();
  if (!Ctor) {
    opts.onError("Voice not supported in this browser. Use Chrome or Edge.");
    return null;
  }
  const rec = new Ctor();
  rec.continuous = false;
  rec.interimResults = true;
  rec.lang = "en-US";

  rec.onresult = (ev: Event) => {
    const e = ev as unknown as {
      resultIndex: number;
      results: {
        length: number;
        [i: number]: { isFinal: boolean; 0: { transcript: string } };
      };
    };
    let interim = "";
    let finalText = "";
    for (let i = e.resultIndex; i < e.results.length; i++) {
      const t = e.results[i][0].transcript;
      if (e.results[i].isFinal) finalText += t;
      else interim += t;
    }
    if (interim) opts.onInterim?.(interim);
    if (finalText.trim()) opts.onFinal(finalText.trim());
  };

  rec.onerror = (ev: Event) => {
    const err = ev as unknown as { error?: string };
    if (err.error === "aborted" || err.error === "no-speech") {
      opts.onEnd();
      return;
    }
    opts.onError(err.error ?? "voice error");
  };

  rec.onend = () => opts.onEnd();

  try {
    rec.start();
  } catch {
    opts.onError("Could not start microphone.");
    return null;
  }

  return {
    stop: () => {
      try {
        rec.stop();
      } catch {
        /* ignore */
      }
    },
  };
}
