/* eralyzer — main runtime */

(function () {
  "use strict";

  const $ = (id) => document.getElementById(id);

  /* ---------- state ---------- */
  const state = {
    fusion:  "late",
    running: false,
  };

  /* ---------- demo dropdown ---------- */
  const demoSelect = $("demo-select");
  DEMOS.forEach((d) => {
    const era = ERAS.find((e) => e.id === d.era);
    const opt = document.createElement("option");
    opt.value = d.title;
    opt.textContent = `${era ? era.label : d.era} — ${d.title}`;
    demoSelect.appendChild(opt);
  });

  // Selecting a demo fills the text input (dropdown = convenience shortcut only)
  demoSelect.addEventListener("change", (e) => {
    const v = e.target.value;
    if (v) $("song-input").value = v;
  });

  /* ---------- fusion toggle ---------- */
  document.querySelectorAll(".fusion-opt").forEach((b) => {
    b.addEventListener("click", () => {
      if (state.running) return; // Prevent switching while a debate is running

      document.querySelectorAll(".fusion-opt").forEach((x) => x.classList.remove("is-active"));
      b.classList.add("is-active");
      state.fusion = b.dataset.fusion;
      
      // FIX 1: Clear the screen and reset stats so old text doesn't linger!
      clearCli();
      $("verdict").hidden = true;
      resetStats("—");
      
      // UI TRANSFORMATION LOGIC
      const audioBox = $("cli-audio");
      const divider = document.querySelector(".debate-divider");
      const lyricBox = $("cli-lyric");
      const lyricHeader = lyricBox.querySelector(".cli-tag-lyric");
      const lyricMeta = lyricBox.querySelector(".cli-meta");
      const lyricModel = lyricBox.querySelector(".cli-foot-val");

      if (state.fusion === "early") {
        audioBox.style.display = "none";
        divider.style.display = "none";
        lyricBox.style.gridColumn = "1 / -1"; 
        lyricBox.style.width = "100%";
        lyricHeader.textContent = "● EARLY FUSION MODEL";
        lyricHeader.style.color = "var(--ink)";
        lyricMeta.textContent = "";
        lyricModel.textContent = "fusion-xgb-v1.0";
      } else {
        audioBox.style.display = "";
        divider.style.display = "";
        lyricBox.style.gridColumn = "";
        lyricBox.style.width = "";
        lyricHeader.textContent = "● LYRIC AGENT";
        lyricHeader.style.color = "";
        lyricMeta.textContent = "";
        lyricModel.textContent = "lyric-bert-v2.4";
      }
    });
  });

  /* ---------- run triggers ---------- */
  $("run-btn").addEventListener("click", run);
  $("song-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter") run();
  });

  /* ---------- helpers ---------- */
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  function formatLine(text) {
    return text
      .replace(/<num>(.*?)<\/num>/g, '<span class="num">$1</span>')
      .replace(/<emp>(.*?)<\/emp>/g, '<span class="emp" style="color:var(--ink);font-weight:600">$1</span>')
      .replace(/<neg>(.*?)<\/neg>/g, '<span class="neg">$1</span>');
  }

  function clearCli() {
    $("cli-audio-body").innerHTML = "";
    $("cli-lyric-body").innerHTML = "";
  }

  function setCursor(panel, show) {
    const body = $(panel === "audio" ? "cli-audio-body" : "cli-lyric-body");
    const existing = body.querySelector(".cli-cursor");
    if (existing) existing.remove();
    if (show) {
      const c = document.createElement("span");
      c.className = "cli-cursor";
      c.textContent = "▌";
      const lastLine = body.lastElementChild;
      if (lastLine && lastLine.classList.contains("cli-line")) {
        lastLine.appendChild(c);
      } else {
        body.appendChild(c);
      }
    }
  }

  function setPillBusy(panel, busy) {
    const pill   = $(`pill-${panel}`);
    const pstate = $(`pill-${panel}-state`);
    if (busy) {
      pill.classList.add("is-busy");
      pstate.textContent = "processing";
    } else {
      pill.classList.remove("is-busy");
      pstate.textContent = "idle";
    }
  }

  function appendLine(panel, text, cls) {
    const body = $(panel === "audio" ? "cli-audio-body" : "cli-lyric-body");
    const existing = body.querySelector(".cli-cursor");
    if (existing) existing.remove();
    
    const line = document.createElement("span");
    line.className = "cli-line" + (cls ? " " + cls : "");
    
    // FIX 2: Change the prefix based on the fusion mode
    let pfx = "";
    if (panel === "audio") {
      pfx = '<span class="prefix pfx-audio">[AUDIO]</span> ';
    } else {
      if (state.fusion === "early") {
        pfx = '<span class="prefix pfx-lyric" style="color:var(--ink)">[FUSION]</span> ';
      } else {
        pfx = '<span class="prefix pfx-lyric">[LYRIC]</span> ';
      }
    }
    
    line.innerHTML = pfx + formatLine(text);
    body.appendChild(line);
    body.scrollTop = body.scrollHeight;
  }

  function appendDivider(text) {
    ["audio", "lyric"].forEach((p) => {
      const body = $(p === "audio" ? "cli-audio-body" : "cli-lyric-body");
      const existing = body.querySelector(".cli-cursor");
      if (existing) existing.remove();
      const d = document.createElement("span");
      d.className = "cli-line is-divider";
      d.textContent = text;
      body.appendChild(d);
    });
  }

  function appendError(panel, text) {
    const body = $(panel === "audio" ? "cli-audio-body" : "cli-lyric-body");
    const line = document.createElement("span");
    line.className = "cli-line is-error";
    line.style.cssText = "color:var(--era-red);font-weight:600;";
    line.textContent = text;
    body.appendChild(line);
  }

  /* ---------- stats ---------- */
  function setStat(which, frac) {
    $(`stat-${which}-pct`).textContent = Math.round(frac * 100) + "%";
    $(`stat-${which}-bar`).style.width  = (frac * 100) + "%";
  }
  function resetStats(totalRounds) {
    setStat("audio", 0);
    setStat("lyric", 0);
    $("stat-round").innerHTML      = `0`;
    $("stat-audio-pct").textContent = "—";
    $("stat-lyric-pct").textContent = "—";
    $("stat-audio-bar").style.width = "0%";
    $("stat-lyric-bar").style.width = "0%";
  }
  function setRound(n) {
    $("stat-round").innerHTML = `${n}`;
  }

  /* ---------- verdict ---------- */
  function showVerdict(demo) {
    const eraId = (demo.era || "").toLowerCase();
    const era   = ERAS.find((e) => e.id === demo.era)
               || ERAS.find((e) => e.id === eraId)
               || ERAS.find((e) => e.label.toLowerCase() === eraId)
               || { label: demo.era, color: "#9b9788" };
    const card = $("verdict");
    card.hidden = false;
    card.style.setProperty("--verdict-accent", era.color);
    $("verdict-era").textContent  = era.label;
    $("verdict-era").style.color  = era.color;
    $("verdict-conf").textContent = Math.round(demo.stacking * 100) + "%";
    $("verdict-reason").textContent = demo.reason;
    const badge = $("verdict-badge");
    if (demo.badge === "consensus") {
      badge.textContent = "CONSENSUS";
      badge.className   = "verdict-badge is-consensus";
    } else if (demo.badge === "joint-inference") {
      // FIX: Add support for our Early Fusion badge
      badge.textContent = "JOINT INFERENCE";
      badge.className   = "verdict-badge is-consensus"; // Reusing the green 'consensus' styling
    } else {
      badge.textContent = "ADJUDICATED";
      badge.className   = "verdict-badge is-adjudicated";
    }
    $("vb-audio").textContent   = demo.audioFinal;
    $("vb-lyric").textContent   = demo.lyricFinal;
    $("vb-rounds").textContent  = demo.rounds;
    $("vb-runtime").textContent = demo.runtime.toFixed(2) + "s";
    $("last-ts").textContent    = new Date().toLocaleTimeString([], {
      hour: "2-digit", minute: "2-digit", second: "2-digit",
    });
  }

  /* ---------- loading state ---------- */
  function showLoading(songTitle) {
    clearCli();
    appendLine("lyric", `> Looking up "${songTitle}" in dataset…`);
    appendLine("audio", "> Standing by…");
    setCursor("lyric", true);
    setCursor("audio", true);
  }

  /* ---------- script playback (same typewriter engine as before) ---------- */
  async function playScript(demo) {
    const finalAudio = demo.audioConf;
    const finalLyric = demo.lyricConf;
    const audioTotal = demo.script.filter((s) => s.who === "audio").length || 1;
    const lyricTotal = demo.script.filter((s) => s.who === "lyric").length || 1;
    let audioLines = 0, lyricLines = 0;
    let prevWho    = null;
    let currentRound = 1;

    setRound(currentRound);

    for (let i = 0; i < demo.script.length; i++) {
      const step = demo.script[i];

      if (step.who === "sys") {
        setCursor("audio", false);
        setCursor("lyric", false);
        await sleep(250);
        appendDivider(step.text);
        
        // FIX: Only increment rounds if we are in Late Fusion!
        if (state.fusion !== "early" && step.text.includes("ROUND")) {
            currentRound++;
            setRound(currentRound);
        }
        
        await sleep(250);
        prevWho = null;
        continue;
      }

      await sleep(prevWho && prevWho !== step.who ? 350 : 160);

      setCursor(step.who, true);
      await sleep(100);
      appendLine(step.who, step.text, step.cls || "");

      if (step.who === "audio") {
        audioLines++;
        setStat("audio", finalAudio * (0.25 + 0.75 * (audioLines / audioTotal)));
      } else {
        lyricLines++;
        setStat("lyric", finalLyric * (0.25 + 0.75 * (lyricLines / lyricTotal)));
      }

      setCursor(step.who, true);
      prevWho = step.who;
    }

    setStat("audio", finalAudio);
    setStat("lyric", finalLyric);
    setCursor("audio", false);
    setCursor("lyric", false);
    await sleep(300);
  }

  /* ---------- main run ---------- */
  async function run() {
    if (state.running) return;

    const songTitle = $("song-input").value.trim();
    if (!songTitle) {
      $("song-input").focus();
      return;
    }

    state.running = true;
    $("run-btn").disabled = true;
    $("run-btn").querySelector(".run-btn-label").textContent = "Analysing…";
    $("verdict").hidden = true;
    resetStats("—");
    setPillBusy("audio", true);
    setPillBusy("lyric", true);

    showLoading(songTitle);

    // DEBATE_API_BASE is injected by eralyzer.py when served via Streamlit.
    // When served directly by FastAPI it is undefined and we use a relative URL.
    const apiBase = (typeof DEBATE_API_BASE !== "undefined") ? DEBATE_API_BASE : "";

    let demo;
    try {
      const res = await fetch(apiBase + "/debate", {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ song_title: songTitle, artist: "Taylor Swift", fusion: state.fusion }),
      });

      const data = await res.json();

      if (!res.ok) {
        clearCli();
        appendError("lyric", `> Error: ${data.error || res.statusText}`);
        appendError("audio", "> Debate aborted.");
        setPillBusy("audio", false);
        setPillBusy("lyric", false);
        state.running = false;
        $("run-btn").disabled = false;
        $("run-btn").querySelector(".run-btn-label").textContent = "Run Debate";
        return;
      }

      demo = data;
    } catch (err) {
      clearCli();
      appendError("lyric", `> Network error: ${err.message}`);
      appendError("audio", "> Is the API server running? (uvicorn api:app --reload)");
      setPillBusy("audio", false);
      setPillBusy("lyric", false);
      state.running = false;
      $("run-btn").disabled = false;
      $("run-btn").querySelector(".run-btn-label").textContent = "Run Debate";
      return;
    }

    // Got the script — clear loading lines and replay
    clearCli();
    resetStats(demo.rounds);

    await playScript(demo);

    setPillBusy("audio", false);
    setPillBusy("lyric", false);
    showVerdict(demo);

    state.running = false;
    $("run-btn").disabled = false;
    $("run-btn").querySelector(".run-btn-label").textContent = "Run Debate";
  }

  /* ---------- confusion matrices ---------- */
  const _cmLabels = (typeof CM_LABELS !== "undefined" && CM_LABELS) ? CM_LABELS : ERAS.map(e => e.label);

  function buildMatrix(wrapId, tipId, confusion, agentLabel) {
    const wrap = $(wrapId);
    if (!wrap) return;
    wrap.innerHTML = "";

    if (!confusion) {
      wrap.innerHTML = '<div style="font-family:var(--font-mono);font-size:12px;color:var(--ink-3);padding:24px;">Train the model first to see the real confusion matrix.</div>';
      return;
    }

    wrap.style.gridTemplateColumns = "60px repeat(" + _cmLabels.length + ", minmax(0, 1fr))";

    const corner = document.createElement("div");
    corner.className = "m-corner";
    corner.innerHTML = '<div style="font-family:var(--font-mono);font-size:9.5px;color:var(--ink-4);text-align:right;padding:0 8px 4px 0;line-height:1.2;">true ↓<br/>pred →</div>';
    wrap.appendChild(corner);

    _cmLabels.forEach((label) => {
      const h = document.createElement("div");
      h.className  = "m-col-head";
      h.textContent = label;
      wrap.appendChild(h);
    });

    const tip = $(tipId);
    const max = 0.42;
    _cmLabels.forEach((rowLabel, ri) => {
      const rh = document.createElement("div");
      rh.className  = "m-row-head";
      rh.textContent = rowLabel;
      wrap.appendChild(rh);

      _cmLabels.forEach((colLabel, ci) => {
        const cell = document.createElement("div");
        cell.className = "m-cell" + (ri === ci ? " is-diag" : "");
        const v = confusion[ri][ci];
        const t = Math.min(1, v / max);
        const r = lerp(0xef, 0x1f, t);
        const g = lerp(0xee, 0x1d, t);
        const b = lerp(0xe4, 0x18, t);
        cell.style.background = `rgb(${r},${g},${b})`;
        if (t < 0.45) cell.classList.add("is-light");
        if (v >= 0.05) {
          cell.textContent = Math.round(v * 100) + "";
          cell.style.color = t >= 0.45 ? "var(--cream)" : "var(--ink-2)";
        }
        cell.dataset.row = ri;
        cell.dataset.col = ci;
        cell.addEventListener("mouseenter", (e) => {
          const row = +e.currentTarget.dataset.row;
          const col = +e.currentTarget.dataset.col;
          const val = confusion[row][col];
          tip.textContent = row === col
            ? `${_cmLabels[row]}: ${Math.round(val * 100)}% correctly classified`
            : `${agentLabel} confused ${_cmLabels[row]} with ${_cmLabels[col]} in ${Math.round(val * 100)}% of cases`;
          tip.hidden = false;
          tip.style.left = (e.clientX + 14) + "px";
          tip.style.top  = (e.clientY + 14) + "px";
        });
        cell.addEventListener("mousemove", (e) => {
          tip.style.left = (e.clientX + 14) + "px";
          tip.style.top  = (e.clientY + 14) + "px";
        });
        cell.addEventListener("mouseleave", () => { tip.hidden = true; });
        wrap.appendChild(cell);
      });
    });
  }

  function lerp(a, b, t) { return Math.round(a + (b - a) * t); }

  const _confAudio = (typeof CONFUSION_AUDIO !== "undefined") ? CONFUSION_AUDIO : null;
  const _confText  = (typeof CONFUSION_TEXT  !== "undefined") ? CONFUSION_TEXT  : null;
  buildMatrix("matrix-audio", "matrix-audio-tooltip", _confAudio, "Audio agent");
  buildMatrix("matrix-text",  "matrix-text-tooltip",  _confText,  "Lyrics agent");

  window.eralyzerRun = run;

})();
