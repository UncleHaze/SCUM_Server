import SftpClient from "ssh2-sftp-client";
import path from "path";
import fs from "fs";
import { defaultRemoteRoot, getEugamehostSftpConfig } from "./eugamehost_sftp.mjs";

const localFile = process.argv[2];
if (!localFile || !fs.existsSync(localFile)) {
  console.error("Usage: node upload_mod_pak.mjs <path-to.pak>");
  process.exit(1);
}

const remoteDir = `${defaultRemoteRoot}/SCUM/Content/Paks/Mods`;
const remoteFile = `${remoteDir}/${path.basename(localFile)}`;

const sftp = new SftpClient();
try {
  await sftp.connect(getEugamehostSftpConfig());
  await sftp.mkdir(remoteDir, true);
  const size = fs.statSync(localFile).size;
  console.log(`Uploading ${localFile} (${(size / 1024 / 1024).toFixed(2)} MB) -> ${remoteFile}`);
  await sftp.put(localFile, remoteFile);
  const stat = await sftp.stat(remoteFile);
  console.log(`Done. Remote size: ${(stat.size / 1024 / 1024).toFixed(2)} MB`);
} finally {
  await sftp.end();
}
