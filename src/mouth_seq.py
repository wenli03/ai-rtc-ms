"""触发 LiveTalking 播报并做"播报前基线 vs 播报期"的口部区域差分。

口部 ROI 依据实测帧定位：576x768 竖屏，人脸中心约 (0.43, 0.30)，嘴部约 (0.43, 0.37)。
因此取 y∈[0.30,0.45]、x∈[0.30,0.58] 为口部条带，另存 y∈[0.22,0.50]、x∈[0.24,0.62] 为人脸裁切供肉眼核对。
"""
import json, os, shutil, time, urllib.request
import cv2
import numpy as np

FRAME = "/root/aics/frames/latest.jpg"
SEQ = "/root/aics/frames/seq2"
BASE = "http://127.0.0.1:8010"
TEXT = ("您好，我是AI视频客服小助手。我们的退换货政策是七天无理由退货，"
        "请在收到商品后联系客服申请，感谢您的来电，祝您生活愉快。")
MOUTH = (0.30, 0.45, 0.30, 0.58)   # y0,y1,x0,x1
FACE = (0.22, 0.50, 0.24, 0.62)


def get_session():
    with urllib.request.urlopen(BASE + "/api/admin/sessions", timeout=10) as r:
        s = ((json.load(r).get("data") or {}).get("sessions")) or []
    return s[-1]["sessionid"] if s else None


def post_human(sid, text):
    body = json.dumps({"sessionid": sid, "text": text, "type": "echo"}).encode()
    req = urllib.request.Request(BASE + "/human", data=body,
                                headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode()


def roi_mouth(img):
    h, w = img.shape[:2]
    y0, y1, x0, x1 = MOUTH
    return cv2.cvtColor(img[int(h * y0):int(h * y1), int(w * x0):int(w * x1)],
                        cv2.COLOR_BGR2GRAY).astype(np.float32)


def grab():
    return cv2.imread(FRAME)


shutil.rmtree(SEQ, ignore_errors=True)
os.makedirs(SEQ, exist_ok=True)
sid = get_session()
print("sessionid:", sid, flush=True)

rows = []
ref = None


def snap(tag, i, tbase):
    global ref
    img = grab()
    if img is None:
        return
    h, w = img.shape[:2]
    m = roi_mouth(img)
    if ref is None:
        ref = m.copy()
    cv2.imwrite(os.path.join(SEQ, f"{tag}_{i:02d}.jpg"),
                img[int(h * FACE[0]):int(h * FACE[1]), int(w * FACE[2]):int(w * FACE[3])])
    r = {"tag": tag, "i": i, "t": round(time.time() - tbase, 2),
         "delta_vs_ref": round(float(np.abs(m - ref).mean()), 3),
         "mouth_mean": round(float(m.mean()), 2),
         "mouth_std": round(float(m.std()), 2)}
    rows.append(r)
    print(f"[{tag} {i:02d}] t={r['t']:6.2f} delta_vs_ref={r['delta_vs_ref']:6.3f} "
          f"mean={r['mouth_mean']} std={r['mouth_std']}", flush=True)


print("\n--- 播报前基线 12 帧 ---", flush=True)
tb = time.time()
for i in range(12):
    snap("pre", i, tb)
    time.sleep(0.3)

pre = [r["delta_vs_ref"] for r in rows if r["tag"] == "pre"]
print(f"pre  delta_vs_ref: mean={np.mean(pre):.3f} max={np.max(pre):.3f}\n", flush=True)

print("--- 触发 /human ---", flush=True)
tb = time.time()
print("resp:", post_human(sid, TEXT), flush=True)
for i in range(45):
    snap("say", i, tb)
    time.sleep(0.3)

say = [r["delta_vs_ref"] for r in rows if r["tag"] == "say"]
summary = {
    "sessionid": sid, "text": TEXT, "roi": MOUTH,
    "pre_delta_mean": round(float(np.mean(pre)), 3), "pre_delta_max": round(float(np.max(pre)), 3),
    "say_delta_mean": round(float(np.mean(say)), 3), "say_delta_max": round(float(np.max(say)), 3),
    "say_peak_t": round(say.index(max(say)) * 0.3, 2),
    "ratio_mean": round(float(np.mean(say) / max(1e-6, np.mean(pre))), 2),
}
print("\nSUMMARY", json.dumps(summary, ensure_ascii=False), flush=True)
with open(os.path.join(SEQ, "index.json"), "w") as f:
    json.dump({"summary": summary, "rows": rows}, f, ensure_ascii=False, indent=2)
print("saved", len(rows), "face crops ->", SEQ, flush=True)
