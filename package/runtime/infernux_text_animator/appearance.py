"""Batch appearance/disappearance transforms, independent of persistent effects."""
from dataclasses import dataclass
from math import isfinite

import numpy as np
from infernux.lib import TextGeometryLayer


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
    def __init__(self, text, appearance=Appearance()):
        self.text, self.appearance = text, appearance
        self.time = 0.0
        self.Refresh()

    def Refresh(self):
        self.layout = self.text.get_text_layout()
        self.buffer = self.text.create_character_buffer()
        count = self.buffer.character_count
        self._starts = np.full(count, -np.inf, dtype=np.float64)
        self._showing = np.ones(count, dtype=np.bool_)
        angles = np.random.default_rng(self.appearance.seed).uniform(0, 2*np.pi, count)
        self._offsets = np.array(self.appearance.offset) + self.appearance.random_offset*np.column_stack((np.cos(angles), np.sin(angles)))
        self.active = False
        return self

    def SetAppearance(self, appearance):
        self._starts[:] = self.time-(self.time-self._starts)*(appearance.duration/self.appearance.duration)
        self.appearance = appearance
        angles = np.random.default_rng(appearance.seed).uniform(0, 2*np.pi, self.buffer.character_count)
        self._offsets = np.array(appearance.offset) + appearance.random_offset*np.column_stack((np.cos(angles), np.sin(angles)))
        return self.Sample(self.time)

    def Play(self, showing=True, *, stagger=0.03):
        if not isfinite(stagger) or stagger < 0:
            raise ValueError("Character stagger must be finite and nonnegative")
        self._starts[:] = self.time + np.arange(self.buffer.character_count)*stagger
        self._showing[:] = showing
        self.active = bool(self.buffer.character_count)
        self.text.max_visible_characters = -1
        return self.Sample(self.time)

    def Character(self, index, showing=True, *, at=None):
        clock = self.time if at is None else at
        progress = min(1, max(0, (clock-self._starts[index])/self.appearance.duration))
        strength = (1-progress)**3 if self._showing[index] else 1-(1-progress)**3
        progress = 1-strength**(1/3) if showing else 1-(1-strength)**(1/3)
        self._starts[index] = clock-progress*self.appearance.duration
        self._showing[index] = showing
        self.active = True
        return self

    def SetVisible(self, visible=True):
        self._starts[:] = -np.inf
        self._showing[:] = visible
        self.active = False
        return self.Sample(self.time)

    def RebaseTime(self, time=0.0):
        self._starts += float(time)-self.time
        self.time = float(time)
        return self

    def Sample(self, time):
        if self.text.get_text_layout() is not self.layout:
            raise RuntimeError("Text layout changed; refresh the appearance animator")
        self.time = float(time)
        effect, buffer = self.appearance, self.buffer
        progress = np.clip((self.time-self._starts)/effect.duration, 0, 1)
        eased = 1-(1-progress)**3
        strength = np.where(self._showing, 1-eased, eased)
        buffer.reset()
        buffer.offsets[:] = strength[:, None]*self._offsets
        buffer.rotations[:] = strength*effect.rotation
        buffer.scales[:] = 1+strength[:, None]*(np.array(effect.scale)-1)
        buffer.colors[:, :, 3] = (1+strength*(effect.alpha-1))[:, None]
        corners = np.array(((-1, -1), (1, -1), (1, 1), (-1, 1)), dtype=np.float32)
        buffer.vertex_offsets[:] = strength[:, None, None]*effect.vertex_expand*corners
        self.text.set_character_data(buffer, TextGeometryLayer.Appearance)
        self.active = bool(np.any(progress < 1))
        return self

    def Update(self, delta): return self.Sample(self.time+delta)

    def Reset(self):
        self.active = False
        self.text.reset_character_data(TextGeometryLayer.Appearance)
        return self
