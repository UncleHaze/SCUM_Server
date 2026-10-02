import SftpClient from "ssh2-sftp-client";
import { defaultRemoteRoot, getEugamehostSftpConfig } from "./eugamehost_sftp.mjs";

const remoteDir = `${defaultRemoteRoot}/SCUM/Content/Paks/Mods`;
const toDelete = process.argv.slice(2);
if (!toDelete.length) {
  console.error("Usage: node delete_mod_paks.mjs <remote-filename.pak> ...");
  process.exit(1);
}

const sftp = new SftpClient();
try {
  await sftp.connect(getEugamehostSftpConfig());
  for (const f of toDelete) {
    const rp = `${remoteDir}/${f}`;
    try {
      await sftp.delete(rp);
      console.log(`Deleted ${rp}`);
    } catch (e) {
      console.log(`Skip ${f}: ${e.message}`);
    }
  }
} finally {
  await sftp.end();
}
