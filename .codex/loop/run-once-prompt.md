Use $safe-grow.

Read `AGENTS.md` and the files under `.codex/loop/`.
Treat `.codex/loop/state.json` as the source of truth.

Process exactly one item:

1. continue unfinished work first
2. stay in `stabilize` while audit items remain
3. switch to `grow` only after audit work is exhausted
4. make the minimum safe change
5. verify immediately
6. update state and log
7. stop after one item

Final response must satisfy the output schema exactly.
