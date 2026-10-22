"""Batch effects composed from rest geometry on every sample."""

from dataclasses import dataclass
from enum import Enum
from math import pi

import numpy as np


class EffectKind(str, Enum):
    Wave = "wave"
    Shake = "shake"
    Wiggle = "wiggle"
    Bounce = "bounce"
    Pulse = "pulse"
    Swing = "swing"
    Alpha = "alpha"


@dataclass(frozen=True, slots=True)
class Effect:
    kind: EffectKind = EffectKind.Wave
    amplitude: float = 8.0
    speed: float = 1.0
    phase: float = 0.6
    start: int = 0
    end: int | None = None
    seed: int = 0
    phase_offset: float = 0.0

    def __post_init__(self):
        object.__setattr__(self, "kind", EffectKind(self.kind))
        if self.start < 0 or (self.end is not None and self.end < self.start):
            raise ValueError("Effect range must be ordered and nonnegative")
        if not all(np.isfinite(v) for v in (self.amplitude, self.speed, self.phase, self.phase_offset)):
            raise ValueError("Effect parameters must be finite")


class EffectStack:
    def __init__(self, character_count, effects=()):
        self.count = character_count
        self._compiled = []
        indices = np.arange(character_count, dtype=np.float32)
        for effect in effects:
            end = character_count if effect.end is None else effect.end
            if end > character_count or effect.start > character_count:
                raise ValueError("Effect range exceeds the text character count")
            selection = slice(effect.start, end)
            phases = indices[selection] * effect.phase + effect.phase_offset
            if effect.kind == EffectKind.Shake:
                phases = np.random.default_rng(effect.seed).uniform(0, 2 * pi, (end - effect.start, 2)).astype(np.float32)
                phases += effect.phase_offset
            self._compiled.append((effect, selection, phases))

    def sample(self, buffer, time):
        buffer.reset()
        for effect, selected, phases in self._compiled:
            phase = phases + time * effect.speed * 2 * pi
            wave = np.sin(phase)
            amplitude = effect.amplitude
            if effect.kind == EffectKind.Wave:
                buffer.offsets[selected, 1] += wave * amplitude
            elif effect.kind == EffectKind.Wiggle:
                buffer.offsets[selected, 0] += wave * amplitude
                buffer.offsets[selected, 1] += np.cos(phase * 0.73) * amplitude
            elif effect.kind == EffectKind.Shake:
                buffer.offsets[selected] += wave * np.sin(phase * 2.17) * amplitude
            elif effect.kind == EffectKind.Bounce:
                buffer.offsets[selected, 1] -= np.abs(wave) * amplitude
            elif effect.kind == EffectKind.Pulse:
                buffer.scales[selected] *= np.maximum(0.0, 1 + wave[:, None] * amplitude)
            elif effect.kind == EffectKind.Swing:
                buffer.rotations[selected] += wave * amplitude
            elif effect.kind == EffectKind.Alpha:
                buffer.colors[selected, :, 3] *= np.clip(1 - amplitude * (wave[:, None] + 1) / 2, 0, 1)


class TextAnimation:
    """Bind once to a UIText; manual and appearance layers remain independent."""

    def __init__(self, text, effects=()):
        from infernux.lib import TextGeometryLayer

        self.text = text
        self.effects = tuple(effects)
        self.time = 0.0
        self.timeScale = 1.0
        self._layer = TextGeometryLayer.Effects
        self._layout = None
        self.Refresh()

    def Refresh(self):
        layout = self.text.get_text_layout()
        if layout is self._layout:
            return False
        buffer = self.text.create_character_buffer()
        stack = EffectStack(buffer.character_count, self.effects)
        self._layout, self._buffer, self._stack = layout, buffer, stack
        return True

    def SetEffects(self, effects):
        effects = tuple(effects)
        layout = self.text.get_text_layout()
        buffer = self._buffer if layout is self._layout else self.text.create_character_buffer()
        stack = EffectStack(buffer.character_count, effects)
        self.effects = effects
        self._layout, self._buffer, self._stack = layout, buffer, stack
        return self

    def Sample(self, time):
        self.Refresh()
        self._stack.sample(self._buffer, float(time))
        self.text.set_character_data(self._buffer, self._layer)
        return self

    def Update(self, delta):
        self.time += delta * self.timeScale
        return self.Sample(self.time)

    def Reset(self):
        self.time = 0.0
        self.text.reset_character_data(self._layer)
        return self
