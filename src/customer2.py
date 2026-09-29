"""客户角色脚本：入房 -> RPC 问 AI -> 保持在线 40s（供坐席端截图）"""
import asyncio, json, urllib.request
from livekit import rtc

async def main():
    r = json.load(urllib.request.urlopen('http://127.0.0.1:3210/start'))
    url, token, room_name = r['url'], r['token'], r['room']
    print('room=', room_name, 'url=', url)
    room = rtc.Room()
    agent_id = None

    def find_agent():
        nonlocal agent_id
        for p in room.remote_participants.values():
            if str(p.identity).startswith('agent-'):
                agent_id = str(p.identity)
                return True
        return False

    @room.on("participant_connected")
    def on_pc(p):
        print("joined:", p.identity, getattr(p, "name", ""))
        find_agent()

    await room.connect(url, token)
    print("local identity:", room.local_participant.identity)
    find_agent()
    for _ in range(30):
        if agent_id:
            break
        await asyncio.sleep(0.5)
    if not agent_id:
        print("NO AGENT FOUND"); return
    print("asking AI via RPC...")
    result = await room.local_participant.perform_rpc(
        destination_identity=agent_id, method="ask", payload="你们多久发货？支持哪些快递？"
    )
    print("AI answer:", result)
    print("staying online 40s for seat-side screenshot...")
    await asyncio.sleep(40)

asyncio.run(main())
