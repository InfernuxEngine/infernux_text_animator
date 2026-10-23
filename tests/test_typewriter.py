from types import SimpleNamespace

import pytest

from infernux_text_animator import Typewriter, parse_markup


def text_fixture(graphemes, word_ids=None):
    text = "".join(graphemes)
    characters, offset = [], 0
    for index, grapheme in enumerate(graphemes):
        end = offset + len(grapheme.encode("utf-8"))
        characters.append(SimpleNamespace(source_start=offset, source_end=end, whitespace=grapheme.isspace(),
                                          word=None if word_ids is None else word_ids[index]))
        offset = end
    layout = SimpleNamespace(text=text, display_text=text, characters=characters)
    return SimpleNamespace(text=text, max_visible_characters=-1, get_text_layout=lambda: layout)


def test_reveal_uses_native_grapheme_ranges_and_pause_resume():
    text = text_fixture(["e\u0301", " ", "👨‍👩‍👧", "中"])
    writer = Typewriter(text, characters_per_second=10)
    events = []
    writer.on_typewriter_start = lambda: events.append("start")
    writer.on_character_visible = lambda data: events.append(data.info.character)
    writer.on_text_showed = lambda: events.append("done")
    writer.show_text(writer.text.text)
    assert text.max_visible_characters == 1
    writer.update(0.1)
    writer.stop_showing_text()
    writer.update(9)
    assert text.max_visible_characters == 2
    writer.start_showing_text()
    writer.update(0.2)
    assert events == ["start", "e\u0301", " ", "👨‍👩‍👧", "中", "done"]
    writer.update(10)
    assert events.count("done") == 1


def test_punctuation_wait_skip_events_and_reverse_hiding():
    text = text_fixture(["A", ".", "B", "C"])
    writer = Typewriter(text, characters_per_second=10, punctuation_pause=0.5)
    events = []
    writer.on_character_visible = lambda data: events.append(data.info.character)
    writer.show_text(writer.text.text)
    writer.update(0.15)
    assert text.max_visible_characters == 2
    writer.update(0.4)
    assert text.max_visible_characters == 2
    writer.trigger_events_on_skip = True
    writer.skip_typewriter()
    assert events == ["A", ".", "B", "C"]
    writer.start_disappearing_text()
    assert text.max_visible_characters == 3
    writer.update(2)
    assert text.max_visible_characters == 0 and not writer.playing


def test_hiding_a_partially_visible_text_never_reveals_hidden_letters():
    text = text_fixture(list("Hello"))
    writer = Typewriter(text, characters_per_second=10)
    writer.show_text(writer.text.text)
    writer.update(0.1)
    assert text.max_visible_characters == 2
    writer.start_disappearing_text()
    assert text.max_visible_characters == 1
    writer.update(0.1)
    assert text.max_visible_characters == 0


def test_word_mode_and_empty_text_complete_once():
    text = text_fixture(list("Hi 世界"), [0, 0, None, 1, 1])
    writer = Typewriter(text, characters_per_second=10, by_word=True)
    writer.show_text(writer.text.text)
    assert text.max_visible_characters == 2
    writer.update(0.2)
    assert text.max_visible_characters == 3
    writer.update(0.11)
    assert text.max_visible_characters == 5
    empty = Typewriter(text_fixture([]))
    events = []
    empty.on_text_showed = lambda: events.append("complete")
    empty.show_text(empty.text.text)
    empty.update(0)
    assert events == ["complete"]


def test_word_hiding_uses_reversed_boundaries_and_partial_word():
    text = text_fixture(list("A longer"), [0, None, 1, 1, 1, 1, 1, 1])
    writer = Typewriter(text, characters_per_second=10, by_word=True)
    writer.start_disappearing_text()
    assert text.max_visible_characters == 2
    writer.update(0.59)
    assert text.max_visible_characters == 2
    writer.update(0.02)
    assert text.max_visible_characters == 1
    writer.update(0.11)
    assert text.max_visible_characters == 0 and not writer.playing
    text.max_visible_characters = 4
    writer.start_disappearing_text()
    assert text.max_visible_characters == 2
    writer.update(1)
    assert text.max_visible_characters == 0


def test_invalid_speed_is_reported_before_playback():
    with pytest.raises(ValueError, match="speed"):
        Typewriter(text_fixture(["A"]), characters_per_second=0).show_text("A")


def test_skip_does_not_replay_events_or_hide_text_when_resumed():
    text = text_fixture(list("Hello"))
    writer, completed = Typewriter(text), []
    writer.on_text_showed = lambda: completed.append(True)
    writer.show_text(writer.text.text)
    writer.skip_typewriter()
    writer.start_showing_text()
    writer.update(1)
    assert text.max_visible_characters == 5 and completed == [True]


