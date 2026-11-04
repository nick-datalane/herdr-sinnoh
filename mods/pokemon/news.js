// Pokédex news: the battle-line card at the bottom right for agents that finished (done) or wait (blocked) while
// nobody was looking. The watcher (watch.js) keeps the entries in shared "pokemon.news"; this part only draws them:
// newest on top, at most 3 shown, a face that springs in; click an entry to go there and remove it; × clears all;
// nothing is drawn without entries.
import { div, image, svg } from "gpui-kit";
import { v_flex, h_flex } from "gpui-base";
import { agents, props, run, shared, setShared } from "herdr";
import { asset, assign, monsterOf } from "./state.js";
import { NEWS, headline } from "./watch.js";

const MAX = 3;
const RED = "#d9573f";

// props().demo: fake entries for the screenshot check [{address, status, space_name, program: {name}, monster}]
export function news(view, t, cx) {
  const demo = props()?.demo;
  const items = demo ?? shared(NEWS) ?? [];
  if (!items.length) return div();
  const live = new Map(agents().map((a) => [a.address, a]));
  const mids = demo ? null : assign(agents());
  // an entry draws 12 px high the first time and springs down on the next frame
  const sprung = (view.sprung ??= new Set());
  const key = (it) => `${it.address}@${it.at ?? 0}`;
  const fresh = (it) => !demo && !sprung.has(key(it));
  if (items.some(fresh)) cx.timer.after(40, (cx) => { items.forEach((it) => sprung.add(key(it))); cx.notify(); });

  const row = (it) => {
    const a = live.get(it.address) ?? it;
    const m = monsterOf(demo ? it.monster : mids.get(it.address));
    const { title, detail } = headline(a, m);
    return h_flex().id(`news-${it.address}`).h(48).px(6).gap(8).items_center().cursor_pointer()
      .hover((s) => s.bg(t.hover))
      .on_mouse_down("left", (_e, cx) => cx.stop_propagation())
      .on_click((_e, cx) => {
        if (demo) return;
        setShared(NEWS, items.filter((x) => x.address !== it.address));
        run("pane.focus", { pane: it.pane });
        cx.notify();
      })
      .child(div().relative().size(32).flex_none()
        .child(div().absolute().left(0).top(fresh(it) ? -12 : 0).spring("top", { response: 420, damping: 0.42 })
          .child(image(asset(t, m.face)).size(32))))
      .child(v_flex().flex_1().min_w(0)
        .child(h_flex().min_w(0).text_size(12)
          .child(div().flex_none().text_color(RED).child("NEWS | "))
          .child(div().min_w(0).truncate().text_color(t.foreground).child(title)))
        .child(div().truncate().text_size(12).text_color(t.dim).child(detail)))
      .when(a.status === "blocked", (el) => el.child(div().size(6).flex_none().bg("#d8a548")));
  };

  const more = items.length - MAX;
  // Herdr draws the floating frame (background, border, corners, shadow); this is only the content: a 3 px red bar + rows
  return v_flex().w(286)
    .child(div().h(3).mx(6).bg(RED))
    .child(v_flex().p(4).gap(2)
      .child(h_flex().h(20).px(6).items_center().justify_between()
        .child(div().text_size(12).text_color(t.dim).child("POKEDEX NEWS"))
        .child(div().id("news-clear").p(3).cursor_pointer().text_color(t.dim)
          .hover((s) => s.bg(t.hover).text_color(t.foreground))
          .on_mouse_down("left", (_e, cx) => cx.stop_propagation())
          .on_click((_e, cx) => { if (!demo) { setShared(NEWS, []); cx.notify(); } })
          .child(svg("mods/workspace-chrome/x.svg").size(12))))
      .children(items.slice(0, MAX).map(row))
      .when(more > 0, (el) => el.child(div().px(6).pb(2).text_size(12).text_color(t.dim).child(`${more} more`))));
}
