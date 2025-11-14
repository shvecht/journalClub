// Journal Club front end logic

const THEME_STORAGE_KEY = "jc-theme-preference";

let sessions = [];
let filteredSessions = [];
let viewMode = "sessions";

const state = {
  month: "all",
  journal: "all",
  search: ""
};

// Cache DOM references
const sessionsListEl = document.getElementById("sessionsList");
const timelineViewEl = document.getElementById("timelineView");
const cardDeckViewEl = document.getElementById("cardDeckView");

const yearFilterEl = document.getElementById("yearFilter");
const journalFilterEl = document.getElementById("journalFilter");
const searchInputEl = document.getElementById("searchInput");

const statSessionsEl = document.getElementById("statSessions");
const statJournalsEl = document.getElementById("statJournals");
const statLatestYearEl = document.getElementById("statLatestYear");

const themeToggleBtn = document.getElementById("themeToggle");
const topNavEl = document.querySelector(".top-nav");
const viewToggleBtns = document.querySelectorAll(".view-toggle-btn");

document.addEventListener("DOMContentLoaded", () => {
  initTheme();
  attachEventHandlers();
  loadSessions();
});

function attachEventHandlers() {
  if (yearFilterEl) {
    yearFilterEl.addEventListener("change", () => {
      state.month = yearFilterEl.value;
      applyFiltersAndRender();
    });
  }

  if (journalFilterEl) {
    journalFilterEl.addEventListener("change", () => {
      state.journal = journalFilterEl.value;
      applyFiltersAndRender();
    });
  }

  if (searchInputEl) {
    searchInputEl.addEventListener("input", () => {
      const q = searchInputEl.value.trim().toLowerCase();
      state.search = q;
      applyFiltersAndRender();
    });
  }

  if (themeToggleBtn) {
    themeToggleBtn.addEventListener("click", toggleTheme);
  }

  if (viewToggleBtns && viewToggleBtns.length) {
    viewToggleBtns.forEach((btn) => {
      btn.addEventListener("click", () => {
        const view = btn.getAttribute("data-view");
        if (!view || view === viewMode) return;
        viewMode = view;
        updateViewModeButtons();
        updateViewVisibility();
      });
    });
  }

  window.addEventListener("scroll", handleScroll);
}

function handleScroll() {
  if (!topNavEl) return;
  const offset = window.scrollY || document.documentElement.scrollTop || 0;
  if (offset > 12) {
    topNavEl.classList.add("nav-scrolled");
  } else {
    topNavEl.classList.remove("nav-scrolled");
  }
}

/* ---------- Theme handling ---------- */

function initTheme() {
  const saved = localStorage.getItem(THEME_STORAGE_KEY);
  const prefersDark = window.matchMedia &&
    window.matchMedia("(prefers-color-scheme: dark)").matches;

  const initialTheme = saved || (prefersDark ? "dark" : "light");
  setTheme(initialTheme);
}

function setTheme(mode) {
  const theme = mode === "dark" ? "dark" : "light";
  document.documentElement.setAttribute("data-theme", theme);
  localStorage.setItem(THEME_STORAGE_KEY, theme);
}

function toggleTheme() {
  const current =
    document.documentElement.getAttribute("data-theme") || "light";
  const next = current === "dark" ? "light" : "dark";
  setTheme(next);
}

/* ---------- Data loading ---------- */

async function loadSessions() {
  if (!sessionsListEl) return;

  try {
    const res = await fetch("data/journal_club.json");
    if (!res.ok) {
      throw new Error("Unable to load journal club data");
    }
    const data = await res.json();
    sessions = normaliseSessions(data);
    sessions.sort((a, b) => b.dateObj - a.dateObj);

    buildFilterOptions();
    updateStats();
    applyFiltersAndRender();
  } catch (err) {
    showError(err);
  }
}

