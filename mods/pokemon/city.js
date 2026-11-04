// The scene: the current space's Sinnoh location (a Platinum overworld map, 1 map px = 1 logical px) with the
// space's agents standing in it as Pokémon. Resting agents nap under drifting Zs, working ones hum with music notes,
// done ones cheer with a "!!", blocked ones wave with a "?". Click a Pokémon to focus its pane.
import { div, image } from "gpui-kit";
import { spaces, agents, setAgentOrder, run, props } from "herdr";
import M from "./manifest.js";
import { asset, assign, assignPlaces, placeOf, monsterOf, STATUS_TEXT } from "./state.js";

const W = M.canvas.w;
const H = M.canvas.h;
const SP = M.sprite;
const MOVE = 500;
const POSE = { idle: "idle", working: "smash", done: "roar", blocked: "wave" };
const BUBBLE = { done: "bang", blocked: "question" };
// music notes over a working Pokémon: [effect, x offset from the feet centre, how far it floats up, period ms]
const NOTES = [["note1", -22, 8, 1500], ["note2", -4, 10, 1900], ["note3", 14, 7, 1700]];
// Zs over a sleeping one: slower, drifting up and right as they fade
const ZS = [["z1", 8, 0, 10, 2600], ["z2", 18, -10, 8, 3200]];   // [effect, dx, dy, rise, period]

const fx = (t, name) => {
  const [w, h] = M.fxSize[name];
  return image(asset(t, M.fx[name])).w(w).h(h);
};

// props().demo.agents: fake agents for screenshots, [{address, space: index, status, name}]
function agentList() {
  const demo = props()?.demo?.agents;
  if (!demo) return agents();
  const sp = spaces();
  return demo.map((d) => ({
    address: d.address, pane: null, status: d.status, focused: false,
    space: sp[d.space]?.id ?? "", program: { name: d.name ?? "agent" },
  }));
}

// one Pokémon with its feet at (x, y) on the stage; moves smoothly when its stand changes
function monster(t, a, mid, x, y) {
  const m = monsterOf(mid);
  const pose = POSE[a.status] ?? "idle";
  const el = div().id(`mon-${a.address}`).absolute().left(x - SP.ax).top(y - SP.ay).w(SP.w).h(SP.h)
    .transition("left", { duration: MOVE, easing: "ease-in-out" })
    .transition("top", { duration: MOVE, easing: "ease-in-out" })
    .child(image(asset(t, m.frames[pose])).w(SP.w).h(SP.h));
  const b = BUBBLE[a.status];
  if (b) {
    const [, bh] = M.fxSize[b];
    el.child(div().absolute().left(SP.ax + 14).top(m.top - bh - 2).child(fx(t, b)));
  }
  if (a.status === "idle") {
    ZS.forEach(([name, dx, dy, rise, period], k) => {
      const [, zh] = M.fxSize[name];
      el.child(div().absolute().left(SP.ax + dx).top(m.top - zh - 2 + dy)
        .child(div().id(`z-${a.address}-${k}`).absolute().left(0).top(0)
          .loop("top", { from: 0, to: -rise, period })
          .loop("opacity", { from: 1, to: 0.15, period })
          .child(fx(t, name))));
    });
  }
  if (a.status === "working") {
    NOTES.forEach(([name, dx, rise, period], k) => {
      const [, nh] = M.fxSize[name];
      el.child(div().absolute().left(SP.ax + dx).top(m.top - nh - 6)
        .child(div().id(`note-${a.address}-${k}`).absolute().left(0).top(0)
          .loop("top", { from: 0, to: -rise, period })
          .loop("opacity", { from: 1, to: 0.35, period })
          .child(fx(t, name))));
    });
  }
  return el;
}

export function city(view, t) {
  const list = spaces();
  const demo = props()?.demo;
  const ags = agentList();
  if (!demo?.agents) setAgentOrder(ags.map((a) => a.address));
  const mids = assign(ags);
  const places = assignPlaces(list);
  const cur = list.find((s) => s.active) ?? list[0];
  const stage = div().relative().w(W).h(H);
  if (!cur) return div().size_full().flex().justify_center().pt(8).child(stage);

  const place = placeOf(places.get(cur.id));
  // smaller maps sit centred on the canvas
  const ox = Math.floor((W - place.w) / 2);
  const oy = Math.floor((H - place.h) / 2);
  stage.child(image(asset(t, place.image)).absolute().left(ox).top(oy).w(place.w).h(place.h));

  // this space's agents on the stands, in order; past the last stand they double up a little further down
  const mine = ags.filter((a) => a.space === cur.id);
  const items = mine.map((a, k) => {
    const st = place.stands;
    const p = st[k % st.length];
    const round = Math.floor(k / st.length);
    return { a, x: ox + p.x + round * 12, y: oy + p.y + round * 8 };
  });
  // back to front: lower feet are drawn later
  items.sort((p, q) => p.y - q.y);
  for (const it of items) stage.child(monster(t, it.a, mids.get(it.a.address), it.x, it.y));

  // caption
  stage.child(div().absolute().left(ox + 6).top(oy + place.h - 26).h(20).px(6).flex().items_center()
    .bg("#000000a0").text_size(12).text_color("#ffffff").child(place.name));

  // click areas: a Pokémon focuses its pane
  const stop = (_e, cx) => cx.stop_propagation();
  for (const it of items) {
    const { a } = it;
    const m = monsterOf(mids.get(a.address));
    const h = SP.h - m.top;
    stage.child(div().id(`mhit-${a.address}`).absolute().left(it.x - 24).top(it.y - h).w(48).h(h)
      .cursor_pointer().tooltip(`${m.name} · ${a.program?.name ?? a.app ?? "Agent"} · ${STATUS_TEXT[a.status] ?? ""}`)
      .on_mouse_down("left", stop)
      .on_click(() => a.pane && run("pane.focus", { pane: a.pane })));
  }
  return div().size_full().flex().justify_center().pt(8).child(stage);
}
