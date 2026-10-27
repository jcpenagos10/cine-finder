"""Daily job: UK now-playing films (TMDB) + IMDb/RT/Metacritic (OMDb) + Letterboxd -> films.json.

Needs env TMDB_KEY and OMDB_KEY. `python3 update.py --selftest` checks the parsers only.
"""
import json, os, re, sys, time, urllib.parse, urllib.request
from datetime import datetime, timezone

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
            "imdb": None, "imdb_votes": None, "rt": None, "metacritic": None,
            "letterboxd": None, "letterboxd_url": None,
        }
        try:
            det = tmdb(f"/movie/{f['id']}", tk, append_to_response="external_ids")
            film["runtime"] = det.get("runtime") or None
            film["genres"] = [g["name"] for g in det.get("genres", [])]
            film["imdb_id"] = det["external_ids"].get("imdb_id")
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


def selftest():
    o = parse_omdb({"imdbRating": "7.8", "imdbVotes": "123,456", "Metascore": "N/A",
                    "Ratings": [{"Source": "Rotten Tomatoes", "Value": "95%"}]})
    assert o == {"imdb": 7.8, "imdb_votes": 123456, "rt": 95.0, "metacritic": None}, o
    assert parse_omdb({"imdbRating": "N/A", "imdbVotes": "N/A"})["imdb_votes"] is None
    assert parse_letterboxd('<meta name="twitter:data2" content="4.10 out of 5" />') == 4.1
    assert parse_letterboxd("<html>no rating yet</html>") is None
    print("selftest ok")


if __name__ == "__main__":
    selftest() if "--selftest" in sys.argv else main()
