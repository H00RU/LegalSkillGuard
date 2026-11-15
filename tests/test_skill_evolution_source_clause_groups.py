from legal_skill_guard.skill_evolution.source_clause_groups import shared_list_group


def test_colon_children_keep_conditions_that_do_not_repeat_the_action():
    rows = [[39, 'All information shall be returned or destroyed:'],
            [40, '(a) if a relationship is not entered into; or'],
            [41, '(b) upon request at any time.'], [42, '6. A different obligation.']]
    assert shared_list_group(rows, 0) == [' '.join(r[1] for r in rows[:3]), [39, 40, 41], 2]


def test_numbered_children_and_unrelated_nonlist_clause_are_distinct():
    rows = [[1, 'It may disclose to:'], [2, '2.3.1 its staff;'], [3, '2.3.2 its advisers.'],
            [4, '3. A different heading.']]
    assert shared_list_group(rows, 0)[1:] == [[1, 2, 3], 2]
    assert shared_list_group([[1, 'A complete sentence.'], [2, '(a) Not its child.']], 0) == ['A complete sentence.', [1], 0]
