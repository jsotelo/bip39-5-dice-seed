"""Independent audit of the generated BIP39 dice-table document.

This module re-derives the dice-to-word-index mapping from scratch and never
imports generate_dice_tables. The duplication is deliberate: an audit that
reused the generator's own code would inherit the generator's bugs and still
report PASS. It also uses the standard library only, so a skeptical reader can
check a printed document with a bare python3 and no install step.
"""

import hashlib
import os
import re
import sys
from dataclasses import dataclass, field
from enum import Enum
from html import unescape
from html.parser import HTMLParser
from itertools import product
from typing import NamedTuple

MIN_PYTHON = (3, 10)
if sys.version_info < MIN_PYTHON:
    sys.exit(
        f"ERROR: audit_dice_tables.py needs Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]} or newer, "
        f"but {sys.executable} is Python {sys.version.split()[0]}. "
        "Re-run with a newer python3 (macOS ships 3.9 as /usr/bin/python3)."
    )

HERE = os.path.dirname(os.path.abspath(__file__))
WORDLIST_PATH = os.path.join(HERE, "bip39_english.txt")
HTML_PATH = os.path.join(HERE, "dice_tables.html")
WORDLIST_SHA256 = "2f5eed53a4727b4bf8880d8f3f199efc90e58503646d9ff8eff3a2ed3b24dbda"

DIE_FACES = (1, 2, 3, 4, 5, 6)
REROLL_FACES = (5, 6)
WORDLIST_SIZE = 2048
WORDS_PER_CELL = 2
TOP_HALF_DIE5 = 1
BOTTOM_HALF_DIE5 = 4
ANCHOR_WORDS = ((0, "abandon"), (512, "divorce"), (WORDLIST_SIZE - 1, "zoo"))
EXAMPLE_ROLL = (5, 3, 6, 2)
EXAMPLE_TOP_INDEX = 1722
EXAMPLE_TOP_WORD = "struggle"
EXAMPLE_BOTTOM_WORD = "student"
HALF_LABELS = ["1-3", "4-6"]
CELL_SPAN_ORDER = ["el", "w", "el", "w"]
COLUMN_HEADERS = [str(face) for face in DIE_FACES]
ROW_AXIS_LABELS = ["2nd", "3rd"]
GROUP_HEADER_NAME = "4th die"
CAPTURED_SPAN_CLASSES = ("el", "w", "dl")
MAX_DISCREPANCIES_SHOWN = 300
BANNER_PATTERN = re.compile(r"1st die = (\d)")
WHITESPACE_PATTERN = re.compile(r"\s+")


def is_reroll(first: int, second: int) -> bool:
    return first in REROLL_FACES and second in REROLL_FACES


VALID_PAIRS: list[tuple[int, int]] = [
    (first, second) for first in DIE_FACES for second in DIE_FACES if not is_reroll(first, second)
]
PAIR_RANK: dict[tuple[int, int], int] = {pair: rank for rank, pair in enumerate(VALID_PAIRS)}
PAIRS_PER_AXIS = len(VALID_PAIRS)
WORDS_PER_PAIR_RANK = PAIRS_PER_AXIS * WORDS_PER_CELL

EXPECTED_PAIRS_PER_AXIS = len(DIE_FACES) ** 2 - len(REROLL_FACES) ** 2
EXPECTED_TOTAL_CELLS = len(DIE_FACES) ** 4
EXPECTED_WORD_CELLS = EXPECTED_PAIRS_PER_AXIS**2
EXPECTED_REROLL_CELLS = EXPECTED_TOTAL_CELLS - EXPECTED_WORD_CELLS
EXPECTED_WORD_SLOTS = EXPECTED_WORD_CELLS * WORDS_PER_CELL


def word_index(die1: int, die2: int, die3: int, die4: int, die5: int) -> int:
    """Word list index for one physical roll of five dice, in roll order."""
    half = 0 if die5 < BOTTOM_HALF_DIE5 else 1
    return WORDS_PER_PAIR_RANK * PAIR_RANK[(die1, die2)] + WORDS_PER_CELL * PAIR_RANK[(die3, die4)] + half


