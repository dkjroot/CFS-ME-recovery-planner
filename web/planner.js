"use strict";

const byId = (id) => document.getElementById(id);
const connection = byId("connection");
const onboardingSection = byId("onboarding");
const dashboard = byId("dashboard");
const topNav = byId("top-nav");
const bottomNav = byId("bottom-nav");
const accountBar = byId("account-bar");
const notice = byId("notice");
const saveFeedback = byId("save-feedback");
const trajectoryCanvas = byId("trajectory-chart");

const shortDateFmt = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", timeZone: "UTC" });
const monthYearFmt = new Intl.DateTimeFormat(undefined, { month: "short", year: "numeric", timeZone: "UTC" });
const fullDateFmt = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeZone: "UTC" });
const headingDateFmt = new Intl.DateTimeFormat(undefined, {
  weekday: "long", month: "long", day: "numeric", timeZone: "UTC",
});

let view = null;
let sessionWriteToken = "";
let activeTab = "today";
let previewLevelOverride = null;
let resumeLevelOverride = null;
let draftBeyondPlan = [];

function el(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined && text !== null) node.textContent = text;
  if (className) node.className = className;
  return node;
}

function fmtDate(iso, formatter = fullDateFmt) {
  if (!iso) return "";
  return formatter.format(new Date(iso + "T00:00:00Z"));
}

function report(message, isError = false) {
  notice.textContent = message;
  notice.classList.toggle("error", isError);
}

function reportSave(message, isError = false) {
  saveFeedback.textContent = message;
  saveFeedback.classList.toggle("error", isError);
}

async function apiRequest(action, payload) {
  const options = payload ? {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Planner-Session": sessionWriteToken },
    body: JSON.stringify(payload),
  } : {};
  const response = await fetch("/api/planner" + (action ? "/" + action : ""), options);
  if (response.headers.get("X-Planner-App") !== "1") {
    throw new Error("Could not reach the planner server.");
  }
  if (response.status === 401) {
    connection.hidden = false;
    connection.textContent = "Opening sign-in…";
    dashboard.hidden = true;
    onboardingSection.hidden = true;
    window.location.replace("/login");
    return null;
  }
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || "Request failed.");
  return result;
}

async function submitAction(action, payload, successMessage, afterSave) {
  const buttons = document.querySelectorAll("#onboarding button, #dashboard button");
  for (const btn of buttons) btn.disabled = true;
  try {
    const result = await apiRequest(action, payload);
    if (!result) return;
    view = result;
    renderAll();
    afterSave?.();
    if (successMessage) report(successMessage, false);
  } catch (error) {
    const msg = error.message || "Could not save. Try again.";
    report(msg, true);
    reportSave(msg, true);
  } finally {
    for (const btn of buttons) btn.disabled = false;
  }
}

/* ---------- Navigation ---------- */

function switchTab(tab, { scroll = true } = {}) {
  activeTab = tab;
  for (const btn of document.querySelectorAll("[data-tab]")) {
    btn.classList.toggle("is-active", btn.dataset.tab === tab);
  }
  for (const name of ["today", "journey", "history", "plan"]) {
    byId("view-" + name).hidden = name !== tab;
  }
  if (tab === "journey") {
    requestAnimationFrame(drawTrajectoryChart);
  }
  if (scroll) {
    window.scrollTo({ top: 0, behavior: "auto" });
  }
}

for (const btn of document.querySelectorAll("[data-tab]")) {
  btn.addEventListener("click", () => switchTab(btn.dataset.tab));
}

/* ---------- Onboarding Assessment ---------- */

function computeAssessmentRecommendation(answers) {
  const capacities = [answers.upright, answers.walk_10, answers.household, answers.mental];
  const limiting = Math.min(...capacities);
  const avg = capacities.reduce((a, b) => a + b, 0) / capacities.length;
  const weighted = 0.55 * limiting + 0.45 * avg;
  let raw = Math.round(1 + weighted * 2.25);

  if (answers.walk_10 === 0 || answers.upright === 0) raw = Math.min(raw, 2);
  else if (answers.walk_10 === 1) raw = Math.min(raw, 3);
  else if (answers.walk_10 === 2) raw = Math.min(raw, 5);
  else if (answers.walk_10 === 3) raw = Math.min(raw, 7);

  if (answers.stability === 0) raw -= 2;
  else if (answers.stability === 1) raw -= 1;
  else if (answers.stability === 4 && limiting >= 3) raw += 1;

  const recommended = Math.max(1, Math.min(10, raw));
  let summary;
  if (answers.stability <= 1) {
    summary = "Because your recent days have felt up and down, this starts gently so you can settle into a steady rhythm without triggering a crash.";
  } else if (answers.walk_10 <= 1) {
    summary = "Starting in Phase 1 keeps movement brief and restorative while your body builds the stability needed for daily short walks.";
  } else {
    summary = "This starting level matches your current capacity with a safety margin so you can hold steady days before stepping up.";
  }
  return { recommended, summary };
}

function readAssessmentAnswers() {
  const answers = {};
  for (const q of view.assessment_questions) {
    const checked = document.querySelector(`input[name="q_${q.id}"]:checked`);
    if (!checked) return null;
    answers[q.id] = Number(checked.value);
  }
  return answers;
}

