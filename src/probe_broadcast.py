import asyncio, json, urllib.request
from livekit import rtc

def get(url):
    with urllib.request.urlopen(url, timeout=10) as r:
        return json.load(r)

async def main():
    d = get("http://127.0.0.1:3210/start")
    room = rtc.Room()
    got = []

    def on_text(reader, sender_identity):
        async def _read():
            txt = await reader.read_all()
            print("TEXT_STREAM from", sender_identity, "topic", reader.info.topic, ":", txt[:120], flush=True)
            got.append(txt)
        asyncio.ensure_future(_read())

    try:
        room.register_text_stream_handler("lk.chat", on_text)
        print("text stream handler registered", flush=True)
    except Exception as e:
        print("register handler err:", e, flush=True)

    @room.on("data_received")
    def on_data(data):
        try:
            txt = data.data.decode("utf-8")
        except Exception:
            txt = repr(data.data)
        pid = getattr(data.participant, "identity", "?")
        print("DATA_RECV from", pid, "topic", data.topic, ":", txt[:100], flush=True)
        got.append(txt)

    @room.on("participant_connected")
    def on_pc(p):
        print("peer join:", p.identity, flush=True)

    await room.connect(d["url"], d["token"])
    agents = []
    for _ in range(30):
        agents = [p.identity for p in room.remote_participants.values() if p.identity.startswith("agent-")]
        if agents:
            break
        await asyncio.sleep(1)
    print("connected; peers:", [p.identity for p in room.remote_participants.values()], flush=True)
    if not agents:
        print("NO AGENT IN ROOM", flush=True)
        return
    lp = room.local_participant
    try:
        reply = await lp.perform_rpc(destination_identity=agents[0], method="ask", payload="测试转写广播")
        print("RPC reply:", reply[:80], flush=True)
    except Exception as e:
        print("RPC err:", e, flush=True)
    for _ in range(10):
        await asyncio.sleep(1)
    print("total data messages received:", len(got), flush=True)
    await room.disconnect()

asyncio.run(main())
