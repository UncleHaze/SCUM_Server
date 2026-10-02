import SftpClient from "ssh2-sftp-client";
import path from "path";
import fs from "fs";
import { defaultRemoteRoot, getEugamehostSftpConfig } from "./eugamehost_sftp.mjs";

const localFile =
  process.argv[2] ||
  path.resolve("ServerSettings.ini");
if (!fs.existsSync(localFile)) {
  console.error("File not found:", localFile);
  process.exit(1);
}

const remoteDir = `${defaultRemoteRoot}/SCUM/Saved/Config/WindowsServer`;
const remoteFile = `${remoteDir}/${path.basename(localFile)}`;

const sftp = new SftpClient();
try {
  await sftp.connect(getEugamehostSftpConfig());
  await sftp.mkdir(remoteDir, true);
  console.log(`Uploading ${localFile} -> ${remoteFile}`);
  await sftp.put(localFile, remoteFile);
  const stat = await sftp.stat(remoteFile);
  console.log(`Done. Remote size: ${stat.size} bytes`);
} finally {
  await sftp.end();
}
