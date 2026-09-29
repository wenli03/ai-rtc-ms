"""数字人画面回灌通道：常驻 WebRTC 观看者 + 最新帧落盘。

LiveTalking 的 WebRTC 媒体面走 UDP，仙宫云端口代理不转发 UDP，浏览器拿不到流。
本进程在同一台服务器内做"观看者"，把解码后的最新视频帧持续写成 latest.jpg，
由 web/server.js 以 MJPEG（multipart/x-mixed-replace）投给浏览器 —— 帧率受限、无音频，
是降级通道而非实时 WebRTC，用途是让数字人与文字会话同屏可取证。
"""
import asyncio, json, os, time
import urllib.request
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCConfiguration

BASE = "http://127.0.0.1:8010"
OUTDIR = "/root/aics/frames"
LATEST = os.path.join(OUTDIR, "latest.jpg")
STATUS = os.path.join(OUTDIR, "status.json")
MIN_WRITE_INTERVAL = 0.30   # ≈3fps 上限，避免磁盘被写满


def http_json(path, payload=None, method=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(BASE + path, data=data,
                                 headers={"Content-Type": "application/json"},
                                 method=method or ("POST" if data else "GET"))
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


stats = {"frames_seen": 0, "frames_written": 0, "last_write_ts": None, "sessionid": None,
         "conn": None, "started": time.time()}


def write_frame(arr):
    import cv2
    # OpenCV 按扩展名选编码器，临时文件必须以 .jpg 结尾
    tmp = os.path.join(OUTDIR, ".latest.tmp.jpg")
    cv2.imwrite(tmp, arr, [cv2.IMWRITE_JPEG_QUALITY, 82])
    os.replace(tmp, LATEST)          # 原子替换，避免 HTTP 侧读到半张图
    stats["frames_written"] += 1
    stats["last_write_ts"] = time.time()
    with open(STATUS, "w") as f:
        json.dump(stats, f, ensure_ascii=False)


async def drain(track, ended):
    last = 0.0
    while True:
        try:
            frame = await asyncio.wait_for(track.recv(), timeout=120)
        except Exception as e:
            print("recv end:", type(e).__name__, e, flush=True)
            ended.set()
            return
        stats["frames_seen"] += 1
        now = time.time()
        if now - last >= MIN_WRITE_INTERVAL:
            last = now
            write_frame(frame.to_ndarray(format="bgr24"))


async def one_session():
    pc = RTCPeerConnection(RTCConfiguration(iceServers=[]))
    ended = asyncio.Event()
    pc.addTransceiver("video", direction="recvonly")
    pc.addTransceiver("audio", direction="recvonly")

    @pc.on("connectionstatechange")
    async def on_cs():
        stats["conn"] = pc.connectionState
        print("connstate:", pc.connectionState, flush=True)
        if pc.connectionState in ("failed", "closed", "disconnected"):
            ended.set()

    @pc.on("track")
    async def on_track(track):
        print("track:", track.kind, flush=True)
        if track.kind == "video":
            asyncio.ensure_future(drain(track, ended))

    offer = await pc.createOffer()
    await pc.setLocalDescription(offer)
    await asyncio.sleep(0.3)
    ans = http_json("/offer", {"sdp": pc.localDescription.sdp, "type": "offer"})
    await pc.setRemoteDescription(RTCSessionDescription(sdp=ans["sdp"], type=ans["type"]))
    print("offer accepted, type=%s" % ans.get("type"), flush=True)

    await asyncio.sleep(2)
    sess = http_json("/api/admin/sessions", method="GET")
    sessions = sess.get("data", {}).get("sessions", [])
    if sessions:
        stats["sessionid"] = sessions[-1]["sessionid"]
    print("sessionid:", stats["sessionid"], "total sessions:", len(sessions), flush=True)

    await ended.wait()
    await pc.close()


async def main():
    os.makedirs(OUTDIR, exist_ok=True)
    while True:
        try:
            await one_session()
        except Exception as e:
            print("session error:", type(e).__name__, e, flush=True)
        print("reconnect in 10s", flush=True)
        await asyncio.sleep(10)


asyncio.run(main())
