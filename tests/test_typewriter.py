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
    writer.on_start = lambda: events.append("start")
    writer.on_character = lambda index, value: events.append(value)
    writer.on_complete = lambda: events.append("done")
    writer.ShowText()
    assert text.max_visible_characters == 1
    writer.Update(0.1)
    writer.StopShowingText().Update(9)
    assert text.max_visible_characters == 2
    writer.StartShowingText().Update(0.2)
    assert events == ["start", "e\u0301", " ", "👨‍👩‍👧", "中", "done"]
    writer.Update(10)
    assert events.count("done") == 1


def test_punctuation_wait_skip_events_and_reverse_hiding():
    text = text_fixture(["A", ".", "B", "C"])
    writer = Typewriter(text, characters_per_second=10, punctuation_pause=0.5)
    events = []
    writer.on_character = lambda index, value: events.append(value)
    writer.ShowText().Update(0.15)
    assert text.max_visible_characters == 2
    writer.Update(0.4)
    assert text.max_visible_characters == 2
    writer.SkipTypewriter(trigger_events=True)
    assert events == ["A", ".", "B", "C"]
    writer.StartDisappearingText()
    assert text.max_visible_characters == 3
    writer.Update(2)
    assert text.max_visible_characters == 0 and not writer.playing


def test_hiding_a_partially_visible_text_never_reveals_hidden_letters():
    text = text_fixture(list("Hello"))
    writer = Typewriter(text, characters_per_second=10)
    writer.ShowText().Update(0.1)
    assert text.max_visible_characters == 2
    writer.StartDisappearingText()
    assert text.max_visible_characters == 1
    writer.Update(0.1)
    assert text.max_visible_characters == 0


def test_word_mode_and_empty_text_complete_once():
    text = text_fixture(list("Hi 世界"), [0, 0, None, 1, 1])
    writer = Typewriter(text, characters_per_second=10, by_word=True)
    writer.ShowText()
    assert text.max_visible_characters == 2
    writer.Update(0.2)
    assert text.max_visible_characters == 3
    writer.Update(0.11)
    assert text.max_visible_characters == 5
    empty = Typewriter(text_fixture([]))
    events = []
    empty.on_complete = lambda: events.append("complete")
    empty.ShowText().Update(0)
    assert events == ["complete"]


def test_word_hiding_uses_reversed_boundaries_and_partial_word():
    text = text_fixture(list("A longer"), [0, None, 1, 1, 1, 1, 1, 1])
    writer = Typewriter(text, characters_per_second=10, by_word=True)
    writer.StartDisappearingText()
    assert text.max_visible_characters == 2
    writer.Update(0.59)
    assert text.max_visible_characters == 2
    writer.Update(0.02)
    assert text.max_visible_characters == 1
    writer.Update(0.11)
    assert text.max_visible_characters == 0 and not writer.playing
    text.max_visible_characters = 4
    writer.StartDisappearingText()
    assert text.max_visible_characters == 2
    writer.Update(1)
    assert text.max_visible_characters == 0


def test_invalid_speed_is_reported_before_playback():
    with pytest.raises(ValueError, match="speed"):
        Typewriter(text_fixture(["A"]), characters_per_second=0).ShowText()


def test_skip_does_not_replay_events_or_hide_text_when_resumed():
    text = text_fixture(list("Hello"))
    writer, completed = Typewriter(text), []
    writer.on_complete = lambda: completed.append(True)
    writer.ShowText().SkipTypewriter().StartShowingText().Update(1)
    assert text.max_visible_characters == 5 and completed == [True]


@pytest.mark.parametrize("hiding", [False, True])
def test_skip_finishes_paused_playback_and_emits_completion_once(hiding):
    text = text_fixture(list("Hello"))
    writer, completed = Typewriter(text), []
    writer.ShowText()
    if hiding:
        writer.SkipTypewriter().StartDisappearingText()
    writer.on_complete = lambda: completed.append("shown")
    writer.on_hidden = lambda: completed.append("hidden")
    writer.StopShowingText().SkipTypewriter()
    assert text.max_visible_characters == (0 if hiding else 5)
    assert completed == ["hidden" if hiding else "shown"]
    writer.SkipTypewriter().StartShowingText().Update(1)
    assert len(completed) == 1