def pair_rank_ok() -> bool:
    return (
        PAIRS_PER_AXIS == EXPECTED_PAIRS_PER_AXIS and PAIR_RANK[(1, 1)] == 0 and PAIR_RANK[(6, 4)] == PAIRS_PER_AXIS - 1
    )


def example_indices_ok(words: list[str]) -> bool:
    die1, die2, die3, die4 = EXAMPLE_ROLL
    top = word_index(die1, die2, die3, die4, TOP_HALF_DIE5)
    bottom = word_index(die1, die2, die3, die4, BOTTOM_HALF_DIE5)
    return (
        top == EXAMPLE_TOP_INDEX
        and bottom == EXAMPLE_TOP_INDEX + 1
        and words[top] == EXAMPLE_TOP_WORD
        and words[bottom] == EXAMPLE_BOTTOM_WORD
    )


class Position(NamedTuple):
    """A cell address: the first four dice, in physical roll order."""

    die1: int
    die2: int
    die3: int
    die4: int

    @property
    def label(self) -> str:
        return f"1st={self.die1},2nd={self.die2},3rd={self.die3},4th={self.die4}"


class CellKind(Enum):
    WORDS = "word cell"
    REROLL_ROW = "full-row RE-ROLL"
    REROLL_CELL = "RE-ROLL cell"
    UNRECOGNIZED = "unrecognized cell"


@dataclass(frozen=True)
class CellContent:
    kind: CellKind
    top: str | None = None
    bottom: str | None = None

    @property
    def is_reroll(self) -> bool:
        return self.kind in (CellKind.REROLL_ROW, CellKind.REROLL_CELL)


class Span(NamedTuple):
    css_class: str
    text: str


@dataclass
class ParsedCell:
    css_class: str
    colspan: int
    text: str
    spans: list[Span]

    def span_classes(self) -> list[str]:
        return [span.css_class for span in self.spans]

    def texts_of(self, css_class: str) -> list[str]:
        return [span.text for span in self.spans if span.css_class == css_class]


@dataclass
class ParsedPage:
    die1: int
    head_rows: list[list[ParsedCell]]
    rows: list[list[ParsedCell]]


@dataclass
class HeaderCheck:
    sheets: int = 0
    columns_ok: bool = False
    axes_ok: bool = False
    group_ok: bool = False
    example_ok: bool = False


@dataclass
class Report:
    lines: list[str] = field(default_factory=list)
    discrepancies: list[str] = field(default_factory=list)

    def add_line(self, text: str) -> None:
        self.lines.append(text)

    def add_discrepancy(self, text: str) -> None:
        self.discrepancies.append(text)

    def add_parse_problem(self, text: str) -> None:
        self.discrepancies.append("PARSE: " + text)

    def text(self) -> str:
        return "\n".join(self.lines)


@dataclass
class WordlistCheck:
    words: list[str]
    hash_ok: bool
    count_ok: bool
    anchors_ok: bool

    @property
    def ok(self) -> bool:
        return self.hash_ok and self.count_ok and self.anchors_ok


@dataclass
class CrossCheck:
    cells_checked: int = 0
    words_verified: int = 0
    rerolls_verified: int = 0
    index_sources: dict[int, tuple[str | None, Position]] = field(default_factory=dict)
    coverage_complete: bool = False
    index_mismatches: int = 0

    @property
    def distinct_indices(self) -> int:
        return len(self.index_sources)


def verify_wordlist(path: str, report: Report) -> WordlistCheck:
    with open(path, "rb") as f:
        raw = f.read()
    sha256 = hashlib.sha256(raw).hexdigest()
    words = raw.decode("utf-8").split()
    hash_ok = sha256 == WORDLIST_SHA256
    count_ok = len(words) == WORDLIST_SIZE
    anchors_ok = count_ok and all(words[index] == word for index, word in ANCHOR_WORDS)

    report.add_line(f"[wordlist] sha256={sha256}")
    report.add_line(f"[wordlist] hash match = {hash_ok}")
    report.add_line(f"[wordlist] count={len(words)} (=={WORDLIST_SIZE} -> {count_ok})")
    anchors = (
        " ".join(f"word[{index}]={words[index]!r}" for index, _ in ANCHOR_WORDS)
        if count_ok
        else "wordlist too short to read anchors"
    )
    report.add_line(f"[wordlist] {anchors} -> anchors_ok={anchors_ok}")
    return WordlistCheck(words, hash_ok, count_ok, anchors_ok)


