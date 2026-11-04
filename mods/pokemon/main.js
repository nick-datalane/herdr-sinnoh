// Pokémon Sinnoh: a reskin of Jiqize's Kaiju City layout for Herdr (github.com/Jiqize/herdr-kaiju, MIT).
// One mod with several roles, picked by props():
//   city：the scene (space = a Sinnoh location, agent = a Pokémon), see city.js
//   roster：the Pokédex cards; a narrow rail when the sidebar is collapsed, see roster.js
//   top：the space capsule and the tab pills, see top.js
//   news：the battle-line news card, see news.js (entries come from the watcher in watch.js)
//   pane header: when props carry a pane, see pane.js

import { View, div } from "gpui-kit";
import { props, theme, nextCommand } from "herdr";
import { city } from "./city.js";
import { roster, toggleSidebar } from "./roster.js";
import { top } from "./top.js";
import { paneHeader } from "./pane.js";
import { news } from "./news.js";
import { startWatch } from "./watch.js";

export default class Kaiju extends View {
  init(_props, cx) {
    // 只有名册这一份接快捷键命令（keys.json: "cmd-b": "pokemon.toggle"），避免多份抢命令
    if (props()?.part === "roster") {
      startWatch(cx); // the news watcher: one copy, keeps running while the window is hidden
      cx.spawn(async (cx) => {
        for (;;) {
          const c = await nextCommand();
          if (c.endsWith("toggle")) toggleSidebar();
          cx.notify();
        }
      });
    }
  }

  render(cx) {
    const t = theme();
    if (props()?.pane) return paneHeader(this, t);
    const part = props()?.part;
    if (part === "city") return city(this, t, cx);
    if (part === "roster") return roster(this, t, cx);
    if (part === "top") return top(this, t);
    if (part === "news") return news(this, t, cx);
    return div();
  }
}
