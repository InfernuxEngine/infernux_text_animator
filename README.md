# Infernux Text Animator

Official character animation plugin for native Infernux `UIText`. Independent of
the Tween plugin and the engine source repository. Requires Infernux **0.4.3
hotfix 4 or later**, including native grapheme splitting, protected markup,
affine character geometry and independent absolute character color/opacity.
Install **Infernux Text Animator** from the official plugin catalog's Animation category.

The plugin provides batch wave, shake, wiggle, bounce, pulse, swing, tint and alpha effects,
grapheme/word typing, nested tags, marker events, appearance/disappearance and
manual character editing. `TextAnimator` uses native serialized lists and nested
independent entry/exit settings, with reversible Editor previews.

```python
from infernux_text_animator import Effect, EffectKind, TextAnimation, Typewriter

animation = TextAnimation(text, [Effect(EffectKind.WAVE, amplitude=5, speed=0.8)])
writer = Typewriter(text, characters_per_second=30)
writer.show_text("Hello 世界 e\u0301")

# In an InxComponent update(delta_time):
animation.update(delta_time)
writer.update(delta_time)
```

The engine supplies Unicode grapheme and glyph mapping. Revealing text changes
visibility rather than truncating strings. Persistent effects start from rest
geometry every frame, use one batch buffer per text, and preserve the separate
manual and appearance layers. There are no per-character GameObjects or tweens.
Word playback preserves the configured characters-per-second rate; reverse hiding
removes whole words from the visible end, including partially shown words.

Enable animation tags with `TextAnimation(text, parse_tags=True)` or the component's
Parse Tags setting. For example:
`<wave a=2 s=0.6>Hello <shake seed=7>世界</shake></wave>`.
Native `<color>` and `<size>` tags remain separate: enable `UIText.rich_text`
to render them. `<?bell>` emits a marker; `<waitfor=0.5>` pauses the writer.
Persistent tags can run to the end without a closing tag; `</>` closes every
open persistent effect. `<noparse>...</noparse>` keeps enclosed tags literal.
Its protection also covers native color/size/br markup when using the engine's
native `noparse` hotfix with `UIText.rich_text=True`.
Modifiers support both assignment (`a=5`) and multiplication of the configured
base value (`a*3`). Repeating the same modifier keeps the last occurrence rather
than multiplying previous occurrences together. `<wave once>` runs one native
cycle, clears its contribution and removes idle updates when nothing else is
active. A new Show starts the one-shot effect again.

`{fade}`, `{incr}`, `{slideh}` and `{rot}` select native incoming character
effects; `{#fade}`, `{#incr}`, `{#slideh}` and `{#rot}` select outgoing effects.
Use `{/}` and `{/#}` to close the open tags in each category. These ranges work
without enabling the component's default appearance profile. They can overlap:
`{fade s=2}{incr}Hello{/}` fades each glyph in twice as fast as it grows.
`a` scales a tag's strength; `s` is its positive speed multiplier. Native defaults
use a full fade, zero-to-full size, an 8-unit horizontal slide or a 90-degree
rotation. Inspector entry/exit durations set their base time. The endpoint,
curve and timing definitions belong to Infernux. Every built-in effect and named
`CustomEffect` preset can be used in all three categories: for example `<fade>`,
`{wave}` or `{#wave}`. Dynamic incoming/outgoing effects sample each glyph's local
phase clock and return to rest through a finite envelope. The same batch evaluator
handles planar transforms, per-corner color, affine transforms and vertex depth;
only one Appearance layer is submitted. Custom evaluators still receive scalar
time and a contiguous selection, grouping glyphs that share the same phase clock.
The complete upstream sample asset/playback database is not bundled.
Markers preserve source order, including when a frame crosses several letters.
An action tag inside a word splits that word's reveal at the tag; untagged words
still appear together. A callback can pause or replace playback immediately.
Pause keeps the clock at that action, discards the rest of the current frame,
and freezes effects and appearance with it. Play resumes without repeating the
action. A paused writer can still skip; a new pause inside a skip stops it too.
`skip_typewriter()` has no parameters. Set `trigger_events_on_skip = True` before
calling it to dispatch remaining marker and character callbacks; the default is false.
`TextAnimator.set_typewriter_speed(2)` doubles the current typing rate without
restarting text or repeating events. The saved Typing Speed Multiplier also
applies when the component is enabled again. Values must be finite and at least 0.001;
use `pause_animation()` to stop the component. Each `update` captures its multiplier, so a change from a
callback applies to the next advance. Character intervals and wait tags scale;
persistent effects and appearance durations retain their own timing.
The low-level equivalent is `writer.speed_multiplier`. Its `elapsed_time` is the logical
typing clock; `playback_time` maps that clock through the rates used so far for
appearance timestamps. Skip can advance both clocks immediately.
Named effect presets can be configured in the Inspector or supplied as a mapping.
The Curve effect uses the native curve editor for offsets, rotation, scale or
alpha. Hermite tangents and clamp/repeat/ping-pong wrapping are compiled once;
character phases are sampled in one vectorized batch. Named presets retain
their curve when used as nested tags.

