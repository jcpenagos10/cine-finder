"""Daily job: UK now-playing films (TMDB) + IMDb/RT/Metacritic (OMDb) + Letterboxd -> films.json,
plus the owner's UK streaming catalogue (TMDB discover, JustWatch data) + OMDb -> home.json.

Needs env TMDB_KEY and OMDB_KEY. `python3 update.py --selftest` checks the parsers only.
"""
import json, os, re, sys, time, urllib.parse, urllib.request
from datetime import date, datetime, timedelta, timezone

UA = "cine-finder/1.0 (personal film list; github.com/jcpenagos10/cine-finder)"


def get(url, raw=False):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        body = r.read().decode("utf-8", "replace")
        return (body, r.geturl()) if raw else json.loads(body)


def num(s):
    """OMDb strings like '7.8', '123,456', '81', 'N/A' -> float or None."""
    try:
        return float(str(s).replace(",", "").rstrip("%"))
    except ValueError:
        return None


def parse_omdb(d):
    rt = next((r["Value"] for r in d.get("Ratings", []) if r["Source"] == "Rotten Tomatoes"), None)
    votes = num(d.get("imdbVotes"))
    return {
        "imdb": num(d.get("imdbRating")),
        "imdb_votes": int(votes) if votes is not None else None,
        "rt": num(rt) if rt else None,
        "metacritic": num(d.get("Metascore")),
    }


def parse_letterboxd(html):
    m = re.search(r'name="twitter:data2" content="([\d.]+) out of 5"', html)
    return float(m.group(1)) if m else None


def parse_details(det):
    """TMDB /movie/{id} with external_ids,keywords,credits,recommendations -> fields the taste scoring uses."""
    credits = det.get("credits", {})
    title, original = det.get("title"), det.get("original_title")
    return {
        "runtime": det.get("runtime") or None,
        "genres": [g["name"] for g in det.get("genres", [])],
        "imdb_id": det.get("external_ids", {}).get("imdb_id"),
        "original_title": original if original and original != title else None,
        "kw": [k["id"] for k in det.get("keywords", {}).get("keywords", [])][:20],
        "people": [p["id"] for p in credits.get("crew", []) if p.get("job") == "Director"]
                  + [p["id"] for p in credits.get("cast", [])[:4]],
        "recs": [r["id"] for r in det.get("recommendations", {}).get("results", [])][:12],
    }


DETAILS = "external_ids,keywords,credits,recommendations"


def tmdb(path, key, **params):
    q = urllib.parse.urlencode({"api_key": key, **params})
    return get(f"https://api.themoviedb.org/3{path}?{q}")


def main():
    tk, ok = os.environ["TMDB_KEY"], os.environ["OMDB_KEY"]
    listing, page, pages = [], 1, 1
    while page <= min(pages, 10):  # ponytail: 10 pages (~200 films) cap, UK now_playing is far smaller
        d = tmdb("/movie/now_playing", tk, region="GB", page=page)
        listing += d["results"]
        pages, page = d["total_pages"], page + 1

    films, seen = [], set()
    for f in listing:
        if f["id"] in seen:
            continue
        seen.add(f["id"])
        film = {
            "tmdb_id": f["id"], "title": f["title"], "release_date": f.get("release_date"),
            "year": (f.get("release_date") or "")[:4] or None,
            "poster": f"https://image.tmdb.org/t/p/w342{f['poster_path']}" if f.get("poster_path") else None,
            "runtime": None, "genres": [], "imdb_id": None,
            "popularity": f.get("popularity"),
            # ponytail: under 20 votes TMDB's average is noise, so it's dropped
            "tmdb": f.get("vote_average") if f.get("vote_count", 0) >= 20 else None,
            "imdb": None, "imdb_votes": None, "rt": None, "metacritic": None,
            "letterboxd": None, "letterboxd_url": None,
        }
        try:
            film.update(parse_details(tmdb(f"/movie/{f['id']}", tk, append_to_response=DETAILS)))
        except Exception as e:
            print("tmdb detail", f["title"], e, file=sys.stderr)
        if film["imdb_id"]:
            try:
                film.update(parse_omdb(get(f"https://www.omdbapi.com/?i={film['imdb_id']}&apikey={ok}")))
            except Exception as e:
                print("omdb", f["title"], e, file=sys.stderr)
        try:
            html, url = get(f"https://letterboxd.com/tmdb/{f['id']}/", raw=True)
            film["letterboxd"], film["letterboxd_url"] = parse_letterboxd(html), url
        except Exception as e:
            print("letterboxd", f["title"], e, file=sys.stderr)
        time.sleep(1)  # be polite to Letterboxd
        films.append(film)

    out = {"updated": datetime.now(timezone.utc).isoformat(timespec="minutes"), "films": films}
    with open("films.json", "w") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print(f"{len(films)} films written")
    try:
        home(tk, ok, films)
    except Exception as e:  # cinema list is already saved; yesterday's home.json stays
        print("home catalogue failed:", repr(e), file=sys.stderr)


