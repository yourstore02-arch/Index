# Halifax Trade Engine v14.2 PWA

This package fixes the confusing **OPEN vs RUN** behavior of the 5R screener.

## What the buttons do
- **OPEN 5R SCREENER** opens the separate results page. It does not pretend to start a scan.
- **START NEW SCAN** on `screener.html` opens the exact GitHub Actions workflow for the repository.
- GitHub requires the repository owner to tap **Run workflow** there. A public webpage cannot safely bypass GitHub authentication without exposing a secret token.
- After you start the workflow, the screener page automatically checks for fresh `screener-data.json` results every 20 seconds for up to 12 minutes.

## Upload to GitHub Pages
Upload **all files and folders in this package** to the root of your GitHub `Index` repository. Keep the paths exactly as shown, especially `.github/workflows/`, `scripts/`, and `icons/`.

GitHub Pages should serve:
- `index.html` — main Halifax Trade Engine
- `screener.html` — separate 5R Opportunity Screener
- `manifest.webmanifest` + `service-worker.js` — installable PWA support

After upload, open **Actions → Update Halifax 5R Screener → Run workflow** once. The workflow also runs automatically every 4 hours on weekdays.

## Scan design
The updater checks the NASDAQ, NYSE, and AMEX exchange snapshots, excludes blocked security types and OTC names, filters for price/liquidity, then performs deeper 5-year historical testing on the highest-priority finalist pool. The UI now labels that pool as the **Deep Historical Pool** instead of implying every exchange symbol receives the expensive 5-year backtest.

## ChatGPT Sites
See `CHATGPT_SITES_DEPLOY.md`. ChatGPT Sites can host a site, but OpenAI currently states that Sites cannot connect directly to live data sources. For a continuously updating stock screener, keep the live scan on GitHub Actions (or another backend).
## v14.2 button visibility fix
- The main Halifax page now has its own green **START NEW SCAN** button.
- The screener page also has a large green **START NEW SCAN** button near the top.
- The PWA cache version was bumped so phones are less likely to keep the older screener page.
- The screener displays **Halifax screener build v14.2** so you can verify the new file is live.

