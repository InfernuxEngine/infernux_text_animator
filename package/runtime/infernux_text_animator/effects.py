"""Batch effects composed from rest geometry on every sample."""

from dataclasses import dataclass, replace
from enum import Enum
from math import pi
from collections.abc import Callable, Mapping, Sequence
from typing import Self

import numpy as np
from infernux.graph.ramp import AnimationCurve
from infernux.lib import TextCharacterBuffer
from infernux.ui import UIText

from .events import TextRegion, TextStyle, TypewriterAction
from .appearance import AppearanceKind, AppearanceTag


class EffectKind(Enum):
    WAVE = "wave"
    SHAKE = "shake"
    WIGGLE = "wiggle"
    BOUNCE = "bounce"
    PULSE = "pulse"
    SWING = "swing"
    ALPHA = "alpha"
    COLOR = "tint"
    CURVE = "curve"


class CurveTarget(Enum):
    OFFSET_X = "offset_x"
    OFFSET_Y = "offset_y"
    ROTATION = "rotation"
    SCALE_X = "scale_x"
    SCALE_Y = "scale_y"
    SCALE = "scale"
    ALPHA = "alpha"


class DefaultEffectsMode(Enum):
    FALLBACK = "fallback"
    CONSTANT = "constant"


@dataclass(frozen=True, slots=True)
class Effect:
    kind: EffectKind = EffectKind.WAVE
    amplitude: float = 8.0
    speed: float = 1.0
    phase: float = 0.6
    start: int = 0
    end: int | None = None
    seed: int = 0
    phase_offset: float = 0.0
    color: tuple[float, float, float, float] = (1.0, 0.25, 0.25, 1.0)
    curve: AnimationCurve | None = None
    curve_target: CurveTarget = CurveTarget.OFFSET_Y
    once: bool = False

    def __post_init__(self):
        if not isinstance(self.kind, EffectKind) or not isinstance(self.curve_target, CurveTarget):
            raise TypeError("Effect kind and curve target must be enum members")
        if not isinstance(self.once, bool):
            raise TypeError("Effect once must be a bool")
        if self.kind == EffectKind.CURVE and self.curve is None:
            object.__setattr__(self, "curve", AnimationCurve(pre_wrap="repeat", post_wrap="repeat"))
        if self.start < 0 or (self.end is not None and self.end < self.start):
            raise ValueError("Effect range must be ordered and nonnegative")
        if not all(np.isfinite(v) for v in (self.amplitude, self.speed, self.phase, self.phase_offset)):
            raise ValueError("Effect parameters must be finite")
        if len(self.color) != 4 or not all(np.isfinite(value) for value in self.color):
            raise ValueError("Effect color must contain four finite values")


@dataclass(frozen=True, slots=True)
class CustomEffect:
    evaluator: Callable[[TextCharacterBuffer, slice, float], None]
    start: int = 0
    end: int | None = None
    amplitude: float = 1.0
    speed: float = 1.0
    once: bool = False

    def __post_init__(self):
        if not callable(self.evaluator) or self.start < 0 or (self.end is not None and self.end < self.start):
            raise ValueError("A custom effect needs a batch evaluator and an ordered range")
        if not np.isfinite(self.amplitude) or not np.isfinite(self.speed) or not isinstance(self.once, bool):
            raise ValueError("Custom effect modifiers must be finite, with bool once")


