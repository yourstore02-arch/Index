# ChatGPT Sites deployment note

Halifax v14.1 can be used as a static website interface, but the live 5R scan should remain on GitHub Actions or another backend.

OpenAI currently documents that ChatGPT Sites can create and host interactive websites/lightweight apps, but **Sites cannot connect directly to live data sources today**. Therefore, a Sites-only deployment cannot directly run the NASDAQ/Yahoo-backed market scan in this package.

Recommended setup for Halifax:
1. Keep the full package in GitHub so `.github/workflows/update-screener.yml` can run the data scan.
2. Use GitHub Pages for the live PWA if you want the newest scan results to appear automatically.
3. If you also publish a ChatGPT Site, treat it as a static/demo interface unless you manually refresh its data.

For ChatGPT Plus/Pro accounts, Sites is in public beta where available. Availability can still depend on rollout, region, and account settings.
