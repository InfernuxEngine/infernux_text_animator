"""Reveal native-layout graphemes without slicing or rewriting the text."""

from bisect import bisect_right
from math import isfinite


class Typewriter:
    def __init__(self, text, *, characters_per_second=30.0, punctuation_pause=0.15, whitespace_pause=0.0, by_word=False):
        self.text = text
        self.characters_per_second = characters_per_second
        self.punctuation_pause = punctuation_pause
        self.whitespace_pause = whitespace_pause
        self.by_word = by_word
        self.timeScale = 1.0
        self.playing = False
        self.on_start = None
        self.on_character = None
        self.on_complete = None
        self.on_hidden = None
        self._clock = 0.0
        self._count = 0
        self._hiding = False
        self._steps = []
        self._times = []
        self._characters = []

    def _prepare(self, hiding=False):
        speed = self.characters_per_second
        if not isfinite(speed) or speed <= 0:
            raise ValueError("Typing speed must be finite and positive")
        if any(not isfinite(v) or v < 0 for v in (self.punctuation_pause, self.whitespace_pause)):
            raise ValueError("Typing pauses must be finite and nonnegative")
        layout = self.text.get_text_layout()
        encoded = layout.text.encode("utf-8")
        characters = layout.characters
        self._characters = [encoded[c.source_start:c.source_end].decode("utf-8") for c in characters]
        visible = self.text.max_visible_characters
        limit = min(visible, len(characters)) if hiding and visible >= 0 else len(characters)
        groups, start = [], 0
        for index in range(limit):
            character = characters[index]
            if self.by_word and index + 1 < limit and character.word is not None and character.word == characters[index + 1].word:
                continue
            groups.append((start, index + 1))
            start = index + 1
        self._steps, self._times = [], []
        time = 0.0
        for start, end in reversed(groups) if hiding else groups:
            self._steps.append(start if hiding else end)
            self._times.append(time)
            time += (end - start) / speed
            for index in range(start, end):
                if characters[index].whitespace:
                    time += self.whitespace_pause
                elif self._characters[index][-1:] in ".,!?;:，。！？；：…":
                    time += self.punctuation_pause
        return limit

    def ShowText(self, value=None):
        if value is not None:
            self.text.text = value
        self._prepare()
        self._count, self._clock, self._hiding = 0, 0.0, False
        self.text.max_visible_characters = 0
        self.playing = True
        if self.on_start is not None:
            self.on_start()
        self.Update(0.0)
        return self

    def StartShowingText(self):
        self.playing = True
        return self

    def StopShowingText(self):
        self.playing = False
        return self

    def StartDisappearingText(self):
        self._count = self._prepare(hiding=True)
        self._hiding, self._clock = True, 0.0
        self.playing = True
        self.Update(0.0)
        return self

    def SkipTypewriter(self, trigger_events=False):
        if self._hiding:
            self._count = 0
            self.text.max_visible_characters = 0
            callback = self.on_hidden
        else:
            if trigger_events and self.on_character is not None:
                for index in range(self._count, len(self._characters)):
                    self.on_character(index, self._characters[index])
            self._count = len(self._characters)
            self.text.max_visible_characters = self._count
            callback = self.on_complete
        was_playing = self.playing
        self.playing = False
        if was_playing and callback is not None:
            callback()
        return self

    def Update(self, delta):
        if not self.playing:
            return self
        if not isfinite(delta) or delta < 0:
            raise ValueError("Typing delta must be finite and nonnegative")
        self._clock += delta * self.timeScale
        steps = bisect_right(self._times, self._clock)
        count = self._steps[steps - 1] if steps else self._count
        if not self._hiding and self.on_character is not None:
            for index in range(self._count, count):
                self.on_character(index, self._characters[index])
        self._count = count
        self.text.max_visible_characters = count
        if (self._hiding and count == 0) or (not self._hiding and count == len(self._characters)):
            self.playing = False
            callback = self.on_hidden if self._hiding else self.on_complete
            if callback is not None:
                callback()
        return self
