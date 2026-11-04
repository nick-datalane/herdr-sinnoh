// The watcher: the roster copy starts it (main.js) on a 1 s timer, and timers keep running while the Herdr
// window is hidden, when nothing renders. It spots agents that turned done or blocked while nobody was looking,
// keeps the news entries in shared "pokemon.news" (news.js draws them), retracts Herdr's own toast for the same
// event and, when the Herdr window isn't active, posts a macOS notification so the event reaches the person in
// whatever app they're in.
import { agents, shared, setShared, window as win, notify, closeOverlay, exec, run, layout } from "herdr";
import { assign, monsterOf, find } from "./state.js";
import { task } from "./roster.js";

export const NEWS = "pokemon.news"; // [{address, pane, at}], newest first
const HOT = (s) => s === "done" || s === "blocked";
// looking at it: its pane is focused and the Herdr window is the active one
const looking = (a, w) => Boolean(a.focused && w?.active);

export function startWatch(cx) {
  let last = null; // address → status at the previous tick; the first tick only takes the baseline
  cx.timer.every(1000, () => {
    if (!last) reconcileSidebar();
    const list = agents();
    const w = win();
    const items = shared(NEWS) ?? [];
    let next = items;
    if (last) {
      const mids = assign(list);
      for (const a of list) {
        const prev = last.get(a.address);
        if (prev === undefined || HOT(prev) || !HOT(a.status) || looking(a, w)) continue;
        next = [{ address: a.address, pane: a.pane, at: Date.now() }, ...next.filter((it) => it.address !== a.address)];
        dismissStockToasts();
        if (!w?.active) banner(a, monsterOf(mids.get(a.address)));
      }
    }
    last = new Map(list.map((a) => [a.address, a.status]));
    // an entry leaves when its agent is gone, no longer done/blocked, or being looked at
    const live = new Map(list.map((a) => [a.address, a]));
    next = next.filter((it) => {
      const a = live.get(it.address);
      return a && HOT(a.status) && !looking(a, w);
    });
    if (JSON.stringify(next) !== JSON.stringify(items)) setShared(NEWS, next);
  });
}

// After a restart the saved clicks can disagree: a wide sidebar with the scene block hidden, or the rail with it
// shown. cmd-b (roster.js toggleSidebar) always moves them together; this puts them back together once at start.
function reconcileSidebar() {
  const L = layout();
  const open = (find(L, "sidebar")?.size?.px ?? 400) >= 160;
  const hidden = Boolean(find(L, "city")?.hidden);
  if (open && hidden) run("layout.show", { id: "city" });
  if (!open && !hidden) run("layout.hide", { id: "city" });
}

// the battle line: "Pikachu used Thunderbolt!" / "Defeated: <task>"; blocked: "Pikachu needs you!"
export function headline(a, m) {
  const done = a.status !== "blocked";
  const where = a.space_name ?? "";
  const what = task(a);
  return {
    title: done ? `${m.name} used ${m.move ?? "Tackle"}!` : `${m.name} needs you!`,
    detail: done
      ? `Defeated: ${what || where || a.program?.name || "the task"}`
      : [where, what].filter(Boolean).join(" · ") || (a.program?.name ?? "Agent"),
  };
}

// Herdr posts its own toast for the same event, and a layout can't replace the shipped toast mod. Overlay ids are
// sequential ("o46"), so a probe notification closed before it can draw reveals the counter, and `herdr-app status`
// says whether anything but toasts is open. Only then are the ids just below the probe closed; an id that isn't
// live is a no-op. Twice, since Herdr may post its toast a moment after the status change.
export function dismissStockToasts(again = true) {
  const probe = notify({ title: "", timeout: 1 });
  closeOverlay(probe);
  const n = Number(String(probe).replace(/\D/g, ""));
  if (!n) return;
  exec("herdr-app", ["status"])
    .then((r) => {
      const overlays = JSON.parse(r.stdout).overlays;
      if (!Array.isArray(overlays) || !overlays.length || overlays.some((o) => o !== "toast")) return;
      for (let k = 1; k <= 16; k++) closeOverlay(`o${n - k}`);
    })
    .catch(() => {});
  if (again) exec("sleep", ["0.5"]).then(() => dismissStockToasts(false)).catch(() => {});
}

// a macOS notification through osascript (no extra tools needed); the sender shows as Script Editor
const q = (s) => `"${String(s).replace(/[\\"]/g, (c) => "\\" + c).replace(/\s+/g, " ")}"`;
function banner(a, m) {
  const { title, detail } = headline(a, m);
  const sub = a.space_name ? ` subtitle ${q(a.space_name)}` : "";
  exec("osascript", ["-e", `display notification ${q(detail)} with title ${q(title)}${sub}`]).catch(() => {});
}
