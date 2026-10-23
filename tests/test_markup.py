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
        (EffectKind.SHAKE, 1, 2), (EffectKind.WAVE, 0, 2)]
    assert effects[0].seed == 7 and effects[1].amplitude == 2


def test_marker_and_wait_order_survive_skip_without_duplicate_callbacks():
    from test_typewriter import text_fixture

    parsed = parse_markup('A<?bell><waitfor=0.5>中<?end>')
    text = text_fixture(['A', '中'])
    _, cues = parsed.bind(text.get_text_layout())
    writer, events = Typewriter(text, characters_per_second=10), []
    writer.cues = cues
    writer.on_message = lambda marker: events.append(marker.name)
    writer.on_character_visible = lambda data: events.append(data.info.character)
    writer.show_text(writer.text.text)
    writer.update(0.4)
    assert text.max_visible_characters == 1 and events == ['A', 'bell']
    writer.update(0.21)
    assert events == ['A', 'bell', '中', 'end']
    writer.update(10)
    assert events == ['A', 'bell', '中', 'end']
    events.clear()
    writer.show_text(writer.text.text)
    writer.trigger_events_on_skip = False
    writer.skip_typewriter()
    assert events == ['A']
    events.clear()
    writer.show_text(writer.text.text)
    writer.trigger_events_on_skip = True
    writer.skip_typewriter()
    assert events == ['A', 'bell', '中', 'end']


def test_invalid_effect_tags_fail_at_compile_time():
    for source in ('<wave><shake>x</wave></shake>', '<wave unknown=3>x</wave>', '<waitfor=-1>', '{fade s=0}x'):
        with pytest.raises(ValueError):
            parse_markup(source)


def test_official_open_ended_close_all_noparse_and_separate_appearance_categories():
    from infernux_text_animator import AppearanceKind
    from test_typewriter import text_fixture

    parsed = parse_markup('<wave a=2 s=0.5>A<shake>B</>C{fade a=0.5 s=2}中{incr}D{/}{#slideh}E{/#}')
    assert parsed.text == 'ABC中DE'
    layout = text_fixture(list(parsed.text)).get_text_layout()
    effects, cues = parsed.bind(layout)
    assert not cues
    assert [(value.kind, value.start, value.end) for value in effects] == [(EffectKind.SHAKE, 1, 2), (EffectKind.WAVE, 0, 2)]
    assert effects[1].amplitude == 2 and effects[1].speed == 0.5
    modified = parse_markup('<wave a*3 a*2 s*0.5 once>Hi</wave>').ranges[0][2]
    assert modified.amplitude == 16 and modified.speed == 0.5 and modified.once
    entering, exiting = parsed.bind_appearance_tags(layout)
    assert [(value.kind, value.start, value.end) for value in entering] == [(AppearanceKind.SCALE, 4, 5), (AppearanceKind.FADE, 3, 5)]
    assert entering[1].amplitude == 0.5 and entering[1].speed == 2
    assert [(value.kind, value.start, value.end) for value in exiting] == [(AppearanceKind.SLIDE, 5, 6)]
    assert parse_markup('<wave>中文').ranges[0][:2] == (0, 6)
    raw = '<noparse><wave><?literal><waitfor=2>{fade}<color=red>中</color></noparse>'
    parsed = parse_markup(raw+'<wave>尾')
    assert parsed.text == raw+'尾' and not parsed.cues and not parsed.appearance_ranges
    assert parsed.ranges[0][:2] == (len(raw.encode()), len((raw+'尾').encode()))
    for name in ('wave', 'shake', 'wiggle', 'fade', 'incr', 'slideh', 'rot'):
        parsed = parse_markup(f'<{name}>A</>{{{name}}}B{{/}}{{#{name}}}中{{/#}}')
        assert parsed.text == 'AB中'
        assert len(parsed.ranges) == 1 and len(parsed.appearance_ranges) == 2
    from infernux_text_animator.events import TextStyle
    style = {'emphasis': TextStyle('<wave><?begin>', '</wave><?end>')}
    parsed = parse_markup('<EMPHASIS>中</emphasis><noparse><emphasis></noparse>', style_sheet=style)
    assert parsed.text == '中<noparse><emphasis></noparse>'
    assert [value.name for _, _, value in parsed.cues] == ['begin', 'end']
    with pytest.raises(ValueError, match='Recursive'):
        parse_markup('<a>text', style_sheet={'a': TextStyle('<a>')})


def test_same_position_markers_follow_source_order_and_trailing_wait_delays_completion():
    from test_typewriter import text_fixture
    parsed = parse_markup('A<?z><waitfor=0.5><?a>')
    text = text_fixture(['A'])
    writer, events = Typewriter(text), []
    writer.cues = parsed.bind(text.get_text_layout())[1]
    writer.on_message = lambda marker: events.append(marker.name)
    writer.on_text_showed = lambda: events.append('done')
    writer.show_text(writer.text.text)
    assert writer.playing and events == ['z']
    writer.update(0.5)
    assert not writer.playing and events == ['z', 'a', 'done']
