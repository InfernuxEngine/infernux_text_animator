# Infernux Text Animator

Official character animation plugin for native Infernux `UIText`. Independent of
the Tween plugin and the engine source repository. Requires Infernux **0.4.3
build 3 or later**, including native grapheme splitting and preload-library imports.
Install **Infernux Text Animator** from the official plugin catalog's Animation category.

The plugin provides batch wave, shake, wiggle, bounce, pulse, swing, tint and alpha effects,
grapheme/word typing, nested tags, marker events, appearance/disappearance and
manual character editing. `TextAnimator` uses native serialized lists and nested
independent entry/exit settings, with reversible Editor previews.

```python
from infernux_text_animator import Effect, EffectKind, TextAnimation, Typewriter

animation = TextAnimation(text, [Effect(EffectKind.Wave, amplitude=5, speed=0.8)])
writer = Typewriter(text, characters_per_second=30)
writer.ShowText("Hello 世界 e\u0301")

# In an InxComponent update(delta_time):
animation.Update(delta_time)
writer.Update(delta_time)
```

The engine supplies Unicode grapheme and glyph mapping. Revealing text changes
visibility rather than truncating strings. Persistent effects start from rest
geometry every frame, use one batch buffer per text, and preserve the separate
manual and appearance layers. There are no per-character GameObjects or tweens.
Word playback preserves the configured characters-per-second rate; reverse hiding
removes whole words from the visible end, including partially shown words.

Enable animation tags with `TextAnimation(text, parse_tags=True)` or the component's
Parse Tags setting. For example:
`<wave amplitude=2 speed=0.6>Hello <shake seed=7>世界</shake></wave>`.
Native `<color>` and `<size>` tags remain separate: enable `UIText.rich_text`
to render them. `<event=bell/>` emits a marker; `<wait=0.5/>` pauses the writer.
Markers preserve source order, including when a frame crosses several letters.
An action tag inside a word splits that word's reveal at the tag; untagged words
still appear together. A callback can pause or replace playback immediately.
Pause keeps the clock at that action, discards the rest of the current frame,
and freezes effects and appearance with it. Play resumes without repeating the
action. A paused writer can still skip; a new pause inside a skip stops it too.
`SkipTypewriter(trigger_events=False)` skips remaining marker and character callbacks.
`TextAnimator.SetTypewriterSpeed(2)` doubles the current typing rate without
restarting text or repeating events. The saved Typing Speed Multiplier also
applies when the component is enabled again. Values must be finite and positive;
use `Pause()` to stop. Each `Update` captures its multiplier, so a change from a
callback applies to the next advance. Character intervals and wait tags scale;
persistent effects and appearance durations retain their own timing.
The low-level equivalent is `writer.timeScale`. Its `elapsed_time` is the logical
typing clock; `playback_time` maps that clock through the rates used so far for
appearance timestamps. Skip can advance both clocks immediately.
Named effect presets can be configured in the Inspector or supplied as a mapping.
The Curve effect uses the native curve editor for offsets, rotation, scale or
alpha. Hermite tangents and clamp/repeat/ping-pong wrapping are compiled once;
character phases are sampled in one vectorized batch. Named presets retain
their curve when used as nested tags.

`CharacterAnimator(text)` owns one Manual-layer buffer. Select `Character(i)`,
`Range(start, count)`, `Word(i)` or `Line(i)`, then set offset, rotation, scale,
skew, corner offsets, RGBA or alpha and call `Apply()` once. Refresh selections
after layout changes. `CustomEffect(evaluator)` supplies a whole-range batch
callback; it creates no per-character objects.

`CharacterAppearance(text, Appearance(...), Appearance(...))` writes only the
Appearance layer, with independent incoming and outgoing profiles.
Fade, scale, offset, rotation, vertex expansion and seeded random direction can
be combined. `PlayAppearance(True/False)` uses the component's separate entry and
exit staggers and replaces the current typing pass. Typed characters instead
follow the configured typing intervals. Mid-animation reversals start from each
glyph's current offset, rotation, scale, alpha and vertices, even when the two
profiles differ. Updating profiles preserves the current visuals and adjusts
their remaining duration. Both phases use cubic-out easing.
The component coordinates appearances with rate-adjusted typewriter timestamps;
disappearing glyphs stay drawable until their animation finishes. Re-showing an
active native layout preserves its currently drawable glyphs; a different layout
gets a fresh buffer. This does not morph unrelated words into each other.
Glyphs waiting for the new reveal retain their current geometry; the replaced
hide no longer advances them in the background.
Pause stops this component's effects, typing and appearance. `SkipTypewriter`
finishes a typing pass; it does not finish a standalone `PlayAppearance` pass.
`on_character` carries `(index, grapheme)`;
`on_event` carries marker names. `on_complete` marks typing completion,
`on_hidden` waits for the outgoing visual animation, and `on_visual_complete`
marks a completed appearance pass. An optional existing AudioSource plays typing
sounds. Disable/unload restores authored text and visibility.

Add **Animation / Text Animator** to a `UIText` object to configure effects,
playback and typewriter settings in the Inspector. Disabling the component clears
its effects layer and restores the previous visibility limit.
In Edit mode, open **Animation / Text Animator** and select the object to preview,
pause or stop and restore. Preview does not emit gameplay events or play typing
audio. Save, Undo, changing selection and entering Play close the preview and
restore authored text before the editor operation continues.
Components share one owned engine callback. Paused, empty or completed typewriters
leave that callback inactive; each component does not carry an idle Update call.
Effect speed is cycles per second, `phase` is radians between characters and
`phase_offset` sets the initial phase. The animation always samples from rest data.

Develop with CPython 3.13: install `sdk-requirements.txt`, run `python -m pytest`,
then `python package.py`. Only `package/` enters the `.inxpkg`. Installed users
will need no pip, Git or compiler. See [maintenance](MAINTAINING.md).

The effect stages and typewriter interactions reference the public
[Text Animator documentation](https://tools.febucci.com/text-animator/unity/docs/quick-start/core-concepts).
The implementation uses Infernux APIs and contains no Unity or Febucci binaries.
