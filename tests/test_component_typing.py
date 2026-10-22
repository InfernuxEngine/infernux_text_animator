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