function updateAssessmentPreview() {
  const preview = byId("assessment-preview");
  const answers = readAssessmentAnswers();
  if (!answers) {
    preview.hidden = true;
    return;
  }
  const rec = computeAssessmentRecommendation(answers);
  if (previewLevelOverride === null) {
    previewLevelOverride = rec.recommended;
  }
  const lvl = Math.max(1, Math.min(12, previewLevelOverride));
  const spec = view.levels[String(lvl)];
  let totalDays = 0;
  for (let i = lvl; i < 12; i++) totalDays += view.levels[String(i)].hold_days;
  const estMs = Date.parse(view.today + "T00:00:00Z") + totalDays * 86400000;
  const estDate = monthYearFmt.format(new Date(estMs));

  byId("preview-phase").textContent = `Recommended start · Phase ${spec.phase}: ${spec.phase_name}`;
  byId("preview-level-title").textContent = `Level ${lvl} · ${spec.title}`;
  byId("preview-level-badge").textContent = `Level ${lvl}`;
  byId("preview-summary").textContent = lvl === rec.recommended ? rec.summary : spec.summary;
  byId("preview-timeline").textContent = lvl === 12
    ? "Level 12 · Normal energy maintenance"
    : `Estimated path to Level 12: ~${estDate} (${totalDays} steady days)`;

  const list = byId("preview-activity-list");
  list.replaceChildren(...spec.activities.map((item) =>
    el("li", `${item.label}: ${item.target}`)
  ));
  byId("preview-level-down").disabled = lvl <= 1;
  byId("preview-level-up").disabled = lvl >= 12;
  preview.hidden = false;
}

function renderOnboarding(isRetake = false) {
  const container = byId("assessment-questions");
  const savedAnswers = view.profile?.assessment?.answers ?? {};
  previewLevelOverride = isRetake && view.program ? view.program.level : null;

  container.replaceChildren(...view.assessment_questions.map((q, index) => {
    const card = el("section", null, "card question-card");
    card.append(
      el("p", `Question ${index + 1} of ${view.assessment_questions.length}`, "question-num"),
      el("h2", q.prompt),
    );
    const optionsWrap = el("div", null, "question-options");
    for (const opt of q.options) {
      const label = el("label", null, "option-row");
      const input = document.createElement("input");
      input.type = "radio";
      input.name = `q_${q.id}`;
      input.value = String(opt.value);
      if (savedAnswers[q.id] === opt.value) input.checked = true;
      input.addEventListener("change", () => {
        previewLevelOverride = null;
        updateAssessmentPreview();
      });
      label.append(input, el("span", opt.label));
      optionsWrap.append(label);
    }
    card.append(optionsWrap);
    return card;
  }));

  byId("cancel-retake-btn").hidden = !isRetake;
  byId("start-plan-btn").textContent = isRetake ? "Update my recovery plan" : "Start my recovery plan";
  onboardingSection.hidden = false;
  dashboard.hidden = true;
  topNav.hidden = true;
  bottomNav.hidden = true;
  updateAssessmentPreview();
}

byId("preview-level-down").addEventListener("click", () => {
  if (previewLevelOverride > 1) {
    previewLevelOverride -= 1;
    updateAssessmentPreview();
  }
});
byId("preview-level-up").addEventListener("click", () => {
  if (previewLevelOverride < 12) {
    previewLevelOverride += 1;
    updateAssessmentPreview();
  }
});
byId("cancel-retake-btn").addEventListener("click", () => {
  onboardingSection.hidden = true;
  renderAll();
});

byId("assessment-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const answers = readAssessmentAnswers();
  if (!answers) {
    report("Answer all five questions first.", true);
    return;
  }
  submitAction(
    "assessment",
    { answers, starting_level: previewLevelOverride },
    "Your starting recovery plan is ready.",
    () => switchTab("today")
  );
});

/* ---------- Today View ---------- */