def verify_mapping(words: list[str], report: Report) -> None:
    report.add_line(
        f"[rank] valid pairs={PAIRS_PER_AXIS} (expected {EXPECTED_PAIRS_PER_AXIS}) "
        f"rank(1,1)={PAIR_RANK[(1, 1)]} rank(6,4)={PAIR_RANK[(6, 4)]} -> rank_ok={pair_rank_ok()}"
    )

    die1, die2, die3, die4 = EXAMPLE_ROLL
    top = word_index(die1, die2, die3, die4, TOP_HALF_DIE5)
    bottom = word_index(die1, die2, die3, die4, BOTTOM_HALF_DIE5)
    example_cell = f"page={die1},row=({die2},{die3}),col={die4}"
    report.add_line(
        f"[example] {example_cell},5th=1-3 -> idx {top} {words[top]!r} (expect {EXAMPLE_TOP_INDEX} {EXAMPLE_TOP_WORD})"
    )
    report.add_line(
        f"[example] {example_cell},5th=4-6 -> idx {bottom} {words[bottom]!r} "
        f"(expect {EXAMPLE_TOP_INDEX + 1} {EXAMPLE_BOTTOM_WORD})"
    )
    report.add_line(f"[example] examples_ok={example_indices_ok(words)}")

    slots = PAIRS_PER_AXIS * PAIRS_PER_AXIS * WORDS_PER_CELL
    report.add_line(
        f"[combinatorics] valid (1st,2nd)={PAIRS_PER_AXIS} valid (3rd,4th)={PAIRS_PER_AXIS} "
        f"-> slots={PAIRS_PER_AXIS}*{PAIRS_PER_AXIS}*{WORDS_PER_CELL}={slots}"
    )


class DiceTableParser(HTMLParser):
    """Produces one ParsedPage per table section, plus any div.cellmock example cells found outside the tables."""

    def __init__(self) -> None:
        super().__init__()
        self.pages: list[ParsedPage] = []
        self.example_cells: list[list[Span]] = []
        self.page_die1: int | None = None
        self.page_head_rows: list[list[ParsedCell]] = []
        self.page_rows: list[list[ParsedCell]] = []
        self.in_thead = False
        self.in_tbody = False
        self.in_row = False
        self.row_cells: list[ParsedCell] = []
        self.in_cell = False
        self.cell_class = ""
        self.cell_colspan = 1
        self.cell_text = ""
        self.cell_spans: list[Span] = []
        self.cellmock_depth = 0
        self.span_class: str | None = None
        self.span_text = ""
        self.in_banner = False
        self.banner_text = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        css_class = attributes.get("class") or ""
        if tag == "section":
            self.page_die1 = None
            self.page_head_rows = []
            self.page_rows = []
            self.in_thead = False
            self.in_tbody = False
        elif tag == "span" and css_class == "big":
            self.in_banner = True
            self.banner_text = ""
        elif tag == "div" and css_class == "cellmock":
            self.cellmock_depth = 1
            self.cell_spans = []
        elif tag == "div" and self.cellmock_depth:
            self.cellmock_depth += 1
        elif tag == "thead":
            self.in_thead = True
        elif tag == "tbody":
            self.in_tbody = True
        elif tag == "tr" and (self.in_thead or self.in_tbody):
            self.in_row = True
            self.row_cells = []
        elif tag in ("td", "th") and self.in_row:
            self.in_cell = True
            self.cell_class = css_class
            self.cell_colspan = int(attributes.get("colspan") or "1")
            self.cell_text = ""
            self.cell_spans = []
        elif tag == "span" and css_class in CAPTURED_SPAN_CLASSES and (self.in_cell or self.cellmock_depth):
            self.span_class = css_class
            self.span_text = ""

    def handle_data(self, data: str) -> None:
        if self.in_banner:
            self.banner_text += data
        if self.in_cell:
            self.cell_text += data
        if self.span_class is not None:
            self.span_text += data

    def handle_endtag(self, tag: str) -> None:
        if tag == "span":
            self._close_span()
        elif tag == "div" and self.cellmock_depth:
            self._close_div()
        elif tag in ("td", "th") and self.in_cell:
            cell = ParsedCell(self.cell_class, self.cell_colspan, unescape(self.cell_text).strip(), self.cell_spans)
            self.row_cells.append(cell)
            self.in_cell = False
        elif tag == "tr" and self.in_row:
            rows = self.page_head_rows if self.in_thead else self.page_rows
            rows.append(self.row_cells)
            self.in_row = False
        elif tag == "thead":
            self.in_thead = False
        elif tag == "tbody":
            self.in_tbody = False
        elif tag == "section" and self.page_die1 is not None:
            self.pages.append(ParsedPage(self.page_die1, self.page_head_rows, self.page_rows))

    def _close_span(self) -> None:
        if self.span_class is not None:
            self.cell_spans.append(Span(self.span_class, unescape(self.span_text).strip()))
            self.span_class = None
        if self.in_banner:
            match = BANNER_PATTERN.search(self.banner_text)
            if match:
                self.page_die1 = int(match.group(1))
            self.in_banner = False

    def _close_div(self) -> None:
        self.cellmock_depth -= 1
        if self.cellmock_depth == 0:
            self.example_cells.append(self.cell_spans)
            self.cell_spans = []


