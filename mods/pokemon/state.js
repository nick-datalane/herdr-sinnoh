// Shared logic: asset paths, night detection, the random Pokémon per agent and the random Sinnoh location per space
import { spaces, shared, setShared } from "herdr";
import M from "./manifest.js";

const ASSETS = "mods/pokemon/assets";

// a dark theme background → night assets
export function isNight(t) {
  const hex = (t.background ?? "#ffffff").slice(1);
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(hex.slice(i, i + 2), 16));
  return 0.299 * r + 0.587 * g + 0.114 * b < 110;
}

// the colour of the pixel hard shadows
export const shadowColor = (t) => (isNight(t) ? "#00000099" : "#2b262033");

// status → face frame
export const FACE = { idle: "idle", working: "smash", done: "roar", blocked: "wave" };

// find a node by id in the layout tree
export function find(node, id) {
  if (node?.id === id) return node;
  for (const child of node?.children ?? []) {
    const found = find(child, id);
    if (found) return found;
  }
  return null;
}

// the scenes, Pokémon and effects are always the daylight art, even when the theme is dark
export const asset = (_t, name) => `${ASSETS}/day/${name}`;

export const STATUS_TEXT = { idle: "Resting", working: "Working", done: "Done", blocked: "Needs you" };

// ---------- Pokémon per agent ----------
const KEY = "pokemon.monsters";
const BY_ID = new Map(M.monsters.map((m) => [m.id, m]));

// Every new agent gets a random Pokémon from the whole roster (493 of them), never one another agent
// on screen already has. The pick is kept in shared state so every part shows the same one and it
// survives a restart; an agent keeps its Pokémon until it goes away.
export function assign(list) {
  const old = shared(KEY) ?? { map: {} };
  const map = {};
  let changed = false;
  for (const a of list) {
    const id = old.map?.[a.address];
    if (id && BY_ID.has(id)) map[a.address] = id;
  }
  for (const a of list) {
    if (map[a.address]) continue;
    const used = new Set(Object.values(map));
    const free = M.monsters.filter((m) => !used.has(m.id));
    const pool = free.length ? free : M.monsters;
    map[a.address] = pool[Math.floor(Math.random() * pool.length)].id;
    changed = true;
  }
  if (Object.keys(old.map ?? {}).some((k) => !(k in map))) changed = true;
  if (changed) setShared(KEY, { map });
  return new Map(Object.entries(map));
}

// A Pokémon with its file paths filled in: monsters/<id>/<file>, where the manifest's "files" says which
// file each pose uses (walk and wave share idle's) and the face crops are the same for every pose
const expanded = new Map();

export function monsterOf(id) {
  const m = BY_ID.get(id) ?? M.monsters[0];
  let e = expanded.get(m.id);
  if (!e) {
    const dir = `monsters/${m.id}/`;
    const F = M.files;
    const poses = Object.keys(F.frames);
    const same = (file) => Object.fromEntries(poses.map((k) => [k, dir + file]));
    const frames = Object.fromEntries(poses.map((k) => [k, dir + F.frames[k]]));
    frames.head = dir + F.head;
    e = { ...m, frames, heads: same(F.head), avatars: same(F.avatar), face: dir + F.face };
    expanded.set(m.id, e);
  }
  return e;
}

// ---------- Sinnoh location per space ----------
const PLACE_KEY = "pokemon.places";
const PLACE_BY_ID = new Map(M.places.map((p) => [p.id, p]));

// Every space gets a random location from the manifest, never one another space has while some are free;
// kept in shared state like the Pokémon, so a space keeps its place until it closes
export function assignPlaces(list) {
  const old = shared(PLACE_KEY) ?? { map: {} };
  const map = {};
  let changed = false;
  for (const s of list) {
    const id = old.map?.[s.id];
    if (id && PLACE_BY_ID.has(id)) map[s.id] = id;
  }
  for (const s of list) {
    if (map[s.id]) continue;
    const used = new Set(Object.values(map));
    const free = M.places.filter((p) => !used.has(p.id));
    const pool = free.length ? free : M.places;
    map[s.id] = pool[Math.floor(Math.random() * pool.length)].id;
    changed = true;
  }
  if (Object.keys(old.map ?? {}).some((k) => !(k in map))) changed = true;
  if (changed) setShared(PLACE_KEY, { map });
  return new Map(Object.entries(map));
}

export const placeOf = (id) => PLACE_BY_ID.get(id) ?? M.places[0];

// the location of one space (by id)
export const placeFor = (spaceId) => placeOf(assignPlaces(spaces()).get(spaceId));