function renderStatusAndBanner() {
  const prog = view.program;
  const traj = view.trajectory;
  const isStab = prog.mode === "stabilizing";
  const statusCard = byId("status-card");
  statusCard.classList.toggle("is-stabilizing", isStab);

  byId("today-date").textContent = headingDateFmt.format(new Date(view.today + "T00:00:00Z"));
  const phasePill = byId("status-phase-pill");
  phasePill.textContent = isStab ? "Stabilization mode" : `Phase ${prog.phase} · ${prog.phase_name}`;
  phasePill.className = isStab ? "pill warn-pill" : "pill accent-pill";

  byId("status-effort-pill").textContent = isStab ? "Rest & gentle reset" : `Effort ceiling: ${prog.effort_ceiling}`;
  const cushionPill = byId("status-cushion-pill");
  cushionPill.hidden = !prog.cushion_pct;
  if (prog.cushion_pct) cushionPill.textContent = `${prog.cushion_pct}% gentler cushion`;

  byId("status-level-title").textContent = isStab
    ? `Resting from Level ${prog.level} · ${prog.title}`
    : `Level ${prog.level} · ${prog.title}`;
  byId("status-summary").textContent = isStab
    ? "Focus on quiet rest, steady meals, and gentle nervous-system calm until your body settles."
    : prog.summary;

  const fill = byId("progress-fill");
  const progressLabel = byId("progress-label");
  const progressEst = byId("progress-estimate");
  if (isStab) {
    const pct = Math.min(100, Math.round((prog.stabilize_steady_days / prog.stabilize_target) * 100));
    fill.style.width = pct + "%";
    progressLabel.textContent = `${prog.stabilize_steady_days} of ${prog.stabilize_target} steady days to resume`;
    progressEst.textContent = prog.ready_to_resume ? "Ready to choose next step" : "Take it day by day";
  } else if (prog.level >= 12) {
    fill.style.width = "100%";
    progressLabel.textContent = "Level 12 · Normal energy & maintenance";
    progressEst.textContent = "Keep listening to your body";
  } else {
    const pct = Math.min(100, Math.round((prog.steady_days / prog.hold_days) * 100));
    fill.style.width = pct + "%";
    progressLabel.textContent = `${prog.steady_days} of ${prog.hold_days} steady days at Level ${prog.level}`;
    const nextDate = traj.projected_dates[String(prog.level + 1)];
    progressEst.textContent = nextDate ? `Est. Level ${prog.level + 1}: ${fmtDate(nextDate, shortDateFmt)}` : "";
  }

  // Contextual action banner
  const banner = byId("action-banner");
  const eyebrow = byId("banner-eyebrow");
  const title = byId("banner-title");
  const body = byId("banner-body");
  const detail = byId("banner-detail");
  const resumeControls = byId("resume-controls");
  const actions = byId("banner-actions");

  banner.className = "card banner-card";
  detail.hidden = true;
  resumeControls.hidden = true;
  actions.replaceChildren();

  if (isStab) {
    banner.hidden = false;
    banner.classList.add("is-stabilize");
    const rec = prog.resume_recommendation;
    const trig = prog.stabilizing_trigger;
    if (trig) {
      const clues = [
        ...(trig.beyond_plan || []).map((b) => `${b.label} (${b.days_before}d earlier)`),
        ...(trig.factors || []).map((f) => view.factors[f] || f),
      ];
      if (clues.length) {
        detail.hidden = false;
        detail.textContent = "Logged beforehand: " + [...new Set(clues)].join(" · ");
      }
    }

    if (prog.ready_to_resume) {
      eyebrow.textContent = "Ready to resume";
      title.textContent = `Recommended return: Level ${rec.recommended_level}`;
      body.textContent = rec.reason;
      if (resumeLevelOverride === null) resumeLevelOverride = rec.recommended_level;
      resumeControls.hidden = false;
      byId("resume-level-badge").textContent = `Level ${resumeLevelOverride}`;
      byId("resume-level-down").disabled = resumeLevelOverride <= 1;
      byId("resume-level-up").disabled = resumeLevelOverride >= 12;

      const btn = el("button", `Resume at Level ${resumeLevelOverride}`);
      btn.type = "button";
      btn.addEventListener("click", () => {
        const chosen = resumeLevelOverride;
        resumeLevelOverride = null;
        submitAction("decision", { choice: "resume", level: chosen }, `Resumed at Level ${chosen}.`);
      });
      actions.append(btn);
    } else {
      eyebrow.textContent = "Stabilizing";
      title.textContent = "Rest and reset before rebuilding";
      body.textContent = `Log ${prog.stabilize_target} consecutive steady days when you feel settled, and we will guide your step back onto the plan.`;
      const earlyBtn = el("button", `Resume early at Level ${rec.recommended_level}`, "secondary");
      earlyBtn.type = "button";
      earlyBtn.addEventListener("click", () => {
        resumeLevelOverride = null;
        submitAction("decision", { choice: "resume", level: rec.recommended_level }, `Resumed at Level ${rec.recommended_level}.`);
      });
      actions.append(earlyBtn);
    }
  } else if (prog.step_up_ready && prog.next_level) {
    banner.hidden = false;
    banner.classList.add("is-stepup");
    eyebrow.textContent = "Progress check";
    title.textContent = `${prog.hold_days} steady days complete — ready for Level ${prog.next_level.level}?`;
    body.textContent = `Next: Level ${prog.next_level.level} (${prog.next_level.title}) — ${prog.next_level.summary}`;
    const moveBtn = el("button", `Move to Level ${prog.next_level.level}`);
    moveBtn.type = "button";
    moveBtn.addEventListener("click", () => {
      submitAction("decision", { choice: "advance" }, `Moved to Level ${prog.next_level.level}.`);
    });
    const waitBtn = el("button", "Reassess in 5 days", "secondary");
    waitBtn.type = "button";
    waitBtn.addEventListener("click", () => {
      submitAction("decision", { choice: "hold_five" }, "Added 5 steady days before the next check.");
    });
    actions.append(moveBtn, waitBtn);
  } else if (prog.pending_watch) {
    banner.hidden = false;
    banner.classList.add("is-watch");
    eyebrow.textContent = "3-day response watch";
    title.textContent = "Watching how your body responds";
    body.textContent = `Following ${prog.pending_watch.items.join(", ")}, stay steady through ${fmtDate(prog.pending_watch.watch_until, shortDateFmt)} before moving up a level.`;
  } else if (prog.hold_note) {
    banner.hidden = false;
    banner.classList.add("is-hold");
    eyebrow.textContent = "Holding steady";
    title.textContent = "Consistency locks in this level";
    body.textContent = prog.hold_note;
  } else {
    banner.hidden = true;
  }
}

byId("resume-level-down").addEventListener("click", () => {
  if (resumeLevelOverride > 1) {
    resumeLevelOverride -= 1;
    renderStatusAndBanner();
  }
});
byId("resume-level-up").addEventListener("click", () => {
  if (resumeLevelOverride < 12) {
    resumeLevelOverride += 1;
    renderStatusAndBanner();
  }
});

