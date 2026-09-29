#!/bin/bash
# 清理房间内所有参与者（含残留的僵尸 agent-*），并打印剩余成员
export PATH=/root/miniconda3/bin:$PATH
cd /root/aics/demo/web
node -e '
const {RoomServiceClient}=require("livekit-server-sdk");
(async()=>{
  const r=new RoomServiceClient("http://localhost:7880","devkey","secret");
  for(const p of await r.listParticipants("cs-demo")){
    try{ await r.removeParticipant("cs-demo",p.identity); console.log("kicked",p.identity); }catch(e){ console.log("err",p.identity,e.message); }
  }
  await new Promise(x=>setTimeout(x,4000));
  console.log("remaining:", (await r.listParticipants("cs-demo")).map(p=>p.identity).join(", ")||"(none)");
})().catch(e=>console.log("fatal",e.message));'
