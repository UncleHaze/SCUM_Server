# SCUM Wiki — PhazeOut image uploads

Use these **re-encoded** files (not raw ImgBB downloads):

| File | Use |
|------|-----|
| `PhazeOut.png` | Infobox `server_image` + gallery (512×512, ~300 KB) |
| `PhazeOut Banner.jpg` | Banner on page (1200×392 JPEG) |

## Upload steps

1. Log in on [scum.wiki.gg](https://scum.wiki.gg).
2. Open [Special:Upload](https://scum.wiki.gg/wiki/Special:Upload).
3. **Destination filename** must match exactly (including spaces/capital P):
   - `PhazeOut.png`
   - `PhazeOut Banner.jpg`
4. In **Summary**, paste: `[[Category:Private Servers]]`
5. Upload **one file at a time**.

## If upload still fails “file verification”

1. **Page title must match** — Your wiki page should be named **`PhazeOut`**. The infobox image must be **`PhazeOut.png`**. If your page has a different title (e.g. `[PhazeOut] 4x`), rename the page to `PhazeOut` *or* rename files to include that exact page name (see [Editing Guide](https://scum.wiki.gg/wiki/Private_Server_Page_Editing_Guide)).
2. **Do not upload** `.jpg` from ImgBB for the logo — use **`PhazeOut.png`** from this folder only.
3. **Account** — Some wikis require a verified / older account before uploads work.
4. **Replace bad upload** — If a broken file already exists, upload again with the same destination name and choose **Replace** if offered.
5. **Browser** — Disable ad blockers on scum.wiki.gg; complete any Cloudflare check, then retry.

## Regenerate files

```bash
python wiki/prepare_wiki_uploads.py
```

Requires `logo-source.png` and `banner-source.jpg` in this folder (download from ImgBB if missing).
