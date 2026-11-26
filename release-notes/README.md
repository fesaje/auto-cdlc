Release notes, one file per version: `vX.Y.Z.md`, with `X.Y.Z` = `VERSION` in `auto_cdlc.py`.

Adding the file to `main` publishes the release (see `.github/workflows/release.yml`). Format:
"**English** | [Español](#español)", "### Changes", "### Install / update", then "## Español"
(two hashes: the updater looks for it), "### Cambios", "### Instalar / actualizar".

Publish outside LaLiga match times: Cloudflare IPs get blocked in Spain and the results server stops answering.
