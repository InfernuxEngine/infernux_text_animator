from infernux.components import FieldType, get_serialized_fields

from TextAnimator import TextAnimator, TextEffect
from infernux_text_animator import EffectKind


def test_effect_list_uses_native_serialization_and_independent_instances():
    first, second = TextAnimator(), TextAnimator()
    setting = TextEffect(kind=EffectKind.Swing, amplitude=12.0, start=2, end=6)
    first.effects.append(setting)
    assert not second.effects
    fields = get_serialized_fields(TextAnimator)
    assert fields["effects"].field_type == FieldType.LIST
    assert fields["effects"].element_class is TextEffect
    restored = TextEffect._deserialize(setting._serialize())
    effect = restored.build()
    assert (effect.kind, effect.amplitude, effect.start, effect.end) == (EffectKind.Swing, 12, 2, 6)
    assert TextEffect().build().end is None
