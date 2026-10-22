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

    def reset(self):
        self.offsets[:] = 0
        self.rotations[:] = 0
        self.scales[:] = 1
        self.colors[:] = 1


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
    assert np.array_equal(buffer.offsets[[0, 1, 6, 7]], np.zeros((4, 2)))


def test_multiple_effects_compose_and_zero_characters_need_no_special_path():
    buffer = Buffer(4)
    EffectStack(4, [Effect(EffectKind.Wave), Effect(EffectKind.Swing, amplitude=15), Effect(EffectKind.Alpha, amplitude=0.5)]).sample(buffer, 0.2)
    assert np.any(buffer.offsets != 0)
    assert np.any(buffer.rotations != 0)
    assert np.all((buffer.colors >= 0) & (buffer.colors <= 1))
    EffectStack(0, [Effect(EffectKind.Wave)]).sample(Buffer(0), 1)


def test_invalid_ranges_fail_when_binding_not_inside_the_frame_loop():
    with pytest.raises(ValueError, match="exceeds"):
        EffectStack(2, [Effect(start=1, end=4)])
    with pytest.raises(ValueError, match="ordered"):
        Effect(start=4, end=1)


def test_text_animation_rebuilds_buffers_only_when_native_layout_changes():
    from infernux_text_animator import TextAnimation

    layout = SimpleNamespace()
    text = SimpleNamespace(get_text_layout=lambda: layout, create_character_buffer=lambda: Buffer(4),
                           set_character_data=lambda buffer, layer: samples.append((buffer, layer)),
                           reset_character_data=lambda layer: None)
    samples = []
    animation = TextAnimation(text, [Effect()])
    animation.Sample(0.1).Sample(0.2)
    assert samples[0][0] is samples[1][0]
    layout = SimpleNamespace()
    animation.Sample(0.3)
    assert samples[-1][0] is not samples[0][0]


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