# Owner's subscriptions -> TMDB's GB provider names (exact; the log lists close matches if one goes missing).
PROVIDERS = {
    "Netflix": {"Netflix"},
    "Prime Video": {"Amazon Prime Video"},
    "Disney+": {"Disney Plus"},
    "HBO Max": {"HBO Max", "Max"},
}
HOME_MIN_VOTES = 150  # ponytail: drops obscure titles; lower it if the catalogue feels thin
HOME_PAGES = 60       # per service, 20 films a page
SEED_PAGES = 15       # all-time most-voted films, so favourites can be picked even if not streaming
OMDB_BUDGET = 600     # of OMDb's 1,000 free calls a day; the cinema list uses ~100
OMDB_REFRESH_DAYS = 30


def discover(tk, pages, **params):
    out, page, total = [], 1, 1
    while page <= min(total, pages):
        d = tmdb("/discover/movie", tk, page=page, **params)
        out += d["results"]
        total, page = d["total_pages"], page + 1
    return out


def home(tk, ok, cinema):
    """Streaming catalogue + seed films + every film ever in the cinema list (so old ratings keep training)."""
    try:
        with open("home.json") as fh:
            cache = {f["tmdb_id"]: f for f in json.load(fh)["films"]}
    except (OSError, ValueError, KeyError):
        cache = {}

    names = {p["provider_name"]: p["provider_id"] for p in tmdb("/watch/providers/movie", tk, watch_region="GB")["results"]}
    listed, providers = {}, {}
    for label, wanted in PROVIDERS.items():
        ids = [str(names[n]) for n in wanted if n in names]
        if not ids:
            word = label.split()[0].lower()
            print("provider missing:", label, "close:", [n for n in names if word in n.lower()], file=sys.stderr)
            continue
        for r in discover(tk, HOME_PAGES, watch_region="GB", with_watch_providers="|".join(ids),
                          with_watch_monetization_types="flatrate", sort_by="popularity.desc",
                          **{"vote_count.gte": HOME_MIN_VOTES}):
            listed[r["id"]] = r
            providers.setdefault(r["id"], set()).add(label)
    for r in discover(tk, SEED_PAGES, sort_by="vote_count.desc"):
        listed.setdefault(r["id"], r)

    today = date.today().isoformat()
    out = {}
    for fid, r in listed.items():
        f = cache.get(fid)
        if not f or "kw" not in f:
            try:
                det = tmdb(f"/movie/{fid}", tk, append_to_response=DETAILS)
            except Exception as e:
                print("tmdb detail", r.get("title"), e, file=sys.stderr)
                continue
            f = {"tmdb_id": fid, "title": r["title"], "year": (r.get("release_date") or "")[:4] or None,
                 "poster": f"https://image.tmdb.org/t/p/w342{r['poster_path']}" if r.get("poster_path") else None,
                 "imdb": None, "imdb_votes": None, "rt": None, "metacritic": None, "omdb_at": None,
                 **parse_details(det)}
        f.update(popularity=r.get("popularity"), votes=r.get("vote_count"),
                 tmdb=r.get("vote_average") if r.get("vote_count", 0) >= 20 else None,
                 providers=sorted(providers.get(fid, [])))
        out[fid] = f
    for c in cinema:
        if c["tmdb_id"] in out:
            out[c["tmdb_id"]]["cine"] = True
        else:
            out[c["tmdb_id"]] = {**c, "providers": [], "cine": True, "omdb_at": today}
    for fid, f in cache.items():
        if f.get("cine") and fid not in out:
            out[fid] = {**f, "providers": []}

    stale = (date.today() - timedelta(days=OMDB_REFRESH_DAYS)).isoformat()
    todo = sorted((f for f in out.values() if f.get("imdb_id") and (f.get("omdb_at") or "") < stale),
                  key=lambda f: (f.get("omdb_at") or "", -(f.get("popularity") or 0)))
    for f in todo[:OMDB_BUDGET]:
        try:
            d = get(f"https://www.omdbapi.com/?i={f['imdb_id']}&apikey={ok}")
        except Exception as e:
            print("omdb", f["title"], e, file=sys.stderr)
            continue
        if d.get("Response") == "False" and "limit" in d.get("Error", "").lower():
            print("omdb daily limit reached", file=sys.stderr)
            break
        f.update(parse_omdb(d))
        f["omdb_at"] = today

    films = sorted(out.values(), key=lambda f: f["tmdb_id"])
    with open("home.json", "w") as fh:  # one film per line keeps the daily git diff small
        fh.write('{"updated":%s,"films":[\n' % json.dumps(datetime.now(timezone.utc).isoformat(timespec="minutes")))
        fh.write(",\n".join(json.dumps(f, ensure_ascii=False, separators=(",", ":")) for f in films))
        fh.write("\n]}\n")
    print(f"{len(films)} home films written, {sum(bool(f['providers']) for f in films)} streaming, "
          f"{len(todo)} needed OMDb", {k: sum(k in f["providers"] for f in films) for k in PROVIDERS})


