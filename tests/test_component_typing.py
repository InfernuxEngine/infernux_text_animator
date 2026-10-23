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
    scheduler.Clear()
    animator.on_disable()


def test_typing_appearance_pause_and_reverse_keep_exiting_glyphs_until_they_finish(component):
    animator, text, scheduler = component
    hidden = []
    animator.on_hidden.add_listener(lambda: hidden.append(True))
    animator.on_enable()
    assert text.max_visible_characters == 1
    scheduler.Update(0.15, 0.15)
    alpha = animator._appearance.buffer.colors[0, 0, 3]
    assert 0 < alpha < 1
    animator.Pause()
    assert not scheduler._active
    animator.Play()
    scheduler.Update(0.5, 0.5)
    assert not animator._writer.playing and not animator._appearance.active
    animator.StartDisappearingText()
    assert text.max_visible_characters == 4
    scheduler.Update(0.31, 0.31)
    assert text.max_visible_characters == 4 and not hidden
    scheduler.Update(0.21, 0.21)
    assert text.max_visible_characters == 0 and hidden == [True]
    assert not scheduler._active


def test_character_callback_can_disable_the_component_without_stale_work(component):
    animator, text, scheduler = component
    animator.on_character.add_listener(lambda data: animator.on_disable() if data[0] == 1 else None)
    animator.on_enable()
    scheduler.Update(0.15, 0.15)
    assert animator._animation is animator._writer is None
    assert not scheduler._active and text.max_visible_characters == 2


def test_manual_play_starts_a_component_with_auto_play_disabled(component):
    animator, text, scheduler = component
    animator.auto_play = False
    animator.on_enable()
    assert not scheduler._active and text.max_visible_characters == 2
    animator.Play()
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
    scheduler.Update(0.15, 0.15)
    appearance = animator._appearance
    alpha = appearance.buffer.colors[:, :, 3].copy()
    animator.Pause()
    animator.appearance.rotation = 20
    animator.appearance.duration = 0.4
    animator.on_validate()
    assert animator._appearance is appearance
    assert appearance.buffer.colors[:, :, 3] == pytest.approx(alpha)
    assert text.max_visible_characters == 2 and not scheduler._active
    assert appearance.active
    animator.Play()
    scheduler.Update(0.05, 0.05)
    assert appearance.buffer.colors[1, 0, 3] > alpha[1, 0]


def test_removing_the_last_effect_clears_its_geometry_before_unscheduling(component):
    import numpy as np
    from TextAnimator import TextEffect
    animator, text, scheduler = component
    animator.typewriter = animator.animate_appearance = False
    animator.effects = [TextEffect()]
    animator.on_enable()
    scheduler.Update(0.15, 0.15)
    assert np.any(animator._animation._buffer.offsets != 0)
    animator.effects.clear()
    animator.on_validate()
    assert np.all(animator._animation._buffer.offsets == 0)
    assert not animator._animation.has_effects and not scheduler._active


def test_character_audio_uses_native_whitespace_metadata(component):
    animator, text, scheduler = component
    animator.on_enable()
    played = []
    animator._sound = SimpleNamespace(play=lambda: played.append(True))
    animator._writer._whitespace[1] = True
    animator._character_shown(1, "<br>")
    animator._character_shown(2, "B")
    assert played == [True]


@pytest.mark.parametrize("initial_marker", [False, True])
def test_first_callback_pause_survives_startup_and_play_resumes_without_replaying(component, initial_marker):
    animator, text, scheduler = component
    events = []
    if initial_marker:
        text.text = '<event=pause/>A中BC'
        animator.on_event.add_listener(lambda value: (events.append(value), animator.Pause()))
    else:
        animator.on_character.add_listener(lambda data: (events.append(data[1]), animator.Pause()) if data[0] == 0 else None)
    animator.on_enable()
    assert not animator._playing and not animator._writer.playing and not scheduler._active
    assert events == (["pause"] if initial_marker else ["A"])
    assert text.max_visible_characters == (0 if initial_marker else 1)
    animator.Play()
    scheduler.Update(1, 1)
    assert len(events) == 1 and text.max_visible_characters == 4
    assert not animator._writer.playing and not scheduler._active


def test_marker_pause_freezes_appearance_and_effects_at_the_same_point(component):
    from TextAnimator import TextEffect
    animator, text, scheduler = component
    animator.effects = [TextEffect()]
    animator.on_event.add_listener(lambda value: animator.Pause())
    animator.on_enable()
    layout = text.get_text_layout()
    animator.ShowText('A<event=pause/><wait=0.5/>中BC')
    assert text.get_text_layout() is layout
    scheduler.Update(1, 1)
    assert text.max_visible_characters == 1 and not scheduler._active
    assert animator._writer.elapsed_time == pytest.approx(0.1)
    assert animator._appearance.time == pytest.approx(0.1)
    assert animator._animation.time == pytest.approx(0.1)
    alpha = animator._appearance.buffer.colors[0, 0, 3]
    assert 0 < alpha < 1
    animator.Play()
    scheduler.Update(0.05, 0.05)
    assert text.max_visible_characters == 1
    assert animator._appearance.time == pytest.approx(0.15)
    assert animator._appearance.buffer.colors[0, 0, 3] > alpha


