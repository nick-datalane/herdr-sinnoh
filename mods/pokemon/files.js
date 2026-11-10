// The PC Box: the focused pane's folder as a tree, every folder a Poké Ball (a different ball at each depth, open
// when expanded) and every file an item by its type. Built on Herdr's own Files mod (mods/files/main.js, Apache-2.0):
// the lazy listing, the folder watch, the git marks and the read-only preview are its code, lightly reshaped. From
// the community file mods: a dot on folders holding changes (munza/better-files, prodBirdy/herdr-explorer) and a
// collapse-all button (herdr-explorer).
import { div, image } from "gpui-kit";
import { v_flex, h_flex, Editor, EditorState } from "gpui-base";
import { spaces, panes, focused, exec, readTextFile, watchFolder, settings, window } from "herdr";
import M from "./manifest.js";
import { asset } from "./state.js";

const BALLS = M.items.balls;
const ICON = M.items.size;
const ball = (t, depth, open) => asset(t, `items/${BALLS[depth % BALLS.length]}${open ? "-open" : ""}.png`);

// file → item: code is a TM in a colour of its own, writing is mail, data is a plain TM, pictures go in the album
const BY_EXT = {
  js: "tm-electric", mjs: "tm-electric", cjs: "tm-electric", jsx: "tm-electric",
  ts: "tm-water", tsx: "tm-water", mts: "tm-water", cts: "tm-water",
  py: "tm-grass", ipynb: "tm-grass", rb: "tm-fighting", rs: "tm-fire", go: "tm-ice", swift: "tm-fire",
  java: "tm-ground", kt: "tm-ground", c: "tm-steel", h: "tm-steel", cpp: "tm-steel", cs: "tm-psychic",
  php: "tm-poison", lua: "tm-dragon", zig: "tm-rock", sh: "tm-dark", zsh: "tm-dark", bash: "tm-dark", fish: "tm-dark",
  html: "tm-flying", css: "tm-flying", scss: "tm-flying", vue: "tm-bug", svelte: "tm-bug", sql: "tm-rock",
  md: "grass-mail", markdown: "grass-mail", txt: "grass-mail", rst: "grass-mail",
  json: "tm-normal", jsonc: "tm-normal", yaml: "tm-normal", yml: "tm-normal", toml: "tm-normal", xml: "tm-normal",
  lock: "tm-normal", ini: "tm-normal", env: "tm-normal",
  png: "photo-album", jpg: "photo-album", jpeg: "photo-album", gif: "photo-album", webp: "photo-album", svg: "photo-album",
  ico: "photo-album", csv: "journal", tsv: "journal", xlsx: "journal", pdf: "journal", docx: "journal",
};
function itemFor(name) {
  if (/^readme/i.test(name)) return "town-map";                 // the map of the project
  if (/^(license|licence|copying)/i.test(name)) return "journal";
  if (name.startsWith(".env")) return "tm-normal";
  const ext = name.includes(".") ? name.split(".").pop().toLowerCase() : "";
  return BY_EXT[ext] ?? "tm-normal";
}

// git mark → the tag on a row: [text, colour]
const MARK = { A: ["NEW", "#4f9b4f"], M: ["EDIT", "#d8a548"], D: ["GONE", "#d9573f"], U: ["!!", "#d9573f"] };

// ---- from Herdr's Files mod ----
function location() {
  const space = spaces().find(s => s.active), f = focused();
  const pane = f?.pane ? panes().find(p => p.pane === f.pane) : null;
  const on = f?.pane === null ? (f.terminal?.includes("/") ? f.terminal.split("/")[0] : null) : space?.machine ?? null;
  return { cwd: pane?.cwd || f?.cwd || space?.folder, on, space: space?.id };
}
const key = () => JSON.stringify(location());
const LANG = { ts: "js", tsx: "js", mts: "js", cts: "js", jsx: "js", mjs: "js", toml: "yaml", jsonc: "json", svelte: "html", vue: "html" };
const PER_FOLDER = 500, TOTAL = 5000;

