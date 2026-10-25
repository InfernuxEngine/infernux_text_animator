from types import SimpleNamespace

import pytest

from TextAnimator import TextAnimator
from infernux_text_animator.playback import PlaybackScheduler


@pytest.fixture
def component(monkeypatch):
    from test_characters import text_buffer
    from test_typewriter import text_fixture
    import TextAnimator as module

    text, _ = text_buffer()
    text.text, text.rich_text = 'A中BC', False
    text.font_size = 18.0
    text.get_text_layout = text_fixture(list(text.text)).get_text_layout
    scheduler = PlaybackScheduler()
    monkeypatch.setattr(module, 'scheduler', scheduler)
    monkeypatch.setattr(module, 'SceneManager', SimpleNamespace(instance=lambda: SimpleNamespace(is_playing=lambda: True)))
    monkeypatch.setattr(TextAnimator, 'game_object', property(lambda _: SimpleNamespace(get_component=lambda _kind: text)))
    animator = TextAnimator()
    animator.typewriter = animator.animate_appearance = True
    animator.characters_per_second = 10
    animator.appearance.duration = 0.2
    animator.disappearance.duration = 0.2
    yield animator, text, scheduler
    scheduler.clear()
    animator.on_disable()


def test_typing_appearance_pause_and_reverse_keep_exiting_glyphs_until_they_finish(component):
    animator, text, scheduler = component
    hidden = []
    animator.on_text_disappeared.add_listener(lambda: hidden.append(True))
    animator.on_enable()
    assert text.max_visible_characters == 1
    scheduler.update(0.15, 0.15)
    alpha = animator._appearance.buffer.colors[0, 0, 3]
    assert 0 < alpha < 1
    animator.pause_animation()
    assert not scheduler._active
    animator.resume_animation()
    scheduler.update(0.5, 0.5)
    assert not animator._writer.playing and not animator._appearance.active
    animator.start_disappearing_text()
    assert text.max_visible_characters == 4
    scheduler.update(0.31, 0.31)
    assert text.max_visible_characters == 4 and not hidden
    scheduler.update(0.21, 0.21)
    assert text.max_visible_characters == 0 and hidden == [True]
    assert not scheduler._active
    visual = []
    animator.on_visual_complete.add_listener(lambda: visual.append(True))
    animator.show_text(animator._animation.source_text)
    animator.skip_typewriter()
    animator.start_disappearing_text()
    scheduler.update(0.31, 0.31)
    assert animator._hidden_pending and animator._appearance.active
    visual.clear()
    animator.disappearance.duration = 0
    animator.on_validate()
    assert hidden == [True, True] and visual == [True]
    assert not animator._hidden_pending and not scheduler._active
    animator.on_validate()
    assert hidden == [True, True] and visual == [True]
    animator.appearance.duration = 0
    animator.on_validate()
    animator.play_appearance()
    animator.play_appearance(False)
    assert visual == [True, True, True] and not scheduler._active


def test_character_callback_can_disable_the_component_without_stale_work(component):
    animator, text, scheduler = component
    animator.on_character_visible.add_listener(lambda data: animator.on_disable() if data.index == 1 else None)
    animator.on_enable()
    scheduler.update(0.15, 0.15)
    assert animator._animation is animator._writer is None
    assert not scheduler._active and text.max_visible_characters == 2


def test_manual_play_starts_a_component_with_auto_play_disabled(component):
    animator, text, scheduler = component
    animator.auto_play = False
    animator.on_enable()
    assert not scheduler._active and text.max_visible_characters == 2
    animator.resume_animation()
    assert scheduler._active and text.max_visible_characters == 1


def test_edit_mode_enable_keeps_authored_text_and_registers_no_playback(component, monkeypatch):
    import TextAnimator as module
    animator, text, scheduler = component
    monkeypatch.setattr(module, 'SceneManager', SimpleNamespace(instance=lambda: SimpleNamespace(is_playing=lambda: False)))
    animator.on_enable()
    assert animator._animation is None and not scheduler._active
    assert text.text == 'A中BC' and text.max_visible_characters == 2


def test_live_appearance_edit_preserves_typing_phase_and_pause(component):
    animator, text, scheduler = component
    animator.on_enable()
    scheduler.update(0.15, 0.15)
    appearance = animator._appearance
    alpha = appearance.buffer.colors[:, :, 3].copy()
    animator.pause_animation()
    animator.appearance.rotation = 20
    animator.appearance.duration = 0.4
    animator.on_validate()
    assert animator._appearance is appearance
    assert appearance.buffer.colors[:, :, 3] == pytest.approx(alpha)
    assert text.max_visible_characters == 2 and not scheduler._active
    assert appearance.active
    animator.resume_animation()
    scheduler.update(0.05, 0.05)
    assert appearance.buffer.colors[1, 0, 3] > alpha[1, 0]


def test_removing_the_last_effect_clears_its_geometry_before_unscheduling(component):
    import numpy as np
    from TextAnimator import TextEffect
    animator, text, scheduler = component
    animator.typewriter = animator.animate_appearance = False
    animator.effects = [TextEffect()]
    animator.on_enable()
    scheduler.update(0.15, 0.15)
    assert np.any(animator._animation._buffer.offsets != 0)
    animator.effects.clear()
    animator.on_validate()
    assert np.all(animator._animation._buffer.offsets == 0)
    assert not animator._animation.has_effects and not scheduler._active
    animator.effects = [TextEffect(once=True, speed=2)]
    animator.on_validate()
    assert animator._animation.has_active_effects and scheduler._active
    scheduler.update(0.6, 0.6)
    assert np.all(animator._animation._buffer.offsets == 0)
    assert animator._animation.has_effects and not animator._animation.has_active_effects and not scheduler._active
    animator.show_text(animator._animation.source_text)
    assert animator._animation.has_active_effects and scheduler._active