def read_html(path: str) -> str:
    if not os.path.exists(path):
        print(f"ERROR: HTML file not found: {path}")
        sys.exit(1)
    with open(path, encoding="utf-8") as f:
        return f.read()


def normalize_space(text: str) -> str:
    return WHITESPACE_PATTERN.sub(" ", text).strip()


def read_head(page: ParsedPage) -> tuple[list[str], list[str], list[str]]:
    """Printed column headers, row axis labels and group headers of one sheet, in document order."""
    head_cells = [cell for row in page.head_rows for cell in row]
    columns = [cell.text for cell in head_cells if cell.css_class == "colh"]
    axes = [text for cell in head_cells if cell.css_class == "idx" for text in cell.texts_of("dl")]
    groups = [normalize_space(cell.text) for cell in head_cells if cell.css_class == "grouph"]
    return columns, axes, groups


def check_headers(pages: list[ParsedPage], report: Report) -> HeaderCheck:
    """Verifies each sheet's printed headers, which body-cell checks cannot see."""
    found = bool(pages)
    result = HeaderCheck(sheets=len(pages), columns_ok=found, axes_ok=found, group_ok=found)
    for page in pages:
        columns, axes, groups = read_head(page)
        where = f"page 1st die={page.die1}"
        if columns != COLUMN_HEADERS:
            result.columns_ok = False
            report.add_discrepancy(f"{where}: printed 4th-die column headers {columns}, expected {COLUMN_HEADERS}")
        if axes != ROW_AXIS_LABELS:
            result.axes_ok = False
            report.add_discrepancy(f"{where}: printed row axis labels {axes}, expected {ROW_AXIS_LABELS}")
        if len(groups) != 1 or GROUP_HEADER_NAME not in groups[0]:
            result.group_ok = False
            report.add_discrepancy(f"{where}: group headers {groups}, expected one naming {GROUP_HEADER_NAME!r}")
    report.add_line(
        f"[headers] {result.sheets} sheets: columns_ok={result.columns_ok} "
        f"axes_ok={result.axes_ok} group_ok={result.group_ok}"
    )
    return result


