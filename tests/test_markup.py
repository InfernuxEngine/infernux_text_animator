from types import SimpleNamespace

import pytest

from infernux_text_animator import EffectKind, Typewriter, parse_markup


def test_nested_tags_preserve_native_rich_text_and_bind_utf8_graphemes():
    source = '<wave amplitude=2><color=#ff0000>é</color><shake seed=7>中</shake></wave>'
    parsed = parse_markup(source)
    assert parsed.text == '<color=#ff0000>é</color>中'
    encoded = parsed.text.encode("utf-8")
    first = encoded.index('é'.encode())
    last = encoded.index('中'.encode())
    layout = SimpleNamespace(characters=[SimpleNamespace(source_start=first, source_end=first+3),
                                         SimpleNamespace(source_start=last, source_end=last+3)])
    effects, _ = parsed.bind(layout)
    assert [(effect.kind, effect.start, effect.end) for effect in effects] == [
        (EffectKind.Shake, 1, 2), (EffectKind.Wave, 0, 2)]
    assert effects[0].seed == 7 and effects[1].amplitude == 2


def test_marker_and_wait_order_survive_skip_without_duplicate_callbacks():
    from test_typewriter import text_fixture

    parsed = parse_markup('A<event=bell/><wait=0.5/>中<event=end/>')
    text = text_fixture(['A', '中'])
    _, cues = parsed.bind(text.get_text_layout())
    writer, events = Typewriter(text, characters_per_second=10), []
    writer.cues, writer.on_event = cues, events.append
    writer.on_character = lambda index, char: events.append(char)
    writer.ShowText().Update(0.4)
    assert text.max_visible_characters == 1 and events == ['A', 'bell']
    writer.Update(0.21)
    assert events == ['A', 'bell', '中', 'end']
    writer.Update(10)
    assert events == ['A', 'bell', '中', 'end']
    events.clear()
    writer.ShowText().SkipTypewriter(trigger_events=False)
    assert events == ['A']
    events.clear()
    writer.ShowText().SkipTypewriter(trigger_events=True)
    assert events == ['A', 'bell', '中', 'end']


def test_invalid_effect_tags_fail_at_compile_time():
    for source in ('<wave><shake>x</wave></shake>', '<wave unknown=3>x</wave>', '<wait=-1/>', '<wave>x'):
        with pytest.raises(ValueError):
            parse_markup(source)


def test_same_position_markers_follow_source_order_and_trailing_wait_delays_completion():
    from test_typewriter import text_fixture
    parsed = parse_markup('A<event=z/><wait=0.5/><event=a/>')
    text = text_fixture(['A'])
    writer, events = Typewriter(text), []
    writer.cues = parsed.bind(text.get_text_layout())[1]
    writer.on_event = events.append
    writer.on_complete = lambda: events.append('done')
    writer.ShowText()
    assert writer.playing and events == ['z']
    writer.Update(0.5)
    assert not writer.playing and events == ['z', 'a', 'done']