def test_character_audio_uses_native_whitespace_metadata(component):
    animator, text, scheduler = component
    animator.on_enable()
    played = []
    animator._sound = SimpleNamespace(play=lambda: played.append(True))
    animator._writer._whitespace[1] = True
    animator._character_shown(animator._writer._character_data[1])
    animator._character_shown(animator._writer._character_data[2])
    assert played == [True]


@pytest.mark.parametrize("initial_marker", [False, True])
def test_first_callback_pause_survives_startup_and_play_resumes_without_replaying(component, initial_marker):
    animator, text, scheduler = component
    events = []
    if initial_marker:
        text.text = '<?pause>A中BC'
        animator.on_message.add_listener(lambda value: (events.append(value.name), animator.pause_animation()))
    else:
        animator.on_character_visible.add_listener(lambda data: (events.append(data.info.character), animator.pause_animation()) if data.index == 0 else None)
    animator.on_enable()
    assert not animator._playing and not animator._writer.playing and not scheduler._active
    assert events == (["pause"] if initial_marker else ["A"])
    assert text.max_visible_characters == (0 if initial_marker else 1)
    animator.resume_animation()
    scheduler.update(1, 1)
    assert len(events) == 1 and text.max_visible_characters == 4
    assert not animator._writer.playing and not scheduler._active


def test_marker_pause_freezes_appearance_and_effects_at_the_same_point(component):
    from TextAnimator import TextEffect
    animator, text, scheduler = component
    animator.effects = [TextEffect()]
    animator.on_message.add_listener(lambda value: animator.pause_animation())
    animator.on_enable()
    layout = text.get_text_layout()
    animator.show_text('A<?pause><waitfor=0.5>中BC')
    assert text.get_text_layout() is layout
    scheduler.update(1, 1)
    assert text.max_visible_characters == 1 and not scheduler._active
    assert animator._writer.elapsed_time == pytest.approx(0.1)
    assert animator._appearance.time == pytest.approx(0.1)
    assert animator._animation.time == pytest.approx(0.1)
    alpha = animator._appearance.buffer.colors[0, 0, 3]
    assert 0 < alpha < 1
    animator.resume_animation()
    scheduler.update(0.05, 0.05)
    assert text.max_visible_characters == 1
    assert animator._appearance.time == pytest.approx(0.15)
    assert animator._appearance.buffer.colors[0, 0, 3] > alpha


def test_live_text_first_marker_pause_does_not_advance_the_new_appearance(component):
    from test_typewriter import text_fixture
    from TextAnimator import TextEffect
    animator, text, scheduler = component
    animator.effects = [TextEffect()]
    animator.on_enable()
    text.text = '<?pause>A中BC'
    text.get_text_layout = text_fixture(list('A中BC')).get_text_layout
    animator.on_message.add_listener(lambda value: animator.pause_animation())
    scheduler.update(1, 1)
    assert text.max_visible_characters == 0 and not scheduler._active
    assert animator._writer.elapsed_time == animator._appearance.time == animator._animation.time == 0


@pytest.mark.parametrize("disable", [False, True])
@pytest.mark.parametrize("finish", ["tick", "edit"])
def test_hidden_callback_can_start_a_new_run_without_completing_its_visuals(component, disable, finish):
    animator, text, scheduler = component
    completed = []
    animator.on_enable()
    animator.skip_typewriter()
    animator.on_text_disappeared.add_listener(animator.on_disable if disable else lambda: animator.show_text(animator._animation.source_text))
    animator.on_visual_complete.add_listener(lambda: completed.append(True))
    animator.start_disappearing_text()
    if finish == "edit":
        scheduler.update(0.31, 0.31)
        animator.disappearance.duration = 0
        animator.on_validate()
    else:
        scheduler.update(1, 1)
    assert completed == []
    assert text.max_visible_characters == (2 if disable else 1)
    assert bool(scheduler._active) is not disable


def test_component_skip_interrupted_by_a_marker_keeps_partial_visuals(component):
    animator, text, scheduler = component
    text.text = 'A<waitfor=2>中<?pause>BC'
    animator.on_message.add_listener(lambda value: animator.pause_animation())
    animator.on_enable()
    scheduler.update(0.05, 0.05)
    animator.pause_animation()
    animator.trigger_events_on_skip = True
    animator.skip_typewriter()
    assert text.max_visible_characters == 2 and not scheduler._active
    assert not animator._writer._finished and animator._appearance.active
    assert animator._appearance.time == pytest.approx(animator._writer.elapsed_time)
    assert 0 < animator._appearance.buffer.colors[1, 0, 3] < 1
    animator.resume_animation()
    scheduler.update(0.1, 0.1)
    assert animator._appearance.buffer.colors[1, 0, 3] == pytest.approx(1)


@pytest.mark.parametrize("restart", ["show_text", "play_appearance"])
def test_show_replaces_an_unfinished_visual_hide_without_delayed_disappearance(component, restart):
    animator, text, scheduler = component
    hidden = []
    animator.on_text_disappeared.add_listener(lambda: hidden.append(True))
    animator.on_enable()
    animator.skip_typewriter()
    animator.start_disappearing_text()
    scheduler.update(0.31, 0.31)
    assert animator._hidden_pending and animator._appearance.active
    getattr(animator, restart)(animator._animation.source_text) if restart == "show_text" else animator.play_appearance()
    scheduler.update(1, 1)
    assert text.max_visible_characters in (-1, 4) and hidden == []
    assert not animator._hidden_pending and not scheduler._active


