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
BANK = HERE / "bank"
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
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<script src="https://accounts.google.com/gsi/client" async defer></script>
<link href="https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,400;8..60,600;8..60,700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
/* ============================================================
   Design tokens. Five themes; every colour flows from these.
   --scale drives ALL sizing - not browser zoom, so layout holds
   together and only type and spacing grow.
   ============================================================ */
:root[data-theme="aqua"]{
  --bg:#eef7fa; --panel:#fff; --panel2:#e3f0f5; --line:#cbe2ea;
  --ink:#0f2a33; --ink2:#2c4a54; --dim:#6b8c98;
  --accent:#0d8fa8; --accent-soft:rgba(13,143,168,.12);
  --easy:#118a63; --medium:#a1741a; --hard:#c04a3d;
  --shadow:0 1px 2px rgba(10,60,75,.06),0 8px 24px rgba(10,60,75,.07); }
:root[data-theme="midnight"]{
  --bg:#0f1117; --panel:#171a23; --panel2:#1e222d; --line:#2a2f3d;
  --ink:#e9ebf0; --ink2:#b9c0cf; --dim:#7f8799;
  --accent:#8ab4ff; --accent-soft:rgba(138,180,255,.14);
  --easy:#5ec98a; --medium:#e3b55f; --hard:#ec7272;
  --shadow:0 1px 2px rgba(0,0,0,.4),0 8px 24px rgba(0,0,0,.24); }
:root[data-theme="forest"]{
  --bg:#0e1512; --panel:#152019; --panel2:#1c2a22; --line:#26382d;
  --ink:#e6efe8; --ink2:#b4c6ba; --dim:#7b9384;
  --accent:#68d19b; --accent-soft:rgba(104,209,155,.14);
  --easy:#68d19b; --medium:#d8b45f; --hard:#e37b72;
  --shadow:0 1px 2px rgba(0,0,0,.4),0 8px 24px rgba(0,0,0,.22); }
:root[data-theme="paper"]{
  --bg:#f7f6f3; --panel:#fff; --panel2:#f0eeea; --line:#e0ddd6;
  --ink:#1d1c1a; --ink2:#403d38; --dim:#7d786f;
  --accent:#2f5fd0; --accent-soft:rgba(47,95,208,.10);
  --easy:#1f8a4c; --medium:#a8760c; --hard:#c0392b;
  --shadow:0 1px 2px rgba(30,25,15,.06),0 8px 24px rgba(30,25,15,.06); }
:root[data-theme="sepia"]{
  --bg:#efe6d6; --panel:#faf3e6; --panel2:#f0e6d2; --line:#ded0b6;
  --ink:#2b2317; --ink2:#4a3f2d; --dim:#857755;
  --accent:#9a5b1e; --accent-soft:rgba(154,91,30,.12);
  --easy:#4a7c3f; --medium:#96702a; --hard:#a83c2b;
  --shadow:0 1px 2px rgba(80,60,20,.08),0 8px 24px rgba(80,60,20,.08); }

:root{ --scale:1; --radius:14px;
  --ui:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
  --read:"Source Serif 4",Georgia,"Times New Roman",serif; }
*{box-sizing:border-box}
html{font-size:calc(16px*var(--scale))}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--ui);
  font-size:1rem;line-height:1.65;-webkit-font-smoothing:antialiased;
  transition:background .2s,color .2s}

header{position:sticky;top:0;z-index:30;
  background:color-mix(in srgb,var(--panel) 92%,transparent);
  backdrop-filter:blur(12px);border-bottom:1px solid var(--line);
  padding:.55rem .9rem;display:flex;gap:.5rem;align-items:center;flex-wrap:wrap}
h1{font-size:1rem;margin:0 .3rem 0 0;font-weight:700;letter-spacing:-.01em}
.tabs{display:flex;gap:.15rem;background:var(--panel2);padding:.18rem;border-radius:11px}
button{cursor:pointer;font:inherit}
.tab{border:0;background:none;color:var(--dim);font-weight:600;font-size:.87rem;
  padding:.4rem .8rem;border-radius:8px}
.tab.on{background:var(--panel);color:var(--ink);box-shadow:var(--shadow)}
input,select{font:inherit;background:var(--panel2);color:var(--ink);
  border:1px solid var(--line);border-radius:9px;padding:.42rem .65rem;font-size:.9rem}
input:focus,select:focus{outline:2px solid var(--accent-soft);border-color:var(--accent)}
.btn{background:var(--panel);color:var(--ink);border:1px solid var(--line);
  border-radius:9px;padding:.42rem .8rem;font-size:.87rem;font-weight:600}
.btn:hover{border-color:var(--accent);color:var(--accent)}
.btn.on,.btn.primary{background:var(--accent);border-color:var(--accent);color:var(--panel)}
.icon{border:1px solid var(--line);background:var(--panel);color:var(--ink2);
  width:2.1rem;height:2.1rem;border-radius:9px;display:grid;place-items:center;font-size:.95rem}
.icon:hover{border-color:var(--accent);color:var(--accent)}
#search{min-width:11rem;flex:1;max-width:20rem}
.spacer{flex:1}
.stats{color:var(--dim);font-size:.8rem;white-space:nowrap}
.dot{display:inline-block;width:.5rem;height:.5rem;border-radius:50%;margin-right:.25rem}
.fontctl{display:flex;align-items:center;gap:.2rem;background:var(--panel2);
  border-radius:10px;padding:.15rem .3rem}
.fontctl button{border:0;background:none;color:var(--ink2);font-weight:700;
  padding:.22rem .42rem;border-radius:7px}
.fontctl button:hover{background:var(--panel);color:var(--accent)}
.fontctl .sm{font-size:.72rem}.fontctl .lg{font-size:1.05rem}
.fontctl output{font-size:.72rem;color:var(--dim);min-width:2.5rem;text-align:center;
  font-variant-numeric:tabular-nums}
main{max-width:46rem;margin:0 auto;padding:1.3rem 1rem 6rem}
/* !important because .sheet sets display:grid later in the file and would
   otherwise win on equal specificity, leaving the settings sheet always open. */
.hidden{display:none!important}
.sep{border:0;border-top:1px solid var(--line);margin:1.1rem 0}

.row{display:flex;align-items:baseline;gap:.7rem;padding:.65rem .85rem;
  border:1px solid var(--line);border-left-width:3px;border-radius:10px;
  margin-bottom:.4rem;cursor:pointer;background:var(--panel)}
.row:hover{border-color:var(--accent)}
.row .w{font-weight:650;min-width:9rem;font-family:var(--read);font-size:1.05rem}
.row .g{color:var(--dim);font-size:.86rem;flex:1}
.row .tag{color:var(--dim);font-size:.7rem;border:1px solid var(--line);
  border-radius:20px;padding:.05rem .55rem}
.d-easy{border-left-color:var(--easy)}.d-medium{border-left-color:var(--medium)}
.d-hard{border-left-color:var(--hard)}.d-none{border-left-color:var(--line)}

.card{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);
  padding:1.5rem 1.6rem;margin-bottom:.9rem;box-shadow:var(--shadow)}
.card h2{margin:0;font-family:var(--read);font-size:2rem;font-weight:700;
  letter-spacing:-.02em;line-height:1.2;display:inline}
.card .pos{color:var(--dim);font-weight:400;font-style:italic;font-size:1rem;margin-left:.4rem}
.card .pron{color:var(--accent);font-weight:600;font-size:1.02rem;margin-left:.45rem;
  background:var(--accent-soft);padding:.1rem .5rem;border-radius:7px;white-space:nowrap}
.card .note{color:var(--dim);font-style:italic;font-size:.85rem;margin-top:.35rem}
h3{font-size:.7rem;text-transform:uppercase;letter-spacing:.14em;color:var(--dim);
  margin:1.4rem 0 .5rem;font-weight:700;display:flex;align-items:center;gap:.5rem}
h3::after{content:"";flex:1;height:1px;background:var(--line)}
.card p,.card li{font-family:var(--read);font-size:1.05rem;line-height:1.72;color:var(--ink2)}
.card strong,strong{color:var(--ink);font-weight:600}
em{color:var(--dim)}
blockquote{font-family:var(--read);margin:.6rem 0;padding:.8rem 1.1rem;
  border-left:3px solid var(--accent);background:var(--accent-soft);
  border-radius:0 10px 10px 0;font-size:1.05rem}
