"""One editable manual buffer with native character, word and line selections."""
from __future__ import annotations
from typing import Self

import numpy as np

from infernux.lib import TextGeometryLayer
from infernux.ui import UIText


class CharacterSelection:
    def __init__(self, owner, indices):
        self.owner, self.indices = owner, indices

    def offset(self, value: tuple[float, float]) -> Self:
        self.owner.buffer.offsets[self.indices] = value
        return self

    def rotate(self, degrees: float) -> Self:
        self.owner.buffer.rotations[self.indices] = degrees
        return self

    def scale(self, value: tuple[float, float]) -> Self:
        self.owner.buffer.scales[self.indices] = value
        return self

    def skew(self, value: float) -> Self:
        self.owner.buffer.skews[self.indices] = value
        return self

    def vertices(self, offsets: tuple[tuple[float, float], ...]) -> Self:
        self.owner.buffer.vertex_offsets[self.indices] = offsets
        return self

    def color(self, rgba: tuple[float, float, float, float]) -> Self:
        self.owner.buffer.colors[self.indices] = rgba
        self.owner.buffer.color_overrides[self.indices] = 3
        return self

    def alpha(self, value: float) -> Self:
        self.owner.buffer.colors[self.indices, :, 3] = value
        flags = self.owner.buffer.color_overrides[self.indices].astype(np.uint8)
        self.owner.buffer.color_overrides[self.indices] = flags | 2
        return self

    def apply(self) -> Self:
        self.owner.apply()
        return self


class CharacterAnimator:
    def __init__(self, text: UIText):
        self.text = text
        self.refresh()

    def refresh(self) -> Self:
        self.layout = self.text.get_text_layout()
        self.buffer = self.text.create_character_buffer()
        return self

    def range(self, start: int = 0, count: int | None = None) -> CharacterSelection:
        end = self.buffer.character_count if count is None else start+count
        if not 0 <= start <= end <= self.buffer.character_count:
            raise ValueError("character range exceeds the native layout")
        return CharacterSelection(self, slice(start, end))

    def character(self, index: int) -> CharacterSelection: return self.range(index, 1)

    def word(self, index: int) -> CharacterSelection:
        word = self.layout.words[index]
        return self.range(word.character_start, word.character_end-word.character_start)

    def line(self, index: int) -> CharacterSelection:
        if not 0 <= index < len(self.layout.lines):
            raise IndexError(index)
        return CharacterSelection(self, np.array([i for i, char in enumerate(self.layout.characters) if char.line == index], dtype=np.intp))

    def apply(self) -> Self:
        if self.text.get_text_layout() is not self.layout:
            raise RuntimeError("Text layout changed; refresh the character animator before editing")
        self.text.set_character_data(self.buffer, TextGeometryLayer.Manual)
        return self

    def reset(self) -> Self:
        self.buffer.reset()
        self.text.reset_character_data(TextGeometryLayer.Manual)
        return self