@pytest.mark.parametrize("hiding", [False, True])
def test_skip_finishes_paused_playback_and_emits_completion_once(hiding):
    text = text_fixture(list("Hello"))
    writer, completed = Typewriter(text), []
    writer.show_text(writer.text.text)
    if hiding:
        writer.skip_typewriter()
        writer.start_disappearing_text()
    writer.on_text_showed = lambda: completed.append("shown")
    writer.on_text_disappeared = lambda: completed.append("hidden")
    writer.stop_disappearing_text() if hiding else writer.stop_showing_text()
    writer.skip_typewriter()
    assert text.max_visible_characters == (0 if hiding else 5)
    assert completed == ["hidden" if hiding else "shown"]
    writer.skip_typewriter()
    writer.update(1)
    assert len(completed) == 1
    if hiding:
        writer.start_showing_text()
        writer.update(1)
        assert completed == ["hidden", "shown"]


@pytest.mark.parametrize("skip", [False, True])
def test_first_start_or_skip_prepares_the_existing_text(skip):
    text, completed = text_fixture(list("Hello")), []
    writer = Typewriter(text, characters_per_second=10)
    writer.on_text_showed = lambda: completed.append(True)
    if skip:
        writer.skip_typewriter()
        assert text.max_visible_characters == 5 and completed == [True]
    else:
        writer.start_showing_text()
        assert text.max_visible_characters == 1 and not completed
    writer.update(1)
    writer.skip_typewriter()
    assert text.max_visible_characters == 5 and completed == [True]


def test_character_callbacks_use_display_graphemes_instead_of_markup_source():
    text = text_fixture(["A", "\n", "中", "e\u0301"])
    text.get_text_layout().text = "A<br>中<color=#ff0000>e\u0301</color>"
    events = []
    writer = Typewriter(text, characters_per_second=10)
    writer.on_character_visible = lambda data: events.append((data.index, data.info.character, writer._whitespace[data.index]))
    writer.show_text(writer.text.text)
    writer.update(1)
    assert events == [(0, "A", False), (1, "\n", True), (2, "中", False), (3, "e\u0301", False)]


def test_marker_pause_stops_the_current_frame_and_resume_keeps_the_remaining_wait():
    text = text_fixture(list("ABC"))
    writer, events = Typewriter(text, characters_per_second=10), []
    writer.cues = parse_markup('A<?pause><waitfor=0.5>BC').bind(text.get_text_layout())[1]
    writer.on_character_visible = lambda data: events.append((data.info.character, text.max_visible_characters))
    writer.on_text_showed = lambda: events.append("done")
    def pause(value):
        events.append((value.name, text.max_visible_characters))
        writer.stop_showing_text()
    writer.on_message = pause
    writer.show_text(writer.text.text)
    writer.update(1)
    assert events == [("A", 1), ("pause", 1)]
    assert writer.elapsed_time == pytest.approx(0.1) and not writer.playing
    writer.start_showing_text()
    writer.update(0.49)
    assert text.max_visible_characters == 1
    writer.update(0.12)
    assert events == [("A", 1), ("pause", 1), ("B", 2), ("C", 3), "done"]


def test_word_cues_split_reveal_groups_in_source_order_and_character_pause_keeps_callbacks():
    text = text_fixture(list("ABC"), [0, 0, 0])
    writer, events = Typewriter(text, characters_per_second=10, by_word=True), []
    writer.cues = parse_markup('A<?ding>BC').bind(text.get_text_layout())[1]
    writer.on_message = lambda marker: events.append(marker.name)
    def character(data):
        index, char = data.index, data.info.character
        events.append(char)
        if char == "B":
            writer.stop_showing_text()
    writer.on_character_visible = character
    writer.show_text(writer.text.text)
    writer.update(1)
    assert events == ["A", "ding", "B"] and text.max_visible_characters == 3
    writer.start_showing_text()
    writer.update(0)
    assert events == ["A", "ding", "B", "C"] and not writer.playing


def test_skip_can_finish_paused_typing_but_a_new_stop_in_a_marker_cancels_it():
    text = text_fixture(list("ABC"))
    writer, events = Typewriter(text, characters_per_second=10), []
    writer.cues = parse_markup('A<?pause>BC').bind(text.get_text_layout())[1]
    writer.on_character_visible = lambda data: events.append(data.info.character)
    writer.on_text_showed = lambda: events.append("done")
    writer.on_message = lambda value: writer.stop_showing_text()
    writer.show_text(writer.text.text)
    writer.stop_showing_text()
    writer.trigger_events_on_skip = True
    writer.skip_typewriter()
    assert events == ["A"] and text.max_visible_characters == 1
    assert not writer.playing and not writer._finished
    writer.trigger_events_on_skip = True
    writer.skip_typewriter()
    assert events == ["A", "B", "C", "done"] and text.max_visible_characters == 3
    writer.trigger_events_on_skip = True
    writer.skip_typewriter()
    assert events.count("done") == 1


