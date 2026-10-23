from types import SimpleNamespace

import numpy as np
import pytest

from infernux_text_animator import Effect, EffectKind, EffectStack


class Buffer:
    def __init__(self, count):
        self.character_count = count
        self.offsets = np.zeros((count, 2), dtype=np.float32)
        self.rotations = np.zeros(count, dtype=np.float32)
        self.scales = np.ones((count, 2), dtype=np.float32)
        self.colors = np.ones((count, 4, 4), dtype=np.float32)
        self.skews = np.zeros(count, dtype=np.float32)
        self.vertex_offsets = np.zeros((count, 4, 2), dtype=np.float32)
        self.affine_transforms = np.tile(np.eye(3, 4, dtype=np.float32), (count, 1, 1))
        self.vertex_depth_offsets = np.zeros((count, 4), dtype=np.float32)
        self.color_overrides = np.zeros(count, dtype=np.float32)

    def reset(self):
        self.offsets[:] = 0
        self.rotations[:] = 0
        self.scales[:] = 1
        self.colors[:] = 1
        self.skews[:] = 0
        self.vertex_offsets[:] = 0
        self.affine_transforms[:] = np.eye(3, 4, dtype=np.float32)
        self.vertex_depth_offsets[:] = 0
        self.color_overrides[:] = 0


@pytest.mark.parametrize("kind", list(EffectKind))
def test_effects_are_repeatable_and_do_not_accumulate(kind):
    stack = EffectStack(8, [Effect(kind, amplitude=0.5, start=2, end=6)])
    buffer = Buffer(8)
    stack.sample(buffer, 0.37)
    values = [array.copy() for array in (buffer.offsets, buffer.rotations, buffer.scales, buffer.colors)]
    stack.sample(buffer, 8.6)
    stack.sample(buffer, 0.37)
    for value, array in zip(values, (buffer.offsets, buffer.rotations, buffer.scales, buffer.colors)):
        assert np.array_equal(value, array)
        assert np.isfinite(array).all()
    stack.sample(buffer, np.arange(8, dtype=np.float32)*0.1)
    assert all(np.isfinite(array).all() for array in (buffer.offsets, buffer.rotations, buffer.scales, buffer.colors))
    assert np.array_equal(buffer.offsets[[0, 1, 6, 7]], np.zeros((4, 2)))


def test_multiple_effects_compose_and_zero_characters_need_no_special_path():
    buffer = Buffer(4)
    EffectStack(4, [Effect(EffectKind.WAVE), Effect(EffectKind.SWING, amplitude=15), Effect(EffectKind.ALPHA, amplitude=0.5)]).sample(buffer, 0.2)
    assert np.any(buffer.offsets != 0)
    assert np.any(buffer.rotations != 0)
    assert np.all((buffer.colors >= 0) & (buffer.colors <= 1))
    EffectStack(0, [Effect(EffectKind.WAVE)]).sample(Buffer(0), 1)


def test_invalid_ranges_fail_when_binding_not_inside_the_frame_loop():
    with pytest.raises(ValueError, match="exceeds"):
        EffectStack(2, [Effect(start=1, end=4)])
    with pytest.raises(ValueError, match="ordered"):
        Effect(start=4, end=1)


def test_text_animation_rebuilds_buffers_only_when_native_layout_changes():
    from infernux_text_animator import TextAnimation
    from test_typewriter import text_fixture

    layout = text_fixture(list('ABCD')).get_text_layout()
    text = SimpleNamespace(text='ABCD', get_text_layout=lambda: layout, create_character_buffer=lambda: Buffer(4),
                           set_character_data=lambda buffer, layer: samples.append((buffer, layer)),
                           reset_character_data=lambda layer: cleared.append(layer))
    samples, cleared = [], []
    animation = TextAnimation(text, parse_tags=True)
    animation.sample(0.1).sample(0.2)
    assert samples[0][0] is samples[1][0]
    animation.set_text('<wave amplitude=3>ABCD</wave><?done>')
    animation.sample(0.25)
    assert samples[-1][0] is samples[0][0] and np.any(samples[-1][0].offsets != 0)
    assert [cue.value.name for cue in animation.cues] == ['done']
    cleared.clear()
    animation.set_text('ABCD')
    assert samples[-1][0] is samples[0][0] and np.all(samples[-1][0].offsets == 0)
    assert not animation.cues and not animation.has_effects and cleared
    layout = text_fixture(list('ABCD')).get_text_layout()
    animation.sample(0.3)
    assert samples[-1][0] is not samples[0][0]


def test_effect_enum_inputs_and_text_visibility_have_one_explicit_contract():
    from enum import Enum
    from infernux_text_animator import CurveTarget, TextAnimation
    from test_typewriter import text_fixture

    for kwargs in ({"kind": "wave"}, {"curve_target": "rotation"}):
        with pytest.raises(TypeError, match="enum"):
            Effect(**kwargs)
    assert isinstance(EffectKind.WAVE, Enum) and not isinstance(EffectKind.WAVE, str)
    assert EffectKind.WAVE.value == "wave" and CurveTarget.OFFSET_Y.value == "offset_y"
    layout = text_fixture(list("AB")).get_text_layout()
    text = SimpleNamespace(text="AB", max_visible_characters=1, get_text_layout=lambda: layout,
                           create_character_buffer=lambda: Buffer(2), reset_character_data=lambda layer: None)
    animation = TextAnimation(text)
    assert animation.set_text("AB") is None and text.max_visible_characters == -1
    assert animation.set_text("AB", True) is None and text.max_visible_characters == 0
    with pytest.raises(TypeError):
        animation.set_text("AB", "false")


def test_wave_amplitude_frequency_and_phase_match_reference_equations():
    from math import pi

    buffer = Buffer(8)
    indices = np.arange(1, 9)
    for amplitude, angular_speed in ((2.0, 4.0), (0.75, 3.0), (0.5, 3.0), (0.25, 2.0)):
        stack = EffectStack(8, [Effect(amplitude=amplitude, speed=angular_speed / (2 * pi),
                                       phase=1.0, phase_offset=1.0)])
        for time in (0, 0.37, 1.2):
            stack.sample(buffer, time)
            assert buffer.offsets[:, 1] == pytest.approx(amplitude * np.sin(angular_speed * time + indices), abs=0.00001)


def test_curve_effects_sample_authored_tangents_wrap_and_character_phase_in_one_batch():
    from math import pi
    from infernux.graph.ramp import AnimationCurve, Keyframe
    from infernux_text_animator import CurveTarget
    curve = AnimationCurve((Keyframe(0, 0, out_tangent=1), Keyframe(1, 1, in_tangent=1)), post_wrap="ping_pong")
    effect = Effect(EffectKind.CURVE, amplitude=2, phase=pi/2, curve=curve, curve_target=CurveTarget.ROTATION)
    buffer = Buffer(4)
    stack = EffectStack(4, [effect])
    stack.sample(buffer, 0.5)
    assert buffer.rotations == pytest.approx([1, 1.5, 2, 1.5])
    stack.sample(buffer, 0.5)
    assert buffer.rotations == pytest.approx([1, 1.5, 2, 1.5])
