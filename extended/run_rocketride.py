#!/usr/bin/env python3
"""Run the RocketRide side of the benchmark locally and print paste-back JSON.

WHY YOU'RE RUNNING THIS: RocketRide Cloud executes pipelines over a WebSocket (DAP)
that is blocked from Milo's environment (HTTP 403), so this one piece has to run from
your machine. Everything else (lines-of-code, fair LangChain concurrency, latency for
the LangChain side) is already done in the repo.

SETUP (once):
    python3.11 -m venv .rrvenv && . .rrvenv/bin/activate    # Python 3.11+ required
    pip install rocketride
    export ROCKETRIDE_URI=https://api.rocketride.ai
    export ROCKETRIDE_AUTH=rr_your_token_here

RUN:
    python extended/run_rocketride.py

Then copy the JSON block it prints (between the >>> markers) back into the chat.
"""
import os, sys, json, time, asyncio, inspect, statistics

REPS = 20
WARMUP = 3

def _get_token(connect_result):
    """ConnectResult is dict-like; find the session/pipeline token."""
    for k in ("token", "pipeline_token", "session_token", "access_token"):
        v = connect_result.get(k) if hasattr(connect_result, "get") else None
        if v:
            return v
    # sometimes nested
    for k in ("data", "result", "session"):
        d = connect_result.get(k) if hasattr(connect_result, "get") else None
        if isinstance(d, dict):
            for kk in ("token", "pipeline_token"):
                if d.get(kk):
                    return d[kk]
    return None

async def _await_maybe(x):
    return await x if inspect.iscoroutine(x) else x

async def main():
    uri = os.environ.get("ROCKETRIDE_URI", "https://api.rocketride.ai")
    auth = os.environ.get("ROCKETRIDE_AUTH")
    if not auth:
        print("ERROR: set ROCKETRIDE_AUTH (your rr_ token)", file=sys.stderr); sys.exit(2)

    import rocketride
    from rocketride.schema.question import Question

    out = {"env": {"uri": uri, "sdk": getattr(rocketride, "__version__", "?"),
                   "python": sys.version.split()[0]}, "rows": []}

    c = rocketride.RocketRideClient(uri=uri, auth=auth)
    try:
        res = await _await_maybe(c.connect(timeout=60))
    except Exception as e:
        print(json.dumps({"error": "connect failed: %r" % e}, indent=2)); sys.exit(1)

    token = _get_token(res) or auth  # fall back to api token if session token not surfaced

    # A minimal, deterministic question = one pipeline execution.
    def make_q():
        return Question(
            type="chat",
            instructions="Reply with exactly the word: pong",
            questions=["ping"],
            expectJson=False,
        )

    async def one_call():
        t0 = time.perf_counter()
        r = await _await_maybe(c.chat(token=token, question=make_q()))
        dt = (time.perf_counter() - t0) * 1000.0
        ans = None
        if isinstance(r, dict):
            a = r.get("answers")
            ans = (a[0] if isinstance(a, list) and a else str(a))[:60] if a else None
        return dt, ans

    # warm-up
    for _ in range(WARMUP):
        try: await one_call()
        except Exception as e:
            print(json.dumps({"error": "warmup chat failed: %r" % e}, indent=2)); 
            try: await _await_maybe(c.close())
            except: pass
            sys.exit(1)

    # cold already passed; now timed warm reps
    lat, sample_ans = [], None
    for i in range(REPS):
        dt, ans = await one_call()
        lat.append(dt)
        if sample_ans is None: sample_ans = ans
    lat.sort()
    def pct(p): return round(lat[min(len(lat)-1, int(len(lat)*p))], 2)
    out["rows"].append({
        "stack": "rocketride_cloud",
        "op": "chat(ping->pong) single request",
        "reps": REPS,
        "warm_p50_ms": pct(0.50), "warm_p95_ms": pct(0.95),
        "mean_ms": round(statistics.mean(lat), 2),
        "sample_answer": sample_ans,
    })

    try: await _await_maybe(c.close())
    except: pass

    print("\n>>> PASTE FROM HERE >>>")
    print(json.dumps(out, indent=2))
    print("<<< PASTE TO HERE <<<\n")

if __name__ == "__main__":
    asyncio.run(main())