/* ---------- Daily Check-in Survey ---------- */

function renderBeyondLogged() {
  const container = byId("beyond-logged-list");
  container.replaceChildren(...draftBeyondPlan.map((item, idx) => {
    const chip = el("span", null, "beyond-chip");
    const mins = item.minutes ? ` · ${item.minutes} min` : "";
    chip.append(el("span", `${item.label} (${item.effort}${mins})`));
    const rm = el("button", "×");
    rm.type = "button";
    rm.setAttribute("aria-label", `Remove ${item.label}`);
    rm.addEventListener("click", () => {
      draftBeyondPlan.splice(idx, 1);
      renderBeyondLogged();
    });
    chip.append(rm);
    return chip;
  }));
}

function renderCheckinForm(selectedDate) {
  const dateInput = byId("checkin-date");
  dateInput.max = view.today;
  dateInput.value = selectedDate || view.today;
  const saved = view.checkins[dateInput.value] || null;
  byId("editing-badge").hidden = !saved;

  // Determine which activities belong to the selected day.
  let activities;
  if (saved) {
    activities = saved.mode === "stabilizing"
      ? view.levels["1"] && STABILIZATION_FALLBACK()
      : view.program.activities;
    if (saved.mode === "stabilizing" && view.program.mode === "stabilizing") {
      activities = view.program.activities;
    } else if (saved.mode === "active") {
      const lvlSpec = view.levels[String(saved.level)];
      const disabled = new Set(view.profile.disabled_categories || []);
      activities = (saved.level === view.program.level && view.program.mode === "active")
        ? view.program.activities
        : lvlSpec.activities.filter((a) => !a.optional || !disabled.has(a.category) || (saved.activities && a.id in saved.activities));
    }
  } else {
    activities = view.program.activities;
  }

  byId("activities-subtitle").textContent = view.program.mode === "stabilizing" && !saved
    ? "Light stabilization routine — tap how each felt today."
    : "Pre-filled for your current level — tap how each felt today.";

  const actWrap = byId("checkin-activities");
  actWrap.replaceChildren(...activities.map((item) => {
    const box = el("div", null, "activity-item");
    const head = el("div", null, "activity-head");
    head.append(el("strong", item.label), el("span", item.category, "activity-cat"));
    box.append(head, el("p", item.target, "activity-target"));

    const group = el("div", null, "rating-group");
    group.setAttribute("role", "radiogroup");
    group.setAttribute("aria-label", item.label);
    const savedRating = saved?.activities?.[item.id] ?? "";

    for (const [key, labelText] of Object.entries(view.activity_ratings)) {
      const tile = el("label", null, "radio-tile");
      tile.dataset.val = key;
      const radio = document.createElement("input");
      radio.type = "radio";
      radio.name = `act_${item.id}`;
      radio.value = key;
      if (savedRating === key) radio.checked = true;
      tile.append(radio, el("span", labelText));
      group.append(tile);
    }
    box.append(group);
    return box;
  }));

  // Feeling radio group
  const feelingWrap = byId("checkin-feeling");
  const savedFeeling = saved?.feeling ?? "";
  feelingWrap.replaceChildren(...Object.entries(view.feelings).map(([key, labelText]) => {
    const tile = el("label", null, "radio-tile feeling-tile");
    tile.dataset.feeling = key;
    const radio = document.createElement("input");
    radio.type = "radio";
    radio.name = "feeling";
    radio.value = key;
    if (savedFeeling === key) radio.checked = true;
    tile.append(radio, el("span", labelText));
    return tile;
  }));

  // Factor toggle chips
  const factorsWrap = byId("checkin-factors");
  const savedFactors = new Set(saved?.factors ?? []);
  factorsWrap.replaceChildren(...Object.entries(view.factors).map(([key, labelText]) => {
    const chip = el("label", null, "check-chip");
    const box = document.createElement("input");
    box.type = "checkbox";
    box.name = "factor";
    box.value = key;
    if (savedFactors.has(key)) box.checked = true;
    chip.append(box, el("span", labelText));
    return chip;
  }));

  // Beyond plan items
  draftBeyondPlan = (saved?.beyond_plan ?? []).map((x) => ({ ...x }));
  renderBeyondLogged();
  byId("beyond-presets").replaceChildren(...view.beyond_plan_presets.map((preset) => {
    const btn = el("button", preset, "preset-chip");
    btn.type = "button";
    btn.addEventListener("click", () => {
      byId("beyond-label").value = preset;
      byId("beyond-label").focus();
    });
    return btn;
  }));
  byId("beyond-effort").replaceChildren(...["light", "medium", "heavy"].map((lvl) => {
    const tile = el("label", null, "radio-tile");
    const radio = document.createElement("input");
    radio.type = "radio";
    radio.name = "beyond_effort";
    radio.value = lvl;
    if (lvl === "medium") radio.checked = true;
    tile.append(radio, el("span", lvl[0].toUpperCase() + lvl.slice(1)));
    return tile;
  }));
  byId("beyond-label").value = "";
  byId("beyond-minutes").value = "";
  byId("beyond-drawer").open = draftBeyondPlan.length > 0;
  byId("checkin-note").value = saved?.note ?? "";
}

