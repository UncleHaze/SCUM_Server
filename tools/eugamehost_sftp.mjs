import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

/** EUgameHost credentials from env or `.vscode/sftp.json` (gitignored). */
export function getEugamehostSftpConfig() {
  if (process.env.SFTP_HOST && process.env.SFTP_PASSWORD) {
    return {
      host: process.env.SFTP_HOST,
      port: Number(process.env.SFTP_PORT || 8822),
      username: process.env.SFTP_USERNAME,
      password: process.env.SFTP_PASSWORD,
    };
  }
  const cfgPath = path.join(repoRoot, ".vscode", "sftp.json");
  if (!fs.existsSync(cfgPath)) {
    throw new Error(
      "Missing SFTP config: set SFTP_HOST/SFTP_USERNAME/SFTP_PASSWORD or add .vscode/sftp.json"
    );
  }
  const cfg = JSON.parse(fs.readFileSync(cfgPath, "utf8"));
  return {
    host: cfg.host,
    port: cfg.port ?? 8822,
    username: cfg.username,
    password: cfg.password,
  };
}

export const defaultRemoteRoot =
  process.env.SFTP_REMOTE_ROOT ||
  "/8979 - 82_153_118_107_8107";
