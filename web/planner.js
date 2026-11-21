"use strict";

const byId = (id) => document.getElementById(id);
const planForm = byId("plan-form");
const entryForm = byId("entry-form");
const notice = byId("notice");
const chart = byId("chart");
const mode = byId("mode");
const signOut = byId("sign-out");
const connection = byId("connection");
const settings = byId("plan");
const routineForm = byId("routine-form");
const reviewForm = byId("review-form");
const shortDate = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", timeZone: "UTC" });
const fullDate = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeZone: "UTC" });
const headingDate = new Intl.DateTimeFormat(undefined, {
  weekday: "long", month: "long", day: "numeric", timeZone: "UTC",
});
const feelings = {
  better: "Better than usual",
  usual: "About the same",
  worse: "Worse than usual",
  crash: "Crash",
};
let view;
let sessionWriteToken;

function showPlanner(ready) {
  for (const id of ["navigation", "account-bar", "dashboard"]) byId(id).hidden = !ready;
  connection.hidden = ready;
}

function report(message, isError = false) {
  notice.textContent = message;
  notice.classList.toggle("error", isError);
}

async function request(action, payload) {
  const options = payload ? {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Planner-Session": sessionWriteToken },
    body: JSON.stringify(payload),
  } : {};
  const response = await fetch("/api/planner" + (action ? "/" + action : ""), options);
  if (response.headers.get("X-Planner-App") !== "1") {
    throw new Error("Could not reach the planner server. Open the address shown by the planner launcher.");
  }
  if (response.status === 401) {
    showPlanner(false);
    connection.textContent = "Opening sign-in…";
    window.location.replace("/login");
    return null;
  }
  const result = await response.json();
  if (!response.ok) throw new Error(result.error);
  return result;
}

function fillPlan() {
  const plan = view.plan;
  if (!plan) return;
  for (const field of ["activity", "limit", "step_back", "rest"]) {
    planForm.elements[field].value = plan[field] ?? "";
  }
}

function fillEntry() {
  const entry = view.history?.find((item) => item.date === entryForm.elements.date.value);
  entryForm.elements.minutes.value = entry?.minutes ?? "";
  entryForm.elements.feeling.value = entry?.feeling ?? "";
  entryForm.elements.context.value = entry?.context ?? "";
  fillRoutineFields();
}

function fillRoutineFields(keepDraft = false) {
  const container = byId("routine-fields");
  const draft = keepDraft ? Object.fromEntries(
    [...container.querySelectorAll("input")].map((input) => [input.name, input.value])
  ) : {};
  const entry = view.history.find((item) => item.date === entryForm.elements.date.value);
  const recorded = entry?.routine ?? {};
  const fields = [];
  for (const [key, item] of Object.entries({ ...view.routine, ...recorded })) {
    const label = element("label", item.name);
    const input = document.createElement("input");
    input.type = "number";
    input.inputMode = "numeric";
    input.min = 0;
    input.max = 1440;
    input.name = key;
    input.value = draft[key] ?? recorded[key]?.minutes ?? "";
    label.append(input);
    fields.push(label);
  }
  container.replaceChildren(...fields);
  byId("routine-check-in").hidden = !fields.length;
}

function recordText(entry) {
  if (!entry.feeling) return "No check-in";
  const amount = entry.minutes === null ? "" : entry.minutes + " min";
  const over = entry.minutes !== null && entry.planned !== null && entry.minutes > entry.planned
    ? " · " + (entry.minutes - entry.planned) + " min above saved limit" : "";
  const routine = Object.values(entry.routine ?? {}).map((item) => {
    const excess = item.kind !== "Rest" && item.planned !== null && item.minutes > item.planned
      ? " (above plan)" : "";
    return item.name + " " + item.minutes + " min" + excess;
  });
  return [amount, feelings[entry.feeling] + over, ...routine, entry.context].filter(Boolean).join(" · ");
}

function element(tag, text) {
  const node = document.createElement(tag);
  if (text) node.textContent = text;
  return node;
}

