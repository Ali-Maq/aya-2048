# AYA 2048

Recover one deterministic game mechanic from a compiled open-source reference, then integrate it in a browser game.

The reference is [mevdschee/2048.c](https://github.com/mevdschee/2048.c), MIT licensed, pinned in `evidence/provenance.json`. The original source remains available for reproducibility. Hermes will receive the binary, the contract, and REA tools, not the C source.

The recovered scope is tile movement, merge ordering, and scoring. Random spawning and the browser interface are application code. This is not reconstruction of the whole game.