class EffectStack:
    def __init__(self, character_count: int, effects: Sequence[Effect | CustomEffect | AppearanceTag] = ()):
        self.count = character_count
        self.effects = tuple(effects)
        self._compiled = []
        self.active_until = 0.0
        indices = np.arange(character_count, dtype=np.float32)
        for effect in self.effects:
            end = character_count if effect.end is None else effect.end
            if end > character_count or effect.start > character_count:
                raise ValueError("Effect range exceeds the text character count")
            if effect.start == end:
                continue
            duration = (1/abs(effect.speed) if effect.speed else float("inf")) if effect.once else float("inf")
            self.active_until = max(self.active_until, duration)
            selection = slice(effect.start, end)
            if not isinstance(effect, Effect):
                self._compiled.append((effect, selection, None))
                continue
            phases = indices[selection] * effect.phase + effect.phase_offset
            if effect.kind == EffectKind.CURVE:
                from .curves import CurveSampler
                phases = (phases/(2*pi), CurveSampler(effect.curve))
            if effect.kind == EffectKind.SHAKE:
                phases = np.random.default_rng(effect.seed).uniform(0, 2 * pi, (end - effect.start, 2)).astype(np.float32)
                phases += effect.phase_offset
            self._compiled.append((effect, selection, phases))

    def _sample_custom(self, buffer, effect, selected, time):
        clocks = np.atleast_1d(time)
        ends = np.r_[0, np.flatnonzero(np.diff(clocks))+1, len(clocks)]
        fields = ("offsets", "rotations", "scales", "colors", "skews", "vertex_offsets", "affine_transforms", "vertex_depth_offsets")
        for first, last in zip(ends[:-1], ends[1:]):
            clock = float(clocks[first])
            if effect.once and effect.speed and clock >= 1/abs(effect.speed):
                continue
            region = selected if np.ndim(time) == 0 else slice(selected.start+int(first), selected.start+int(last))
            previous = [getattr(buffer, field)[region].copy() for field in fields] if effect.amplitude != 1 else ()
            effect.evaluator(buffer, region, clock*effect.speed)
            for field, initial in zip(fields, previous):
                target = getattr(buffer, field)[region]
                target[:] = initial+(target-initial)*effect.amplitude

    def sample(self, buffer: TextCharacterBuffer, time: float | np.ndarray, *,
               once_time: float | np.ndarray | None = None, scale: float = 1.0) -> None:
        buffer.reset()
        for effect, selected, phases in self._compiled:
            clock = np.asarray(once_time if effect.once and once_time is not None else time)
            effect_time = clock[selected] if clock.ndim else clock
            if effect.once:
                effect_time = np.maximum(0, effect_time)
            if isinstance(effect, CustomEffect):
                self._sample_custom(buffer, effect, selected, effect_time)
                continue
            if effect.once and effect.speed:
                valid = effect_time < 1/abs(effect.speed)
                if not np.any(valid):
                    continue
                if np.ndim(valid):
                    selected = np.arange(selected.start, selected.stop)[valid]
                    effect_time = effect_time[valid]
                    if effect.kind is EffectKind.CURVE:
                        phases = phases[0][valid], phases[1]
                    elif phases is not None:
                        phases = phases[valid]
            if not isinstance(effect, Effect):
                phase = np.clip(effect_time*effect.speed, 0, 1) if effect.once else (effect_time*effect.speed) % 1
                amount = effect.amplitude*(1-phase)**3
                if effect.kind is AppearanceKind.FADE:
                    buffer.colors[selected, :, 3] *= np.clip(1-amount, 0, 1)[..., None]
                elif effect.kind is AppearanceKind.SCALE:
                    buffer.scales[selected] *= np.maximum(0, 1-amount)[..., None]
                elif effect.kind is AppearanceKind.SLIDE:
                    buffer.offsets[selected, 0] += 8*amount
                elif effect.kind is AppearanceKind.ROTATION:
                    buffer.rotations[selected] += 90*amount
                continue
            if effect.kind == EffectKind.CURVE:
                offsets, curve = phases
                value = curve(offsets+effect_time*effect.speed)*effect.amplitude
                if effect.curve_target in (CurveTarget.OFFSET_X, CurveTarget.OFFSET_Y):
                    buffer.offsets[selected, 0 if effect.curve_target == CurveTarget.OFFSET_X else 1] += value
                elif effect.curve_target == CurveTarget.ROTATION:
                    buffer.rotations[selected] += value
                elif effect.curve_target == CurveTarget.SCALE:
                    buffer.scales[selected] *= 1+value[:, None]
                elif effect.curve_target in (CurveTarget.SCALE_X, CurveTarget.SCALE_Y):
                    buffer.scales[selected, 0 if effect.curve_target == CurveTarget.SCALE_X else 1] *= 1+value
                elif effect.curve_target == CurveTarget.ALPHA:
                    buffer.colors[selected, :, 3] *= np.clip(1-value[:, None], 0, 1)
                continue
            phase = phases + (effect_time[..., None] if effect.kind is EffectKind.SHAKE else effect_time) * effect.speed * 2 * pi
            wave = np.sin(phase)
            amplitude = effect.amplitude
            if effect.kind == EffectKind.WAVE:
                buffer.offsets[selected, 1] += wave * amplitude
            elif effect.kind == EffectKind.WIGGLE:
                buffer.offsets[selected, 0] += wave * amplitude
                buffer.offsets[selected, 1] += np.cos(phase * 0.73) * amplitude
            elif effect.kind == EffectKind.SHAKE:
                buffer.offsets[selected] += wave * np.sin(phase * 2.17) * amplitude
            elif effect.kind == EffectKind.BOUNCE:
                buffer.offsets[selected, 1] -= np.abs(wave) * amplitude
            elif effect.kind == EffectKind.PULSE:
                buffer.scales[selected] *= np.maximum(0.0, 1 + wave[:, None] * amplitude)
            elif effect.kind == EffectKind.SWING:
                buffer.rotations[selected] += wave * amplitude
            elif effect.kind == EffectKind.ALPHA:
                buffer.colors[selected, :, 3] *= np.clip(1 - amplitude * (wave[:, None] + 1) / 2, 0, 1)
            elif effect.kind == EffectKind.COLOR:
                weight = np.clip(amplitude*(wave+1)/2, 0, 1)
                buffer.colors[selected] *= 1+weight[:, None, None]*(np.asarray(effect.color)-1)
        if scale != 1:
            buffer.offsets[:] *= scale
            buffer.vertex_offsets[:] *= scale
            buffer.affine_transforms[:, :, 3] *= scale
            buffer.vertex_depth_offsets[:] *= scale


