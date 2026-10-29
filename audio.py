"""Synthesises the whole soundtrack from scratch (no samples, no third-party audio).

Usage: python3 audio.py out.wav
Timeline constants mirror build_scene.py.
"""
import math
import random
import struct
import sys
import wave

SR = 44100
T_END = 29.4
T_CLICK = 1.6
T_ROOMBA_GO = 3.1
T_BUMP = T_ROOMBA_GO + ((2.1 - 0.17) + 3.0) / 0.30   # roomba reaches the bed
T_EYES = T_BUMP + 1.3
T_REVEAL = 25.65                                      # light reaches the cat
T_CARD = 26.6

random.seed(5)
N = int(SR * T_END)
L = [0.0] * N
R = [0.0] * N


def add(t0, dur, fn, gain=1.0, pan=0.0):
    i0 = int(t0 * SR)
    n = int(dur * SR)
    gl = gain * (1 - max(0, pan))
    gr = gain * (1 + min(0, pan))
    for k in range(n):
        i = i0 + k
        if i >= N:
            break
        v = fn(k / SR, k / n)
        L[i] += v * gl
        R[i] += v * gr


def env(x, a=0.02, r=0.3):
    """attack/release on normalised position x"""
    if x < a:
        return x / a
    if x > 1 - r:
        return max(0.0, (1 - x) / r)
    return 1.0


# --- room tone: very quiet, brown-ish noise, a little darker once the light arrives
state = [0.0]


def room(t, x):
    state[0] = state[0] * 0.995 + (random.random() - 0.5) * 0.02
    return state[0] * 0.5


add(0, T_END, room, 0.7)

# --- switch: a dry click, then the bulb waking up (rising sweep + mains hum)


def click(t, x):
    return (random.random() - 0.5) * math.exp(-t * 900) + 0.6 * math.sin(2 * math.pi * 2600 * t) * math.exp(-t * 400)


add(T_CLICK - 0.02, 0.1, click, 0.9)
add(T_CLICK + 0.02, 0.9, lambda t, x: math.sin(2 * math.pi * (70 * t + 300 * t * t / 2 * 1.0)) * env(x, 0.05, 0.6) * 0.18, 1.0)
add(T_CLICK + 0.02, T_END - T_CLICK - 0.5,
    lambda t, x: (math.sin(2 * math.pi * 100 * t) * 0.5 + math.sin(2 * math.pi * 200 * t) * 0.25
                  + math.sin(2 * math.pi * 300 * t) * 0.12) * env(x, 0.6, 0.15) * (0.02 + 0.03 * x), 1.0)

# --- the light front: a soft airy shimmer that gets wider as the front grows (filtered noise, two bands)
lp = [0.0, 0.0]


def shimmer(t, x):
    n = random.random() - 0.5
    lp[0] += (n - lp[0]) * (0.03 + 0.05 * x)
    lp[1] += (lp[0] - lp[1]) * 0.15
    return (lp[0] - lp[1]) * 0.5


add(T_CLICK, T_REVEAL - T_CLICK + 1.2, shimmer, 0.9)

# --- Roomba: motor whirr + brush, with small speed wobble, panned left to right over the journey


def whirr(t, x):
    f = 95 + 4 * math.sin(2 * math.pi * 0.7 * t)
    saw = ((t * f) % 1.0) * 2 - 1
    brush = math.sin(2 * math.pi * 17 * t) > 0.2
    return (saw * 0.05 + (random.random() - 0.5) * 0.04 * (1.0 if brush else 0.4)) * env(x, 0.03, 0.02)


add(T_ROOMBA_GO, T_BUMP - T_ROOMBA_GO, whirr, 0.8)

# --- chase insert (build_scene.py T_CHASE_IN/OUT): camera rides just ahead of the Roomba, so its
# motor is up close for those seconds; a short airy whoosh marks each hard cut
T_CHASE_IN, T_CHASE_OUT = 9.5, 14.0
add(T_CHASE_IN, T_CHASE_OUT - T_CHASE_IN, whirr, 1.6)
wlp = [0.0]


