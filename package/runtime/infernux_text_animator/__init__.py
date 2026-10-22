"""Character animation and typewriter playback on native Infernux UIText."""

from .effects import CurveTarget, CustomEffect, Effect, EffectKind, EffectStack, TextAnimation
from .typewriter import Typewriter
from .markup import Cue, ParsedText, parse_markup
from .characters import CharacterAnimator, CharacterSelection
from .appearance import Appearance, CharacterAppearance

__all__ = ["Appearance", "CharacterAnimator", "CharacterAppearance", "CharacterSelection", "Cue", "CurveTarget", "CustomEffect", "Effect", "EffectKind", "EffectStack", "ParsedText", "TextAnimation", "Typewriter", "parse_markup"]
