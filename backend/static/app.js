const dropZone = document.getElementById("drop-zone");
const fileInput = document.getElementById("file-input");
const uploadStatus = document.getElementById("upload-status");
const taskList = document.getElementById("task-list");
const emptyState = document.getElementById("empty-state");
const modalOverlay = document.getElementById("modal-overlay");
const modalBody = document.getElementById("modal-body");
const modalClose = document.getElementById("modal-close");
const filterBtns = document.querySelectorAll(".filter-btn");

let allTasks = [];
let currentFilter = "all";

// ---------- Upload ----------
dropZone.addEventListener("click", () => fileInput.click());
dropZone.addEventListener("dragover", (e) => { e.preventDefault(); dropZone.classList.add("dragover"); });
dropZone.addEventListener("dragleave", () => dropZone.classList.remove("dragover"));
dropZone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropZone.classList.remove("dragover");
  if (e.dataTransfer.files.length) uploadFile(e.dataTransfer.files[0]);
});
fileInput.addEventListener("change", () => {
  if (fileInput.files.length) uploadFile(fileInput.files[0]);
});

async function uploadFile(file) {
  showStatus(`Analyzing "${file.name}"…`, false);
  const formData = new FormData();
  formData.append("file", file);
  try {
    const res = await fetch("/api/upload", { method: "POST", body: formData });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Upload failed");
    }
    const task = await res.json();
    showStatus(`✅ Extracted: "${task.title}"`, false);
    fileInput.value = "";
    await loadTasks();
  } catch (e) {
    showStatus(`❌ ${e.message}`, true);
  }
}

function showStatus(msg, isError) {
  uploadStatus.textContent = msg;
  uploadStatus.classList.remove("hidden");
  uploadStatus.classList.toggle("error", isError);
  clearTimeout(showStatus._t);
  showStatus._t = setTimeout(() => uploadStatus.classList.add("hidden"), 5000);
}

// ---------- Task list ----------
async function loadTasks() {
  const res = await fetch("/api/tasks");
  allTasks = await res.json();
  renderTasks();
}

function renderTasks() {
  let tasks = allTasks;
  if (currentFilter === "high") tasks = tasks.filter((t) => t.priority === "high");
  else if (currentFilter === "event") tasks = tasks.filter((t) => t.category === "event");
  else if (currentFilter === "bill") tasks = tasks.filter((t) => t.category === "bill");

  taskList.innerHTML = "";
  emptyState.classList.toggle("hidden", tasks.length !== 0);

  for (const task of tasks) {
    const card = document.createElement("div");
    card.className = "task-card";

    const check = document.createElement("div");
    check.className = "task-check" + (task.completed ? " done" : "");
    check.addEventListener("click", (e) => { e.stopPropagation(); toggleComplete(task); });

    const main = document.createElement("div");
    main.className = "task-main";

    const title = document.createElement("p");
    title.className = "task-title" + (task.completed ? " done" : "");
    title.textContent = task.title;

    const meta = document.createElement("div");
    meta.className = "task-meta";
    meta.innerHTML = `
      <span class="badge ${task.priority}">${task.priority}</span>
      <span class="badge category">${task.category}</span>
      ${task.event_date ? `<span>📅 ${task.event_date}</span>` : ""}
      ${task.event_time ? `<span>🕒 ${task.event_time}</span>` : ""}
      ${task.calendar_event_link ? `<span>✅ In calendar</span>` : ""}
    `;

    main.appendChild(title);
    main.appendChild(meta);
    card.appendChild(check);
    card.appendChild(main);
    card.addEventListener("click", () => openModal(task));
    taskList.appendChild(card);
  }
}

filterBtns.forEach((btn) => {
  btn.addEventListener("click", () => {
    filterBtns.forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    currentFilter = btn.dataset.filter;
    renderTasks();
  });
});

async function toggleComplete(task) {
  await fetch(`/api/tasks/${task.id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ completed: !task.completed }),
  });
  await loadTasks();
}

// ---------- Modal (view/edit + calendar) ----------
function openModal(task) {
  modalBody.innerHTML = `
    <h3>Edit Task</h3>
    <label>Title</label>
    <input id="f-title" value="${escapeHtml(task.title)}" />

    <label>Description</label>
    <textarea id="f-desc">${escapeHtml(task.description || "")}</textarea>

    <div style="display:flex; gap:10px;">
      <div style="flex:1">
        <label>Date</label>
        <input id="f-date" type="date" value="${task.event_date || ""}" />
      </div>
      <div style="flex:1">
        <label>Time</label>
        <input id="f-time" type="time" value="${task.event_time || ""}" />
      </div>
    </div>

    <div style="display:flex; gap:10px;">
      <div style="flex:1">
        <label>Priority</label>
        <select id="f-priority">
          ${["low", "medium", "high"].map(p => `<option value="${p}" ${task.priority === p ? "selected" : ""}>${p}</option>`).join("")}
        </select>
      </div>
      <div style="flex:1">
        <label>Category</label>
        <select id="f-category">
          ${["task", "event", "bill", "reminder"].map(c => `<option value="${c}" ${task.category === c ? "selected" : ""}>${c}</option>`).join("")}
        </select>
      </div>
    </div>

    ${task.raw_text ? `<label>Extracted text (${task.ai_engine === "openai" ? "AI" : "rule-based"})</label>
    <div class="raw-text-box">${escapeHtml(task.raw_text)}</div>` : ""}

    <div class="modal-actions">
      <button class="btn btn-primary" id="save-btn">Save</button>
      <button class="btn btn-secondary" id="calendar-btn">${task.calendar_event_link ? "Update in Calendar" : "Add to Google Calendar"}</button>
      <button class="btn btn-danger" id="delete-btn">Delete</button>
    </div>
    ${task.calendar_event_link ? `<p style="margin-top:10px;"><a href="${task.calendar_event_link}" target="_blank">View in Google Calendar →</a></p>` : ""}
  `;
  modalOverlay.classList.remove("hidden");

  document.getElementById("save-btn").addEventListener("click", () => saveTask(task.id));
  document.getElementById("calendar-btn").addEventListener("click", () => addToCalendar(task.id));
  document.getElementById("delete-btn").addEventListener("click", () => deleteTask(task.id));
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

modalClose.addEventListener("click", () => modalOverlay.classList.add("hidden"));
modalOverlay.addEventListener("click", (e) => { if (e.target === modalOverlay) modalOverlay.classList.add("hidden"); });

async function saveTask(id) {
  const body = {
    title: document.getElementById("f-title").value,
    description: document.getElementById("f-desc").value,
    event_date: document.getElementById("f-date").value || null,
    event_time: document.getElementById("f-time").value || null,
    priority: document.getElementById("f-priority").value,
    category: document.getElementById("f-category").value,
  };
  await fetch(`/api/tasks/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  modalOverlay.classList.add("hidden");
  await loadTasks();
}

async function addToCalendar(id) {
  try {
    const res = await fetch(`/api/tasks/${id}/calendar`, { method: "POST" });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Could not add to calendar");
    }
    modalOverlay.classList.add("hidden");
    await loadTasks();
    showStatus("✅ Added to Google Calendar", false);
  } catch (e) {
    showStatus(`❌ ${e.message}`, true);
  }
}

async function deleteTask(id) {
  if (!confirm("Delete this task?")) return;
  await fetch(`/api/tasks/${id}`, { method: "DELETE" });
  modalOverlay.classList.add("hidden");
  await loadTasks();
}

// ---------- Init ----------
loadTasks();
