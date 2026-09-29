# deploy/ — 云主机远程运维

本目录**不含任何凭据**。`ssh-run.js` 从环境变量读取连接信息。

## 准备

```bash
cd deploy
npm install ssh2

export XGY_SSH_HOST=<你的云主机 SSH 地址>
export XGY_SSH_PORT=<端口>
export XGY_SSH_USER=root
export XGY_SSH_PASSWORD='<云主机密码>'
```

## 用法

```bash
node ssh-run.js remote/setup-all.sh    # 一键部署全栈
node ssh-run.js remote/health.sh       # 服务健康检查
node ssh-run.js remote/kick-all.sh     # 清空房间成员（清理僵尸 agent）
```

`ssh-run.js` 会把每次执行的输出追加到本地 `ssh-log.txt`（已在 `.gitignore` 中，不会进仓库）。

## 端口代理说明（仙宫云）

容器内任意端口 `P` 对应公网 `https://{实例ID}-{P}.container.x-gpu.com`，**只提供 HTTPS / WSS，不转发 UDP**。
这直接决定了 WebRTC 媒体面无法从浏览器直连——详见 `docs/使用手册-云端实测.md` §2、§5.3。