@pytest.mark.parametrize("speed", [1, 2])
def test_nested_skip_pause_samples_the_appearance_once_at_the_retained_event_time(component, speed):
    animator, text, scheduler = component
    text.text = 'A<?skip>中<?pause><waitfor=1>BC'
    animator.set_typewriter_speed(speed)
    animator.trigger_events_on_skip = True
    def marker(value):
        animator.skip_typewriter() if value.name == 'skip' else animator.pause_animation()
    animator.on_message.add_listener(marker)
    animator.on_enable()
    scheduler.update(1, 1)
    assert not scheduler._active and text.max_visible_characters == 2
    assert animator._writer.elapsed_time == pytest.approx(0.2)
    assert animator._appearance.time == pytest.approx(0.2/speed)
    assert animator._appearance.buffer.colors[1, 0, 3] == pytest.approx(1-(1-0.5/speed)**3)


def test_live_typing_speed_changes_remaining_intervals_without_scaling_appearances(component):
    animator, text, scheduler = component
    animator.set_typewriter_speed(2)
    animator.on_character_visible.add_listener(lambda data: animator.set_typewriter_speed(0.5) if data.index == 1 else None)
    animator.on_enable()
    scheduler.update(0.05, 0.05)
    assert text.max_visible_characters == 2
    assert animator._writer.elapsed_time == pytest.approx(0.1)
    assert animator._writer.playback_time == animator._appearance.time == pytest.approx(0.05)
    assert animator._appearance.buffer.colors[0, 0, 3] == pytest.approx(0.578125)
    assert animator._appearance.buffer.colors[1, 0, 3] == 0
    assert animator.typewriter_speed == 0.5
    scheduler.update(0.1, 0.1)
    assert text.max_visible_characters == 2
    assert animator._appearance.buffer.colors[1, 0, 3] == pytest.approx(0.875)
    animator.pause_animation()
    animator.resume_animation()
    scheduler.update(0.1, 0.1)
    assert text.max_visible_characters == 3
    animator.on_disable()
    animator.on_enable()
    assert animator.typewriter_speed == animator._writer.speed_multiplier == 0.5


def test_scaled_marker_pause_and_changed_speed_resume_use_real_appearance_time(component):
    animator, text, scheduler = component
    text.text = 'A<?pause><waitfor=0.5>中BC'
    animator.set_typewriter_speed(2)
    animator.on_message.add_listener(lambda value: animator.pause_animation())
    animator.on_enable()
    scheduler.update(1, 1)
    assert not scheduler._active and text.max_visible_characters == 1
    assert animator._writer.elapsed_time == pytest.approx(0.1)
    assert animator._writer.playback_time == animator._appearance.time == pytest.approx(0.05)
    animator.set_typewriter_speed(0.5)
    animator.resume_animation()
    scheduler.update(0.99, 0.99)
    assert text.max_visible_characters == 1
    scheduler.update(0.02, 0.02)
    assert text.max_visible_characters == 2
    assert 0 < animator._appearance.buffer.colors[1, 0, 3] < 1


def test_show_reverses_an_unfinished_hide_without_resetting_visible_glyphs(component):
    import numpy as np
    animator, text, scheduler = component
    animator.appearance.offset = (0, 12)
    animator.disappearance.offset = (-8, 0)
    animator.disappearance.duration = 0.4
    animator.on_enable()
    animator.skip_typewriter()
    animator.start_disappearing_text()
    scheduler.update(0.05, 0.05)
    previous = animator._appearance.buffer.colors.copy()
    offsets = animator._appearance.buffer.offsets.copy()
    animator.show_text(animator._animation.source_text)
    assert text.max_visible_characters == 4
    assert np.array_equal(animator._appearance.buffer.colors, previous)
    assert np.array_equal(animator._appearance.buffer.offsets, offsets)
    scheduler.update(1, 1)
    assert np.all(animator._appearance.buffer.colors[:, :, 3] == 1)
    assert np.all(animator._appearance.buffer.offsets == 0)


def test_slow_show_holds_the_replaced_hide_until_each_glyph_is_taken_over(component):
    import numpy as np
    animator, text, scheduler = component
    animator.characters_per_second = 1
    animator.appearance.offset = (0, 12)
    animator.disappearance.duration = 0.1
    animator.disappearance.offset = (-8, 0)
    animator.disappearance.rotation = 45
    animator.disappearance.scale = (0.7, 0.7)
    animator.disappearance.vertex_expand = 1
    animator.on_enable()
    animator.skip_typewriter()
    animator.start_disappearing_text()
    scheduler.update(0.05, 0.05)
    names = ('offsets', 'rotations', 'scales', 'colors', 'vertex_offsets')
    held = [getattr(animator._appearance.buffer, name)[3].copy() for name in names]
    assert animator._appearance.buffer.colors[3, 0, 3] == pytest.approx(0.125)
    animator.show_text(animator._animation.source_text)
    scheduler.update(0.4, 0.4)
    assert text.max_visible_characters == 4
    for name, value in zip(names, held):
        assert np.array_equal(getattr(animator._appearance.buffer, name)[3], value)
    animator.pause_animation()
    scheduler.update(1, 1)
    assert animator._writer.playback_time == pytest.approx(0.4)
    animator.resume_animation()
    scheduler.update(2.6, 2.6)
    for name, value in zip(names, held):
        assert getattr(animator._appearance.buffer, name)[3] == pytest.approx(value)
    scheduler.update(0.1, 0.1)
    assert animator._appearance.buffer.colors[3, 0, 3] == pytest.approx(0.890625)
    scheduler.update(0.2, 0.2)
    assert np.all(animator._appearance.buffer.colors[:, :, 3] == 1)
    assert np.all(animator._appearance.buffer.offsets == 0)
    assert not scheduler._active


