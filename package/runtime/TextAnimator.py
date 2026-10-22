from infernux.components import (
    FieldType, InxComponent, SerializableObject, add_component_menu,
    disallow_multiple, require_component, serialized_field,
)
from infernux.ui import UIText
from infernux.lib import SceneManager

from infernux_text_animator import Appearance, CharacterAppearance, Effect, EffectKind, TextAnimation, Typewriter
from infernux_text_animator.playback import scheduler
from infernux.ui.ui_event import UIEvent, UIEvent1


class TextEffect(SerializableObject):
    kind: EffectKind = serialized_field(default=EffectKind.Wave, display_name_key="text_animator.kind",
                                        enum_labels=["text_animator.effect."+kind.value for kind in EffectKind])
    amplitude: float = serialized_field(default=8.0, display_name_key="text_animator.amplitude")
    speed: float = serialized_field(default=1.0, display_name_key="text_animator.speed")
    phase: float = serialized_field(default=0.6, display_name_key="text_animator.phase")
    phase_offset: float = serialized_field(default=0.0, display_name_key="text_animator.phase_offset")
    start: int = serialized_field(default=0, range=(0, 100000), slider=False, display_name_key="text_animator.range_start")
    end: int = serialized_field(default=-1, range=(-1, 100000), slider=False, display_name_key="text_animator.range_end")
    seed: int = serialized_field(default=0, display_name_key="text_animator.seed")
    color: list = serialized_field(default=[1.0, 0.25, 0.25, 1.0], field_type=FieldType.COLOR,
                                  display_name_key="text_animator.color")

    def build(self):
        return Effect(self.kind, self.amplitude, self.speed, self.phase,
                      self.start, None if self.end == -1 else self.end, self.seed, self.phase_offset, tuple(self.color))


class TextPreset(SerializableObject):
    name: str = serialized_field(default="emphasis", display_name_key="text_animator.preset_name")
    effect: TextEffect = serialized_field(default=TextEffect(), display_name_key="text_animator.preset_effect")


class TextAppearance(SerializableObject):
    duration: float = serialized_field(default=0.25, range=(0.01, 10), display_name_key="text_animator.duration")
    offset = serialized_field(default=(0.0, 0.0), field_type=FieldType.VEC2, display_name_key="text_animator.offset")
    scale = serialized_field(default=(1.0, 1.0), field_type=FieldType.VEC2, display_name_key="text_animator.scale")
    rotation: float = serialized_field(default=0.0, display_name_key="text_animator.rotation")
    alpha: float = serialized_field(default=0.0, range=(0.0, 1.0), display_name_key="text_animator.alpha")
    vertex_expand: float = serialized_field(default=0.0, display_name_key="text_animator.vertex_expand")
    random_offset: float = serialized_field(default=0.0, display_name_key="text_animator.random_offset")
    seed: int = serialized_field(default=0, display_name_key="text_animator.seed")

    def build(self):
        return Appearance(self.duration, tuple(self.offset), tuple(self.scale), self.rotation,
                          self.alpha, self.vertex_expand, self.random_offset, self.seed)


