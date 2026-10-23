"""Reveal native-layout graphemes without slicing or rewriting the text."""

from math import isfinite
from abc import ABC, abstractmethod
from typing import Callable, Self

from infernux.lib import TextLayout
from infernux.ui import UIText
from infernux.input import InputAction

from .events import ActionStatus, CharacterData, CharacterInfo, EventMarker, TypewriterAction, TypingInfo, WaitInputMode, WaitMode, _VisibilityState


class TypingTimings(ABC):
    by_word = False
    wait_for_last_character = False

    @abstractmethod
    def get_wait_appearance_time_of(self, character: CharacterData, animator: object) -> float:
        raise NotImplementedError

    def get_wait_disappearance_time_of(self, character: CharacterData, animator: object) -> float:
        return self.get_wait_appearance_time_of(character, animator)


class TypingDelaysByCharacter(TypingTimings):
    def __init__(self):
        self.wait_for_normal_chars = 1/30
        self.wait_middle = 0.15
        self.wait_long = 0.3
        self.wait_for_new_lines = True
        self.avoid_multiple_punctuation_wait = True
        self.skip_last_punctuation_wait = False
        self.enable_punctuation_whitelist = False
        self.punctuation_whitelist = [".", ",", "!", "?", ";", ":"]
        self.use_typewriter_wait_for_disappearances = True
        self.disappearance_speed_multiplier = 1.0

    def get_wait_appearance_time_of(self, character: CharacterData, animator: object) -> float:
        value = character.info.character
        if value in ('\r', '\n', '\r\n') and not self.wait_for_new_lines:
            return 0.0
        punctuation = value[-1:] in '.,!?;:，。！？；：…'
        if self.enable_punctuation_whitelist:
            punctuation = value in self.punctuation_whitelist
        if punctuation:
            if self.skip_last_punctuation_wait and character.index == len(animator.characters)-1:
                return 0.0
            previous = animator.characters[character.index-1].info.character if character.index else ''
            if self.avoid_multiple_punctuation_wait and previous[-1:] in '.,!?;:，。！？；：…':
                return self.wait_for_normal_chars
            return self.wait_long if value[-1:] in '.!?。！？…' else self.wait_middle
        return self.wait_for_normal_chars

    def get_wait_disappearance_time_of(self, character: CharacterData, animator: object) -> float:
        value = self.get_wait_appearance_time_of(character, animator) if self.use_typewriter_wait_for_disappearances else self.wait_for_normal_chars
        return value/self.disappearance_speed_multiplier


class TypingDelaysByWord(TypingTimings):
    by_word = True

    def __init__(self):
        self.wait_for_normal_word = 0.1
        self.wait_for_word_with_punctuation = 0.3
        self.disappearance_delay = 0.1

    def get_wait_appearance_time_of(self, character: CharacterData, animator: object) -> float:
        index = character.index
        info, characters = character.info.native, animator.characters
        if info.word is not None and index+1 < len(characters) and info.word == characters[index+1].info.native.word:
            return 0.0
        return self.wait_for_word_with_punctuation if character.info.character[-1:] in '.,!?;:，。！？；：…' else self.wait_for_normal_word

    def get_wait_disappearance_time_of(self, character: CharacterData, animator: object) -> float:
        return self.disappearance_delay if self.get_wait_appearance_time_of(character, animator) else 0.0