def check_guide_example(example_cells: list[list[Span]], report: Report) -> bool:
    """Verifies the guide's worked-example cell prints the two words the mapping derives for that roll."""
    if len(example_cells) != 1:
        report.add_discrepancy(f"guide: {len(example_cells)} worked-example cells (expected 1)")
        report.add_line(f"[guide] worked-example cells found={len(example_cells)} -> guide_example_ok=False")
        return False

    spans = example_cells[0]
    classes = [span.css_class for span in spans]
    labels = [span.text for span in spans if span.css_class == "el"]
    words = [span.text for span in spans if span.css_class == "w"]
    expected = [EXAMPLE_TOP_WORD, EXAMPLE_BOTTOM_WORD]

    ok = True
    if classes != CELL_SPAN_ORDER:
        ok = False
        report.add_discrepancy(f"guide: worked-example span order {classes} (expected {CELL_SPAN_ORDER})")
    if labels != HALF_LABELS:
        ok = False
        report.add_discrepancy(f"guide: worked-example labels {labels} (expected {HALF_LABELS})")
    if words != expected:
        ok = False
        report.add_discrepancy(f"guide: worked-example prints {words} (expected {expected})")
    report.add_line(f"[guide] worked-example cell prints {words} (expect {expected}) -> guide_example_ok={ok}")
    return ok


def parse_document(html_text: str, report: Report) -> tuple[dict[Position, CellContent], HeaderCheck]:
    parser = DiceTableParser()
    parser.feed(html_text)

    page_order = [page.die1 for page in parser.pages]
    expected_order = list(DIE_FACES)
    report.add_line(f"[parse] table pages found (by banner 1st die, in order) = {page_order}")
    if sorted(page_order) != expected_order:
        report.add_discrepancy(f"page set is {sorted(page_order)}, expected {expected_order}")
    if page_order != expected_order:
        report.add_discrepancy(f"page ORDER is {page_order}, expected ascending {expected_order}")

    headers = check_headers(parser.pages, report)
    headers.example_ok = check_guide_example(parser.example_cells, report)

    cells: dict[Position, CellContent] = {}
    duplicates: list[Position] = []
    for page in parser.pages:
        for position, content in read_page(page, report):
            if position in cells:
                duplicates.append(position)
            cells[position] = content

    if duplicates:
        unique = sorted(set(duplicates))
        shown = [position.label for position in unique[:20]]
        report.add_discrepancy(f"duplicate cell addresses in HTML: {shown} (n={len(unique)})")
    return cells, headers


def read_page(page: ParsedPage, report: Report) -> list[tuple[Position, CellContent]]:
    entries: list[tuple[Position, CellContent]] = []
    seen_rows: set[tuple[int, int]] = set()
    for cells in page.rows:
        header = read_row_header(page.die1, cells, report)
        if header is None:
            continue
        die2, die3 = header
        seen_rows.add(header)
        entries.extend(read_row_cells(page.die1, die2, die3, cells[2:], report))

    missing = {(die2, die3) for die2 in DIE_FACES for die3 in DIE_FACES} - seen_rows
    if missing:
        report.add_discrepancy(f"page 1st die={page.die1}: missing rows for (2nd,3rd) {sorted(missing)}")
    return entries


def read_row_header(die1: int, cells: list[ParsedCell], report: Report) -> tuple[int, int] | None:
    if len(cells) < 2 or cells[0].css_class != "idx" or cells[1].css_class != "idx":
        classes = [cell.css_class for cell in cells]
        report.add_parse_problem(f"page 1st die={die1}: row without two leading idx cells: {classes}")
        return None
    try:
        return int(cells[0].text), int(cells[1].text)
    except ValueError:
        report.add_parse_problem(f"page 1st die={die1}: non-int idx cells {cells[0].text!r},{cells[1].text!r}")
        return None


def read_row_cells(
    die1: int, die2: int, die3: int, data_cells: list[ParsedCell], report: Report
) -> list[tuple[Position, CellContent]]:
    if len(data_cells) == 1 and data_cells[0].css_class == "reroll":
        return read_full_row_reroll(die1, die2, die3, data_cells[0], report)

    if len(data_cells) != len(DIE_FACES):
        report.add_parse_problem(
            f"page 1st die={die1} row (2nd={die2},3rd={die3}): {len(data_cells)} data cells (expected {len(DIE_FACES)})"
        )

    entries: list[tuple[Position, CellContent]] = []
    # strict=False: a wrong-length row is a finding reported just above, not a crash.
    for die4, cell in zip(DIE_FACES, data_cells, strict=False):
        position = Position(die1, die2, die3, die4)
        entries.append((position, read_cell(position, cell, report)))
    return entries