async function directory(path, on) {
  const windowsDirectory = async () => {
    const r = await exec("powershell", ["-NoProfile", "-Command", "[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false); & { param($p) @(Get-ChildItem -LiteralPath $p -Force -ErrorAction Stop | Where-Object Name -ne '.git' | Select-Object -First 501 | ForEach-Object { @{ name=$_.Name; dir=($_.PSIsContainer -and (-not ($_.Attributes -band [IO.FileAttributes]::ReparsePoint) -or -not $_.LinkType -or ($_.Target -and [IO.Directory]::Exists(([IO.Path]::Combine([IO.Path]::GetDirectoryName($_.FullName), $_.Target[0])))))) } }) | ConvertTo-Json -Compress } '" + path.replace(/['‘’‚‛]/g, "$&$&") + "'"], { on });
    if (r.code !== 0) throw new Error(r.stderr || "Cannot list this folder");
    const result = JSON.parse(r.stdout || "[]");
    return Array.isArray(result) ? result : [result];
  };
  if (!on && window()?.platform === "windows") return windowsDirectory();
  const script = 'n=0; for p in "$1"/* "$1"/.[!.]* "$1"/..?*; do [ -e "$p" ] || [ -L "$p" ] || continue; name=${p##*/}; [ "$name" = .git ] && continue; if [ -d "$p" ]; then kind=d; else kind=f; fi; printf "%s\\0%s\\0" "$kind" "$name"; n=$((n+1)); [ "$n" -gt 500 ] && break; done; test -d "$1"';
  let r;
  try { r = await exec("sh", ["-c", script, "files", path], { on }); }
  catch (e) {
    if (on && String(e).includes("cannot start sh: program not found")) return windowsDirectory();
    throw e;
  }
  if (r.code !== 0) throw new Error(r.stderr || "Cannot list this folder");
  const fields = r.stdout.split("\0"), out = [];
  for (let i = 0; i + 1 < fields.length; i += 2) out.push({ name: fields[i + 1], dir: fields[i] === "d" });
  return out;
}

export class PCBox {
  init(cx) {
    this.saved = new Map();
    this.entries = new Map(); this.folders = new Set(); this.pending = new Set(); this.marks = {}; this.dirty = new Set();
    this.refresh(cx);
    cx.timer.every(10000, cx => this.refresh(cx));
  }

  watch(root, cx) {
    if (this.on || this.watched === root) return;
    this.watched = root;
    const context = this.context;
    cx.spawn(async cx => {
      try { while (this.context === context) { await watchFolder(root); if (this.current(context)) this.refresh(cx); } }
      catch { if (this.context === context) this.watched = null; }
    });
  }

  current(context) {
    return this.context === context && key() === context.key;
  }

  async loadFolder(path, context) {
    const { on, cwd: root } = context;
    const entries = await directory(path ? `${root}/${path}` : root, on);
    if (!this.current(context) || (path && !this.folders.has(path))) return;
    const used = [...this.entries.entries()].filter(([p]) => p !== path).reduce((n, [, e]) => n + e.length, 0);
    this.entries.set(path, entries.slice(0, Math.max(0, Math.min(PER_FOLDER, TOTAL - used))).sort((a, b) => Number(b.dir) - Number(a.dir) || a.name.localeCompare(b.name)));
    if (entries.length > PER_FOLDER || used + entries.length > TOTAL) this.limited = true;
  }

  refresh(cx) {
    const { cwd, on } = location(), next = key();
    if (next !== this.context?.key) {
      if (this.context) this.saved.set(this.context.key, { folders: this.folders, file: this.file });
      const saved = this.saved.get(next);
      this.context = { key: next, cwd, on }; this.root = cwd; this.on = on; this.entries = new Map(); this.folders = new Set(saved?.folders);
      this.pending = new Set(); this.marks = {}; this.dirty = new Set(); this.show(null); this.watched = null; this.error = null; this.limited = false;
      this.loading = false;
      if (saved?.file) this.show(saved.file, cx);
    }
    if (!cwd || this.loading) return;
    const context = this.context;
    this.loading = true;
    this.limited = false;
    cx.spawn(async cx => {
      try {
        for (const path of ["", ...this.folders]) {
          if (!this.current(context)) return;
          await this.loadFolder(path, context);
        }
        const top = await exec("git", ["rev-parse", "--show-toplevel"], { cwd, on }).catch(() => null);
        const marks = {};
        if (top?.code === 0) {
          // Writes nothing under .git (index lock, fsmonitor cookie): the folder watch would refresh again.
          const status = await exec("git", ["--no-optional-locks", "-c", "core.fsmonitor=false", "status", "--porcelain=v1", "-z", "--no-renames", "--untracked-files=all"], { cwd, on }).catch(() => null);
          if (status?.code === 0) for (const entry of status.stdout.split("\0").filter(Boolean).slice(0, TOTAL)) {
            const xy = entry.slice(0, 2);
            marks[`${top.stdout.trim()}/${entry.slice(3)}`] = xy === "??" || xy.includes("A") ? "A" : xy.includes("U") ? "U" : xy.includes("D") ? "D" : "M";
          }
        }
        if (!this.current(context)) return;
        // every folder (relative to the root) that holds a change somewhere below it
        const dirty = new Set(), pre = `${cwd}/`;
        for (const p of Object.keys(marks)) {
          if (!p.startsWith(pre)) continue;
          const parts = p.slice(pre.length).split("/");
          for (let i = 1; i < parts.length; i++) dirty.add(parts.slice(0, i).join("/"));
        }
        this.marks = marks; this.dirty = dirty; this.error = null; this.watch(cwd, cx);
      } catch (e) { if (this.current(context)) this.error = String(e); }
      finally { if (this.context === context) this.loading = false; cx.notify(); }
    });
  }

  toggle(path, cx) {
    if (this.folders.has(path)) {
      for (const folder of [...this.folders]) if (folder === path || folder.startsWith(path + "/")) {
        this.folders.delete(folder);
        this.entries.delete(folder);
      }
    } else {
      this.folders.add(path);
      if (!this.entries.has(path) && !this.pending.has(path)) {
        const context = this.context;
        this.pending.add(path);
        cx.spawn(async cx => {
          try { await this.loadFolder(path, context); }
          catch (e) { if (this.current(context)) this.error = String(e); }
          finally { if (this.context === context) this.pending.delete(path); cx.notify(); }
        });
      }
    }
    cx.notify();
  }

  collapseAll(cx) {
    for (const f of this.folders) this.entries.delete(f);
    this.folders = new Set();
    cx.notify();
  }

  show(path, cx) {
    this.code?.release(); this.code = null; this.file = path; this.fileError = null;
    if (!path || !cx) return;
    const context = this.context, root = this.root, on = this.on;
    cx.spawn(async cx => {
      try {
        const text = await readTextFile(`${root}/${path}`, { on });
        if (this.file !== path || !this.current(context)) return;
        if (text === null) { this.fileError = "This file is no longer available"; return; }
        if (text.includes("\0")) { this.fileError = "Binary file · no text preview"; return; }
        const t = this.t, ext = path.includes(".") ? path.split(".").pop() : "txt";
        this.code = EditorState.new({ language: LANG[ext] ?? ext, readonly: true,
          value: text.length > 400000 ? text.slice(0, 400000) + "\n… (file truncated)" : text,
          font_family: settings().font_family, font_size: 12,
          syntax: { keyword: t.ansi5, string: t.ansi2, comment: t.dim, function: t.ansi4, type: t.ansi3, number: t.ansi1, constant: t.ansi6 } });
      } catch { if (this.file === path && this.current(context)) this.fileError = "Cannot preview this file (binary, too large, or unreadable)"; }
      finally { cx.notify(); }
    });
  }

  // ---- the Pokémon look ----
  rows(prefix, depth, out, t) {
    if (out.length >= TOTAL || depth > 40) return out;
    for (const entry of this.entries.get(prefix) ?? []) {
      if (out.length >= TOTAL) break;
      const path = prefix ? `${prefix}/${entry.name}` : entry.name, open = this.folders.has(path), mark = this.marks[`${this.root}/${path}`];
      const tag = entry.dir ? null : MARK[mark];
      out.push(h_flex().id(`pc-${path}`).h(28).flex_none().pl(6 + depth * 16).pr(8).gap(6).items_center().cursor_pointer()
        .hover(s => s.bg(t.hover))
        .on_click((_e, cx) => entry.dir ? this.toggle(path, cx) : this.show(path, cx))
        .child(image(entry.dir ? ball(t, depth, open) : asset(t, `items/${itemFor(entry.name)}.png`)).size(ICON).flex_none())
        .child(div().flex_1().min_w(0).truncate().when(entry.dir, el => el.font_semibold()).child(entry.name))
        .when(entry.dir && this.dirty.has(path), el => el.child(div().size(6).flex_none().bg(MARK.M[1]).border(1).border_color(t.chrome)))
        .when(Boolean(tag), el => el.child(div().flex_none().px(4).text_size(10).font_semibold().text_color("#ffffff").bg(tag[1]).child(tag[0]))));
      if (entry.dir && open) this.rows(path, depth + 1, out, t);
    }
    return out;
  }

  render(cx, t) {
    this.t = t;
    if (key() !== this.context?.key) this.refresh(cx);
    const folder = this.root?.split(/[\\/]/).pop() ?? "";
    const headBtn = (id, label, tip, act) => div().id(id).flex_none().h(24).px(8).flex().items_center().cursor_pointer()
      .border(2).border_color(t.chrome).text_size(11).text_color(t.muted)
      .hover(s => s.bg(t.hover).text_color(t.foreground)).tooltip(tip).on_click(act).child(label);
    return v_flex().id("pc-box").size_full().min_h(0).overflow_hidden().bg(t.background).border_2().border_color(t.chrome)
      .text_color(t.foreground).text_size(13)
      .child(h_flex().h(42).flex_none().px(10).gap(8).items_center().border_b(2).border_color(t.chrome).bg(t.canvas)
        .when(Boolean(this.file), el => el.child(headBtn("pc-back", "← Box", "Back to the tree", (_e, cx) => { this.show(null); cx.notify(); })))
        .when(!this.file, el => el.child(image(ball(t, 0, false)).size(ICON).flex_none())
          .child(div().flex_none().font_semibold().child("PC Box")))
        .child(div().flex_1().min_w(0).truncate().text_right().text_size(12).text_color(t.dim).child(this.file ?? folder))
        .when(!this.file && this.folders.size > 0, el => el.child(headBtn("pc-collapse", "Close all", "Collapse every folder", (_e, cx) => this.collapseAll(cx)))))
      .when(!this.file, el => el.child(v_flex().id("pc-tree").flex_1().min_h(0).overflow_y_scrollbar().py(4).children(this.rows("", 0, [], t))
        .when(Boolean(this.error) || !this.entries.get("")?.length, el => el.child(div().p(8).text_size(12).text_color(t.dim).child(this.error || (this.loading ? "Booting up the PC…" : this.root ? "This box is empty" : "No folder"))))
        .when(this.limited, el => el.child(div().p(8).text_size(11).text_color(t.dim).child("Showing at most 500 entries per folder and 5,000 in all")))))
      .when(Boolean(this.file), el => el.child(this.code ? Editor.new(this.code).flex_1().min_h(0) : div().p(12).text_color(t.dim).child(this.fileError || "Loading file…")));
  }
}
