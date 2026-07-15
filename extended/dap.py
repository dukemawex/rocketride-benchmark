"""Minimal direct DAP client for RocketRide Cloud — bypasses the SDK handshake that
stalls in headless environments. Speaks the wire protocol the SDK uses:
  frame = json_header + b"\n" + binary_payload   (over wss://<host>/task/service)
"""
import asyncio, os, json, time, websockets

class Dap:
    def __init__(self, uri=None, auth=None, path="/task/service"):
        host=(uri or os.environ.get("ROCKETRIDE_URI","https://api.rocketride.ai"))
        host=host.replace("https://","wss://").replace("http://","ws://").rstrip("/")
        self.url=host+path
        self.auth=auth or os.environ["ROCKETRIDE_AUTH"]
        self.ws=None; self.seq=0; self.usertoken=None; self.account=None

    def _f(self, msg, payload=b""):
        return json.dumps(msg).encode()+b"\n"+payload

    async def _recv(self, timeout=60):
        data=await asyncio.wait_for(self.ws.recv(), timeout=timeout)
        if isinstance(data,str): data=data.encode()
        nl=data.find(b"\n"); hdr=data[:nl] if nl>=0 else data
        payload=data[nl+1:] if nl>=0 else b""
        try: j=json.loads(hdr.decode("utf-8","replace"))
        except Exception: j={"_raw":hdr[:120].decode('utf-8','replace')}
        return j, payload

    async def connect(self, timeout=25):
        self.ws=await asyncio.wait_for(websockets.connect(self.url, max_size=None, open_timeout=timeout), timeout=timeout+5)
        self.seq+=1
        await self.ws.send(self._f({"type":"request","command":"auth","seq":self.seq,
                                    "arguments":{"auth":self.auth,"clientName":"bench","clientVersion":"1.0"}}))
        j,_=await self._recv(timeout)
        if not j.get("success"): raise RuntimeError("auth failed: %s"%json.dumps(j)[:200])
        b=j.get("body",{}); self.usertoken=b.get("userToken"); self.account=b.get("displayName")
        return b

    async def call(self, command, timeout=120, **args):
        self.seq+=1
        await self.ws.send(self._f({"type":"request","command":command,"seq":self.seq,"arguments":args}))
        # read until we get the response matching our seq (skip events)
        deadline=time.time()+timeout
        while time.time()<deadline:
            j,payload=await self._recv(timeout)
            if j.get("type")=="response" and j.get("request_seq")==self.seq:
                return j, payload
        raise TimeoutError("no response for %s"%command)

    async def close(self):
        try:
            if self.ws: await self.ws.close()
        except: pass