function renderRecords() {
  const reviews = view.lows.map((low) => {
    const record = element("div");
    record.className = "record";
    record.append(element("h3", fullDate.format(new Date(low.date)) + " · " + feelings[low.feeling]));
    const list = element("ul");
    for (const prior of low.prior) {
      list.append(element("li", shortDate.format(new Date(prior.date)) + " · " + recordText(prior)));
    }
    record.append(list);
    return record;
  });
  byId("review-panel").hidden = reviews.length === 0;
  byId("reviews").replaceChildren(...reviews);

  const records = view.history.slice().reverse().map((entry) => {
    const record = element("div");
    record.className = "record history-row";
    const date = fullDate.format(new Date(entry.date));
    const button = element("button", "Edit check-in");
    button.type = "button";
    button.className = "secondary";
    button.setAttribute("aria-label", "Edit check-in for " + date);
    button.addEventListener("click", () => {
      entryForm.elements.date.value = entry.date;
      fillEntry();
      entryForm.elements.date.focus();
    });
    const evidence = view.roadmap.findings[entry.date];
    const response = evidence?.status === "low"
      ? "A low or crash was logged " + evidence.days_until_low + (evidence.days_until_low === 1 ? " day later." : " days later.")
      : evidence?.status === "observed" ? "The next three check-ins were usual or better."
        : evidence?.status === "pending" ? "Follow-up still open."
          : evidence?.status === "incomplete" ? "Some follow-up days were unlogged." : "";
    record.append(element("h3", date), element("p", recordText(entry)), button);
    if (response) {
      const followUp = element("p", response);
      followUp.className = "follow-up";
      record.append(followUp);
    }
    return record;
  });
  byId("history-panel").hidden = records.length === 0;
  byId("history").replaceChildren(...records);
}

function renderGuidance() {
  const guide = view.roadmap;
  const next = guide.stages[guide.stage + 1];
  const current = guide.stages[guide.stage];
  const dateLabel = (day) => fullDate.format(new Date(day));
  byId("guide-label").textContent = guide.setback ? "Step-back plan" : "Current stage";
  byId("guide-title").textContent = guide.setback ? "Make today lighter" : current.title;
  byId("guide-focus").textContent = guide.setback
    ? "Bring quiet rest and essentials to the front. Review optional items and use the lighter plan you’ve chosen."
    : guide.follow_up ? "An activity went over plan. Give the next few days of check-ins time to come in before reviewing a change."
      : guide.missing_follow_ups ? "Some days after going over plan were unlogged. A few fresh check-ins will help you review the routine."
        : guide.ready && next ? "Your review is open. Look back at how the last few days went and choose whether to stay here or start the next stage."
          : current.description;
  byId("guide-items").hidden = !guide.review_items.length;
  byId("guide-items").textContent = "Above plan in your log · " + guide.review_items.join(", ");
  byId("guide-date").textContent = next ? "Earliest review · " + dateLabel(next.review_date) : "See roadmap";
  byId("stage-list").replaceChildren(...guide.stages.map((stage, index) => {
    const card = element("li");
    if (index === guide.stage) card.setAttribute("aria-current", "step");
    const label = element("p", index === guide.stage ? "Current stage"
      : stage.review_date ? "Earliest review · " + dateLabel(stage.review_date) : "Previous stage");
    label.className = "guide-label";
    card.append(label, element("h3", stage.title), element("p", stage.description),
      element("p", stage.ideas.join(" · ")));
    return card;
  }));
  const progress = guide.logged_days + " of " + guide.interval + " usual or better check-ins in this review window.";
  let followUp = "";
  if (guide.follow_up) {
    followUp = " Follow-up after going over plan is open through " + dateLabel(guide.follow_up) + ".";
  } else if (guide.missing_follow_ups) {
    followUp = " More check-ins needed after going over plan · " + guide.missing_follow_ups + ".";
  }
  byId("review-progress").textContent = progress + followUp;
  byId("stage-next").hidden = !guide.ready || !next;
  byId("stage-next").textContent = next ? "Start “" + next.title + "”" : "";
  byId("stage-back").hidden = guide.stage === 0;
  reviewForm.elements.interval.value = guide.interval;

  const items = Object.entries(view.routine);
  const activeName = view.plan?.activity.trim().toLowerCase();
  byId("suggestions").replaceChildren(...guide.suggestions.map((suggestion) => {
    const card = element("div");
    card.className = "suggestion";
    const picked = items.some(([, item]) => item.suggestion === suggestion.key
      || item.name.toLowerCase() === suggestion.name.toLowerCase())
      || activeName === suggestion.name.toLowerCase()
      || (suggestion.key === "walking" && ["walk", "walking"].includes(activeName))
      || (suggestion.key === "stretching" && ["stretch", "stretching"].includes(activeName));
    const action = picked ? element("span", "In your plan") : element("button", "Add");
    if (!picked) {
      action.type = "button";
      action.className = "secondary";
      action.setAttribute("aria-label", "Add " + suggestion.name);
      action.addEventListener("click", () => save("routine",
        { operation: "add", suggestion: suggestion.key }, "Added to your routine.", () => fillRoutineFields(true)));
    }
    card.append(element("h4", suggestion.name), element("p", suggestion.description), action);
    return card;
  }));
  byId("routine-empty").hidden = !!items.length;
  byId("routine-items").replaceChildren(...items.map(([id, item]) => {
    const form = element("form");
    form.className = "routine-row";
    const title = element("strong", item.name);
    if (guide.setback && item.kind !== "Rest") title.append(element("small", "Review for today"));
    const label = element("label", "Planned minutes");
    const input = document.createElement("input");
    input.name = "planned";
    input.type = "number";
    input.min = 0;
    input.max = 1440;
    input.value = item.planned ?? "";
    label.append(input);
    const update = element("button", "Save");
    update.className = "secondary";
    const remove = element("button", "Remove");
    remove.type = "button";
    remove.className = "secondary";
    remove.setAttribute("aria-label", "Remove " + item.name);
    form.append(title, label, update, remove);
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      save("routine", { operation: "edit", id, planned: input.value === "" ? null : Number(input.value) },
        "Routine updated.", () => fillRoutineFields(true));
    });
    remove.addEventListener("click", () => save("routine", { operation: "remove", id },
      "Removed from your routine.", () => fillRoutineFields(true)));
    return form;
  }));
}

