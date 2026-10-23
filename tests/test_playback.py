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
    animation = SimpleNamespace(text=text, Reset=lambda: resets.append("reset"), has_effects=False,
                                Refresh=lambda: False, source_text="hello")
    writer = Typewriter(text, characters_per_second=100).ShowText()
    component = TextAnimator()
    component._animation, component._writer = animation, writer
    component.typewriter = True
    component._started_playback = True
    component.Play()
    assert activity == [True]
    scheduler.Update(0.1, 0.2)
    assert activity == [True, False]
    assert not scheduler._active
    writer.ShowText()
    component.Play()
    scheduler.Clear()
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
    scheduler.Update(0.1, 0.5)
    assert events == [("first", 0.1, 0.5)]
    scheduler.Clear()
    assert not scheduler._active