@pytest.mark.parametrize("command", ["show", "hide", "skip"])
def test_callback_control_replaces_the_old_tick_without_stale_visibility_or_double_completion(command):
    text = text_fixture(list("ABC"))
    writer, completed = Typewriter(text, characters_per_second=10), []
    writer.on_text_showed = lambda: completed.append(True)
    def character(data):
        index, char = data.index, data.info.character
        if index != (2 if command == "skip" else 1):
            return
        writer.on_character_visible = None
        if command == "show":
            writer.show_text(writer.text.text)
        elif command == "hide":
            writer.start_disappearing_text()
        else:
            writer.trigger_events_on_skip = True
            writer.skip_typewriter()
    writer.on_character_visible = character
    writer.show_text(writer.text.text)
    writer.update(1)
    assert text.max_visible_characters == (3 if command == "skip" else 1)
    assert writer.elapsed_time == pytest.approx(0.2 if command == "skip" else 0)
    assert completed == ([True] if command == "skip" else [])


def test_public_control_signatures_return_none_and_have_no_legacy_aliases():
    from inspect import Parameter, isclass, isfunction, signature
    import infernux_text_animator as library
    from infernux_text_animator import CharacterData

    text = text_fixture(list("ABC"))
    writer, characters = Typewriter(text, characters_per_second=10), []
    writer.on_character_visible = characters.append
    assert signature(Typewriter.show_text).parameters["text"].default is Parameter.empty
    assert signature(Typewriter.start_showing_text).parameters["restart"].default is False
    assert tuple(signature(Typewriter.skip_typewriter).parameters) == ("self",)
    assert writer.show_text("ABC") is None
    assert isinstance(characters[0], CharacterData)
    assert characters[0].index == 0 and characters[0].info.character == "A"
    assert characters[0].info.native is text.get_text_layout().characters[0]
    assert writer.stop_showing_text() is None
    assert writer.set_typewriter_speed(2.0) is None
    assert writer.start_showing_text(False) is None
    writer.update(0.05)
    assert text.max_visible_characters == 2
    assert writer.start_showing_text(True) is None
    assert text.max_visible_characters == 1
    assert writer.skip_typewriter() is None
    assert writer.start_disappearing_text() is None
    assert writer.stop_disappearing_text() is None and not writer.is_hiding_text
    for name in ("ShowText", "SkipTypewriter", "timeScale", "on_character", "on_event"):
        assert not hasattr(writer, name)
    for name in library.__all__:
        cls = getattr(library, name)
        if isclass(cls):
            for method, value in vars(cls).items():
                if not method.startswith("_") and (isfunction(value) or isinstance(value, property)):
                    assert method == method.lower()
    for call in (lambda: writer.show_text(), lambda: writer.show_text(123),
                 lambda: writer.start_showing_text("false"), lambda: writer.skip_typewriter(True),
                 lambda: writer.set_typewriter_speed(True)):
        with pytest.raises(TypeError):
            call()


def test_marker_records_preserve_string_parameters_and_explicit_dispatch_does_not_reveal_characters():
    from infernux_text_animator import EventMarker

    text = text_fixture(list("AB"))
    writer, messages, characters = Typewriter(text), [], []
    writer.cues = parse_markup("A<?purchase=1,ALPHA>B<?end>").bind(text.get_text_layout())[1]
    writer.on_message = messages.append
    writer.on_character_visible = characters.append
    writer.show_text("AB")
    assert writer.trigger_visible_events() is None
    assert messages == [EventMarker("purchase", ["1", "ALPHA"])]
    assert len(characters) == text.max_visible_characters == 1
    assert writer.trigger_remaining_events() is None
    assert messages == [EventMarker("purchase", ["1", "ALPHA"]), EventMarker("end", [])]
    with pytest.raises(TypeError):
        EventMarker("purchase", [1])
    assert parse_markup("A<?奖励=10,金币>中").cues[0][2] == EventMarker("奖励", ["10", "金币"])
    writer.update(1)
    writer.trigger_remaining_events()
    assert len(messages) == len(characters) == 2
    parsed = parse_markup("<event=old/><wait=1/>")
    assert parsed.text == "<event=old/><wait=1/>" and not parsed.cues


