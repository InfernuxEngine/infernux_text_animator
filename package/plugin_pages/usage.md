# Text Animator

Requires Infernux 0.4.3 hotfix 4 or later. The preload checks the native character
color capability once and reports an explicit engine-update requirement.

Enable Parse Tags for `<wave a=2 s=0.6>text</wave>`, nested effects and named
Inspector presets. `<?name>` and `<waitfor=0.5>` drive typewriter actions.
Enable `UIText.rich_text` separately for native color/size tags.
Open effects extend to the end of the text; `</>` closes all persistent tags.
`<noparse>...</noparse>` leaves the enclosed tags literal. Native color/size/br
protection requires the engine's native `noparse` hotfix and rich-text mode.
`{fade}`, `{incr}`, `{slideh}`, `{rot}` apply incoming effects, while `{#fade}`,
`{#incr}`, `{#slideh}`, `{#rot}` apply outgoing effects. `{/}` and `{/#}` close
their categories. Overlapping ranges share one Appearance buffer and keep
independent channel timing: `{fade s=2}{incr}Hello{/}` fades twice as fast as it
grows. `a` changes strength; `s` changes speed. Base durations use the Inspector
profiles; native default strengths are full fade, zero-to-full scale, 8 local
units of horizontal offset and 90 degrees of rotation. These are native endpoint
effects. Every built-in and named CustomEffect also works in all three categories:
`<fade>`, `{wave}` and `{#wave}` share the same evaluators. Dynamic phases use
per-glyph local clocks and a finite envelope in the existing Appearance layer;
custom scalar-time evaluators are batched for glyphs sharing a clock.
Numeric modifiers support `a=5` assignment and `a*3` multiplication of the base
value. The last repeated modifier wins. `<wave once>` plays one native cycle,
clears its geometry and stops idle updates; a new Show can play it again.

Separate Appearance and Disappearance settings combine fade, size, offset,
rotation, vertex expansion and seeded random offsets. They animate each typed character and retain outgoing
glyphs until hiding finishes. character events can play an existing AudioSource.
`CharacterAnimator` edits characters, ranges, words or lines through one manual
buffer; call `apply()` once after multiple edits.
Manual color/alpha edits are absolute; element and parent opacity remain separate.

`TextAnimation(text, effects)` binds effects to an existing `UIText`.
Call `update(delta_time)` or `sample(time)`; `reset()` clears only its effects
layer. `Effect` supports an optional character range, amplitude, speed, character
phase and initial phase offset. Speed is cycles per second; phases are radians.
Offsets use local text coordinates, with positive Y pointing down.

`Typewriter(text).show_text(value)` starts a reveal. `stop_showing_text` pauses,
`start_showing_text` resumes, `skip_typewriter` finishes, and
`start_disappearing_text` hides visible characters. Set `on_typewriter_start`, `on_character_visible`,
`on_text_showed` or `on_text_disappeared` for events. Skip events are opt-in.

Skipping also finishes paused playback. Completion is emitted once; calling
`skip_typewriter` again does not repeat it. Set `trigger_events_on_skip = True` before skipping to
dispatch remaining reveal-character and marker callbacks. The component's
`pause_animation()` and `resume_animation()` control its effects, typewriter and appearance together;
the low-level `Typewriter` is advanced explicitly with `update(delta_time)`.
Character events use native displayed graphemes: a rich-text `<br>` produces a
newline, and whitespace does not play typing audio. Updating appearance settings
preserves the current reveal/hide phase and pause state. `set_effects([])` clears
the Effects layer while preserving Manual and Appearance layers.

Markers follow text order, including inside words. A marker splits a word's
reveal; ordinary words still appear together. Pause from any callback stops that
frame at the callback, including effects and appearance. Play continues without
repeating it. Skip works while paused; another pause during Skip stops it there.
`show_text(text)` can replace an unfinished hide. Changing only tags rebinds effects and
events while retaining the native layout; removing effects clears their layer.

`TextAnimator.set_typewriter_speed(2)` doubles the current typing rate without
restarting it. Typing Speed Multiplier is saved independently of Characters Per
Second and survives disable/enable. Use a finite multiplier of at least 0.001; use pause_animation
to stop. Each advance captures its rate, so a callback change starts with the next
advance. Wait tags scale too; effects and appearance durations do not.
For a low-level writer, assign `speed_multiplier`. `elapsed_time` is logical typing time;
`playback_time` is the rate-adjusted presentation time used for glyph animation.
Skipping can advance these clocks without waiting.

