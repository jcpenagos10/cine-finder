# Cine Finder — handoff notes

Films now showing in the UK ranked by IMDb / Rotten Tomatoes / Metacritic / Letterboxd, with links to showtimes on cinemaguide.co.uk for the owner's six Odeons (Leicester Sq, West End, Haymarket, Tottenham Ct Rd, Swiss Cottage, Greenwich). Owner has Odeon Limitless; non-technical, explain click by click, in Spanish.

- `index.html`: the whole page (vanilla JS, no build). Reads `films.json`.
- `update.py`: stdlib-only daily job (TMDB now_playing GB → TMDB details → OMDb → Letterboxd via `letterboxd.com/tmdb/<id>/`). `--selftest` checks parsers.
- `.github/workflows/update.yml`: runs it 06:00 UTC daily + manual run, commits `films.json`. Secrets `TMDB_KEY`, `OMDB_KEY` (owner enters them; never type keys for them).
- Design: `docs/superpowers/specs/2026-10-27-cine-finder-design.md`.

Showtimes are links only: Odeon's site is behind a Cloudflare bot challenge (don't bypass) and cinemaguide's API is private (use only with its owner's permission).

Default view "Cines grandes" = TMDB wide UK release (release type 3 in GB) OR top 60 by TMDB popularity (`TOP_POPULAR` in index.html); "Todo UK" shows everything.