def test_typed_wait_callbacks_pause_at_the_boundary_and_skip_only_the_current_wait():
    from infernux_text_animator import WaitMode

    text = text_fixture(list("AB"))
    writer, events = Typewriter(text, characters_per_second=10), []
    writer.cues = parse_markup("A<waitfor=2>B").bind(text.get_text_layout())[1]
    assert writer.get_approximate_show_duration() == writer.get_approximate_hide_duration() == pytest.approx(0.2)
    def wait_started(data, mode):
        events.append(("start", data, mode))
        writer.stop_showing_text()
    writer.on_character_wait_started = wait_started
    writer.on_character_wait_finished = lambda data, mode: events.append(("finish", data, mode))
    writer.show_text("AB")
    assert writer.get_approximate_hide_duration() == pytest.approx(0.1)
    assert writer.elapsed_time == 0 and writer.is_waiting_for_action and not writer.playing
    assert events[0][1] is writer._character_data[0] and events[0][2] is WaitMode.APPEARANCE
    assert writer.skip_current_action() is True
    assert writer.elapsed_time == pytest.approx(0.1) and text.max_visible_characters == 1
    assert [event[0] for event in events] == ["start", "finish", "start"]
    writer.on_character_wait_started = None
    assert writer.skip_current_action() is True
    assert text.max_visible_characters == 2 and not writer.playing
    assert [event[0] for event in events] == ["start", "finish", "start", "finish"]
    assert writer.skip_current_action() is False
    writer.on_character_wait_started = wait_started
    writer.start_disappearing_text()
    assert writer.stop_showing_text() is None and writer.playing
    writer.update(0)
    assert events[-1][2] is WaitMode.DISAPPEARANCE


def test_inline_speed_splits_a_long_frame_without_mutating_the_saved_multiplier():
    text = text_fixture(list('ABCD'))
    writer = Typewriter(text, characters_per_second=10)
    writer.cues = parse_markup('A<speed=2>B<speed=0.5>C<?event>D').bind(text.get_text_layout())[1]
    shown, markers = [], []
    writer.on_character_visible = lambda data: shown.append((data.info.character, writer.playback_time))
    writer.on_message = lambda data: markers.append(data.name)
    writer.show_text(text.text)
    writer.update(0.2)
    assert [value[0] for value in shown] == ['A', 'B', 'C'] and markers == []
    assert [value[1] for value in shown] == pytest.approx([0, 0.1, 0.15])
    assert writer.elapsed_time == pytest.approx(0.225)
    assert writer.playback_time == pytest.approx(0.2) and writer.speed_multiplier == 1
    writer.set_typewriter_speed(2)
    writer.update(0.1)
    assert shown[-1] == ('D', pytest.approx(0.275))
    assert markers == ['event']
    shown.clear()
    writer.show_text(text.text)
    writer.trigger_events_on_skip = True
    writer.skip_typewriter()
    assert [value[1] for value in shown] == pytest.approx([0, 0.05, 0.075, 0.175])
    assert not writer.playing and writer.speed_multiplier == 2


def test_waitinput_uses_new_native_frames_named_actions_and_skip_controls(monkeypatch):
    import infernux.input as input_module
    import infernux.input.actions as actions_module
    from infernux.input import InputAction
    from infernux_text_animator import WaitInputMode

    input_state = SimpleNamespace(frame_index=10, any_key_down=True, touches=[],
                                  _accepts_game_input=lambda: True)
    monkeypatch.setattr(input_module, 'Input', input_state)
    monkeypatch.setattr(actions_module, 'Input', input_state)
    action = InputAction('Confirm')
    text = text_fixture(list('ABCD'))
    writer = Typewriter(text, characters_per_second=10)
    writer.input_mode = WaitInputMode.SPECIFIC_ACTION
    writer.input_actions['confirm'] = action
    writer.default_input_key = 'confirm'
    writer.cues = parse_markup('A<waitinput=any>B<waitinput=confirm>C<waitinput>D').bind(text.get_text_layout())[1]
    writer.show_text(text.text)
    writer.update(0.2)
    assert text.max_visible_characters == 1 and writer.is_waiting_for_action
    writer.update(1)
    assert text.max_visible_characters == 1 and writer.elapsed_time == pytest.approx(0.1)
    assert writer.playback_time == pytest.approx(1.2)
    input_state.frame_index += 1
    writer.update(0.1)
    assert text.max_visible_characters == 2 and writer.is_waiting_for_action
    input_state.frame_index += 1
    input_state.any_key_down = False
    writer.update(0.1)
    assert text.max_visible_characters == 2
    input_state.frame_index += 1
    action.set_virtual_value('test', 1)
    writer.update(0.1)
    assert text.max_visible_characters == 3 and writer.is_waiting_for_action
    assert writer.skip_current_action() is True
    assert text.max_visible_characters == 4 and not writer.playing
    assert writer.skip_current_action() is False
    writer.show_text(text.text)
    writer.update(0.1)
    writer.stop_showing_text()
    writer.trigger_events_on_skip = True
    writer.skip_typewriter()
    assert text.max_visible_characters == 4 and not writer.is_waiting_for_action
    with pytest.raises(TypeError):
        writer.input_mode = 'any'