@pytest.mark.parametrize("skip", [False, True])
def test_first_start_or_skip_prepares_the_existing_text(skip):
    text, completed = text_fixture(list("Hello")), []
    writer = Typewriter(text, characters_per_second=10)
    writer.on_complete = lambda: completed.append(True)
    if skip:
        writer.SkipTypewriter()
        assert text.max_visible_characters == 5 and completed == [True]
    else:
        writer.StartShowingText()
        assert text.max_visible_characters == 1 and not completed
    writer.Update(1).SkipTypewriter()
    assert text.max_visible_characters == 5 and completed == [True]


def test_character_callbacks_use_display_graphemes_instead_of_markup_source():
    text = text_fixture(["A", "\n", "中", "e\u0301"])
    text.get_text_layout().text = "A<br>中<color=#ff0000>e\u0301</color>"
    events = []
    writer = Typewriter(text, characters_per_second=10)
    writer.on_character = lambda index, char: events.append((index, char, writer._whitespace[index]))
    writer.ShowText().Update(1)
    assert events == [(0, "A", False), (1, "\n", True), (2, "中", False), (3, "e\u0301", False)]


def test_marker_pause_stops_the_current_frame_and_resume_keeps_the_remaining_wait():
    text = text_fixture(list("ABC"))
    writer, events = Typewriter(text, characters_per_second=10), []
    writer.cues = parse_markup('A<event=pause/><wait=0.5/>BC').bind(text.get_text_layout())[1]
    writer.on_character = lambda index, char: events.append((char, text.max_visible_characters))
    writer.on_complete = lambda: events.append("done")
    def pause(value):
        events.append((value, text.max_visible_characters))
        writer.StopShowingText()
    writer.on_event = pause
    writer.ShowText().Update(1)
    assert events == [("A", 1), ("pause", 1)]
    assert writer.elapsed_time == pytest.approx(0.1) and not writer.playing
    writer.StartShowingText().Update(0.49)
    assert text.max_visible_characters == 1
    writer.Update(0.12)
    assert events == [("A", 1), ("pause", 1), ("B", 2), ("C", 3), "done"]


def test_word_cues_split_reveal_groups_in_source_order_and_character_pause_keeps_callbacks():
    text = text_fixture(list("ABC"), [0, 0, 0])
    writer, events = Typewriter(text, characters_per_second=10, by_word=True), []
    writer.cues = parse_markup('A<event=ding/>BC').bind(text.get_text_layout())[1]
    writer.on_event = events.append
    def character(index, char):
        events.append(char)
        if char == "B":
            writer.StopShowingText()
    writer.on_character = character
    writer.ShowText().Update(1)
    assert events == ["A", "ding", "B"] and text.max_visible_characters == 3
    writer.StartShowingText().Update(0)
    assert events == ["A", "ding", "B", "C"] and not writer.playing


def test_skip_can_finish_paused_typing_but_a_new_stop_in_a_marker_cancels_it():
    text = text_fixture(list("ABC"))
    writer, events = Typewriter(text, characters_per_second=10), []
    writer.cues = parse_markup('A<event=pause/>BC').bind(text.get_text_layout())[1]
    writer.on_character = lambda index, char: events.append(char)
    writer.on_complete = lambda: events.append("done")
    writer.on_event = lambda value: writer.StopShowingText()
    writer.ShowText().StopShowingText().SkipTypewriter(True)
    assert events == ["A"] and text.max_visible_characters == 1
    assert not writer.playing and not writer._finished
    writer.SkipTypewriter(True)
    assert events == ["A", "B", "C", "done"] and text.max_visible_characters == 3
    writer.SkipTypewriter(True)
    assert events.count("done") == 1


@pytest.mark.parametrize("command", ["show", "hide", "skip"])
def test_callback_control_replaces_the_old_tick_without_stale_visibility_or_double_completion(command):
    text = text_fixture(list("ABC"))
    writer, completed = Typewriter(text, characters_per_second=10), []
    writer.on_complete = lambda: completed.append(True)
    def character(index, char):
        if index != (2 if command == "skip" else 1):
            return
        writer.on_character = None
        if command == "show":
            writer.ShowText()
        elif command == "hide":
            writer.StartDisappearingText()
        else:
            writer.SkipTypewriter(True)
    writer.on_character = character
    writer.ShowText().Update(1)
    assert text.max_visible_characters == (3 if command == "skip" else 1)
    assert writer.elapsed_time == pytest.approx(0.2 if command == "skip" else 0)
    assert completed == ([True] if command == "skip" else [])