Configure entry and exit duration, transforms and random seed independently.
`play_appearance()` and `play_appearance(False)` replace typing with a whole-text
visual pass and use Whole-text Entry/Exit Stagger respectively. During typing,
glyph starts follow the typing intervals instead. Reversing an unfinished pass
continues from current glyph geometry in the same Appearance layer. Re-showing
an active layout retains drawable glyphs; a different layout starts fresh rather
than morphing unrelated text. Pending glyphs hold their geometry until the new
reveal reaches them; the replaced hide does not continue. Live profile edits retain the current visual state
and adjust the remaining duration. Both profiles use cubic-out easing.
`pause_animation()`/`resume_animation()` also work on standalone visual passes; `skip_typewriter()` only skips a
typing pass.

```python
animator.appearance.duration = 0.3
animator.appearance.offset = (0, 12)
animator.disappearance.duration = 0.1
animator.disappearance.offset = (-8, 0)
animator.set_typewriter_speed(2)
animator.show_text("Hello 世界")
# Later: animator.start_disappearing_text()
```

For manual character geometry:

```python
from infernux_text_animator import CharacterAnimator

characters = CharacterAnimator(label)
characters.word(0).offset((0, -8)).rotate(-5)
characters.range().alpha(0.8)
characters.apply()
```

The Manual, Effects and Appearance layers compose in that order. Use one
Manual-layer controller per label. Refresh selections after changing layout,
and call `reset()` when its manual geometry is no longer needed.

Add **Animation / Text Animator** to a UIText to edit the native serialized effect
list and typewriter settings. Components share an update entry per phase; paused, empty or
completed playback disables idle work. Open **Animation / Text Animator** in Edit
mode to preview the selected component. Stop restores authored text; Save, Undo,
selection changes and entering play also end previews before proceeding. Preview
does not send gameplay events or play typing sounds.

All public functions use `snake_case`, with no old aliases. Control methods return
`None`: `show_text(text: str)` requires a string; `start_showing_text(restart=False)`
resumes, or restarts when passed `True`. `stop_showing_text()` and
`stop_disappearing_text()` stop their respective direction. `skip_typewriter()`
takes no arguments. `trigger_visible_events()`/`trigger_remaining_events()` send
undelivered markers without revealing characters. `skip_current_action()` returns
whether an active timed wait, input wait or custom action was skipped, cancelling
the custom action when applicable. Approximate show/hide duration queries omit
tags, callbacks and appearance durations.
Stopping a typewriter direction leaves persistent effects and current glyph
transitions running. `pause_animation()` freezes the whole component instead.

`on_character_visible` receives one `CharacterData` with `index`,
`info.character` (the Unicode grapheme) and `info.native` (native layout metadata).
`on_message` receives one `EventMarker`, containing `name: str` and
`parameters: list[str]`: `<?reward=10,gold>` preserves `"10"` as a string.
`on_typewriter_start`, `on_text_showed` and `on_text_disappeared` have no arguments.
`on_character_wait_started` and `on_character_wait_finished` receive
`(CharacterData, WaitMode)` and can pause/replace the run at that boundary.
`WaitMode.APPEARANCE` and `DISAPPEARANCE` currently denote native playback directions.
The referenced official Unity API does not publish the core enum members, so their
upstream names, values and meaning remain unverified pending an authorized core
package. This is an open contract item, not a claim of complete enum parity.

The component provides immediate replacement with `set_text(text: str,
hide_text: bool = False)` and visibility-preserving replacement with
`swap_text(text: str)`. `append_text(appended_text: str, hide_text: bool = False,
skip_old_text: bool = True)` appends without repeating old markers. With
`skip_old_text=False`, old typing waits and appearance progress continue;
`hide_text=False` makes the new tail immediately visible.

`set_visibility_char(index: int, is_visible: bool, can_play_effects: bool = True)`,
`set_visibility_word(index: int, is_visible: bool, can_play_effects: bool = True)`
and `set_visibility_entire_text(is_visible: bool, can_play_effects: bool = True)`
control native graphemes, words or the complete label. False effect control makes
the change immediate. Individual overrides remain effective while typing proceeds,
using the existing Appearance layer. `set_appearances_active(is_category_enabled:
bool)` snaps semantic visibility when disabled; `set_behaviors_active(
is_category_enabled: bool)` clears/re-enables only persistent effects. Both retain
their configuration. These component controls return `None`.
`is_animation_paused` reports the state controlled by `pause_animation()` and
`resume_animation()`. The signature baseline is the public Text Animator for Unity
3.22.1 base component/typewriter API; native effect/profile helpers retain their
Infernux semantics.

`<speed=2>` changes the rate of subsequent typing in the same update, even across
a long frame. It multiplies the saved typing rate locally to the current run;
it does not accelerate effects or appearances or overwrite the saved multiplier.
`<waitinput>` stops typing until a new input arrives in a later native input frame.
Effects and already-started glyph transitions continue. Skip and
`skip_current_action()` can pass input barriers.
`input_mode` takes `WaitInputMode.ANY_INPUT` (default) or `SPECIFIC_ACTION`.
For specific input, assign native `InputAction` objects to `input_actions` by string
key: `<waitinput=confirm>` queries that action's `was_pressed_this_frame` state.
Without a parameter it uses `default_input_key`; `any` always selects any input.
Missing action keys are configuration errors, never implicit physical bindings.