def test_whole_text_phase_staggers_cancel_typing_and_resume_only_the_visual_pass(component):
    import numpy as np
    animator, text, scheduler = component
    characters = []
    animator.on_character_visible.add_listener(lambda data: characters.append(data.info.character))
    animator.on_enable()
    animator.appearance.duration = 0.4
    animator.appearance_stagger = 0.1
    animator.disappearance.duration = 0.1
    animator.disappearance_stagger = 0.05
    animator.disappearance.offset = (-6, 0)
    animator.play_appearance()
    scheduler.update(0.15, 0.15)
    assert animator._appearance.buffer.colors[0, 0, 3] > animator._appearance.buffer.colors[1, 0, 3] > 0
    assert animator._appearance.buffer.colors[2, 0, 3] == 0
    previous = animator._appearance.buffer.colors.copy()
    animator.play_appearance(False)
    animator.pause_animation()
    animator.resume_animation()
    assert np.array_equal(animator._appearance.buffer.colors, previous)
    scheduler.update(0.26, 0.26)
    assert np.all(animator._appearance.buffer.colors[:, :, 3] == 0)
    assert np.all(animator._appearance.buffer.offsets[:, 0] == -6)
    animator.skip_typewriter()
    assert np.all(animator._appearance.buffer.colors[:, :, 3] == 0)
    assert characters == ['A'] and not scheduler._active


def test_typewriter_speed_rejects_invalid_values_without_changing_the_saved_rate(component):
    animator, _, _ = component
    animator.set_typewriter_speed(2)
    for value in (0, 0.0001, -1, float('nan'), float('inf')):
        with pytest.raises(ValueError, match='finite and at least 0.001'):
            animator.set_typewriter_speed(value)
    assert animator.typewriter_speed == 2
    animator.on_enable()
    for value in (0, 0.0001, -1, float('nan'), float('inf')):
        with pytest.raises(ValueError, match='finite and at least 0.001'):
            animator._writer.speed_multiplier = value
    assert animator._writer.speed_multiplier == 2
    animator.set_typewriter_speed(0.001)
    assert animator.typewriter_speed == animator._writer.speed_multiplier == 0.001


def test_component_start_and_wait_events_keep_typed_payloads_and_pause_without_being_overwritten(component):
    from typing import get_type_hints
    from infernux_text_animator import CharacterData, EventMarker, TimeScale, WaitMode

    animator, text, scheduler = component
    assert get_type_hints(animator.on_character_visible.invoke)['character'] is CharacterData
    assert get_type_hints(animator.on_message.invoke)['marker'] is EventMarker
    animator.time_scale = TimeScale.UNSCALED
    animator.on_typewriter_start.add_listener(animator.pause_animation)
    animator.on_enable()
    assert text.max_visible_characters == 0 and not scheduler._active
    animator.on_typewriter_start.remove_all_listeners()
    events = []
    animator.on_character_wait_started.add_listener(lambda data, mode: (events.append((data, mode)), animator.pause_animation()))
    assert animator.start_showing_text() is None
    scheduler.update(0, 1)
    assert text.max_visible_characters == 1 and not scheduler._active
    assert isinstance(events[0][0], CharacterData) and events[0][1] is WaitMode.APPEARANCE
    assert animator._writer.playback_time == animator._appearance.time == 0
    animator.on_character_wait_started.remove_all_listeners()
    assert animator.start_showing_text() is None
    scheduler.update(0, 0.1)
    assert text.max_visible_characters == 2
    assert animator.skip_typewriter() is None


@pytest.fixture
def dynamic_component(component):
    import numpy as np
    from infernux.lib import TextLayout
    from test_effects import Buffer
    from test_typewriter import text_fixture

    animator, text, scheduler = component
    layouts, commits = {}, []
    def layout():
        if text.text not in layouts:
            value = text_fixture(TextLayout.split_graphemes(text.text)).get_text_layout()
            words, start = [], None
            for index, character in enumerate(value.characters):
                if character.whitespace:
                    if start is not None:
                        words.append(SimpleNamespace(character_start=start, character_end=index))
                        start = None
                elif start is None:
                    start = index
            if start is not None:
                words.append(SimpleNamespace(character_start=start, character_end=len(value.characters)))
            value.words = words
            layouts[text.text] = value
        return layouts[text.text]
    def buffer():
        result = Buffer(len(layout().characters))
        result.skews = np.zeros(result.character_count, dtype=np.float32)
        result.vertex_offsets = np.zeros((result.character_count, 4, 2), dtype=np.float32)
        return result
    text.get_text_layout = layout
    text.create_character_buffer = buffer
    text.set_character_data = lambda value, layer: commits.append(layer)
    text.reset_character_data = lambda layer: commits.append(layer)
    return animator, text, scheduler, commits


