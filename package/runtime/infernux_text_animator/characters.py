"""One editable manual buffer with native character, word and line selections."""
import numpy as np

from infernux.lib import TextGeometryLayer


class CharacterSelection:
    def __init__(self, owner, indices):
        self.owner, self.indices = owner, indices

    def Offset(self, value):
        self.owner.buffer.offsets[self.indices] = value
        return self

    def Rotate(self, degrees):
        self.owner.buffer.rotations[self.indices] = degrees
        return self

    def Scale(self, value):
        self.owner.buffer.scales[self.indices] = value
        return self

    def Skew(self, value):
        self.owner.buffer.skews[self.indices] = value
        return self

    def Vertices(self, offsets):
        self.owner.buffer.vertex_offsets[self.indices] = offsets
        return self

    def Color(self, rgba):
        self.owner.buffer.colors[self.indices] = rgba
        return self

    def Alpha(self, value):
        self.owner.buffer.colors[self.indices, :, 3] = value
        return self

    def Apply(self):
        self.owner.Apply()
        return self


class CharacterAnimator:
    def __init__(self, text):
        self.text = text
        self.Refresh()

    def Refresh(self):
        self.layout = self.text.get_text_layout()
        self.buffer = self.text.create_character_buffer()
        return self

    def Range(self, start=0, count=None):
        end = self.buffer.character_count if count is None else start+count
        if not 0 <= start <= end <= self.buffer.character_count:
            raise ValueError("Character range exceeds the native layout")
        return CharacterSelection(self, slice(start, end))

    def Character(self, index): return self.Range(index, 1)

    def Word(self, index):
        word = self.layout.words[index]
        return self.Range(word.character_start, word.character_end-word.character_start)

    def Line(self, index):
        if not 0 <= index < len(self.layout.lines):
            raise IndexError(index)
        return CharacterSelection(self, np.array([i for i, char in enumerate(self.layout.characters) if char.line == index], dtype=np.intp))

    def Apply(self):
        if self.text.get_text_layout() is not self.layout:
            raise RuntimeError("Text layout changed; refresh the character animator before editing")
        self.text.set_character_data(self.buffer, TextGeometryLayer.Manual)
        return self

    def Reset(self):
        self.buffer.reset()
        self.text.reset_character_data(TextGeometryLayer.Manual)
        return self