ol,ul{margin:.5rem 0;padding-left:1.3rem}li{margin:.45rem 0}
code{background:var(--panel2);padding:.05rem .3rem;border-radius:5px;font-size:.9em}
.chips{display:flex;flex-wrap:wrap;gap:.4rem;margin-top:.5rem}
.chip{font-size:.76rem;border:1px solid var(--line);border-radius:20px;
  padding:.18rem .7rem;color:var(--dim);background:var(--panel2);cursor:pointer}
.chip b{color:var(--accent);font-weight:600}
.chip:hover{border-color:var(--accent)}

.speak{border:1px solid var(--line);background:var(--panel2);color:var(--accent);
  border-radius:50%;width:1.9rem;height:1.9rem;display:inline-grid;place-items:center;
  font-size:.85rem;flex:0 0 auto;vertical-align:middle;margin-left:.4rem;padding:0}
.speak:hover{background:var(--accent);color:var(--panel);border-color:var(--accent)}
.speaking{background:var(--accent-soft);border-radius:6px;
  box-shadow:0 0 0 .35rem var(--accent-soft)}
.readbar{display:flex;align-items:center;gap:.5rem;flex-wrap:wrap;margin-bottom:.8rem;
  background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);
  padding:.6rem .8rem;box-shadow:var(--shadow)}
.readbar label{font-size:.74rem;color:var(--dim);font-weight:600}

.drill{min-height:20rem}
.drill .front{text-align:center;padding:3rem 0 2rem}
.drill .front h2{font-size:2.8rem}
.marks{display:flex;gap:.6rem;justify-content:center;margin-top:1.2rem;flex-wrap:wrap}
.marks button{padding:.6rem 1.3rem;font-weight:600;min-width:6rem;border-radius:10px;
  border:1px solid var(--line);background:var(--panel);color:var(--ink)}
.mk-hard{border-color:var(--hard);color:var(--hard)}
.mk-medium{border-color:var(--medium);color:var(--medium)}
.mk-easy{border-color:var(--easy);color:var(--easy)}
.mk-hard:hover{background:var(--hard);color:var(--panel)}
.mk-medium:hover{background:var(--medium);color:var(--panel)}
.mk-easy:hover{background:var(--easy);color:var(--panel)}
.nav{display:flex;justify-content:space-between;align-items:center;
  margin-top:1rem;color:var(--dim);font-size:.83rem}
.empty{text-align:center;color:var(--dim);padding:3.5rem 1rem}
.bar{height:3px;background:var(--panel2);border-radius:2px;overflow:hidden;margin-top:.7rem}
.bar div{height:100%;background:var(--accent);transition:width .2s}

.q{max-width:42rem;margin:0 auto}
.qhead{display:flex;justify-content:space-between;align-items:baseline;
  color:var(--dim);font-size:.8rem;margin-bottom:.7rem;gap:.6rem;flex-wrap:wrap}
.qtype{color:var(--accent);text-transform:uppercase;letter-spacing:.12em;
  font-size:.7rem;font-weight:700}
.qstem{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);
  padding:1.3rem 1.45rem;font-family:var(--read);font-size:1.12rem;line-height:1.78;
  box-shadow:var(--shadow)}
.qstem p{margin:.4rem 0}
.qstem .blank{color:var(--accent);font-weight:700;letter-spacing:.05em}
.opts{display:flex;flex-direction:column;gap:.45rem;margin-top:.85rem}
.opt{text-align:left;padding:.75rem 1rem;font-size:.98rem;border-radius:11px;
  background:var(--panel);border:1px solid var(--line);color:var(--ink);
  transition:border-color .12s,transform .06s}
.opt:hover:not(:disabled){border-color:var(--accent);transform:translateX(2px)}
.opt:disabled{cursor:default}
.opt.correct{border-color:var(--easy);background:color-mix(in srgb,var(--easy) 12%,var(--panel))}
.opt.wrong{border-color:var(--hard);background:color-mix(in srgb,var(--hard) 12%,var(--panel))}
.opt.picked{border-color:var(--accent);background:var(--accent-soft)}
.opt.missed{border-color:var(--easy);border-style:dashed}
.opt .why{display:block;color:var(--dim);font-size:.83rem;margin-top:.3rem;line-height:1.5}
#typed{width:100%;padding:.8rem 1rem;font-size:1.05rem;margin-top:.9rem;font-family:var(--read)}
.verdict{margin-top:.9rem;padding:.9rem 1.1rem;border-radius:11px;background:var(--panel2);
  border-left:3px solid var(--accent);font-family:var(--read)}
.verdict h4{margin:0 0 .35rem;font-size:.9rem;font-family:var(--ui)}
.qfoot{display:flex;justify-content:space-between;align-items:center;
  margin-top:1rem;gap:.6rem;flex-wrap:wrap}
.score{color:var(--dim);font-size:.8rem}
.due{color:var(--accent);font-weight:600}
.setup{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);
  padding:1.4rem 1.5rem;box-shadow:var(--shadow)}
.setup h3{margin-top:0}.setup h3::after{display:none}
.setup label{display:flex;gap:.6rem;align-items:flex-start;margin:.6rem 0;cursor:pointer}
.setup input[type=checkbox]{margin-top:.3rem;accent-color:var(--accent)}
.setup .hint{color:var(--dim);font-size:.85rem}
.blankgrp{margin-top:1rem}
.blankgrp h5{margin:0 0 .45rem;font-size:.7rem;letter-spacing:.13em;
  text-transform:uppercase;color:var(--accent);font-weight:700}
.blankgrp .opts{margin-top:0}

.row.grow{border-left-color:var(--accent)}
.tag.kind{min-width:7rem;text-align:center;color:var(--accent);
  border-color:var(--accent);flex:0 0 auto}
ul.nuance{list-style:none;padding-left:0;margin:.9rem 0 0}
ul.nuance li{border-left:3px solid var(--line);padding:.3rem 0 .3rem .8rem;margin:.6rem 0}

.sheet{position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:50;
  display:grid;place-items:center;padding:1rem}
.sheet .inner{background:var(--panel);border:1px solid var(--line);border-radius:16px;
  padding:1.5rem 1.6rem;max-width:26rem;width:100%;box-shadow:var(--shadow);
  max-height:85vh;overflow:auto}
.acct{display:flex;align-items:center;gap:.7rem;margin-bottom:1rem}
.avatar{width:2.3rem;height:2.3rem;border-radius:50%;background:var(--accent);
  color:var(--panel);display:grid;place-items:center;font-weight:700;flex:0 0 auto}
.swatches{display:flex;gap:.45rem;flex-wrap:wrap;margin:.5rem 0 1rem}
.sw{border:2px solid var(--line);border-radius:10px;padding:.4rem .7rem;
  font-size:.8rem;font-weight:600;display:flex;align-items:center;gap:.4rem;
  background:var(--panel);color:var(--ink)}
.sw.on{border-color:var(--accent)}
.sw i{width:.85rem;height:.85rem;border-radius:50%;display:inline-block}
</style></head><body>

<header>
  <h1>GRE Vocab</h1>
  <div class="tabs">
    <button id="mBrowse" class="tab on">Browse</button>
    <button id="mDrill" class="tab">Drill</button>
    <button id="mQuiz" class="tab">Quiz</button>
    <button id="mGroups" class="tab">Groups</button>
  </div>
  <input id="search" placeholder="search word, meaning, root, tag...">
  <select id="group"></select>
  <select id="diff">
    <option value="">all marks</option>
    <option value="none">unmarked</option>
    <option value="hard">hard</option>
    <option value="medium">medium</option>
    <option value="easy">easy</option>
  </select>
  <button id="shuffle" class="icon" title="Shuffle drill order">&#8646;</button>
  <div class="spacer"></div>
  <div class="stats" id="stats"></div>
  <div class="fontctl" title="Text size">
    <button class="sm" id="fdown">A</button>
    <output id="fpct">100%</output>
    <button class="lg" id="fup">A</button>
  </div>
  <button id="openSettings" class="icon" title="Settings">&#9881;</button>
  <input type="file" id="file" accept=".json" class="hidden">
</header>

<main>
  <div id="browse"></div>
  <div id="drill" class="hidden"></div>
  <div id="quiz" class="hidden"></div>
  <div id="groups" class="hidden"></div>
</main>