@require_component(UIText)
@disallow_multiple
@add_component_menu("Animation/Text Animator")
class TextAnimator(InxComponent):
    effects: list = serialized_field(default=[], field_type=FieldType.LIST, element_type=FieldType.SERIALIZABLE_OBJECT,
                                     element_class=TextEffect, group="Effects", display_name_key="text_animator.effects")
    presets: list = serialized_field(default=[], field_type=FieldType.LIST, element_type=FieldType.SERIALIZABLE_OBJECT,
                                     element_class=TextPreset, group="Effects", display_name_key="text_animator.presets")
    auto_play: bool = serialized_field(default=True, group="Playback", display_name_key="text_animator.auto_play")
    parse_tags: bool = serialized_field(default=True, group="Effects", display_name_key="text_animator.parse_tags")
    unscaled_time: bool = serialized_field(default=False, group="Playback", display_name_key="text_animator.unscaled_time")
    typewriter: bool = serialized_field(default=False, group="Typewriter", display_name_key="text_animator.typewriter")
    characters_per_second: float = serialized_field(default=30.0, range=(0.1, 1000.0), group="Typewriter",
                                                    display_name_key="text_animator.characters_per_second")
    punctuation_pause: float = serialized_field(default=0.15, range=(0.0, 10.0), group="Typewriter",
                                               display_name_key="text_animator.punctuation_pause")
    whitespace_pause: float = serialized_field(default=0.0, range=(0.0, 10.0), group="Typewriter",
                                              display_name_key="text_animator.whitespace_pause")
    by_word: bool = serialized_field(default=False, group="Typewriter", display_name_key="text_animator.by_word")
    character_audio = serialized_field(default=None, field_type=FieldType.GAME_OBJECT, group="Typewriter",
                                        required_component="AudioSource",
                                        display_name_key="text_animator.character_audio")
    characters_per_sound: int = serialized_field(default=1, range=(1, 1000), group="Typewriter",
                                                 display_name_key="text_animator.characters_per_sound")
    animate_appearance: bool = serialized_field(default=False, group="Appearance", display_name_key="text_animator.animate_appearance")
    appearance: TextAppearance = serialized_field(default=TextAppearance(), group="Appearance", display_name_key="text_animator.appearance")
    appearance_stagger: float = serialized_field(default=0.03, range=(0.0, 10), group="Appearance", display_name_key="text_animator.stagger")

    _animation = None
    _writer = None
    _playing = False
    _previous_visible_count = -1
    _appearance = None
    _hidden_pending = False
    _preview = False
    _preview_registration = None
    _sound = None
    _started_playback = False

    def _event(self, name, kind):
        if name not in self.__dict__:
            self.__dict__[name] = kind()
        return self.__dict__[name]

    @property
    def on_character(self): return self._event("_character_event", UIEvent1)
    @property
    def on_event(self): return self._event("_marker_event", UIEvent1)
    @property
    def on_complete(self): return self._event("_complete_event", UIEvent)
    @property
    def on_hidden(self): return self._event("_hidden_event", UIEvent)
    @property
    def on_visual_complete(self): return self._event("_visual_event", UIEvent)

    def on_enable(self):
        if not self._preview and not SceneManager.instance().is_playing():
            return
        text = self.game_object.get_component(UIText)
        self._previous_visible_count = text.max_visible_characters
        self._animation = TextAnimation(text, [effect.build() for effect in self.effects], parse_tags=self.parse_tags,
                                        presets={preset.name: preset.effect.build() for preset in self.presets})
        self._writer = Typewriter(text, characters_per_second=self.characters_per_second,
                                  punctuation_pause=self.punctuation_pause, whitespace_pause=self.whitespace_pause,
                                  by_word=self.by_word)
        self._writer.cues = self._animation.cues
        self._sound = None
        if self.character_audio is not None and not self._preview:
            from infernux.components.builtin import AudioSource
            self._sound = self.character_audio.get_component(AudioSource)
            if self._sound is None:
                raise ValueError("Character audio object needs an AudioSource")
        self._writer.on_character = self._character_shown
        self._writer.on_event = lambda value: self._emit(self.on_event, value)
        self._writer.on_complete = lambda: self._emit(self.on_complete)
        self._writer.on_hidden = self._finished_hiding
        self._writer.on_character_hidden = self._character_hidden
        self._hidden_pending = False
        self._appearance = CharacterAppearance(text, self.appearance.build()) if self.animate_appearance else None
        if self._appearance is not None:
            self._writer.visibility_handler = self._publish_visibility
        self._playing = self._started_playback = False
        if self.auto_play:
            self.Play()
        else:
            self._schedule()

    def _character_shown(self, index, character):
        if self._appearance is not None:
            self._appearance.Character(index, at=self._writer.event_time)
        if self._sound is not None and not character.isspace() and index % self.characters_per_sound == 0:
            self._sound.play()
        self._emit(self.on_character, (index, character))

    def _emit(self, event, *arguments):
        if not self._preview:
            event.invoke(*arguments)

    def _character_hidden(self, index, character):
        if self._appearance is not None:
            self._appearance.Character(index, False, at=self._writer.event_time)

    def _publish_visibility(self, count, hiding):
        self._animation.text.max_visible_characters = self._writer.visible_limit if hiding else count

    def _finished_hiding(self):
        if self._appearance is not None and self._appearance.active:
            self._hidden_pending = True
        else:
            self._emit(self.on_hidden)

    def _schedule(self):
        active = self._playing and ((self._animation.has_effects and self._animation.text.max_visible_characters != 0)
                                   or self._writer.playing or (self._appearance is not None and self._appearance.active))
        if self._preview:
            if self._preview_registration is not None:
                self._preview_registration.enabled = active
        elif active:
            scheduler.add(self)
        else:
            scheduler.remove(self)

    def _tick(self, delta_time, unscaled_delta):
        delta = unscaled_delta if self.unscaled_time else delta_time
        animation = self._animation
        if self._animation.Refresh():
            self._writer.cues = self._animation.cues
            if self._appearance is not None:
                self._appearance.Refresh()
            if self.typewriter:
                self.ShowText()
                if self._animation is not animation:
                    return
        if self._animation.has_effects:
            self._animation.Update(delta)
        if self._writer.playing:
            writer = self._writer
            generation = writer._generation
            self._writer.Update(delta)
            if self._writer is not writer or writer._generation != generation:
                return
        if self._animation is not animation:
            return
        if self._appearance is not None and self._appearance.active:
            self._appearance.Update(delta)
            if not self._appearance.active:
                if self._hidden_pending:
                    self._hidden_pending = False
                    self._animation.text.max_visible_characters = 0
                    self._emit(self.on_hidden)
                self._emit(self.on_visual_complete)
                if self._animation is not animation:
                    return
        self._schedule()

    def on_validate(self):
        if self._animation is not None:
            source = self._animation.source_text
            self._animation.parse_tags = self.parse_tags
            self._animation.presets = {preset.name: preset.effect.build() for preset in self.presets}
            self._animation.SetText(source)
            self._animation.SetEffects([effect.build() for effect in self.effects])
            self._writer.characters_per_second = self.characters_per_second
            self._writer.punctuation_pause = self.punctuation_pause
            self._writer.whitespace_pause = self.whitespace_pause
            self._writer.by_word = self.by_word
            if self._appearance is not None:
                self._appearance.Reset()
            self._appearance = CharacterAppearance(self._animation.text, self.appearance.build()) if self.animate_appearance else None
            self._writer.visibility_handler = self._publish_visibility if self._appearance is not None else None
            self._schedule()

    def on_disable(self):
        self._playing = False
        scheduler.remove(self)
        if self._animation is not None:
            if self._appearance is not None:
                self._appearance.Reset()
                self._appearance = None
            self._animation.Reset()
            self._animation.text.text = self._animation.source_text
            self._animation.text.max_visible_characters = self._previous_visible_count
            self._writer.StopShowingText()
            self._animation = self._writer = None

    def Play(self):
        if self._animation is None:
            raise RuntimeError("Enable TextAnimator before playback")
        if not self._started_playback:
            self._started_playback = True
            if self.typewriter:
                self.ShowText()
            elif self._appearance is not None:
                self._appearance.Play(stagger=self.appearance_stagger)
            if self._animation is None:
                return self
        self._playing = True
        self._schedule()
        return self

    def Pause(self):
        self._playing = False
        self._schedule()
        return self

    def ShowText(self, value=None):
        self._started_playback = True
        if value is not None:
            self._animation.SetText(value)
        self._writer.cues = self._animation.cues
        if self._appearance is not None:
            if self._appearance.layout is not self._animation.text.get_text_layout():
                self._appearance.Refresh()
            self._appearance.RebaseTime(0).SetVisible(False)
        self._writer.ShowText()
        if self._writer is None:
            return self
        self._playing = True
        self._schedule()
        return self

    def SkipTypewriter(self, trigger_events=False):
        writer = self._writer
        generation = writer._generation
        writer.SkipTypewriter(trigger_events)
        if self._writer is not writer or writer._generation != generation:
            return self
        if self._appearance is not None:
            self._appearance.SetVisible(not self._writer.hiding)
            if self._writer.hiding:
                self._animation.text.max_visible_characters = 0
                if self._hidden_pending:
                    self._hidden_pending = False
                    self._emit(self.on_hidden)
        self._schedule()
        return self

    def StartDisappearingText(self):
        self._started_playback = True
        if self._appearance is not None:
            self._appearance.RebaseTime(0)
        self._writer.StartDisappearingText()
        if self._writer is None:
            return self
        self._playing = True
        self._schedule()
        return self

    def PlayAppearance(self, showing=True):
        if self._appearance is None:
            raise RuntimeError("Enable appearance animation in the Inspector first")
        self._appearance.Play(showing, stagger=self.appearance_stagger)
        self._started_playback = True
        self._playing = True
        self._schedule()
        return self

    def BeginPreview(self, scope):
        if self._animation is not None:
            raise RuntimeError("Stop the active playback before starting an editor preview")
        text = self.game_object.get_component(UIText)
        scope.capture(self, "_preview", "_preview_registration", "_playing", "_animation", "_writer",
                      "_appearance", "_previous_visible_count", "_hidden_pending", "_sound", "_started_playback")
        scope.capture_text(text)
        scope.capture(text, "text")
        self._preview = True
        self.on_enable()
        if not self._playing:
            self.Play()
        self._preview_registration = scope.add_update(lambda dt: self._tick(dt, dt))
        self._schedule()
        return self
