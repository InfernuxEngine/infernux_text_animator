from infernux.components import (
    FieldType, InxComponent, SerializableObject, add_component_menu,
    disallow_multiple, list_field, require_component, serialized_field,
)
from infernux.ui import UIText

from infernux_text_animator import Effect, EffectKind, TextAnimation, Typewriter
from infernux_text_animator.playback import scheduler


class TextEffect(SerializableObject):
    kind: EffectKind = serialized_field(default=EffectKind.Wave, display_name_key="text_animator.kind")
    amplitude: float = serialized_field(default=8.0, display_name_key="text_animator.amplitude")
    speed: float = serialized_field(default=1.0, display_name_key="text_animator.speed")
    phase: float = serialized_field(default=0.6, display_name_key="text_animator.phase")
    phase_offset: float = serialized_field(default=0.0, display_name_key="text_animator.phase_offset")
    start: int = serialized_field(default=0, range=(0, 100000), slider=False, display_name_key="text_animator.range_start")
    end: int = serialized_field(default=-1, range=(-1, 100000), slider=False, display_name_key="text_animator.range_end")
    seed: int = serialized_field(default=0, display_name_key="text_animator.seed")

    def build(self):
        return Effect(self.kind, self.amplitude, self.speed, self.phase,
                      self.start, None if self.end == -1 else self.end, self.seed, self.phase_offset)


@require_component(UIText)
@disallow_multiple
@add_component_menu("Animation/Text Animator")
class TextAnimator(InxComponent):
    effects: list = list_field(element_type=FieldType.SERIALIZABLE_OBJECT, element_class=TextEffect,
                              default=[], group="Effects")
    auto_play: bool = serialized_field(default=True, group="Playback")
    unscaled_time: bool = serialized_field(default=False, group="Playback", display_name_key="text_animator.unscaled_time")
    typewriter: bool = serialized_field(default=False, group="Typewriter")
    characters_per_second: float = serialized_field(default=30.0, range=(0.1, 1000.0), group="Typewriter",
                                                    display_name_key="text_animator.characters_per_second")
    punctuation_pause: float = serialized_field(default=0.15, range=(0.0, 10.0), group="Typewriter",
                                               display_name_key="text_animator.punctuation_pause")
    whitespace_pause: float = serialized_field(default=0.0, range=(0.0, 10.0), group="Typewriter",
                                              display_name_key="text_animator.whitespace_pause")
    by_word: bool = serialized_field(default=False, group="Typewriter", display_name_key="text_animator.by_word")

    _animation = None
    _writer = None
    _playing = False
    _previous_visible_count = -1

    def on_enable(self):
        text = self.game_object.get_component(UIText)
        self._previous_visible_count = text.max_visible_characters
        self._animation = TextAnimation(text, [effect.build() for effect in self.effects])
        self._writer = Typewriter(text, characters_per_second=self.characters_per_second,
                                  punctuation_pause=self.punctuation_pause, whitespace_pause=self.whitespace_pause,
                                  by_word=self.by_word)
        self._playing = self.auto_play
        if self.typewriter and self.auto_play:
            self._writer.ShowText()
        self._schedule()

    def _schedule(self):
        if self._playing and (self.effects or self._writer.playing):
            scheduler.add(self)
        else:
            scheduler.remove(self)

    def _tick(self, delta_time, unscaled_delta):
        delta = unscaled_delta if self.unscaled_time else delta_time
        if self.effects:
            self._animation.Update(delta)
        if self._writer.playing:
            self._writer.Update(delta)
        self._schedule()

    def on_validate(self):
        if self._animation is not None:
            self._animation.SetEffects([effect.build() for effect in self.effects])
            self._writer.characters_per_second = self.characters_per_second
            self._writer.punctuation_pause = self.punctuation_pause
            self._writer.whitespace_pause = self.whitespace_pause
            self._writer.by_word = self.by_word
            self._schedule()

    def on_disable(self):
        self._playing = False
        scheduler.remove(self)
        if self._animation is not None:
            self._animation.Reset()
            if self.typewriter:
                self._animation.text.max_visible_characters = self._previous_visible_count
            self._writer.StopShowingText()
            self._animation = self._writer = None

    def Play(self):
        if self._animation is None:
            raise RuntimeError("Enable TextAnimator before playback")
        self._playing = True
        self._schedule()
        return self

    def Pause(self):
        self._playing = False
        self._schedule()
        return self

    def ShowText(self, value=None):
        self._writer.ShowText(value)
        self._playing = True
        self._schedule()
        return self

    def SkipTypewriter(self, trigger_events=False):
        self._writer.SkipTypewriter(trigger_events)
        self._schedule()
        return self