def test_visibility_words_and_categories_share_one_layer_and_obey_effect_control(dynamic_component):
    import numpy as np
    from TextAnimator import TextEffect
    from infernux.lib import TextGeometryLayer

    animator, text, scheduler, commits = dynamic_component
    text.text = 'AB 中C'
    animator.effects = [TextEffect()]
    animator.on_enable()
    animator.set_visibility_char(4, True, False)
    animator.set_visibility_char(0, False, False)
    scheduler.update(0.1, 0.1)
    assert animator._appearance.buffer.colors[0, 0, 3] == 0
    assert animator._appearance.buffer.colors[4, 0, 3] == 1
    animator.skip_typewriter()
    appearance = animator._appearance
    assert animator.set_visibility_word(1, False, False) is None
    assert np.all(appearance.buffer.colors[3:, :, 3] == 0)
    assert np.all(appearance.buffer.colors[:3, :, 3] == 1)
    animator.set_visibility_char(3, True)
    scheduler.update(0.1, 0.1)
    assert 0 < appearance.buffer.colors[3, 0, 3] < 1
    assert animator.set_appearances_active(False) is None
    assert animator._appearance is appearance
    assert appearance.buffer.colors[3, 0, 3] == 1 and appearance.buffer.colors[4, 0, 3] == 0
    animator.set_visibility_entire_text(True)
    assert np.all(appearance.buffer.colors[:, :, 3] == 1)
    assert animator.set_behaviors_active(False) is None
    assert commits[-1] is TextGeometryLayer.Effects and not scheduler._active
    assert animator._animation.has_effects
    animator.set_behaviors_active(True)
    assert scheduler._active
    animator.pause_animation()
    assert animator.is_animation_paused and not scheduler._active
    animator.resume_animation()
    assert not animator.is_animation_paused and scheduler._active
    assert not hasattr(animator, 'play') and not hasattr(animator, 'pause')


def test_set_swap_and_visibility_keep_native_glyph_indices_and_cancel_old_playback(dynamic_component):
    import numpy as np

    animator, text, scheduler, _ = dynamic_component
    animator.on_enable()
    assert animator.set_text('e\u0301 中👨‍👩‍👧', True) is None
    assert text.max_visible_characters == 0 and not scheduler._active
    assert animator._animation._buffer.character_count == 4
    animator.set_visibility_char(2, True, False)
    assert text.max_visible_characters == -1
    assert np.array_equal(animator._appearance.buffer.colors[:, 0, 3], [0, 0, 1, 0])
    assert animator.swap_text('A BC尾') is None
    assert np.array_equal(animator._appearance.buffer.colors[:, 0, 3], [0, 0, 1, 0, 0])
    animator.set_text('AB')
    assert text.max_visible_characters == -1 and not scheduler._active
    assert np.all(animator._appearance.buffer.colors[:, :, 3] == 1)
    animator.set_text('ABC', True)
    animator.set_visibility_char(2, True, False)
    animator.start_showing_text()
    assert text.max_visible_characters == 1
    scheduler.update(1, 1)
    assert text.max_visible_characters == 3
    animator.typewriter = False
    animator.animate_appearance = False
    started, showed = [], []
    animator.on_typewriter_start.add_listener(lambda: started.append(True))
    animator.on_text_showed.add_listener(lambda: showed.append(True))
    animator.show_text('Instant')
    assert text.max_visible_characters == -1 and not scheduler._active
    assert not animator._writer.playing and started == [] and showed == [True]
    animator.typewriter = True
    markers = []
    animator.on_message.add_listener(lambda value: markers.append(value.name))
    animator.show_text('A<?old><waitfor=3>B')
    animator.stop_showing_text()
    animator.set_text('C<?new>D')
    animator.trigger_remaining_events()
    assert markers == ['new']
    assert animator.skip_current_action() is False
    assert text.text == 'CD' and text.max_visible_characters == -1


@pytest.mark.parametrize('hide_tail', [False, True])
def test_append_without_skipping_preserves_remaining_wait_and_existing_appearance(dynamic_component, hide_tail):
    import numpy as np

    animator, text, scheduler, _ = dynamic_component
    text.text = 'A<waitfor=0.4>中<?old>'
    markers = []
    animator.on_message.add_listener(lambda value: markers.append(value.name))
    animator.on_enable()
    scheduler.update(0.05, 0.05)
    before = animator._appearance.buffer.colors[:, 0, 3].copy()
    assert animator.append_text('BC<?new>', hide_tail, False) is None
    assert np.array_equal(animator._appearance.buffer.colors[:2, 0, 3], before)
    assert np.all(animator._appearance.buffer.colors[2:, 0, 3] == (0 if hide_tail else 1))
    scheduler.update(0.4, 0.4)
    assert markers == [] and animator._writer._count == 1
    scheduler.update(0.051, 0.051)
    assert animator._writer._count == 2 and markers == ['old']
    scheduler.update(0.2, 0.2)
    assert markers == ['old', 'new'] and animator._writer._count == 4
    scheduler.update(0.3, 0.3)
    assert np.all(animator._appearance.buffer.colors[:, :, 3] == 1)
    assert not scheduler._active


def test_append_skip_old_obeys_new_tail_tags_and_callback_replacement(dynamic_component):
    animator, text, scheduler, _ = dynamic_component
    text.text = 'A<?old><waitfor=3>中'
    markers = []
    animator.on_message.add_listener(lambda value: markers.append(value.name))
    animator.on_enable()
    assert animator.append_text('<?new>B', True) is None
    scheduler.update(0, 0)
    assert markers == ['new'] and animator._writer._count == 3
    assert animator._writer.elapsed_time == 0
    animator.show_text('A<?replace>中')
    animator.trigger_events_on_skip = True
    animator.on_message.add_listener(lambda value: animator.show_text('Z') if value.name == 'replace' else None)
    animator.append_text('never appended', True)
    assert animator._animation.source_text == 'Z' and text.text == 'Z'
    animator.on_message.remove_all_listeners()
    animator.show_text('A<?pause>中')
    animator.on_message.add_listener(lambda value: animator.pause_animation())
    animator.append_text('must wait', True)
    assert animator._animation.source_text == 'A<?pause>中'
    assert not animator._playing and not animator._writer._finished


