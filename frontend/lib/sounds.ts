// enable_sounds — tiny completion chime. WebAudio, no audio files on the USB.
let ctx: AudioContext | null = null;

export function playChime(): void {
  try {
    const AC =
      window.AudioContext ||
      (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!AC) return;
    ctx = ctx ?? new AC();
    if (ctx.state === 'suspended') void ctx.resume();
    const t = ctx.currentTime;
    [660, 880].forEach((freq, i) => {
      const osc = ctx!.createOscillator();
      const gain = ctx!.createGain();
      osc.type = 'sine';
      osc.frequency.value = freq;
      gain.gain.setValueAtTime(0.08, t + i * 0.12);
      gain.gain.exponentialRampToValueAtTime(0.0001, t + i * 0.12 + 0.25);
      osc.connect(gain).connect(ctx!.destination);
      osc.start(t + i * 0.12);
      osc.stop(t + i * 0.12 + 0.25);
    });
  } catch {
    // sounds must never break chat
  }
}