function dayOffset(day) {
  return (Date.parse(day) - Date.parse(view.start)) / 86400000;
}

function drawChart() {
  if (!view?.plan) return;
  const width = chart.clientWidth;
  const height = chart.clientHeight;
  if (!width || !height) return;
  const scale = window.devicePixelRatio || 1;
  chart.width = Math.round(width * scale);
  chart.height = Math.round(height * scale);
  const context = chart.getContext("2d");
  context.scale(scale, scale);

  const lastDay = dayOffset(view.end);
  const today = dayOffset(view.today);
  const plan = view.plan.stepped_back ? view.plan.step_back : view.plan.limit;
  const recordedMax = view.history.map((entry) => Math.max(entry.minutes ?? 0, entry.planned ?? 0));
  const maxValue = Math.max(1, plan, view.projection ?? 0, ...recordedMax);
  const tick = Math.ceil(maxValue / 4);
  const left = 41;
  const right = width - 23;
  const top = 23;
  const bottom = height - 53;
  const x = (day) => left + (right - left) * day / lastDay;
  const y = (minutes) => bottom - (bottom - top) * minutes / (4 * tick);
  const css = getComputedStyle(chart);
  const color = (name) => css.getPropertyValue("--" + name).trim();
  function line(x1, y1, x2, y2, stroke, size = 1, dash = []) {
    context.beginPath();
    context.setLineDash(dash);
    context.strokeStyle = stroke;
    context.lineWidth = size;
    context.moveTo(x1, y1);
    context.lineTo(x2, y2);
    context.stroke();
    context.setLineDash([]);
  }

  context.fillStyle = color("chart-future");
  context.fillRect(x(today), top, x(lastDay) - x(today), bottom - top);
  context.font = '12px "Segoe UI", system-ui, sans-serif';
  context.fillStyle = color("muted");
  context.fillText("Minutes", 2, 14);
  for (let level = 0; level <= 4; level++) {
    line(left, y(tick * level), right, y(tick * level), color("chart-grid"));
    context.textAlign = "right";
    context.fillText(String(tick * level), left - 6, y(tick * level) + 4);
  }
  context.textAlign = "left";
  context.fillText(shortDate.format(new Date(view.start)), left, height - 5);
  context.textAlign = "center";
  context.fillText("Today", x(today), height - 5);
  context.textAlign = "right";
  context.fillText(shortDate.format(new Date(view.end)), width - 2, height - 5);

  line(x(today), top, x(today), bottom, color("chart-grid"));
  line(x(today), y(plan), right, y(plan), color("plan"), 2);
  if (view.projection !== null) {
    // A small offset keeps both lines legible when their values coincide.
    const forecastY = y(view.projection) - (view.projection === plan ? 3 : 0);
    line(x(today), forecastY, right, forecastY, color("estimate"), 2, [5, 4]);
  }

  let previousPlan;
  for (const entry of view.history) {
    if (entry.planned === null) continue;
    const day = dayOffset(entry.date);
    if (previousPlan && day === previousPlan.day + 1) {
      line(x(previousPlan.day), y(previousPlan.minutes), x(day), y(entry.planned), color("plan"), 1);
    }
    line(x(day) - 3, y(entry.planned), x(day) + 3, y(entry.planned), color("plan"), 2);
    previousPlan = { day, minutes: entry.planned };
  }

  let previous;
  for (const entry of view.history) {
    const day = dayOffset(entry.date);
    if (entry.minutes !== null) {
      if (previous && day === previous.day + 1) {
        line(x(previous.day), y(previous.minutes), x(day), y(entry.minutes), color("logged"), 2);
      }
      context.beginPath();
      context.fillStyle = color("logged");
      context.arc(x(day), y(entry.minutes), 3.5, 0, 2 * Math.PI);
      context.fill();
      previous = { day, minutes: entry.minutes };
    }
    if (entry.feeling === "crash" || entry.feeling === "worse") {
      const center = bottom + 15;
      context.beginPath();
      context.moveTo(x(day), center - 5);
      context.lineTo(x(day) + 5, center);
      context.lineTo(x(day), center + 5);
      context.lineTo(x(day) - 5, center);
      context.closePath();
      context.lineWidth = 2;
      context.strokeStyle = color("low");
      context.stroke();
    }
  }
}

