from collections.abc import Iterator
from pathlib import Path

import pytest

from generate_dice_tables import (
    DIE_FACES,
    FACES,
    PAIRS_PER_AXIS,
    VALID_PAIRS,
    WORDLIST_ANCHORS,
    WORDLIST_SIZE,
    WORKED_EXAMPLE_ROLL,
    DiceTableError,
    build_sheets,
    is_reroll,
    load_words,
    word_index,
    worked_example,
)

TOP_FACE = 1
BOTTOM_FACE = 4


def accepted_rolls() -> Iterator[tuple[int, int, int, int, int]]:
    for die1 in FACES:
        for die2 in FACES:
            for die3 in FACES:
                for die4 in FACES:
                    for die5 in FACES:
                        if is_reroll(die1, die2) or is_reroll(die3, die4):
                            continue
                        yield die1, die2, die3, die4, die5


def test_valid_pairs_count() -> None:
    assert len(VALID_PAIRS) == 32
    assert PAIRS_PER_AXIS == 32


def test_word_index_is_bijection() -> None:
    hits: dict[int, set[tuple[int, int, int, int, int]]] = {}
    for roll in accepted_rolls():
        index = word_index(*roll)
        assert 0 <= index < WORDLIST_SIZE
        hits.setdefault(index, set()).add(roll)
    assert len(hits) == WORDLIST_SIZE
    for rolls in hits.values():
        assert len(rolls) == 3
        assert len({roll[:4] for roll in rolls}) == 1


def test_reroll_rate() -> None:
    accepted = sum(1 for _ in accepted_rolls())
    total = DIE_FACES**5
    assert accepted == 6144
    assert total == 7776
    assert round(1 - accepted / total, 4) == 0.2099


def test_sheets_mark_reroll_exactly_where_a_pair_is_rejected() -> None:
    sheets, _ = build_sheets(load_words())
    for sheet in sheets:
        for row in sheet.rows:
            assert row.full_reroll == is_reroll(sheet.page, row.die2)
            if row.full_reroll:
                assert row.cells == ()
                continue
            assert len(row.cells) == DIE_FACES
            for die4, cell in zip(FACES, row.cells, strict=True):
                assert cell.reroll == is_reroll(row.die3, die4)


def test_sheet_cells_hold_the_words_the_mapping_selects() -> None:
    words = load_words()
    sheets, emitted = build_sheets(words)
    for sheet in sheets:
        for row in sheet.rows:
            if row.full_reroll:
                continue
            for die4, cell in zip(FACES, row.cells, strict=True):
                if cell.reroll:
                    continue
                assert cell.top == words[word_index(sheet.page, row.die2, row.die3, die4, TOP_FACE)]
                assert cell.bot == words[word_index(sheet.page, row.die2, row.die3, die4, BOTTOM_FACE)]
    assert sorted(emitted) == list(range(WORDLIST_SIZE))


def test_worked_example_matches_the_printed_guide() -> None:
    words = load_words()
    assert word_index(*WORKED_EXAMPLE_ROLL) == 1722
    assert words[1722] == "struggle"
    assert words[1723] == "student"

    example = worked_example(words)
    assert (example.die1, example.die2, example.die3, example.die4, example.die5) == WORKED_EXAMPLE_ROLL
    assert example.top == "struggle"
    assert example.bot == "student"


def test_wordlist_loads_with_expected_anchors() -> None:
    words = load_words()
    assert len(words) == WORDLIST_SIZE
    for index, expected in WORDLIST_ANCHORS.items():
        assert words[index] == expected


def test_load_words_rejects_an_unpinned_wordlist(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    impostor = tmp_path / "bip39_english.txt"
    impostor.write_text("abandon\nability\n", encoding="utf-8")
    monkeypatch.setattr("generate_dice_tables.WORDLIST_PATH", impostor)
    with pytest.raises(DiceTableError, match="sha256 mismatch"):
        load_words()
