// node taste.test.js
const assert = require('assert');
const {makeIndex, sim, profile, taste, netflixSeen, encodeSync, decodeSync} = require('./taste.js');

const films = [
  {tmdb_id: 1, title: 'Arrival', genres: ['Science Fiction', 'Drama'], kw: [10, 11], people: [100], recs: [2]},
  {tmdb_id: 2, title: 'Dune', genres: ['Science Fiction', 'Adventure'], kw: [10], people: [100]},
  {tmdb_id: 3, title: 'Paddington 2', genres: ['Comedy', 'Family'], kw: [20], people: [200]},
  {tmdb_id: 4, title: 'Hereditary', genres: ['Horror'], kw: [30], people: [300]},
  {tmdb_id: 5, title: 'Amélie', original_title: "Le Fabuleux Destin d'Amélie Poulain", genres: ['Comedy', 'Romance'], kw: [21], people: [400]},
];
const ix = makeIndex(films);

assert(sim(ix, 1, 2) > sim(ix, 1, 3), 'same director + keyword beats nothing shared');
assert.strictEqual(sim(ix, 3, 4), 0);
assert(sim(ix, 2, 1) > 0.3, 'recommendation link adds a bonus either way round');

const me = {1: 5, 4: 1, 3: 0};
const p = profile([me, 1]);
assert.deepStrictEqual([...p], [[1, 2], [4, -2]], 'seen-without-stars teaches nothing');
const dune = taste(ix, p, 2), amelie = taste(ix, p, 5);
assert(dune.score > amelie.score);
assert.strictEqual(dune.why, 1, 'Dune is suggested because of Arrival');
assert(taste(ix, profile([{4: 5}, 1]), 4).score === 0, "a film doesn't recommend itself");
assert.deepStrictEqual([...profile([{2: -1}, 1], [{2: 5}, 0.5])], [[2, 0.5]], 'Nosotros + half of Yo');

const csv = 'Title,Date\n"Arrival","1/2/26"\n"Stranger Things: Stranger Things 2: Chapter One","1/1/26"\nAmelie,3/3/25\n"Le Fabuleux Destin d\'Amélie Poulain","3/3/25"\n';
assert.deepStrictEqual(netflixSeen(csv, films), [1, 5]);

const data = {r: {1: 5, 4: -1}, u: {3: 4}};
assert.deepStrictEqual(decodeSync(encodeSync(data)), data);

console.log('taste ok');