@pytest.mark.parametrize('hiding', [False, True])
def test_stopping_only_the_writer_keeps_effects_and_current_glyph_animation_running(component, hiding):
    from TextAnimator import TextEffect
    animator, text, scheduler = component
    animator.effects = [TextEffect()]
    animator.on_enable()
    if hiding:
        animator.skip_typewriter()
        animator.start_disappearing_text()
    scheduler.update(0.05, 0.05)
    count, clock = animator._writer._count, animator._writer.elapsed_time
    effect_clock = animator._animation.time
    stop = animator.stop_disappearing_text if hiding else animator.stop_showing_text
    assert stop() is None
    scheduler.update(0.4, 0.4)
    assert animator._writer._count == count and animator._writer.elapsed_time == clock
    assert animator._animation.time == pytest.approx(effect_clock+0.4)
    assert not animator._writer.playing and animator._playing and scheduler._active
    if not hiding:
        animator.start_showing_text()
        scheduler.update(0.05, 0.05)
        assert animator._writer._count == count+1
        assert animator._appearance.buffer.colors[1, 0, 3] == pytest.approx(0)
        scheduler.update(0.1, 0.1)
        assert animator._appearance.buffer.colors[1, 0, 3] == pytest.approx(0.875)


def test_tagged_entry_and_exit_regions_use_one_appearance_layer_without_default_effects(dynamic_component):
    import numpy as np

    animator, text, scheduler, _ = dynamic_component
    text.text = 'A{fade s=2}{incr}中{/}{#slideh a=-2}{#fade}B{/#}'
    animator.animate_appearance = False
    animator.on_enable()
    appearance = animator._appearance
    assert appearance is not None and appearance.buffer.colors[0, 0, 3] == 1
    scheduler.update(0.15, 0.15)
    assert appearance.buffer.colors[1, 0, 3] == pytest.approx(0.875)
    assert appearance.buffer.scales[1] == pytest.approx((0.578125, 0.578125))
    animator.pause_animation()
    held = appearance.buffer.colors.copy()
    scheduler.update(1, 1)
    assert np.array_equal(appearance.buffer.colors, held)
    animator.resume_animation()
    scheduler.update(1, 1)
    animator.start_disappearing_text()
    scheduler.update(0.1, 0.1)
    assert animator._appearance is appearance
    assert appearance.buffer.offsets[2, 0] == pytest.approx(-14)
    assert appearance.buffer.colors[2, 0, 3] == pytest.approx(0.125)
    assert appearance.buffer.colors[1, 0, 3] == 0
    scheduler.update(1, 1)
    assert text.max_visible_characters == 0 and not scheduler._active
    animator.show_text('{fade}A中B')
    assert animator._appearance is appearance
    assert np.all(appearance.buffer.colors[:, :, 3] == 0)
    scheduler.update(0.05, 0.05)
    assert 0 < appearance.buffer.colors[0, 0, 3] < 1
    animator.show_text('A中B')
    assert animator._appearance is None
    scheduler.update(1, 1)
    assert text.max_visible_characters == 3 and not scheduler._active


def test_editor_preview_buttons_call_current_python_controls(component, monkeypatch):
    import importlib
    from pathlib import Path

    monkeypatch.syspath_prepend(str(Path(__file__).parents[1]/'package/editor'))
    tools = importlib.import_module('TextAnimatorTools')
    animator, text, _ = component
    monkeypatch.setattr(TextAnimator, 'game_object', property(lambda _: SimpleNamespace(
        name='Label', get_component=lambda _kind: text)))
    animator.on_enable()
    monkeypatch.setattr(tools, 'translate', lambda key: key)
    monkeypatch.setattr(tools.TextAnimatorPanel, 'services', property(lambda _: SimpleNamespace(
        play_mode_manager=SimpleNamespace(is_playing=False))))
    panel = tools.TextAnimatorPanel()
    panel._component = animator
    panel._scope = SimpleNamespace(closed=False)
    monkeypatch.setattr(TextAnimator, 'is_valid', property(lambda _: True))
    clicked = 'text_animator.pause'
    context = SimpleNamespace(label=lambda _: None, same_line=lambda: None, button=lambda label: label == clicked)
    panel.on_render_content(context)
    assert animator.is_animation_paused
    clicked = 'text_animator.play'
    panel.on_render_content(context)
    assert not animator.is_animation_paused


def test_native_base_queries_visibility_limits_and_current_binding_are_coherent(dynamic_component):
    animator, text, scheduler, _ = dynamic_component
    animator.auto_play = False
    animator.animate_appearance = False
    text.text = 'AB 中'
    animator.on_enable()
    assert animator.characters_count == 4 and animator.words_count == 2
    assert animator.characters is animator.characters
    assert [data.is_visible for data in animator.characters] == [True, True, False, False]
    assert animator.latest_character_shown.info.character == 'B'
    assert animator.any_letter_visible and not animator.all_letters_shown
    animator.set_text('<wave>AB</> 中')
    assert animator.text_full == '<wave>AB</> 中'
    assert animator.text_without_text_anim_tags == animator.text_without_any_tag == 'AB 中'
    assert animator.all_letters_shown
    animator.first_visible_character = 1
    animator.max_visible_characters = 2
    assert [data.is_visible for data in animator.characters] == [False, True, False, False]
    assert animator.first_visible_character == 1 and animator.max_visible_characters == 2
    animator.set_visibility_char(0, True, False)
    assert not animator.characters[0].is_visible
    animator.first_visible_character, animator.max_visible_characters = 0, -1
    assert animator.all_letters_shown
    animator.set_visibility_word(1, False, False)
    assert not animator.all_letters_shown and animator.any_letter_visible
    animator.set_visibility_word(1, True, False)
    assert animator.latest_character_shown.info.character == '中' and animator.all_letters_shown
    animator.max_visible_characters = 2
    animator.show_text('AB 中')
    scheduler.update(1, 1)
    assert text.max_visible_characters == 2 and not animator.is_showing_text
    assert [data.is_visible for data in animator.characters] == [True, True, False, False]
    previous_data = animator.characters[-1]
    animator.set_text('', True)
    assert animator.characters_count == 0 and animator.latest_character_shown is None
    assert animator.all_letters_shown and not animator.any_letter_visible
    assert not animator._animation.has_effects and not scheduler._active
    assert previous_data.info.character == '中' and not previous_data.is_visible


