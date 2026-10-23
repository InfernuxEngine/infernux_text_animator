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
        self.on_character_hidden = None
        self.on_complete = None
        self.on_hidden = None
        self.on_event = None
        self.visibility_handler = None
        self.event_time = 0.0
        self.cues = ()
        self._actions = ()
        self._action_index = 0
        self._generation = 0
        self._finished = False
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
        self.visible_limit = limit
        groups, start = [], 0
        for index in range(limit):
            character = characters[index]
            if self.by_word and index + 1 < limit and character.word is not None and character.word == characters[index + 1].word:
                continue
            groups.append((start, index + 1))
            start = index + 1
        self._generation += 1
        self._finished = False
        self._steps, self._times, self._actions = [], [], []
        cues = {}
        for cue in self.cues:
            cues.setdefault(cue.character, []).append(cue)
        self._action_index = 0
        time = 0.0

        def schedule_cues(index, clock):
            for cue in cues.get(index, ()):
                if cue.kind == "wait":
                    clock += cue.value
                elif cue.kind == "event":
                    self._actions.append((clock, "event", cue.value))
            return clock

        for start, end in reversed(groups) if hiding else groups:
            if not hiding:
                time = schedule_cues(start, time)
            self._steps.append(start if hiding else end)
            self._times.append(time)
            self._actions.append((time, "hidden" if hiding else "characters", (start, end)))
            for index in range(start, end):
                if self.by_word and not hiding and index != start:
                    time = schedule_cues(index, time)
                time += 1 / speed
                if characters[index].whitespace:
                    time += self.whitespace_pause
                elif self._characters[index][-1:] in ".,!?;:，。！？；：…":
                    time += self.punctuation_pause
        finish = max(self._times[-1] if self._times else 0, self._actions[-1][0] if self._actions else 0)
        self._completion_time = schedule_cues(limit, finish) if not hiding else finish
        return limit

    def _dispatch_actions(self, clock):
        generation = self._generation
        while self._action_index < len(self._actions) and self._actions[self._action_index][0] <= clock:
            self.event_time, kind, value = self._actions[self._action_index]
            self._action_index += 1
            if kind == "event":
                if self.on_event is not None:
                    self.on_event(value)
            else:
                callback = self.on_character_hidden if kind == "hidden" else self.on_character
                for index in range(*value):
                    if callback is not None:
                        callback(index, self._characters[index])
                    if generation != self._generation:
                        return False
            if generation != self._generation:
                return False
        return True

    @property
    def elapsed_time(self): return self._clock

    @property
    def hiding(self): return self._hiding

    def _publish(self, count):
        if self.visibility_handler is None:
            self.text.max_visible_characters = count
        else:
            self.visibility_handler(count, self._hiding)

    def ShowText(self, value=None):
        if value is not None:
            self.text.text = value
        self._prepare()
        self._count, self._clock, self._hiding = 0, 0.0, False
        self._publish(0)
        self.playing = True
        if self.on_start is not None:
            self.on_start()
        self.Update(0.0)
        return self

    def StartShowingText(self):
        if not self._finished:
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
            self._publish(0)
            callback = self.on_hidden
        else:
            if trigger_events:
                if not self._dispatch_actions(float("inf")):
                    return self
            self._count = len(self._characters)
            self._publish(self._count)
            callback = self.on_complete
        was_finished = self._finished
        self._clock = self._completion_time
        self._action_index = len(self._actions)
        self.playing = False
        self._finished = True
        if not was_finished and callback is not None:
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
        self._count = count
        self._publish(count)
        if not self._dispatch_actions(self._clock):
            return self
        if ((self._hiding and count == 0) or (not self._hiding and count == len(self._characters))) and self._clock >= self._completion_time:
            self.playing = False
            self._finished = True
            callback = self.on_hidden if self._hiding else self.on_complete
            if callback is not None:
                callback()
        return self