<div id="sheet" class="sheet hidden"><div class="inner">
  <div style="display:flex;align-items:center;justify-content:space-between">
    <h3 style="margin:0">Settings</h3>
    <button id="closeSettings" class="icon">&times;</button>
  </div>

  <h3>Account</h3>
  <div id="acctBox"></div>

  <h3>Theme</h3>
  <div class="swatches" id="swatches"></div>

  <h3>Reading voice</h3>
  <label style="display:block"><span class="hint">Voice</span>
    <select id="vsel" style="width:100%;margin-top:.3rem"></select></label>
  <label style="display:block;margin-top:.6rem"><span class="hint">Speed <output id="rateOut">1.00x</output></span>
    <input type="range" id="rate" min=".6" max="1.4" step=".05" value="1" style="width:100%"></label>

  <h3>Progress</h3>
  <p class="hint" style="margin-top:0">Difficulty marks and review schedule. Kept out of the
     card data, so regenerating cards never touches them.</p>
  <div style="display:flex;gap:.5rem;flex-wrap:wrap">
    <button id="exp" class="btn">Export</button>
    <button id="imp" class="btn">Import</button>
  </div>
</div></div>

<script>
const CARDS = __DATA__;
const GROUPS = __GROUPS__;
const BANK = __BANK__;
const KINDLABEL = __KINDLABEL__;
const KEY = "gre-vocab-difficulty-v1";
let marks = JSON.parse(localStorage.getItem(KEY) || "{}");
let mode = "browse", order = [], idx = 0, revealed = false,
    openWord = null, openGroup = null, quizGroup = null;

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

function save(){ localStorage.setItem(KEY, JSON.stringify(marks)); renderStats();
  if(typeof queueSync === "function") queueSync(); }
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
  h += `<button class="speak" data-speak="${esc(c.word)}" title="Read the whole card aloud">&#9654;</button>`;
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
  h += `<div style="margin-top:16px"><button class="qgroup" data-gid="${esc(g.id)}">Quiz just these ${g.words.length} words →</button></div>`;
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
    el.onclick = () => go(openGroup === el.dataset.gid
      ? "/groups" : "/groups/" + encodeURIComponent(el.dataset.gid)));
  document.querySelectorAll("#groups .qgroup").forEach(el =>
    el.onclick = e => { e.stopPropagation(); go("/quiz/" + encodeURIComponent(el.dataset.gid)); });
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
    el.onclick = () => go(openWord === el.dataset.w
      ? "/browse" : "/browse/" + encodeURIComponent(el.dataset.w)));
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

/* ==========================================================================
   Spaced repetition (SM-2) + quiz
   --------------------------------------------------------------------------
   Recognition — "yes, I know that one" — is the weakest thing you can do with a
   flashcard, because familiarity feels identical to recall and isn't. Every
   question type below forces retrieval, and the hard distractors come from the
   word's own meaning cluster, which is exactly how the GRE builds its options.
   ========================================================================== */

const SRS_KEY = "gre-vocab-srs-v1";
let srs = JSON.parse(localStorage.getItem(SRS_KEY) || "{}");
const saveSrs = () => { localStorage.setItem(SRS_KEY, JSON.stringify(srs));
  if(typeof queueSync === "function") queueSync(); };
const DAY = 86400000;
const today = () => Math.floor(Date.now() / DAY);

/* SM-2. q: 0 = missed, 4 = got it, 5 = instant. */
function schedule(word, q){
  const s = srs[word] || {ef:2.5, iv:0, reps:0, lapses:0};
  if(q < 3){ s.reps = 0; s.iv = 1; s.lapses = (s.lapses||0) + 1; }
  else {
    s.reps++;
    s.iv = s.reps === 1 ? 1 : s.reps === 2 ? 6 : Math.round(s.iv * s.ef);
    s.ef = Math.max(1.3, s.ef + (0.1 - (5-q)*(0.08 + (5-q)*0.02)));
  }
  s.due = today() + Math.max(1, s.iv);
  s.seen = (s.seen||0) + 1;
  srs[word] = s; saveSrs();
}
const isDue = c => { const s = srs[c.word]; return !s || s.due <= today(); };
const dueCount = () => CARDS.filter(isDue).length;

/* ---- helpers ---- */
const pick = a => a[Math.floor(Math.random()*a.length)];
function shuffled(a){ a = a.slice(); for(let i=a.length-1;i>0;i--){ const j=Math.floor(Math.random()*(i+1)); [a[i],a[j]]=[a[j],a[i]]; } return a; }
const stemOf = w => { w = w.toLowerCase().split(" ")[0]; return w.slice(0, Math.max(4, w.length-3)); };
function maskWord(text, word){
  const re = new RegExp("\\b" + stemOf(word).replace(/[.*+?^${}()|[\]\\]/g,"\\$&") + "[a-z]*", "gi");
  return text.replace(re, "———");
}
/* Groups a word sits in, largest first, so distractors come from a real cluster. */
const groupsFor = w => (GROUPS_OF[w.toLowerCase()] || []);
/* Distractors in strict preference order, each tier exhausted before the next:
   the group being quizzed, then any group the word belongs to, then random.
   Shuffling the tiers together would let a random word beat an in-cluster one,
   which is exactly what makes a question easy. */
function distractors(card, n){
  const self = card.word.toLowerCase();
  const take = (src, seen) => shuffled([...new Set(src)]
      .filter(w => w.toLowerCase() !== self && !seen.has(w.toLowerCase())));

  const scoped = quizGroup && groupById(quizGroup);
  const tier1 = scoped ? scoped.words.map(m => m.word) : [];
  const tier2 = groupsFor(card.word).flatMap(g => g.words.map(m => m.word));

  const out = [], seen = new Set();
  for(const tier of [tier1, tier2]){
    for(const w of take(tier, seen)){
      if(out.length >= n) break;
      out.push(w); seen.add(w.toLowerCase());
    }
  }
  for(let i = 0; out.length < n && i < 400; i++){   // last resort: random
    const r = pick(CARDS).word;
    if(r.toLowerCase() !== self && !seen.has(r.toLowerCase())){ out.push(r); seen.add(r.toLowerCase()); }
  }
  return out;
}
const glossOf = w => (CARDS.find(c => c.word.toLowerCase() === w.toLowerCase()) || {}).one_line || "";
const groupById = id => GROUPS.find(g => g.id === id);
/* Words of the group the quiz is scoped to, or null when quizzing everything. */
function scopedCards(){
  const g = quizGroup && groupById(quizGroup);
  if(!g) return null;
  const want = new Set(g.words.map(m => m.word.toLowerCase()));
  return CARDS.filter(c => want.has(c.word.toLowerCase()));
}

/* ---- question generators: each returns {type,label,stem,options,answer,why} or null ---- */
const GEN = {
  cloze(c){
    const s = (c.sentences||[]).find(x => /\*\*.+?\*\*/.test(x));
    if(!s) return null;
    const opts = shuffled([c.word, ...distractors(c, 4)]);
    // md() escapes HTML before formatting, so the span has to go in as a plain
    // sentinel and be swapped for real markup afterwards.
    return {type:"cloze", label:"Fill the blank",
      stem: md(s.replace(/\*\*(.+?)\*\*/g, "@@BLANK@@"))
              .replace(/@@BLANK@@/g, '<span class="blank">———</span>'),
      options: opts, answer: c.word,
      why: `**${c.word}** — ${c.one_line}`, whyOpt: o => glossOf(o)};
  },
  nuance(c){
    const g = groupsFor(c.word).filter(g => g.words.length >= 4)
                .find(g => (g.words.find(m => m.word.toLowerCase()===c.word.toLowerCase())||{}).nuance);
    if(!g) return null;
    const mine = g.words.find(m => m.word.toLowerCase() === c.word.toLowerCase());
    const opts = shuffled(g.words.map(m => m.word)).slice(0, 5);
    if(!opts.some(o => o.toLowerCase() === c.word.toLowerCase())) opts[0] = c.word;
    return {type:"nuance", label:`Which word? — ${g.title}`,
      stem: md(maskWord(mine.nuance, c.word)),
      options: shuffled(opts), answer: c.word,
      why: `**${c.word}** — ${c.one_line}`, whyOpt: o => glossOf(o)};
  },
  odd(c){
    const g = groupsFor(c.word).find(g => g.words.length >= 4);
    if(!g) return null;
    const inGroup = shuffled(g.words.map(m=>m.word).filter(w => w.toLowerCase()!==c.word.toLowerCase())).slice(0,3);
    if(inGroup.length < 3) return null;
    const members = new Set(g.words.map(m=>m.word.toLowerCase()));
    let outsider = null;
    for(let i=0;i<60 && !outsider;i++){ const r = pick(CARDS).word; if(!members.has(r.toLowerCase())) outsider = r; }
    if(!outsider) return null;
    return {type:"odd", label:"Odd one out",
      stem: `<p>Four of these belong together. Which one does <strong>not</strong>?</p>`,
      options: shuffled([c.word, ...inGroup, outsider]), answer: outsider,
      why: `The other four are all **${g.title.toLowerCase()}**. ${outsider} — ${glossOf(outsider)}`,
      whyOpt: o => glossOf(o)};
  },
  strongest(c){
    const g = groupsFor(c.word).find(g => g.kind === "intensity" && g.words.length >= 3);
    if(!g) return null;
    const ws = g.words.map(m=>m.word);
    return {type:"strongest", label:`Intensity — ${g.title}`,
      stem: `<p>These sit on one scale. Which is the <strong>strongest</strong>?</p>`,
      options: shuffled(ws).slice(0,5), answer: ws[ws.length-1],
      why: `Weakest to strongest: ${ws.join(" → ")}`, whyOpt: o => glossOf(o)};
  },
  connotation(c){
    if(!c.connotation || c.connotation === "depends") return null;
    return {type:"connotation", label:"Positive or negative?",
      stem: `<p>What charge does <strong>${esc(c.word)}</strong> carry?<br><span style="color:var(--dim)">${esc(c.one_line)}</span></p>`,
      options: ["positive","neutral","negative"], answer: c.connotation,
      why: `**${c.word}** is ${c.connotation}. ${c.one_line}`};
  },
  tc2(c){ return bankQuestion(c, "tc2"); },
  se(c){ return bankQuestion(c, "se"); },
  fresh(c){ return bankQuestion(c, "cloze"); },
  recall(c){
    return {type:"recall", label:"Type the word", typed:true,
      stem: `<p>${esc(c.one_line)}</p><p style="color:var(--dim);font-size:14px">Starts with <strong>${esc(c.word[0])}</strong> · ${c.word.length} letters</p>`,
      options: null, answer: c.word,
      why: `**${c.word}** — ${c.one_line}`};
  },
};