`animation_loop` takes `AnimationLoop.UPDATE`, `LATE_UPDATE` or `SCRIPT`
(0, 1, 2). Automatic callbacks run in the selected native phase. Script mode
leaves automatic updates disabled; `animate(delta_time: float) -> None` advances
playing animation manually. `pause_animation()` freezes manual advances too.

The component exposes `characters`, `characters_count`, `words` and `words_count`
from its current native binding. `CharacterData.is_visible` is semantic visibility,
including individual flags and the independent `first_visible_character` /
`max_visible_characters` bounds (`-1` is unlimited). Changing bounds preserves
individual flags. `all_letters_shown`, `any_letter_visible`,
`latest_character_shown` and the showing/hiding/waiting properties report state.
The latest record is `None` before a reveal or for empty text.
`text_full` retains source tags, `text_without_text_anim_tags` retains native
rich text, and `text_without_any_tag` is actual native display text. Native tags
stay literal if native rich-text parsing is disabled. Replacing text rebinds its
records and events; explicit marker dispatch cannot publish an earlier text's cues.

Use enum members for API configuration: `EffectKind.WAVE`,
`CurveTarget.OFFSET_Y`, `TimeScale.SCALED`/`UNSCALED`. Their stored values are
stable; raw strings are not accepted as enum arguments. Tag names remain strings
in markup. `time_scale` selects scaled or unscaled engine time, while
`speed_multiplier` is the separate numeric typing rate.
`TextAnimation.set_text(text: str, hide_text: bool = False)` shows/hides immediately;
its boolean is not TMP's text-input synchronization flag. Native batch selection
and appearance profiles are Infernux extensions. Custom effects can also edit
native affine transforms and vertex depth.

`all_letters_shown` waits for appearance completion as well as semantic flags.
`any_letter_visible` stays true while outgoing glyphs have visible alpha.
`trigger_visible_events()` respects first/maximum bounds and individual masks;
remaining-event dispatch is independent of visibility.

`appearances`, `behaviors` and `disappearances` return native `TextRegion(start,
end, effect)` records for the actually applied ranges, including defaults.
`default_tags_mode` takes `DefaultEffectsMode.FALLBACK` (only untagged ranges) or
`CONSTANT` (combine). These enum values are native configuration strings; no
unpublished upstream numeric values are assumed. `use_dynamic_scaling=True`
scales pixel offsets and vertices by `UIText.font_size/reference_font_size`;
the native reference size is 18. Dimensionless color/scale/rotation are unchanged.

`try_initializing_once()` binds without replaying an existing run.
`force_database_refresh()` reparses changed presets/styles;
`refresh_all_effect_states()` applies settings while preserving current effects
and pause. A changed cue sequence or layout requires a new typing binding.
`schedule_mesh_refresh()` schedules one geometry refresh even while paused,
without advancing the clock. All four controls take no arguments and return None.

Add named custom effects to `database_effects` and named action factories to
`database`. A factory implements `create_action_from(ActionMarker, object) ->
ActionState`; its state implements `progress(float, TypingInfo) -> ActionStatus`
and `cancel() -> None`. Return `ActionStatus.RUNNING` or `FINISHED`, never a raw
string. Marker parameters remain strings. Pausing retains the state; skip, text
replacement and disable cancel it. Custom completion consumes its supplied
progress delta; subsequent letters start at that update boundary. The native
`TypingInfo` carries the owner, presentation time and writable typing speed.

Assign `timing_settings = TypingDelaysByCharacter()` / `TypingDelaysByWord()`, or
subclass `TypingTimings`. Implement `get_wait_appearance_time_of(character,
animator) -> float`; the disappearance method defaults to the same wait and can
be overridden. Policies operate on typed native CharacterData. Changing policy
rebuilds future groups at the current character-wait boundary without cue replay.
`style_sheet["accent"] = TextStyle("<wave>", "</wave><?done>")` expands
case-insensitive opening/closing style tags; `noparse` still protects raw text.

These Python protocols implement the public
[custom action](https://tools.febucci.com/text-animator/unity/docs/writing-custom-classes/writing-custom-actions-c)
and [typing wait](https://tools.febucci.com/text-animator/unity/docs/writing-custom-classes/writing-custom-typing-waits-c)
extension points without ScriptableObject assets. Exact upstream
`StartTypewriterMode` flags remain unverified, like the core `WaitMode` members;
native auto-play and explicit controls do not claim an equivalent flag type.