def whoosh(t, x):
    wlp[0] += ((random.random() - 0.5) - wlp[0]) * (0.02 + 0.25 * x)
    return wlp[0] * (x ** 2) * (1 - x) * 6


add(T_CHASE_IN - 0.3, 0.32, whoosh, 0.9)
add(T_CHASE_OUT - 0.3, 0.32, whoosh, 0.7)

# --- bumps: thud + little complaint chirp


def thud(t, x):
    return (math.sin(2 * math.pi * (70 - 25 * t) * t) * math.exp(-t * 14) * 0.9
            + (random.random() - 0.5) * math.exp(-t * 60) * 0.5)


def chirp(f0, f1):
    def fn(t, x):
        f = f0 + (f1 - f0) * x
        return math.sin(2 * math.pi * f * t) * env(x, 0.05, 0.4) * 0.12
    return fn


add(T_BUMP, 0.5, thud, 1.0)
add(T_BUMP + 0.12, 0.12, chirp(900, 600), 1.0)
add(T_BUMP + 0.28, 0.12, chirp(600, 420), 1.0)
add(T_BUMP + 0.95, 0.5, thud, 0.8)
add(T_BUMP + 1.05, 0.15, chirp(500, 380), 1.0)

# --- the cat wakes: a small, suspicious "mrrp" (pitch glide with vibrato)


def mrrp(base, depth, dur_gain=1.0):
    def fn(t, x):
        f = base * (1 + depth * math.sin(math.pi * x)) + 12 * math.sin(2 * math.pi * 28 * t)
        ph = 2 * math.pi * f * t
        v = (math.sin(ph) + 0.5 * math.sin(2 * ph) + 0.3 * math.sin(3 * ph)) * 0.08 * dur_gain
        return v * env(x, 0.08, 0.35)
    return fn


add(T_EYES + 0.2, 0.28, mrrp(420, 0.35), 1.0, 0.25)
add(T_BUMP + 4.4, 0.7, mrrp(300, 0.25, 1.2), 1.0, 0.25)    # a grumble when the second bump settles

# --- the light arrives: swell + warm chord, then a tiny 'ding'


def chord(t, x):
    v = 0.0
    for f, g in ((220, 1.0), (277.2, 0.8), (329.6, 0.7), (440, 0.5)):
        v += math.sin(2 * math.pi * f * t) * g
    return v * 0.04 * env(x, 0.25, 0.5)


add(T_REVEAL - 0.4, 1.8, chord, 1.0)

# --- end card: clicks as the lines type in, then the Roomba "done" jingle
for tt in (T_CARD + 0.1, T_CARD + 0.5):
    add(tt, 0.08, click, 0.5)


def beep(f):
    def fn(t, x):
        return math.sin(2 * math.pi * f * t) * env(x, 0.05, 0.3) * 0.18
    return fn


for i, f in enumerate((660, 880, 1320)):
    add(T_CARD + 1.0 + 0.15 * i, 0.13, beep(f), 1.0)

# --- master: soft limiter + 0.4 s fade at the very end
peak = max(max(abs(v) for v in L), max(abs(v) for v in R), 1e-9)
scale = 0.85 / peak
fade_n = int(0.4 * SR)
out = wave.open(sys.argv[1], "wb")
out.setnchannels(2)
out.setsampwidth(2)
out.setframerate(SR)
buf = bytearray()
for i in range(N):
    g = scale * (min(1.0, (N - i) / fade_n))
    buf += struct.pack("<hh", int(max(-1, min(1, L[i] * g)) * 32767), int(max(-1, min(1, R[i] * g)) * 32767))
out.writeframes(bytes(buf))
out.close()
print("wrote", sys.argv[1], "peak before norm %.3f" % peak, "bump at %.2f" % T_BUMP)
