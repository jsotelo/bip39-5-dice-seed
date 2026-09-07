# Security model

What this design guarantees, and what it does not. The mechanics behind these
claims are in [how it works](how-it-works.md), and the commands that check them
are in [build and verify](build-and-verify.md).

## Entropy

The dice supply 253 bits. That is 23 words at 11 bits each, and every one of
those bits comes from a physical throw.

The 24th word is a checksum over the first 23. It also carries the 3 remaining
entropy bits of a 24-word phrase, which the first 23 words do not cover, so
exactly 8 different words are valid in the 24th position. A BIP39 tool will offer
all of them. Any one is fine. Pick one and the seed is complete.

For scale, 128 bits is already considered cryptographically secure. 253 bits of
dice entropy is far beyond any practical attack, and the margin is not close
enough to be worth arguing about.

## Uniformity

Every accepted throw maps to a word with exactly equal probability. There is no
bias to correct for and no word that is slightly more likely than another.

This holds because throws are rejected rather than folded. Five d6 give 7776
outcomes, 2048 does not divide 7776, and any scheme that assigns all 7776
outcomes to words gives some words four throws and others three. Instead, 6144
outcomes are accepted and the other 1632 (about 21%) are rejected as RE-ROLL.
6144 is exactly 3 * 2048, so each word gets exactly three throws.

The generator asserts that the rendered tables cover all 2048 words exactly once,
the test suite proves the mapping is a bijection, and the independent audit
re-checks the printed document against the wordlist. Uniformity is a verifiable
property here, not a claim you have to take on faith.

## No trusted electronics for the entropy

The dice are the entropy source. Nothing electronic touches the 23 words. There
is no random number generator to audit, no firmware to trust, and no way for a
compromised machine to influence which words you get.

A device is used exactly once, at the end, to compute the 24th word. That step
is deterministic: the 24th word is fully determined (up to the 8 valid choices)
by the 23 words you already have. Computing it does not reduce the strength of
the seed.

The risk in that step is the device, not the math. Use a hardware wallet or a
purpose-built air-gapped signer, for example SeedSigner or Blockstream Jade.

Do not use your everyday phone or laptop, and note that switching off the wifi
does not make one safe. A general-purpose machine has a disk that remembers, an
operating system you did not audit, and a network stack that will come back up.
Anything that puts your words on such a machine has handed over the seed,
regardless of how carefully the words were generated.

## Position, not faces

Each die's role is fixed by where it lands in the row, 1st through 5th. It is
never fixed by the number it shows.

This matters more than it looks. Re-rolling or rearranging dice after seeing
their faces is precisely what destroys uniformity, because the choice of what to
redo is then correlated with the outcome. Deciding roles by position removes the
opportunity to make that mistake. The printed guide states the rule prominently
for the same reason.

The same logic covers repeats. A repeated word in a 23-word list is normal and
expected. Re-rolling to avoid one biases the seed.

## Limits

- **The dice are the weak point.** These tables map dice to words uniformly.
  They cannot fix an unfair die. Use five identical dice, and prefer precision
  dice (sold as casino dice), which are machined for even weight and sharp
  edges. A worn or cheaply moulded die produces a biased seed.
- **The paper is a secret.** Once you have written the words down, the sheet is
  your seed. Protect it accordingly. Nothing in this project helps with storage,
  backup, or duress.
- **Verify the document you print.** Run the audit against the HTML you actually
  generated. A document handed to you by someone else is only as trustworthy as
  your check of it.
- **Offline means offline.** Generate the seed away from networked machines, and
  keep the checksum step offline too.

## Disclaimer

This tool generates the first 23 words of a 24-word BIP39 seed. You are
responsible for verifying it yourself (run the audit, check the hash) and for
securing the resulting seed. Generate seeds offline. Provided without warranty,
see [LICENSE](../LICENSE).

## Related documents

- [README](../README.md), the quickstart.
- [How it works](how-it-works.md), the mapping and the page layout.
- [Build and verify](build-and-verify.md), the audit, tests, and wordlist
  provenance.