function normaliseSessions(raw) {
  if (!Array.isArray(raw)) return [];

  return raw
    .map((item) => {
      const dateObj = new Date(item.date);
      const year = Number.isFinite(dateObj.getTime())
        ? dateObj.getFullYear()
        : null;
      const monthIndex = Number.isFinite(dateObj.getTime())
        ? dateObj.getMonth()
        : null;

      return {
        ...item,
        dateObj,
        year,
        monthIndex
      };
    })
    .filter((s) => s.year !== null && s.monthIndex !== null);
}

/* ---------- Filters and search ---------- */

function buildFilterOptions() {
  const months = Array.from(
    new Set(
      sessions
        .map((s) => s.monthIndex)
        .filter((m) => m !== null && m !== undefined)
    )
  ).sort((a, b) => a - b);

  fillSelect(yearFilterEl, ["all", ...months], (val) =>
    val === "all"
      ? "All months"
      : new Date(2000, Number(val), 1).toLocaleString(undefined, {
          month: "long"
        })
  );

  const journals = Array.from(
    new Set(sessions.map((s) => s.journal).filter(Boolean))
  ).sort((a, b) => a.localeCompare(b));

  fillSelect(journalFilterEl, ["all", ...journals], (val) =>
    val === "all" ? "All journals" : String(val)
  );
}

function fillSelect(selectEl, values, labelFn) {
  if (!selectEl || !Array.isArray(values)) return;
  const previous = selectEl.value || "all";
  selectEl.innerHTML = "";

  values.forEach((val) => {
    const opt = document.createElement("option");
    opt.value = String(val);
    opt.textContent = labelFn ? labelFn(val) : String(val);
    if (String(val) === previous) opt.selected = true;
    selectEl.appendChild(opt);
  });
}

function applyFiltersAndRender() {
  filteredSessions = sessions.filter((session) => {
    if (
      state.month !== "all" &&
      String(session.monthIndex) !== String(state.month)
    ) {
      return false;
    }
    if (
      state.journal !== "all" &&
      session.journal &&
      session.journal !== state.journal
    ) {
      return false;
    }
    if (state.search) {
      const haystack = [
        session.title,
        session.journal,
        session.authors,
        session.notes,
        session.abstract
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();

      if (!haystack.includes(state.search)) return false;
    }

    return true;
  });

  renderCards();
  renderTimeline();
  renderCardDeck();
  updateViewVisibility();
}

/* ---------- Rendering: cards ---------- */

function renderCards() {
  if (!sessionsListEl) return;

  sessionsListEl.innerHTML = "";

  if (!filteredSessions.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.innerHTML = "<p>No sessions match your filters yet.</p>";
    sessionsListEl.appendChild(empty);
    return;
  }

  filteredSessions.forEach((session, index) => {
    const card = document.createElement("article");
    card.className = "session-card";
    const delay = Math.min(index * 0.035, 0.35);
    card.style.animationDelay = delay.toFixed(3) + "s";

    const title = escapeHtml(session.title || "Untitled session");
    const journal = escapeHtml(session.journal || "");
    const authors = escapeHtml(session.authors || "");
    const notes = escapeHtml(session.notes || "");
    const abstract = escapeHtml(session.abstract || "");
    const hasBody = Boolean(notes || abstract);

    card.innerHTML = `
      <header class="session-header">
        <div class="session-date">
          <span class="session-date-day">${formatDay(session.dateObj)}</span>
          <span class="session-date-month">${formatMonthShort(
            session.dateObj
          )}</span>
          <span class="session-date-year">${session.year}</span>
        </div>
        <div class="session-meta">
          <h2 class="session-title">${title}</h2>
          ${
            journal
              ? `<p class="session-journal">${journal}</p>`
              : `<p class="session-journal">&nbsp;</p>`
          }
          ${
            authors
              ? `<p class="session-authors">${authors}</p>`
              : ""
          }
        </div>
      </header>

      ${
        hasBody
          ? `<div class="session-body">
              ${
                notes
                  ? `<p class="session-notes">${notes}</p>`
                  : ""
              }
              ${
                abstract
                  ? `<p class="session-abstract">${abstract}</p>`
                  : ""
              }
            </div>`
          : ""
      }

      <footer class="session-footer">
        <div class="session-links">
          ${
            session.pmid
              ? `<a href="https://pubmed.ncbi.nlm.nih.gov/${encodeURIComponent(
                  session.pmid
                )}/"
                    target="_blank"
                    rel="noopener"
                    class="chip chip-primary">
                  PMID ${escapeHtml(session.pmid)}
                </a>`
              : ""
          }
          ${
            session.pdf
              ? `<a href="${escapeAttr(
                  session.pdf
                )}" target="_blank" rel="noopener" class="chip chip-soft">
                  PDF
                </a>`
              : ""
          }
        </div>
        <span class="session-tag">${session.year}</span>
      </footer>
    `;

    sessionsListEl.appendChild(card);
  });
}

