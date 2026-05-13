# China CO2 Allocation Interactive Map

This folder is a static website. Upload the folder contents to any static host.

Recommended public deployment options:

1. GitHub Pages
   - Create a public GitHub repository.
   - Upload every file in this `static_site` folder to the repository root.
   - In GitHub, open Settings -> Pages.
   - Set Source to `Deploy from a branch`, branch `main`, folder `/root`.
   - The map will be available at `https://<user>.github.io/<repo>/`.

2. Cloudflare Pages
   - Create a Pages project.
   - Upload this folder directly or connect a GitHub repository.
   - Build command: leave empty.
   - Output directory: `/` if uploading this folder, or `docs/interactive_map_public/static_site` if deploying the full repository.

3. Netlify or Vercel
   - Drag-and-drop this folder in the web UI.
   - No build command is required.

Do not open `index.html` directly from disk for the normal static-site version,
because browsers may block local JSON/GeoJSON fetches. Use a static host or the
single-file standalone HTML package instead.
