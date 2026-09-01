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

/* ---- quiz ---- */
.q{max-width:660px;margin:0 auto}
.qhead{display:flex;justify-content:space-between;align-items:baseline;
  color:var(--dim);font-size:13px;margin-bottom:12px}
.qtype{color:var(--accent);text-transform:uppercase;letter-spacing:1.1px;font-size:11px;font-weight:650}
.qstem{background:var(--panel);border:1px solid var(--line);border-radius:12px;
  padding:22px 24px;font-size:17px;line-height:1.7}
.qstem .blank{color:var(--accent);font-weight:700;letter-spacing:1px}
.opts{display:flex;flex-direction:column;gap:8px;margin-top:16px}
.opt{text-align:left;padding:12px 16px;font-size:15px;border-radius:9px;
  background:var(--panel);border:1px solid var(--line);color:var(--ink);cursor:pointer}
.opt:hover:not(:disabled){border-color:var(--accent)}
.opt:disabled{cursor:default}
.opt.correct{border-color:var(--easy);background:rgba(95,191,127,.12)}
.opt.wrong{border-color:var(--hard);background:rgba(224,106,106,.12)}
.opt .why{display:block;color:var(--dim);font-size:13px;margin-top:5px;line-height:1.5}
#typed{width:100%;padding:12px 16px;font-size:17px;margin-top:16px}
.verdict{margin-top:16px;padding:14px 18px;border-radius:10px;background:var(--panel2);
  border-left:3px solid var(--accent)}
.verdict h4{margin:0 0 6px;font-size:14px}
.qfoot{display:flex;justify-content:space-between;align-items:center;margin-top:18px}
.score{color:var(--dim);font-size:13px}
.due{color:var(--accent);font-weight:600}
.setup{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:22px 24px}
.setup h3{margin-top:0}
.setup label{display:flex;gap:9px;align-items:flex-start;margin:9px 0;cursor:pointer}
.setup input[type=checkbox]{margin-top:4px;accent-color:var(--accent)}
.setup .hint{color:var(--dim);font-size:13px}
.blankgrp{margin-top:16px}
.blankgrp h5{margin:0 0 7px;font-size:11px;letter-spacing:1.1px;
  text-transform:uppercase;color:var(--accent);font-weight:650}
.blankgrp .opts{margin-top:0}
.opt.picked{border-color:var(--accent);background:rgba(122,162,247,.12)}
.opt.missed{border-color:var(--easy);border-style:dashed}

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
  <button id="mQuiz">Quiz</button>
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
  <div id="quiz" class="hidden"></div>
  <div id="groups" class="hidden"></div>
</main>

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
const saveSrs = () => localStorage.setItem(SRS_KEY, JSON.stringify(srs));
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

/* ---- wiring ---- */
const groups = [...new Set(CARDS.flatMap(c=>c.groups||[]))].sort((a,b)=>a-b);
$("group").innerHTML = `<option value="">all groups</option>` +
  groups.map(g=>`<option value="${g}">group ${g}</option>`).join("");

["search","group","diff"].forEach(id =>
  $(id).addEventListener("input", () => { idx=0; revealed=false; render(); }));

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