/* ---------- Rendering: card deck (playing cards) ---------- */

function renderCardDeck() {
  if (!cardDeckViewEl) return;

  cardDeckViewEl.innerHTML = "";

  if (!filteredSessions.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.innerHTML = "<p>No sessions match your filters yet.</p>";
    cardDeckViewEl.appendChild(empty);
    return;
  }

  filteredSessions.forEach((session, index) => {
    const card = document.createElement("article");
    card.className = "playing-card";
    const delay = Math.min(index * 0.035, 0.35);
    card.style.animationDelay = delay.toFixed(3) + "s";

    const title = escapeHtml(session.title || "Untitled session");
    const journal = escapeHtml(session.journal || "");
    const day = formatDay(session.dateObj);
    const month = formatMonthShort(session.dateObj);
    const year = session.year != null ? String(session.year) : "";

    card.dataset.day = day;
    card.dataset.month = month;
    card.dataset.year = year;
    const ariaBits = [title];
    if (journal) ariaBits.push(journal);
    ariaBits.push(`${day} ${month}${year ? ` ${year}` : ""}`.trim());
    card.setAttribute("aria-label", ariaBits.join(", "));

    card.innerHTML = `
      <div class="playing-card-inner">
        <header class="playing-card-header">
          <span class="playing-card-date">${day} ${month}</span>
          <span class="playing-card-year">${year}</span>
        </header>
        <div class="playing-card-body">
          <h2 class="playing-card-title">${title}</h2>
          ${
            journal
              ? `<p class="playing-card-journal">${journal}</p>`
              : ""
          }
        </div>
        <footer class="playing-card-footer">
          ${
            session.pmid
              ? `<span class="playing-card-meta">PMID ${escapeHtml(
                  session.pmid
                )}</span>`
              : ""
          }
        </footer>
      </div>
    `;

    cardDeckViewEl.appendChild(card);
  });
}

/* ---------- Rendering: timeline ---------- */

function renderTimeline() {
  if (!timelineViewEl) return;
  timelineViewEl.innerHTML = "";

  if (!filteredSessions.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.innerHTML = "<p>No sessions match your filters yet.</p>";
    timelineViewEl.appendChild(empty);
    return;
  }

  const mapByYear = new Map();
  filteredSessions.forEach((s) => {
    if (!mapByYear.has(s.year)) mapByYear.set(s.year, []);
    mapByYear.get(s.year).push(s);
  });

  const yearsSorted = Array.from(mapByYear.keys()).sort((a, b) => b - a);

  yearsSorted.forEach((year) => {
    const yearBlock = document.createElement("section");
    yearBlock.className = "timeline-year";

    const yearLabel = document.createElement("h2");
    yearLabel.className = "timeline-year-label";
    yearLabel.textContent = String(year);
    yearBlock.appendChild(yearLabel);

    const list = document.createElement("ol");
    list.className = "timeline-list";

    mapByYear.get(year).forEach((session, index) => {
      const item = document.createElement("li");
      item.className = "timeline-item";
      const delay = Math.min(index * 0.035, 0.35);
      item.style.animationDelay = delay.toFixed(3) + "s";

      const title = escapeHtml(session.title || "Untitled session");
      const journal = escapeHtml(session.journal || "");

      item.innerHTML = `
        <div class="timeline-dot"></div>
        <div class="timeline-content">
          <div class="timeline-date">${formatDateLong(session.dateObj)}</div>
          <div class="timeline-title">${title}</div>
          ${
            journal
              ? `<div class="timeline-sub">
                  <span>${journal}</span>
                </div>`
              : ""
          }
        </div>
      `;

      list.appendChild(item);
    });

    yearBlock.appendChild(list);
    timelineViewEl.appendChild(yearBlock);
  });
}