def test_live_text_first_marker_pause_does_not_advance_the_new_appearance(component):
    from test_typewriter import text_fixture
    from TextAnimator import TextEffect
    animator, text, scheduler = component
    animator.effects = [TextEffect()]
    animator.on_enable()
    text.text = '<event=pause/>A中BC'
    text.get_text_layout = text_fixture(list('A中BC')).get_text_layout
    animator.on_event.add_listener(lambda value: animator.Pause())
    scheduler.Update(1, 1)
    assert text.max_visible_characters == 0 and not scheduler._active
    assert animator._writer.elapsed_time == animator._appearance.time == animator._animation.time == 0


@pytest.mark.parametrize("disable", [False, True])
def test_hidden_callback_can_start_a_new_run_without_completing_its_visuals(component, disable):
    animator, text, scheduler = component
    completed = []
    animator.on_enable()
    animator.SkipTypewriter()
    animator.on_hidden.add_listener(animator.on_disable if disable else animator.ShowText)
    animator.on_visual_complete.add_listener(lambda: completed.append(True))
    animator.StartDisappearingText()
    scheduler.Update(1, 1)
    assert completed == []
    assert text.max_visible_characters == (2 if disable else 1)
    assert bool(scheduler._active) is not disable


def test_component_skip_interrupted_by_a_marker_keeps_partial_visuals(component):
    animator, text, scheduler = component
    text.text = 'A<wait=2/>中<event=pause/>BC'
    animator.on_event.add_listener(lambda value: animator.Pause())
    animator.on_enable()
    scheduler.Update(0.05, 0.05)
    animator.Pause().SkipTypewriter(True)
    assert text.max_visible_characters == 2 and not scheduler._active
    assert not animator._writer._finished and animator._appearance.active
    assert animator._appearance.time == pytest.approx(animator._writer.elapsed_time)
    assert 0 < animator._appearance.buffer.colors[1, 0, 3] < 1
    animator.Play()
    scheduler.Update(0.1, 0.1)
    assert animator._appearance.buffer.colors[1, 0, 3] == pytest.approx(1)


@pytest.mark.parametrize("restart", ["ShowText", "PlayAppearance"])
def test_show_replaces_an_unfinished_visual_hide_without_delayed_disappearance(component, restart):
    animator, text, scheduler = component
    hidden = []
    animator.on_hidden.add_listener(lambda: hidden.append(True))
    animator.on_enable()
    animator.SkipTypewriter().StartDisappearingText()
    scheduler.Update(0.31, 0.31)
    assert animator._hidden_pending and animator._appearance.active
    getattr(animator, restart)()
    scheduler.Update(1, 1)
    assert text.max_visible_characters in (-1, 4) and hidden == []
    assert not animator._hidden_pending and not scheduler._active


@pytest.mark.parametrize("speed", [1, 2])
def test_nested_skip_pause_samples_the_appearance_once_at_the_retained_event_time(component, speed):
    animator, text, scheduler = component
    text.text = 'A<event=skip/>中<event=pause/><wait=1/>BC'
    animator.SetTypewriterSpeed(speed)
    def marker(value):
        animator.SkipTypewriter(True) if value == 'skip' else animator.Pause()
    animator.on_event.add_listener(marker)
    animator.on_enable()
    scheduler.Update(1, 1)
    assert not scheduler._active and text.max_visible_characters == 2
    assert animator._writer.elapsed_time == pytest.approx(0.2)
    assert animator._appearance.time == pytest.approx(0.2/speed)
    assert animator._appearance.buffer.colors[1, 0, 3] == pytest.approx(1-(1-0.5/speed)**3)


def test_live_typing_speed_changes_remaining_intervals_without_scaling_appearances(component):
    animator, text, scheduler = component
    animator.SetTypewriterSpeed(2)
    animator.on_character.add_listener(lambda data: animator.SetTypewriterSpeed(0.5) if data[0] == 1 else None)
    animator.on_enable()
    scheduler.Update(0.05, 0.05)
    assert text.max_visible_characters == 2
    assert animator._writer.elapsed_time == pytest.approx(0.1)
    assert animator._writer.playback_time == animator._appearance.time == pytest.approx(0.05)
    assert animator._appearance.buffer.colors[0, 0, 3] == pytest.approx(0.578125)
    assert animator._appearance.buffer.colors[1, 0, 3] == 0
    assert animator.typewriter_speed == 0.5
    scheduler.Update(0.1, 0.1)
    assert text.max_visible_characters == 2
    assert animator._appearance.buffer.colors[1, 0, 3] == pytest.approx(0.875)
    animator.Pause().Play()
    scheduler.Update(0.1, 0.1)
    assert text.max_visible_characters == 3
    animator.on_disable()
    animator.on_enable()
    assert animator.typewriter_speed == animator._writer.timeScale == 0.5


