"""
Build a self-contained flashcard app from cards/*.json.

Produces out/flashcards.html - one file, no server, no network. Open it by
double-clicking. Card data is embedded at build time so it works over file://.

Difficulty marks are deliberately NOT stored in the cards. They live in the
browser's localStorage and can be exported to difficulty.json, so regenerating
every card never touches your progress.

    python build_app.py
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).parent
CARDS = HERE / "cards"
GROUPS = HERE / "groups"
OUT = HERE / "out"

# Order the group kinds by study value, most useful first.
KIND_ORDER = ["meaning", "lookalike", "second-meaning", "intensity",
              "connotation", "antonym", "root"]
KIND_LABEL = {
    "meaning": "Meaning cluster", "lookalike": "Lookalike",
    "second-meaning": "Second meaning", "intensity": "Intensity scale",
    "connotation": "Connotation", "antonym": "Opposites", "root": "Root family",
}

# Only the fields the app actually renders - keeps the payload small.
KEEP = ("word", "pos", "pron", "pron_note", "means", "trap", "trick_line",
        "trick_unpack", "sentences", "in_the_wild", "etymology",
        "one_line", "root", "root_family", "confusables", "sense_tags",
        "register", "connotation", "groups")

TEMPLATE = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>GRE Vocab</title>
<style>
:root{
  --bg:#12131a; --panel:#1a1c26; --panel2:#22252f; --line:#2e3240;
  --ink:#e8e9ee; --dim:#9aa0b0; --accent:#7aa2f7;
  --easy:#5fbf7f; --medium:#e0b354; --hard:#e06a6a;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
header{position:sticky;top:0;z-index:10;background:var(--panel);
  border-bottom:1px solid var(--line);padding:10px 16px;
  display:flex;gap:10px;align-items:center;flex-wrap:wrap}
h1{font-size:15px;margin:0 8px 0 0;font-weight:650;letter-spacing:.3px}
input,select,button{font:inherit;background:var(--panel2);color:var(--ink);
  border:1px solid var(--line);border-radius:7px;padding:6px 10px}
input:focus,select:focus{outline:1px solid var(--accent)}
button{cursor:pointer}
button:hover{border-color:var(--accent)}
button.on{background:var(--accent);color:#0d0f16;border-color:var(--accent);font-weight:600}
#search{min-width:200px;flex:1;max-width:340px}
.spacer{flex:1}
.stats{color:var(--dim);font-size:13px;white-space:nowrap}
.dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:4px}
main{max-width:860px;margin:0 auto;padding:20px 16px 80px}

/* ---- browse ---- */
.row{display:flex;align-items:baseline;gap:10px;padding:9px 12px;
  border:1px solid var(--line);border-left-width:3px;border-radius:8px;
  margin-bottom:6px;cursor:pointer;background:var(--panel)}
.row:hover{border-color:var(--accent)}
.row .w{font-weight:650;min-width:150px}
.row .g{color:var(--dim);font-size:13px;flex:1}
.row .tag{color:var(--dim);font-size:11px;border:1px solid var(--line);
  border-radius:20px;padding:1px 8px}
.d-easy{border-left-color:var(--easy)} .d-medium{border-left-color:var(--medium)}
.d-hard{border-left-color:var(--hard)} .d-none{border-left-color:var(--line)}

/* ---- card ---- */
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;
  padding:22px 26px;margin-bottom:14px}
.card h2{margin:0;font-size:26px;font-weight:700}
.card .pos{color:var(--dim);font-weight:400;font-style:italic;font-size:17px}
.card .pron{color:var(--accent);font-weight:650;font-size:19px;margin-left:8px}
.card .note{color:var(--dim);font-style:italic;font-size:13px;margin-top:4px}
h3{font-size:12px;text-transform:uppercase;letter-spacing:1.2px;color:var(--dim);
  margin:22px 0 8px;font-weight:650}
blockquote{margin:10px 0;padding:10px 16px;border-left:3px solid var(--accent);
  background:var(--panel2);border-radius:0 8px 8px 0}
ol,ul{margin:8px 0;padding-left:22px} li{margin:5px 0}
strong{color:#fff} em{color:var(--dim)}
.sep{border:0;border-top:1px solid var(--line);margin:18px 0}

/* ---- drill ---- */
.drill{min-height:340px}
.drill .front{text-align:center;padding:46px 0 30px}
.drill .front h2{font-size:42px}
.hidden{display:none}
.marks{display:flex;gap:10px;justify-content:center;margin-top:20px}
.marks button{padding:10px 22px;font-weight:600;min-width:104px}
.mk-hard{border-color:var(--hard);color:var(--hard)}
.mk-medium{border-color:var(--medium);color:var(--medium)}
.mk-easy{border-color:var(--easy);color:var(--easy)}
.mk-hard:hover{background:var(--hard);color:#12131a}
.mk-medium:hover{background:var(--medium);color:#12131a}
.mk-easy:hover{background:var(--easy);color:#12131a}
.nav{display:flex;justify-content:space-between;align-items:center;
  margin-top:16px;color:var(--dim);font-size:13px}
.empty{text-align:center;color:var(--dim);padding:60px 20px}

/* ---- groups ---- */
.row.grow{border-left-color:var(--accent)}
.tag.kind{min-width:112px;text-align:center;color:var(--accent);
  border-color:var(--accent);flex:0 0 auto}
ul.nuance{list-style:none;padding-left:0;margin:14px 0 0}
ul.nuance li{border-left:3px solid var(--line);padding:5px 0 5px 12px;margin:9px 0}
.chips{display:flex;flex-wrap:wrap;gap:7px;margin-top:8px}
.chip{font-size:12px;border:1px solid var(--line);border-radius:20px;
  padding:3px 11px;cursor:pointer;color:var(--dim);background:var(--panel2)}
.chip b{color:var(--accent);font-weight:600}
.chip:hover{border-color:var(--accent)}
.bar{height:3px;background:var(--panel2);border-radius:2px;overflow:hidden;margin-top:12px}
.bar div{height:100%;background:var(--accent);transition:width .2s}
</style></head><body>

<header>
  <h1>GRE Vocab</h1>
  <button id="mBrowse" class="on">Browse</button>
  <button id="mDrill">Drill</button>
  <button id="mGroups">Groups</button>
  <input id="search" placeholder="search word, meaning, root, tag…">
  <select id="group"></select>
  <select id="diff">
    <option value="">all marks</option>
    <option value="none">unmarked</option>
    <option value="hard">hard</option>
    <option value="medium">medium</option>
    <option value="easy">easy</option>
  </select>
  <button id="shuffle" title="Shuffle drill order">⤨</button>
  <div class="spacer"></div>
  <div class="stats" id="stats"></div>
  <button id="exp" title="Save your difficulty marks to a file">Export</button>
  <button id="imp" title="Load difficulty marks from a file">Import</button>
  <input type="file" id="file" accept=".json" class="hidden">
</header>

<main>
  <div id="browse"></div>
  <div id="drill" class="hidden"></div>
  <div id="groups" class="hidden"></div>
</main>

<script>
const CARDS = __DATA__;
const GROUPS = __GROUPS__;
const KINDLABEL = __KINDLABEL__;
const KEY = "gre-vocab-difficulty-v1";
let marks = JSON.parse(localStorage.getItem(KEY) || "{}");
let mode = "browse", order = [], idx = 0, revealed = false, openWord = null, openGroup = null;

/* word -> the groups it belongs to, so a card can show its neighbourhoods */
const GROUPS_OF = {};
GROUPS.forEach(g => g.words.forEach(w => {
  (GROUPS_OF[w.word.toLowerCase()] ||= []).push(g);
}));

const $ = id => document.getElementById(id);
const esc = s => (s||"").replace(/[&<>]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));

/* Minimal markdown - only what the card fields actually use. */
function md(src){
  if(!src) return "";
  const blocks = esc(src).split(/\n\s*\n/).map(b => b.trim()).filter(Boolean);
  return blocks.map(b => {
    const lines = b.split("\n");
    let html;
    if(lines.every(l => /^>\s?/.test(l)))
      html = "<blockquote>" + lines.map(l=>l.replace(/^>\s?/,"")).join("<br>") + "</blockquote>";
    else if(lines.every(l => /^[-*]\s+/.test(l)))
      html = "<ul>" + lines.map(l=>"<li>"+l.replace(/^[-*]\s+/,"")+"</li>").join("") + "</ul>";
    else if(lines.every(l => /^\d+\.\s+/.test(l)))
      html = "<ol>" + lines.map(l=>"<li>"+l.replace(/^\d+\.\s+/,"")+"</li>").join("") + "</ol>";
    else html = "<p>" + lines.join("<br>") + "</p>";
    return html;
  }).join("")
   .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
   .replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<em>$2</em>")
   .replace(/`([^`]+)`/g, "<code>$1</code>");
}

function save(){ localStorage.setItem(KEY, JSON.stringify(marks)); renderStats(); }
function mark(w,d){ if(d) marks[w]=d; else delete marks[w]; save(); }

function filtered(){
  const q = $("search").value.trim().toLowerCase();
  const g = $("group").value, d = $("diff").value;
  return CARDS.filter(c => {
    if(g && !(c.groups||[]).map(String).includes(g)) return false;
    const m = marks[c.word] || "none";
    if(d && m !== d) return false;
    if(!q) return true;
    return (c.word + " " + (c.one_line||"") + " " + (c.root||"") + " " +
            (c.sense_tags||[]).join(" ") + " " + (c.means||"")).toLowerCase().includes(q);
  });
}

function cardHTML(c, front){
  let h = `<div class="card"><h2>${esc(c.word)} <span class="pos">${esc(c.pos||"")}</span>`;
  if(c.pron) h += `<span class="pron">${esc(c.pron)}</span>`;
  h += `</h2>`;
  if(c.pron_note) h += `<div class="note">${md(c.pron_note)}</div>`;
  if(front) return h + `</div>`;
  h += `<h3>Means</h3>${md(c.means)}`;
  if(c.trap) h += md(c.trap);
  if(c.trick_line){
    h += `<h3>Trick to lock it in</h3><blockquote>${md(c.trick_line).replace(/<\/?p>/g,"")}</blockquote>`;
    if(c.trick_unpack) h += md(c.trick_unpack);
  }
  if(c.sentences && c.sentences.length)
    h += `<h3>In sentences</h3><ol>` + c.sentences.map(s=>`<li>${md(s).replace(/<\/?p>/g,"")}</li>`).join("") + `</ol>`;
  if(c.in_the_wild) h += `<h3>In the wild</h3>${md(c.in_the_wild)}`;
  if(c.etymology)  h += `<h3>Where it comes from</h3>${md(c.etymology)}`;
  const gs = GROUPS_OF[c.word.toLowerCase()] || [];
  if(gs.length){
    h += `<h3>Also sits in</h3><div class="chips">` + gs.map(g =>
      `<span class="chip" data-gid="${esc(g.id)}"><b>${esc(KINDLABEL[g.kind]||g.kind)}</b> ${esc(g.title)}</span>`
    ).join("") + `</div>`;
  }
  return h + `</div>`;
}

function groupHTML(g, open){
  let h = `<div class="row grow" data-gid="${esc(g.id)}">
      <span class="tag kind">${esc(KINDLABEL[g.kind]||g.kind)}</span>
      <span class="w">${esc(g.title)}</span>
      <span class="g">${g.words.map(w=>esc(w.word)).join(" · ")}</span></div>`;
  if(!open) return h;
  h += `<div class="card">${md(g.core)}<ul class="nuance">` +
       g.words.map(w=>{
         const m = marks[w.word] || "none";
         return `<li class="d-${m}"><strong>${esc(w.word)}</strong> — ${md(w.nuance).replace(/<\/?p>/g,"")}</li>`;
       }).join("") + `</ul>`;
  if(g.exam_note) h += `<blockquote><strong>On the exam:</strong> ${md(g.exam_note).replace(/<\/?p>/g,"")}</blockquote>`;
  return h + `</div>`;
}

function renderGroups(){
  const q = $("search").value.trim().toLowerCase();
  const list = GROUPS.filter(g => !q || (g.title + " " + g.core + " " +
      g.words.map(w=>w.word+" "+w.nuance).join(" ")).toLowerCase().includes(q));
  $("groups").innerHTML = list.length
    ? list.map(g => groupHTML(g, g.id === openGroup)).join("")
    : `<div class="empty">No group matches that.</div>`;
  document.querySelectorAll("#groups .grow").forEach(el =>
    el.onclick = () => { openGroup = openGroup === el.dataset.gid ? null : el.dataset.gid; renderGroups(); });
}

function renderBrowse(){
  const list = filtered();
  $("browse").innerHTML = list.length ? list.map(c => {
    const m = marks[c.word] || "none";
    const open = c.word === openWord;
    return `<div class="row d-${m}" data-w="${esc(c.word)}">
        <span class="w">${esc(c.word)}</span>
        <span class="g">${esc(c.one_line||"")}</span>
        <span class="tag">g${(c.groups||[]).join(",")}</span>
      </div>` + (open ? cardHTML(c,false) + markRow(c.word) : "");
  }).join("") : `<div class="empty">Nothing matches that filter.</div>`;

  document.querySelectorAll("#browse .row").forEach(el =>
    el.onclick = () => { openWord = openWord === el.dataset.w ? null : el.dataset.w; renderBrowse(); });
  wireMarks(renderBrowse);
}

function markRow(w){
  const m = marks[w]||"";
  return `<div class="marks" data-for="${esc(w)}">
    <button class="mk-hard ${m==="hard"?"on":""}" data-d="hard">Hard</button>
    <button class="mk-medium ${m==="medium"?"on":""}" data-d="medium">Medium</button>
    <button class="mk-easy ${m==="easy"?"on":""}" data-d="easy">Easy</button>
    <button data-d="">Clear</button></div>`;
}

function wireMarks(rerender){
  document.querySelectorAll(".marks").forEach(box =>
    box.querySelectorAll("button").forEach(b =>
      b.onclick = e => { e.stopPropagation(); mark(box.dataset.for, b.dataset.d); rerender(); }));
}

function renderDrill(){
  const list = order.length ? order.map(w=>CARDS.find(c=>c.word===w)).filter(Boolean).filter(c=>filtered().includes(c)) : filtered();
  if(!list.length){ $("drill").innerHTML = `<div class="empty">Nothing matches that filter.</div>`; return; }
  if(idx >= list.length) idx = 0;
  const c = list[idx];
  $("drill").innerHTML =
    `<div class="drill">` +
      (revealed ? cardHTML(c,false)
                : `<div class="card front">${cardHTML(c,true).replace(/^<div class="card">|<\/div>$/g,"")}
                     <div style="margin-top:26px"><button id="show">Show answer</button></div></div>`) +
    `</div>` +
    (revealed ? markRow(c.word) : "") +
    `<div class="nav"><button id="prev">← prev</button>
       <span>${idx+1} / ${list.length}</span>
       <button id="next">skip →</button></div>
     <div class="bar"><div style="width:${(idx+1)/list.length*100}%"></div></div>`;

  const go = d => { idx = (idx + d + list.length) % list.length; revealed = false; renderDrill(); };
  if($("show")) $("show").onclick = () => { revealed = true; renderDrill(); };
  $("prev").onclick = () => go(-1);
  $("next").onclick = () => go(1);
  wireMarks(() => { idx = (idx+1) % list.length; revealed = false; renderDrill(); });
}

function renderStats(){
  const n = {easy:0,medium:0,hard:0};
  Object.values(marks).forEach(v => n[v] !== undefined && n[v]++);
  const done = n.easy+n.medium+n.hard;
  $("stats").innerHTML =
    `<span class="dot" style="background:var(--hard)"></span>${n.hard}
     <span class="dot" style="background:var(--medium)"></span>${n.medium}
     <span class="dot" style="background:var(--easy)"></span>${n.easy}
     &nbsp;· ${done}/${CARDS.length} marked`;
}

function render(){
  if(mode === "browse") renderBrowse();
  else if(mode === "drill") renderDrill();
  else renderGroups();
  renderStats();
}

/* Clicking a group chip on a card jumps to that group. */
document.addEventListener("click", e => {
  const chip = e.target.closest(".chip");
  if(!chip) return;
  e.stopPropagation();
  openGroup = chip.dataset.gid;
  setMode("groups");
  document.querySelector(`#groups .grow[data-gid="${CSS.escape(openGroup)}"]`)
    ?.scrollIntoView({block:"center"});
});

function setMode(m){
  mode = m;
  [["browse","mBrowse"],["drill","mDrill"],["groups","mGroups"]].forEach(([k,id]) => {
    $(id).classList.toggle("on", k === m);
    $(k).classList.toggle("hidden", k !== m);
  });
  if(m === "drill") revealed = false;
  render();
}

/* ---- wiring ---- */
const groups = [...new Set(CARDS.flatMap(c=>c.groups||[]))].sort((a,b)=>a-b);
$("group").innerHTML = `<option value="">all groups</option>` +
  groups.map(g=>`<option value="${g}">group ${g}</option>`).join("");

["search","group","diff"].forEach(id =>
  $(id).addEventListener("input", () => { idx=0; revealed=false; render(); }));

$("mBrowse").onclick = () => setMode("browse");
$("mDrill").onclick  = () => setMode("drill");
$("mGroups").onclick = () => setMode("groups");

$("shuffle").onclick = () => {
  order = filtered().map(c=>c.word);
  for(let i=order.length-1;i>0;i--){ const j=Math.floor(Math.random()*(i+1)); [order[i],order[j]]=[order[j],order[i]]; }
  idx=0; revealed=false; render();
};

$("exp").onclick = () => {
  const blob = new Blob([JSON.stringify(marks,null,2)],{type:"application/json"});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob); a.download = "difficulty.json"; a.click();
};
$("imp").onclick = () => $("file").click();
$("file").onchange = e => {
  const f = e.target.files[0]; if(!f) return;
  f.text().then(t => { marks = {...marks, ...JSON.parse(t)}; save(); render(); });
};

document.addEventListener("keydown", e => {
  if(mode!=="drill" || /input|select/i.test(e.target.tagName)) return;
  if(e.key===" "){ e.preventDefault(); revealed=true; renderDrill(); }
  if(e.key==="1") document.querySelector(".mk-hard")?.click();
  if(e.key==="2") document.querySelector(".mk-medium")?.click();
  if(e.key==="3") document.querySelector(".mk-easy")?.click();
  if(e.key==="ArrowRight") $("next")?.click();
  if(e.key==="ArrowLeft")  $("prev")?.click();
});

render();
</script></body></html>
"""