/* ---------- View mode visibility ---------- */

function updateViewVisibility() {
  if (!sessionsListEl || !timelineViewEl) return;

  if (viewMode === "timeline") {
    sessionsListEl.classList.add("hidden");
    if (cardDeckViewEl) cardDeckViewEl.classList.add("hidden");
    timelineViewEl.classList.remove("hidden");
  } else if (viewMode === "cards") {
    sessionsListEl.classList.add("hidden");
    timelineViewEl.classList.add("hidden");
    if (cardDeckViewEl) cardDeckViewEl.classList.remove("hidden");
  } else {
    // sessions list
    sessionsListEl.classList.remove("hidden");
    timelineViewEl.classList.add("hidden");
    if (cardDeckViewEl) cardDeckViewEl.classList.add("hidden");
  }
}

function updateViewModeButtons() {
  if (!viewToggleBtns) return;
  viewToggleBtns.forEach((btn) => {
    const view = btn.getAttribute("data-view");
    const isActive = view === viewMode;
    btn.classList.toggle("active", isActive);
    btn.setAttribute("aria-selected", String(isActive));
  });
}

/* ---------- Stats / counters ---------- */

function updateStats() {
  if (!sessions.length) {
    setCounter(statSessionsEl, 0);
    setCounter(statJournalsEl, 0);
    if (statLatestYearEl) statLatestYearEl.textContent = "–";
    return;
  }

  const totalSessions = sessions.length;
  const totalJournals = new Set(
    sessions.map((s) => s.journal).filter(Boolean)
  ).size;
  const latestYear = Math.max(...sessions.map((s) => s.year));

  animateCounter(statSessionsEl, totalSessions);
  animateCounter(statJournalsEl, totalJournals);
  if (statLatestYearEl) statLatestYearEl.textContent = String(latestYear);
}

function setCounter(el, value) {
  if (!el) return;
  el.textContent = String(value);
}

function animateCounter(el, target, duration = 800) {
  if (!el) return;
  const startVal = Number(el.textContent.replace(/\D/g, "")) || 0;
  const startTime = performance.now();
  const from = startVal;
  const to = target;

  function frame(now) {
    const elapsed = now - startTime;
    const t = Math.min(elapsed / duration, 1);
    const eased = easeOutQuad(t);
    const value = Math.round(from + (to - from) * eased);
    el.textContent = String(value);
    if (t < 1) {
      requestAnimationFrame(frame);
    }
  }

  requestAnimationFrame(frame);
}

function easeOutQuad(t) {
  return t * (2 - t);
}

/* ---------- Utilities ---------- */

function formatDay(date) {
  if (!(date instanceof Date)) return "";
  return String(date.getDate()).padStart(2, "0");
}

function formatMonthShort(date) {
  if (!(date instanceof Date)) return "";
  return date.toLocaleString(undefined, { month: "short" });
}

function formatDateLong(date) {
  if (!(date instanceof Date)) return "";
  return date.toLocaleDateString(undefined, {
    day: "2-digit",
    month: "short",
    year: "numeric"
  });
}

function escapeHtml(str) {
  if (str == null) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function escapeAttr(str) {
  return escapeHtml(str);
}

function showError(err) {
  if (!sessionsListEl) return;
  sessionsListEl.innerHTML = "";
  const box = document.createElement("div");
  box.className = "empty-state";
  box.innerHTML = `
    <p>There was a problem loading the journal club data.</p>
    <p style="font-size:0.78rem; color:var(--danger); margin-top:0.4rem;">
      ${escapeHtml(err && err.message ? err.message : "Unknown error")}
    </p>
  `;
  sessionsListEl.appendChild(box);
}