def test_scaled_marker_pause_and_changed_speed_resume_use_real_appearance_time(component):
    animator, text, scheduler = component
    text.text = 'A<event=pause/><wait=0.5/>中BC'
    animator.SetTypewriterSpeed(2)
    animator.on_event.add_listener(lambda value: animator.Pause())
    animator.on_enable()
    scheduler.Update(1, 1)
    assert not scheduler._active and text.max_visible_characters == 1
    assert animator._writer.elapsed_time == pytest.approx(0.1)
    assert animator._writer.playback_time == animator._appearance.time == pytest.approx(0.05)
    animator.SetTypewriterSpeed(0.5).Play()
    scheduler.Update(0.99, 0.99)
    assert text.max_visible_characters == 1
    scheduler.Update(0.02, 0.02)
    assert text.max_visible_characters == 2
    assert 0 < animator._appearance.buffer.colors[1, 0, 3] < 1


def test_show_reverses_an_unfinished_hide_without_resetting_visible_glyphs(component):
    import numpy as np
    animator, text, scheduler = component
    animator.appearance.offset = (0, 12)
    animator.disappearance.offset = (-8, 0)
    animator.disappearance.duration = 0.4
    animator.on_enable()
    animator.SkipTypewriter().StartDisappearingText()
    scheduler.Update(0.05, 0.05)
    previous = animator._appearance.buffer.colors.copy()
    offsets = animator._appearance.buffer.offsets.copy()
    animator.ShowText()
    assert text.max_visible_characters == 4
    assert np.array_equal(animator._appearance.buffer.colors, previous)
    assert np.array_equal(animator._appearance.buffer.offsets, offsets)
    scheduler.Update(1, 1)
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
    animator.SkipTypewriter().StartDisappearingText()
    scheduler.Update(0.05, 0.05)
    names = ('offsets', 'rotations', 'scales', 'colors', 'vertex_offsets')
    held = [getattr(animator._appearance.buffer, name)[3].copy() for name in names]
    assert animator._appearance.buffer.colors[3, 0, 3] == pytest.approx(0.125)
    animator.ShowText()
    scheduler.Update(0.4, 0.4)
    assert text.max_visible_characters == 4
    for name, value in zip(names, held):
        assert np.array_equal(getattr(animator._appearance.buffer, name)[3], value)
    animator.Pause()
    scheduler.Update(1, 1)
    assert animator._writer.playback_time == pytest.approx(0.4)
    animator.Play()
    scheduler.Update(2.6, 2.6)
    for name, value in zip(names, held):
        assert getattr(animator._appearance.buffer, name)[3] == pytest.approx(value)
    scheduler.Update(0.1, 0.1)
    assert animator._appearance.buffer.colors[3, 0, 3] == pytest.approx(0.890625)
    scheduler.Update(0.2, 0.2)
    assert np.all(animator._appearance.buffer.colors[:, :, 3] == 1)
    assert np.all(animator._appearance.buffer.offsets == 0)
    assert not scheduler._active


def test_whole_text_phase_staggers_cancel_typing_and_resume_only_the_visual_pass(component):
    import numpy as np
    animator, text, scheduler = component
    characters = []
    animator.on_character.add_listener(lambda data: characters.append(data[1]))
    animator.on_enable()
    animator.appearance.duration = 0.4
    animator.appearance_stagger = 0.1
    animator.disappearance.duration = 0.1
    animator.disappearance_stagger = 0.05
    animator.disappearance.offset = (-6, 0)
    animator.PlayAppearance()
    scheduler.Update(0.15, 0.15)
    assert animator._appearance.buffer.colors[0, 0, 3] > animator._appearance.buffer.colors[1, 0, 3] > 0
    assert animator._appearance.buffer.colors[2, 0, 3] == 0
    previous = animator._appearance.buffer.colors.copy()
    animator.PlayAppearance(False).Pause().Play()
    assert np.array_equal(animator._appearance.buffer.colors, previous)
    scheduler.Update(0.26, 0.26)
    assert np.all(animator._appearance.buffer.colors[:, :, 3] == 0)
    assert np.all(animator._appearance.buffer.offsets[:, 0] == -6)
    animator.SkipTypewriter()
    assert np.all(animator._appearance.buffer.colors[:, :, 3] == 0)
    assert characters == ['A'] and not scheduler._active


def test_typewriter_speed_rejects_invalid_values_without_changing_the_saved_rate(component):
    animator, _, _ = component
    animator.SetTypewriterSpeed(2)
    for value in (0, -1, float('nan'), float('inf')):
        with pytest.raises(ValueError, match='finite and positive'):
            animator.SetTypewriterSpeed(value)
    assert animator.typewriter_speed == 2
    animator.on_enable()
    for value in (0, -1, float('nan'), float('inf')):
        with pytest.raises(ValueError, match='finite and positive'):
            animator._writer.timeScale = value
    assert animator._writer.timeScale == 2
