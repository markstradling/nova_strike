"""Procedurally synthesised sound effects: every sound is generated at startup, so no audio files are needed."""

from __future__ import annotations

import math
import random
from array import array
from collections.abc import Sequence
from typing import TYPE_CHECKING

import pygame

if TYPE_CHECKING:
    from .config import Samples


_SR = 22050  # sample rate, replaced by the mixer's actual rate in build_sounds


_noise_rng = random.Random(1234)  # separate RNG so sound generation never disturbs gameplay randomness


def _wave(kind: str, phase: float) -> float:
    x = phase % 1.0
    if kind == "sine":
        return math.sin(phase * math.tau)
    if kind == "square":
        return 1.0 if x < 0.5 else -1.0
    if kind == "saw":
        return 2 * x - 1
    return 4 * abs(x - 0.5) - 1  # triangle


def tone(  # noqa: PLR0917 - synth parameters read naturally positionally
    duration: float,
    f0: float,
    f1: float | None = None,
    kind: str = "square",
    decay: float = 2.0,
    attack: float = 0.004,
    vibrato: float = 0.0,
    vib_rate: float = 0.0,
) -> Samples:
    """Oscillator sweeping from f0 to f1 Hz with a decaying envelope."""
    f1 = f0 if f1 is None else f1
    n = int(_SR * duration)
    out, phase = [], 0.0
    attack_n = attack * _SR + 1
    for i in range(n):
        p = i / n
        f = f0 + (f1 - f0) * p
        if vibrato:
            f *= 1 + vibrato * math.sin(math.tau * vib_rate * i / _SR)
        phase += f / _SR
        out.append(_wave(kind, phase) * min(1.0, i / attack_n) * (1 - p) ** decay)
    return out


def noise(duration: float, decay: float = 2.0, smooth: float = 0.0, smooth_end: float | None = None) -> Samples:
    """White noise through a sweepable one-pole low-pass filter (higher smooth = darker)."""
    smooth_end = smooth if smooth_end is None else smooth_end
    n = int(_SR * duration)
    out, y = [], 0.0
    for i in range(n):
        p = i / n
        a = smooth + (smooth_end - smooth) * p
        y = a * y + (1 - a) * _noise_rng.uniform(-1, 1)
        out.append(y * (1 - p) ** decay)
    return _normalize(out, 1.0)


def silence(duration: float) -> Samples:
    return [0.0] * int(_SR * duration)


def mix(*parts: tuple[Samples, float]) -> Samples:
    """Mix (samples, gain) pairs, padding the shorter ones."""
    n = max(len(s) for s, _ in parts)
    out = [0.0] * n
    for samples, gain in parts:
        for i, v in enumerate(samples):
            out[i] += v * gain
    return out


def concat(*parts: Samples) -> Samples:
    out = []
    for part in parts:
        out.extend(part)
    return out


def _normalize(samples: Samples, peak: float) -> Samples:
    top = max((abs(v) for v in samples), default=0) or 1.0
    return [v * peak / top for v in samples]


def notes(
    freqs: Sequence[float], step: float, kind: str = "square", decay: float = 0.6, last: float | None = None
) -> Samples:
    """Quick arpeggio: each frequency for `step` seconds, the last held for `last`."""
    parts = [tone(step, f, kind=kind, decay=decay) for f in freqs[:-1]]
    parts.append(tone(last or step * 2, freqs[-1], kind=kind, decay=1.2))
    return concat(*parts)