function STABILIZATION_FALLBACK() {
  return [
    { id: "rest", label: "Quiet rest & low stimulation", category: "Rest", target: "Prioritize quiet horizontal rest without screens" },
    { id: "nourish", label: "Meals & hydration", category: "Rest", target: "Gentle regular meals and steady fluids" },
    { id: "reset", label: "Calming nervous-system reset", category: "Movement", target: "5 min slow breathing or legs up the wall" },
    { id: "household", label: "Bare-minimum essentials only", category: "Household", target: "Only essential self-care" },
  ];
}

function appendDraftBeyondFromInputs() {
  const label = byId("beyond-label").value.trim();
  if (!label) return true;
  if (draftBeyondPlan.length >= 5) {
    reportSave("You can add up to 5 unplanned activities per day.", true);
    return false;
  }
  const effort = document.querySelector('input[name="beyond_effort"]:checked')?.value || "medium";
  const minsRaw = byId("beyond-minutes").value.trim();
  const minutes = minsRaw === "" ? null : Number(minsRaw);
  if (minutes !== null && (!Number.isInteger(minutes) || minutes < 0 || minutes > 1440)) {
    reportSave("Enter minutes between 0 and 1440.", true);
    return false;
  }
  draftBeyondPlan.push({ label, effort, minutes });
  byId("beyond-label").value = "";
  byId("beyond-minutes").value = "";
  renderBeyondLogged();
  return true;
}

byId("add-beyond-btn").addEventListener("click", () => {
  if (!byId("beyond-label").value.trim()) {
    reportSave("Enter an activity name or tap a quick preset.", true);
    byId("beyond-label").focus();
    return;
  }
  reportSave("");
  if (appendDraftBeyondFromInputs()) {
    byId("beyond-drawer").open = false;
  }
});

byId("checkin-date").addEventListener("change", (event) => {
  reportSave("");
  renderCheckinForm(event.target.value);
});