def test_script_and_late_animation_loops_use_their_selected_phase_only(component, monkeypatch):
    import TextAnimator as module
    from infernux_text_animator import AnimationLoop

    animator, text, scheduler = component
    late = PlaybackScheduler()
    monkeypatch.setattr(module, 'late_scheduler', late)
    animator.animation_loop = AnimationLoop.SCRIPT
    animator.on_enable()
    assert text.max_visible_characters == 1 and not scheduler._active and not late._active
    assert animator.animate(0.1) is None
    assert text.max_visible_characters == 2
    animator.animation_loop = AnimationLoop.LATE_UPDATE
    animator.on_validate()
    assert not scheduler._active and late._active
    scheduler.update(1, 1)
    assert text.max_visible_characters == 2
    late.update(0.1, 0.1)
    assert text.max_visible_characters == 3
    animator.pause_animation()
    animator.animate(1)
    assert text.max_visible_characters == 3 and not late._active
    animator.animation_loop = AnimationLoop.UPDATE
    animator.on_validate()
    animator.resume_animation()
    assert scheduler._active and not late._active


def test_waitinput_keeps_appearance_real_time_and_releases_after_pause(component, monkeypatch):
    import infernux.input as input_module
    import infernux.input.actions as actions_module
    from infernux.input import InputAction
    from infernux_text_animator import WaitInputMode

    animator, text, scheduler = component
    state = SimpleNamespace(frame_index=1, any_key_down=False, touches=[], _accepts_game_input=lambda: True)
    monkeypatch.setattr(input_module, 'Input', state)
    text.text = 'A<waitinput><speed=2>中BC'
    animator.on_enable()
    scheduler.update(0.2, 0.2)
    assert text.max_visible_characters == 1 and animator.is_waiting_for_action
    assert animator._writer.elapsed_time == pytest.approx(0.1)
    assert animator._writer.playback_time == animator._appearance.time == pytest.approx(0.2)
    assert animator._appearance.buffer.colors[0, 0, 3] == 1
    animator.pause_animation()
    state.frame_index, state.any_key_down = 2, True
    scheduler.update(1, 1)
    assert text.max_visible_characters == 1
    animator.resume_animation()
    scheduler.update(0.05, 0.05)
    assert text.max_visible_characters == 3
    assert animator._writer.playback_time == animator._appearance.time == pytest.approx(0.25)
    assert animator._appearance.buffer.colors[1, 0, 3] == pytest.approx(0.578125)
    assert animator.typewriter_speed == animator._writer.speed_multiplier == 1
    state.frame_index, state.any_key_down = 3, False
    scheduler.update(0.051, 0.051)
    assert text.max_visible_characters == 4 and not animator.is_waiting_for_action
    scheduler.update(1, 1)
    monkeypatch.setattr(actions_module, 'Input', state)
    action = InputAction('Confirm')
    animator.show_text('A<waitinput=confirm>中BC')
    animator.input_mode = WaitInputMode.SPECIFIC_ACTION
    animator.input_actions['confirm'] = action
    scheduler.update(0.1, 0.1)
    state.frame_index, state.any_key_down = 4, True
    scheduler.update(0.1, 0.1)
    assert text.max_visible_characters == 1
    state.frame_index, state.any_key_down = 5, False
    action.set_virtual_value('test', 1)
    scheduler.update(0, 0)
    assert text.max_visible_characters == 2


def test_visibility_queries_wait_for_appearance_and_visible_events_respect_masks(dynamic_component):
    animator, text, scheduler, _ = dynamic_component
    animator.appearance.duration = 1
    animator.on_enable()
    scheduler.update(0.31, 0.31)
    assert animator._appearance.active and not animator.all_letters_shown
    scheduler.update(1, 1)
    assert animator.all_letters_shown
    animator.set_visibility_entire_text(False, True)
    assert not any(data.is_visible for data in animator.characters)
    assert animator.any_letter_visible
    scheduler.update(1, 1)
    assert not animator.any_letter_visible
    animator.set_text('<?before>A<?inside>中BC<?end>')
    animator.first_visible_character = 1
    markers = []
    animator.on_message.add_listener(lambda marker: markers.append(marker.name))
    animator.trigger_visible_events()
    assert markers == ['inside', 'end']


