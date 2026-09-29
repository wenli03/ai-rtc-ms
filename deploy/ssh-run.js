// 远端执行器：node deploy/ssh-run.js deploy/remote/setup-all.sh
// 凭据只从环境变量读取，仓库内不含任何明文密钥。
//   XGY_SSH_HOST / XGY_SSH_PORT / XGY_SSH_USER / XGY_SSH_PASSWORD
const fs = require('fs');
const { Client } = require('ssh2');

const host = process.env.XGY_SSH_HOST;
const port = Number(process.env.XGY_SSH_PORT || 22);
const user = process.env.XGY_SSH_USER || 'root';
const pass = process.env.XGY_SSH_PASSWORD;

if (!host || !pass) {
  console.error('缺少环境变量 XGY_SSH_HOST / XGY_SSH_PASSWORD');
  process.exit(2);
}

const script = fs.readFileSync(process.argv[2], 'utf8');
const conn = new Client();
conn.on('ready', () => {
  console.log('[SSH] connected');
  conn.exec('bash -s', (err, stream) => {
    if (err) throw err;
    let out = '';
    stream.on('data', d => { out += d; process.stdout.write(d); });
    stream.stderr.on('data', d => { out += d; process.stderr.write(d); });
    stream.on('close', code => {
      fs.appendFileSync(__dirname + '/ssh-log.txt', `\n$ ${process.argv[2]} -> exit ${code}\n${out}\n`);
      conn.end();
    });
    stream.end(script);
  });
}).connect({ host, port, username: user, password: pass });
