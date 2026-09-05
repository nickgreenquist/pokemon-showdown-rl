# LADDER R4 — board evidence

A screenshot of the public `gen1randombattle` top-500 board taken by the
maintainer during LADDER R4 to collect evidence of the account being listed.
No stopping decision attached to the viewing — the run went to n = 200 by the
mechanical rule (ladder_r4.yaml G-BLIND; the readout states it).

| file | taken (local, EDT) | shows |
|---|---|---|
| `2026-09-04_2116_top500_rank369.png` | 2026-09-04 21:16 (between battles 114 and 115; the JSONL's pre-battle rating for battle 115 is 1393) | `nickgen1rbrlbot` at **rank 369**, Elo **1394**, GXE **63.2 %**, Glicko-1 **1602 ± 25**; ranks 364–396 span Elo 1396–1387 |

Cross-check against the run's own record: battle 114 (a win) finished 21:12:41
EDT and lifted the pre-battle rating to 1393; battle 115 (a loss, 21:17:16)
dropped it to 1359 — the excursion this screenshot caught lasted one battle,
which is what the readout's "13 excursions over 42 listed battles" looks like
from the board's side. The replay-derived exposure statistics in
`readouts/LADDER_R4_READOUT.md` stand on their own; the peak pre-battle Elo
was 1431 (before battle 176), which no screenshot captured.
