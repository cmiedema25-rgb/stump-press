let challenges = [];
let current = null;

const BACKREF = /\b(that|those|the same|said|aforementioned|above|this|their|its|which|who|where|there|hall|society|church|club|notice|named|using)\b/i;

function tokens(s) {
  return new Set((s.match(/[A-Za-z][A-Za-z']{2,}/g) || []).map((t) => t.toLowerCase()));
}

function chainWarnings(c1, c2, c3) {
  const warns = [];
  if (!c1 || !c2 || !c3) return warns;
  const stop = new Set(["the","and","for","that","with","from","this","find","read","note","locate","using","only","page","clue","answer","identify"]);
  const sig1 = [...tokens(c1)].filter((t) => !stop.has(t));
  const t2 = tokens(c2);
  const t3 = tokens(c3);
  const c2ok = BACKREF.test(c2) || sig1.some((t) => t2.has(t));
  const c3ok = BACKREF.test(c3) || sig1.some((t) => t3.has(t)) || [...t2].some((t) => !stop.has(t) && t3.has(t));
  if (!c2ok) warns.push("Clue 2 looks independent of Clue 1 — it should use entity A from Clue 1.");
  if (!c3ok) warns.push("Clue 3 looks independent of prior clues — it should use entity B from Clue 2.");
  return warns;
}

function liveWarn() {
  const form = document.getElementById("form");
  const el = document.getElementById("chain-warn");
  if (!form || !el) return;
  const w = chainWarnings(form.c1.value.trim(), form.c2.value.trim(), form.c3.value.trim());
  if (w.length) {
    el.textContent = w.join(" ");
    el.classList.remove("hidden");
  } else {
    el.textContent = "";
    el.classList.add("hidden");
  }
}

async function load() {
  const res = await fetch("challenges.json");
  const data = await res.json();
  challenges = data.challenges || [];
  renderList();
}

function renderList() {
  const root = document.getElementById("list");
  root.innerHTML = "";
  if (!challenges.length) {
    root.innerHTML = "<p class='small'>No cards yet. Run <code>stump pack</code> or <code>stump hunt</code>.</p>";
    return;
  }
  for (const c of challenges) {
    const btn = document.createElement("button");
    btn.className = "card" + (current && current.id === c.id ? " active" : "");
    const score = (c.ocr_score ?? c.score ?? 0).toFixed(2);
    const hits = (c.local_crumb_hits || []).slice(0, 3).join(", ");
    btn.innerHTML = `
      <div><span class="score">${score}</span> · ${escapeHtml(c.date || "?")}</div>
      <div>${escapeHtml((c.title || c.id || "").slice(0, 72))}</div>
      <div class="small">${escapeHtml(hits || c.crumb_type || "local crumb")}</div>`;
    btn.onclick = () => select(c.id);
    root.appendChild(btn);
  }
}

function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function cluesOf(c) {
  if (Array.isArray(c.chaining_clues) && c.chaining_clues.length) {
    return [0, 1, 2].map((i) => {
      const x = c.chaining_clues[i];
      if (!x) return "";
      if (typeof x === "string") return x;
      return x.clue || x.text || "";
    });
  }
  const hops = Array.isArray(c.hops) ? c.hops : [];
  return [0, 1, 2].map((i) => {
    const h = hops[i];
    if (!h) return "";
    if (typeof h === "string") return h;
    return h.clue || h.text || "";
  });
}

function select(id) {
  current = challenges.find((c) => c.id === id) || null;
  renderList();
  const empty = document.getElementById("empty");
  const editor = document.getElementById("editor");
  if (!current) {
    empty.classList.remove("hidden");
    editor.classList.add("hidden");
    return;
  }
  empty.classList.add("hidden");
  editor.classList.remove("hidden");
  document.getElementById("title").textContent = current.title || current.id;
  document.getElementById("meta-line").textContent =
    `${current.date || ""} · ${current.lccn || ""} · id ${current.id}`;
  const link = document.getElementById("page-link");
  link.href = current.page_url || current.image_url || "#";
  link.textContent = "Open page image / LOC resource";
  const hits = (current.local_crumb_hits || []).join(", ");
  document.getElementById("crumb-hits").textContent = hits ? `local: ${hits}` : "";
  document.getElementById("ocr").textContent = current.ocr_excerpt || "(no OCR excerpt)";
  const score = current.ocr_score ?? current.score;
  const reasons = (current.ocr_reasons || current.reasons || []).join(", ");
  document.getElementById("score-line").textContent =
    `OCR junk score: ${score ?? "?"} · ${reasons}`;

  const form = document.getElementById("form");
  form.crumb_type.value = current.crumb_type || "local_notice";
  form.question.value = current.question || "";
  const [c1, c2, c3] = cluesOf(current);
  form.c1.value = c1;
  form.c2.value = c2;
  form.c3.value = c3;
  form.answer.value = current.answer || "";
  form.why_stumps_text_model.value =
    current.why_stumps_text_model || current.why_model_fails || "";
  document.getElementById("save-status").textContent = "";
  liveWarn();
}

document.getElementById("form").addEventListener("input", liveWarn);

document.getElementById("form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  if (!current) return;
  const form = ev.target;
  const chaining_clues = [
    form.c1.value.trim(),
    form.c2.value.trim(),
    form.c3.value.trim(),
  ];
  const localWarns = chainWarnings(...chaining_clues);
  const payload = {
    ...current,
    crumb_type: form.crumb_type.value,
    question: form.question.value.trim(),
    chaining_clues,
    hops: chaining_clues.map((clue, i) => ({ step: i + 1, clue })),
    answer: form.answer.value.trim(),
    why_stumps_text_model: form.why_stumps_text_model.value.trim(),
    why_model_fails: form.why_stumps_text_model.value.trim(),
  };
  if (location.protocol === "file:" || location.hostname.endsWith("github.io")) {
    alert("Static Chrome demo: saving is disabled on GitHub Pages. Run make serve locally to save.");
    return;
  }
  const res = await fetch("/api/challenges", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json();
  const status = document.getElementById("save-status");
  if (data.ok) {
    const gaps = data.incomplete || [];
    const chainGaps = gaps.filter((g) => /chain|independent|clue/i.test(g));
    const other = gaps.filter((g) => !chainGaps.includes(g));
    let msg = `Saved ${data.path}`;
    if (localWarns.length || chainGaps.length) {
      msg += " — ⚠ chain dependency warning: " + (localWarns.concat(chainGaps).join("; "));
    } else if (other.length) {
      msg += ` (draft gaps: ${other.join("; ")})`;
    } else {
      msg += " — chaining card complete";
    }
    status.textContent = msg;
    const idx = challenges.findIndex((c) => c.id === payload.id);
    if (idx >= 0) challenges[idx] = data.challenge;
    else challenges.unshift(data.challenge);
    current = data.challenge;
    renderList();
  } else {
    status.textContent = data.error || "Save failed";
  }
});

load();
