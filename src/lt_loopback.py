import asyncio, json, os, time
import urllib.request
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCConfiguration

BASE = "http://127.0.0.1:8010"
OUTDIR = "/root/aics/frames"
FRAME_TARGET = 7

def http_json(path, payload=None, method=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(BASE + path, data=data,
                                 headers={"Content-Type": "application/json"},
                                 method=method or ("POST" if data else "GET"))
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())

saved = []
t_first = None

async def main():
    global t_first
    os.makedirs(OUTDIR, exist_ok=True)
    pc = RTCPeerConnection(RTCConfiguration(iceServers=[]))
    pc.addTransceiver("video", direction="recvonly")
    pc.addTransceiver("audio", direction="recvonly")

    @pc.on("connectionstatechange")
    async def on_cs():
        print("connstate:", pc.connectionState, flush=True)

    @pc.on("iceconnectionstatechange")
    async def on_ice():
        print("icestate:", pc.iceConnectionState, flush=True)

    @pc.on("track")
    async def on_track(track):
        print("track:", track.kind, flush=True)
        if track.kind == "video":
            asyncio.ensure_future(drain(track))

    async def drain(track):
        global t_first
        n = 0
        while len(saved) < FRAME_TARGET:
            try:
                frame = await asyncio.wait_for(track.recv(), timeout=90)
            except Exception as e:
                print("recv end:", type(e).__name__, e, flush=True)
                break
            now = time.time()
            if t_first is None:
                t_first = now
                print("FIRST FRAME at t=0", flush=True)
            el = now - t_first
            if n == 0 or el >= (len(saved)) * 4.0:
                import cv2
                arr = frame.to_ndarray(format="bgr24")
                fn = os.path.join(OUTDIR, "lt_%02d_t%05.1fs.jpg" % (len(saved), el))
                cv2.imwrite(fn, arr)
                saved.append(fn)
                print("saved", fn, flush=True)
            n += 1

    offer = await pc.createOffer()
    await pc.setLocalDescription(offer)
    await asyncio.sleep(0.3)
    local_sdp = pc.localDescription.sdp

    ans = http_json("/offer", {"sdp": local_sdp, "type": "offer"})
    print("offer ok, type=%s" % ans.get("type"), flush=True)
    await pc.setRemoteDescription(RTCSessionDescription(sdp=ans["sdp"], type=ans["type"]))
    for ln in ans["sdp"].split("\n"):
        if ln.startswith("m=") or "a=send" in ln or "a=recv" in ln or "a=inactive" in ln:
            print("ANS:", ln.strip()[:80], flush=True)

    await asyncio.sleep(2)
    sess = http_json("/api/admin/sessions", method="GET")
    sessions = sess.get("data", {}).get("sessions", [])
    print("sessions:", [s["sessionid"] for s in sessions], flush=True)
    sid = sessions[-1]["sessionid"] if sessions else None
    if sid is None:
        print("NO SESSION FOUND", flush=True)
        return

    import cv2  # preload
    for i, text in enumerate(["您好，我是AI视频客服小助手。",
                              "请问有什么可以帮您？",
                              "我们支持七天无理由退款，退货包运费。"]):
        r = http_json("/human", {"sessionid": sid, "text": text, "type": "echo"})
        print("human#%d ->" % i, json.dumps(r)[:100], flush=True)
        await asyncio.sleep(8)

    deadline = time.time() + 120
    while len(saved) < FRAME_TARGET and time.time() < deadline:
        await asyncio.sleep(1)

    await pc.close()
    print("DONE saved=%d" % len(saved), flush=True)

asyncio.run(main())
