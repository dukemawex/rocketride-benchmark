# Extended Benchmark — the fair dimensions the upstream suite skips

Independent addition by **Emmanuel Effiom Duke** ([duker.me](https://duker.me)) on top of the
upstream RocketRide vs LangChain suite. The upstream repo is technically honest but frames
**RocketRide's safe default vs LangChain's *worst* default**. This layer adds the two
comparisons a fair reviewer wants:

1. **Single-request latency** — the dimension upstream explicitly disclaims. What does one
   request actually cost, cold and warm, on each stack?
2. **Correctly-written LangChain concurrency** — instead of the shared-SQLite-connection
   anti-pattern, use the idiomatic correct build (per-call connection; `ProcessPoolExecutor`
   for GIL-bound CPU work). Same AST-identical `busy()` unit of work as upstream, so the
   comparison stays fair.

Goal: report **where RocketRide genuinely wins and where LangChain, done right, holds its own** —
honest results either way, exactly as the client asked.

## Run
```bash
pip install -r ../concurrent-work/harness/rocketride-bench/requirements-competitors.txt
python latency.py            # single-request latency (no cloud needed for the LC side)
python fair_concurrency.py   # correct LangChain concurrency vs the same unit of work
```
The RocketRide side of latency reads `ROCKETRIDE_URI` / `ROCKETRIDE_AUTH` when a token is present;
without it, only the LangChain/stdlib reference numbers run, and RocketRide rows are marked `skipped`.