def selftest():
    o = parse_omdb({"imdbRating": "7.8", "imdbVotes": "123,456", "Metascore": "N/A",
                    "Ratings": [{"Source": "Rotten Tomatoes", "Value": "95%"}]})
    assert o == {"imdb": 7.8, "imdb_votes": 123456, "rt": 95.0, "metacritic": None}, o
    assert parse_omdb({"imdbRating": "N/A", "imdbVotes": "N/A"})["imdb_votes"] is None
    assert parse_letterboxd('<meta name="twitter:data2" content="4.10 out of 5" />') == 4.1
    assert parse_letterboxd("<html>no rating yet</html>") is None
    d = parse_details({"title": "Arrival", "original_title": "Arrival", "runtime": 116, "genres": [{"name": "Drama"}],
                       "external_ids": {"imdb_id": "tt2543164"}, "keywords": {"keywords": [{"id": 1}, {"id": 2}]},
                       "credits": {"crew": [{"id": 9, "job": "Director"}, {"id": 8, "job": "Writer"}],
                                   "cast": [{"id": c} for c in range(10, 20)]},
                       "recommendations": {"results": [{"id": 5}]}})
    assert d == {"runtime": 116, "genres": ["Drama"], "imdb_id": "tt2543164", "original_title": None,
                 "kw": [1, 2], "people": [9, 10, 11, 12, 13], "recs": [5]}, d
    assert parse_details({"title": "Amélie", "original_title": "Le Fabuleux Destin d'Amélie Poulain"})["original_title"]
    print("selftest ok")


if __name__ == "__main__":
    selftest() if "--selftest" in sys.argv else main()
