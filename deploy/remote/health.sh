#!/bin/bash
# 服务健康检查：端口、进程、GPU 显存、磁盘
export PATH=/root/miniconda3/bin:$PATH
echo "=== 监听端口 (期望 6 个: 7880/7881/8081/8010/3210/11434) ==="
ss -tlnp | grep -E "7880|7881|3210|8010|11434|8081" | wc -l
echo "=== 进程 ==="
pgrep -af "livekit-server|agent.py|node server.js|app.py|ollama" | cut -c1-90
echo "=== GPU ==="
nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv,noheader
nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader
echo "=== LiveTalking 会话 ==="
curl -s http://127.0.0.1:8010/api/admin/sessions | head -c 300
echo
