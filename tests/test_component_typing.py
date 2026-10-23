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
