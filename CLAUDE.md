# Cine Finder — handoff notes

Films now showing in the UK ranked by IMDb / Rotten Tomatoes / Metacritic / Letterboxd, with links to showtimes on cinemaguide.co.uk for the owner's six Odeons (Leicester Sq, West End, Haymarket, Tottenham Ct Rd, Swiss Cottage, Greenwich). Owner has Odeon Limitless; non-technical, explain click by click, in Spanish.

- `index.html`: the whole page (vanilla JS, no build). Tabs "🎬 Cine" (reads `films.json`) and "🛋 En casa" (reads `home.json`), profile toggle "Yo / Nosotros".
- `taste.js`: pure taste logic (idf-weighted similarity on genres/keywords/director+top cast, plus TMDB recommendations), Netflix CSV import, sync link. `node taste.test.js` checks it.
- `update.py`: stdlib-only daily job (TMDB now_playing GB → TMDB details → OMDb → Letterboxd via `letterboxd.com/tmdb/<id>/`), then `home()`: owner's services in GB via TMDB discover (JustWatch data, flatrate, ≥150 votes) + all-time most-voted films (for picking favourites) + every film ever in the cinema list, cached in `home.json` (only new films fetch details; OMDb ≤600 calls/day, refreshed every 30 days). `--selftest` checks parsers.
- `.github/workflows/update.yml`: runs it 06:00 UTC daily + manual run, commits `*.json`. Secrets `TMDB_KEY`, `OMDB_KEY` (owner enters them; never type keys for them).
- Design: `docs/superpowers/specs/2026-10-27-cine-finder-design.md`.

Showtimes are links only: Odeon's site is behind a Cloudflare bot challenge (don't bypass) and cinemaguide's API is private (use only with its owner's permission).

Default view "Cines grandes" = top 30 by TMDB popularity (`TOP_POPULAR` in index.html); "Todo UK" shows everything. TMDB's UK wide-release tag (type 3) was tried and dropped: ~70% of films had it.
"En casa" (added 2026-10-29, owner skipped the written spec): first visit asks for 10 favourites (stored as 5★), then mood buttons + 3 suggestions + "Otras 3"; every third suggestion is "✨ Para descubrir" (best rated, ≥1000 votes, taste below the median; `suggestions()` in index.html) and "✨ Sorpréndeme" makes all 3 like that; "Más filtros" has services, min score and genre sliders (−2 hides the genre). Owner's services: Netflix, Prime Video, Disney+, HBO Max (`PROVIDERS` in update.py, `SERVICES` in index.html).
Ratings are in localStorage `ratings` (Yo) and `ratings_us` (Nosotros): {tmdb id: 1-5 stars, 0 seen, -1 "No me llama"}. Old `seen` list migrates to 0. "Nosotros" scores with its own ratings + Yo at half weight. Per browser: "Ajustes → Crear link" puts both lists in a `#sync=` link to open on the other device.
OMDb lags IMDb on new releases (imdbRating "N/A" for weeks); TMDB vote_average (≥20 votes) is shown and stands in for IMDb in the combined score. Do not scrape IMDb (its terms forbid it).
