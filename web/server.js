const http = require('http');
const fs = require('fs');
const path = require('path');
const { AccessToken, RoomServiceClient, AgentDispatchClient } = require('livekit-server-sdk');

const API_KEY = 'devkey';
const API_SECRET = 'secret';
const LK_URL = 'ws://localhost:7880';
const ROOM = 'cs-demo';

// 浏览器端 signaling 地址：本地开发返回 ws://localhost:7880；
// 仙宫云按 {id}-{端口}.container.x-gpu.com 代理端口，https 页面必须用 wss 子域
function publicLkUrl(req) {
  const host = req.headers.host || '';
  if (host.startsWith('localhost') || host.startsWith('127.')) return 'ws://localhost:7880';
  return 'wss://' + host.replace(/-\d+\./, '-7880.');
}

const rooms = new RoomServiceClient('http://localhost:7880', API_KEY, API_SECRET);
const dispatch = new AgentDispatchClient('http://localhost:7880', API_KEY, API_SECRET);

async function tokenFor(name) {
  const at = new AccessToken(API_KEY, API_SECRET, { identity: name, ttl: '2h' });
  at.addGrant({ roomJoin: true, room: ROOM, canPublish: true, canSubscribe: true });
  return await at.toJwt();
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, 'http://localhost');
  res.setHeader('Access-Control-Allow-Origin', '*');
  if (url.pathname === '/start') {
    try {
      await rooms.createRoom({ name: ROOM, emptyTimeout: 300, departureTimeout: 30 });
    } catch (e) {
      if (!String(e.message).match(/already|exists/i)) throw e;
    }
    try {
      await dispatch.createDispatch(ROOM, 'default');
    } catch (e) {
      console.log('dispatch warn:', e.message);
    }
    const token = await tokenFor('customer');
    res.setHeader('Content-Type', 'application/json');
    res.end(JSON.stringify({ url: publicLkUrl(req), token, room: ROOM }));
    return;
  }
  if (url.pathname === '/token') {
    const name = url.searchParams.get('name') || 'customer';
    const token = await tokenFor(name);
    res.setHeader('Content-Type', 'application/json');
    res.end(JSON.stringify({ url: publicLkUrl(req), token, room: ROOM }));
    return;
  }
  let file = url.pathname === '/' ? '/index.html' : url.pathname;
  if (file.startsWith('/node_modules/')) {
    fs.readFile(path.join(__dirname, file), (err, buf) => {
      res.setHeader('Content-Type', file.endsWith('.js') ? 'text/javascript' : 'text/plain');
      res.end(err ? '404' : buf);
    });
    return;
  }
  fs.readFile(path.join(__dirname, file), (err, buf) => {
    if (err) { res.writeHead(404); res.end('not found'); return; }
    res.setHeader('Content-Type', file.endsWith('.html') ? 'text/html' : 'text/javascript');
    res.end(buf);
  });
});

server.listen(3210, () => console.log('token+web server on http://localhost:3210'));
