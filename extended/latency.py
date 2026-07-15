#!/usr/bin/env python3
"""Single-request latency — the dimension upstream explicitly disclaims.

Measures cold + warm latency for one unit of work on each available stack:
  - stdlib reference : busy(iters) direct call (the physical floor)
  - langchain        : the same work wrapped in a RunnableLambda .invoke() (real framework overhead)
  - rocketride       : one .pipe invocation via the SDK, IF ROCKETRIDE_URI/AUTH are set (else skipped)

Reports cold (first call) and warm p50/p95 over N reps, so 'framework overhead' is visible per request.
"""
import json, os, sys, time, statistics

HARNESS = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "..", "concurrent-work", "harness", "rocketride-bench")
sys.path.insert(0, HARNESS)
from harness.competitors import busy, calibrate_iters  # noqa: E402

REPS = 30

def _stats(name, call):
    cold_t0 = time.perf_counter(); call(); cold = (time.perf_counter()-cold_t0)*1000
    warm = []
    for _ in range(REPS):
        t0 = time.perf_counter(); call(); warm.append((time.perf_counter()-t0)*1000)
    warm.sort()
    return {"stack": name, "cold_ms": round(cold,2),
            "warm_p50_ms": round(warm[len(warm)//2],2),
            "warm_p95_ms": round(warm[min(len(warm)-1,int(len(warm)*0.95))],2)}

def stdlib_ref(iters):
    return _stats("stdlib_ref", lambda: busy(iters))

def langchain_ref(iters):
    try:
        from langchain_core.runnables import RunnableLambda
    except Exception as e:
        return {"stack": "langchain", "skipped": "langchain not installed: %r" % e}
    chain = RunnableLambda(lambda _: busy(iters))
    return _stats("langchain", lambda: chain.invoke(0))

def rocketride_ref(iters):
    uri, auth = os.getenv("ROCKETRIDE_URI"), os.getenv("ROCKETRIDE_AUTH")
    if not (uri and auth):
        return {"stack": "rocketride", "skipped": "ROCKETRIDE_URI/AUTH not set — sign up + apply promo, then re-run"}
    try:
        from rocketride import Client  # SDK name per docs; adjust to actual export if needed
    except Exception as e:
        return {"stack": "rocketride", "skipped": "rocketride SDK not installed: %r" % e}
    try:
        client = Client(uri=uri, auth=auth)
        pipe = os.path.join(os.path.dirname(__file__), "latency_unit.pipe")
        return _stats("rocketride", lambda: client.run(pipe, inputs={"iters": iters}))
    except Exception as e:
        return {"stack": "rocketride", "error": "SDK call failed: %r" % e}

def main():
    iters = calibrate_iters(target_s=0.02)
    rows = [stdlib_ref(iters), langchain_ref(iters), rocketride_ref(iters)]
    out = {"unit": "busy(%d)" % iters, "reps": REPS, "rows": rows}
    os.makedirs(os.path.join(os.path.dirname(__file__), "results"), exist_ok=True)
    p = os.path.join(os.path.dirname(__file__), "results", "latency.json")
    open(p, "w").write(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2)); print("\nWrote", p)

if __name__ == "__main__":
    main()
