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
    animator.Word(0).Offset((2, 3)).Rotate(15).Scale((2, 1))
    animator.Line(1).Skew(0.2).Color((1, 0, 0, 0.5)).Alpha(0.25)
    animator.Character(3).Vertices(((1, 0), (0, 1), (-1, 0), (0, -1))).Apply()
    assert np.all(animator.buffer.offsets[:2] == (2, 3))
    assert np.all(animator.buffer.rotations[:2] == 15)
    assert np.all(animator.buffer.colors[2:, :, 3] == 0.25)
    assert len(commits) == 1
    text.get_text_layout = lambda: object()
    with pytest.raises(RuntimeError, match="refresh"):
        animator.Apply()


def test_appearance_staggers_from_rest_and_hides_without_touching_other_layers():
    from infernux.lib import TextGeometryLayer
    text, commits = text_buffer()
    animator = CharacterAppearance(text, Appearance(duration=1, offset=(0, 8), scale=(0, 0), rotation=90, vertex_expand=2))
    animator.Play(stagger=0.25).Sample(0.5)
    expected = 1-(1-0.5)**3
    assert animator.buffer.colors[0, 0, 3] == pytest.approx(expected)
    assert animator.buffer.colors[-1, 0, 3] == 0
    assert animator.buffer.offsets[0, 1] == pytest.approx(8*(1-expected))
    animator.Sample(2)
    assert not animator.active and np.all(animator.buffer.colors[:, :, 3] == 1)
    animator.Play(False, stagger=0).Update(1)
    assert not animator.active and np.all(animator.buffer.colors[:, :, 3] == 0)
    assert set(commits) == {TextGeometryLayer.Appearance}
    animator.Reset()


def test_independent_phase_profiles_reverse_from_the_current_glyph_state_in_one_layer():
    from infernux.lib import TextGeometryLayer
    text, commits = text_buffer()
    animator = CharacterAppearance(
        text, Appearance(duration=1, offset=(0, 8), scale=(0.5, 0.5), rotation=90, vertex_expand=2),
        Appearance(duration=0.4, offset=(-5, 0), scale=(0.7, 0.7), rotation=-30, alpha=0.2, vertex_expand=-1),
    )
    animator.Play(stagger=0.1).Sample(0.3)
    before = [getattr(animator.buffer, name).copy() for name in ('offsets', 'rotations', 'scales', 'colors', 'vertex_offsets')]
    animator.Play(False, stagger=0.05)
    for name, value in zip(('offsets', 'rotations', 'scales', 'colors', 'vertex_offsets'), before):
        assert getattr(animator.buffer, name) == pytest.approx(value)
    animator.Sample(0.45)
    previous = animator.buffer.colors.copy()
    animator.Play(True, stagger=0)
    assert animator.buffer.colors == pytest.approx(previous)
    animator.Sample(2)
    assert np.all(animator.buffer.colors[:, :, 3] == 1)
    animator.Play(False, stagger=0).Update(0.4)
    assert animator.buffer.offsets == pytest.approx(np.tile((-5, 0), (4, 1)))
    assert np.allclose(animator.buffer.colors[:, :, 3], 0.2)
    assert not animator.active and set(commits) == {TextGeometryLayer.Appearance}
