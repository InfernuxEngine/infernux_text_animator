"""Reveal native-layout graphemes without slicing or rewriting the text."""

from math import isfinite

from infernux.lib import TextLayout


class Typewriter:
    def __init__(self, text, *, characters_per_second=30.0, punctuation_pause=0.15, whitespace_pause=0.0, by_word=False):
        self.text = text
        self.characters_per_second = characters_per_second
        self.punctuation_pause = punctuation_pause
        self.whitespace_pause = whitespace_pause
        self.by_word = by_word
        self._time_scale = 1.0
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
        self._control_serial = 0
        self._finished = False
        self._clock = 0.0
        self._playback_clock = 0.0
        self._completion_time = None
        self._count = 0
        self._hiding = False
        self._characters = []
        self._whitespace = []

    def _prepare(self, hiding=False):
        speed = self.characters_per_second
        if not isfinite(speed) or speed <= 0:
            raise ValueError("Typing speed must be finite and positive")
        if any(not isfinite(v) or v < 0 for v in (self.punctuation_pause, self.whitespace_pause)):
            raise ValueError("Typing pauses must be finite and nonnegative")
        layout = self.text.get_text_layout()
        characters = layout.characters
        self._characters = TextLayout.split_graphemes(layout.display_text)
        self._whitespace = [character.whitespace for character in characters]
        visible = self.text.max_visible_characters
        limit = min(visible, len(characters)) if hiding and visible >= 0 else len(characters)
        self.visible_limit = limit
        cues = {}
        for cue in self.cues:
            cues.setdefault(cue.character, []).append(cue)
        groups, start = [], 0
        for index in range(limit):
            character = characters[index]
            if (self.by_word and index + 1 < limit and character.word is not None
                    and character.word == characters[index + 1].word and (hiding or index + 1 not in cues)):
                continue
            groups.append((start, index + 1))
            start = index + 1
        self._generation += 1
        self._control_serial += 1
        self._finished = False
        self._actions = []
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
            group_time = time
            for index in range(start, end):
                self._actions.append((group_time, "hidden" if hiding else "character", (index, start if hiding else end)))
                time += 1 / speed
                if characters[index].whitespace:
                    time += self.whitespace_pause
                elif self._characters[index][-1:] in ".,!?;:，。！？；：…":
                    time += self.punctuation_pause
        finish = self._actions[-1][0] if self._actions else 0
        self._completion_time = schedule_cues(limit, finish) if not hiding else finish
        return limit

    def _advance_clock(self, clock, scale):
        self._playback_clock += (clock-self._clock)/scale
        self._clock = clock

    def _dispatch_actions(self, clock, scale):
        serial = self._control_serial
        while self._action_index < len(self._actions) and self._actions[self._action_index][0] <= clock:
            self.event_time, kind, value = self._actions[self._action_index]
            self._advance_clock(self.event_time, scale)
            self._action_index += 1
            if kind == "event":
                if self.on_event is not None:
                    self.on_event(value)
            else:
                index, count = value
                if count != self._count:
                    self._count = count
                    self._publish(count)
                callback = self.on_character_hidden if kind == "hidden" else self.on_character
                if callback is not None:
                    callback(index, self._characters[index])
            if serial != self._control_serial:
                return False
        return True

    @property
    def elapsed_time(self): return self._clock

    @property
    def playback_time(self): return self._playback_clock

    @property
    def timeScale(self): return self._time_scale

    @timeScale.setter
    def timeScale(self, value):
        if not isfinite(value) or value <= 0:
            raise ValueError("Typewriter speed multiplier must be finite and positive")
        self._time_scale = float(value)

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
        self._count, self._clock, self._playback_clock, self._hiding = 0, 0.0, 0.0, False
        self._publish(0)
        self.playing = True
        serial = self._control_serial
        if self.on_start is not None:
            self.on_start()
        if serial == self._control_serial:
            self.Update(0.0)
        return self

    def StartShowingText(self):
        if self._completion_time is None:
            return self.ShowText()
        if not self._finished:
            self._control_serial += 1
            self.playing = True
        return self

    def StopShowingText(self):
        self._control_serial += 1
        self.playing = False
        return self

    def _cancel(self):
        self.StopShowingText()
        self._generation += 1
        self._completion_time = None
        self._finished = True

    def StartDisappearingText(self):
        self._count = self._prepare(hiding=True)
        self._hiding, self._clock, self._playback_clock = True, 0.0, 0.0
        self.playing = True
        self.Update(0.0)
        return self

    def SkipTypewriter(self, trigger_events=False):
        if self._finished:
            return self
        if self._completion_time is None:
            self._prepare()
        self._control_serial += 1
        scale = self.timeScale
        if self._hiding:
            self._count = 0
            self._publish(0)
        else:
            if trigger_events:
                if not self._dispatch_actions(float("inf"), scale):
                    return self
            self._count = len(self._characters)
            self._publish(self._count)
        self._advance_clock(self._completion_time, scale)
        self._action_index = len(self._actions)
        self._finish()
        return self

    def _finish(self):
        was_finished = self._finished
        self.playing = False
        self._finished = True
        callback = self.on_hidden if self._hiding else self.on_complete
        if not was_finished and callback is not None:
            callback()

    def Update(self, delta):
        if not self.playing:
            return self
        if not isfinite(delta) or delta < 0:
            raise ValueError("Typing delta must be finite and nonnegative")
        scale = self.timeScale
        clock = self._clock + delta * scale
        if not self._dispatch_actions(clock, scale):
            return self
        self._advance_clock(clock, scale)
        if clock >= self._completion_time:
            self._finish()
        return self
