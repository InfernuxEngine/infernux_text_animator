# Infernux Text Animator

Official character animation plugin for native Infernux `UIText`. Independent of
the Tween plugin and the engine source repository. Requires Infernux **>=0.4.3**
with the **0.4.3 build 2** native-text hotfix installed.

**In development.** No public plugin version is advertised yet. The current core
provides batch wave, shake, wiggle, bounce, pulse, swing and alpha effects, plus
grapheme/word typewriter playback. Authoring components, effect tags, appearance
animation, presets and the remaining product/platform checks are in progress.

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

Develop with CPython 3.13: install `sdk-requirements.txt`, run `python -m pytest`,
then `python package.py`. Only `package/` enters the `.inxpkg`. Installed users
will need no pip, Git or compiler. See [maintenance](MAINTAINING.md).

The effect stages and typewriter interactions reference the public
[Text Animator documentation](https://tools.febucci.com/text-animator/unity/docs/quick-start/core-concepts).
The implementation uses Infernux APIs and contains no Unity or Febucci binaries.