function render() {
  byId("today-date").textContent = headingDate.format(new Date(view.today));
  byId("log-panel").hidden = false;
  byId("primary-minutes").hidden = !view.plan;
  entryForm.elements.date.min = view.start;
  entryForm.elements.date.max = view.today;
  renderGuidance();
  renderRecords();
  if (!view.plan) return;
  for (const id of ["today-panel", "trend-panel", "log-panel", "activity-link"]) byId(id).hidden = false;
  const plan = view.plan;
  byId("daily-limit").textContent = (plan.stepped_back ? plan.step_back : plan.limit) + " min";
  byId("activity-name").textContent = plan.activity;
  byId("rest-note").textContent = plan.rest;
  byId("rest-note").hidden = !plan.rest;
  let planNote = "A better day leaves your saved limit in place.";
  if (plan.stepped_back) {
    planNote = "Your lower limit stays in place until you choose to return to your usual plan.";
  } else if (view.above_before_low) {
    planNote = "You went above your saved limit in the days before a low or crash. You can review those days and choose to step back.";
  } else if (view.review) {
    planNote = "You logged a recent low or crash. Review the previous days and step back if that fits how you’re doing.";
  }
  byId("plan-note").textContent = planNote;
  byId("review-link").hidden = !view.review;
  mode.hidden = plan.step_back === null;
  mode.textContent = plan.stepped_back ? "Return to usual limit" : "Step back to " + plan.step_back + " min";
  const projection = byId("projection");
  if (view.paused) {
    projection.textContent = plan.stepped_back
      ? "Projection paused while your lower plan is active."
      : "Projection paused after a recent low or crash.";
  } else if (view.projection === null) {
    projection.textContent = "The seven-day projection appears once there are enough check-ins to see how you felt after activity.";
  } else {
    projection.textContent = view.projection + " min projected for the next seven days, based on " +
      view.sample_size + " recent entries followed by three days of usual or better check-ins.";
  }
  drawChart();
}

