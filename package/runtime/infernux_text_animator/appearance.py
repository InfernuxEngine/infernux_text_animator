"""Batch appearance/disappearance transforms, independent of persistent effects."""
from dataclasses import dataclass
from math import isfinite

import numpy as np
from infernux.lib import TextGeometryLayer


# Offset XY, rotation, scale XY, alpha, vertex expansion.
_REST = np.array((0, 0, 0, 1, 1, 1, 0), dtype=np.float32)


@dataclass(frozen=True)
class Appearance:
    duration: float = 0.25
    offset: tuple = (0.0, 0.0)
    scale: tuple = (1.0, 1.0)
    rotation: float = 0.0
    alpha: float = 0.0
    vertex_expand: float = 0.0
    random_offset: float = 0.0
    seed: int = 0

    def __post_init__(self):
        if not isfinite(self.duration) or self.duration <= 0:
            raise ValueError("Appearance duration must be positive and finite")
        if not all(isfinite(value) for value in (*self.offset, *self.scale, self.rotation, self.alpha,
                                                 self.vertex_expand, self.random_offset)):
            raise ValueError("Appearance transforms must be finite")
        if len(self.offset) != 2 or len(self.scale) != 2 or not 0 <= self.alpha <= 1:
            raise ValueError("Appearance uses 2D transforms and alpha in [0, 1]")


class CharacterAppearance:
    def __init__(self, text, appearance=Appearance(), disappearance=Appearance()):
        self.text, self.appearance, self.disappearance = text, appearance, disappearance
        self.time = 0.0
        self.Refresh()

    def _hidden_state(self, effect):
        count = self.buffer.character_count
        values = np.tile(np.array((*effect.offset, effect.rotation, *effect.scale, effect.alpha, effect.vertex_expand),
                                  dtype=np.float32), (count, 1))
        angles = np.random.default_rng(effect.seed).uniform(0, 2*np.pi, count)
        values[:, :2] += effect.random_offset*np.column_stack((np.cos(angles), np.sin(angles)))
        return values

    def Refresh(self):
        self.layout = self.text.get_text_layout()
        self.buffer = self.text.create_character_buffer()
        count = self.buffer.character_count
        self._starts = np.full(count, -np.inf, dtype=np.float64)
        self._durations = np.full(count, self.appearance.duration, dtype=np.float64)
        self._showing = np.ones(count, dtype=np.bool_)
        self._from = np.tile(_REST, (count, 1))
        self._to = self._from.copy()
        self._incoming = self._hidden_state(self.appearance)
        self._outgoing = self._hidden_state(self.disappearance)
        self.active = False
        return self

    def SetAppearance(self, appearance):
        return self.SetAppearances(appearance, self.disappearance)

    def SetAppearances(self, appearance, disappearance):
        current = self._values(self.time)
        progress = np.clip((self.time-self._starts)/self._durations, 0, 1)
        ratio = np.where(self._showing, appearance.duration/self.appearance.duration,
                         disappearance.duration/self.disappearance.duration)
        remaining = self._durations*(1-progress)*ratio
        pending = remaining > 0
        self.appearance, self.disappearance = appearance, disappearance
        self._incoming = self._hidden_state(appearance)
        self._outgoing = self._hidden_state(disappearance)
        self._from[:] = current
        self._to[:] = np.where(self._showing[:, None], _REST, self._outgoing)
        self._to[~pending] = current[~pending]
        self._starts[:] = np.where(pending, np.maximum(self.time, self._starts), -np.inf)
        self._durations[:] = np.where(pending, remaining, 1)
        return self.Sample(self.time)

    def Play(self, showing=True, *, stagger=0.03):
        if not isfinite(stagger) or stagger < 0:
            raise ValueError("Character stagger must be finite and nonnegative")
        self._from[:] = self._incoming if showing and not self.active else self._values(self.time)
        self._to[:] = _REST if showing else self._outgoing
        self._starts[:] = self.time + np.arange(self.buffer.character_count)*stagger
        self._durations[:] = (self.appearance if showing else self.disappearance).duration
        self._showing[:] = showing
        self.active = bool(self.buffer.character_count)
        self.text.max_visible_characters = -1
        return self.Sample(self.time)

    def Character(self, index, showing=True, *, at=None):
        clock = self.time if at is None else at
        self._from[index] = (self._incoming[index] if showing and not self._showing[index] and self._starts[index] == -np.inf
                             else self._values(clock, index))
        self._to[index] = _REST if showing else self._outgoing[index]
        self._starts[index] = clock
        self._durations[index] = (self.appearance if showing else self.disappearance).duration
        self._showing[index] = showing
        self.active = True
        return self

    def SetVisible(self, visible=True):
        self._starts[:] = -np.inf
        self._showing[:] = visible
        self._from[:] = self._to[:] = _REST if visible else self._incoming
        self.active = False
        return self.Sample(self.time)

    def Hold(self):
        self._from[:] = self._to[:] = self._values(self.time)
        self._starts[:] = -np.inf
        self._showing[:] = True  # A later reveal continues from these held values.
        self.active = False
        return self.Sample(self.time)

    def RebaseTime(self, time=0.0):
        self._starts += float(time)-self.time
        self.time = float(time)
        return self

    def _values(self, time, index=slice(None)):
        progress = np.clip((time-self._starts[index])/self._durations[index], 0, 1)
        return self._to[index]+(self._from[index]-self._to[index])*((1-progress)**3)[..., None]

    def Sample(self, time):
        if self.text.get_text_layout() is not self.layout:
            raise RuntimeError("Text layout changed; refresh the appearance animator")
        self.time = float(time)
        values, buffer = self._values(self.time), self.buffer
        buffer.reset()
        buffer.offsets[:] = values[:, :2]
        buffer.rotations[:] = values[:, 2]
        buffer.scales[:] = values[:, 3:5]
        buffer.colors[:, :, 3] = values[:, 5, None]
        corners = np.array(((-1, -1), (1, -1), (1, 1), (-1, 1)), dtype=np.float32)
        buffer.vertex_offsets[:] = values[:, 6, None, None]*corners
        self.text.set_character_data(buffer, TextGeometryLayer.Appearance)
        self.active = bool(np.any(self.time < self._starts+self._durations))
        return self

    def Update(self, delta): return self.Sample(self.time+delta)

    def Reset(self):
        self.active = False
        self.text.reset_character_data(TextGeometryLayer.Appearance)
        return self
