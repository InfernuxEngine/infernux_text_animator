# Text Animator

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
