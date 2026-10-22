# Text Animator

Enable Parse Tags for `<wave amplitude=2>text</wave>`, nested effects and named
Inspector presets. `<event=name/>` and `<wait=0.5/>` drive typewriter actions.
Enable `UIText.rich_text` separately for native color/size tags.

Appearance settings combine fade, size, offset, rotation, vertex expansion and
seeded random offsets. They animate each typed character and retain outgoing
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

Add **Animation / Text Animator** to a UIText to edit the native serialized effect
list and typewriter settings. Components share one update entry; paused, empty or
completed playback disables idle work. Effect tags and appearance presets remain
in progress.
