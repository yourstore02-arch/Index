# Halifax Trade Engine v14.0 PWA

Upload **all files and folders in this package** to the root of your GitHub `Index` repository. Keep the paths exactly as shown, especially `.github/workflows/`, `scripts/`, and `icons/`.

GitHub Pages should then serve:
- `index.html` — main Halifax Trade Engine
- `screener.html` — separate 5R Opportunity Screener
- `manifest.webmanifest` + `service-worker.js` — installable PWA support

After upload, run **Actions → Update Halifax 5R Screener → Run workflow** once to generate fresh screener results.

The PWA requires HTTPS; GitHub Pages provides HTTPS. Live market analysis still requires an internet connection.
