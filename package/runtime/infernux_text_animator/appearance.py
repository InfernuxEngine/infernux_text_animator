"""Batch appearance/disappearance transforms, independent of persistent effects."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from math import isfinite
from collections.abc import Sequence
from typing import Self, TYPE_CHECKING

import numpy as np
from infernux.lib import TextGeometryLayer
from infernux.ui import UIText

if TYPE_CHECKING:
    from .effects import CustomEffect, Effect


# Transform, alpha, expansion, per-vertex RGBA, skew and per-vertex XY.
_REST = np.array((0, 0, 0, 1, 1, 1, 0, *([1]*16), 0, *([0]*8),
                  1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0), dtype=np.float32)


class AppearanceKind(Enum):
    FADE = "fade"
    SCALE = "incr"
    SLIDE = "slideh"
    ROTATION = "rot"


@dataclass(frozen=True, slots=True)
class AppearanceTag:
    kind: AppearanceKind
    amplitude: float = 1.0
    speed: float = 1.0
    start: int = 0
    end: int | None = None
    once: bool = False

    def __post_init__(self):
        if not isinstance(self.kind, AppearanceKind):
            raise TypeError("Appearance kind must be an AppearanceKind member")
        if not isfinite(self.amplitude) or not isfinite(self.speed) or self.speed <= 0 or not isinstance(self.once, bool):
            raise ValueError("Appearance modifiers must be finite, with positive speed")
        if self.start < 0 or self.end is not None and self.end < self.start:
            raise ValueError("Appearance range must be ordered and nonnegative")


@dataclass(frozen=True)
class Appearance:
    duration: float = 0.25
    offset: tuple[float, float] = (0.0, 0.0)
    scale: tuple[float, float] = (1.0, 1.0)
    rotation: float = 0.0
    alpha: float = 0.0
    vertex_expand: float = 0.0
    random_offset: float = 0.0
    seed: int = 0

    def __post_init__(self):
        if not isfinite(self.duration):
            raise ValueError("Appearance duration must be finite")
        if not all(isfinite(value) for value in (*self.offset, *self.scale, self.rotation, self.alpha,
                                                 self.vertex_expand, self.random_offset)):
            raise ValueError("Appearance transforms must be finite")
        if len(self.offset) != 2 or len(self.scale) != 2 or not 0 <= self.alpha <= 1:
            raise ValueError("Appearance uses 2D transforms and alpha in [0, 1]")


class CharacterAppearance:
    def __init__(self, text: UIText, appearance: Appearance = Appearance(), disappearance: Appearance = Appearance(), *,
                 appearance_tags: Sequence[AppearanceTag | Effect | CustomEffect] = (),
                 disappearance_tags: Sequence[AppearanceTag | Effect | CustomEffect] = (),
                 default_enabled: bool = True, constant_defaults: bool = False):
        self.text, self.appearance, self.disappearance = text, appearance, disappearance
        self.appearance_tags, self.disappearance_tags = tuple(appearance_tags), tuple(disappearance_tags)
        self.default_enabled = default_enabled
        self.constant_defaults = constant_defaults
        self.scale = 1.0
        self.first_visible_character = 0
        self.max_visible_characters = -1
        self.time = 0.0
        self.refresh()

    def _hidden_state(self, effect):
        count = self.buffer.character_count
        values = np.tile(_REST, (count, 1))
        values[:, :7] = (*effect.offset, effect.rotation, *effect.scale, effect.alpha, effect.vertex_expand)
        angles = np.random.default_rng(effect.seed).uniform(0, 2*np.pi, count)
        values[:, :2] += effect.random_offset*np.column_stack((np.cos(angles), np.sin(angles)))
        return values

    def _compile(self, profile, tags):
        from .effects import EffectStack
        count = self.buffer.character_count
        duration = max(0.0, profile.duration)
        values = self._hidden_state(profile) if self.default_enabled else np.tile(_REST, (count, 1))
        if not self.default_enabled:
            values[:, 5] = 0
        durations = np.full((count, len(_REST)), duration if self.default_enabled else 0.0)
        tagged = np.zeros(count, dtype=np.bool_)
        explicit = np.zeros_like(durations)
        channels_set = np.zeros_like(durations, dtype=np.bool_)
        alpha_tags = np.zeros(count, dtype=np.bool_)
        motion = []
        for tag in tags:
            end = count if tag.end is None else tag.end
            if end > count or tag.start > count:
                raise ValueError("Appearance range exceeds the native character count")
            selected = slice(tag.start, end)
            fresh = ~tagged[selected] if not self.constant_defaults else np.zeros(end-tag.start, dtype=np.bool_)
            values[selected][fresh] = _REST
            durations[selected][fresh] = 0
            tagged[selected] = True
            if not isinstance(tag, AppearanceTag):
                motion.append(tag)
                durations[selected] = np.maximum(durations[selected], duration)
                continue
            if tag.kind is AppearanceKind.FADE:
                channels = slice(5, 6)
                values[selected, 5] *= np.clip(1-tag.amplitude, 0, 1)
                alpha_tags[selected] = True
            elif tag.kind is AppearanceKind.SCALE:
                channels = slice(3, 5)
                values[selected, 3:5] *= max(0, 1-tag.amplitude)
            elif tag.kind is AppearanceKind.SLIDE:
                channels = slice(0, 1)
                values[selected, 0] += 8*tag.amplitude
            elif tag.kind is AppearanceKind.ROTATION:
                channels = slice(2, 3)
                values[selected, 2] += 90*tag.amplitude
            explicit[selected, channels] = np.maximum(explicit[selected, channels], duration/tag.speed)
            channels_set[selected, channels] = True
        durations[channels_set] = np.maximum(durations[channels_set], explicit[channels_set]) if self.constant_defaults else explicit[channels_set]
        # Dynamic effects use the same evaluator in every category. The phase
        # envelope starts and ends at rest so reversals retain current geometry.
        for effect in motion:
            end = count if effect.end is None else effect.end
            indices = np.arange(effect.start, end)[~alpha_tags[effect.start:end]]
            values[indices, 5] = 0
        return values, durations, EffectStack(count, motion)

    def refresh(self) -> Self:
        self.layout = self.text.get_text_layout()
        self.buffer = self.text.create_character_buffer()
        count = self.buffer.character_count
        self._starts = np.full(count, -np.inf, dtype=np.float64)
        self._durations = np.full((count, len(_REST)), self.appearance.duration, dtype=np.float64)
        self._showing = np.ones(count, dtype=np.bool_)
        self._from = np.tile(_REST, (count, 1))
        self._to = self._from.copy()
        self._incoming, self._entry_durations, self._entry_stack = self._compile(self.appearance, self.appearance_tags)
        self._outgoing, self._exit_durations, self._exit_stack = self._compile(self.disappearance, self.disappearance_tags)
        self._motion_buffer = self.text.create_character_buffer() if self._entry_stack._compiled or self._exit_stack._compiled else None
        self._motion_time = None
        self.active = False
        return self

    def set_appearance(self, appearance: Appearance) -> Self:
        return self.set_appearances(appearance, self.disappearance)

    def set_appearances(self, appearance: Appearance, disappearance: Appearance) -> Self:
        current = self._values(self.time)
        elapsed = self.time-self._starts[:, None]
        progress = np.clip(np.divide(elapsed, self._durations, out=np.ones_like(self._durations), where=self._durations > 0), 0, 1)
        old_duration = np.where(self._showing[:, None], self._entry_durations, self._exit_durations)
        self.appearance, self.disappearance = appearance, disappearance
        self._incoming, self._entry_durations, self._entry_stack = self._compile(appearance, self.appearance_tags)
        self._outgoing, self._exit_durations, self._exit_stack = self._compile(disappearance, self.disappearance_tags)
        self._motion_buffer = self.text.create_character_buffer() if self._entry_stack._compiled or self._exit_stack._compiled else None
        self._motion_time = None
        new_duration = np.where(self._showing[:, None], self._entry_durations, self._exit_durations)
        ratio = np.divide(new_duration, old_duration, out=np.zeros_like(new_duration), where=old_duration > 0)
        remaining = self._durations*(1-progress)*ratio
        pending = remaining > 0
        self._from[:] = current
        self._to[:] = np.where(self._showing[:, None], _REST, self._outgoing)
        skipped = (new_duration == 0) & (self._durations > 0) & (progress < 1)
        retained = ~pending & ~skipped
        self._to[retained] = current[retained]
        self._starts[:] = np.where(np.any(pending, axis=1), np.maximum(self.time, self._starts), -np.inf)
        self._durations[:] = np.where(pending, remaining, 0)
        return self.sample(self.time)

    def set_appearance_tags(self, appearances: Sequence[AppearanceTag | Effect | CustomEffect],
                            disappearances: Sequence[AppearanceTag | Effect | CustomEffect], *,
                            default_enabled: bool = True, constant_defaults: bool = False) -> Self:
        self.appearance_tags, self.disappearance_tags = tuple(appearances), tuple(disappearances)
        self.default_enabled = default_enabled
        self.constant_defaults = constant_defaults
        return self.set_appearances(self.appearance, self.disappearance)

    def play(self, showing: bool = True, *, stagger: float = 0.03) -> Self:
        if not isfinite(stagger) or stagger < 0:
            raise ValueError("character stagger must be finite and nonnegative")
        self._from[:] = self._incoming if showing and not self.active else self._values(self.time)
        self._to[:] = _REST if showing else self._outgoing
        durations = self._entry_durations if showing else self._exit_durations
        self._starts[:] = np.where(np.any(durations > 0, axis=1), self.time + np.arange(self.buffer.character_count)*stagger, -np.inf)
        self._durations[:] = durations
        self._from[durations == 0] = self._to[durations == 0]
        self._showing[:] = showing
        self._motion_time = None
        self.active = bool(self.buffer.character_count)
        self.text.max_visible_characters = -1
        return self.sample(self.time)

    def character(self, index: int, showing: bool = True, *, at: float | None = None) -> Self:
        clock = self.time if at is None else at
        self._from[index] = (self._incoming[index] if showing and not self._showing[index] and self._starts[index] == -np.inf
                             else self._values(clock, index))
        self._to[index] = _REST if showing else self._outgoing[index]
        duration = (self._entry_durations if showing else self._exit_durations)[index]
        self._starts[index] = clock if np.any(duration > 0) else -np.inf
        self._durations[index] = duration
        self._from[index, duration == 0] = self._to[index, duration == 0]
        self._showing[index] = showing
        self._motion_time = None
        self.active = True
        return self

    def _set_visibility(self, indices, visible, animated, *, at=None, commit=True):
        clock = self.time if at is None else at
        current = self._values(clock, indices)
        if visible:
            fresh = ~self._showing[indices] & (self._starts[indices] == -np.inf)
            current = np.where(fresh[:, None], self._incoming[indices], current)
        self._from[indices] = current
        self._to[indices] = _REST if visible else self._outgoing[indices]
        if not visible:
            self._to[indices, 5] = 0
        durations = (self._entry_durations if visible else self._exit_durations)[indices].copy()
        if not visible:
            durations[:, 5] = np.maximum(durations[:, 5], np.max(durations, axis=1))
        moving = animated & (durations > 0)
        self._starts[indices] = np.where(np.any(moving, axis=1), clock, -np.inf)
        self._durations[indices] = np.where(moving, durations, 0)
        self._showing[indices] = visible
        self._motion_time = None
        self._from[indices] = np.where(moving, self._from[indices], self._to[indices])
        self.active = True
        return self.sample(self.time) if commit else self

    def set_visible(self, visible: bool = True) -> Self:
        self._starts[:] = -np.inf
        self._showing[:] = visible
        self._from[:] = self._to[:] = _REST if visible else self._incoming
        self.active = False
        return self.sample(self.time)

    def hold(self) -> Self:
        self._from[:] = self._to[:] = self._values(self.time)
        self._starts[:] = -np.inf
        self._showing[:] = True  # A later reveal continues from these held values.
        self.active = False
        return self.sample(self.time)

    def rebase_time(self, time: float = 0.0) -> Self:
        self._starts += float(time)-self.time
        self.time = float(time)
        return self

    def _values(self, time, index=slice(None)):
        elapsed = np.asarray(time-self._starts[index])[..., None]
        durations = self._durations[index]
        progress = np.clip(np.divide(elapsed, durations, out=np.ones_like(durations), where=durations > 0), 0, 1)
        values = self._to[index]+(self._from[index]-self._to[index])*((1-progress)**3)
        duration = np.max(durations, axis=-1)
        phase = np.clip(np.divide(elapsed[..., 0], duration, out=np.ones_like(duration), where=duration > 0), 0, 1)
        if self._motion_buffer is not None and np.any((phase > 0) & (phase < 1)):
            if self._motion_time != time:
                motions = []
                buffer = self._motion_buffer
                clocks = np.maximum(0, np.where(np.isfinite(self._starts), time-self._starts, 0))
                for stack in (self._entry_stack, self._exit_stack):
                    stack.sample(buffer, clocks)
                    state = np.tile(_REST, (buffer.character_count, 1))
                    state[:, :2], state[:, 2], state[:, 3:5] = buffer.offsets, buffer.rotations, buffer.scales
                    state[:, 7:23], state[:, 23], state[:, 24:32] = buffer.colors.reshape(-1, 16), buffer.skews, buffer.vertex_offsets.reshape(-1, 8)
                    state[:, 32:44], state[:, 44:48] = buffer.affine_transforms.reshape(-1, 12), buffer.vertex_depth_offsets
                    motions.append(state)
                self._motions = motions
                self._motion_time = time
            motion = np.where(np.asarray(self._showing[index])[..., None], self._motions[0][index], self._motions[1][index])
            envelope = (4*phase*(1-phase))[..., None]
            delta = (motion-_REST)*envelope
            values[..., :3] += delta[..., :3]
            values[..., 3:5] *= 1+delta[..., 3:5]
            values[..., 7:23] *= 1+delta[..., 7:23]
            values[..., 23:] += delta[..., 23:]
        return values

    def sample(self, time: float) -> Self:
        if self.text.get_text_layout() is not self.layout:
            raise RuntimeError("Text layout changed; refresh the appearance animator")
        self.time = float(time)
        values, buffer = self._values(self.time), self.buffer
        buffer.reset()
        buffer.offsets[:] = values[:, :2]*self.scale
        buffer.rotations[:] = values[:, 2]
        buffer.scales[:] = values[:, 3:5]
        buffer.colors[:] = values[:, 7:23].reshape(-1, 4, 4)
        buffer.colors[:, :, 3] *= values[:, 5, None]
        buffer.skews[:] = values[:, 23]
        buffer.colors[:self.first_visible_character, :, 3] = 0
        if self.max_visible_characters >= 0:
            buffer.colors[self.max_visible_characters:, :, 3] = 0
        corners = np.array(((-1, -1), (1, -1), (1, 1), (-1, 1)), dtype=np.float32)
        buffer.vertex_offsets[:] = (values[:, 24:32].reshape(-1, 4, 2)+values[:, 6, None, None]*corners)*self.scale
        buffer.affine_transforms[:] = values[:, 32:44].reshape(-1, 3, 4)
        buffer.affine_transforms[:, :, 3] *= self.scale
        buffer.vertex_depth_offsets[:] = values[:, 44:48]*self.scale
        self.text.set_character_data(buffer, TextGeometryLayer.Appearance)
        self.active = bool(np.any(self.time < self._starts[:, None]+self._durations))
        return self

    def update(self, delta: float) -> Self: return self.sample(self.time+delta)

    def reset(self) -> Self:
        self.active = False
        self.text.reset_character_data(TextGeometryLayer.Appearance)
        return self