`CharacterAnimator(text)` owns one Manual-layer buffer. Select `character(i)`,
`range(start, count)`, `word(i)` or `line(i)`, then set offset, rotation, scale,
skew, corner offsets, RGBA or alpha and call `apply()` once. Refresh selections
after layout changes. `CustomEffect(evaluator)` supplies a whole-range batch
callback; it creates no per-character objects.
Manual `color()` and `alpha()` set absolute glyph color/alpha. Element and parent
opacity remain independent; persistent and appearance colors multiply this result.

`CharacterAppearance(text, Appearance(...), Appearance(...))` writes only the
Appearance layer, with independent incoming and outgoing profiles.
Fade, scale, offset, rotation, vertex expansion and seeded random direction can
be combined. `play_appearance(True/False)` uses the component's separate entry and
exit staggers and replaces the current typing pass. Typed characters instead
follow the configured typing intervals. Mid-animation reversals start from each
glyph's current offset, rotation, scale, alpha and vertices, even when the two
profiles differ. Updating profiles preserves the current visuals and adjusts
their remaining duration. Both phases use cubic-out easing. A nonpositive phase
duration completes immediately, including when changed during playback; it does
not leave a stagger delay or retain a partially transformed glyph.
The component coordinates appearances with rate-adjusted typewriter timestamps;
disappearing glyphs stay drawable until their animation finishes. Re-showing an
active native layout preserves its currently drawable glyphs; a different layout
gets a fresh buffer. This does not morph unrelated words into each other.
Glyphs waiting for the new reveal retain their current geometry; the replaced
hide no longer advances them in the background.
Pause stops this component's effects, typing and appearance. `skip_typewriter`
finishes a typing pass; it does not finish a standalone `play_appearance` pass.
`on_character_visible` carries one `CharacterData`: `index`, `info.character`
(the displayed grapheme), and `info.native` (the native `TextCharacterInfo`).
`on_message` carries one `EventMarker` with `name: str` and `parameters: list[str]`.
For example, `<?reward=10,gold>` retains `"10"` as a string; it does not become an
integer or enum. Both payloads are bound once per text run, rather than per frame.
`on_typewriter_start` and `on_text_showed` have no arguments; the latter marks typing completion,
`on_text_disappeared` waits for the outgoing visual animation, and `on_visual_complete`
marks a completed appearance pass. An optional existing AudioSource plays typing
sounds. Disable/unload restores authored text and visibility.

Add **Animation / Text Animator** to a `UIText` object to configure effects,
playback and typewriter settings in the Inspector. Disabling the component clears
its effects layer and restores the previous visibility limit.
In Edit mode, open **Animation / Text Animator** and select the object to preview,
pause or stop and restore. Preview does not emit gameplay events or play typing
audio. Save, Undo, changing selection and entering Play close the preview and
restore authored text before the editor operation continues.
Components share an owned callback for each automatic phase. Paused, empty or
completed playback leaves those callbacks inactive; components carry no idle update.
Effect speed is cycles per second, `phase` is radians between characters and
`phase_offset` sets the initial phase. The animation always samples from rest data.

All functions use `snake_case`; there are no PascalCase aliases. Classes retain
PascalCase. `EffectKind` and `CurveTarget` are enums with uppercase members and
stable values; pass `EffectKind.WAVE`, not `"wave"`, to `Effect`. Tag names are
strings at the markup boundary. The component's `time_scale` takes
`TimeScale.SCALED` or `TimeScale.UNSCALED`; the numeric typing multiplier is the
separate `speed_multiplier` / `set_typewriter_speed` API.

`<speed=2>` multiplies the typing rate for the following part of the current run.
The writer accounts for a rate change even when one update crosses the tag and
several characters. This multiplier is local to the text run; it does not modify
the saved Typing Speed Multiplier, and effects/appearances keep real-time timing.
`<waitinput>` blocks typing until a later native input frame provides a new key,
mouse press or touch. It does not freeze effects or appearances. Skip and
`skip_current_action()` can pass that input barrier.

In `WaitInputMode.SPECIFIC_ACTION`, `<waitinput=confirm>` queries
`input_actions["confirm"].was_pressed_this_frame` on an existing native
`InputAction`. Omitting the parameter uses `default_input_key`; the reserved
`any` parameter uses any input. The default mode is `WaitInputMode.ANY_INPUT`.
An unknown specific key is a configuration error, not an implicit key binding.

