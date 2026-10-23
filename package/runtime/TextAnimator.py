from math import isfinite
import numpy as np

from infernux.components import (
    FieldType, InxComponent, SerializableObject, add_component_menu,
    disallow_multiple, require_component, serialized_field,
)
from infernux.ui import UIText
from infernux.lib import SceneManager, TextWordInfo
from infernux.graph.ramp import AnimationCurve

from infernux_text_animator import AnimationLoop, Appearance, AppearanceTag, CharacterAppearance, CharacterData, CurveTarget, CustomEffect, DefaultEffectsMode, Effect, EffectKind, TextAnimation, TimeScale, Typewriter, WaitInputMode
from infernux.input import InputAction
from infernux_text_animator.playback import scheduler, late_scheduler
from infernux_text_animator.events import CharacterEvent, CharacterWaitEvent, MessageEvent, TextRegion
from infernux_text_animator.events import TextStyle, TypewriterAction
from infernux_text_animator.typewriter import TypingTimings
from infernux.ui.ui_event import UIEvent


class TextEffect(SerializableObject):
    kind: EffectKind = serialized_field(default=EffectKind.WAVE, display_name_key="text_animator.kind",
                                        enum_labels=["text_animator.effect."+kind.value for kind in EffectKind])
    amplitude: float = serialized_field(default=8.0, display_name_key="text_animator.amplitude")
    speed: float = serialized_field(default=1.0, display_name_key="text_animator.speed")
    phase: float = serialized_field(default=0.6, display_name_key="text_animator.phase")
    phase_offset: float = serialized_field(default=0.0, display_name_key="text_animator.phase_offset")
    once: bool = serialized_field(default=False, display_name_key="text_animator.once")
    start: int = serialized_field(default=0, range=(0, 100000), slider=False, display_name_key="text_animator.range_start")
    end: int = serialized_field(default=-1, range=(-1, 100000), slider=False, display_name_key="text_animator.range_end")
    seed: int = serialized_field(default=0, display_name_key="text_animator.seed")
    color: list = serialized_field(default=[1.0, 0.25, 0.25, 1.0], field_type=FieldType.COLOR,
                                  display_name_key="text_animator.color")
    curve: AnimationCurve = serialized_field(default=AnimationCurve(pre_wrap="repeat", post_wrap="repeat"),
                                              field_type=FieldType.ANIMATION_CURVE, display_name_key="text_animator.curve",
                                              visible_when=lambda e: e.kind == EffectKind.CURVE)
    curve_target: CurveTarget = serialized_field(default=CurveTarget.OFFSET_Y, display_name_key="text_animator.curve_target",
                                                  enum_labels=["text_animator.curve_target."+v.value for v in CurveTarget],
                                                  visible_when=lambda e: e.kind == EffectKind.CURVE)

    def build(self):
        return Effect(self.kind, self.amplitude, self.speed, self.phase,
                      self.start, None if self.end == -1 else self.end, self.seed, self.phase_offset, tuple(self.color),
                      self.curve if self.kind == EffectKind.CURVE else None, self.curve_target, self.once)


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
                                     element_class=TextEffect, group="text_animator.group.effects", display_name_key="text_animator.effects")
    presets: list = serialized_field(default=[], field_type=FieldType.LIST, element_type=FieldType.SERIALIZABLE_OBJECT,
                                     element_class=TextPreset, group="text_animator.group.effects", display_name_key="text_animator.presets")
    parse_tags: bool = serialized_field(default=True, group="text_animator.group.effects", display_name_key="text_animator.parse_tags")
    default_tags_mode: DefaultEffectsMode = serialized_field(default=DefaultEffectsMode.FALLBACK, group="text_animator.group.effects",
                                                            enum_labels=["text_animator.fallback", "text_animator.constant"],
                                                            display_name_key="text_animator.default_tags_mode")
    use_dynamic_scaling: bool = serialized_field(default=True, group="text_animator.group.effects", display_name_key="text_animator.use_dynamic_scaling")
    reference_font_size: float = serialized_field(default=18.0, range=(1.0, 256.0), slider=False,
                                                 group="text_animator.group.effects", display_name_key="text_animator.reference_font_size")
    auto_play: bool = serialized_field(default=True, group="text_animator.group.playback", display_name_key="text_animator.auto_play")
    time_scale: TimeScale = serialized_field(default=TimeScale.SCALED, group="text_animator.group.playback",
                                            enum_labels=["text_animator.scaled", "text_animator.unscaled"],
                                            display_name_key="text_animator.time_scale")
    animation_loop: AnimationLoop = serialized_field(default=AnimationLoop.UPDATE, group="text_animator.group.playback",
                                                     enum_labels=["text_animator.update", "text_animator.late_update", "text_animator.script"],
                                                     display_name_key="text_animator.animation_loop")
    typewriter: bool = serialized_field(default=False, group="text_animator.group.typewriter", display_name_key="text_animator.typewriter")
    characters_per_second: float = serialized_field(default=30.0, range=(0.1, 1000.0), group="text_animator.group.typewriter",
                                                    display_name_key="text_animator.characters_per_second")
    typewriter_speed: float = serialized_field(default=1.0, range=(0.001, 100.0), slider=False,
                                              group="text_animator.group.typewriter", display_name_key="text_animator.typewriter_speed")
    punctuation_pause: float = serialized_field(default=0.15, range=(0.0, 10.0), group="text_animator.group.typewriter",
                                               display_name_key="text_animator.punctuation_pause")
    whitespace_pause: float = serialized_field(default=0.0, range=(0.0, 10.0), group="text_animator.group.typewriter",
                                              display_name_key="text_animator.whitespace_pause")
    by_word: bool = serialized_field(default=False, group="text_animator.group.typewriter", display_name_key="text_animator.by_word")
    trigger_events_on_skip: bool = serialized_field(default=False, group="text_animator.group.typewriter",
                                                   display_name_key="text_animator.trigger_events_on_skip")
    input_mode: WaitInputMode = serialized_field(default=WaitInputMode.ANY_INPUT, group="text_animator.group.typewriter",
                                               enum_labels=["text_animator.any_input", "text_animator.specific_action"],
                                               display_name_key="text_animator.input_mode")
    default_input_key: str = serialized_field(default="", group="text_animator.group.typewriter",
                                              display_name_key="text_animator.default_input_key")
    character_audio = serialized_field(default=None, field_type=FieldType.GAME_OBJECT, group="text_animator.group.typewriter",
                                        required_component="AudioSource",
                                        display_name_key="text_animator.character_audio")
    characters_per_sound: int = serialized_field(default=1, range=(1, 1000), group="text_animator.group.typewriter",
                                                 display_name_key="text_animator.characters_per_sound")
    animate_appearance: bool = serialized_field(default=False, group="text_animator.group.appearance", display_name_key="text_animator.animate_appearance")
    appearance: TextAppearance = serialized_field(default=TextAppearance(), group="text_animator.group.appearance", display_name_key="text_animator.appearance")
    appearance_stagger: float = serialized_field(default=0.03, range=(0.0, 10), group="text_animator.group.appearance", display_name_key="text_animator.stagger")
    disappearance: TextAppearance = serialized_field(default=TextAppearance(), group="text_animator.group.appearance", display_name_key="text_animator.disappearance")
    disappearance_stagger: float = serialized_field(default=0.03, range=(0.0, 10), group="text_animator.group.appearance", display_name_key="text_animator.disappearance_stagger")

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
    _reveal_floor = 0
    _behaviors_active = True
    _appearances_active = True
    _visibility_overrides = None
    _first_visible_character = 0
    _max_visible_characters = -1
    _scheduled_by = None
    _mesh_refresh_requested = False
    _timing_settings = None

    def _event(self, name, kind):
        if name not in self.__dict__:
            self.__dict__[name] = kind()
        return self.__dict__[name]

    @property
    def input_actions(self) -> dict[str, InputAction]:
        return self.__dict__.setdefault("_input_actions", {})

    @property
    def database_effects(self) -> dict[str, Effect | CustomEffect | AppearanceTag]:
        return self.__dict__.setdefault("_database_effects", {})

    @database_effects.setter
    def database_effects(self, value: dict[str, Effect | CustomEffect | AppearanceTag]) -> None:
        self.__dict__["_database_effects"] = value
        if self._animation is not None:
            self.force_database_refresh()

    @property
    def database(self) -> dict[str, TypewriterAction]:
        return self.__dict__.setdefault("_database", {})

    @property
    def style_sheet(self) -> dict[str, TextStyle]:
        return self.__dict__.setdefault("_style_sheet", {})

    @style_sheet.setter
    def style_sheet(self, value: dict[str, TextStyle]) -> None:
        self.__dict__["_style_sheet"] = value
        if self._animation is not None:
            self._animation.style_sheet = value
            self.force_database_refresh()

    @property
    def timing_settings(self) -> TypingTimings | None: return self._timing_settings

    @timing_settings.setter
    def timing_settings(self, value: TypingTimings | None) -> None:
        if value is not None and not isinstance(value, TypingTimings):
            raise TypeError("Timing settings must be a TypingTimings object")
        self._timing_settings = value
        if self._writer is not None:
            self._writer.timing_settings = value

    def _presets(self):
        return {**{preset.name: preset.effect.build() for preset in self.presets}, **self.database_effects}

    @property
    def appearances(self) -> tuple[TextRegion, ...]: return self._phase_regions(False)
    @property
    def behaviors(self) -> tuple[TextRegion, ...]: return self._animation.behaviors
    @property
    def disappearances(self) -> tuple[TextRegion, ...]: return self._phase_regions(True)

    def _phase_regions(self, hiding):
        tags = self._animation.disappearance_tags if hiding else self._animation.appearance_tags
        count = self.characters_count
        regions = [TextRegion(tag.start, count if tag.end is None else tag.end, tag) for tag in tags
                   if tag.start < (count if tag.end is None else tag.end)]
        if self.animate_appearance and count:
            free = np.ones(count, dtype=np.bool_)
            if self.default_tags_mode is DefaultEffectsMode.FALLBACK:
                for region in regions:
                    free[region.start:region.end] = False
            bounds = np.flatnonzero(np.diff(np.r_[False, free, False])).reshape(-1, 2)
            profile = self.disappearance.build() if hiding else self.appearance.build()
            regions[:0] = [TextRegion(int(start), int(end), profile) for start, end in bounds]
        return tuple(regions)

    def _effect_scale(self):
        return self._animation.text.font_size/self.reference_font_size if self.use_dynamic_scaling else 1.0

    @property
    def characters(self) -> list[CharacterData]: return self._writer._character_data
    @property
    def characters_count(self) -> int: return self._animation._buffer.character_count
    @property
    def words(self) -> list[TextWordInfo]: return self._animation.text.get_text_layout().words
    @property
    def words_count(self) -> int: return len(self.words)
    @property
    def text_full(self) -> str: return self._animation.source_text
    @property
    def text_without_any_tag(self) -> str: return self._animation.text.get_text_layout().display_text
    @property
    def text_without_text_anim_tags(self) -> str: return self._animation.text.text
    @property
    def all_letters_shown(self) -> bool:
        return all(data.is_visible for data in self.characters) and (self._appearance is None or not self._appearance.active)
    @property
    def any_letter_visible(self) -> bool:
        if self._appearance is None:
            return any(data.is_visible for data in self.characters)
        limit = self._animation.text.max_visible_characters
        alpha = self._appearance.buffer.colors[:, :, 3]
        return bool(np.any(alpha[:limit if limit >= 0 else len(alpha)] > 0))
    @property
    def latest_character_shown(self) -> CharacterData | None: return self._writer._latest_character
    @property
    def is_showing_text(self) -> bool: return self._writer.is_showing_text
    @property
    def is_hiding_text(self) -> bool: return self._writer.is_hiding_text
    @property
    def is_waiting_for_action(self) -> bool: return self._writer.is_waiting_for_action

    @property
    def first_visible_character(self) -> int: return self._first_visible_character

    @first_visible_character.setter
    def first_visible_character(self, value: int) -> None:
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError("First visible character must be an int")
        if value < 0:
            raise ValueError("First visible character must be nonnegative")
        self._first_visible_character = value
        self._refresh_visibility_limits()

    @property
    def max_visible_characters(self) -> int: return self._max_visible_characters

    @max_visible_characters.setter
    def max_visible_characters(self, value: int) -> None:
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError("Max visible characters must be an int")
        if value < -1:
            raise ValueError("Max visible characters must be -1 or nonnegative")
        self._max_visible_characters = value
        self._refresh_visibility_limits()

    def _sync_visibility_metadata(self):
        state = self._writer._visibility_state
        state.first, state.limit, state.overrides = self._first_visible_character, self._max_visible_characters, self._visibility_overrides

    def _refresh_visibility_limits(self):
        if self._appearance is None and self._first_visible_character:
            self._appearance = self._new_appearance()
            self._writer.visibility_handler = self._publish_visibility
        if self._appearance is not None:
            self._appearance.first_visible_character = self._first_visible_character
            self._appearance.max_visible_characters = self._max_visible_characters
            self._appearance.sample(self._appearance.time)
        self._publish_visibility(self._writer._count, self._writer.hiding)
        self._schedule()

    @property
    def on_character_visible(self) -> CharacterEvent: return self._event("_character_event", CharacterEvent)
    @property
    def on_typewriter_start(self): return self._event("_start_event", UIEvent)
    @property
    def on_character_wait_started(self) -> CharacterWaitEvent: return self._event("_wait_started_event", CharacterWaitEvent)
    @property
    def on_character_wait_finished(self) -> CharacterWaitEvent: return self._event("_wait_finished_event", CharacterWaitEvent)
    @property
    def on_message(self) -> MessageEvent: return self._event("_marker_event", MessageEvent)
    @property
    def on_text_showed(self): return self._event("_complete_event", UIEvent)
    @property
    def on_text_disappeared(self): return self._event("_hidden_event", UIEvent)
    @property
    def on_visual_complete(self): return self._event("_visual_event", UIEvent)

    def on_enable(self):
        if not self._preview and not SceneManager.instance().is_playing():
            return
        self.try_initializing_once()
        if self.auto_play:
            self.resume_animation()
        else:
            self._schedule()

    def try_initializing_once(self) -> None:
        if self._animation is not None:
            return
        if not isinstance(self.time_scale, TimeScale):
            raise TypeError("Time scale must be a TimeScale enum member")
        if not isinstance(self.animation_loop, AnimationLoop):
            raise TypeError("Animation loop must be an AnimationLoop member")
        self._first_visible_character, self._max_visible_characters = 0, -1
        text = self.game_object.get_component(UIText)
        self._previous_visible_count = text.max_visible_characters
        self._animation = TextAnimation(text, [effect.build() for effect in self.effects], parse_tags=self.parse_tags,
                                        presets=self._presets(), default_tags_mode=self.default_tags_mode,
                                        actions=self.database, style_sheet=self.style_sheet)
        self._animation.scale = self._effect_scale()
        self._writer = Typewriter(text, characters_per_second=self.characters_per_second,
                                  punctuation_pause=self.punctuation_pause, whitespace_pause=self.whitespace_pause,
                                  by_word=self.by_word)
        self._writer.speed_multiplier = self.typewriter_speed
        self._writer.trigger_events_on_skip = self.trigger_events_on_skip
        self._writer.input_mode = self.input_mode
        self._writer.default_input_key = self.default_input_key
        self._writer.input_actions = self.input_actions
        self._writer._input_settings = self
        self._writer._owner = self
        self._writer.database = self.database
        self._writer.timing_settings = self.timing_settings
        self._writer.cues = self._animation.cues
        if not self.auto_play or not self.typewriter:
            self._writer._bind_text(text.max_visible_characters)
        self._sound = None
        if self.character_audio is not None and not self._preview:
            from infernux.components.builtin import AudioSource
            self._sound = self.character_audio.get_component(AudioSource)
            if self._sound is None:
                raise ValueError("character audio object needs an AudioSource")
        self._writer.on_character_visible = self._character_shown
        self._writer.on_typewriter_start = lambda: self._emit(self.on_typewriter_start)
        self._writer.on_character_wait_started = lambda data, mode: self._emit(self.on_character_wait_started, data, mode)
        self._writer.on_character_wait_finished = lambda data, mode: self._emit(self.on_character_wait_finished, data, mode)
        self._writer.on_message = lambda value: self._emit(self.on_message, value)
        self._writer.on_text_showed = lambda: self._emit(self.on_text_showed)
        self._writer.on_text_disappeared = self._finished_hiding
        self._writer.on_character_hidden = self._character_hidden
        self._hidden_pending = False
        self._appearance = self._new_appearance() if self._uses_appearance() else None
        self._visibility_overrides = None
        self._reveal_floor = 0
        self._writer.visibility_handler = self._publish_visibility
        self._playing = self._started_playback = False
        self._mesh_refresh_requested = False

    def _character_shown(self, character):
        index = character.index
        if self._appearance is not None:
            if self._visibility_overrides is None:
                self._appearance.character(index, at=self._writer.playback_time)
            elif self._visibility_overrides[index] == -1:
                self._appearance._set_visibility(np.array([index]), True, self._uses_appearance(),
                                                 at=self._writer.playback_time, commit=False)
        if self._sound is not None and not self._writer._whitespace[index] and index % self.characters_per_sound == 0:
            self._sound.play()
        self._emit(self.on_character_visible, character)

    def _emit(self, event, *arguments):
        if not self._preview:
            event.invoke(*arguments)

    def _character_hidden(self, character):
        if self._appearance is not None:
            if self._visibility_overrides is None or self._visibility_overrides[character.index] == -1:
                self._appearance._set_visibility(np.array([character.index]), False, self._uses_appearance(),
                                                 at=self._writer.playback_time, commit=False)

    def _publish_visibility(self, count, hiding):
        self._sync_visibility_metadata()
        visible = -1 if self._visibility_overrides is not None else self._writer.visible_limit if hiding else max(count, self._reveal_floor)
        if self._visibility_overrides is None and self._max_visible_characters >= 0:
            visible = min(visible, self._max_visible_characters) if visible >= 0 else self._max_visible_characters
        self._animation.text.max_visible_characters = visible

    def _configure_appearance(self):
        incoming, outgoing = self.appearance.build(), self.disappearance.build()
        if (incoming, outgoing) != (self._appearance.appearance, self._appearance.disappearance):
            self._appearance.set_appearances(incoming, outgoing)
        tags = tuple(self._animation.appearance_tags), tuple(self._animation.disappearance_tags)
        constant = self.default_tags_mode is DefaultEffectsMode.CONSTANT
        if (tags != (self._appearance.appearance_tags, self._appearance.disappearance_tags)
                or self.animate_appearance != self._appearance.default_enabled or constant != self._appearance.constant_defaults):
            self._appearance.set_appearance_tags(*tags, default_enabled=self.animate_appearance, constant_defaults=constant)
        self._appearance.scale = self._effect_scale()

    def _uses_appearance(self):
        return self._appearances_active and bool(self.animate_appearance or self._animation.appearance_tags or self._animation.disappearance_tags)

    def _new_appearance(self):
        appearance = CharacterAppearance(self._animation.text, self.appearance.build(), self.disappearance.build(),
                                         appearance_tags=self._animation.appearance_tags,
                                         disappearance_tags=self._animation.disappearance_tags, default_enabled=self.animate_appearance,
                                         constant_defaults=self.default_tags_mode is DefaultEffectsMode.CONSTANT)
        appearance.scale = self._effect_scale()
        appearance.first_visible_character = self._first_visible_character
        appearance.max_visible_characters = self._max_visible_characters
        return appearance

    def _finished_hiding(self):
        if self._visibility_overrides is not None and np.any(self._visibility_overrides == 1):
            return
        if self._appearance is not None and self._appearance.active:
            self._hidden_pending = True
        else:
            self._emit(self.on_text_disappeared)

    def _schedule(self):
        active = self._mesh_refresh_requested or self._playing and ((self._behaviors_active and self._animation.has_active_effects and self._animation.text.max_visible_characters != 0)
                                   or self._writer.playing or (self._appearance is not None and self._appearance.active))
        if self._preview:
            if self._preview_registration is not None:
                self._preview_registration.enabled = active
        else:
            target = None if self.animation_loop is AnimationLoop.SCRIPT else late_scheduler if self.animation_loop is AnimationLoop.LATE_UPDATE else scheduler
            if self._scheduled_by is not target:
                if self._scheduled_by is not None:
                    self._scheduled_by.remove(self)
                self._scheduled_by = target
            if target is not None:
                target.add(self) if active else target.remove(self)

    def animate(self, delta_time: float) -> None:
        if isinstance(delta_time, bool) or not isfinite(delta_time) or delta_time < 0:
            raise ValueError("Animation delta must be finite and nonnegative")
        if self._playing:
            self._tick(delta_time, delta_time)

    def force_database_refresh(self) -> None:
        self.try_initializing_once()
        self.on_validate()

    def refresh_all_effect_states(self) -> None:
        self.try_initializing_once()
        self.on_validate()

    def schedule_mesh_refresh(self) -> None:
        self.try_initializing_once()
        self._mesh_refresh_requested = True
        self._schedule()

    def _tick(self, delta_time, unscaled_delta):
        delta = unscaled_delta if self.time_scale is TimeScale.UNSCALED else delta_time
        animation = self._animation
        if self._animation.refresh():
            self._writer.cues = self._animation.cues
            if self._appearance is not None:
                self._appearance.refresh()
            if self.typewriter:
                self.show_text(self._animation.source_text)
                if self._animation is not animation or not self._playing:
                    return
        if self._mesh_refresh_requested:
            self._mesh_refresh_requested = False
            if self._behaviors_active:
                animation.sample(animation.time)
            if self._appearance is not None:
                self._appearance.sample(self._appearance.time)
            if not self._playing:
                self._schedule()
                return
        self._animation.scale = self._effect_scale()
        if self._appearance is not None:
            self._appearance.scale = self._animation.scale
        appearance_clock = self._appearance.time if self._appearance is not None else 0
        if self._writer.playing:
            writer = self._writer
            generation, serial = writer._generation, writer._control_serial
            clock = writer.playback_time
            self._writer.update(delta)
            if self._writer is not writer or writer._generation != generation:
                return
            if writer._control_serial != serial and not writer._finished and not self._playing:
                delta = min(delta, max(0, writer.playback_time-clock))
        if self._animation is not animation:
            return
        if self._behaviors_active and self._animation.has_active_effects:
            self._animation.update(delta)
        if self._appearance is not None and self._appearance.active:
            self._appearance.sample(max(self._appearance.time, appearance_clock+delta))
            if not self._appearance.active:
                if self._hidden_pending:
                    self._hidden_pending = False
                    self._animation.text.max_visible_characters = 0
                    writer, generation = self._writer, self._writer._generation
                    self._emit(self.on_text_disappeared)
                    if self._writer is not writer or writer._generation != generation or self._appearance.active:
                        return
                self._emit(self.on_visual_complete)
                if self._animation is not animation:
                    return
        if not self._writer.playing and not self._writer._finished and self._appearance is not None:
            self._writer._playback_clock = max(self._writer.playback_time, self._appearance.time)
        self._schedule()

    def on_validate(self):
        if not isinstance(self.time_scale, TimeScale):
            raise TypeError("Time scale must be a TimeScale enum member")
        if not isinstance(self.animation_loop, AnimationLoop):
            raise TypeError("Animation loop must be an AnimationLoop member")
        if self._animation is not None:
            layout = self._animation._layout
            source = self._animation.source_text
            self._animation.parse_tags = self.parse_tags
            self._animation.presets = self._presets()
            self._animation.default_tags_mode = self.default_tags_mode
            self._animation.scale = self._effect_scale()
            self._animation._set_text(source)
            self._animation.set_effects([effect.build() for effect in self.effects])
            if not self._behaviors_active:
                self._animation.text.reset_character_data(self._animation._layer)
            self._writer.characters_per_second = self.characters_per_second
            self._writer.speed_multiplier = self.typewriter_speed
            self._writer.trigger_events_on_skip = self.trigger_events_on_skip
            self._writer.input_mode = self.input_mode
            self._writer.default_input_key = self.default_input_key
            self._writer.punctuation_pause = self.punctuation_pause
            self._writer.whitespace_pause = self.whitespace_pause
            self._writer.by_word = self.by_word
            self._writer.timing_settings = self.timing_settings
            changed_cues = self._writer.cues != self._animation.cues
            self._writer.cues = self._animation.cues
            changed_layout = self._animation.text.get_text_layout() is not layout
            if self._uses_appearance() or self._visibility_overrides is not None or self._first_visible_character:
                if self._appearance is not None and not changed_layout:
                    self._configure_appearance()
                else:
                    self._appearance = self._new_appearance()
                    if self.typewriter and not changed_layout and self._writer._completion_time is not None:
                        self._appearance.rebase_time(self._writer.playback_time).set_visible(False)
                        for index in range(self._writer._count):
                            self._appearance.character(index, at=self._writer.playback_time-self.appearance.duration)
                        self._appearance.sample(self._writer.playback_time)
            elif self._appearance is not None:
                self._appearance.reset()
                self._appearance = None
            self._writer.visibility_handler = self._publish_visibility
            if (changed_layout or changed_cues) and self.typewriter and self._started_playback:
                playing = self._playing
                self.show_text(self._animation.source_text)
                if not playing:
                    self.pause_animation()
            elif changed_layout or changed_cues:
                self._writer._bind_text(self._animation.text.max_visible_characters)
                self._sync_visibility_metadata()
            elif self.typewriter and self._writer._completion_time is not None:
                self._writer._publish(self._writer._count)
            if self._hidden_pending and self._appearance is None:
                self._hidden_pending = False
                self._emit(self.on_text_disappeared)
            self._schedule()

    def on_disable(self):
        source = self._animation.source_text if self._animation is not None else None
        if self._writer is not None:
            self._writer._cancel()
        self._playing = False
        self._mesh_refresh_requested = False
        if self._scheduled_by is not None:
            self._scheduled_by.remove(self)
            self._scheduled_by = None
        if self._animation is not None:
            if self._appearance is not None:
                self._appearance.reset()
                self._appearance = None
            self._animation.reset()
            self._animation.text.text = source
            self._animation.text.max_visible_characters = self._previous_visible_count
            self._animation = self._writer = None

    @property
    def is_animation_paused(self) -> bool:
        return not self._playing

    def set_behaviors_active(self, is_category_enabled: bool) -> None:
        if not isinstance(is_category_enabled, bool):
            raise TypeError("Category state must be a bool")
        self._behaviors_active = is_category_enabled
        if self._animation is None:
            return
        if is_category_enabled:
            self._animation.sample(self._animation.time)
        else:
            self._animation.text.reset_character_data(self._animation._layer)
        self._schedule()

    def set_appearances_active(self, is_category_enabled: bool) -> None:
        if not isinstance(is_category_enabled, bool):
            raise TypeError("Category state must be a bool")
        self._appearances_active = is_category_enabled
        if not is_category_enabled and self._appearance is not None and self._visibility_overrides is not None:
            showing = self._appearance._showing.copy()
            self._appearance._set_visibility(np.flatnonzero(showing), True, False)
            self._appearance._set_visibility(np.flatnonzero(~showing), False, False)
        self.on_validate()

    def _set_visibility(self, indices, is_visible, can_play_effects):
        if not isinstance(is_visible, bool) or not isinstance(can_play_effects, bool):
            raise TypeError("Visibility and effect control must be bools")
        text = self._animation.text
        if self._visibility_overrides is None:
            count = self._animation._buffer.character_count
            previous = text.max_visible_characters
            if self._appearance is None:
                self._appearance = self._new_appearance()
            self._visibility_overrides = np.full(count, -1, dtype=np.int8)
            if previous >= 0:
                self._appearance._set_visibility(np.arange(min(previous, count), count), False, False)
            self._writer.visibility_handler = self._publish_visibility
        self._hidden_pending = False
        self._appearance.sample(max(self._appearance.time, self._writer.playback_time))
        self._visibility_overrides[indices] = int(is_visible)
        self._sync_visibility_metadata()
        self._appearance._set_visibility(indices, is_visible,
                                         can_play_effects and self._uses_appearance())
        text.max_visible_characters = -1
        self._schedule()

    def set_visibility_char(self, index: int, is_visible: bool, can_play_effects: bool = True) -> None:
        count = self._animation._buffer.character_count
        if isinstance(index, bool) or not isinstance(index, int):
            raise TypeError("Character index must be an int")
        if not 0 <= index < count:
            raise IndexError(index)
        self._set_visibility(np.array([index]), is_visible, can_play_effects)
        if is_visible:
            self._writer._latest_character = self.characters[index]

    def set_visibility_word(self, index: int, is_visible: bool, can_play_effects: bool = True) -> None:
        words = self._animation.text.get_text_layout().words
        if isinstance(index, bool) or not isinstance(index, int):
            raise TypeError("Word index must be an int")
        if not 0 <= index < len(words):
            raise IndexError(index)
        word = words[index]
        self._set_visibility(np.arange(word.character_start, word.character_end), is_visible, can_play_effects)
        if is_visible:
            self._writer._latest_character = self.characters[word.character_end-1]

    def set_visibility_entire_text(self, is_visible: bool, can_play_effects: bool = True) -> None:
        self._set_visibility(np.arange(self._animation._buffer.character_count), is_visible, can_play_effects)
        if is_visible and self.characters:
            self._writer._latest_character = self.characters[-1]

    def _replace_text(self, text, visible, *, cancel_writer=True):
        if not isinstance(text, str):
            raise TypeError("Text must be a string")
        if cancel_writer:
            if not self._writer._cancel():
                return False
        self._hidden_pending = False
        self._visibility_overrides = None
        self._animation._set_text(text)
        self._animation._once_started = self._animation.time
        self._writer.cues = self._animation.cues
        if cancel_writer:
            self._writer._bind_text(visible)
        if self._appearance is not None:
            self._appearance.reset()
        if self._uses_appearance() or self._first_visible_character:
            self._appearance = self._new_appearance()
            self._appearance.set_visible(visible < 0)
            if visible >= 0:
                self._appearance._set_visibility(np.arange(min(visible, self._appearance.buffer.character_count)), True, False)
        else:
            self._appearance = None
        self._writer.visibility_handler = self._publish_visibility
        count = self._animation._buffer.character_count
        self._animation.text.max_visible_characters = min(visible, count) if visible >= 0 else -1
        if self._max_visible_characters >= 0:
            self._animation.text.max_visible_characters = min(visible, self._max_visible_characters) if visible >= 0 else self._max_visible_characters
        self._sync_visibility_metadata()
        if self._behaviors_active and self._animation.has_effects:
            self._animation.sample(self._animation.time)
        self._schedule()
        return True

    def set_text(self, text: str, hide_text: bool = False) -> None:
        if not isinstance(hide_text, bool):
            raise TypeError("Hide text must be a bool")
        self._replace_text(text, 0 if hide_text else -1)

    def swap_text(self, text: str) -> None:
        previous = self._animation.text.max_visible_characters
        states = self._appearance._showing.copy() if self._visibility_overrides is not None else None
        if not self._replace_text(text, previous):
            return
        if states is not None:
            count = self._animation._buffer.character_count
            visible = np.zeros(count, dtype=np.bool_)
            visible[:min(count, len(states))] = states[:count]
            self._set_visibility(np.flatnonzero(~visible), False, False)

    def append_text(self, appended_text: str, hide_text: bool = False, skip_old_text: bool = True) -> None:
        if not isinstance(appended_text, str) or not isinstance(hide_text, bool) or not isinstance(skip_old_text, bool):
            raise TypeError("Append requires a string followed by two bools")
        if not appended_text:
            if skip_old_text:
                self.skip_typewriter()
            return
        animation, writer = self._animation, self._writer
        source, old_count = animation.source_text, animation._buffer.character_count
        old_cue_count = len(animation.cues)
        generation = writer._generation
        if skip_old_text:
            self.skip_typewriter()
            if self._animation is not animation or self._writer is not writer or writer._generation != generation:
                return
            if not writer._finished and writer._completion_time is not None:
                return
        visible = writer._count if writer._completion_time is not None else animation.text.max_visible_characters
        visible = old_count if skip_old_text or visible < 0 else min(visible, old_count)
        overrides = self._visibility_overrides.copy() if self._visibility_overrides is not None else None
        previous_appearance = self._appearance
        if previous_appearance is not None:
            previous_appearance.sample(max(previous_appearance.time, writer.playback_time))
        self._replace_text(source+appended_text, visible, cancel_writer=False)
        if overrides is not None:
            self._set_visibility(np.flatnonzero(overrides == 0), False, False)
            self._set_visibility(np.flatnonzero(overrides == 1), True, False)
        count = animation._buffer.character_count
        if not hide_text:
            self._set_visibility(np.arange(old_count, count), True, False)
        if self.typewriter and (hide_text or not skip_old_text and visible < old_count):
            writer._append(old_count, visible, animation.cues, old_cue_count, not skip_old_text)
            if self._appearance is not None:
                if previous_appearance is not None and not skip_old_text:
                    self._appearance.rebase_time(previous_appearance.time)
                    for name in ("_from", "_to", "_starts", "_durations", "_showing"):
                        getattr(self._appearance, name)[:old_count] = getattr(previous_appearance, name)
                    self._appearance.sample(previous_appearance.time)
                    writer._playback_clock = previous_appearance.time
                else:
                    self._appearance.rebase_time(writer.playback_time)
            writer.playing = self._playing and not writer._finished
            self._started_playback = True
        else:
            writer._cancel()
        self._sync_visibility_metadata()
        self._schedule()

    def resume_animation(self) -> None:
        if self._animation is None:
            raise RuntimeError("Enable TextAnimator before playback")
        self._playing = True
        if not self._started_playback:
            self._started_playback = True
            if self.typewriter:
                self.show_text(self._animation.source_text)
            elif self._appearance is not None and self._uses_appearance():
                self.play_appearance()
            if self._animation is None:
                return
        elif not self._writer.playing and self._writer._completion_time is not None:
            self._writer._resume()
        self._schedule()

    def pause_animation(self) -> None:
        self._playing = False
        if self._writer is not None:
            self._writer._stop()
        self._schedule()

    def set_typewriter_speed(self, value: float) -> None:
        if isinstance(value, bool):
            raise TypeError("Typewriter speed multiplier must be a number")
        if not isfinite(value) or value < 0.001:
            raise ValueError("Typewriter speed multiplier must be finite and at least 0.001")
        self.typewriter_speed = float(value)
        if self._writer is not None:
            self._writer.speed_multiplier = value

    def show_text(self, text: str) -> None:
        if not isinstance(text, str):
            raise TypeError("Text must be a string")
        self._started_playback = True
        self._playing = True
        if not self.typewriter:
            if not self._replace_text(text, -1):
                return
            if self._appearance is not None and self._uses_appearance():
                self.play_appearance()
            self._emit(self.on_text_showed)
            return
        self._hidden_pending = False
        self._visibility_overrides = None
        if self._appearance is not None and self._appearance.layout is self._animation.text.get_text_layout():
            self._appearance.sample(max(self._appearance.time, self._writer.playback_time))
        self._animation._set_text(text)
        self._animation._once_started = self._animation.time
        self._writer.cues = self._animation.cues
        if (self._uses_appearance() or self._first_visible_character) and self._appearance is None:
            self._appearance = self._new_appearance()
        elif not self._uses_appearance() and not self._first_visible_character and self._appearance is not None:
            self._appearance.reset()
            self._appearance = None
        self._writer.visibility_handler = self._publish_visibility
        self._reveal_floor = 0
        if self._appearance is not None:
            if self._appearance.layout is not self._animation.text.get_text_layout():
                self._appearance.refresh()
            self._configure_appearance()
            continuing = self._appearance.active
            if continuing:
                visible = self._animation.text.max_visible_characters
                self._reveal_floor = visible if visible >= 0 else self._appearance.buffer.character_count
            self._appearance.rebase_time(0)
            if continuing:
                self._appearance.hold()
            else:
                self._appearance.set_visible(False)
        self._writer.show_text(self._animation.text.text)
        if self._writer is None:
            return
        if self._appearance is not None:
            self._appearance.sample(max(self._appearance.time, self._writer.playback_time))
        self._schedule()

    def skip_typewriter(self) -> None:
        writer = self._writer
        if writer._finished and writer._completion_time is None:
            return
        generation = writer._generation
        writer.trigger_events_on_skip = self.trigger_events_on_skip
        writer.skip_typewriter()
        if self._writer is not writer or writer._generation != generation:
            return
        if self._appearance is not None:
            if writer._finished:
                self._visibility_overrides = None
                self._appearance.set_visible(not self._writer.hiding)
                if self._writer.hiding:
                    self._animation.text.max_visible_characters = 0
                    if self._hidden_pending:
                        self._hidden_pending = False
                        self._emit(self.on_text_disappeared)
            else:
                self._appearance.sample(writer.playback_time)
        self._schedule()

    def start_showing_text(self, restart: bool = False) -> None:
        if not isinstance(restart, bool):
            raise TypeError("Restart must be a bool")
        if restart or self._writer.hiding or self._writer._completion_time is None:
            self.show_text(self._animation.source_text)
        else:
            self.resume_animation()

    def stop_showing_text(self) -> None:
        if not self._writer.hiding:
            self._writer.stop_showing_text()
            self._schedule()

    def stop_disappearing_text(self) -> None:
        if self._writer.hiding:
            self._writer.stop_disappearing_text()
            self._schedule()

    def trigger_remaining_events(self) -> None:
        self._writer.trigger_remaining_events()

    def trigger_visible_events(self) -> None:
        self._writer.trigger_visible_events()

    def skip_current_action(self) -> bool:
        writer, generation = self._writer, self._writer._generation
        skipped = writer.skip_current_action()
        if self._writer is not writer or writer._generation != generation:
            return skipped
        if skipped and self._appearance is not None:
            self._appearance.sample(max(self._appearance.time, writer.playback_time))
        self._playing = writer.playing
        self._schedule()
        return skipped

    def get_approximate_show_duration(self) -> float:
        return self._writer.get_approximate_show_duration()

    def get_approximate_hide_duration(self) -> float:
        return self._writer.get_approximate_hide_duration()

    def start_disappearing_text(self) -> None:
        self._started_playback = True
        self._playing = True
        self._hidden_pending = False
        self._visibility_overrides = None
        self._reveal_floor = 0
        if self._appearance is not None:
            self._appearance.sample(max(self._appearance.time, self._writer.playback_time))
            self._configure_appearance()
            self._appearance.rebase_time(0)
        self._writer.start_disappearing_text()
        if self._writer is None:
            return
        if self._appearance is not None:
            self._appearance.sample(max(self._appearance.time, self._writer.playback_time))
        self._schedule()

    def play_appearance(self, showing: bool = True) -> None:
        if self._appearance is None or not self._uses_appearance():
            raise RuntimeError("Enable appearance animation in the Inspector first")
        self._hidden_pending = False
        self._appearance.sample(max(self._appearance.time, self._writer.playback_time))
        self._configure_appearance()
        self._writer._cancel()
        self._appearance.play(showing, stagger=self.appearance_stagger if showing else self.disappearance_stagger)
        self._started_playback = True
        self._playing = True
        self._schedule()

    def begin_preview(self, scope):
        if self._animation is not None:
            raise RuntimeError("Stop the active playback before starting an editor preview")
        text = self.game_object.get_component(UIText)
        scope.capture(self, "_preview", "_preview_registration", "_playing", "_animation", "_writer",
                      "_appearance", "_previous_visible_count", "_hidden_pending", "_sound", "_started_playback", "_reveal_floor",
                      "_visibility_overrides", "_behaviors_active", "_appearances_active", "_scheduled_by",
                      "_first_visible_character", "_max_visible_characters")
        scope.capture_text(text)
        scope.capture(text, "text")
        self._preview = True
        self.on_enable()
        if not self._playing:
            self.resume_animation()
        self._preview_registration = scope.add_update(lambda dt: self._tick(dt, dt))
        self._schedule()
        return self