/* ---- the pre-generated, independently verified bank ---------------------
   Each bank question was written offline and then blind re-solved by a second
   pass that had to agree on the answer AND judge it uniquely determined. They
   are the only source of real two-blank Text Completion and six-option Sentence
   Equivalence, which templates cannot produce.
   Seen ids are remembered so a question does not repeat until its pool is dry. */
const SEEN_KEY = "gre-vocab-seenq-v1";
let seenQ = new Set(JSON.parse(localStorage.getItem(SEEN_KEY) || "[]"));
const markSeen = id => { seenQ.add(id);
  localStorage.setItem(SEEN_KEY, JSON.stringify([...seenQ])); };

const BANK_BY_WORD = {};
BANK.forEach(q => (q.words||[]).forEach(w =>
  (BANK_BY_WORD[w.toLowerCase()] ||= []).push(q)));

function bankQuestion(card, kind){
  let pool = (BANK_BY_WORD[card.word.toLowerCase()] || []).filter(q => q.type === kind);
  if(!pool.length) return null;
  const fresh = pool.filter(q => !seenQ.has(q.id));
  const q = pick(fresh.length ? fresh : pool);   // recycle only once exhausted
  // Blanks the user must fill: tc2 has two picking one each, se has one picking two.
  const blanks = q.blanks.map((b, i) => ({
    label: q.type === "tc2" ? `Blank (${i === 0 ? "i" : "ii"})` : "Choose two",
    options: shuffled(b.options), answers: b.answers,
    need: q.type === "se" ? 2 : 1, sel: [],
  }));
  return {
    type: q.type, bankId: q.id, multi: true, blanks,
    label: q.type === "tc2" ? "Text Completion — two blanks"
         : q.type === "se"  ? "Sentence Equivalence — pick two"
         : "Fill the blank",
    stem: esc(q.stem)
            .replace(/\{1\}/g, '<span class="blank">———</span>')
            .replace(/\{2\}/g, '<span class="blank">———</span>'),
    why: q.explanation,
  };
}

/* ---- live top-up via Google Gemini -------------------------------------
   Optional. The bank is offline and verified; this is the escape hatch for
   when you want something it has never asked before.

   The key is YOURS, stored only in this browser's localStorage, and is sent
   only to generativelanguage.googleapis.com. Anyone with access to this device
   can read it, so use a free-tier key and restrict it in the Google console.

   Live questions are NOT verified - nothing blind-solves them before you see
   them - so they are off by default and labelled when they appear. */
const GEM_KEY = "gre-vocab-gemini-key", GEM_MODEL = "gre-vocab-gemini-model";
const gemKey   = () => localStorage.getItem(GEM_KEY) || "";
const gemModel = () => localStorage.getItem(GEM_MODEL) || "";
const GEM_BASE = "https://generativelanguage.googleapis.com/v1beta";

