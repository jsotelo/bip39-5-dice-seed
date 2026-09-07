import hashlib
import sys
from dataclasses import dataclass
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

HERE = Path(__file__).resolve().parent
WORDLIST_PATH = HERE / "bip39_english.txt"
TEMPLATES_DIR = HERE / "templates"
OUT_PATH = HERE / "dice_tables.html"

WORDLIST_SHA256 = "2f5eed53a4727b4bf8880d8f3f199efc90e58503646d9ff8eff3a2ed3b24dbda"
WORDLIST_SIZE = 2048
WORDLIST_ANCHORS = {0: "abandon", 512: "divorce", WORDLIST_SIZE - 1: "zoo"}

DIE_FACES = 6
FACES = tuple(range(1, DIE_FACES + 1))
REROLL_FACES = (5, 6)
WORDS_PER_CELL = 2

WORKED_EXAMPLE_ROLL = (5, 3, 6, 2, 2)


class DiceTableError(Exception):
    """Raised when an input file or a rendered document fails validation."""


def is_reroll(first_die: int, second_die: int) -> bool:
    """Whether a pair of dice must be re-rolled."""
    return first_die in REROLL_FACES and second_die in REROLL_FACES


VALID_PAIRS = [(first, second) for first in FACES for second in FACES if not is_reroll(first, second)]
PAIR_RANK = {pair: rank for rank, pair in enumerate(VALID_PAIRS)}
PAIRS_PER_AXIS = len(VALID_PAIRS)

# Rejecting the four both-5-or-6 pairs leaves 32 outcomes per pair, so two pairs
# plus the top/bottom choice address the wordlist exactly, with no bias.
assert PAIRS_PER_AXIS**2 * WORDS_PER_CELL == WORDLIST_SIZE


@dataclass(frozen=True)
class Cell:
    """One table cell. Both words are None when the cell is a RE-ROLL."""

    top: str | None
    bot: str | None

    @property
    def reroll(self) -> bool:
        return self.top is None


REROLL_CELL = Cell(top=None, bot=None)


@dataclass(frozen=True)
class Row:
    die2: int
    die3: int
    css_class: str
    full_reroll: bool
    cells: tuple[Cell, ...]


@dataclass(frozen=True)
class Sheet:
    page: int
    rows: tuple[Row, ...]


@dataclass(frozen=True)
class WorkedExample:
    die1: int
    die2: int
    die3: int
    die4: int
    die5: int
    top: str
    bot: str


def cell_index(die1: int, die2: int, die3: int, die4: int) -> int:
    """Index of the top word of the cell that the first four dice select."""
    high = PAIR_RANK[(die1, die2)]
    low = PAIR_RANK[(die3, die4)]
    return (high * PAIRS_PER_AXIS + low) * WORDS_PER_CELL


def offset_in_cell(die5: int) -> int:
    return 0 if die5 <= DIE_FACES // 2 else 1


def word_index(die1: int, die2: int, die3: int, die4: int, die5: int) -> int:
    """Wordlist index for one accepted roll of the five dice.

    On the printed sheets die1 picks the page, die2 and die3 pick the row, die4
    picks the column, and die5 picks the top or bottom word of the cell. The
    index itself is a two-digit base-32 number whose digits are the ranks of the
    re-roll pairs (die1, die2) and (die3, die4).
    """
    return cell_index(die1, die2, die3, die4) + offset_in_cell(die5)


def row_css_class(die2: int, die3: int) -> str:
    classes: list[str] = []
    if die3 % 2 == 1:
        classes.append("band")
    if die2 > 1 and die3 == 1:
        classes.append("blockstart")
    return " ".join(classes)


def build_row(words: list[str], die1: int, die2: int, die3: int) -> tuple[Row, list[int]]:
    css_class = row_css_class(die2, die3)
    if is_reroll(die1, die2):
        return Row(die2=die2, die3=die3, css_class=css_class, full_reroll=True, cells=()), []

    cells: list[Cell] = []
    indices: list[int] = []
    for die4 in FACES:
        if is_reroll(die3, die4):
            cells.append(REROLL_CELL)
            continue
        top = cell_index(die1, die2, die3, die4)
        indices.extend((top, top + 1))
        cells.append(Cell(top=words[top], bot=words[top + 1]))
    return Row(die2=die2, die3=die3, css_class=css_class, full_reroll=False, cells=tuple(cells)), indices


def build_sheets(words: list[str]) -> tuple[list[Sheet], list[int]]:
    """Return one sheet per face of die1, plus every wordlist index they print."""
    sheets: list[Sheet] = []
    emitted: list[int] = []
    for die1 in FACES:
        rows: list[Row] = []
        for die2 in FACES:
            for die3 in FACES:
                row, indices = build_row(words, die1, die2, die3)
                rows.append(row)
                emitted.extend(indices)
        sheets.append(Sheet(page=die1, rows=tuple(rows)))
    return sheets, emitted


def load_words() -> list[str]:
    """Return the BIP39 English wordlist. Raises DiceTableError if it is not the pinned wordlist."""
    raw = WORDLIST_PATH.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != WORDLIST_SHA256:
        raise DiceTableError(f"BIP39 wordlist sha256 mismatch: {digest}")

    words = raw.decode("utf-8").split()
    if len(words) != WORDLIST_SIZE:
        raise DiceTableError(f"expected {WORDLIST_SIZE} words, got {len(words)}")

    for index, expected in WORDLIST_ANCHORS.items():
        if words[index] != expected:
            raise DiceTableError(f"anchor mismatch: word[{index}]={words[index]!r} != {expected!r}")
    return words


def worked_example(words: list[str]) -> WorkedExample:
    die1, die2, die3, die4, die5 = WORKED_EXAMPLE_ROLL
    top = cell_index(die1, die2, die3, die4)
    return WorkedExample(
        die1=die1,
        die2=die2,
        die3=die3,
        die4=die4,
        die5=die5,
        top=words[top],
        bot=words[top + 1],
    )


def render_document(words: list[str], example: WorkedExample) -> str:
    """Render the printable document. Raises DiceTableError unless the sheets print every word exactly once."""
    sheets, emitted = build_sheets(words)
    if sorted(emitted) != list(range(WORDLIST_SIZE)):
        raise DiceTableError(f"rendered sheets do not cover 0..{WORDLIST_SIZE - 1} exactly once")

    env = Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        autoescape=select_autoescape(["html", "j2"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    styles = (TEMPLATES_DIR / "style.css").read_text(encoding="utf-8")
    template = env.get_template("document.html.j2")
    return template.render(styles=styles, columns=FACES, sheets=sheets, example=example)


def write_html(html: str) -> None:
    OUT_PATH.write_text(html, encoding="utf-8")


def main() -> int:
    try:
        words = load_words()
        html = render_document(words, worked_example(words))
    except DiceTableError as error:
        print(error, file=sys.stderr)
        return 1

    print(f"OK  rendered {DIE_FACES} table sheets covering all {WORDLIST_SIZE} words exactly once")
    write_html(html)
    print(f"wrote {OUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