def test_default_regions_database_refresh_and_font_scale_have_real_effects(dynamic_component):
    import numpy as np
    from TextAnimator import TextEffect
    from infernux_text_animator import CustomEffect, DefaultEffectsMode

    animator, text, scheduler, commits = dynamic_component
    animator.auto_play = animator.typewriter = animator.animate_appearance = False
    animator.effects = [TextEffect(amplitude=2, phase=0, phase_offset=np.pi/2, speed=0)]
    text.text = 'A<custom>B</>{wave}中{/}{#wave}C{/#}'
    animator.database_effects['custom'] = CustomEffect(lambda buffer, selected, time: buffer.offsets.__setitem__((selected, 0), 3))
    assert animator.try_initializing_once() is None
    animation, writer = animator._animation, animator._writer
    assert animator.try_initializing_once() is None and animator._animation is animation and animator._writer is writer
    animator.set_text(animator.text_full)
    animation.sample(0)
    assert animation._buffer.offsets[:, 1] == pytest.approx([2, 0, 2, 2])
    assert animation._buffer.offsets[1, 0] == 3
    assert [(value.start, value.end) for value in animator.behaviors] == [(0, 1), (2, 4), (1, 2)]
    assert [(value.start, value.end) for value in animator.appearances] == [(2, 3)]
    assert [(value.start, value.end) for value in animator.disappearances] == [(3, 4)]
    animator.animate_appearance = True
    animator.refresh_all_effect_states()
    assert [(value.start, value.end) for value in animator.appearances] == [(0, 2), (3, 4), (2, 3)]
    assert [(value.start, value.end) for value in animator.disappearances] == [(0, 3), (3, 4)]
    animator.default_tags_mode = DefaultEffectsMode.CONSTANT
    assert animator.force_database_refresh() is None
    assert [(value.start, value.end) for value in animator.appearances] == [(0, 4), (2, 3)]
    assert animation._buffer.offsets[:, 1] == pytest.approx([2, 2, 2, 2])
    text.font_size = 36
    assert animator.refresh_all_effect_states() is None
    assert animation._buffer.offsets[:, 1] == pytest.approx([4, 4, 4, 4])
    assert animation._buffer.offsets[1, 0] == 6
    animator.use_dynamic_scaling = False
    animator.refresh_all_effect_states()
    assert animation._buffer.offsets[1, 0] == 3
    animator.database_effects['custom'] = CustomEffect(lambda buffer, selected, time: buffer.offsets.__setitem__((selected, 0), 7))
    animator.force_database_refresh()
    assert animation._buffer.offsets[1, 0] == 7
    animator.pause_animation()
    commits.clear()
    clock = animation.time
    assert animator.schedule_mesh_refresh() is None and scheduler._active
    scheduler.update(1, 1)
    assert commits and animation.time == clock and animator.is_animation_paused and not scheduler._active


def test_custom_action_styles_and_replaceable_timings_preserve_pause_skip_and_cancel(dynamic_component):
    from infernux_text_animator.events import ActionMarker, ActionStatus, TextStyle
    from infernux_text_animator.typewriter import TypingTimings, TypingDelaysByWord

    animator, text, scheduler, _ = dynamic_component
    states, seen = [], []

    class Timings(TypingTimings):
        def get_wait_appearance_time_of(self, character, owner):
            assert owner is animator
            return 0.1 if character.info.character != ' ' else 0

        def get_wait_disappearance_time_of(self, character, owner):
            return 0.2

    class State:
        elapsed = 0
        cancelled = 0
        def progress(self, delta_time, typing_info):
            assert typing_info.typewriter is animator
            self.elapsed += delta_time
            return ActionStatus.FINISHED if self.elapsed >= 0.2 else ActionStatus.RUNNING
        def cancel(self): self.cancelled += 1

    class Gate:
        def create_action_from(self, marker, owner):
            assert owner is animator and marker == ActionMarker('Gate', ['10', 'gold'])
            state = State()
            states.append(state)
            return state

    animator.timing_settings = Timings()
    animator.database['Gate'] = Gate()
    animator.style_sheet['accent'] = TextStyle('<wave a=2>', '</wave><?done>')
    text.text = '<AcCeNt>A<gAtE=10,gold>中 B</ACCENT>'
    animator.on_message.add_listener(lambda value: seen.append(value.name))
    animator.on_enable()
    assert text.text == 'A中 B' and animator.text_full.startswith('<AcCeNt>')
    scheduler.update(0.1, 0.1)
    assert len(states) == 1 and animator.is_waiting_for_action and text.max_visible_characters == 1
    animator.pause_animation()
    scheduler.update(1, 1)
    assert states[0].elapsed == 0
    animator.resume_animation()
    scheduler.update(0.2, 0.2)
    assert text.max_visible_characters == 2 and states[0].cancelled == 0
    assert animator._writer.playback_time == pytest.approx(0.3)
    animator.timing_settings = TypingDelaysByWord()
    scheduler.update(1, 1)
    assert text.max_visible_characters == 4 and seen == ['done']
    animator.show_text('A<gate=10,gold>中 B')
    scheduler.update(0.1, 0.1)
    assert animator.skip_current_action() is True and states[-1].cancelled == 1
    assert animator._writer._count >= 2
    animator.show_text('A<gate=10,gold>中 B')
    scheduler.update(0.1, 0.1)
    pending = states[-1]
    animator.set_text('replacement')
    assert pending.cancelled == 1 and not animator.is_waiting_for_action
    assert animator.text_without_any_tag == 'replacement'
    animator.timing_settings = Timings()

    class PausingGate(Gate):
        def create_action_from(self, marker, owner):
            state = super().create_action_from(marker, owner)
            owner.pause_animation()
            return state

    animator.database['Gate'] = PausingGate()
    animator.show_text('A<gate=10,gold>中')
    scheduler.update(1, 1)
    assert animator.is_animation_paused and text.max_visible_characters == 1
    assert animator._writer.playback_time == animator._appearance.time == pytest.approx(0.1)
    animator.resume_animation()
    scheduler.update(0.21, 0.21)
    assert text.max_visible_characters == 2 and states[-1].cancelled == 0
    animator.database['Gate'] = Gate()
    animator.show_text('A<gate=10,gold>中')
    scheduler.update(0.1, 0.1)
    states[-1].cancel = lambda: animator.show_text('callback wins')
    animator.set_text('must not overwrite callback')
    assert animator.text_without_any_tag == 'callback wins'
    animator.show_text('A<gate=10,gold>中')
    scheduler.update(0.1, 0.1)
    states[-1].cancel = lambda: animator.show_text('must be disabled too')
    animator.on_disable()
    assert animator._animation is animator._writer is None and not scheduler._active
