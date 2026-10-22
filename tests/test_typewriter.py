from types import SimpleNamespace

import pytest

from infernux_text_animator import Typewriter


def text_fixture(graphemes, word_ids=None):
    text = "".join(graphemes)
    characters, offset = [], 0
    for index, grapheme in enumerate(graphemes):
        end = offset + len(grapheme.encode("utf-8"))
        characters.append(SimpleNamespace(source_start=offset, source_end=end, whitespace=grapheme.isspace(),
                                          word=None if word_ids is None else word_ids[index]))
        offset = end
    layout = SimpleNamespace(text=text, characters=characters)
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
    assert text.max_visible_characters == 5
    empty = Typewriter(text_fixture([]))
    events = []
    empty.on_complete = lambda: events.append("complete")
    empty.ShowText().Update(0)
    assert events == ["complete"]


def test_invalid_speed_is_reported_before_playback():
    with pytest.raises(ValueError, match="speed"):
        Typewriter(text_fixture(["A"]), characters_per_second=0).ShowText()
