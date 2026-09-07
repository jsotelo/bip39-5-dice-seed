# How the mapping works

This document explains how five six-sided dice select one of 2048 BIP39 words
uniformly, and how that mapping is laid out on the printed page. For the
security consequences see the [security model](security.md). For instructions on
building and checking the tables yourself see
[build and verify](build-and-verify.md).

## Why some throws must be rejected

Five d6 produce 6^5 = 7776 equally likely outcomes. The BIP39 wordlist has 2048
words. 2048 does not divide 7776, so no assignment of all 7776 outcomes to words
can be uniform. Some words would get four outcomes and others three.

The fix is rejection sampling. Accept a subset of outcomes whose size is a
multiple of 2048, and throw the dice again for anything outside it. The largest
multiple of 2048 that fits inside 7776 is 3 * 2048 = 6144, which leaves 1632
outcomes rejected. That is 1632 / 7776, or about 21% of throws.

That figure is a floor, not a design choice. Accepting any larger set would make
the set size not a multiple of 2048 and reintroduce bias. No cleverer layout of
five d6 can beat it. In practice it costs about 1.27 throws per accepted word.

## Where the rejection is placed

The rejection rule works on pairs of dice. A pair `(x, y)` is rejected when both
dice show 5 or 6. Four of the 36 ordered pairs meet that test, so 32 survive, and
32 is exactly 2^5.

The five dice are read left to right and split into two pairs plus a spare:

- The **1st and 2nd dice** form the first pair. 32 accepted values, 5 bits.
- The **3rd and 4th dice** form the second pair. 32 accepted values, 5 bits.
- The **5th die** contributes one bit. 1 to 3 is 0, and 4 to 6 is 1. Three faces
  each, so the split is exactly even.

A throw is rejected if either pair is rejected. That gives 32 * 32 * 6 = 6144
accepted outcomes, matching the count above, and 32 * 32 * 2 = 2048 distinct
results. Each word is reachable by exactly three throws, one for each face of
the 5th die on its side of the split.

## The index formula

The 32 accepted pairs are ranked 0 to 31 in row-major order over `(x, y)`, with
`x` the earlier die, skipping the four rejected pairs. The ranking runs
`(1,1)`, `(1,2)`, ... `(1,6)`, `(2,1)`, ... `(4,6)`, `(5,1)`, ... `(5,4)`,
`(6,1)`, ... `(6,4)`. Call that ranking `RANK`.

Reading the dice left to right as `a b c d e`:

```
index = 64 * RANK[(a, b)] + 2 * RANK[(c, d)] + bit
bit   = 0 if e in {1, 2, 3} else 1
```

The multipliers follow from the block sizes. The second pair and the 5th die
together address 32 * 2 = 64 words, so the first pair advances the index in
steps of 64. Within a block, the second pair addresses 32 word pairs, so it
advances in steps of 2, and the 5th die picks one of the two.

The result is a bijection. Every accepted throw yields an index in 0 to 2047, and
every index in that range is produced by exactly one `(a, b, c, d)` combination
and one half of the 5th die.

## The printed layout

The document is 7 pages. Page 1 is the guide. Pages 2 to 7 are the six lookup
tables, one per value of the 1st die. Within a table:

| Axis | Die |
|---|---|
| Page (which of the six sheets) | 1st |
| Row, outer | 2nd |
| Row, inner | 3rd |
| Column | 4th |
| Top or bottom word in the cell | 5th |

Each table has 36 rows, one for every `(2nd, 3rd)` combination, and 6 columns.
Six sheets of 36 by 6 give 1296 grid positions. Of those, 1024 hold a cell with
two words, which is 2048 words in total, each appearing exactly once. The
remaining 272 positions are marked RE-ROLL.

The layout keeps the dice in reading order. You walk the page, the row, the
column, and then the cell in the same sequence you read the dice off the table,
so nothing has to be reordered or remembered. That choice has one visible cost,
described next.

## Why RE-ROLL is not one tidy block

This is the most confusing thing about the printed tables, and it is worth
understanding before you use them.

The rejection rule pairs the 1st die with the 2nd, and the 3rd with the 4th. The
printed axes are page (1st), row (2nd then 3rd), and column (4th). The two
groupings cut across each other. Each ranked pair straddles two different printed
axes, so neither one lines up with a rectangle on the page.

The consequences are:

- **Whole rows go RE-ROLL** when the 1st and 2nd dice are both 5 or 6. The 1st
  die is the page, so this only happens on pages 5 and 6. On each of those pages
  the 12 rows where the 2nd die is 5 or 6 are struck out entirely, as two blocks
  of 6 consecutive rows. That is 144 of the 272 rejected positions.
- **The two right-hand columns go RE-ROLL** when the 3rd and 4th dice are both 5
  or 6. The 4th die is the column, so only the columns headed 5 and 6 are
  affected, and only in the rows whose 3rd die is 5 or 6. That accounts for the
  remaining 128 positions, scattered as four cells in each surviving block of
  six rows.

Nothing is missing or misprinted. Both patterns are the rejection rule showing
through a layout organized on different axes. A cell marked RE-ROLL means the
throw is discarded and all five dice are rolled again.

## Related documents

- [README](../README.md), the quickstart.
- [Security model](security.md), the entropy accounting and limitations.
- [Build and verify](build-and-verify.md), how to regenerate and check the tables.
