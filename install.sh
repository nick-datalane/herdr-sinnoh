#!/bin/sh
# Installs the Pokémon Sinnoh layout into the Herdr app's home folder (only this layout's own files).
# Respects HERDR_APP_HOME. Merges the layout's cmd-b binding into keys.json, asking before replacing a key
# that is already bound to something else, and backs keys.json up first.
set -e
cd "$(dirname "$0")"
H="${HERDR_APP_HOME:-$HOME/.config/herdr-app}"
if [ ! -d "$H" ]; then
  echo "Herdr app home not found at $H. Open the Herdr app once first (or set HERDR_APP_HOME)." >&2
  exit 1
fi
mkdir -p "$H/layouts" "$H/themes" "$H/mods/pokemon"
cp layouts/pokemon.json layouts/pokemon.svg "$H/layouts/"
cp themes/pokemon.json themes/pokemon-night.json "$H/themes/"
rsync -a --delete --exclude jsconfig.json --exclude '*.d.ts' mods/pokemon/ "$H/mods/pokemon/"

python3 -I - "$H/keys.json" mods/pokemon/keys.json <<'PY'
import json, os, shutil, sys, time
dst, src = sys.argv[1], sys.argv[2]
mine = json.load(open(src))
cur = json.load(open(dst)) if os.path.exists(dst) else {}
changed = False
for section, binds in mine.items():
    sec = cur.setdefault(section, {})
    for key, action in binds.items():
        if sec.get(key) == action:
            continue
        if key in sec:
            print(f"[{section}] {key} is bound to {sec[key]}; change it to {action}? [y/N] ", end="", flush=True)
            try:
                reply = open("/dev/tty").readline().strip().lower()
            except OSError:
                reply = ""
            if reply != "y":
                print("kept the existing binding")
                continue
        sec[key] = action
        changed = True
if changed:
    if os.path.exists(dst):
        shutil.copy(dst, f"{dst}.bak-{time.strftime('%Y%m%d%H%M%S')}")
    json.dump(cur, open(dst, "w"), indent=2, ensure_ascii=False)
    print("keys.json: added the layout's cmd-b binding")
PY
echo "installed to $H"
echo "switch to it with:  herdr-app do layout.switch '{\"name\":\"pokemon\"}'   (or ctrl-shift-l in the app)"
