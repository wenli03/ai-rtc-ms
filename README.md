# ai-rtc-ms · AI 视频客服微服务（LiveKit + Agents + Ollama + LiveTalking）

企业 AI 视频客服的最小可运行内核：**对话基座**（LiveKit Agents + 本地大模型）与**数字人层**（LiveTalking / Wav2LiP GPU 唇形渲染）两层解耦，可在同一房间内以「客户 / AI 客服 / 人工坐席 / 管理员」多角色并发实测。

全部推理本地完成，**零云厂商 API Key、零 Docker**，适合内网与数据不出域场景。

## 架构

```
浏览器(客户/坐席) ──WSS──┐
                         ├─→ LiveKit Server (:7880 SFU+信令)
AI 客服 worker ──RPC──────┘        │
   │  (livekit-agents 1.8.3)       │ AgentDispatch 自动派生 job
   ▼                               ▼
Ollama qwen2.5:3b (:11434)   房间转写广播(topic=transcript)

LiveTalking (:8010) ──/offer WebRTC──→ 数字人音视频流（GPU 推理）
        └─ /human 文本驱动播报 · /api/admin/sessions 会话观测
```

## 目录

| 路径 | 说明 |
|---|---|
| `src/agent.py` | AI 客服 worker：注册 RPC `ask`，答完向房间广播 `[转写]` |
| `src/customer2.py` | 服务器端"第二客户"模拟器（自动化只能跟单标签页时用） |
| `src/probe_broadcast.py` | 转写广播探针，验证 topic 与到达性 |
| `src/lt_loopback.py` | 服务器环回 WebRTC 客户端，抓数字人真实帧 |
| `web/server.js` | token 发放 + 房间/dispatch 创建 + 静态托管(:3210)，按 Host 头推导公网 wss |
| `web/index.html` | 多角色共用页面，`?name=xxx` 切换身份；**发送按角色分流**：客户 → RPC 问 AI，其他角色 → `sendText` 广播（人工接管外呼 / 质检发言） |
| `deploy/` | 云主机远程执行器与部署脚本（凭据走环境变量） |
| `docs/` | 使用手册（云端实测）+ 本地复现指南 |
| `evidence/` | 实测截图与 GPU 取证帧 |

## 快速开始（单机）

```bash
# 1. LiveKit Server
./livekit-server --dev

# 2. 大模型
ollama serve &  ollama pull qwen2.5:3b

# 3. AI 客服 worker
pip install "livekit-agents==1.8.3"
export LIVEKIT_URL=ws://localhost:7880 LIVEKIT_API_KEY=devkey LIVEKIT_API_SECRET=secret
python src/agent.py start

# 4. 页面与 token 服务
cd web && npm install && node server.js
```

打开 `http://localhost:3210/?name=customer`，点「开始服务」即可提问。
再开一个窗口用 `?name=human-seat` 加入：既能实时旁听客户与 AI 的完整问答，也能**直接对房间内所有人说话**（人工接管外呼）。第三个窗口用 `?name=quality-admin` 即为质检/监听视角。

## 实测结论（2026-09-29，仙宫云 RTX 4090D）

| 项 | 结果 |
|---|---|
| 客户 ↔ AI 文字问答 | ✅ 通过 RPC `ask` 同步返回 |
| 房间转写广播（坐席旁听） | ✅ topic=`transcript` 自定义文本流 |
| 人工坐席接管外呼 | ✅ `sendText` 广播，客户与质检同屏实时收到（`evidence/09、10`） |
| 四参与者同房在线 | ✅ 浏览器成员列表与服务端 `listParticipants` 一致（`evidence/11`） |
| 接管后 AI 自动静默 | ❌ **未实现**，坐席发言后 AI 仍照常应答 —— 需服务端会话状态位 |
| 数字人 GPU 推理 | ✅ Wav2LiP 常驻 2532 MiB，环回抓到 7 帧，帧间像素差 5.8–6.8 |
| 浏览器直连数字人画面 | ❌ 端口代理不转发 UDP，WebRTC 媒体面无路径 |
| 语音 ASR | ⚠️ 未启用（funasr 未安装） |
| AI 首答 / 后续问答延迟 | 约 30s（冷启动加载 3B） / 约 3s |

细节、踩坑根因与复现命令见 **[`docs/使用手册-云端实测.md`](docs/使用手册-云端实测.md)**。

## 已知坑（复现前必读）

1. `send_text()` 默认 `topic=''`，SDK 会静默丢弃 —— 必须显式传 topic。
2. topic 不要用 `lk.chat`：该主题被 livekit-client 官方聊天协议（protobuf）占用，纯文本会被吞。用自定义主题。
3. Web SDK 的 `reader.readAll()` 返回 **string**（Python SDK 返回字节），直接 `TextDecoder().decode()` 会抛类型错。
4. LiveTalking `/offer` 的客户端轨道必须是 **recvonly**，否则服务端 aiortc 抛 `ValueError: None is not in list` → HTTP 500。
5. 房间会残留历史 `agent-*` 僵尸参与者，RPC 打上去会 `Connection timeout`；前端按 `joinedAt` 取最新，服务端用 `deploy/remote/kick-all.sh` 清理。
6. `livekit-rtc` 这个 PyPI 包名不存在，装 `livekit-agents` 即可。
7. `livekit-server --dev` 已隐含 `devkey/secret`，再传 `--keys devkey=secret` 会报格式错（需 `key: secret` 带空格）。
8. 同一 identity 重复 `connect()`（例如脚本里点了两次「加入」）会触发重复身份互踢，先连的那条被静默断开 —— 一个身份只连一次，要多实例就换 identity。
9. 自己广播的话会在自己的面板里出现两遍（本地 `log()` + 房间回声），transcript handler 里要按 `sender === local.identity` 过滤回声。
10. 文本流只投递给"当时在房"的成员，**没有历史回放**；后入房的坐席看不到之前的问答。要做旁听/质检就得让坐席常驻房间，或由服务端落库后另走 HTTP 查询。
11. 自动化测试只能跟住单标签页时，用**同源 iframe** 加载 `?name=xxx` 即可获得真实的第二/第三个 LiveKit 参与者（独立文档、独立连接），比服务器端模拟更接近浏览器现场。

## License

LiveKit (Apache-2.0)、LiveTalking (LGPL-3.0)、Wav2LiP 权重 —— 商用前请自行完成 License 合规审查。
