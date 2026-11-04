// 怪兽快讯：后台 Agent 拆完了（done）或在等你（blocked）时，右下角浮出新闻条
//   规则同 veggie 收获卡片：首次见到不算；最多显示 3 条；点一条跳过去并移除；
//   自己切过去、状态变化或 Agent 消失时自动移除；× 清空；没有条目不渲染
import { div, image, svg } from "gpui-kit";
import { v_flex, h_flex } from "gpui-base";
import { agents, props, run, notify, closeOverlay, exec } from "herdr";
import { asset, assign, monsterOf } from "./state.js";
import { task } from "./roster.js";

const HOT = (s) => s === "done" || s === "blocked";

// Herdr posts its own toast for the same event ("… is done" / "needs you") next to this card, and a
// layout can't replace the toast mod. So the card retracts it: overlay ids are sequential ("o46"), so a
// probe notification (closed before it can draw) reveals the counter, and `herdr-app status` says whether
// anything but toasts is open. Only when toasts are the only overlays, the ids just below the probe are
// closed; closing an id that isn't live does nothing. Called twice per event, since Herdr may post its
// toast a moment after the status change reaches us.
async function dismissStockToasts() {
  const probe = notify({ title: "", timeout: 1 });
  closeOverlay(probe);
  const n = Number(String(probe).replace(/\D/g, ""));
  if (!n) return;
  let overlays;
  try {
    overlays = JSON.parse((await exec("herdr-app", ["status"])).stdout).overlays;
  } catch {
    return;
  }
  if (!Array.isArray(overlays) || !overlays.length || overlays.some((o) => o !== "toast")) return;
  for (let k = 1; k <= 16; k++) closeOverlay(`o${n - k}`);
}
const MAX = 3;
const RED = "#d9573f";

// 根据 agents() 的变化更新 view.news（每次 render 调用）
function track(view) {
  const n = (view.news ??= { items: [], last: new Map() });
  const list = agents();
  const live = new Map(list.map((a) => [a.address, a]));
  for (const a of list) {
    const prev = n.last.get(a.address);
    // seen before (in any state, even starting) and now done or blocked
    if (prev !== undefined && !HOT(prev) && HOT(a.status) && !a.focused) {
      n.items = n.items.filter((it) => it.address !== a.address);
      n.items.unshift({ address: a.address, pane: a.pane, fresh: true });
    }
  }
  n.last = new Map(list.map((a) => [a.address, a.status]));
  n.items = n.items.filter((it) => {
    const a = live.get(it.address);
    return a && !a.focused && HOT(a.status);
  });
  return n;
}

// props().demo：截图检查用的假条目 [{address, status, space_name, program: {name}, monster}]
export function news(view, t, cx) {
  const demo = props()?.demo;
  const n = demo ? { items: demo } : track(view);
  if (!n.items.length) return div();
  const live = new Map(agents().map((a) => [a.address, a]));
  const mids = demo ? null : assign(agents());
  // 新条目先画高一点，下一帧落回原位，弹簧带出回弹
  if (!demo && n.items.some((it) => it.fresh)) {
    cx.timer.after(40, (cx) => { n.items.forEach((it) => (it.fresh = false)); cx.notify(); });
  }
  // a new entry replaces Herdr's toast for the same event
  if (!demo && n.items.some((it) => it.fresh && !it.swept)) {
    n.items.forEach((it) => (it.swept = true));
    cx.timer.after(5, () => dismissStockToasts());
    cx.timer.after(450, () => dismissStockToasts());
  }

  const row = (it) => {
    const a = live.get(it.address) ?? it;
    const m = monsterOf(demo ? it.monster : mids.get(it.address));
    // done reads like a battle line: "Pikachu used Thunderbolt!" / "Defeated: <task>"; blocked: "<name> needs you!"
    const where = a.space_name ?? "";
    const what = task(a);
    const done = a.status !== "blocked";
    const title = done ? `${m.name} used ${m.move ?? "Tackle"}!` : `${m.name} needs you!`;
    const detail = done ? `Defeated: ${what || where || a.program?.name || "the task"}` : [where, what].filter(Boolean).join(" · ") || (a.program?.name ?? "Agent");
    return h_flex().id(`news-${it.address}`).h(48).px(6).gap(8).items_center().cursor_pointer()
      .hover((s) => s.bg(t.hover))
      .on_mouse_down("left", (_e, cx) => cx.stop_propagation())
      .on_click((_e, cx) => {
        if (demo) return;
        n.items = n.items.filter((x) => x.address !== it.address);
        run("pane.focus", { pane: it.pane });
        cx.notify();
      })
      .child(div().relative().size(32).flex_none()
        .child(div().absolute().left(0).top(it.fresh ? -12 : 0).spring("top", { response: 420, damping: 0.42 })
          .child(image(asset(t, m.face)).size(32))))
      .child(v_flex().flex_1().min_w(0)
        .child(h_flex().min_w(0).text_size(12)
          .child(div().flex_none().text_color(RED).child("NEWS | "))
          .child(div().min_w(0).truncate().text_color(t.foreground).child(title)))
        .child(div().truncate().text_size(12).text_color(t.dim).child(detail)))
      .when(a.status === "blocked", (el) => el.child(div().size(6).flex_none().bg("#d8a548")));
  };

  const more = n.items.length - MAX;
  // 浮层外框（底色、边框、圆角、阴影）由 Herdr 画；这里只画内容：顶部 3px 红色像素条 + 条目
  return v_flex().w(286)
    .child(div().h(3).mx(6).bg(RED))
    .child(v_flex().p(4).gap(2)
      .child(h_flex().h(20).px(6).items_center().justify_between()
        .child(div().text_size(12).text_color(t.dim).child("POKEDEX NEWS"))
        .child(div().id("news-clear").p(3).cursor_pointer().text_color(t.dim)
          .hover((s) => s.bg(t.hover).text_color(t.foreground))
          .on_mouse_down("left", (_e, cx) => cx.stop_propagation())
          .on_click((_e, cx) => { if (!demo) { n.items = []; cx.notify(); } })
          .child(svg("mods/workspace-chrome/x.svg").size(12))))
      .children(n.items.slice(0, MAX).map(row))
      .when(more > 0, (el) => el.child(div().px(6).pb(2).text_size(12).text_color(t.dim).child(`${more} more`))));
}
