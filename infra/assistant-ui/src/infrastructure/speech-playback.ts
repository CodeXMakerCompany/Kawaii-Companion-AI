/**
 * Isolated module: play a voice sample and drive Live2D mouth in sync with
 * the actual sound (volume-based lip-sync) for realistic speech simulation.
 *
 * Events (decoupled from adapter):
 * - live2d-mouth-level: { detail: { level: 0-1 } } every frame while playing
 * - live2d-stop-talking: when playback ends
 */

export const MOUTH_LEVEL_EVENT = "live2d-mouth-level";
export const STOP_TALKING_EVENT = "live2d-stop-talking";

/** Put your sample in public/ and reference as /pneuma_voice_sample.wav (or .mp3). */
const DEFAULT_VOICE_SAMPLE = "pneuma_voice_sample.wav";

const FFT_SIZE = 256;
const SMOOTHING = 0.8;
const LEVEL_SCALE = 9;

function dispatchMouthLevel(level: number): void {
  window.dispatchEvent(new CustomEvent(MOUTH_LEVEL_EVENT, { detail: { level } }));
}

function dispatchStopTalking(): void {
  window.dispatchEvent(new CustomEvent(STOP_TALKING_EVENT));
}

/** RMS from time-domain samples (0–255 from getByteTimeDomainData). */
function rmsFromTimeDomain(data: Uint8Array): number {
  let sum = 0;
  for (let i = 0; i < data.length; i++) {
    const s = (data[i] - 128) / 128;
    sum += s * s;
  }
  return Math.sqrt(sum / data.length);
}

/**
 * Play the voice sample and drive mouth level from real-time volume
 * so the model opens/closes with the speech. Uses Web Audio API for analysis.
 */
export function playLlmResponseVoice(audioUrl: string = DEFAULT_VOICE_SAMPLE): Promise<void> {
  return new Promise((resolve, reject) => {
    const audio = new Audio(audioUrl);
    const ctx = new (window.AudioContext || (window as any).webkitAudioContext)();
    const source = ctx.createMediaElementSource(audio);
    const analyser = ctx.createAnalyser();
    analyser.fftSize = FFT_SIZE;
    analyser.smoothingTimeConstant = SMOOTHING;
    source.connect(analyser);
    analyser.connect(ctx.destination);

    const timeData = new Uint8Array(analyser.fftSize);
    let rafId = 0;

    const tick = () => {
      if (audio.ended || audio.paused) {
        return;
      }
      analyser.getByteTimeDomainData(timeData);
      const rms = rmsFromTimeDomain(timeData);
      const level = Math.min(1, rms * LEVEL_SCALE);
      dispatchMouthLevel(level);
      rafId = requestAnimationFrame(tick);
    };

    audio.onended = () => {
      cancelAnimationFrame(rafId);
      dispatchStopTalking();
      resolve();
    };

    audio.onerror = () => {
      cancelAnimationFrame(rafId);
      dispatchStopTalking();
      reject(new Error(`Failed to load voice sample: ${audioUrl}`));
    };

    audio.onplay = () => {
      if (ctx.state === "suspended") void ctx.resume();
      rafId = requestAnimationFrame(tick);
    };

    audio.oncanplaythrough = () => {
      audio.play().catch(reject);
    };

    audio.load();
  });
}
