// Taste scoring, shared by index.html and taste.test.js (node taste.test.js).
// A rating is 1-5 stars, 0 = seen without stars, -1 = "No me llama". Favourites picked at the start are 5.
const WEIGHT = {5: 2, 4: 1, 3: 0, 2: -1, 1: -2, 0: 0, '-1': -0.5};
const REC_BONUS = 0.3; // extra similarity when TMDB lists one film among the other's recommendations

const feats = f => new Set([...(f.genres || []).map(g => 'g' + g), ...(f.kw || []).map(k => 'k' + k), ...(f.people || []).map(p => 'p' + p)]);

// Feature vectors weighted by rarity (idf), so a shared director counts more than a shared "Drama".
function makeIndex(films) {
  const df = new Map(), byId = new Map(), fs = films.map(f => [f, feats(f)]);
  for (const [f, s] of fs) { byId.set(f.tmdb_id, f); for (const x of s) df.set(x, (df.get(x) || 0) + 1); }
  const vec = new Map();
  for (const [f, s] of fs) {
    const v = new Map(); let norm = 0;
    for (const x of s) { const w = Math.log(films.length / df.get(x)); if (w > 0) { v.set(x, w); norm += w * w; } }
    vec.set(f.tmdb_id, {v, norm: Math.sqrt(norm) || 1, recs: new Set(f.recs || [])});
  }
  return {byId, vec};
}

function sim(ix, a, b) {
  const A = ix.vec.get(a), B = ix.vec.get(b);
  if (!A || !B) return 0;
  const [s, l] = A.v.size < B.v.size ? [A, B] : [B, A];
  let dot = 0;
  for (const [x, w] of s.v) if (l.v.has(x)) dot += w * l.v.get(x);
  return dot / (A.norm * B.norm) + (A.recs.has(b) || B.recs.has(a) ? REC_BONUS : 0);
}

// sources: [[ratings, factor], ...] -> Map(film id -> weight). "Nosotros" mixes in "Yo" at half weight.
function profile(...sources) {
  const w = new Map();
  for (const [r, k] of sources) for (const [id, s] of Object.entries(r)) {
    const x = (WEIGHT[s] ?? 0) * k;
    if (x) w.set(+id, (w.get(+id) || 0) + x);
  }
  return w;
}

// How much this profile should like film `id`, and which rated film pushed it most (for "Porque te gustó …").
function taste(ix, prof, id) {
  let score = 0, why = null, best = 0;
  for (const [l, w] of prof) {
    if (l === id) continue;
    const s = w * sim(ix, id, l);
    score += s;
    if (s > best) { best = s; why = l; }
  }
  return {score, why};
}

const norm = s => String(s).normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();

// Netflix "Viewing activity" CSV (Title,Date) -> ids of films whose title matches a whole row exactly.
// ponytail: same-title remakes (Dune 1984/2021) both get marked seen; stars can fix it by hand.
function netflixSeen(csv, films) {
  const titles = new Set();
  for (const line of csv.split(/\r?\n/).slice(1)) {
    const m = line.match(/^"((?:[^"]|"")*)"/) || line.match(/^([^,]*)/);
    if (m && m[1].trim()) titles.add(norm(m[1].replace(/""/g, '"')));
  }
  return films.filter(f => titles.has(norm(f.title)) || (f.original_title && titles.has(norm(f.original_title)))).map(f => f.tmdb_id);
}

// "Pasar a mi Mac": both rating lists travel in the link's #sync= part. Ids and numbers only, so plain base64 is safe.
const encodeSync = data => btoa(JSON.stringify(data));
const decodeSync = s => JSON.parse(atob(s));

if (typeof module !== 'undefined') module.exports = {makeIndex, sim, profile, taste, netflixSeen, encodeSync, decodeSync, norm};