async function save(action, payload, message, afterSave) {
  const controls = document.querySelectorAll("#dashboard button");
  for (const control of controls) control.disabled = true;
  try {
    const result = await request(action, payload);
    if (!result) return;
    view = result;
    render();
    afterSave?.();
    report(message);
  } catch (error) {
    report(error.message || "Could not save. Try again.", true);
  } finally {
    for (const control of controls) control.disabled = false;
  }
}

function readFields(form, numeric) {
  const data = Object.fromEntries(new FormData(form));
  for (const field of numeric) data[field] = data[field] === "" ? null : Number(data[field]);
  return data;
}

planForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const creating = !view.plan;
  save("plan", readFields(planForm, ["limit", "step_back"]), "Plan saved.", () => {
    fillPlan();
    entryForm.elements.date.value ||= view.today;
    fillEntry();
    if (creating) {
      settings.open = false;
      entryForm.elements.date.focus();
    }
  });
});

entryForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const activity = view.plan?.activity ?? null;
  const payload = { ...readFields(entryForm, ["minutes"]), activity, routine: {} };
  for (const input of byId("routine-fields").querySelectorAll("input")) {
    delete payload[input.name];
    payload.routine[input.name] = input.value === "" ? null : Number(input.value);
  }
  save("entry", payload, "Check-in saved.");
});

routineForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const payload = { operation: "add", ...readFields(routineForm, ["planned"]) };
  save("routine", payload, "Added to your routine.", () => {
    routineForm.reset();
    fillRoutineFields(true);
  });
});

reviewForm.addEventListener("submit", (event) => {
  event.preventDefault();
  save("roadmap", { direction: "interval", ...readFields(reviewForm, ["interval"]) }, "Review timing saved.");
});

byId("stage-next").addEventListener("click", () => save("roadmap", { direction: "next" }, "Stage updated."));
byId("stage-back").addEventListener("click", () => save("roadmap", { direction: "back" }, "Stage updated."));

entryForm.elements.date.addEventListener("change", fillEntry);
mode.addEventListener("click", () => {
  const stepped_back = !view.plan.stepped_back;
  save("mode", { activity: view.plan.activity, stepped_back },
    stepped_back ? "Lower limit saved." : "Usual limit restored.");
});

for (const link of document.querySelectorAll("[data-edit-plan]")) {
  link.addEventListener("click", () => { settings.open = true; });
}

signOut.addEventListener("click", async () => {
  signOut.disabled = true;
  try {
    const response = await fetch("/logout", { method: "POST" });
    if (!response.ok || response.headers.get("X-Planner-App") !== "1"
        || new URL(response.url).pathname !== "/login") {
      throw new Error();
    }
    showPlanner(false);
    connection.textContent = "Opening sign-in…";
    window.location.replace("/login");
  } catch {
    report("Could not sign out. Check that the planner server is running, then try again.", true);
    signOut.disabled = false;
  }
});

new ResizeObserver(drawChart).observe(chart);

async function openPlanner() {
  try {
    const result = await request();
    if (!result) return;
    if (typeof result.username !== "string" || !/^[a-f0-9]{64}$/.test(result.write_token)) {
      throw new Error();
    }
    view = result;
    sessionWriteToken = result.write_token;
    byId("account-name").textContent = result.username;
    byId("account-name").setAttribute("aria-label", "Signed in as " + result.username);
    fillPlan();
    routineForm.elements.kind.replaceChildren(...view.roadmap.kinds.map((kind) => element("option", kind)));
    entryForm.elements.date.value = view.today;
    fillEntry();
    settings.open = !view.plan || window.location.hash === "#plan";
    render();
    showPlanner(true);
    drawChart();
  } catch {
    connection.textContent = "Could not connect to the planner. Open the address shown in the terminal after starting the planner.";
  }
}

openPlanner();

window.addEventListener("pageshow", (event) => {
  if (event.persisted) window.location.reload();
});
