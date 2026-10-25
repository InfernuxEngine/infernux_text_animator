from types import SimpleNamespace

import numpy as np
import pytest

from infernux_text_animator import Appearance, CharacterAnimator, CharacterAppearance


def text_buffer():
    from test_effects import Buffer
    layout = SimpleNamespace(words=[SimpleNamespace(character_start=0, character_end=2)],
                             lines=[object(), object()], characters=[SimpleNamespace(line=i//2) for i in range(4)])
    committed = []
    def create():
        buffer = Buffer(4)
        buffer.skews = np.zeros(4, dtype=np.float32)
        buffer.vertex_offsets = np.zeros((4, 4, 2), dtype=np.float32)
        return buffer
    text = SimpleNamespace(get_text_layout=lambda: layout, create_character_buffer=create,
                           set_character_data=lambda buffer, layer: committed.append(layer),
                           reset_character_data=lambda layer: committed.append(layer), max_visible_characters=2)
    return text, committed


def test_manual_words_lines_vertices_and_layout_lifetime():
    text, commits = text_buffer()
    animator = CharacterAnimator(text)
    animator.word(0).offset((2, 3)).rotate(15).scale((2, 1))
    animator.line(1).skew(0.2).color((1, 0, 0, 0.5)).alpha(0.25)
    animator.character(3).vertices(((1, 0), (0, 1), (-1, 0), (0, -1))).apply()
    assert np.all(animator.buffer.offsets[:2] == (2, 3))
    assert np.all(animator.buffer.rotations[:2] == 15)
    assert np.all(animator.buffer.colors[2:, :, 3] == 0.25)
    assert np.all(animator.buffer.color_overrides[2:] == 3)
    assert len(commits) == 1
    text.get_text_layout = lambda: object()
    with pytest.raises(RuntimeError, match="refresh"):
        animator.apply()


def test_appearance_staggers_from_rest_and_hides_without_touching_other_layers():
    from infernux.lib import TextGeometryLayer
    text, commits = text_buffer()
    animator = CharacterAppearance(text, Appearance(duration=1, offset=(0, 8), scale=(0, 0), rotation=90, vertex_expand=2))
    animator.play(stagger=0.25)
    animator.sample(0.5)
    expected = 1-(1-0.5)**3
    assert animator.buffer.colors[0, 0, 3] == pytest.approx(expected)
    assert animator.buffer.colors[-1, 0, 3] == 0
    assert animator.buffer.offsets[0, 1] == pytest.approx(8*(1-expected))
    animator.sample(2)
    assert not animator.active and np.all(animator.buffer.colors[:, :, 3] == 1)
    animator.play(False, stagger=0)
    animator.update(1)
    assert not animator.active and np.all(animator.buffer.colors[:, :, 3] == 0)
    assert set(commits) == {TextGeometryLayer.Appearance}
    animator.reset()
    for duration in (0.0, -0.25):
        animator = CharacterAppearance(text, Appearance(duration=duration, offset=(0, 8), scale=(0, 0)),
                                       Appearance(duration=duration, offset=(-5, 0)))
        animator.play(stagger=0.25)
        assert not animator.active
        assert np.all(animator.buffer.colors[:, :, 3] == 1)
        assert np.all(animator.buffer.offsets == 0) and np.all(animator.buffer.scales == 1)
        animator.play(False, stagger=0.25)
        assert not animator.active
        assert np.all(animator.buffer.colors[:, :, 3] == 0)
        assert np.all(animator.buffer.offsets == (-5, 0))


def test_independent_phase_profiles_reverse_from_the_current_glyph_state_in_one_layer():
    from infernux.lib import TextGeometryLayer
    text, commits = text_buffer()
    animator = CharacterAppearance(
        text, Appearance(duration=1, offset=(0, 8), scale=(0.5, 0.5), rotation=90, vertex_expand=2),
        Appearance(duration=0.4, offset=(-5, 0), scale=(0.7, 0.7), rotation=-30, alpha=0.2, vertex_expand=-1),
    )
    animator.play(stagger=0.1)
    animator.sample(0.3)
    before = [getattr(animator.buffer, name).copy() for name in ('offsets', 'rotations', 'scales', 'colors', 'vertex_offsets')]
    animator.play(False, stagger=0.05)
    for name, value in zip(('offsets', 'rotations', 'scales', 'colors', 'vertex_offsets'), before):
        assert getattr(animator.buffer, name) == pytest.approx(value)
    animator.sample(0.45)
    previous = animator.buffer.colors.copy()
    animator.play(True, stagger=0)
    assert animator.buffer.colors == pytest.approx(previous)
    animator.sample(2)
    assert np.all(animator.buffer.colors[:, :, 3] == 1)
    animator.play(False, stagger=0)
    animator.update(0.4)
    assert animator.buffer.offsets == pytest.approx(np.tile((-5, 0), (4, 1)))
    assert np.allclose(animator.buffer.colors[:, :, 3], 0.2)
    assert not animator.active and set(commits) == {TextGeometryLayer.Appearance}
    animator.set_visible(False).play(stagger=0).update(0.2)
    assert animator.active
    animator.set_appearance(Appearance(duration=0))
    assert not animator.active and np.all(animator.buffer.colors[:, :, 3] == 1)
    assert np.all(animator.buffer.offsets == 0) and np.all(animator.buffer.scales == 1)
    animator.play(False, stagger=0).update(0.1)
    assert animator.active
    animator.set_appearances(animator.appearance, Appearance(duration=0, offset=(-5, 0)))
    assert not animator.active and np.all(animator.buffer.colors[:, :, 3] == 0)
    assert np.all(animator.buffer.offsets == (-5, 0))


def test_named_custom_effect_runs_in_each_category_and_reverses_without_geometry_jump():
    from infernux_text_animator import CustomEffect, EffectStack, parse_markup
    from test_typewriter import text_fixture

    def deform(buffer, selected, time):
        buffer.offsets[selected, 0] += 3+time
        buffer.skews[selected] += 0.2
        buffer.vertex_offsets[selected, 0, 1] += 2
        buffer.vertex_depth_offsets[selected, 0] += 4
        buffer.affine_transforms[selected, 2, 3] += 5
        buffer.colors[selected, 0, 1] *= 0.3

    text, commits = text_buffer()
    parsed = parse_markup('<custom a=2>A</>{custom}{#custom}B{/}CD{/#}', {'custom': CustomEffect(deform)})
    text.get_text_layout = text_fixture(list('ABCD')).get_text_layout
    effects, _ = parsed.bind(text.get_text_layout())
    phases = parsed.bind_appearance_tags(text.get_text_layout())
    buffer = text.create_character_buffer()
    EffectStack(4, effects).sample(buffer, 0.5)
    assert buffer.offsets[0, 0] == 7 and buffer.skews[0] == pytest.approx(0.4)
    assert buffer.vertex_offsets[0, 0, 1] == 4 and buffer.colors[0, 0, 1] == pytest.approx(-0.4)
    assert buffer.vertex_depth_offsets[0, 0] == 8 and buffer.affine_transforms[0, 2, 3] == 10
    animator = CharacterAppearance(text, Appearance(duration=1), Appearance(duration=1),
                                   appearance_tags=phases[0], disappearance_tags=phases[1], default_enabled=False)
    animator.play(stagger=0).sample(0.5)
    assert animator.buffer.offsets[1, 0] == pytest.approx(3.5)
    assert animator.buffer.skews[1] == pytest.approx(0.2)
    assert animator.buffer.colors[1, 0, 1] == pytest.approx(0.3)
    assert animator.buffer.vertex_depth_offsets[1, 0] == 4 and animator.buffer.affine_transforms[1, 2, 3] == 5
    before = animator.buffer.offsets.copy(), animator.buffer.colors.copy(), animator.buffer.vertex_offsets.copy()
    animator.rebase_time(0).hold()
    animator.character(1, False).sample(0)
    for field, expected in zip(('offsets', 'colors', 'vertex_offsets'), before):
        assert getattr(animator.buffer, field) == pytest.approx(expected)
    animator.sample(0.5)
    assert animator.buffer.offsets[2, 0] == 0
    animator.play(False, stagger=0).sample(1.0)
    assert animator.buffer.offsets[2, 0] != 0 and animator.buffer.vertex_offsets[2, 0, 1] != 0
    animator.sample(2)
    assert not animator.active
    animator.set_visible(False).rebase_time(0).play(stagger=0.5).sample(0.75)
    assert animator.buffer.offsets[1, 0] == pytest.approx(3.25*0.75)
    assert animator.buffer.affine_transforms[1, 2, 3] == pytest.approx(5*0.75)