class TextAnimation:
    """Bind once to a UIText; manual and appearance layers remain independent."""

    def __init__(self, text: UIText, effects: Sequence[Effect | CustomEffect | AppearanceTag] = (), *,
                 parse_tags: bool = False, presets: Mapping[str, Effect | CustomEffect | AppearanceTag] | None = None,
                 default_tags_mode: DefaultEffectsMode = DefaultEffectsMode.FALLBACK,
                 actions: Mapping[str, TypewriterAction] | None = None, style_sheet: Mapping[str, TextStyle] | None = None):
        from infernux.lib import TextGeometryLayer

        self.text = text
        self.effects = tuple(effects)
        if not isinstance(parse_tags, bool):
            raise TypeError("Parse tags must be a bool")
        self.parse_tags, self.presets = parse_tags, dict(presets or {})
        self.default_tags_mode = default_tags_mode
        self.actions, self.style_sheet = actions if actions is not None else {}, style_sheet if style_sheet is not None else {}
        self._markup = None
        self.cues = ()
        self.appearance_tags, self.disappearance_tags = (), ()
        self.time = 0.0
        self._once_started = 0.0
        self.speed_multiplier = 1.0
        self.scale = 1.0
        self._layer = TextGeometryLayer.Effects
        self._layout = None
        self._bound_markup = None
        self.refresh()

    def refresh(self) -> bool:
        if self.parse_tags and (self._markup is None or self.text.text != self._markup.text):
            from .markup import parse_markup
            markup = parse_markup(self.text.text, self.presets, actions=self.actions, style_sheet=self.style_sheet)
            self.text.text = markup.text
            self._markup = markup
        layout = self.text.get_text_layout()
        if layout is self._layout and self._markup is self._bound_markup:
            return False
        if self._markup is not None and (self._bound_markup is None or self._markup.source != self._bound_markup.source):
            self._once_started = self.time
        buffer = self._buffer if layout is self._layout else self.text.create_character_buffer()
        tagged, cues = self._markup.bind(layout) if self._markup is not None else ([], ())
        stack = self._compile_stack(buffer.character_count, self.effects, tagged)
        self._layout, self._buffer, self._stack = layout, buffer, stack
        self._bound_markup = self._markup
        self.cues = cues
        self.appearance_tags, self.disappearance_tags = self._markup.bind_appearance_tags(layout) if self._markup is not None else ((), ())
        if not self.has_effects:
            buffer.reset()
            self.text.reset_character_data(self._layer)
        return True

    @property
    def behaviors(self) -> tuple[TextRegion, ...]:
        return tuple(TextRegion(effect.start, self._buffer.character_count if effect.end is None else effect.end, effect)
                     for effect in self._stack.effects if effect.start < (self._buffer.character_count if effect.end is None else effect.end))

    def _compile_stack(self, count, defaults, tagged):
        if not isinstance(self.default_tags_mode, DefaultEffectsMode):
            raise TypeError("Default tag mode must be a DefaultEffectsMode member")
        if self.default_tags_mode is DefaultEffectsMode.CONSTANT or not tagged:
            return EffectStack(count, (*defaults, *tagged))
        free = np.ones(count, dtype=np.bool_)
        for effect in tagged:
            free[effect.start:effect.end] = False
        regions = np.flatnonzero(np.diff(np.r_[False, free, False])).reshape(-1, 2)
        effective = [replace(effect, start=max(effect.start, int(first)),
                             end=min(count if effect.end is None else effect.end, int(last)))
                     for effect in defaults for first, last in regions
                     if max(effect.start, first) < min(count if effect.end is None else effect.end, last)]
        return EffectStack(count, (*effective, *tagged))

    @property
    def source_text(self) -> str:
        return self._markup.source if self._markup is not None and self.text.text == self._markup.text else self.text.text

    @property
    def has_effects(self) -> bool:
        return bool(self._stack._compiled)

    @property
    def has_active_effects(self) -> bool:
        return self.has_effects and self.time-self._once_started < self._stack.active_until

    def _set_text(self, text):
        self._markup = None
        self.text.text = text
        self.refresh()

    def set_text(self, text: str, hide_text: bool = False) -> None:
        if not isinstance(text, str) or not isinstance(hide_text, bool):
            raise TypeError("set_text requires a string and a bool")
        self._set_text(text)
        self._once_started = self.time
        self.text.max_visible_characters = 0 if hide_text else -1

    def set_effects(self, effects: Sequence[Effect | CustomEffect | AppearanceTag]) -> Self:
        effects = tuple(effects)
        if effects != self.effects:
            self._once_started = self.time
        layout = self.text.get_text_layout()
        buffer = self._buffer if layout is self._layout else self.text.create_character_buffer()
        tagged, cues = self._markup.bind(layout) if self._markup is not None else ([], ())
        stack = self._compile_stack(buffer.character_count, effects, tagged)
        self.effects = effects
        self._layout, self._buffer, self._stack = layout, buffer, stack
        self._bound_markup = self._markup
        self.cues = cues
        self.appearance_tags, self.disappearance_tags = self._markup.bind_appearance_tags(layout) if self._markup is not None else ((), ())
        return self.sample(self.time)

    def sample(self, time: float) -> Self:
        self.refresh()
        self._stack.sample(self._buffer, float(time), once_time=float(time)-self._once_started, scale=self.scale)
        self.text.set_character_data(self._buffer, self._layer)
        return self

    def update(self, delta: float) -> Self:
        self.time += delta * self.speed_multiplier
        return self.sample(self.time)

    def reset(self) -> Self:
        self.time = 0.0
        self._once_started = 0.0
        self.text.reset_character_data(self._layer)
        return self
