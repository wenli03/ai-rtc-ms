#!/bin/bash
# 仙宫云 / 任意 Ubuntu+CUDA 云主机上的一键部署脚本（在 /root/aics 下工作）
# 用法：XGY_SSH_* 配好后 → node deploy/ssh-run.js deploy/remote/setup-all.sh
set -e
export PATH=/root/miniconda3/bin:$PATH
mkdir -p /root/aics && cd /root/aics

# ---------- 1. LiveKit Server（Docker Hub 不可用时走 GitHub Releases 二进制）----------
if [ ! -x ./livekit-server ]; then
  curl -L -o lk.tar.gz https://github.com/livekit/livekit/releases/download/v1.13.7/livekit_1.13.7_linux_amd64.tar.gz
  tar -xzf lk.tar.gz
  chmod +x livekit-server
fi
nohup ./livekit-server --dev >> /root/aics/livekit.log 2>&1 &
# 注意：--dev 已隐含 devkey/secret；再传 --keys devkey=secret 会报格式错

# ---------- 2. Ollama + qwen2.5:3b ----------
if ! command -v ollama >/dev/null; then
  curl -L -o ollama.tgz https://github.com/ollama/ollama/releases/download/v0.12.6/ollama-linux-amd64.tgz
  tar -xzf ollama.tgz
fi
nohup ollama serve >> /root/aics/ollama.log 2>&1 &
sleep 3
ollama pull qwen2.5:3b

# ---------- 3. Agents worker ----------
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple "livekit-agents==1.8.3"
# 说明：livekit-rtc 这个包名在 PyPI 上不存在，装 livekit-agents 即可（自带 livekit.rtc）

# ---------- 4. Web + Token 服务 ----------
mkdir -p /root/aics/demo/web && cd /root/aics/demo/web
npm install livekit-client livekit-server-sdk
# 把仓库 web/ 下的 server.js + index.html 传到此处

# ---------- 5. LiveTalking 数字人（GPU）----------
cd /root/aics
[ -d LiveTalking ] || git clone --depth 1 https://github.com/lipku/LiveTalking.git
cd LiveTalking
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
# 模型权重走 Google Drive（gdown），云端几秒完成；国内本机下载不可行
gdown --folder https://drive.google.com/drive/folders/1p2XzPNpF5DQJiuw0wPB6PuWuApKi9t3- -O ./models
nohup python -u app.py --transport webrtc --model wav2lip --avatar_id wav2lip256_avatar1 \
  >> /root/aics/livetalking.log 2>&1 &

# ---------- 6. 启动 agent worker ----------
cd /root/aics/demo
export LIVEKIT_URL=ws://localhost:7880 LIVEKIT_API_KEY=devkey LIVEKIT_API_SECRET=secret
nohup python -u agent.py start >> /root/aics/agent.log 2>&1 &

# ---------- 7. 端口代理规则（仙宫云）----------
# 容器端口 P → https://{实例ID}-{P}.container.x-gpu.com   仅 HTTPS/WSS，不转发 UDP
# 因此服务端 publicLkUrl() 需按 Host 头推导 wss 地址，见 web/server.js
