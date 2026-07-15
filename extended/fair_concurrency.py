#!/usr/bin/env python3
"""Correct-LangChain concurrency vs the SAME unit of work upstream uses.

Upstream's 'default LangChain' shares one SQLite connection across threads (an anti-pattern) and
runs GIL-bound CPU via .batch's thread pool. Here we run the CORRECT idioms and report the real
picture:

  - lc_threads_shared_conn : the upstream 'default' (reproduced, to show the failure)
  - lc_percall_conn_seq    : correct per-call connection, sequential (correct, baseline)
  - py_processes           : correct parallel CPU via ProcessPoolExecutor (the honest way to beat the GIL)

Unit of work = competitors.busy(iters) — AST-identical to the workload node, calibrated to ~0.25s.
No cloud account needed: this isolates *how LangChain is used*, which is the crux of the upstream claim.
"""
import json, os, sys, sqlite3, tempfile, time
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor

HARNESS = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "..", "concurrent-work", "harness", "rocketride-bench")
sys.path.insert(0, HARNESS)
from harness.competitors import busy, calibrate_iters  # noqa: E402

N = 16
WORKERS = 8

def _write(db_path, i, val):
    # correct: fresh connection per call
    c = sqlite3.connect(db_path); c.execute("INSERT INTO t(k,v) VALUES(?,?)", (i, val)); c.commit(); c.close()

def _setup(db_path):
    c = sqlite3.connect(db_path); c.execute("CREATE TABLE IF NOT EXISTS t(k INT, v REAL)"); c.commit(); c.close()

def _count(db_path):
    c = sqlite3.connect(db_path); n = c.execute("SELECT COUNT(*) FROM t").fetchone()[0]; c.close(); return n

def lc_threads_shared_conn(iters, db_path):
    """Reproduce upstream's anti-pattern: one connection shared across threads."""
    _setup(db_path); conn = sqlite3.connect(db_path, check_same_thread=False)
    ok = err = 0
    def task(i):
        nonlocal ok, err
        try:
            conn.execute("INSERT INTO t(k,v) VALUES(?,?)", (i, busy(iters))); conn.commit(); ok += 1
        except Exception:
            err += 1
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        list(ex.map(task, range(N)))
    wall = time.perf_counter() - t0; conn.close()
    return {"mode": "lc_threads_shared_conn", "wall_s": round(wall,3), "n_ok": ok, "n_err": err,
            "rows_persisted": _count(db_path), "expected": N}

def lc_percall_conn_seq(iters, db_path):
    """Correct idiom: per-call connection. Sequential (the honest correctness baseline)."""
    _setup(db_path); ok = 0
    t0 = time.perf_counter()
    for i in range(N):
        _write(db_path, i, busy(iters)); ok += 1
    wall = time.perf_counter() - t0
    return {"mode": "lc_percall_conn_seq", "wall_s": round(wall,3), "n_ok": ok, "n_err": 0,
            "rows_persisted": _count(db_path), "expected": N}

def py_processes(iters):
    """Correct parallel CPU: ProcessPoolExecutor sidesteps the GIL (what a C++ node also targets)."""
    t0 = time.perf_counter()
    with ProcessPoolExecutor(max_workers=WORKERS) as ex:
        list(ex.map(busy, [iters]*N))
    wall = time.perf_counter() - t0
    return {"mode": "py_processes", "wall_s": round(wall,3), "n_ok": N, "n_err": 0,
            "rows_persisted": None, "expected": N}

def main():
    iters = calibrate_iters(target_s=0.05)  # keep the demo quick but representative
    res = []
    with tempfile.TemporaryDirectory() as d:
        res.append(lc_threads_shared_conn(iters, os.path.join(d, "a.db")))
        res.append(lc_percall_conn_seq(iters, os.path.join(d, "b.db")))
    res.append(py_processes(iters))
    out = {"unit": "busy(%d) ~AST-identical to workload node" % iters, "N": N, "workers": WORKERS, "runs": res}
    os.makedirs(os.path.join(os.path.dirname(__file__), "results"), exist_ok=True)
    p = os.path.join(os.path.dirname(__file__), "results", "fair_concurrency.json")
    open(p, "w").write(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2)); print("\nWrote", p)

if __name__ == "__main__":
    main()
