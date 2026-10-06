from __future__ import annotations

import pygame
import pytest

from nova_strike import sound


def test_tone_has_requested_length_and_stays_in_range() -> None:
    samples = sound.tone(0.1, 440)
    assert len(samples) == int(sound._SR * 0.1)
    assert max(abs(v) for v in samples) <= 1.0


def test_tone_decays_to_silence() -> None:
    samples = sound.tone(0.2, 300, decay=2.0)
    assert abs(samples[-1]) < 0.01


@pytest.mark.parametrize("kind", ["sine", "square", "saw", "tri"])
def test_waveforms_are_bounded(kind: str) -> None:
    assert all(-1.0 <= sound._wave(kind, p / 100) <= 1.0 for p in range(200))


def test_noise_is_normalised() -> None:
    samples = sound.noise(0.05, smooth=0.5)
    assert max(abs(v) for v in samples) == pytest.approx(1.0)


def test_silence_mix_and_concat() -> None:
    assert sound.silence(0.01) == [0.0] * int(sound._SR * 0.01)
    assert sound.mix(([1.0, 1.0], 0.5), ([1.0], 1.0)) == [1.5, 0.5]  # shorter parts are padded
    assert sound.concat([1.0], [2.0, 3.0]) == [1.0, 2.0, 3.0]


def test_normalize_scales_to_peak() -> None:
    assert sound._normalize([0.5, -0.25], 1.0) == [1.0, -0.5]
    assert sound._normalize([0.0, 0.0], 1.0) == [0.0, 0.0]  # silence doesn't divide by zero


def test_every_sound_effect_is_defined_with_a_sane_volume() -> None:
    effects = sound.build_sound_samples()
    for name in ("shoot", "explosion", "laser", "nuke", "boss_alarm", "game_over"):
        assert name in effects
    for samples, volume in effects.values():
        assert samples
        assert 0 < volume <= 1


def test_disabled_sound_skips_synthesis_until_enabled(display: None) -> None:
    fx = sound.SoundFX(enabled=False)
    assert not fx.loaded
    fx.play("shoot")  # muted: a no-op, not an error
    fx.toggle()
    assert fx.enabled
    assert fx.loaded


def test_repeated_sound_within_min_gap_is_skipped(display: None, monkeypatch: pytest.MonkeyPatch) -> None:
    fx = sound.SoundFX(enabled=True)
    played: list[str] = []

    class FakeSound:
        def play(self) -> None:
            played.append("x")

    fx.sounds["shoot"] = FakeSound()  # type: ignore[assignment]
    now = [1000]
    monkeypatch.setattr(pygame.time, "get_ticks", lambda: now[0])
    fx.play("shoot")
    fx.play("shoot")  # same instant: dropped
    now[0] += 100
    fx.play("shoot")
    assert len(played) == 2