```python
from infernux.input import InputAction, KeyCode
from infernux_text_animator import WaitInputMode

animator.input_mode = WaitInputMode.SPECIFIC_ACTION
animator.input_actions["confirm"] = InputAction("Confirm").bind_key(KeyCode.SPACE)
animator.default_input_key = "confirm"
animator.show_text("Ready?<waitinput><speed=2> Let's go.")
```

`animation_loop` uses `AnimationLoop.UPDATE`, `LATE_UPDATE` or `SCRIPT`
(values 0, 1 and 2). The first two use owned callbacks in their actual engine
phase; Script removes automatic ticking. Call `animate(delta_time: float) ->
None` to advance manually while the component is playing. `pause_animation()`
also stops manual advancement. Each automatic phase shares a callback, and an
empty phase leaves its callback disabled.

The typewriter control signatures follow the public Text Animator for Unity
3.22.1 API, adapted to native `UIText` and Python overloads:

```python
show_text(text: str) -> None
start_showing_text(restart: bool = False) -> None
stop_showing_text() -> None
start_disappearing_text() -> None
stop_disappearing_text() -> None
skip_typewriter() -> None
set_typewriter_speed(value: float) -> None
skip_current_action() -> bool
trigger_remaining_events() -> None
trigger_visible_events() -> None
get_approximate_show_duration() -> float
get_approximate_hide_duration() -> float
```

`show_text` requires text; use `start_showing_text()` to start/resume the current
run or `start_showing_text(True)` to restart it. Control methods return `None`.
The component's `pause_animation()`/`resume_animation()` control all its animation stages together.
Explicit marker dispatch does not reveal characters, advance the clock, or
repeat already-dispatched markers. `skip_current_action()` skips an active timed
wait, input wait or custom action, cancelling the custom action when applicable,
and returns false when none is active. Wait callbacks receive `(CharacterData,
WaitMode)`. The current native adapter uses `APPEARANCE`/`DISAPPEARANCE` playback
directions. **The official core `WaitMode` members are not published on the
referenced Unity API page and have not been verified from an authorized package.**
Matching that enum's members and meaning remains an open API-contract item;
the current names and values must not be presented as confirmed upstream parity.
`stop_showing_text()`/`stop_disappearing_text()` stop only typing in the matching
direction. Persistent effects and an already-started glyph transition continue;
use `pause_animation()` to freeze the entire component.

The native component also implements these base operations with the documented
argument order and defaults:

```python
set_text(text: str, hide_text: bool = False) -> None
append_text(appended_text: str, hide_text: bool = False, skip_old_text: bool = True) -> None
swap_text(text: str) -> None
set_visibility_char(index: int, is_visible: bool, can_play_effects: bool = True) -> None
set_visibility_word(index: int, is_visible: bool, can_play_effects: bool = True) -> None
set_visibility_entire_text(is_visible: bool, can_play_effects: bool = True) -> None
pause_animation() -> None
resume_animation() -> None
set_appearances_active(is_category_enabled: bool) -> None
set_behaviors_active(is_category_enabled: bool) -> None
animate(delta_time: float) -> None
try_initializing_once() -> None
force_database_refresh() -> None
refresh_all_effect_states() -> None
schedule_mesh_refresh() -> None
```

`set_text` replaces immediately and cancels the previous typing pass. `swap_text`
retains the visible prefix, or an explicitly edited per-character visibility mask,
on the new native glyph indices. `append_text` can reveal the old part immediately
or preserve its remaining waits, marker order and appearance progress; `hide_text`
chooses whether the appended part waits for typing or is visible immediately.
Visibility indices are native Unicode graphemes/words, not source-string offsets.
`can_play_effects=False` applies visibility immediately. Character visibility and
appearance reuse one Appearance-layer buffer; disabling the appearance category
keeps semantic visibility while removing animated transitions. Disabling behaviors
clears only the Effects layer and preserves its effect configuration. Paused or
completed components do not retain an idle scheduler callback.

Read `characters: list[CharacterData]`, `characters_count`, `words` (native
`TextWordInfo` records) and `words_count` for the current native layout.
Character records are created once per binding and expose semantic `is_visible`;
it respects individual flags and the independent `first_visible_character` /
`max_visible_characters` bounds. `-1` means no maximum in the native API. These
range bounds do not overwrite individual character flags. `all_letters_shown`,
`any_letter_visible` and `latest_character_shown` describe the reveal state.
`all_letters_shown` also waits for appearance effects to finish; outgoing glyphs
with nonzero rendered alpha keep `any_letter_visible` true until they disappear;
the last record is `None` before a character is shown or for empty text.
`is_showing_text`, `is_hiding_text` and `is_waiting_for_action` expose playback
state. `text_full` keeps source tags, `text_without_text_anim_tags` keeps native
rich-text markup, and `text_without_any_tag` is the actual native display text.
Native tags remain literal when native rich-text parsing is disabled.

