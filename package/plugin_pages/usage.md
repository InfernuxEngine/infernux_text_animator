# Text Animator

`TextAnimation(text, effects)` binds effects to an existing `UIText`.
Call `Update(delta_time)` or `Sample(time)`; `Reset()` clears only its effects
layer. `Effect` supports an optional character range, amplitude, speed and phase.

`Typewriter(text).ShowText(value)` starts a reveal. `StopShowingText` pauses,
`StartShowingText` resumes, `SkipTypewriter` finishes, and
`StartDisappearingText` hides visible characters. Set `on_start`, `on_character`,
`on_complete` or `on_hidden` for events. Skip events are opt-in.

This development build provides the programmatic core; authoring components
and appearance presets are still in progress.