byId("checkin-form").addEventListener("submit", (event) => {
  event.preventDefault();
  reportSave("");
  if (!appendDraftBeyondFromInputs()) return;

  const feeling = document.querySelector('input[name="feeling"]:checked')?.value;
  if (!feeling) {
    reportSave("Choose how you are feeling today before saving.", true);
    byId("checkin-feeling").scrollIntoView({ behavior: "smooth", block: "center" });
    return;
  }

  const activities = {};
  for (const radio of document.querySelectorAll('#checkin-activities input[type="radio"]:checked')) {
    const id = radio.name.replace(/^act_/, "");
    activities[id] = radio.value;
  }
  const factors = [...document.querySelectorAll('#checkin-factors input[type="checkbox"]:checked')].map((el) => el.value);

  const payload = {
    date: byId("checkin-date").value,
    feeling,
    activities,
    factors,
    beyond_plan: draftBeyondPlan,
    note: byId("checkin-note").value,
  };

  submitAction("checkin", payload, null, () => {
    reportSave("Check-in saved for " + fmtDate(payload.date, shortDateFmt) + ".");
    if (view.program.mode === "stabilizing" || view.program.step_up_ready) {
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  });
});

/* ---------- Journey Tab & Trajectory Chart ---------- */

function drawTrajectoryChart() {
  if (!view?.trajectory) return;
  const width = trajectoryCanvas.clientWidth;
  const height = trajectoryCanvas.clientHeight;
  if (!width || !height) return;

  const scale = window.devicePixelRatio || 1;
  trajectoryCanvas.width = Math.round(width * scale);
  trajectoryCanvas.height = Math.round(height * scale);
  const ctx = trajectoryCanvas.getContext("2d");
  ctx.scale(scale, scale);

  const css = getComputedStyle(trajectoryCanvas);
  const cAccent = css.getPropertyValue("--accent").trim();
  const cSky = css.getPropertyValue("--sky").trim();
  const cWarn = css.getPropertyValue("--warn").trim();
  const cLow = css.getPropertyValue("--low").trim();
  const cMuted = css.getPropertyValue("--muted").trim();
  const cGrid = css.getPropertyValue("--chart-grid").trim();

  const traj = view.trajectory;
  const allPts = [...traj.actual_points, ...traj.projected_points];
  const parseMs = (iso) => Date.parse(iso + "T00:00:00Z");
  let minMs = Math.min(...allPts.map((p) => parseMs(p.date)));
  let maxMs = Math.max(...allPts.map((p) => parseMs(p.date)));
  if (maxMs - minMs < 14 * 86400000) maxMs = minMs + 14 * 86400000;

  const left = 36;
  const right = width - 16;
  const top = 18;
  const bottom = height - 34;
  const x = (iso) => left + ((parseMs(iso) - minMs) / (maxMs - minMs)) * (right - left);
  const y = (lvl) => bottom - ((lvl - 1) / 11) * (bottom - top);

  // Subtle horizontal phase bands: P1 (1-4), P2 (5-8), P3 (9-12)
  const bands = [
    { from: 1, to: 4.5, fill: "rgba(143, 212, 176, 0.04)", label: "P1" },
    { from: 4.5, to: 8.5, fill: "rgba(142, 197, 240, 0.04)", label: "P2" },
    { from: 8.5, to: 12, fill: "rgba(240, 185, 122, 0.04)", label: "P3" },
  ];
  for (const b of bands) {
    const yTop = y(b.to);
    const yBot = y(b.from);
    ctx.fillStyle = b.fill;
    ctx.fillRect(left, yTop, right - left, yBot - yTop);
    ctx.fillStyle = "rgba(158, 176, 169, 0.45)";
    ctx.font = '10px -apple-system, system-ui, sans-serif';
    ctx.textAlign = "right";
    ctx.fillText(b.label, right - 4, yTop + 12);
  }

  // Horizontal level gridlines (1, 4, 8, 12)
  ctx.font = '11px -apple-system, system-ui, sans-serif';
  for (const lvl of [1, 4, 8, 12]) {
    const py = y(lvl);
    ctx.beginPath();
    ctx.strokeStyle = cGrid;
    ctx.lineWidth = 1;
    ctx.moveTo(left, py);
    ctx.lineTo(right, py);
    ctx.stroke();
    ctx.fillStyle = cMuted;
    ctx.textAlign = "right";
    ctx.fillText("L" + lvl, left - 6, py + 4);
  }

  // Vertical "Today" line
  const todayX = x(view.today);
  ctx.beginPath();
  ctx.setLineDash([3, 3]);
  ctx.strokeStyle = "rgba(158, 176, 169, 0.4)";
  ctx.moveTo(todayX, top);
  ctx.lineTo(todayX, bottom);
  ctx.stroke();
  ctx.setLineDash([]);

  // X-axis date labels (deduplicated calendar ticks, spaced to avoid overlap)
  ctx.fillStyle = cMuted;
  const spanDays = (maxMs - minMs) / 86400000;
  const fmt = spanDays <= 45 ? shortDateFmt : monthYearFmt;
  const tickTimes = [minMs];
  if (spanDays > 45) {
    const startD = new Date(minMs);
    let cursor = Date.UTC(startD.getUTCFullYear(), startD.getUTCMonth() + 1, 1);
    while (cursor < maxMs) {
      tickTimes.push(cursor);
      const d = new Date(cursor);
      cursor = Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 1, 1);
    }
  } else {
    for (let i = 1; i < 4; i++) tickTimes.push(minMs + (i / 4) * (maxMs - minMs));
  }
  tickTimes.push(maxMs);

  let lastRightEdge = -Infinity;
  let lastLabel = "";
  const endLabel = fmt.format(new Date(maxMs));
  const endWidth = ctx.measureText(endLabel).width;
  const endLeftEdge = right - endWidth - 12;
  for (let i = 0; i < tickTimes.length; i++) {
    const tMs = tickTimes[i];
    const px = left + ((tMs - minMs) / (maxMs - minMs)) * (right - left);
    const label = fmt.format(new Date(tMs));
    const w = ctx.measureText(label).width;
    const isFirst = i === 0;
    const isLast = i === tickTimes.length - 1;
    const align = isFirst ? "left" : isLast ? "right" : "center";
    const textLeft = align === "left" ? px : align === "right" ? px - w : px - w / 2;
    const textRight = textLeft + w;
    if (!isFirst && !isLast) {
      if (label === lastLabel || label === endLabel) continue;
      if (textLeft < lastRightEdge + 12 || textRight > endLeftEdge) continue;
    } else if (isLast && (label === lastLabel || textLeft < lastRightEdge + 10)) {
      continue;
    }
    ctx.textAlign = align;
    ctx.fillText(label, px, height - 10);
    lastRightEdge = textRight;
    lastLabel = label;
  }

  // Projected path (dashed sky-blue)
  if (traj.projected_points.length >= 2) {
    ctx.beginPath();
    ctx.setLineDash([6, 5]);
    ctx.strokeStyle = cSky;
    ctx.lineWidth = 2.2;
    traj.projected_points.forEach((pt, idx) => {
      const px = x(pt.date);
      const py = y(pt.level);
      if (idx === 0) ctx.moveTo(px, py);
      else ctx.lineTo(px, py);
    });
    ctx.stroke();
    ctx.setLineDash([]);

    const lastProj = traj.projected_points[traj.projected_points.length - 1];
    ctx.beginPath();
    ctx.fillStyle = cSky;
    ctx.arc(x(lastProj.date), y(lastProj.level), 3.5, 0, Math.PI * 2);
    ctx.fill();
  }

  // Actual trajectory path (solid sage-teal)
  if (traj.actual_points.length >= 1) {
    ctx.beginPath();
    ctx.strokeStyle = cAccent;
    ctx.lineWidth = 2.8;
    traj.actual_points.forEach((pt, idx) => {
      const px = x(pt.date);
      const py = y(pt.level);
      if (idx === 0) ctx.moveTo(px, py);
      else ctx.lineTo(px, py);
    });
    ctx.stroke();
  }

  // Daily low / crash markers
  for (const m of traj.daily_markers) {
    if (m.feeling !== "crash" && m.feeling !== "worse") continue;
    const px = x(m.date);
    const py = y(m.level);
    if (m.feeling === "crash") {
      ctx.beginPath();
      ctx.moveTo(px, py - 6);
      ctx.lineTo(px + 6, py);
      ctx.lineTo(px, py + 6);
      ctx.lineTo(px - 6, py);
      ctx.closePath();
      ctx.fillStyle = cLow;
      ctx.fill();
    } else {
      ctx.beginPath();
      ctx.fillStyle = cWarn;
      ctx.arc(px, py, 3.5, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  // "You are here" glowing marker
  const hereX = x(view.today);
  const hereY = y(view.program.level);
  ctx.beginPath();
  ctx.fillStyle = "rgba(143, 212, 176, 0.25)";
  ctx.arc(hereX, hereY, 10, 0, Math.PI * 2);
  ctx.fill();
  ctx.beginPath();
  ctx.fillStyle = cAccent;
  ctx.arc(hereX, hereY, 5, 0, Math.PI * 2);
  ctx.fill();
}

function renderJourney() {
  const traj = view.trajectory;
  const etaPill = byId("journey-eta-pill");
  if (view.program.level >= 12) {
    etaPill.textContent = "Level 12 reached";
  } else {
    etaPill.textContent = "Est. Level 12: " + fmtDate(traj.estimated_full_recovery_date, monthYearFmt);
  }

  // Benchmarks
  const bWrap = byId("benchmarks-list");
  if (!view.benchmarks.length) {
    bWrap.replaceChildren(el("p", "When you log an unplanned drive, appointment, or outing, it appears here with its 3-day outcome.", "muted-copy"));
  } else {
    bWrap.replaceChildren(...view.benchmarks.map((bm) => {
      const row = el("div", null, "benchmark-row");
      const top = el("div", null, "benchmark-top");
      const mins = bm.minutes ? ` · ${bm.minutes} min` : "";
      top.append(el("strong", `${bm.label} (${bm.effort}${mins})`));
      const badgeClass = bm.outcome === "tolerated" ? "pill accent-pill"
        : bm.outcome === "not_ready" ? "pill low-pill"
          : bm.outcome === "watching" ? "pill sky-pill" : "pill";
      const badgeLabel = bm.outcome === "tolerated" ? "Handled well"
        : bm.outcome === "not_ready" ? "Above capacity"
          : bm.outcome === "watching" ? "Watching" : "Unlogged";
      top.append(el("span", badgeLabel, badgeClass));
      row.append(top, el("p", `${fmtDate(bm.date)} · ${bm.outcome_text}`, "muted-copy"));
      return row;
    }));
  }

  // 12-level roadmap grouped by phase
  const roadmapWrap = byId("roadmap-levels");
  const phases = [1, 2, 3].map((p) => {
    const block = el("div", null, "phase-block");
    const phaseInfo = view.phases[String(p)];
    block.append(el("p", `Phase ${p} · ${phaseInfo.name} (Effort ${phaseInfo.effort})`, "phase-header"));
    for (const m of traj.milestones.filter((item) => item.phase === p)) {
      const details = el("details", null, "level-row" + (m.status === "current" ? " is-current" : ""));
      if (m.status === "current") details.open = true;
      const summary = el("summary");
      summary.append(el("span", `Level ${m.level} · ${m.title}`));
      let statusText;
      let pillClass = "pill";
      if (m.status === "completed") {
        statusText = m.date ? `Done ${fmtDate(m.date, shortDateFmt)}` : "Completed";
        pillClass = "pill accent-pill";
      } else if (m.status === "current") {
        statusText = "Current";
        pillClass = "pill accent-pill";
      } else {
        statusText = m.date ? `Est. ${fmtDate(m.date, shortDateFmt)}` : "Upcoming";
        pillClass = "pill sky-pill";
      }
      summary.append(el("span", statusText, pillClass));
      details.append(summary);

      const detail = el("div", null, "level-detail");
      detail.append(
        el("p", `${m.summary} (Hold ~${m.hold_days} steady days · Effort ${m.effort_ceiling})`, "muted-copy"),
        (() => {
          const ul = el("ul", null, "clean-list");
          for (const act of m.activities) ul.append(el("li", `${act.label}: ${act.target}`));
          return ul;
        })(),
      );
      details.append(detail);
      block.append(details);
    }
    return block;
  });
  roadmapWrap.replaceChildren(...phases);
  drawTrajectoryChart();
}

/* ---------- History Tab ---------- */

function renderHistory() {
  const lowCard = byId("low-reviews-card");
  const lowList = byId("low-reviews-list");
  if (view.recent_lows.length) {
    lowCard.hidden = false;
    lowList.replaceChildren(...view.recent_lows.map((low) => {
      const card = el("div", null, "lookback-card");
      const top = el("div", null, "history-top");
      top.append(
        el("strong", `${fmtDate(low.date)} · Level ${low.level}`),
        el("span", view.feelings[low.feeling], low.feeling === "crash" ? "pill low-pill" : "pill warn-pill")
      );
      const clues = [
        ...(low.beyond_plan || []).map((b) => `${b.label} (${b.days_before}d earlier)`),
        ...(low.too_much || []).map((t) => `${t.id} too much (${t.days_before}d earlier)`),
        ...(low.factors || []).map((f) => view.factors[f] || f),
      ];
      card.append(top, el("p", clues.length ? "Prior 3 days: " + [...new Set(clues)].join(" · ") : "No unplanned activity or overexertion flagged in the prior 3 days.", "muted-copy"));
      return card;
    }));
  } else {
    lowCard.hidden = true;
  }

  const dates = Object.keys(view.checkins).sort().reverse();
  byId("history-empty").hidden = dates.length > 0;
  const list = byId("history-list");
  list.replaceChildren(...dates.map((day) => {
    const entry = view.checkins[day];
    const card = el("div", null, "history-card");
    const top = el("div", null, "history-top");
    top.append(el("strong", `${fmtDate(day)} · Level ${entry.level}${entry.mode === "stabilizing" ? " (Stabilizing)" : ""}`));
    const pillClass = entry.feeling === "crash" ? "pill low-pill"
      : entry.feeling === "worse" ? "pill warn-pill"
        : entry.feeling === "steady" ? "pill accent-pill" : "pill sky-pill";
    top.append(el("span", view.feelings[entry.feeling], pillClass));
    card.append(top);

    const parts = [];
    const ratings = Object.entries(entry.activities || {}).map(([id, r]) => `${id}: ${view.activity_ratings[r] || r}`);
    if (ratings.length) parts.push(ratings.join(" · "));
    if (entry.factors?.length) parts.push("Factors: " + entry.factors.map((f) => view.factors[f] || f).join(", "));
    if (entry.beyond_plan?.length) parts.push("Beyond plan: " + entry.beyond_plan.map((b) => b.label).join(", "));
    if (entry.note) parts.push(entry.note);
    if (parts.length) card.append(el("p", parts.join(" · "), "muted-copy"));

    const editBtn = el("button", "Edit check-in", "secondary compact-btn");
    editBtn.type = "button";
    editBtn.addEventListener("click", () => {
      switchTab("today");
      renderCheckinForm(day);
      byId("checkin-date").focus();
    });
    card.append(editBtn);
    return card;
  }));
}

/* ---------- Plan Tab (Preferences) ---------- */

function renderPlanTab() {
  const disabled = new Set(view.profile.disabled_categories || []);
  byId("pref-movement").checked = !disabled.has("Movement");
  byId("pref-social").checked = !disabled.has("Social");
  byId("pref-cognitive").checked = !disabled.has("Cognitive");

  const paceWrap = byId("pace-options");
  const currentScale = Number(view.profile.hold_scale || 1.0);
  const paces = [
    { value: 1.25, label: "Gentler (+25%)" },
    { value: 1.0, label: "Standard" },
    { value: 0.8, label: "Faster (−20%)" },
  ];
  paceWrap.replaceChildren(...paces.map((p) => {
    const tile = el("label", null, "radio-tile");
    const radio = document.createElement("input");
    radio.type = "radio";
    radio.name = "hold_scale";
    radio.value = String(p.value);
    if (Math.abs(currentScale - p.value) < 0.05) radio.checked = true;
    tile.append(radio, el("span", p.label));
    return tile;
  }));

  byId("pref-hold-days").value = String(view.program.hold_days);

  const select = byId("manual-level-select");
  select.replaceChildren(...Object.values(view.levels).map((lvl) => {
    const opt = el("option", `Level ${lvl.level} · ${lvl.title} (Phase ${lvl.phase})`);
    opt.value = String(lvl.level);
    if (lvl.level === view.program.level) opt.selected = true;
    return opt;
  }));
}

byId("preferences-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const disabled_categories = [];
  if (!byId("pref-movement").checked) disabled_categories.push("Movement");
  if (!byId("pref-social").checked) disabled_categories.push("Social");
  if (!byId("pref-cognitive").checked) disabled_categories.push("Cognitive");

  const scaleRadio = document.querySelector('input[name="hold_scale"]:checked');
  const hold_scale = scaleRadio ? Number(scaleRadio.value) : 1.0;
  const holdInput = byId("pref-hold-days").value.trim();
  const payload = { disabled_categories, hold_scale };
  if (holdInput !== "" && Number(holdInput) !== view.program.hold_days && Math.abs(hold_scale - (view.profile.hold_scale || 1.0)) < 0.01) {
    payload.hold_days = Number(holdInput);
  }
  submitAction("preferences", payload, "Plan preferences saved.");
});

byId("manual-level-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const level = Number(byId("manual-level-select").value);
  submitAction("decision", { choice: "set_level", level }, `Updated current level to Level ${level}.`);
});

byId("retake-assessment-btn").addEventListener("click", () => renderOnboarding(true));

/* ---------- Sign out & Init ---------- */

byId("sign-out").addEventListener("click", async () => {
  const btn = byId("sign-out");
  btn.disabled = true;
  try {
    const response = await fetch("/logout", { method: "POST" });
    if (!response.ok || response.headers.get("X-Planner-App") !== "1"
        || new URL(response.url).pathname !== "/login") {
      throw new Error();
    }
    window.location.replace("/login");
  } catch {
    report("Could not sign out. Check that the server is running.", true);
    btn.disabled = false;
  }
});

function renderAll() {
  connection.hidden = true;
  accountBar.hidden = false;
  if (!view.onboarded) {
    renderOnboarding(false);
    return;
  }
  onboardingSection.hidden = true;
  dashboard.hidden = false;
  topNav.hidden = false;
  bottomNav.hidden = false;

  renderStatusAndBanner();
  renderCheckinForm(byId("checkin-date").value || view.today);
  renderJourney();
  renderHistory();
  renderPlanTab();
  switchTab(activeTab, { scroll: false });
}

new ResizeObserver(drawTrajectoryChart).observe(trajectoryCanvas);

async function initPlanner() {
  try {
    const result = await apiRequest();
    if (!result) return;
    if (typeof result.username !== "string" || !/^[a-f0-9]{64}$/.test(result.write_token)) {
      throw new Error();
    }
    view = result;
    sessionWriteToken = result.write_token;
    byId("account-name").textContent = result.username;
    byId("account-name").setAttribute("aria-label", "Signed in as " + result.username);
    renderAll();
  } catch {
    connection.hidden = false;
    connection.textContent = "Could not connect to the planner. Open the address shown in the terminal.";
  }
}

initPlanner();

window.addEventListener("pageshow", (event) => {
  if (event.persisted) window.location.reload();
});
