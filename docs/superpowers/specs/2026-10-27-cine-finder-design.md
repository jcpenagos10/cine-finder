# Cine Finder — design

## Goal
One page, opened on iPhone or Mac, that lists the films now showing in the UK ranked by IMDb, Rotten Tomatoes, Metacritic and Letterboxd, with one-tap links to showtimes at the owner's six Odeons. The owner has Odeon Limitless, so the hard part is choosing *what* to see, not the price.

Success: in under a minute the owner can see which current films are best reviewed, spot lesser-known good ones, and jump to times at a chosen cinema.

## Out of scope (for now)
- Showtimes inside the app. Odeon's site sits behind a Cloudflare bot challenge, and cinemaguide.co.uk's data API is private. Revisit only if cinemaguide's owner grants permission.
- Non-Odeon cinemas, watchlists, notifications, a Telegram digest.

## Architecture
Two pieces in one public repo `jcpenagos10/cine-finder`, served by GitHub Pages from `main`, root:

1. **`update.py`** (Python stdlib only), run daily at 06:00 UK by a GitHub Actions cron (`.github/workflows/update.yml`), also runnable by hand (`workflow_dispatch`). It writes `films.json` and commits it if changed.
2. **`index.html`** (HTML + CSS + vanilla JS, no build, no dependencies, same style as Spot Finder). It fetches `films.json` and renders it. No keys in the browser.

## Data flow (`update.py`)
1. **TMDB** `GET /3/movie/now_playing?region=GB`, all pages → TMDB id, title, release date, poster path.
2. For each film: **TMDB** `GET /3/movie/{id}?append_to_response=external_ids` → runtime, genres, IMDb id.
3. **OMDb** `GET ?i={imdb_id}` → `imdbRating`, `imdbVotes`, `Metascore`, and the Rotten Tomatoes entry in `Ratings`. Values of `"N/A"` become `null`.
4. **Letterboxd** `GET https://letterboxd.com/tmdb/{id}/` (redirects to the film page; verified working) → parse `<meta name="twitter:data2" content="4.10 out of 5">` → 4.10, plus the film URL. One request per second, honest User-Agent naming the project. Film pages are allowed by Letterboxd's robots.txt for general bots.
5. Write `films.json`: `{ "updated": ISO time, "films": [ {tmdb_id, title, year, release_date, runtime, genres, poster, imdb_id, imdb, imdb_votes, rt, metacritic, letterboxd, letterboxd_url} ] }`.

Keys: `TMDB_KEY` (v3 API key) and `OMDB_KEY` live only as GitHub Actions secrets, entered by the owner. Free tiers suffice (~100 films/day; OMDb allows 1,000/day).

## Errors
- One source failing for one film → that field is `null`; the film stays.
- TMDB list fails → script exits non-zero and does **not** overwrite `films.json`, so the page keeps yesterday's data. GitHub emails the owner on a failed run.
- Page shows "updated <date>" so stale data is visible.

## Page
- **Header:** "updated" time and six fixed buttons opening cinemaguide pages:
  `odeon-london-leicester-square`, `odeon-london-west-end`, `odeon-london-haymarket`, `odeon-london-tottenham-court-road`, `odeon-swiss-cottage`, `odeon-greenwich` → `https://cinemaguide.co.uk/cinemas/<slug>`.
- **Card per film:** poster, title, year, runtime, genres; four rating chips (IMDb x/10, RT %, MC, Letterboxd x/5), each linking to its source where a URL is known; combined score.
- **Combined score (0–100):** mean of the available ratings rescaled to 0–100 (IMDb×10, RT, Metacritic, Letterboxd×20). Fewer than two ratings → shown but sorted last.
- **Sort:** combined (default), IMDb, RT, Letterboxd, newest.
- **Quick filters:** *New* = released in the last 21 days; *Hidden gems* = combined ≥ 75 and IMDb votes < 20,000.
- Mobile-first, works at iPhone width, dark/light follows the system.

## Known limits
- "Now playing in the UK" (TMDB) is not exactly "showing at these Odeons"; cinemaguide links confirm.
- Ratings refresh daily.
- If Letterboxd changes its page markup, that chip goes empty; the rest keeps working.

## Testing
- `update.py` has a `--selftest` flag that runs asserts on the pure parsing functions (OMDb `N/A` handling, RT percent, Letterboxd meta tag) against inline sample strings. Run in CI before the real update.
- Page checked locally with a sample `films.json` in the browser preview, at phone and desktop widths.