`appearances`, `behaviors` and `disappearances` return native `TextRegion` records
with `start`, exclusive `end` and the actual `effect`/profile. The lists include
defaults on the ranges where they apply. `DefaultEffectsMode.FALLBACK` applies
defaults only where that category has no explicit tag; `CONSTANT` combines them
with explicit effects. These enum values are the native configuration strings
`"fallback"` and `"constant"`, not an assertion about unpublished upstream numeric
values. By default, effects' pixel offsets and vertices scale by
`UIText.font_size / reference_font_size` (native reference size: 18).
`use_dynamic_scaling=False` retains authored pixel amplitudes. Scale, rotation and
color amplitudes are dimensionless and do not change with font size.

`try_initializing_once()` binds native text without replaying an initialized run.
`force_database_refresh()` reparses current tags against changed named presets or
styles; `refresh_all_effect_states()` updates live settings while retaining phase
and pause state. A changed cue sequence or native layout establishes a fresh
typing binding. `schedule_mesh_refresh()` reapplies the native geometry at the
next loop, including a single refresh while paused, without advancing playback.

Custom effects can be installed programmatically in
`animator.database_effects["custom"] = CustomEffect(evaluator)`. Their `a`, `s`
and `once` modifiers use the same path in all categories. `style_sheet` maps names
to `TextStyle(opening, closing)`. For example,
`TextStyle("<wave><?begin>", "</wave><?end>")` expands a case-insensitive style tag
into effects and ordered typing cues; styles are not expanded inside `noparse`.

`timing_settings` accepts a `TypingTimings` object. Implement
`get_wait_appearance_time_of(character: CharacterData, animator: object) -> float`
and optionally `get_wait_disappearance_time_of(character, animator) -> float`.
The latter defaults to the appearance wait. `TypingDelaysByCharacter` and
`TypingDelaysByWord` provide replaceable native policies, including punctuation
and independent disappearance waits. Changing policy while running takes effect
at the current character-wait boundary and rebuilds the remaining groups without
replaying cues. Approximate durations sum the active policy's character waits.

`database: dict[str, TypewriterAction]` registers custom action factories.
`create_action_from(marker: ActionMarker, typewriter: object) -> ActionState`
creates one state per encountered tag. `ActionMarker` retains the configured
name and string parameters. A state implements
`progress(delta_time: float, typing_info: TypingInfo) -> ActionStatus` and
`cancel() -> None`; return `RUNNING` to block, `FINISHED` to continue. These are
typed enum members, not strings. Native `TypingInfo` exposes the owner, elapsed
presentation time and writable typing `speed`. State progress receives logical
typing delta, including speed modifiers. A custom completion consumes the delta
given to that progress call; following letters start at the resulting update
boundary. Pausing preserves the state; skipping, replacing text or disabling
cancels it exactly once. Factory/progress/cancel callbacks can pause or replace
playback, and the superseded run does not continue publishing.

The public action and timing protocols map the corresponding upstream extension
points into Python objects. They do not recreate ScriptableObject assets. The
official core `StartTypewriterMode` flag definitions, like `WaitMode`, are not
available in the referenced public API or a local authorized package; exact enum
parity remains unverified. Native auto-play and explicit Show/Start controls work
without claiming a matching upstream flag type.

The baseline is the public **Text Animator for Unity 3.22.1**
[typewriter](https://tools.febucci.com/text-animator/unity/api/febucci/text-animator-for-unity/typewriter-component)
and [base component](https://tools.febucci.com/text-animator/unity/api/febucci/text-animator-for-unity/text-animator-component-base)
API. Native authoring lists, curves, geometry helpers and effect kinds are Infernux
APIs, rather than substitute declarations for Unity settings/database classes.

`TextAnimation.set_text(text: str, hide_text: bool = False)` returns `None` and
immediately shows or hides the new text. The bool is a visibility control, not
TMP's text-input synchronization flag. Native batch helpers such as
`CharacterAnimator.range(start=0, count=None)` and `CharacterAppearance` remain
Infernux extensions, with planar offsets and rotation; fluent selection/editing
helpers return their controller. There is no second TMP-style component tree.

Develop with CPython 3.13: install `sdk-requirements.txt`, run `python -m pytest`,
then `python package.py`. Only `package/` enters the `.inxpkg`. Installed users
will need no pip, Git or compiler. See [maintenance](MAINTAINING.md).

The effect stages and typewriter interactions reference the public
[Text Animator documentation](https://tools.febucci.com/text-animator/unity/docs/quick-start/core-concepts).
The implementation uses Infernux APIs and contains no Unity or Febucci binaries.
