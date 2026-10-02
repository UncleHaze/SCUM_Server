import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import Client from 'ssh2-sftp-client';

const cfg = JSON.parse(fs.readFileSync(path.join(path.dirname(fileURLToPath(import.meta.url)), '.vscode', 'sftp.json'), 'utf8'));
const sftp = new Client();
await sftp.connect({ host: cfg.host, port: cfg.port, username: cfg.username, password: cfg.password, readyTimeout: 30000 });

async function safeList(dir) {
  try { return (await sftp.list(dir)).map((i) => ({ name: i.name, type: i.type, size: i.size })); }
  catch { return null; }
}

const checks = {
  win64: await safeList('SCUM/Binaries/Win64'),
  mods: await safeList('SCUM/Content/Paks/~mods'),
  paksRoot: (await safeList('SCUM/Content/Paks'))?.filter((i) => /mod|~mods|disabled|phoenix|ue4ss|dwmapi/i.test(i.name)),
};

// suspicious names anywhere under Win64
const suspicious = [];
if (checks.win64) {
  for (const i of checks.win64) {
    if (/dwmapi|ue4ss|phoenix|phex/i.test(i.name)) suspicious.push(`Win64/${i.name}`);
  }
}

await sftp.end();
console.log(JSON.stringify({ checks, suspicious }, null, 2));
