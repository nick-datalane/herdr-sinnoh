// Shared logic: asset paths, night detection, the random Pokémon per agent and the random Sinnoh location per space
import { spaces, shared, setShared, terminals } from "herdr";
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
const key = (s) => String(s).toLowerCase().replace(/[^a-z0-9\u2640\u2642]/g, "");
const BY_NAME = new Map(M.monsters.map((m) => [key(m.name), m]));

// A person can pick an agent's Pokémon by hand with a label on its terminal, `hc label t4 pokemon=piplup`
// (a name or a Dex number); the label stays with the terminal, so the choice survives restarts. Unknown
// names are ignored and the random pick stays.
function chosen(address) {
  const want = terminals().find((t) => t.address === address)?.labels?.pokemon;
  if (want == null || want === "") return null;
  const m = BY_ID.get(String(want).trim().padStart(3, "0")) ?? BY_NAME.get(key(want));
  return m?.id ?? null;
}

// Every new agent gets a random Pokémon from the whole roster (493 of them), never one another agent
// on screen already has, unless its terminal's `pokemon` label names one. The pick is kept in shared
// state so every part shows the same one and it survives a restart; an agent keeps its Pokémon until
// it goes away.
export function assign(list) {
  const old = shared(KEY) ?? { map: {} };
  const map = {};
  let changed = false;
  for (const a of list) {
    const want = chosen(a.address);
    const id = want ?? old.map?.[a.address];
    if (id && BY_ID.has(id)) map[a.address] = id;
    if (want && want !== old.map?.[a.address]) changed = true;
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
const PLACE_BY_NAME = new Map(M.places.map((p) => [key(p.name), p]));

// a place by id ("verity") or by name ("Lake Verity", "lake verity"), else null
export function placeNamed(v) {
  const t = String(v ?? "").trim();
  return PLACE_BY_ID.get(t.toLowerCase()) ?? PLACE_BY_NAME.get(key(t)) ?? null;
}

// `hc label <t> place=verity` on any terminal of a space names that space's place: space id → label value
function placeLabels() {
  const out = new Map();
  for (const t of terminals()) {
    const sid = t.labels?.["herdr.space"];
    const want = t.labels?.place;
    if (sid && want != null && want !== "" && !out.has(sid)) out.set(sid, String(want));
  }
  return out;
}

// Every space gets a random location from the manifest, never one another space has while some are free;
// kept in shared state like the Pokémon, so a space keeps its place until it closes. A `place` label on one of
// its terminals picks the place instead; it acts once per value (recorded in `labels`), so a click on the
// scene's caption can still move on afterwards.
export function assignPlaces(list) {
  const old = shared(PLACE_KEY) ?? { map: {} };
  const map = {};
  const labels = {};
  const wanted = placeLabels();
  let changed = false;
  for (const s of list) {
    let id = old.map?.[s.id];
    const want = wanted.get(s.id) ?? wanted.get(s.id.replace(/^.*\//, ""));   // remote ids carry a machine/ prefix
    if (want !== undefined) {
      labels[s.id] = want;
      if (want !== old.labels?.[s.id]) {
        const p = placeNamed(want);
        if (p) id = p.id;
        changed = true;
      }
    }
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
  if (JSON.stringify(labels) !== JSON.stringify(old.labels ?? {})) changed = true;
  if (changed) setShared(PLACE_KEY, { map, labels });
  return new Map(Object.entries(map));
}

// the next (step 1) or previous (step -1) place for a space, in manifest order: the caption click
export function stepPlace(spaceId, step = 1) {
  const cur = shared(PLACE_KEY) ?? { map: {} };
  const ids = M.places.map((p) => p.id);
  const i = Math.max(0, ids.indexOf(cur.map?.[spaceId]));
  const map = { ...(cur.map ?? {}), [spaceId]: ids[(i + step + ids.length) % ids.length] };
  setShared(PLACE_KEY, { ...cur, map });
}

export const placeOf = (id) => PLACE_BY_ID.get(id) ?? M.places[0];

// the location of one space (by id)
export const placeFor = (spaceId) => placeOf(assignPlaces(spaces()).get(spaceId));
