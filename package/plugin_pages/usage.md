# Text Animator

Enable Parse Tags for `<wave amplitude=2>text</wave>`, nested effects and named
Inspector presets. `<event=name/>` and `<wait=0.5/>` drive typewriter actions.
Enable `UIText.rich_text` separately for native color/size tags.

Separate Appearance and Disappearance settings combine fade, size, offset,
rotation, vertex expansion and seeded random offsets. They animate each typed character and retain outgoing
glyphs until hiding finishes. Character events can play an existing AudioSource.
`CharacterAnimator` edits characters, ranges, words or lines through one manual
buffer; call `Apply()` once after multiple edits.

`TextAnimation(text, effects)` binds effects to an existing `UIText`.
Call `Update(delta_time)` or `Sample(time)`; `Reset()` clears only its effects
layer. `Effect` supports an optional character range, amplitude, speed, character
phase and initial phase offset. Speed is cycles per second; phases are radians.
Offsets use local text coordinates, with positive Y pointing down.

`Typewriter(text).ShowText(value)` starts a reveal. `StopShowingText` pauses,
`StartShowingText` resumes, `SkipTypewriter` finishes, and
`StartDisappearingText` hides visible characters. Set `on_start`, `on_character`,
`on_complete` or `on_hidden` for events. Skip events are opt-in.

Skipping also finishes paused playback. Completion is emitted once; calling
`SkipTypewriter` again does not repeat it. `trigger_events=True` additionally
dispatches remaining reveal-character and marker callbacks. The component's
`Pause()` and `Play()` control its effects, typewriter and appearance together;
the low-level `Typewriter` is advanced explicitly with `Update(delta_time)`.
Character events use native displayed graphemes: a rich-text `<br>` produces a
newline, and whitespace does not play typing audio. Updating appearance settings
preserves the current reveal/hide phase and pause state. `SetEffects([])` clears
the Effects layer while preserving Manual and Appearance layers.

Markers follow text order, including inside words. A marker splits a word's
reveal; ordinary words still appear together. Pause from any callback stops that
frame at the callback, including effects and appearance. Play continues without
repeating it. Skip works while paused; another pause during Skip stops it there.
ShowText can replace an unfinished hide. Changing only tags rebinds effects and
events while retaining the native layout; removing effects clears their layer.

`TextAnimator.SetTypewriterSpeed(2)` doubles the current typing rate without
restarting it. Typing Speed Multiplier is saved independently of Characters Per
Second and survives disable/enable. Use a positive finite multiplier; use Pause
to stop. Each advance captures its rate, so a callback change starts with the next
advance. Wait tags scale too; effects and appearance durations do not.
For a low-level writer, assign `timeScale`. `elapsed_time` is logical typing time;
`playback_time` is the rate-adjusted presentation time used for glyph animation.
Skipping can advance these clocks without waiting.

Configure entry and exit duration, transforms and random seed independently.
`PlayAppearance()` and `PlayAppearance(False)` replace typing with a whole-text
visual pass and use Whole-text Entry/Exit Stagger respectively. During typing,
glyph starts follow the typing intervals instead. Reversing an unfinished pass
continues from current glyph geometry in the same Appearance layer. Re-showing
an active layout retains drawable glyphs; a different layout starts fresh rather
than morphing unrelated text. Pending glyphs hold their geometry until the new
reveal reaches them; the replaced hide does not continue. Live profile edits retain the current visual state
and adjust the remaining duration. Both profiles use cubic-out easing.
Pause/Play also works on standalone visual passes; SkipTypewriter only skips a
typing pass.

```python
animator.appearance.duration = 0.3
animator.appearance.offset = (0, 12)
animator.disappearance.duration = 0.1
animator.disappearance.offset = (-8, 0)
animator.SetTypewriterSpeed(2)
animator.ShowText("Hello 世界")
# Later: animator.StartDisappearingText()
```

For manual character geometry:

```python
from infernux_text_animator import CharacterAnimator

characters = CharacterAnimator(label)
characters.Word(0).Offset((0, -8)).Rotate(-5)
characters.Range().Alpha(0.8)
characters.Apply()
```

The Manual, Effects and Appearance layers compose in that order. Use one
Manual-layer controller per label. Refresh selections after changing layout,
and call `Reset()` when its manual geometry is no longer needed.

Add **Animation / Text Animator** to a UIText to edit the native serialized effect
list and typewriter settings. Components share one update entry; paused, empty or
completed playback disables idle work. Open **Animation / Text Animator** in Edit
mode to preview the selected component. Stop restores authored text; Save, Undo,
selection changes and entering Play also end previews before proceeding. Preview
does not send gameplay events or play typing sounds.
