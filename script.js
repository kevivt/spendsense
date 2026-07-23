const API_BASE = "/api";

const grandTotalEl = document.getElementById("grand-total");
const monthSelect = document.getElementById("month-select");
const syncBtn = document.getElementById("sync-btn");
const platformCardsEl = document.getElementById("platform-cards");
const ledgerEmptyEl = document.getElementById("ledger-empty");
const chatLog = document.getElementById("chat-log");
const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");
const chatSend = document.querySelector(".chat-send");

// The API is stateless - this browser-side array is the only place
// conversation history lives, sent with each /api/chat request so the
// agent has context for follow-ups (e.g. "what about May?"). Resets on
// page refresh, which is an intentional, simple default for a
// single-user tool - no server-side session management needed.
let conversationHistory = [];

function formatRupees(amount) {
  return "₹ " + Number(amount).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function lastNMonths(n) {
  const months = [];
  const now = new Date();
  for (let i = 0; i < n; i++) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    const ym = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
    const label = d.toLocaleString("default", { month: "short", year: "numeric" });
    months.push({ ym, label });
  }
  return months;
}

function populateMonthSelect() {
  const months = lastNMonths(12);
  monthSelect.innerHTML = months
    .map((m) => `<option value="${m.ym}">${m.label}</option>`)
    .join("");
}

async function loadSummary(yearMonth) {
  platformCardsEl.innerHTML = "";
  ledgerEmptyEl.hidden = true;

  try {
    const res = await fetch(`${API_BASE}/summary?year_month=${encodeURIComponent(yearMonth)}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    grandTotalEl.textContent = formatRupees(data.grand_total || 0);

    const platforms = Object.entries(data.platforms || {});
    if (platforms.length === 0) {
      ledgerEmptyEl.hidden = false;
      return;
    }

    for (const [platform, stats] of platforms) {
      const card = document.createElement("div");
      card.className = "platform-card";

      const itemRows = (stats.top_items || [])
        .map(
          ([name, count]) =>
            `<div class="item-row"><span>${escapeHtml(name)}</span><span class="leader"></span><span class="item-count">×${count}</span></div>`
        )
        .join("");

      card.innerHTML = `
        <div class="platform-card-header">
          <span class="platform-name">${escapeHtml(platform)}</span>
          <span class="platform-total">${formatRupees(stats.total_spent)}</span>
        </div>
        <div class="platform-meta">${stats.order_count} order${stats.order_count === 1 ? "" : "s"}</div>
        ${itemRows}
      `;
      platformCardsEl.appendChild(card);
    }
  } catch (err) {
    grandTotalEl.textContent = "₹ ---.--";
    ledgerEmptyEl.hidden = false;
    ledgerEmptyEl.querySelector("p").textContent = "Couldn't load summary.";
    console.error(err);
  }
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function appendChatMessage(role, text) {
  const msg = document.createElement("div");
  msg.className = `chat-msg ${role}`;
  msg.innerHTML = `<span class="chat-tag">${role === "user" ? "YOU" : "AGENT"}</span><p></p>`;
  msg.querySelector("p").textContent = text;
  chatLog.appendChild(msg);
  chatLog.scrollTop = chatLog.scrollHeight;
  return msg;
}

chatForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const message = chatInput.value.trim();
  if (!message) return;

  appendChatMessage("user", message);
  chatInput.value = "";
  chatInput.disabled = true;
  chatSend.disabled = true;

  const thinkingMsg = appendChatMessage("agent", "…thinking…");

  try {
    const res = await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, history: conversationHistory }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
    thinkingMsg.querySelector("p").textContent = data.answer;

    // Only the clean user/assistant text goes into history - no tool-call
    // scaffolding, so this stays small and simple across turns
    conversationHistory.push({ role: "user", content: message });
    conversationHistory.push({ role: "assistant", content: data.answer });
  } catch (err) {
    thinkingMsg.querySelector("p").textContent = "Something went wrong reaching the agent. Is the server running?";
    console.error(err);
  } finally {
    chatInput.disabled = false;
    chatSend.disabled = false;
    chatInput.focus();
  }
});

syncBtn.addEventListener("click", async () => {
  syncBtn.disabled = true;
  syncBtn.textContent = "SYNCING…";

  try {
    const res = await fetch(`${API_BASE}/sync`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ max_results: 20 }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    await loadSummary(monthSelect.value);
  } catch (err) {
    console.error(err);
  } finally {
    syncBtn.disabled = false;
    syncBtn.textContent = "SYNC";
  }
});

monthSelect.addEventListener("change", () => loadSummary(monthSelect.value));

populateMonthSelect();
loadSummary(monthSelect.value);
