"""character animation and typewriter playback on native Infernux UIText."""

from .effects import CurveTarget, CustomEffect, DefaultEffectsMode, Effect, EffectKind, EffectStack, TextAnimation
from .typewriter import Typewriter, TypingDelaysByCharacter, TypingDelaysByWord, TypingTimings
from .markup import Cue, ParsedText, parse_markup
from .characters import CharacterAnimator, CharacterSelection
from .appearance import Appearance, AppearanceKind, AppearanceTag, CharacterAppearance
from .events import (ActionMarker, ActionState, ActionStatus, AnimationLoop, CharacterData, CharacterEvent,
                     CharacterInfo, CharacterWaitEvent, EventMarker, MessageEvent, TextRegion, TextStyle,
                     TimeScale, TypewriterAction, TypingInfo, WaitInputMode, WaitMode)

__all__ = [
    "ActionMarker", "ActionState", "ActionStatus", "AnimationLoop", "Appearance", "AppearanceKind", "AppearanceTag",
    "CharacterAnimator", "CharacterAppearance", "CharacterData", "CharacterEvent", "CharacterInfo", "CharacterSelection",
    "CharacterWaitEvent", "Cue", "CurveTarget", "CustomEffect", "DefaultEffectsMode", "Effect", "EffectKind", "EffectStack",
    "EventMarker", "MessageEvent", "ParsedText", "TextAnimation", "TextRegion", "TextStyle", "TimeScale", "Typewriter",
    "TypewriterAction", "TypingDelaysByCharacter", "TypingDelaysByWord", "TypingInfo", "TypingTimings", "WaitInputMode",
    "WaitMode", "parse_markup",
]
