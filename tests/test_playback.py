from types import SimpleNamespace

from TextAnimator import TextAnimator
from infernux_text_animator import Typewriter
from infernux_text_animator.playback import PlaybackScheduler


def test_component_callback_disables_after_typing_and_unload_restores_state(monkeypatch):
    import TextAnimator as component_module

    scheduler, activity, resets = PlaybackScheduler(), [], []
    scheduler.on_activity = activity.append
    monkeypatch.setattr(component_module, "scheduler", scheduler)
    from test_typewriter import text_fixture
    text = text_fixture(list("hello"))
    text.font_size = 18.0
    animation = SimpleNamespace(text=text, reset=lambda: resets.append("reset"), has_effects=False, has_active_effects=False,
                                refresh=lambda: False, source_text="hello")
    writer = Typewriter(text, characters_per_second=100)
    writer.show_text(writer.text.text)
    component = TextAnimator()
    component._animation, component._writer = animation, writer
    component.typewriter = True
    component._started_playback = True
    component.resume_animation()
    assert activity == [True]
    scheduler.update(0.1, 0.2)
    assert activity == [True, False]
    assert not scheduler._active
    writer.show_text(writer.text.text)
    component.resume_animation()
    scheduler.clear()
    assert activity == [True, False, True, False]
    assert resets == ["reset"] and text.max_visible_characters == -1
    assert component._animation is component._writer is None


def test_scheduler_skips_controllers_removed_by_an_earlier_callback():
    scheduler, events = PlaybackScheduler(), []

    class Controller:
        def __init__(self, name): self.name = name
        def _tick(self, delta, unscaled):
            events.append((self.name, delta, unscaled))
            scheduler.remove(second)
        def on_disable(self): scheduler.remove(self)

    first, second = Controller("first"), Controller("second")
    scheduler.add(first)
    scheduler.add(second)
    scheduler.update(0.1, 0.5)
    assert events == [("first", 0.1, 0.5)]
    scheduler.clear()
    assert not scheduler._active