class Typewriter:
    def __init__(self, text: UIText, *, characters_per_second: float = 30.0, punctuation_pause: float = 0.15,
                 whitespace_pause: float = 0.0, by_word: bool = False):
        self.text = text
        self.characters_per_second = characters_per_second
        self.punctuation_pause = punctuation_pause
        self.whitespace_pause = whitespace_pause
        self.by_word = by_word
        self._time_scale = 1.0
        self._action_speed = 1.0
        self.trigger_events_on_skip = False
        self.input_mode = WaitInputMode.ANY_INPUT
        self.default_input_key = ""
        self.input_actions: dict[str, InputAction] = {}
        self._input_settings = self
        self._owner = self
        self.database: dict[str, TypewriterAction] = {}
        self._timing_settings = None
        self._timing_dirty = False
        self._character_wait_groups = {}
        self._custom_wait = None
        self._typing_info = TypingInfo(self, 0.0, 1.0)
        self.playing = False
        self.on_typewriter_start: Callable[[], None] | None = None
        self.on_character_visible: Callable[[CharacterData], None] | None = None
        self.on_character_hidden: Callable[[CharacterData], None] | None = None
        self.on_text_showed: Callable[[], None] | None = None
        self.on_text_disappeared: Callable[[], None] | None = None
        self.on_message: Callable[[EventMarker], None] | None = None
        self.on_character_wait_started: Callable[[CharacterData, WaitMode], None] | None = None
        self.on_character_wait_finished: Callable[[CharacterData, WaitMode], None] | None = None
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
        self._character_data = []
        self._whitespace = []
        self._triggered_events = set()
        self._waiting = None
        self._input_wait = None
        self._latest_character = None
        self._visibility_state = _VisibilityState()

    @property
    def characters(self) -> list[CharacterData]: return self._character_data

    @property
    def timing_settings(self) -> TypingTimings | None: return self._timing_settings

    @timing_settings.setter
    def timing_settings(self, value: TypingTimings | None) -> None:
        if value is not None and not isinstance(value, TypingTimings):
            raise TypeError("Timing settings must be a TypingTimings object")
        self._timing_settings = value
        self._timing_dirty = True

    def _interval(self, index, hiding=False):
        if self._timing_settings is not None:
            callback = (self._timing_settings.get_wait_disappearance_time_of if hiding
                        else self._timing_settings.get_wait_appearance_time_of)
            interval = callback(self._character_data[index], self._owner)
        else:
            interval = 1/self.characters_per_second
            if self._whitespace[index]:
                interval += self.whitespace_pause
            elif self._characters[index][-1:] in '.,!?;:，。！？；：…':
                interval += self.punctuation_pause
        if not isfinite(interval) or interval < 0:
            raise ValueError("Character wait must be finite and nonnegative")
        return interval

    def _prepare(self, hiding=False, *, start_character=0):
        speed = self.characters_per_second
        if not isinstance(self.by_word, bool) or any(isinstance(value, bool) for value in (speed, self.punctuation_pause, self.whitespace_pause)):
            raise TypeError("Typing mode must be a bool and timing values must be numbers")
        if not isfinite(speed) or speed <= 0:
            raise ValueError("Typing speed must be finite and positive")
        if any(not isfinite(v) or v < 0 for v in (self.punctuation_pause, self.whitespace_pause)):
            raise ValueError("Typing pauses must be finite and nonnegative")
        layout = self.text.get_text_layout()
        characters = layout.characters
        self._characters = TextLayout.split_graphemes(layout.display_text)
        self._visibility_state = _VisibilityState()
        visibility = self._visibility_state
        self._character_data = [CharacterData(index, CharacterInfo(value, info), visibility)
                                for index, (value, info) in enumerate(zip(self._characters, characters))]
        self._whitespace = [character.whitespace for character in characters]
        visible = self.text.max_visible_characters
        limit = min(visible, len(characters)) if hiding and visible >= 0 else len(characters)
        self.visible_limit = limit
        self._generation += 1
        self._control_serial += 1
        self._finished = False
        self._action_index = 0
        self._triggered_events.clear()
        self._waiting = self._input_wait = None
        self._action_speed = 1.0
        self._latest_character = None
        self._actions, self._completion_time, self._character_wait_groups = self._build_actions(limit, hiding, start_character)
        self._timing_dirty = False
        return limit

    def _build_actions(self, limit, hiding, start_character=0):
        characters = self.text.get_text_layout().characters
        cues, actions, character_waits = {}, [], {}
        for cue in self.cues:
            cues.setdefault(cue.character, []).append(cue)
        groups, start = [], start_character
        by_word = self._timing_settings.by_word if self._timing_settings is not None else self.by_word
        for index in range(start_character, limit):
            character = characters[index]
            if (by_word and index + 1 < limit and character.word is not None
                    and character.word == characters[index + 1].word and (hiding or index + 1 not in cues)):
                continue
            groups.append((start, index + 1))
            start = index + 1
        time = 0.0
        mode = WaitMode.DISAPPEARANCE if hiding else WaitMode.APPEARANCE

        def schedule_wait(index, start, end, group=None):
            if end > start and limit:
                data = self._character_data[min(index, limit-1)]
                if group is not None:
                    character_waits[len(actions)] = group
                actions.append((start, "wait_started", (data, mode, end)))
                actions.append((end, "wait_finished", (data, mode, end)))

        def schedule_cues(index, clock):
            for cue in cues.get(index, ()):
                if cue.kind == "wait":
                    schedule_wait(index, clock, clock+cue.value)
                    clock += cue.value
                elif cue.kind == "event":
                    actions.append((clock, "event", (index, cue.value)))
                elif cue.kind in ("speed", "input", "action"):
                    actions.append((clock, cue.kind, cue.value))
            return clock

        ordered = list(reversed(groups)) if hiding else groups
        finish = 0.0
        for group, (start, end) in enumerate(ordered):
            if not hiding:
                time = schedule_cues(start, time)
            group_time = time
            for index in range(start, end):
                actions.append((group_time, "hidden" if hiding else "character", (index, start if hiding else end)))
                time += self._interval(index, hiding)
            finish = group_time
            if group+1 < len(ordered):
                schedule_wait(end-1, group_time, time, (start, end))
        if self._timing_settings is not None and self._timing_settings.wait_for_last_character and ordered:
            schedule_wait(ordered[-1][1]-1, finish, time, ordered[-1])
            finish = time
        completion = schedule_cues(limit, finish) if not hiding else finish
        return actions, completion, character_waits

    def _rebuild_pending_timing(self):
        prefix = self._actions[:self._action_index]
        future, finish, waits = self._build_actions(self._count if self._hiding else len(self._characters), self._hiding,
                                                    0 if self._hiding else self._count)
        shifted = [(time+self._clock, kind, (*value[:2], value[2]+self._clock) if kind.startswith("wait_") else value)
                   for time, kind, value in future]
        self._actions = prefix+shifted
        self._completion_time = self._clock+finish
        self._character_wait_groups = {index: group for index, group in self._character_wait_groups.items() if index < len(prefix)}
        self._character_wait_groups.update({len(prefix)+index: group for index, group in waits.items()})
        self._timing_dirty = False

    def _cancel_action(self):
        serial = self._control_serial
        pending, self._custom_wait = self._custom_wait, None
        if pending is not None and pending[1] is not None:
            pending[1].cancel()
        return serial == self._control_serial

    def _advance_clock(self, clock, scale):
        self._playback_clock += (clock-self._clock)/scale
        self._clock = clock

    def _dispatch_actions(self, clock, scale, *, skip_waits=False):
        serial = self._control_serial
        base_scale = scale/self._action_speed
        while self._action_index < len(self._actions) and self._actions[self._action_index][0] <= clock:
            self.event_time, kind, value = self._actions[self._action_index]
            action = self._action_index
            self._advance_clock(self.event_time, scale)
            if kind == "action":
                if skip_waits:
                    self._action_index += 1
                    if not self._cancel_action():
                        return None
                    continue
                else:
                    if self._custom_wait is None:
                        pending = [action, None]
                        self._custom_wait = pending
                        generation = self._generation
                        state = self.database[value.name].create_action_from(value, self._owner)
                        if self._custom_wait is not pending or self._generation != generation:
                            state.cancel()
                            return None
                        pending[1] = state
                        if serial != self._control_serial:
                            return None
                    state = self._custom_wait[1]
                    self._typing_info.typewriter = self._owner
                    delta = max(0, clock-self._clock)
                    self._playback_clock += delta/scale
                    self._typing_info.time_passed, self._typing_info.speed = self._playback_clock, self.speed_multiplier
                    previous_speed = self._typing_info.speed
                    status = state.progress(delta, self._typing_info)
                    if self._custom_wait is None or self._custom_wait[1] is not state or serial != self._control_serial:
                        return None
                    if self._typing_info.speed != previous_speed:
                        self.speed_multiplier = self._typing_info.speed
                    if status is ActionStatus.RUNNING:
                        return None
                    if status is not ActionStatus.FINISHED:
                        raise TypeError("Action progress must return ActionStatus")
                    self._custom_wait = None
                    clock = self._clock
            if kind == "input" and not skip_waits:
                from infernux.input import Input
                if self._input_wait is None:
                    self._input_wait = (action, Input.frame_index)
                    return None
                if Input.frame_index <= self._input_wait[1] or not self._input_ready(value):
                    return None
            self._input_wait = None
            self._action_index += 1
            if kind == "event":
                if action not in self._triggered_events:
                    self._triggered_events.add(action)
                    if self.on_message is not None:
                        self.on_message(value[1])
            elif kind == "speed":
                remaining = (clock-self._clock)/scale
                self._action_speed = value
                scale = base_scale*value
                clock = self._clock+remaining*scale
            elif kind in ("input", "action"):
                pass
            elif kind.startswith("wait_"):
                data, mode, end = value
                started = kind == "wait_started"
                if started and action in self._character_wait_groups:
                    first, last = self._character_wait_groups[action]
                    end = self.event_time+sum(self._interval(index, self._hiding) for index in range(first, last))
                    shift = end-value[2]
                    if shift:
                        self._actions[action] = (self.event_time, kind, (data, mode, end))
                        for index in range(self._action_index, len(self._actions)):
                            time, following_kind, following_value = self._actions[index]
                            if following_kind.startswith("wait_"):
                                following_value = (*following_value[:2], following_value[2]+shift)
                            self._actions[index] = time+shift, following_kind, following_value
                        self._completion_time += shift
                self._waiting = end if started else None
                if not started and action-1 in self._character_wait_groups and self._timing_dirty:
                    self._rebuild_pending_timing()
                callback = self.on_character_wait_started if started else self.on_character_wait_finished
                if callback is not None:
                    callback(data, mode)
            else:
                index, count = value
                if count != self._count:
                    self._count = count
                    self._publish(count)
                callback = self.on_character_hidden if kind == "hidden" else self.on_character_visible
                if kind == "character":
                    self._latest_character = self._character_data[index]
                if callback is not None:
                    callback(self._character_data[index])
            if serial != self._control_serial:
                return None
        return clock, scale

    def _input_ready(self, key):
        from infernux.input import Input
        settings = self._input_settings
        if not isinstance(settings.input_mode, WaitInputMode):
            raise TypeError("Input mode must be a WaitInputMode member")
        if settings.input_mode is WaitInputMode.ANY_INPUT or key.lower() == "any":
            return Input.any_key_down or any(touch.began_this_frame for touch in Input.touches)
        return settings.input_actions[key or settings.default_input_key].was_pressed_this_frame

    @property
    def elapsed_time(self) -> float: return self._clock

    @property
    def playback_time(self) -> float: return self._playback_clock

    @property
    def speed_multiplier(self) -> float: return self._time_scale

    @speed_multiplier.setter
    def speed_multiplier(self, value: float) -> None:
        if isinstance(value, bool):
            raise TypeError("Typewriter speed multiplier must be a number")
        if not isfinite(value) or value < 0.001:
            raise ValueError("Typewriter speed multiplier must be finite and at least 0.001")
        self._time_scale = float(value)

    @property
    def trigger_events_on_skip(self) -> bool: return self._trigger_events_on_skip

    @trigger_events_on_skip.setter
    def trigger_events_on_skip(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise TypeError("Trigger events on skip must be a bool")
        self._trigger_events_on_skip = value

    @property
    def input_mode(self) -> WaitInputMode: return self._input_mode

    @input_mode.setter
    def input_mode(self, value: WaitInputMode) -> None:
        if not isinstance(value, WaitInputMode):
            raise TypeError("Input mode must be a WaitInputMode member")
        self._input_mode = value

    @property
    def hiding(self) -> bool: return self._hiding

    @property
    def is_showing_text(self) -> bool: return self.playing and not self._hiding

    @property
    def is_hiding_text(self) -> bool: return self.playing and self._hiding

    @property
    def is_waiting_for_action(self) -> bool: return self._waiting is not None or self._input_wait is not None or self._custom_wait is not None

    def _publish(self, count):
        self._visibility_state.count = count
        if self.visibility_handler is None:
            self.text.max_visible_characters = count
        else:
            self.visibility_handler(count, self._hiding)

    def show_text(self, text: str) -> None:
        if not isinstance(text, str):
            raise TypeError("Text must be a string")
        if not self._cancel_action():
            return
        self.text.text = text
        self._prepare()
        self._count, self._clock, self._playback_clock, self._hiding = 0, 0.0, 0.0, False
        self._publish(0)
        self.playing = True
        serial = self._control_serial
        if self.on_typewriter_start is not None:
            self.on_typewriter_start()
        if serial == self._control_serial:
            self.update(0.0)

    def start_showing_text(self, restart: bool = False) -> None:
        if not isinstance(restart, bool):
            raise TypeError("Restart must be a bool")
        if restart or self._hiding or self._completion_time is None:
            self.show_text(self.text.text)
            return
        self._resume()

    def _resume(self):
        if not self._finished:
            self._control_serial += 1
            self.playing = True

    def _append(self, old_count, visible, cues, old_cue_count, preserve):
        continuing = preserve and self._completion_time is not None and not self._hiding
        actions, cursor, clock, playback = self._actions, self._action_index, self._clock, self._playback_clock
        end, finished, waiting, input_wait, triggered = self._completion_time, self._finished, self._waiting, self._input_wait, self._triggered_events.copy()
        action_speed = self._action_speed
        custom_wait, character_waits = self._custom_wait, self._character_wait_groups
        if continuing:
            self._custom_wait = None
        elif not self._cancel_action():
            return
        latest = self._latest_character.index if self._latest_character is not None else None
        self.cues = cues[old_cue_count:] if continuing or not preserve else tuple(cue for cue in cues if cue.character >= visible)
        self._prepare(start_character=old_count if continuing or not preserve else visible)
        self._action_speed = action_speed
        self._latest_character = self._character_data[latest] if latest is not None else None
        self._count, self._hiding = visible, False
        self._visibility_state.count = visible
        self._clock = self._playback_clock = 0.0
        if continuing:
            bridge = 0.0
            if not finished and old_count and len(self._characters) > old_count:
                bridge = self._interval(old_count-1)
            shift = clock if finished else end+bridge
            prefix = [(time, kind, (self._character_data[value[0].index], *value[1:]) if kind.startswith("wait_") else value)
                      for time, kind, value in actions]
            if bridge:
                data = self._character_data[old_count-1]
                prefix += [(end, "wait_started", (data, WaitMode.APPEARANCE, shift)),
                           (shift, "wait_finished", (data, WaitMode.APPEARANCE, shift))]
            tail = [(time+shift, kind, (*value[:2], value[2]+shift) if kind.startswith("wait_") else value)
                    for time, kind, value in self._actions]
            self._actions, self._action_index = prefix+tail, cursor
            self._clock, self._playback_clock, self._waiting = clock, playback, waiting
            self._input_wait = input_wait
            self._custom_wait = custom_wait
            self._character_wait_groups = {**character_waits, **{len(prefix)+index: group for index, group in self._character_wait_groups.items()}}
            self._completion_time += shift
            self._triggered_events = triggered
        self._finished = self._action_index == len(self._actions)

    def _stop(self):
        self._control_serial += 1
        self.playing = False

    def stop_showing_text(self) -> None:
        if not self._hiding:
            self._stop()

    def stop_disappearing_text(self) -> None:
        if self._hiding:
            self._stop()

    def set_typewriter_speed(self, value: float) -> None:
        self.speed_multiplier = value

    def _cancel(self):
        self._stop()
        self._generation += 1
        self._completion_time = None
        self._finished = True
        self._waiting = self._input_wait = None
        self._actions = ()
        self._action_index = 0
        self._triggered_events.clear()
        return self._cancel_action()

    def _bind_text(self, visible):
        self._prepare()
        self._count = len(self._characters) if visible < 0 else min(visible, len(self._characters))
        self._visibility_state.count = self._count
        self._clock = self._playback_clock = 0.0
        self._hiding = self.playing = False
        self._completion_time = None
        self._finished = True
        self._latest_character = self._character_data[self._count-1] if self._count else None

    def start_disappearing_text(self) -> None:
        if not self._cancel_action():
            return
        latest = self._latest_character.index if self._latest_character is not None else None
        self._count = self._prepare(hiding=True)
        self._latest_character = self._character_data[latest] if latest is not None else None
        self._hiding, self._clock, self._playback_clock = True, 0.0, 0.0
        self.playing = True
        self.update(0.0)

    def skip_typewriter(self) -> None:
        if self._finished:
            return
        if self._completion_time is None:
            self._prepare()
        self._control_serial += 1
        scale = self.speed_multiplier*self._action_speed
        if self._hiding:
            self._count = 0
            self._publish(0)
        else:
            if self.trigger_events_on_skip:
                result = self._dispatch_actions(float("inf"), scale, skip_waits=True)
                if result is None:
                    return
                _, scale = result
            self._count = len(self._characters)
            self._latest_character = self._character_data[-1] if self._character_data else None
            self._publish(self._count)
        if not self._cancel_action():
            return
        self._advance_clock(self._completion_time, scale)
        self._action_index = len(self._actions)
        self._finish()

    def _trigger_events(self, visible_only):
        serial = self._control_serial
        for action, (_, kind, value) in enumerate(self._actions):
            if kind != "event" or action in self._triggered_events:
                continue
            character, marker = value
            if visible_only:
                state = self._visibility_state
                end = min(state.count, state.limit) if state.limit >= 0 else state.count
                in_range = character < len(self._character_data) and state(character)
                at_end = character == end and character > state.first and state(character-1)
                if not (in_range or at_end):
                    continue
            self._triggered_events.add(action)
            if self.on_message is not None:
                self.on_message(marker)
            if self._control_serial != serial:
                break

    def trigger_remaining_events(self) -> None:
        self._trigger_events(False)

    def trigger_visible_events(self) -> None:
        self._trigger_events(True)

    def skip_current_action(self) -> bool:
        if self._custom_wait is not None:
            self._control_serial += 1
            serial = self._control_serial
            self._action_index += 1
            self._cancel_action()
            if serial != self._control_serial:
                return True
            self.playing = True
            self.update(0.0)
            return True
        if self._input_wait is not None:
            self._control_serial += 1
            self._input_wait = None
            self._action_index += 1
            self.playing = True
            self.update(0.0)
            return True
        if self._waiting is None:
            return False
        self._control_serial += 1
        self._advance_clock(self._waiting, self.speed_multiplier*self._action_speed)
        self.playing = True
        self.update(0.0)
        return True

    def _approximate_duration(self, hiding):
        if self._timing_settings is not None:
            limit = self.text.max_visible_characters if hiding else -1
            count = min(limit, len(self._character_data)) if hiding and limit >= 0 else len(self._character_data)
            return sum(self._interval(index, hiding) for index in range(count))/self.speed_multiplier
        layout = self.text.get_text_layout()
        characters = layout.characters
        limit = self.text.max_visible_characters if hiding else -1
        characters = characters[:limit] if limit >= 0 else characters
        graphemes = TextLayout.split_graphemes(layout.display_text)
        interval = 0.0
        for index, character in enumerate(characters):
            interval += 1/self.characters_per_second
            if character.whitespace:
                interval += self.whitespace_pause
            elif graphemes[index][-1:] in ".,!?;:，。！？；：…":
                interval += self.punctuation_pause
        return interval/self.speed_multiplier

    def get_approximate_show_duration(self) -> float:
        return self._approximate_duration(False)

    def get_approximate_hide_duration(self) -> float:
        return self._approximate_duration(True)

    def _finish(self):
        was_finished = self._finished
        self.playing = False
        self._finished = True
        self._waiting = None
        self._input_wait = None
        callback = self.on_text_disappeared if self._hiding else self.on_text_showed
        if not was_finished and callback is not None:
            callback()

    def update(self, delta: float) -> Self:
        if not self.playing:
            return self
        if not isfinite(delta) or delta < 0:
            raise ValueError("Typing delta must be finite and nonnegative")
        scale = self.speed_multiplier*self._action_speed
        clock = self._clock + delta * scale
        presentation_start = self._playback_clock
        serial = self._control_serial
        result = self._dispatch_actions(clock, scale)
        if result is None:
            if serial == self._control_serial and (self._input_wait is not None or self._custom_wait is not None):
                self._playback_clock = max(self._playback_clock, presentation_start+delta)
            return self
        clock, scale = result
        self._advance_clock(clock, scale)
        if clock >= self._completion_time:
            self._finish()
        return self
