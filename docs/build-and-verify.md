# Build and verify

How to regenerate the document from source, print it, and check that what you
printed is correct. For the mapping itself see [how it works](how-it-works.md).
For what the verification buys you see the [security model](security.md).

## Requirements

[uv](https://docs.astral.sh/uv/), `make`, and Python 3.11 or newer. `uv`
installs the build dependency (`jinja2`) and the dev dependencies (`pytest` and
`ruff`) automatically, so there is nothing to install by hand.

The audit script is the exception. It is standard library only, so it runs under
any Python 3.10 or newer interpreter with no environment at all. It refuses to
run on anything older with a clear message rather than a traceback, which
matters on macOS, where `/usr/bin/python3` is still 3.9.

## Build

The default target regenerates the HTML, then lints, tests, and audits the
result:

```
make
```

| Target | Does |
|---|---|
| `make build` | Regenerates `dice_tables.html` from the wordlist and templates. |
| `make lint` | Runs `ruff check` over the Python sources. |
| `make format` | Rewrites the Python sources with `ruff format`. |
| `make test` | Runs the pytest mapping tests. |
| `make audit` | Runs the independent audit against the generated HTML. |
| `make verify` | `lint`, then `test`, then `audit`. |
| `make pdf` | Optional PDF snapshot via a headless Chromium browser. |
| `make clean` | Removes `__pycache__` and `.venv`. |

Without `make`, the generator runs directly:

```
uv run python generate_dice_tables.py
```

It prints the output path and confirms that the rendered sheets cover all 2048
words exactly once. It exits nonzero if they do not.

## Print

The document is designed to print correctly from any browser. Open
`dice_tables.html` and Save as PDF at **US Letter, default margins**. The CSS
sets zero page margins, so browsers add no headers or footers of their own.

For a scripted snapshot:

```
make pdf
```

That looks for an installed Chromium browser (Chrome, Chromium, Edge, or Brave)
and prints headlessly to `dice_tables.pdf`. If none is found it says so and
falls back to the manual instructions above. To point it at a specific binary:

```
make pdf CHROME="/path/to/chrome"
```

### Editing the guide page

The guide fills page 1 almost exactly. Adding a sentence to it can push the
overflow onto a second page, which shifts all six tables and turns the document
into 8 pages. The generator will not catch this, because it validates the
mapping rather than the pagination. After any edit to `templates/guide.html.j2`
or `templates/style.css`, run `make pdf` and confirm the result is still 7
pages.

## Audit

Do not trust, verify.

```
python3 audit_dice_tables.py
```

It needs Python 3.10 or newer and nothing else. A clean run ends with
`AUDIT RESULT: PASS`.

What it checks:

- The wordlist hash and its anchor words.
- Every one of the 1296 table positions. The displayed word must match the
  wordlist at the index the audit computes for itself.
- That all 2048 words appear exactly once, a perfect bijection onto 0 to 2047.
- That RE-ROLL appears exactly where a both-5/6 pair occurs, and holds no words.
- The printed headers a reader navigates by: the 4th-die column headers must
  read 1 to 6 in order on every sheet, the row axes must be labelled 2nd and
  3rd, and the group header must name the 4th die. A correct grid under a
  swapped header would send every lookup to the wrong word, so these are
  checked against the printed text rather than assumed from position.
- The worked example printed on the guide page, against the same index the
  audit derives.

What it does not check: the rest of the guide's prose. The instructions, the
entropy figure, and the safety rules on page 1 are English, not data, so read
them yourself before trusting a document someone else handed you.

### Why the audit is a separate program

The audit does not import the generator. It re-derives the entire mapping from
scratch, in its own code, and it reads the shipped HTML rather than any
in-memory structure.

That is deliberate, and it is the whole point of the exercise. An audit that
imported the generator would inherit every one of the generator's bugs. If the
rank ordering were wrong, both sides would be wrong the same way and the check
would pass. A program agreeing with itself is not evidence.

Two independent implementations agreeing is evidence. Reading the rendered HTML
extends that to the templates and the rendering step, so a bug anywhere between
the wordlist and the printed grid shows up as a mismatch. The audit is also
dependency-free for the same reason: it should be checkable by someone who does
not want to install this project's build stack.

## Tests

```
uv run pytest
```

`test_mapping.py` is the lighter self-test. It proves that 32 pairs survive the
rejection rule, that the index function is a perfect bijection over all 2048
indices with each index reachable in exactly three ways, and that the reroll rate
is 6144 accepted out of 7776, about 21%.

## Continuous integration

`.github/workflows/ci.yml` runs on every push and pull request. It regenerates
the HTML, fails if the result differs from the committed `dice_tables.html`,
lints, runs the tests, and runs the audit. The committed document is therefore
always the one the current source produces.

## Wordlist provenance

`bip39_english.txt` is the official BIP39 English wordlist, 2048 words, SHA-256:

```
2f5eed53a4727b4bf8880d8f3f199efc90e58503646d9ff8eff3a2ed3b24dbda
```

Anchor words: index 0 is `abandon`, index 512 is `divorce`, index 2047 is `zoo`.
Both the generator and the audit refuse to run if the hash does not match, and
both check the anchors.

## Repository contents

| Path | Purpose |
|---|---|
| `generate_dice_tables.py` | Builds `dice_tables.html` from the Jinja templates. Verifies the wordlist hash and asserts the tables cover all 2048 words exactly once. |
| `audit_dice_tables.py` | Independent, dependency-free verifier. Re-derives the mapping from scratch, parses the generated HTML, and cross-checks every cell against BIP39. |
| `test_mapping.py` | pytest tests proving the index function is a bijection with the correct reroll rate. |
| `templates/` | Jinja templates and `style.css` for the document (guide, table sheets, page shell). |
| `docs/` | This documentation and the README preview images. |
| `bip39_english.txt` | The official BIP39 English wordlist, pinned by hash. |
| `dice_tables.html` | The generated print document. |
| `dice_tables.pdf` | Optional PDF snapshot, print-ready at Letter size. |
| `Makefile` | Build and verification targets. |
| `pyproject.toml` | uv project config. Python 3.11+, `jinja2` to build, `pytest` for tests. |
| `.github/workflows/ci.yml` | CI: regenerate, check for drift, lint, test, audit. |

## Related documents

- [README](../README.md), the quickstart.
- [How it works](how-it-works.md), the mapping and the page layout.
- [Security model](security.md), the entropy accounting and limitations.
