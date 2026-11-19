from experiments.convergence_revision5_maud_sibling_cue import CUES, mask, span_edits


def test_equal_width_cue_and_control_masks_preserve_nonselected_text():
    text = 'The relevant Agreement addressed COVID-19. The business handled the outbreak separately.'
    selected = span_edits(text)
    ranked = {mode: sorted(right - left for left, right in points)
              for mode, points in selected.items()}
    assert ranked['pandemic_mask'] == ranked['length_matched_mask']
    removed = mask(text, selected['pandemic_mask'])
    control = mask(text, selected['length_matched_mask'])
    assert not CUES.search(removed)
    assert CUES.findall(control) == CUES.findall(text)
    for mode, edited in (('pandemic_mask', removed), ('length_matched_mask', control)):
        assert len(edited) == len(text)
        changed = {i for left, right in selected[mode] for i in range(left, right)}
        assert all(old == new for i, (old, new) in enumerate(zip(text, edited, strict=True)) if i not in changed)