def build_sound_samples() -> dict[str, tuple[Samples, float]]:
    return {
        "shoot": (tone(0.09, 1500, 450, "square", decay=1.6), 0.13),
        "spread": (mix((tone(0.12, 950, 280, "saw", decay=1.4), 1.0), (noise(0.06, smooth=0.3), 0.4)), 0.15),
        "missile": (
            mix(
                (noise(0.4, decay=1.2, smooth=0.5, smooth_end=0.95), 1.0), (tone(0.4, 180, 520, "saw", decay=1.5), 0.25)
            ),
            0.22,
        ),
        "laser": (
            mix(
                (tone(0.5, 110, kind="saw", decay=0, vibrato=0.04, vib_rate=8), 1.0),
                (tone(0.5, 220, kind="square", decay=0), 0.25),
                (tone(0.5, 880, kind="sine", decay=0, vibrato=0.02, vib_rate=16), 0.2),
            ),
            0.13,
        ),
        "enemy_shot": (tone(0.13, 640, 230, "tri", decay=1.3), 0.14),
        "hit": (mix((noise(0.05, decay=3, smooth=0.2), 1.0), (tone(0.05, 320, 160, "square", decay=2), 0.4)), 0.16),
        "explosion": (
            mix(
                (noise(0.6, decay=2.2, smooth=0.8, smooth_end=0.97), 1.0), (tone(0.4, 130, 40, "sine", decay=1.5), 0.7)
            ),
            0.45,
        ),
        "big_explosion": (
            mix(
                (noise(1.3, decay=1.7, smooth=0.88, smooth_end=0.985), 1.0), (tone(1.0, 95, 28, "sine", decay=1.2), 0.9)
            ),
            0.65,
        ),
        "rock_break": (
            mix((noise(0.35, decay=2.5, smooth=0.75, smooth_end=0.9), 1.0), (tone(0.2, 90, 50, "tri", decay=2), 0.6)),
            0.35,
        ),
        "hurt": (mix((tone(0.25, 190, 55, "square", decay=1.5), 1.0), (noise(0.15, smooth=0.7), 0.6)), 0.32),
        "deflect": (tone(0.06, 2000, 2600, "sine", decay=2), 0.1),
        "pickup": (notes([660, 880, 1320], 0.05, kind="square"), 0.2),
        "heal": (notes([523, 659, 784], 0.06, kind="tri"), 0.3),
        "invincible": (notes([523, 659, 784, 1047, 1319, 1568], 0.05, kind="square", last=0.25), 0.22),
        "extra_life": (notes([784, 988, 1175, 1568, 1175, 1568], 0.08, kind="tri", last=0.35), 0.35),
        "level_up": (
            mix((tone(0.55, 300, 1200, "tri", decay=0.8), 1.0), (tone(0.55, 450, 1800, "sine", decay=0.8), 0.5)),
            0.3,
        ),
        "empty": (concat(tone(0.08, 440, kind="square", decay=0.5), tone(0.14, 220, kind="square", decay=1)), 0.15),
        "switch": (tone(0.05, 1300, 900, "square", decay=2.5), 0.12),
        "gate_on": (
            mix(
                (noise(0.3, decay=1.5, smooth=0.1), 0.6),
                (tone(0.3, 60, kind="saw", decay=1.2), 1.0),
                (tone(0.3, 1800, 900, "sine", decay=2), 0.3),
            ),
            0.16,
        ),
        "mine_arm": (
            concat(
                tone(0.05, 1500, kind="square", decay=0.3), silence(0.04), tone(0.05, 1500, kind="square", decay=0.3)
            ),
            0.12,
        ),
        "warning": (concat(*[tone(0.14, f, kind="square", decay=0.2) for f in (880, 660, 880, 660)]), 0.13),
        "menu": (tone(0.06, 880, 1100, "square", decay=1), 0.15),
        "start": (
            mix((tone(0.6, 200, 900, "saw", decay=1), 0.6), (noise(0.6, decay=1.5, smooth=0.6, smooth_end=0.9), 0.5)),
            0.3,
        ),
        "slowmo_on": (
            mix(
                (tone(0.6, 900, 140, "saw", decay=0.6, vibrato=0.03, vib_rate=6), 1.0),
                (tone(0.6, 450, 70, "sine", decay=0.6), 0.6),
            ),
            0.25,
        ),
        "slowmo_off": (
            mix((tone(0.35, 140, 900, "saw", decay=1.0), 1.0), (tone(0.35, 70, 450, "sine", decay=1.0), 0.6)),
            0.2,
        ),
        "nuke": (
            mix(
                (noise(2.2, decay=1.4, smooth=0.9, smooth_end=0.995), 1.0),
                (tone(1.8, 70, 25, "sine", decay=1.0), 1.0),
                (noise(0.3, decay=3, smooth=0.3), 0.5),
            ),
            0.85,
        ),
        "boss_alarm": (
            concat(*[tone(0.35, f0, f1, "saw", decay=0.15) for f0, f1 in ((300, 700), (700, 300)) * 2]),
            0.22,
        ),
        "boss_missile": (
            mix(
                (noise(0.45, decay=1.0, smooth=0.7, smooth_end=0.95), 1.0),
                (tone(0.45, 110, 300, "saw", decay=1.2), 0.4),
            ),
            0.24,
        ),
        "game_over": (notes([440, 392, 349, 262], 0.22, kind="tri", decay=0.4, last=0.7), 0.35),
    }


def _encode(samples: Samples, *, float_format: bool) -> array[float] | array[int]:
    """PCM for the mixer: 16-bit signed ints natively; 32-bit floats where the mixer wants them (the web)."""
    if float_format:
        return array("f", samples)
    return array("h", (int(v * 32767) for v in samples))


class SoundFX:
    def __init__(self, *, enabled: bool = True) -> None:
        self.enabled = enabled
        self.sounds: dict[str, pygame.mixer.Sound] = {}
        self.last_played: dict[str, float] = {}
        self.loops: dict[str, pygame.mixer.Channel] = {}
        self.loaded = False
        if enabled:
            self.load()

    def load(self) -> None:
        """Synthesise every sound for the mixer's output format. Runs once, on first enable."""
        global _SR  # noqa: PLW0603 - the synth functions read the mixer's actual sample rate
        self.loaded = True
        try:
            mixer_state: tuple[int, int, int] | None = pygame.mixer.get_init()
            if mixer_state is None:
                pygame.mixer.init(22050, -16, 1, 512)
            freq, size, channels = pygame.mixer.get_init()
            if size not in (-16, 32):
                return  # unusual output format: stay silent rather than play garbage
            _SR = freq
            pygame.mixer.set_num_channels(32)
            for name, (samples, volume) in build_sound_samples().items():
                mono = _normalize(samples, volume)
                frames = [v for v in mono for _ in range(channels)]  # same signal on every channel
                pcm = _encode(frames, float_format=size == 32)
                self.sounds[name] = pygame.mixer.Sound(buffer=pcm.tobytes())
        except (pygame.error, TypeError):
            self.sounds = {}  # no audio device available: the game runs silently

    def play(self, name: str, min_gap: float = 0.04) -> None:
        """Play a one-shot sound, ignoring repeats within min_gap seconds so rapid events don't stack up."""
        if not self.enabled or name not in self.sounds:
            return
        now = pygame.time.get_ticks() / 1000
        if now - self.last_played.get(name, -1.0) < min_gap:
            return
        self.last_played[name] = now
        self.sounds[name].play()

    def set_loop(self, name: str, *, on: bool) -> None:
        on = on and self.enabled and name in self.sounds
        channel = self.loops.get(name)
        if on and channel is None:
            channel = self.sounds[name].play(loops=-1)
            if channel:
                self.loops[name] = channel
        elif not on and channel is not None:
            channel.stop()
            del self.loops[name]

    def toggle(self) -> None:
        self.enabled = not self.enabled
        if self.enabled and not self.loaded:
            self.load()
        if not self.enabled:
            if pygame.mixer.get_init():
                pygame.mixer.stop()
            self.loops.clear()