def read_full_row_reroll(
    die1: int, die2: int, die3: int, cell: ParsedCell, report: Report
) -> list[tuple[Position, CellContent]]:
    where = f"page 1st die={die1} row (2nd={die2},3rd={die3})"
    if cell.colspan != len(DIE_FACES):
        report.add_parse_problem(f"{where}: full-row reroll colspan={cell.colspan} (!={len(DIE_FACES)})")
    if "RE-ROLL" not in cell.text:
        report.add_parse_problem(f"{where}: full-row reroll missing RE-ROLL text")
    if cell.texts_of("w"):
        report.add_parse_problem(f"{where}: full-row reroll unexpectedly holds words")
    return [(Position(die1, die2, die3, die4), CellContent(CellKind.REROLL_ROW)) for die4 in DIE_FACES]


def read_cell(position: Position, cell: ParsedCell, report: Report) -> CellContent:
    where = f"({position.label})"
    if cell.css_class == "reroll":
        if "RE-ROLL" not in cell.text:
            report.add_parse_problem(f"{where}: reroll cell missing RE-ROLL text")
        if cell.texts_of("w"):
            report.add_parse_problem(f"{where}: reroll cell holds words")
        return CellContent(CellKind.REROLL_CELL)

    if cell.css_class != "wc":
        report.add_parse_problem(f"{where}: unexpected cell class {cell.css_class!r}")
        return CellContent(CellKind.UNRECOGNIZED)

    labels = cell.texts_of("el")
    words = cell.texts_of("w")
    if labels != HALF_LABELS:
        report.add_parse_problem(f"{where}: labels {labels} (expected {HALF_LABELS})")
    if cell.span_classes() != CELL_SPAN_ORDER:
        report.add_parse_problem(f"{where}: span order {cell.span_classes()} (expected {CELL_SPAN_ORDER})")
    if len(words) != WORDS_PER_CELL:
        report.add_parse_problem(f"{where}: {len(words)} words in cell (expected {WORDS_PER_CELL})")
    return CellContent(
        CellKind.WORDS,
        top=words[0] if len(words) > 0 else None,
        bottom=words[1] if len(words) > 1 else None,
    )


def all_positions() -> list[Position]:
    return [Position(*faces) for faces in product(DIE_FACES, repeat=4)]


def cross_check(cells: dict[Position, CellContent], words: list[str], report: Report) -> CrossCheck:
    result = CrossCheck()
    for position in all_positions():
        result.cells_checked += 1
        content = cells.get(position)
        if content is None:
            report.add_discrepancy(f"({position.label}): MISSING cell in HTML")
            continue

        if is_reroll(position.die1, position.die2) or is_reroll(position.die3, position.die4):
            if content.is_reroll:
                result.rerolls_verified += 1
            else:
                report.add_discrepancy(f"({position.label}): expected RE-ROLL, got {content.kind.value}")
            continue

        if content.kind is not CellKind.WORDS:
            report.add_discrepancy(f"({position.label}): expected word cell, got {content.kind.value}")
            continue

        halves = (("TOP", TOP_HALF_DIE5, content.top), ("BOTTOM", BOTTOM_HALF_DIE5, content.bottom))
        for half, die5, found in halves:
            index = word_index(*position, die5)
            if found == words[index]:
                result.words_verified += 1
            else:
                report.add_discrepancy(
                    f"({position.label}) {half}: expected {words[index]!r} (idx {index}), got {found!r}"
                )
            if index in result.index_sources:
                _, owner = result.index_sources[index]
                report.add_discrepancy(
                    f"index {index} implied by multiple cells: ({owner.label}) and ({position.label})"
                )
            result.index_sources[index] = (found, position)
    return result