async function gemListModels(key){
  const r = await fetch(`${GEM_BASE}/models?key=${encodeURIComponent(key)}`);
  if(!r.ok) throw new Error((await r.json().catch(()=>({})))?.error?.message || `HTTP ${r.status}`);
  const j = await r.json();
  return (j.models||[])
    .filter(m => (m.supportedGenerationMethods||[]).includes("generateContent"))
    .map(m => m.name.replace(/^models\//, ""))
    .sort();
}

const LIVE_SYSTEM = `You write a single GRE verbal practice question.

Formats: "tc2" = one sentence with two interacting blanks written {1} and {2},
three options each. "se" = one sentence with blank {1}, six options, EXACTLY two
correct that give equivalent meaning. "cloze" = blank {1}, five options, one answer.

Rules:
- EXACTLY ONE answer set may be defensible. If a second option also genuinely
  fits, the question is broken. Add constraining context rather than hoping.
- The sentence must MAKE the word necessary, through contrast, cause or concession.
- Distractors must be near-synonyms or genuine confusables, never random words.
- Never put the answer or a variant of it elsewhere in the stem.
- Real adult subject matter: history, science, criticism, politics, biography.
- Answers must reproduce option strings verbatim.
- Explanation: why the answer fits and why the nearest wrong option does not.`;

const LIVE_SCHEMA = {
  type:"OBJECT",
  properties:{
    type:{type:"STRING", enum:["tc2","se","cloze"]},
    stem:{type:"STRING"},
    blanks:{type:"ARRAY", items:{type:"OBJECT", properties:{
      options:{type:"ARRAY", items:{type:"STRING"}},
      answers:{type:"ARRAY", items:{type:"STRING"}}},
      required:["options","answers"]}},
    explanation:{type:"STRING"}},
  required:["type","stem","blanks","explanation"],
};

async function liveQuestion(card, kind){
  const key = gemKey(), model = gemModel();
  if(!key || !model) throw new Error("no key or model set");
  const near = groupsFor(card.word).slice(0,4).map(g =>
    `${g.title}: ${g.words.map(m=>m.word).join(", ")}`).join("\n");
  const prompt = `Write ONE question of type "${kind}" whose target word is "${card.word}".

${card.word} (${card.pos||""}) — ${card.one_line||""}
${card.means||""}

Near-synonyms and confusables to draw distractors from:
${near || "(none recorded)"}`;

  const r = await fetch(`${GEM_BASE}/models/${encodeURIComponent(model)}:generateContent?key=${encodeURIComponent(key)}`,
    {method:"POST", headers:{"Content-Type":"application/json"},
     body: JSON.stringify({
       systemInstruction:{parts:[{text:LIVE_SYSTEM}]},
       contents:[{role:"user", parts:[{text:prompt}]}],
       generationConfig:{responseMimeType:"application/json", responseSchema:LIVE_SCHEMA},
     })});
  if(!r.ok) throw new Error((await r.json().catch(()=>({})))?.error?.message || `HTTP ${r.status}`);
  const j = await r.json();
  const txt = j?.candidates?.[0]?.content?.parts?.[0]?.text;
  if(!txt) throw new Error("empty response");
  const g = JSON.parse(txt);

  const blanks = g.blanks.map((b,i) => ({
    label: g.type === "tc2" ? `Blank (${i===0?"i":"ii"})` : "Choose two",
    options: shuffled(b.options), answers: b.answers,
    need: g.type === "se" ? 2 : 1, sel: [],
  }));
  return {
    type:g.type, multi:true, live:true, blanks, card,
    label:(g.type==="tc2"?"Text Completion":g.type==="se"?"Sentence Equivalence":"Fill the blank")+" — live, unverified",
    stem: esc(g.stem).replace(/\{1\}/g,'<span class="blank">———</span>')
                     .replace(/\{2\}/g,'<span class="blank">———</span>'),
    why: g.explanation,
  };
}

let quizTypes = JSON.parse(localStorage.getItem("gre-vocab-qtypes") ||
  '["tc2","se","fresh","cloze","nuance","odd","strongest","connotation","recall"]');
let quizOnlyDue = JSON.parse(localStorage.getItem("gre-vocab-qdue") || "true");
let q = null, qAnswered = false, qScore = {right:0, total:0}, qStarted = false;

function nextQuestion(){
  let pool = scopedCards() || filtered();
  // A group is small, so "only what's due" would usually empty it. Scope wins.
  if(quizOnlyDue && !quizGroup){ const d = pool.filter(isDue); if(d.length) pool = d; }
  if(!pool.length){ q = null; return; }
  for(let i=0;i<40;i++){
    const c = pick(pool);
    const t = pick(quizTypes);
    const made = GEN[t] && GEN[t](c);
    if(made){ made.card = c; q = made; qAnswered = false; return; }
  }
  q = {...GEN.recall(pick(pool)), card: pick(pool)}; qAnswered = false;
}

const sameSet = (a,b) => a.length===b.length &&
  a.map(x=>String(x).toLowerCase()).sort().join("|") ===
  b.map(x=>String(x).toLowerCase()).sort().join("|");

/* tc2 and se are graded all-or-nothing: both blanks, or both words. */
function checkMulti(){
  if(qAnswered) return;
  qAnswered = true;
  const ok = q.blanks.every(b => sameSet(b.sel, b.answers));
  qScore.total++; if(ok) qScore.right++;
  if(q.bankId) markSeen(q.bankId);
  schedule(q.card.word, ok ? 4 : 0);
  q.ok = ok;
  renderQuiz();
}

function answerQuestion(choice){
  if(qAnswered) return;
  qAnswered = true;
  const ok = String(choice).trim().toLowerCase() === String(q.answer).trim().toLowerCase();
  qScore.total++; if(ok) qScore.right++;
  if(q.bankId) markSeen(q.bankId);
  // Odd-one-out grades the cluster it tested, not the outsider.
  schedule(q.card.word, ok ? 4 : 0);
  q.chosen = choice; q.ok = ok;
  renderQuiz();
}

function renderQuiz(){
  const el = $("quiz");
  if(!qStarted){
    const scoped = quizGroup && groupById(quizGroup);
    const labels = {
      tc2:"Two-blank Text Completion from the verified bank. The real exam format, and the closest practice you have to the test itself.",
      se:"Sentence Equivalence from the bank — six options, pick the two that mean the same thing here.",
      fresh:"Fill in the blank in a brand-new sentence from the bank, rather than one of the card's own two.",
      cloze:"Fill in the blank — a real sentence with the word removed, distractors drawn from its own meaning cluster. Closest to the actual exam.",
      nuance:"A nuance from one of your group write-ups, with the word hidden. Pure discrimination between near-synonyms.",
      odd:"Four words from one cluster plus an intruder. Tests whether you've internalised the cluster.",
      strongest:"Pick the strongest word on an intensity scale.",
      connotation:"Positive, neutral or negative — the thing Sentence Equivalence turns on.",
      recall:"Produce the word from its definition. Hardest, and worth several passive reviews."};
    el.innerHTML = `<div class="q"><div class="setup">
      <h3>Quiz${scoped ? ": " + esc(scoped.title) : ""}</h3>
      ${scoped
        ? `<p class="hint">${scoped.words.length} words in this group — ${scoped.words.map(m=>esc(m.word)).join(" · ")}<br>
             <span class="chip" id="qall">quiz all ${CARDS.length} words instead</span></p>`
        : `<p class="hint">${dueCount()} of ${CARDS.length} words are due for review today.</p>`}
      <label style="${scoped?"opacity:.5":""}"><input type="checkbox" id="qdue" ${quizOnlyDue?"checked":""} ${scoped?"disabled":""}>
        <span><strong>Only ask what's due</strong><br><span class="hint">Spaced repetition. Uncheck to drill everything.</span></span></label>
      <hr class="sep">
      ${Object.keys(GEN).map(k=>`<label><input type="checkbox" class="qt" value="${k}" ${quizTypes.includes(k)?"checked":""}>
        <span><strong>${k}</strong><br><span class="hint">${labels[k]}</span></span></label>`).join("")}
      <hr class="sep">
      <details ${gemKey()?"":""}>
        <summary style="cursor:pointer;color:var(--dim);font-size:13px">
          Live question generation (optional) — ${gemKey()&&gemModel() ? "configured: "+esc(gemModel()) : "not set up"}
        </summary>
        <p class="hint" style="margin-top:10px">
          Adds a <strong>Fresh</strong> button that generates a brand-new question on the spot
          with Google Gemini. Free tier. Your key is stored only in this browser and sent only
          to Google — anyone using this device can read it, so use a restricted free-tier key.
          Live questions are <strong>not verified</strong>, unlike the ${BANK.length} in the bank.
        </p>
        <input id="gkey" placeholder="Gemini API key from aistudio.google.com"
               value="${esc(gemKey())}" style="width:100%;margin:6px 0">
        <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
          <button id="gcheck">Check key and list models</button>
          <select id="gmodel" style="min-width:220px"></select>
        </div>
        <p class="hint" id="gstatus"></p>
      </details>
      <div style="margin-top:18px"><button id="qstart" class="on">Start</button></div>
    </div></div>`;

    const gsel = $("gmodel"), gst = $("gstatus");
    const fillModels = list => {
      gsel.innerHTML = list.map(m => `<option ${m===gemModel()?"selected":""}>${esc(m)}</option>`).join("");
    };
    if(gemModel()) fillModels([gemModel()]);
    $("gcheck").onclick = async () => {
      const k = $("gkey").value.trim();
      if(!k){ gst.textContent = "Enter a key first."; return; }
      gst.textContent = "checking…";
      try{
        const models = await gemListModels(k);
        localStorage.setItem(GEM_KEY, k);
        fillModels(models);
        if(!models.includes(gemModel())) localStorage.setItem(GEM_MODEL, models[0] || "");
        gst.textContent = `Key works. ${models.length} usable models.`;
      }catch(e){ gst.textContent = "Failed: " + e.message; }
    };
    gsel.onchange = () => localStorage.setItem(GEM_MODEL, gsel.value);
    $("qstart").onclick = () => {
      quizTypes = [...document.querySelectorAll(".qt:checked")].map(x=>x.value);
      if(!quizTypes.length) quizTypes = ["cloze"];
      quizOnlyDue = $("qdue").checked;
      localStorage.setItem("gre-vocab-qtypes", JSON.stringify(quizTypes));
      localStorage.setItem("gre-vocab-qdue", JSON.stringify(quizOnlyDue));
      qStarted = true; qScore = {right:0,total:0}; nextQuestion(); renderQuiz();
    };
    if($("qall")) $("qall").onclick = () => go("/quiz");
    return;
  }
  if(!q){ el.innerHTML = `<div class="empty">Nothing due. Uncheck "only what's due" to keep drilling.</div>`; return; }

  const pct = qScore.total ? Math.round(qScore.right/qScore.total*100) : 0;
  let h = `<div class="q">
    <div class="qhead"><span class="qtype">${esc(q.label)}${quizGroup && groupById(quizGroup) ? " · " + esc(groupById(quizGroup).title) : ""}</span>
      <span class="score">${qScore.right}/${qScore.total}${qScore.total?` · ${pct}%`:""} · <span class="due">${dueCount()} due</span></span></div>
    <div class="qstem">${q.stem}</div>`;

  if(q.multi){
    h += q.blanks.map((b, bi) => `<div class="blankgrp"><h5>${esc(b.label)}</h5><div class="opts">` +
      b.options.map(o => {
        let cls = "";
        if(qAnswered){
          if(b.answers.some(a => a.toLowerCase() === o.toLowerCase()))
            cls = b.sel.some(x => x.toLowerCase() === o.toLowerCase()) ? "correct" : "missed";
          else if(b.sel.some(x => x.toLowerCase() === o.toLowerCase())) cls = "wrong";
        } else if(b.sel.some(x => x.toLowerCase() === o.toLowerCase())) cls = "picked";
        return `<button class="opt ${cls}" data-b="${bi}" data-o="${esc(o)}" ${qAnswered?"disabled":""}>${esc(o)}</button>`;
      }).join("") + `</div></div>`).join("");
    if(!qAnswered){
      const ready = q.blanks.every(b => b.sel.length === b.need);
      h += `<div class="qfoot"><span class="score">` +
           q.blanks.map(b => `${b.sel.length}/${b.need}`).join(" · ") +
           ` selected</span><button id="qcheck" class="on" ${ready?"":"disabled"}>Check</button></div>`;
    }
  } else if(q.typed){
    h += `<input id="typed" placeholder="type the word and press Enter" ${qAnswered?"disabled":""}
             value="${qAnswered?esc(q.chosen||""):""}">`;
  } else {
    h += `<div class="opts">` + q.options.map(o=>{
      let cls = "";
      if(qAnswered){
        if(String(o).toLowerCase()===String(q.answer).toLowerCase()) cls = "correct";
        else if(String(o)===String(q.chosen)) cls = "wrong";
      }
      const why = qAnswered && q.whyOpt ? `<span class="why">${esc(q.whyOpt(o)||"")}</span>` : "";
      return `<button class="opt ${cls}" data-o="${esc(String(o))}" ${qAnswered?"disabled":""}>${esc(String(o))}${why}</button>`;
    }).join("") + `</div>`;
  }

  if(qAnswered){
    const ansText = q.multi
      ? q.blanks.map(b => b.answers.join(" + ")).join("   ·   ")
      : String(q.answer);
    h += `<div class="verdict"><h4>${q.ok?"Correct":"Not quite — it was <em>"+esc(ansText)+"</em>"}</h4>${md(q.why)}
          ${q.live?`<p class="hint">Generated live and not verified — if you think your answer was defensible, it may well have been.</p>`:""}
          <div style="margin-top:8px"><span class="chip" data-w="${esc(q.card.word)}">open the full card for ${esc(q.card.word)}</span></div></div>
          <div class="qfoot"><span class="score">${q.ok?"scheduled further out":"back in the pile for tomorrow"}</span>
          <span>${gemKey()&&gemModel()?`<button id="qfresh">Fresh (live)</button> `:""}<button id="qnext" class="on">Next →</button></span></div>`;
  }
  h += `</div>`;
  el.innerHTML = h;

  if(q.multi){
    el.querySelectorAll(".blankgrp .opt").forEach(btn => btn.onclick = () => {
      const blank = q.blanks[+btn.dataset.b], o = btn.dataset.o;
      const i = blank.sel.findIndex(x => x.toLowerCase() === o.toLowerCase());
      if(i >= 0) blank.sel.splice(i, 1);
      else { if(blank.sel.length >= blank.need) blank.sel.shift(); blank.sel.push(o); }
      renderQuiz();
    });
    if($("qcheck")) $("qcheck").onclick = checkMulti;
  } else {
    el.querySelectorAll(".opt").forEach(b => b.onclick = () => answerQuestion(b.dataset.o));
  }
  const t = $("typed");
  if(t && !qAnswered){ t.focus(); t.onkeydown = e => { if(e.key==="Enter" && t.value.trim()) answerQuestion(t.value); }; }
  const nx = $("qnext");
  if(nx) nx.onclick = () => { nextQuestion(); renderQuiz(); };
  const fr = $("qfresh");
  if(fr) fr.onclick = async () => {
    fr.disabled = true; fr.textContent = "generating…";
    try{
      const pool = scopedCards() || filtered();
      const kind = pick(["tc2","se","cloze"]);
      q = await liveQuestion(pick(pool), kind);
      qAnswered = false; renderQuiz();
    }catch(e){
      fr.disabled = false; fr.textContent = "Fresh (live)";
      alert("Live generation failed: " + e.message);
    }
  };
  el.querySelectorAll(".verdict .chip").forEach(ch =>
    ch.onclick = () => go("/browse/" + encodeURIComponent(ch.dataset.w)));
}

function render(){
  if(mode === "browse") renderBrowse();
  else if(mode === "drill") renderDrill();
  else if(mode === "quiz") renderQuiz();
  else renderGroups();
  renderStats();
}

/* Clicking a group chip on a card jumps to that group. */
document.addEventListener("click", e => {
  const chip = e.target.closest(".chip");
  if(!chip) return;
  e.stopPropagation();
  go("/groups/" + encodeURIComponent(chip.dataset.gid));
});

/* ==========================================================================
   Routing
   --------------------------------------------------------------------------
   Without this the app is one history entry, so Back leaves the site entirely
   instead of stepping back through what you were reading. Every navigation
   pushes a hash route, and the last route is persisted so reopening the app
   returns you to where you were rather than to the top of the word list.

   Routes:  /browse  /browse/<word>  /drill  /quiz  /quiz/<groupId>
            /groups  /groups/<groupId>
   ========================================================================== */

const ROUTE_KEY = "gre-vocab-route";
const MODES = [["browse","mBrowse"],["drill","mDrill"],["quiz","mQuiz"],["groups","mGroups"]];

function currentRoute(){
  let r = "/" + mode;
  if(mode === "browse" && openWord)  r += "/" + encodeURIComponent(openWord);
  if(mode === "groups" && openGroup) r += "/" + encodeURIComponent(openGroup);
  if(mode === "quiz"   && quizGroup) r += "/" + encodeURIComponent(quizGroup);
  return r;
}

/* Apply a route to the UI. Does not touch history - callers decide that. */
function applyRoute(route){
  const bits = (route || "/browse").split("/");
  let m = bits[1] || "browse";
  const arg = bits[2] ? decodeURIComponent(bits[2]) : null;
  if(!MODES.some(([k]) => k === m)) m = "browse";

  const prevMode = mode, prevQuizGroup = quizGroup;
  mode = m;
  openWord  = m === "browse" ? arg : null;
  openGroup = m === "groups" ? arg : null;
  quizGroup = m === "quiz"   ? arg : null;

  MODES.forEach(([k, id]) => {
    $(id).classList.toggle("on", k === m);
    $(k).classList.toggle("hidden", k !== m);
  });
  if(m === "drill") revealed = false;
  // Re-show the quiz setup when entering the quiz fresh or switching scope, so
  // a group-scoped quiz doesn't silently continue the previous session.
  if(m === "quiz" && (prevMode !== "quiz" || prevQuizGroup !== quizGroup)) qStarted = false;

  localStorage.setItem(ROUTE_KEY, route);
  render();
  if(arg) setTimeout(() => {
    const sel = m === "browse" ? `#browse .row[data-w="${CSS.escape(arg)}"]`
                               : `#groups .grow[data-gid="${CSS.escape(arg)}"]`;
    document.querySelector(sel)?.scrollIntoView({block:"center"});
  }, 0);
}

function go(route, replace){
  if(!replace && location.hash.slice(1) === route){ applyRoute(route); return; }
  history[replace ? "replaceState" : "pushState"]({route}, "", "#" + route);
  applyRoute(route);
}

function setMode(m){ go("/" + m); }

window.addEventListener("popstate", () => applyRoute(location.hash.slice(1) || "/browse"));

/* ============================================================
   Appearance: theme + text scale. One CSS variable drives all sizing, so
   this is not browser zoom - the layout holds and only type grows.
   ============================================================ */
const THEMES = [["aqua","Aqua","#0d8fa8"],["midnight","Midnight","#8ab4ff"],
                ["forest","Forest","#68d19b"],["paper","Paper","#2f5fd0"],
                ["sepia","Sepia","#9a5b1e"]];
const PREF = "gre-vocab-prefs-v1";
let prefs = Object.assign({theme:"aqua", scale:1, voice:null, rate:1},
                          JSON.parse(localStorage.getItem(PREF) || "{}"));
const savePrefs = () => localStorage.setItem(PREF, JSON.stringify(prefs));

function applyTheme(t){
  prefs.theme = t; savePrefs();
  document.documentElement.dataset.theme = t;
  document.querySelectorAll(".sw").forEach(b => b.classList.toggle("on", b.dataset.t === t));
}
function applyScale(v){
  prefs.scale = Math.min(1.6, Math.max(.8, +v.toFixed(2))); savePrefs();
  document.documentElement.style.setProperty("--scale", prefs.scale);
  $("fpct").textContent = Math.round(prefs.scale * 100) + "%";
}

/* ============================================================
   Speech. The Web Speech API ignores SSML, so prosody has to come from how
   the text is CHOPPED rather than from markup:
     - the **bolded** target word is split out and spoken slower and higher,
       which is audibly stress, and it comes from the card data itself
     - real pauses between sections, by driving the queue ourselves
     - the best installed voice is ranked and chosen, not index 0
   ============================================================ */
const V = {voice:null, rate:1};
function rankVoice(v){
  return (/natural|neural|premium|enhanced/i.test(v.name) ? 8 : 0)
       + (/google/i.test(v.name) ? 4 : 0)
       + (/microsoft/i.test(v.name) ? 2 : 0)
       + (/^en-(GB|US)/i.test(v.lang) ? 1 : 0);
}
function loadVoices(){
  if(!window.speechSynthesis) return;
  const vs = speechSynthesis.getVoices().filter(v => /^en/i.test(v.lang));
  if(!vs.length) return;
  vs.sort((a,b) => rankVoice(b) - rankVoice(a));
  V.voice = vs.find(v => v.name === prefs.voice) || vs[0];
  const sel = $("vsel");
  if(sel){
    sel.innerHTML = vs.map(v => `<option${v.name===V.voice.name?" selected":""}>${esc(v.name)}</option>`).join("");
    sel.onchange = () => { V.voice = vs.find(v => v.name === sel.value); prefs.voice = sel.value; savePrefs(); };
  }
}
if(window.speechSynthesis) speechSynthesis.onvoiceschanged = loadVoices;

const speechText = t => (t||"")
  .replace(/\*\*(.+?)\*\*/g, "$1").replace(/\*(.+?)\*/g, "$1")
  .replace(/`([^`]+)`/g, "$1")
  .replace(/[←-⇿☀-➿\uD83C-􏰀-\uDFFF]/g, " ")
  .replace(/[—–]/g, ", ").replace(/\s+/g, " ").trim();

/* split at **bold** and stress those pieces */
function emphasised(md){
  return String(md||"").split(/(\*\*[^*]+\*\*)/g).filter(Boolean).map(part =>
    part.startsWith("**")
      ? {text: speechText(part), rate:.68, pitch:1.22, pause:110}
      : {text: speechText(part), rate:1, pitch:1, pause:0}
  ).filter(x => x.text);
}

let sQueue = [], sIdx = 0, sPlaying = false;
function stopSpeech(){
  sPlaying = false;
  if(window.speechSynthesis) speechSynthesis.cancel();
  document.querySelectorAll(".speak.on").forEach(b => b.classList.remove("on"));
}
function sStep(){
  if(!sPlaying || sIdx >= sQueue.length){ stopSpeech(); return; }
  const seg = sQueue[sIdx];
  const u = new SpeechSynthesisUtterance(seg.text);
  if(V.voice) u.voice = V.voice;
  u.rate = Math.min(2, (seg.rate === undefined ? 1 : seg.rate) * V.rate);
  u.pitch = seg.pitch === undefined ? 1 : seg.pitch;
  const gap = (seg.pause === undefined ? 120 : seg.pause) / V.rate;
  u.onend = () => { sIdx++; setTimeout(sStep, gap); };
  u.onerror = () => { sIdx++; setTimeout(sStep, 60); };
  speechSynthesis.speak(u);
}
function speak(segs){
  if(!window.speechSynthesis){ alert("This browser has no speech support."); return; }
  stopSpeech(); sQueue = segs.filter(x => x && x.text); sIdx = 0; sPlaying = true; sStep();
}

/* the whole card, in reading order */
function cardSegments(c){
  const seg = [{text:c.word, rate:.72, pitch:1.05, pause:520},
               {text:speechText(c.pos||""), rate:.95, pause:400}];
  const section = (label, md) => {
    if(!md) return;
    seg.push({text:label, rate:.9, pitch:.92, pause:260});
    seg.push(...emphasised(md));
    seg.push({text:" ", pause:480});
  };
  section("Means.", c.means);
  if(c.trap) section("Careful.", c.trap);
  if(c.trick_line) section("A trick to lock it in.", c.trick_line + ". " + (c.trick_unpack||""));
  if(c.sentences && c.sentences.length){
    seg.push({text:"In sentences.", rate:.9, pitch:.92, pause:300});
    c.sentences.forEach(x => { seg.push(...emphasised(x)); seg.push({text:" ", pause:420}); });
  }
  if(c.in_the_wild) section("In the wild.", c.in_the_wild);
  if(c.etymology) section("Where it comes from.", c.etymology);
  return seg;
}

/* ============================================================
   Accounts and sync.

   Two modes, deliberately: Guest keeps everything in localStorage and needs no
   network at all, and signing in with Google syncs progress to a hidden folder
   in the user's OWN Drive.

   The appDataFolder scope is the narrow one - it can only see files this app
   created, never the user's actual Drive contents. Nothing is stored on any
   server we run, because there isn't one. That is what lets accounts exist
   without breaking the zero-backend architecture.

   The client id is public by design; OAuth web client ids ship in client code
   and are not secrets. There is no client secret here and there must not be.
   ============================================================ */
const GOOGLE_CLIENT_ID =
  "482453347232-uggskn8e9eeuaamsephh7t108nherqo7.apps.googleusercontent.com";
const DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.appdata";
const SYNC_FILE = "gre-vocab-progress.json";

const AUTH = {token:null, expires:0, profile:null, fileId:null, status:"guest", last:null};
let tokenClient = null;

function authed(){ return AUTH.token && Date.now() < AUTH.expires; }

function gsiReady(){ return typeof google !== "undefined" && google.accounts && google.accounts.oauth2; }

function signIn(){
  if(!gsiReady()){ alert("Google sign-in library did not load. Check your connection."); return; }
  if(!tokenClient){
    tokenClient = google.accounts.oauth2.initTokenClient({
      client_id: GOOGLE_CLIENT_ID,
      scope: "openid email profile " + DRIVE_SCOPE,
      callback: async resp => {
        if(resp.error){ AUTH.status = "guest"; renderAccount(); return; }
        AUTH.token = resp.access_token;
        AUTH.expires = Date.now() + (resp.expires_in ? resp.expires_in * 1000 : 3500000);
        AUTH.status = "syncing"; renderAccount();
        try{
          AUTH.profile = await gFetch("https://www.googleapis.com/oauth2/v3/userinfo");
          await syncNow();
          AUTH.status = "on";
        }catch(e){ AUTH.status = "error"; AUTH.last = e.message; }
        renderAccount(); render();
      },
    });
  }
  tokenClient.requestAccessToken({prompt: AUTH.profile ? "" : "consent"});
}

function signOut(){
  if(AUTH.token && gsiReady()) google.accounts.oauth2.revoke(AUTH.token, () => {});
  Object.assign(AUTH, {token:null, expires:0, profile:null, fileId:null, status:"guest", last:null});
  renderAccount();
}

async function gFetch(url, opts){
  const r = await fetch(url, Object.assign({}, opts, {
    headers: Object.assign({Authorization: "Bearer " + AUTH.token}, (opts||{}).headers)}));
  if(!r.ok) throw new Error((await r.text()).slice(0, 160) || ("HTTP " + r.status));
  return r.status === 204 ? null : r.json();
}

async function findFile(){
  if(AUTH.fileId) return AUTH.fileId;
  const q = encodeURIComponent("name='" + SYNC_FILE + "'");
  const j = await gFetch("https://www.googleapis.com/drive/v3/files?spaces=appDataFolder&q=" + q + "&fields=files(id)");
  AUTH.fileId = (j.files && j.files[0] && j.files[0].id) || null;
  return AUTH.fileId;
}

/* Per-key merge, not last-writer-wins on the whole blob: two devices used on
   the same day would otherwise silently discard one of them. */
function mergeProgress(remote){
  const rM = (remote && remote.marks) || {}, rS = (remote && remote.srs) || {};
  Object.keys(rM).forEach(w => { if(!marks[w]) marks[w] = rM[w]; });
  Object.keys(rS).forEach(w => {
    const a = srs[w], b = rS[w];
    if(!a || (b.seen || 0) > (a.seen || 0)) srs[w] = b;
  });
  const rSeen = (remote && remote.seenq) || [];
  rSeen.forEach(id => seenQ.add(id));
  save(); saveSrs();
  localStorage.setItem(SEEN_KEY, JSON.stringify([...seenQ]));
}

async function syncNow(){
  const id = await findFile();
  if(id){
    try{
      const r = await fetch("https://www.googleapis.com/drive/v3/files/" + id + "?alt=media",
        {headers:{Authorization: "Bearer " + AUTH.token}});
      if(r.ok) mergeProgress(await r.json());
    }catch(e){ /* a corrupt remote must not block writing a good local copy */ }
  }
  const body = JSON.stringify({marks, srs, seenq:[...seenQ], updatedAt: Date.now(), v:1});
  const meta = {name: SYNC_FILE, mimeType: "application/json"};
  if(!id) meta.parents = ["appDataFolder"];
  const boundary = "gvb" + Math.random().toString(36).slice(2);
  const multipart =
    "--" + boundary + "\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n" +
    JSON.stringify(meta) +
    "\r\n--" + boundary + "\r\nContent-Type: application/json\r\n\r\n" + body +
    "\r\n--" + boundary + "--";
  const url = id
    ? "https://www.googleapis.com/upload/drive/v3/files/" + id + "?uploadType=multipart"
    : "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart";
  const j = await gFetch(url, {method: id ? "PATCH" : "POST", body: multipart,
    headers: {"Content-Type": "multipart/related; boundary=" + boundary}});
  if(j && j.id) AUTH.fileId = j.id;
  AUTH.last = new Date().toLocaleTimeString();
}

/* Progress changes constantly while drilling; push on a trailing debounce. */
let syncTimer = null;
function queueSync(){
  if(!authed()) return;
  clearTimeout(syncTimer);
  syncTimer = setTimeout(() => {
    AUTH.status = "syncing"; renderAccount();
    syncNow().then(() => { AUTH.status = "on"; })
             .catch(e => { AUTH.status = "error"; AUTH.last = e.message; })
             .finally(renderAccount);
  }, 4000);
}

function renderAccount(){
  const box = $("acctBox");
  if(!box) return;
  const p = AUTH.profile;
  if(authed() && p){
    const label = {on:"Synced to your Google Drive", syncing:"Syncing...",
                   error:"Sync failed: " + (AUTH.last||"")}[AUTH.status] || "Signed in";
    box.innerHTML = `<div class="acct">
        <div class="avatar">${esc((p.name||p.email||"?")[0].toUpperCase())}</div>
        <div style="flex:1">
          <div style="font-weight:600">${esc(p.name || p.email || "Signed in")}</div>
          <div class="hint"><span class="dot" style="background:var(--${AUTH.status==="error"?"hard":"easy"})"></span>${esc(label)}${AUTH.last&&AUTH.status==="on"?" &middot; "+esc(AUTH.last):""}</div>
        </div>
        <button class="btn" id="soBtn">Sign out</button>
      </div>
      <button class="btn" id="syncBtn" style="width:100%">Sync now</button>`;
    $("soBtn").onclick = signOut;
    $("syncBtn").onclick = () => { AUTH.status="syncing"; renderAccount();
      syncNow().then(()=>{AUTH.status="on";}).catch(e=>{AUTH.status="error";AUTH.last=e.message;})
               .finally(()=>{renderAccount(); render();}); };
  } else {
    box.innerHTML = `<div class="acct">
        <div class="avatar" style="background:var(--panel2);color:var(--dim)">?</div>
        <div style="flex:1">
          <div style="font-weight:600">Guest</div>
          <div class="hint">Progress saved on this device only</div>
        </div>
      </div>
      <button class="btn primary" id="siBtn" style="width:100%">Sign in with Google</button>
      <p class="hint" style="margin-bottom:0">Syncs your marks and review schedule to a hidden
        folder in your own Google Drive. The app can only see files it created there, never the
        rest of your Drive.</p>`;
    $("siBtn").onclick = signIn;
  }
}

/* ---- wiring ---- */
const groups = [...new Set(CARDS.flatMap(c=>c.groups||[]))].sort((a,b)=>a-b);
$("group").innerHTML = `<option value="">all groups</option>` +
  groups.map(g=>`<option value="${g}">group ${g}</option>`).join("");

["search","group","diff"].forEach(id =>
  $(id).addEventListener("input", () => { idx=0; revealed=false; render(); }));

applyTheme(prefs.theme);
applyScale(prefs.scale);
V.rate = prefs.rate || 1;
loadVoices();

$("fup").onclick   = () => applyScale(prefs.scale + .1);
$("fdown").onclick = () => applyScale(prefs.scale - .1);

$("swatches").innerHTML = THEMES.map(([id,label,col]) =>
  `<button class="sw" data-t="${id}"><i style="background:${col}"></i>${label}</button>`).join("");
document.querySelectorAll(".sw").forEach(b => b.onclick = () => applyTheme(b.dataset.t));
applyTheme(prefs.theme);

$("openSettings").onclick = () => { $("sheet").classList.remove("hidden"); renderAccount(); loadVoices(); };
renderAccount();
$("closeSettings").onclick = () => $("sheet").classList.add("hidden");
$("sheet").onclick = e => { if(e.target.id === "sheet") $("sheet").classList.add("hidden"); };
if($("rate")){
  $("rate").value = V.rate;
  $("rateOut").textContent = V.rate.toFixed(2) + "x";
  $("rate").oninput = e => { V.rate = +e.target.value; prefs.rate = V.rate; savePrefs();
    $("rateOut").textContent = V.rate.toFixed(2) + "x"; };
}

/* any element carrying data-speak reads that word's whole card */
document.addEventListener("click", e => {
  const b = e.target.closest("[data-speak]");
  if(!b) return;
  e.stopPropagation();
  if(sPlaying){ stopSpeech(); return; }
  const c = CARDS.find(x => x.word.toLowerCase() === b.dataset.speak.toLowerCase());
  if(!c) return;
  b.classList.add("on");
  speak(cardSegments(c));
});

$("mBrowse").onclick = () => setMode("browse");
$("mDrill").onclick  = () => setMode("drill");
$("mQuiz").onclick   = () => setMode("quiz");
$("mGroups").onclick = () => setMode("groups");

$("shuffle").onclick = () => {
  order = filtered().map(c=>c.word);
  for(let i=order.length-1;i>0;i--){ const j=Math.floor(Math.random()*(i+1)); [order[i],order[j]]=[order[j],order[i]]; }
  idx=0; revealed=false; render();
};

$("exp").onclick = () => {
  const text = JSON.stringify({marks, srs},null,2);
  // Inside the Android WebView wrapper a blob download silently does nothing,
  // so hand the text to the native side instead when the bridge is present.
  if(window.AndroidBridge && AndroidBridge.saveText){
    AndroidBridge.saveText("difficulty.json", text);
    return;
  }
  const blob = new Blob([text],{type:"application/json"});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob); a.download = "difficulty.json"; a.click();
};
$("imp").onclick = () => $("file").click();
$("file").onchange = e => {
  const f = e.target.files[0]; if(!f) return;
  f.text().then(t => {
    const d = JSON.parse(t);
    // Accept both the new {marks,srs} envelope and the original bare marks map.
    if(d && (d.marks || d.srs)){ marks = {...marks, ...(d.marks||{})}; srs = {...srs, ...(d.srs||{})}; }
    else marks = {...marks, ...d};
    save(); saveSrs(); render();
  });
};

/* Restore where you were: URL hash wins, else the last route from last time. */
go(location.hash.slice(1) || localStorage.getItem(ROUTE_KEY) || "/browse", true);

document.addEventListener("keydown", e => {
  if(mode!=="drill" || /input|select/i.test(e.target.tagName)) return;
  if(e.key===" "){ e.preventDefault(); revealed=true; renderDrill(); }
  if(e.key==="1") document.querySelector(".mk-hard")?.click();
  if(e.key==="2") document.querySelector(".mk-medium")?.click();
  if(e.key==="3") document.querySelector(".mk-easy")?.click();
  if(e.key==="ArrowRight") $("next")?.click();
  if(e.key==="ArrowLeft")  $("prev")?.click();
});

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

    # Pre-generated, independently verified exam-format questions.
    bank = []
    for f in sorted(BANK.glob("*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        for q in d.get("questions", []):
            bank.append({k: q[k] for k in
                         ("id", "type", "stem", "blanks", "words", "explanation")
                         if k in q} | {"g": q.get("gregmat_group")})

    OUT.mkdir(exist_ok=True)
    html = (TEMPLATE
            .replace("__DATA__", json.dumps(data, ensure_ascii=False))
            .replace("__GROUPS__", json.dumps(groups, ensure_ascii=False))
            .replace("__BANK__", json.dumps(bank, ensure_ascii=False))
            .replace("__KINDLABEL__", json.dumps(KIND_LABEL, ensure_ascii=False)))
    dest = OUT / "flashcards.html"
    dest.write_text(html, encoding="utf-8")

    print(f"{len(data)} cards + {len(groups)} groups + {len(bank)} bank questions "
          f"-> {dest}  ({dest.stat().st_size/1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
