# Pokémon Sinnoh · a layout for the Herdr app

![Pokémon Sinnoh](preview.png)

A [Herdr](https://herdr.dev) desktop layout in the look of Pokémon Platinum, built on top of **[Kaiju City](https://github.com/Jiqize/herdr-kaiju) by [Jiqize](https://github.com/Jiqize)**, who made the original layout, its sidebar, dossier cards and news card. This is a reskin of that work; the Pokémon parts are the only new thing. The sidebar shows the current space as one of twelve Sinnoh locations, cut from the real DS overworld maps, with the space's agents standing in it as Pokémon drawn with their Platinum sprites. Every space gets a random place and every agent a random Pokémon out of all 493. Working Pokémon hum with music notes, done ones cheer with sparkles, blocked ones wave a "?", resting ones nap. The Pokédex below lists the agents as dossier cards with their Dex number, task, place and score, and a news card announces finished work as "Bidoof used Tackle! Defeated: fix the login bug".

![The twelve places](art/samples/assets-check.png)

## Install

Needs the Herdr desktop app (built and checked with 0.1.13 on macOS) and the `python3` that ships with macOS. No Python packages: all the art is in the repo, ready made.

```sh
git clone https://github.com/nick-datalane/herdr-sinnoh.git
cd herdr-sinnoh
./install.sh
herdr-app do layout.switch '{"name":"pokemon"}'
```

`install.sh` copies only this layout's own files into `~/.config/herdr-app/` (it respects `HERDR_APP_HOME`): `layouts/pokemon.json` + `.svg`, `themes/pokemon.json` + `pokemon-night.json` and `mods/pokemon/`. It merges one key, `cmd-b` → collapse the sidebar while this layout is shown, into `keys.json`, asks before replacing a `cmd-b` you already bound in this layout's section, and backs `keys.json` up first. The chrome and the cards follow the system's light or dark mode; the scenes and the Pokémon are always in daylight.

## Keys

| Key | Action |
|---|---|
| `cmd-b` | collapse / expand the sidebar |
| `ctrl-1…9` | go to space N |
| `cmd-1…9` | go to tab N |
| `ctrl-shift-l` | switch layout |
| click a Pokémon or a card | focus that agent's pane |
| click the space capsule | rename the space |

## What you get

- **Twelve places**, random per space: Lake Verity, Lake Acuity, Floaroma Meadow, Eterna Forest, Sunyshore City, Snowpoint City, Valor Lakefront, the Pokémon League, the Resort Area, Flower Paradise, Twinleaf Town and Hearthome City. A space keeps its place until it closes.
- **The scenes move a little**, as on the DS: lake and sea water drifts, the League's waterfall flows, the flowers of Floaroma and Flower Paradise sway, snow falls on Snowpoint, Hearthome's fountains run, the ponds of Twinleaf and the Resort (and its hot springs) glint, and Eterna's tall grass rustles one clump at a time. All twelve places are animated GIFs built from the same maps.
- **Pick a scene**: click the place name in the scene for the next place, right-click for the previous one. Or label any terminal of the space with a place id or name, `hc label t4 place=verity`, which an agent can do for you. The choice is kept with the space.
- **All 493 Pokémon**, random per agent, with their Platinum battle sprites. An agent keeps its Pokémon until it goes away. To pick one by hand, label the agent's terminal with a name or Dex number, `hc label t4 pokemon=piplup`; the label stays with the terminal, so the choice survives restarts.
- **Status without noise**: working = music notes, done = sparkles and "!!", blocked = "?", resting = slowly drifting Zs. Nothing shakes.
- **Pokédex cards** (or small photos: the toggle in the header) with the Dex number, the app, the tab, the task, a timer, the place and a score.
- **The PC Box**, a file tree: the Poké Ball button at the top right opens the focused pane's folder. Every folder is a Poké Ball, a different one at each level (Poké, Great, Ultra, Master, Premier and on through the Platinum balls), shut when collapsed and popped open when expanded; click to open or close, **Close all** to fold everything. Files are items by type: TMs for code (a colour per language), mail for writing, the town map for a README, the photo album for pictures. Changed files carry NEW / EDIT / GONE tags and folders holding changes a dot. Click a file to read it.
- **Battle-line news** for agents finishing in the background: "Giratina used Shadow Force! Defeated: migrate the schema". Click it to jump there.

## Uninstall

Switch to another layout (`ctrl-shift-l`), then delete `layouts/pokemon.json`, `layouts/pokemon.svg`, `themes/pokemon.json`, `themes/pokemon-night.json` and `mods/pokemon/` from `~/.config/herdr-app/`, and the `layout:pokemon` section from `keys.json`.

## Changing the art (optional)

The build lives in `art/` and needs Pillow and numpy (`pip3 install pillow numpy`).

- Places: `art/places.json` lists each place's map (`art/maps-gen4/`), the 400×480 window to show and the spots where Pokémon stand; `art/animate.py` says how each place moves. The whole process is in [Adding a scene](#adding-a-scene). If a wiki rip was captured at dusk (Floaroma Meadow was), `art/daylight.py` recolours it to daylight from a daytime screenshot of the same tiles.
- Pokémon: `art/roster.json` lists who can appear; delete lines to shrink the pool to favourites.
- Then `python3 art/build_assets.py`, look at `art/samples/assets-check.png`, and run `./install.sh` again.

[RECIPE.md](RECIPE.md) is the full brief: what every part shows, how it behaves and what it is built from.

## Adding a scene

Every scene is a window cut from a real DS overworld map, with four spots where the Pokémon stand and, where the place has water or flowers, a description of what moves. Adding one takes an evening at most; the build does the rest.

1. **Get the map.** Find the Platinum (or Diamond/Pearl) overworld map of the place on the [Pokémon Fandom wiki](https://pokemon.fandom.com) at native size: 1 image pixel = 1 DS pixel, so a tile is 16 px. (Bulbapedia refuses downloads.) Save it as `art/maps-gen4/<id>.png`, where `<id>` is a short lowercase name you will use everywhere (`acuity`, `valor-beach`).
2. **Check the light.** The art is always daylight. Some rips are captured at dusk (grass bluish, paths orange): keep the rip in `art/maps-gen4/raw/` and fix it with `python3 art/daylight.py <raw> <daytime reference> <out> [x0,y0,x1,y1 of the same tiles in each]`, which fits a per-channel gain and offset against a daytime screenshot of the same tiles. Floaroma Meadow was done this way.
3. **Choose the window.** Add an entry to `art/places.json`:
   ```json
   {"id": "acuity", "name": "Lake Acuity", "color": "#9fc4e6", "map": "acuity.png",
    "crop": [0, 150, 400, 480], "stands": [[200, 215], [300, 215], [195, 135], [295, 135]]}
   ```
   `crop` is `[x, y, w, h]` on the map, at most 400×480 (smaller windows are centred); pick a view with the place's best feature filling the frame. `color` is the place's swatch on the Pokédex cards and the top bar. `stands` are four `[x, y]` spots in crop coordinates where feet go: walkable ground, toward the middle (never a corner), at least a sprite apart (85 px sideways or 80 px vertically) so Pokémon never overlap. Past four agents the stands repeat a little down and right.
4. **Say what moves** in the `ANIM` table at the top of `art/animate.py`, or add `"<id>": {}` for a still scene:
   - `"water": (b−r, b−g, min b)`: how blue a pixel must be to count as water. `(60, 20, 120)` fits lakes and ponds, `(70, 30, 140)` the sea. Specks smaller than 300 px are ignored. The water's texture scrolls down and wraps over its own repeat; flat water (a pond with a shaded rim and no texture) is left still by itself.
   - `"split": [[x, y, w, h]]`: rectangles that cut a body with a texture of its own, such as a waterfall, out of the water around it, so each scrolls at its own repeat. Pixels that don't repeat (a crest, foam along a shore) stay still.
   - `"flowers": true`: small bright patches on grass are blooms and rock one pixel left and right.
   - `"glint": true`: flat water (a pond: one colour, nothing to scroll) gets small sparkles that come and go. `"pools": [g-r, |g-b|, min g]` adds teal water (hot springs) the blue rule misses.
   - `"fountains": true`: pale cyan fountains get rings that flow down their tiers from the jet.
   - `"snow": true`: snow falls over the whole scene, in three layers.
   - `"rustle": 5`: that many tall grass clumps, spread over the scene, shake two pixels in turn, with a pause between.

   Check what got caught: `python3 art/animate.py --masks` writes `art/animated/masks.png` (water in blue, blooms in magenta, pools in green, fountains in cyan, tall grass in yellow with the rustling clumps in red), and `python3 art/animate.py <id>` writes `art/animated/<id>.gif` plus `preview.html`, each GIF next to its still scene, for a look in a browser. Loops stay within 16 frames, since Herdr keeps every decoded frame of a shown GIF in memory (about 8 MB each).
5. **Build.** `python3 art/build_assets.py` (needs numpy, Pillow and scipy; on a Mac whose Python can't see them under `-I`, run it plainly). It cuts the scene, builds the GIF, makes the 64 px thumb for the cards, rewrites `manifest.js` and checks every file. Look at `art/samples/assets-check.png`: every scene with Pokémon on its stands.
6. **Install.** `./install.sh`, or copy `mods/pokemon/assets/` and `mods/pokemon/manifest.js` into `~/.config/herdr-app/mods/pokemon/`; Herdr reloads the mod on save. New spaces may now draw the place; to see it at once, click the place name in the scene until it comes up, or `hc label <a terminal of the space> place=<id>`.

Removing a place is the reverse: delete its entry (and its map if you like) and rebuild; spaces that had it get a new random one.

## Credits

- Started from Jiqize's [Kaiju City](https://github.com/Jiqize/herdr-kaiju) layout (MIT), whose structure, Pokédex cards and news card this keeps.
- Pixel font: [Fusion Pixel Font](https://github.com/TakWolf/fusion-pixel-font), SIL OFL 1.1.
- Pokémon sprites, names and move data from [PokeAPI](https://github.com/PokeAPI/sprites); location maps from the Pokémon Fandom wiki. Pokémon is © Nintendo / Creatures Inc. / GAME FREAK inc. This is a fan-made skin for personal use; the code is MIT, the game art is not.