def check_coverage(cross: CrossCheck, words: list[str], report: Report) -> None:
    implied = set(cross.index_sources)
    expected = set(range(WORDLIST_SIZE))
    cross.coverage_complete = implied == expected

    missing = sorted(expected - implied)
    extra = sorted(implied - expected)
    if missing:
        tail = " ..." if len(missing) > 20 else ""
        report.add_discrepancy(f"coverage: missing indices {missing[:20]}{tail} (n={len(missing)})")
    if extra:
        report.add_discrepancy(f"coverage: extra/out-of-range indices {extra[:20]} (n={len(extra)})")

    for index, (found, position) in cross.index_sources.items():
        if index in expected and words[index] != found:
            cross.index_mismatches += 1
            report.add_discrepancy(
                f"index {index}: HTML word {found!r} != wordlist {words[index]!r} (cell {position.label})"
            )


def verdict(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


def write_summary(
    report: Report,
    wordlist: WordlistCheck,
    cells: dict[Position, CellContent],
    cross: CrossCheck,
    headers: HeaderCheck,
) -> None:
    word_cells = sum(1 for content in cells.values() if content.kind is CellKind.WORDS)
    reroll_cells = sum(1 for content in cells.values() if content.is_reroll)

    report.add_line("")
    report.add_line("================ RESULTS ================")
    report.add_line(f"wordlist hash .............. {verdict(wordlist.hash_ok)}")
    report.add_line(f"wordlist anchors ........... {verdict(wordlist.anchors_ok)}")
    report.add_line(f"pair rank sanity ........... {verdict(pair_rank_ok())}")
    report.add_line(f"example indices ............ {verdict(example_indices_ok(wordlist.words))}")
    report.add_line(
        f"4th-die column headers ..... {verdict(headers.columns_ok)} "
        f"({headers.sheets} sheets, expected {len(DIE_FACES)})"
    )
    report.add_line(f"row axis labels 2nd/3rd .... {verdict(headers.axes_ok)}")
    report.add_line(f"4th-die group header ....... {verdict(headers.group_ok)}")
    report.add_line(f"guide worked example ....... {verdict(headers.example_ok)}")
    report.add_line(f"cells cross-checked ........ {cross.cells_checked} (expected {EXPECTED_TOTAL_CELLS})")
    report.add_line(f"  word cells ............... {word_cells} (expected {EXPECTED_WORD_CELLS})")
    report.add_line(f"  reroll cells ............. {reroll_cells} (expected {EXPECTED_REROLL_CELLS})")
    report.add_line(f"words verified (top+bot).... {cross.words_verified} (expected {EXPECTED_WORD_SLOTS})")
    report.add_line(f"rerolls verified ........... {cross.rerolls_verified} (expected {EXPECTED_REROLL_CELLS})")
    report.add_line(
        f"coverage 0..{WORDLIST_SIZE - 1} each once.. {verdict(cross.coverage_complete)} "
        f"(distinct indices={cross.distinct_indices})"
    )
    report.add_line(
        f"words match wordlist@idx.... {verdict(cross.index_mismatches == 0)} (mismatches={cross.index_mismatches})"
    )
    report.add_line(f"discrepancies total ........ {len(report.discrepancies)}")
    report.add_line("")

    if not report.discrepancies:
        report.add_line("AUDIT RESULT: PASS")
        return

    report.add_line("---- DISCREPANCIES ----")
    for item in report.discrepancies[:MAX_DISCREPANCIES_SHOWN]:
        report.add_line("  " + item)
    hidden = len(report.discrepancies) - MAX_DISCREPANCIES_SHOWN
    if hidden > 0:
        report.add_line(f"  ... and {hidden} more")
    report.add_line("")
    report.add_line(f"AUDIT RESULT: FAIL ({len(report.discrepancies)} discrepancies)")


def main() -> None:
    report = Report()
    wordlist = verify_wordlist(WORDLIST_PATH, report)
    if not wordlist.ok:
        report.add_line("FATAL: wordlist verification failed; aborting.")
        print(report.text())
        sys.exit(1)

    verify_mapping(wordlist.words, report)
    cells, headers = parse_document(read_html(HTML_PATH), report)
    cross = cross_check(cells, wordlist.words, report)
    check_coverage(cross, wordlist.words, report)
    write_summary(report, wordlist, cells, cross, headers)
    print(report.text())
    sys.exit(1 if report.discrepancies else 0)


if __name__ == "__main__":
    main()
