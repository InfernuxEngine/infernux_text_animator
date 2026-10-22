# Infernux Text Animator

Official character animation plugin for native Infernux `UIText`. Independent of
the Tween plugin and the engine source repository. Requires Infernux **>=0.4.3**
with the **0.4.3 build 2** native-text hotfix installed.
Project-script imports additionally need the preload-library import fix currently
under verification in the engine. No public plugin release is available yet.

**In development.** No public plugin version is advertised yet. The current core
provides batch wave, shake, wiggle, bounce, pulse, swing, tint and alpha effects,
grapheme/word typing, nested tags, marker events, appearance/disappearance and
manual character editing. `TextAnimator` uses native serialized lists and nested
appearance settings. Editor preview, curve authoring and the remaining
product/platform checks are still in progress.

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
`SkipTypewriter(trigger_events=False)` skips remaining marker and character callbacks.
Named effect presets can be configured in the Inspector or supplied as a mapping.

`CharacterAnimator(text)` owns one Manual-layer buffer. Select `Character(i)`,
`Range(start, count)`, `Word(i)` or `Line(i)`, then set offset, rotation, scale,
skew, corner offsets, RGBA or alpha and call `Apply()` once. Refresh selections
after layout changes. `CustomEffect(evaluator)` supplies a whole-range batch
callback; it creates no per-character objects.

`CharacterAppearance(text, Appearance(...))` writes only the Appearance layer.
Fade, scale, offset, rotation, vertex expansion and seeded random direction can
be combined. The component coordinates appearances with typewriter timestamps;
disappearing glyphs stay drawable until their animation finishes. Pausing stops
all three layers' playback. `on_character` carries `(index, grapheme)`;
`on_event` carries marker names. `on_complete` marks typing completion,
`on_hidden` waits for the outgoing visual animation, and `on_visual_complete`
marks a completed appearance pass. An optional existing AudioSource plays typing
sounds. Disable/unload restores authored text and visibility.

Add **Animation / Text Animator** to a `UIText` object to configure effects,
playback and typewriter settings in the Inspector. Disabling the component clears
its effects layer and restores the previous visibility limit.
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
