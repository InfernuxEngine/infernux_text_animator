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
    Color = "tint"
    Curve = "curve"


class CurveTarget(str, Enum):
    OffsetX = "offset_x"
    OffsetY = "offset_y"
    Rotation = "rotation"
    ScaleX = "scale_x"
    ScaleY = "scale_y"
    Scale = "scale"
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
    color: tuple = (1.0, 0.25, 0.25, 1.0)
    curve: object = None
    curve_target: CurveTarget = CurveTarget.OffsetY

    def __post_init__(self):
        object.__setattr__(self, "kind", EffectKind(self.kind))
        object.__setattr__(self, "curve_target", CurveTarget(self.curve_target))
        if self.kind == EffectKind.Curve and self.curve is None:
            from infernux.graph.ramp import AnimationCurve
            object.__setattr__(self, "curve", AnimationCurve(pre_wrap="repeat", post_wrap="repeat"))
        if self.start < 0 or (self.end is not None and self.end < self.start):
            raise ValueError("Effect range must be ordered and nonnegative")
        if not all(np.isfinite(v) for v in (self.amplitude, self.speed, self.phase, self.phase_offset)):
            raise ValueError("Effect parameters must be finite")
        if len(self.color) != 4 or not all(np.isfinite(value) for value in self.color):
            raise ValueError("Effect color must contain four finite values")


@dataclass(frozen=True, slots=True)
class CustomEffect:
    evaluator: object
    start: int = 0
    end: int | None = None

    def __post_init__(self):
        if not callable(self.evaluator) or self.start < 0 or (self.end is not None and self.end < self.start):
            raise ValueError("A custom effect needs a batch evaluator and an ordered range")


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
            if isinstance(effect, CustomEffect):
                self._compiled.append((effect, selection, None))
                continue
            phases = indices[selection] * effect.phase + effect.phase_offset
            if effect.kind == EffectKind.Curve:
                from .curves import CurveSampler
                phases = (phases/(2*pi), CurveSampler(effect.curve))
            if effect.kind == EffectKind.Shake:
                phases = np.random.default_rng(effect.seed).uniform(0, 2 * pi, (end - effect.start, 2)).astype(np.float32)
                phases += effect.phase_offset
            self._compiled.append((effect, selection, phases))

    def sample(self, buffer, time):
        buffer.reset()
        for effect, selected, phases in self._compiled:
            if isinstance(effect, CustomEffect):
                effect.evaluator(buffer, selected, time)
                continue
            if effect.kind == EffectKind.Curve:
                offsets, curve = phases
                value = curve(offsets+time*effect.speed)*effect.amplitude
                if effect.curve_target in (CurveTarget.OffsetX, CurveTarget.OffsetY):
                    buffer.offsets[selected, 0 if effect.curve_target == CurveTarget.OffsetX else 1] += value
                elif effect.curve_target == CurveTarget.Rotation:
                    buffer.rotations[selected] += value
                elif effect.curve_target == CurveTarget.Scale:
                    buffer.scales[selected] *= 1+value[:, None]
                elif effect.curve_target in (CurveTarget.ScaleX, CurveTarget.ScaleY):
                    buffer.scales[selected, 0 if effect.curve_target == CurveTarget.ScaleX else 1] *= 1+value
                elif effect.curve_target == CurveTarget.Alpha:
                    buffer.colors[selected, :, 3] *= np.clip(1-value[:, None], 0, 1)
                continue
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
            elif effect.kind == EffectKind.Color:
                weight = np.clip(amplitude*(wave+1)/2, 0, 1)
                buffer.colors[selected] *= 1+weight[:, None, None]*(np.asarray(effect.color)-1)


class TextAnimation:
    """Bind once to a UIText; manual and appearance layers remain independent."""

    def __init__(self, text, effects=(), *, parse_tags=False, presets=None):
        from infernux.lib import TextGeometryLayer

        self.text = text
        self.effects = tuple(effects)
        self.parse_tags, self.presets = bool(parse_tags), dict(presets or {})
        self._markup = None
        self.cues = ()
        self.time = 0.0
        self.timeScale = 1.0
        self._layer = TextGeometryLayer.Effects
        self._layout = None
        self.Refresh()

    def Refresh(self):
        if self.parse_tags and (self._markup is None or self.text.text != self._markup.text):
            from .markup import parse_markup
            markup = parse_markup(self.text.text, self.presets)
            self.text.text = markup.text
            self._markup = markup
        layout = self.text.get_text_layout()
        if layout is self._layout:
            return False
        buffer = self.text.create_character_buffer()
        tagged, cues = self._markup.bind(layout) if self._markup is not None else ([], ())
        stack = EffectStack(buffer.character_count, (*self.effects, *tagged))
        self._layout, self._buffer, self._stack = layout, buffer, stack
        self.cues = cues
        return True

    @property
    def source_text(self):
        return self._markup.source if self._markup is not None and self.text.text == self._markup.text else self.text.text

    @property
    def has_effects(self):
        return bool(self._stack._compiled)

    def SetText(self, value):
        self._markup = None
        self.text.text = value
        self.Refresh()
        return self

    def SetEffects(self, effects):
        effects = tuple(effects)
        layout = self.text.get_text_layout()
        buffer = self._buffer if layout is self._layout else self.text.create_character_buffer()
        tagged, cues = self._markup.bind(layout) if self._markup is not None else ([], ())
        stack = EffectStack(buffer.character_count, (*effects, *tagged))
        self.effects = effects
        self._layout, self._buffer, self._stack = layout, buffer, stack
        self.cues = cues
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