def main() -> int:
    files = sorted(CARDS.glob("*.json"))
    if not files:
        print(f"no cards in {CARDS}")
        return 1

    data = []
    for f in files:
        try:
            c = json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            print(f"skipping {f.name}: {e}")
            continue
        data.append({k: c.get(k) for k in KEEP if c.get(k) is not None})

    data.sort(key=lambda c: c["word"].lower())

    # Only groups that actually have prose - a discovered-but-unwritten group
    # would render as an empty heading.
    groups = []
    for f in sorted(GROUPS.rglob("*.json")):
        try:
            g = json.loads(f.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        if not g.get("core") or not g.get("words"):
            continue
        groups.append({"kind": g["kind"], "id": g["id"], "title": g["title"],
                       "core": g["core"], "words": g["words"],
                       "exam_note": g.get("exam_note")})
    groups.sort(key=lambda g: (KIND_ORDER.index(g["kind"]) if g["kind"] in KIND_ORDER else 99,
                               g["title"].lower()))

    OUT.mkdir(exist_ok=True)
    html = (TEMPLATE
            .replace("__DATA__", json.dumps(data, ensure_ascii=False))
            .replace("__GROUPS__", json.dumps(groups, ensure_ascii=False))
            .replace("__KINDLABEL__", json.dumps(KIND_LABEL, ensure_ascii=False)))
    dest = OUT / "flashcards.html"
    dest.write_text(html, encoding="utf-8")

    print(f"{len(data)} cards + {len(groups)} groups -> {dest}  "
          f"({dest.stat().st_size/1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
