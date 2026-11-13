#!/usr/bin/env python3
"""BGM を numpy だけで合成する（BPM120 / 20小節 = 40秒）。

    python3 music.py out/music.wav

場面転換の小節は video.html の SC と同じ: [0, 2, 6, 10, 14, 17, 20]
"""
import sys
import wave
import numpy as np

SR = 44100
BPM = 120
BEAT = 60 / BPM
BAR = BEAT * 4
BARS = 20
SCENES = [0, 2, 6, 10, 14, 17]
rs = np.random.RandomState(7)
L = int(SR * BARS * BAR)
mix = np.zeros((L, 2))
duck = np.ones(L)  # キックに合わせたサイドチェイン


def add(sig, t, gain=1.0, pan=0.0):
    i = int(t * SR)
    if i >= L:
        return
    sig = sig[: L - i]
    mix[i:i + len(sig), 0] += sig * gain * (1 - max(0, pan))
    mix[i:i + len(sig), 1] += sig * gain * (1 + min(0, pan))


def tt(d):
    return np.arange(int(d * SR)) / SR


def kick():
    t = tt(0.32)
    f = 45 + 110 * np.exp(-t * 28)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 9) + 0.25 * rs.randn(len(t)) * np.exp(-t * 300)


def hat(d=0.05):
    t = tt(d)
    n = np.diff(rs.randn(len(t) + 2), 2)
    return n * np.exp(-t * (3.2 / d)) * 0.3


def clap():
    t = tt(0.22)
    n = np.convolve(np.diff(rs.randn(len(t) + 1)), np.ones(5) / 5, "same")
    env = sum(np.exp(-np.clip(t - d, 0, None) * 38) * (t >= d) for d in (0, 0.011, 0.023))
    return n * env * 0.5


def tone(f, d, harm, decay, detune=0.0):
    t = tt(d)
    out = np.zeros(len(t))
    for h, a in enumerate(harm, 1):
        out += a * np.sin(2 * np.pi * f * h * t)
        if detune:
            out += a * np.sin(2 * np.pi * f * h * (1 + detune) * t)
    env = np.exp(-t * decay) * np.clip(t / 0.004, 0, 1) * np.clip((d - t) / 0.01, 0, 1)
    return out * env


def impact():
    t = tt(2.2)
    boom = np.sin(2 * np.pi * np.cumsum(38 + 60 * np.exp(-t * 6)) / SR) * np.exp(-t * 2.2)
    n = np.convolve(rs.randn(len(t)), np.ones(24) / 24, "same") * np.exp(-t * 3.5) * 2.2
    return boom + n


def riser(d):
    t = tt(d)
    x = t / d
    n = np.diff(rs.randn(len(t) + 1)) * x ** 2 * 0.22
    sw = np.sin(2 * np.pi * np.cumsum(200 + 1800 * x ** 2) / SR) * x ** 2 * 0.12
    return n + sw


def midi(n):
    return 440 * 2 ** ((n - 69) / 12)


# Am - F - C - G
CHORDS = [(45, [57, 60, 64, 69]), (41, [57, 60, 65, 69]), (48, [55, 60, 64, 67]), (43, [55, 59, 62, 67])]
SAW = [1 / h for h in range(1, 7)]
SOFT = [1, 0.35, 0.15, 0.06]

K, H8, CL = kick(), hat(), clap()
for bar in range(BARS):
    t0 = bar * BAR
    root, notes = CHORDS[bar % 4]
    intro = bar < 2
    brk = bar == 16           # ブレイク（キック無し、ライザー）
    outro = bar == 19         # 最後の一発と余韻
    full = bar >= 10 and not brk and not outro

    # パッド
    pg = 0.10 if (intro or brk or outro) else 0.045
    for n in notes[:3]:
        add(tone(midi(n), BAR * (2.0 if outro else 1.0), SOFT, 0.25, 0.004), t0, pg, 0.0)
    if outro:
        continue

    for b in range(4):
        tb = t0 + b * BEAT
        if not intro and not brk:
            add(K, tb, 0.95)
            i = int(tb * SR)
            n = int(0.24 * SR)
            duck[i:i + n] = np.minimum(duck[i:i + n], 0.35 + 0.65 * np.linspace(0, 1, n) ** 1.5)
            add(H8, tb + BEAT / 2, 0.55, 0.2)
            if full:
                add(hat(0.03), tb + BEAT / 4, 0.3, -0.3)
                add(hat(0.03), tb + BEAT * 3 / 4, 0.3, -0.3)
        if bar >= 6 and not brk and b in (1, 3):
            add(CL, tb, 0.7)
        if brk:  # スネアロール風に細かく
            div = 2 if b < 2 else 4
            for k in range(div):
                add(CL, tb + k * BEAT / div, 0.25 + 0.12 * b)

    # ベース（8分）
    if not intro and not brk:
        for e in range(8):
            f = midi(root - 12 + (12 if e % 4 == 3 else 0))
            add(tone(f, BEAT / 2 * 0.9, SAW[:4], 7), t0 + e * BEAT / 2, 0.30)

    # アルペジオ（16分）
    if bar >= 6 or intro or brk:
        g = 0.05 if intro else (0.11 if full else 0.085)
        for s in range(16):
            if intro and s % 2:
                continue
            n = notes[(s * 3) % 4] + (12 if full or s % 8 >= 4 else 0)
            sig = tone(midi(n), 0.22, [1, 0.5, 0.33, 0.2], 14)
            add(sig, t0 + s * BEAT / 4, g, 0.5 if s % 2 else -0.5)
            add(sig, t0 + s * BEAT / 4 + BEAT * 0.75, g * 0.35, -0.5 if s % 2 else 0.5)

# サイドチェイン → インパクト・ライザーは後乗せ
mix *= duck[:, None]
for b in SCENES[1:] + [19]:
    add(impact(), b * BAR, 0.8)
for b, d in ((2, BAR), (6, BAR / 2), (10, BAR / 2), (14, BAR / 2), (17, BAR)):
    add(riser(d), b * BAR - d, 1.0)

fade = np.clip((L - np.arange(L)) / (SR * 0.7), 0, 1) * np.clip(np.arange(L) / (SR * 0.02), 0, 1)
mix *= fade[:, None]
mix = np.tanh(mix * 1.3)
mix *= 0.89 / np.abs(mix).max()

out = sys.argv[1] if len(sys.argv) > 1 else "music.wav"
with wave.open(out, "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes((mix * 32767).astype("<i2").tobytes())
rms = np.sqrt((mix ** 2).mean())
print(f"{out}: {L / SR:.1f}s peak={np.abs(mix).max():.2f} rms={rms:.3f}")
