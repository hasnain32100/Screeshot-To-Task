/* =========================================================
   SCREENSHOT-TO-TASK
   FRONTEND APPLICATION
========================================================= */

const API = "http://127.0.0.1:8000";


// =========================================================
// DOM ELEMENTS
// =========================================================

const fileInput = document.getElementById("file");
const dropZone = document.getElementById("drop");
const analyzeButton = document.getElementById("analyze");
const textInput = document.getElementById("txt");
const statusBox = document.getElementById("status");
const resultBox = document.getElementById("result");
const tasksBox = document.getElementById("tasks");
const refreshButton = document.getElementById("refresh");
const calendarButton = document.getElementById("cal");


// Stores the latest AI result
let latestResult = null;


// =========================================================
// UTILITY
// =========================================================

function escapeHtml(value) {

    if (value === null || value === undefined) {
        return "";
    }

    return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}


function setStatus(message, type = "") {

    statusBox.textContent = message;

    statusBox.className = "status";

    if (type) {
        statusBox.classList.add(type);
    }
}


function formatValue(value) {

    if (
        value === null ||
        value === undefined ||
        value === ""
    ) {
        return "Not detected";
    }

    if (typeof value === "object") {
        try {
            return JSON.stringify(value, null, 2);
        } catch {
            return String(value);
        }
    }

    return String(value);
}


function capitalize(value) {

    if (!value) {
        return "";
    }

    return String(value)
        .charAt(0)
        .toUpperCase() +
        String(value).slice(1);
}


// =========================================================
// FILE SELECTION
// =========================================================

fileInput.addEventListener("change", function () {

    if (!this.files || !this.files.length) {
        return;
    }

    const file = this.files[0];

    if (file.size > 15 * 1024 * 1024) {

        setStatus(
            "File is too large. Maximum size is 15MB."
        );

        this.value = "";

        return;
    }

    setStatus(
        `Selected: ${file.name}`
    );

});


// =========================================================
// DRAG & DROP
// =========================================================

["dragenter", "dragover"].forEach(eventName => {

    dropZone.addEventListener(eventName, event => {

        event.preventDefault();

        dropZone.classList.add("dragover");

    });

});


["dragleave", "drop"].forEach(eventName => {

    dropZone.addEventListener(eventName, event => {

        event.preventDefault();

        dropZone.classList.remove("dragover");

    });

});


dropZone.addEventListener("drop", event => {

    const files = event.dataTransfer.files;

    if (!files.length) {
        return;
    }

    const file = files[0];

    if (file.size > 15 * 1024 * 1024) {

        setStatus(
            "File is too large. Maximum size is 15MB."
        );

        return;
    }

    fileInput.files = files;

    setStatus(
        `Selected: ${file.name}`
    );

});


// =========================================================
// ANALYZE BUTTON
// =========================================================

analyzeButton.addEventListener(
    "click",
    analyzeInput
);


async function analyzeInput() {

    const file =
        fileInput.files &&
        fileInput.files[0];

    const text =
        textInput.value.trim();


    if (!file && !text) {

        setStatus(
            "Please upload a file or paste some text first."
        );

        return;
    }


    analyzeButton.disabled = true;

    analyzeButton.innerHTML =
        `<span class="btn-icon">◌</span>
         Analyzing...
         <span class="btn-arrow">...</span>`;


    setStatus(
        "AI is analyzing your information..."
    );


    try {

        let data;


        // -------------------------------------------------
        // FILE ANALYSIS
        // -------------------------------------------------

        if (file) {

            const formData = new FormData();

            formData.append("file", file);


            const response = await fetch(
                `${API}/api/analyze`,
                {
                    method: "POST",
                    body: formData
                }
            );


            if (!response.ok) {

                const errorText =
                    await response.text();

                throw new Error(
                    errorText ||
                    `Server error: ${response.status}`
                );
            }


            data = await response.json();

        }


        // -------------------------------------------------
        // TEXT ANALYSIS
        // -------------------------------------------------

        else {

            const response = await fetch(
                `${API}/api/analyze-text`,
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify({
                        text: text
                    })
                }
            );


            if (!response.ok) {

                const errorText =
                    await response.text();

                throw new Error(
                    errorText ||
                    `Server error: ${response.status}`
                );
            }


            data = await response.json();

        }


        latestResult = data;


        renderResult(data);


        setStatus(
            "Analysis completed successfully."
        );


    } catch (error) {

        console.error(error);

        setStatus(
            "Error: " +
            (error.message || "Unable to analyze.")
        );

    } finally {

        analyzeButton.disabled = false;

        analyzeButton.innerHTML =
            `<span class="btn-icon">✦</span>
             Analyze with AI
             <span class="btn-arrow">→</span>`;

    }

}


// =========================================================
// RENDER RESULT
// =========================================================

function renderResult(data) {

    if (!data) {
        return;
    }


    const extraction =
        data.extraction || {};


    const agent =
        data.agent || {};


    const title =
        extraction.title ||
        extraction.name ||
        "Extracted Information";


    const summary =
        extraction.summary ||
        extraction.description ||
        "Information extracted from your uploaded content.";


    resultBox.classList.remove(
        "empty-result"
    );


    let fieldsHtml = "";


    const fieldDefinitions = [

        ["task_type", "Type"],
        ["category", "Category"],
        ["date", "Date"],
        ["event_date", "Event Date"],
        ["time", "Time"],
        ["event_time", "Event Time"],
        ["location", "Location"],
        ["person", "Person"],
        ["organization", "Organization"],
        ["phone", "Phone"],
        ["email", "Email"],
        ["url", "URL"],
        ["amount", "Amount"],
        ["currency", "Currency"],
        ["priority", "Priority"]

    ];


    const usedKeys = new Set();


    fieldDefinitions.forEach(
        ([key, label]) => {

            if (
                extraction[key] !== undefined &&
                extraction[key] !== null &&
                extraction[key] !== ""
            ) {

                fieldsHtml += createInfoItem(
                    label,
                    extraction[key]
                );

                usedKeys.add(key);
            }

        }
    );


    // -----------------------------------------------------
    // Additional AI fields
    // -----------------------------------------------------

    Object.entries(extraction)
        .forEach(([key, value]) => {

            if (
                usedKeys.has(key) ||
                [
                    "title",
                    "summary",
                    "description",
                    "raw_text",
                    "raw_extraction",
                    "tasks"
                ].includes(key)
            ) {
                return;
            }


            if (
                value === null ||
                value === undefined ||
                value === ""
            ) {
                return;
            }


            fieldsHtml += createInfoItem(
                formatLabel(key),
                value
            );

        });


    // -----------------------------------------------------
    // Agent information
    // -----------------------------------------------------

    let agentHtml = "";


    if (Object.keys(agent).length) {

        const agentText =
            agent.action ||
            agent.decision ||
            agent.intent ||
            agent.reason ||
            "";


        if (agentText) {

            agentHtml = `
                <div class="description-box">

                    <strong>
                        ✦ AI Agent Decision
                    </strong>

                    <p>
                        ${escapeHtml(
                            formatValue(agentText)
                        )}
                    </p>

                </div>
            `;

        }

    }


    // -----------------------------------------------------
    // Raw OCR
    // -----------------------------------------------------

    let ocrHtml = "";


    if (data.raw_text) {

        ocrHtml = `
            <details class="ocr-box">

                <summary>
                    View OCR / extracted source text
                </summary>

                <pre>${escapeHtml(
                    data.raw_text
                )}</pre>

            </details>
        `;

    }


    // -----------------------------------------------------
    // Result HTML
    // -----------------------------------------------------

    resultBox.innerHTML = `

        <div class="result-title">

            <div>

                <span class="mini-label">
                    AI EXTRACTION
                </span>

                <h3>
                    ${escapeHtml(
                        formatValue(title)
                    )}
                </h3>

                <p>
                    ${escapeHtml(
                        formatValue(
                            data.source_type ||
                            "AI analyzed content"
                        )
                    )}
                </p>

            </div>

        </div>


        <div class="result-actions">

            <button
                class="result-action-btn pdf-btn"
                type="button"
                onclick="saveResultAsPDF()"
            >
                📄 Save as PDF
            </button>


            <button
                class="result-action-btn"
                type="button"
                onclick="copyExtractedInfo()"
            >
                📋 Copy
            </button>


            <button
                class="result-action-btn save-btn"
                type="button"
                onclick="saveCurrentTask()"
            >
                💾 Save Task
            </button>


            ${
                extraction.date ||
                extraction.event_date
                    ? `
                    <button
                        class="result-action-btn calendar-btn"
                        type="button"
                        onclick="createCalendarEvent()"
                    >
                        📅 Calendar
                    </button>
                    `
                    : ""
            }

        </div>


        <div class="result-grid">

            ${fieldsHtml}

        </div>


        ${
            summary
                ? `
                <div class="description-box">

                    <strong>
                        AI Summary
                    </strong>

                    <p>
                        ${escapeHtml(
                            formatValue(summary)
                        )}
                    </p>

                </div>
                `
                : ""
        }


        ${agentHtml}

        ${ocrHtml}

    `;


    // Scroll result into view on mobile
    if (window.innerWidth <= 600) {

        setTimeout(() => {

            resultBox.scrollIntoView({
                behavior: "smooth",
                block: "start"
            });

        }, 200);

    }

}


// =========================================================
// CREATE INFORMATION FIELD
// =========================================================

function createInfoItem(label, value) {

    return `
        <div class="info-item">

            <span class="info-label">
                ${escapeHtml(label)}
            </span>

            <span class="info-value">
                ${escapeHtml(
                    formatValue(value)
                )}
            </span>

        </div>
    `;
}


function formatLabel(key) {

    return String(key)
        .replace(/_/g, " ")
        .replace(/\b\w/g, char =>
            char.toUpperCase()
        );
}


// =========================================================
// COPY INFORMATION
// =========================================================

async function copyExtractedInfo() {

    if (!latestResult) {

        alert(
            "There is no extracted information to copy."
        );

        return;
    }


    const text =
        buildExportText(latestResult);


    try {

        await navigator.clipboard.writeText(text);

        setStatus(
            "Extracted information copied."
        );

    } catch (error) {

        console.error(error);

        alert(
            "Unable to copy information."
        );

    }

}


// =========================================================
// BUILD EXPORT TEXT
// =========================================================

function buildExportText(data) {

    const extraction =
        data.extraction || {};


    const agent =
        data.agent || {};


    let output = "";


    output +=
        "SCREENSHOT-TO-TASK\n";

    output +=
        "AI LIFE ORGANIZER\n";

    output +=
        "==============================\n\n";


    output +=
        `Title: ${
            formatValue(
                extraction.title ||
                "Extracted Information"
            )
        }\n\n`;


    Object.entries(extraction)
        .forEach(([key, value]) => {

            if (
                [
                    "title",
                    "raw_text",
                    "raw_extraction"
                ].includes(key)
            ) {
                return;
            }


            if (
                value === null ||
                value === undefined ||
                value === ""
            ) {
                return;
            }


            output +=
                `${formatLabel(key)}: ${
                    formatValue(value)
                }\n`;

        });


    if (extraction.summary) {

        output +=
            `\nSummary:\n${
                formatValue(
                    extraction.summary
                )
            }\n`;

    }


    if (extraction.description) {

        output +=
            `\nDescription:\n${
                formatValue(
                    extraction.description
                )
            }\n`;

    }


    if (agent && Object.keys(agent).length) {

        output +=
            "\nAI Agent Decision:\n";

        output +=
            `${formatValue(
                agent.action ||
                agent.decision ||
                agent.intent ||
                agent.reason ||
                JSON.stringify(agent)
            )}\n`;

    }


    if (data.raw_text) {

        output +=
            "\nOCR / Source Text:\n";

        output +=
            data.raw_text;

        output += "\n";

    }


    return output;
}


// =========================================================
// SAVE AS PDF
// =========================================================

async function saveResultAsPDF() {

    if (!latestResult) {

        alert(
            "Please analyze something first."
        );

        return;
    }


    // jsPDF loaded from CDN
    if (
        !window.jspdf ||
        !window.jspdf.jsPDF
    ) {

        // Fallback to browser printing
        window.print();

        return;
    }


    const {
        jsPDF
    } = window.jspdf;


    const pdf = new jsPDF({
        orientation: "p",
        unit: "mm",
        format: "a4"
    });


    const extraction =
        latestResult.extraction || {};


    const title =
        extraction.title ||
        "Extracted Information";


    let y = 20;


    // -----------------------------------------------------
    // PDF HEADER
    // -----------------------------------------------------

    pdf.setFontSize(20);

    pdf.setFont(
        "helvetica",
        "bold"
    );

    pdf.text(
        "Screenshot-to-Task",
        15,
        y
    );


    y += 8;


    pdf.setFontSize(10);

    pdf.setFont(
        "helvetica",
        "normal"
    );

    pdf.text(
        "AI Life Organizer — Extracted Information",
        15,
        y
    );


    y += 12;


    pdf.setDrawColor(
        200,
        200,
        200
    );

    pdf.line(
        15,
        y,
        195,
        y
    );


    y += 10;


    // -----------------------------------------------------
    // TITLE
    // -----------------------------------------------------

    pdf.setFontSize(16);

    pdf.setFont(
        "helvetica",
        "bold"
    );


    const titleLines =
        pdf.splitTextToSize(
            String(title),
            175
        );


    pdf.text(
        titleLines,
        15,
        y
    );


    y +=
        titleLines.length * 7 +
        5;


    // -----------------------------------------------------
    // EXTRACTION FIELDS
    // -----------------------------------------------------

    pdf.setFontSize(10);


    Object.entries(extraction)
        .forEach(([key, value]) => {

            if (
                [
                    "title",
                    "raw_text",
                    "raw_extraction"
                ].includes(key)
            ) {
                return;
            }


            if (
                value === null ||
                value === undefined ||
                value === ""
            ) {
                return;
            }


            const label =
                `${formatLabel(key)}:`;


            const text =
                formatValue(value);


            const lines =
                pdf.splitTextToSize(
                    text,
                    130
                );


            // Page break
            if (y > 270) {

                pdf.addPage();

                y = 20;

            }


            pdf.setFont(
                "helvetica",
                "bold"
            );

            pdf.text(
                label,
                15,
                y
            );


            pdf.setFont(
                "helvetica",
                "normal"
            );


            pdf.text(
                lines,
                60,
                y
            );


            y +=
                Math.max(
                    6,
                    lines.length * 5
                );

        });


    // -----------------------------------------------------
    // SUMMARY
    // -----------------------------------------------------

    if (extraction.summary) {

        if (y > 250) {

            pdf.addPage();

            y = 20;

        }


        y += 5;


        pdf.setFont(
            "helvetica",
            "bold"
        );

        pdf.text(
            "Summary",
            15,
            y
        );


        y += 6;


        pdf.setFont(
            "helvetica",
            "normal"
        );


        const summaryLines =
            pdf.splitTextToSize(
                String(
                    extraction.summary
                ),
                175
            );


        pdf.text(
            summaryLines,
            15,
            y
        );


        y +=
            summaryLines.length * 5 +
            5;

    }


    // -----------------------------------------------------
    // DESCRIPTION
    // -----------------------------------------------------

    if (extraction.description) {

        if (y > 250) {

            pdf.addPage();

            y = 20;

        }


        pdf.setFont(
            "helvetica",
            "bold"
        );

        pdf.text(
            "Description",
            15,
            y
        );


        y += 6;


        pdf.setFont(
            "helvetica",
            "normal"
        );


        const descriptionLines =
            pdf.splitTextToSize(
                String(
                    extraction.description
                ),
                175
            );


        pdf.text(
            descriptionLines,
            15,
            y
        );


        y +=
            descriptionLines.length * 5 +
            5;

    }


    // -----------------------------------------------------
    // AI AGENT
    // -----------------------------------------------------

    const agent =
        latestResult.agent || {};


    if (Object.keys(agent).length) {

        if (y > 250) {

            pdf.addPage();

            y = 20;

        }


        pdf.setFont(
            "helvetica",
            "bold"
        );

        pdf.text(
            "AI Agent Decision",
            15,
            y
        );


        y += 6;


        pdf.setFont(
            "helvetica",
            "normal"
        );


        const agentText =
            formatValue(
                agent.action ||
                agent.decision ||
                agent.intent ||
                agent.reason ||
                JSON.stringify(agent)
            );


        const agentLines =
            pdf.splitTextToSize(
                agentText,
                175
            );


        pdf.text(
            agentLines,
            15,
            y
        );


        y +=
            agentLines.length * 5 +
            5;

    }


    // -----------------------------------------------------
    // OCR TEXT
    // -----------------------------------------------------

    if (latestResult.raw_text) {

        if (y > 235) {

            pdf.addPage();

            y = 20;

        }


        pdf.setFont(
            "helvetica",
            "bold"
        );

        pdf.text(
            "OCR / Source Text",
            15,
            y
        );


        y += 6;


        pdf.setFont(
            "helvetica",
            "normal"
        );


        const ocrLines =
            pdf.splitTextToSize(
                String(
                    latestResult.raw_text
                ),
                175
            );


        // Write OCR in chunks
        let index = 0;


        while (
            index < ocrLines.length
        ) {

            if (y > 275) {

                pdf.addPage();

                y = 20;

            }


            const chunk =
                ocrLines.slice(
                    index,
                    index + 45
                );


            pdf.text(
                chunk,
                15,
                y
            );


            y +=
                chunk.length * 4.5;


            index += 45;

        }

    }


    // -----------------------------------------------------
    // FOOTER
    // -----------------------------------------------------

    const pageCount =
        pdf.internal.getNumberOfPages();


    for (
        let page = 1;
        page <= pageCount;
        page++
    ) {

        pdf.setPage(page);

        pdf.setFontSize(8);

        pdf.setTextColor(
            120,
            120,
            120
        );


        pdf.text(
            `Screenshot-to-Task • Page ${page} of ${pageCount}`,
            15,
            290
        );


        pdf.text(
            new Date().toLocaleString(),
            145,
            290
        );

    }


    // -----------------------------------------------------
    // DOWNLOAD
    // -----------------------------------------------------

    const safeTitle =
        String(title)
            .replace(
                /[^a-z0-9]/gi,
                "_"
            )
            .substring(0, 60);


    pdf.save(
        `Screenshot-to-Task_${safeTitle || "Result"}.pdf`
    );


    setStatus(
        "PDF created successfully."
    );

}


// =========================================================
// SAVE CURRENT TASK
// =========================================================

async function saveCurrentTask() {

    if (!latestResult) {

        alert(
            "Analyze information first."
        );

        return;
    }


    const extraction =
        latestResult.extraction || {};


    const payload = {

        title:
            extraction.title ||
            "Untitled Task",

        task_type:
            extraction.task_type ||
            "task",

        description:
            extraction.description ||
            extraction.summary ||
            "",

        event_date:
            extraction.date ||
            extraction.event_date ||
            null,

        event_time:
            extraction.time ||
            extraction.event_time ||
            null,

        location:
            extraction.location ||
            null,

        priority:
            extraction.priority ||
            "medium",

        person:
            extraction.person ||
            null,

        amount:
            extraction.amount ||
            null,

        currency:
            extraction.currency ||
            null,

        phone:
            extraction.phone ||
            null,

        email:
            extraction.email ||
            null,

        url:
            extraction.url ||
            null,

        organization:
            extraction.organization ||
            null,

        summary:
            extraction.summary ||
            null,

        raw_extraction:
            extraction,

        source_text:
            latestResult.raw_text ||
            ""

    };


    try {

        setStatus(
            "Saving task..."
        );


        const response =
            await fetch(
                `${API}/api/tasks`,
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body:
                        JSON.stringify(payload)
                }
            );


        if (!response.ok) {

            const text =
                await response.text();

            throw new Error(
                text ||
                "Could not save task."
            );

        }


        setStatus(
            "Task saved successfully."
        );


        await loadTasks();


    } catch (error) {

        console.error(error);

        setStatus(
            "Could not save task: " +
            error.message
        );

    }

}


// =========================================================
// LOAD TASKS
// =========================================================

async function loadTasks() {

    try {

        const response =
            await fetch(
                `${API}/api/tasks`
            );


        if (!response.ok) {
            throw new Error(
                "Could not load tasks."
            );
        }


        const tasks =
            await response.json();


        renderTasks(tasks);


    } catch (error) {

        console.error(error);

        tasksBox.innerHTML = `
            <div class="task-card">
                <h3>
                    Unable to load tasks
                </h3>

                <p>
                    Make sure the backend server
                    is running.
                </p>
            </div>
        `;

    }

}


// =========================================================
// RENDER TASKS
// =========================================================

function renderTasks(tasks) {

    if (!tasks || !tasks.length) {

        tasksBox.innerHTML = `
            <div class="task-card">

                <h3>
                    No saved tasks yet
                </h3>

                <p>
                    Analyze something and click
                    "Save Task" to create your
                    first task.
                </p>

            </div>
        `;

        return;
    }


    tasksBox.innerHTML =
        tasks.map(
            task => `

            <article class="task-card">

                <div class="task-top">

                    <h3>
                        ${escapeHtml(
                            task.title ||
                            "Untitled Task"
                        )}
                    </h3>

                    <button
                        class="delete-task"
                        onclick="deleteTask(${task.id})"
                        title="Delete task"
                    >
                        ×
                    </button>

                </div>


                <p>
                    ${escapeHtml(
                        task.description ||
                        task.summary ||
                        "No description available."
                    )}
                </p>


                <div class="task-meta">

                    ${
                        task.task_type
                            ? `
                            <span class="task-badge">
                                ${escapeHtml(
                                    task.task_type
                                )}
                            </span>
                            `
                            : ""
                    }


                    ${
                        task.event_date
                            ? `
                            <span class="task-badge">
                                📅 ${escapeHtml(
                                    task.event_date
                                )}
                            </span>
                            `
                            : ""
                    }


                    ${
                        task.event_time
                            ? `
                            <span class="task-badge">
                                ⏰ ${escapeHtml(
                                    task.event_time
                                )}
                            </span>
                            `
                            : ""
                    }


                    ${
                        task.location
                            ? `
                            <span class="task-badge">
                                📍 ${escapeHtml(
                                    task.location
                                )}
                            </span>
                            `
                            : ""
                    }


                    ${
                        task.priority
                            ? `
                            <span class="task-badge">
                                ${escapeHtml(
                                    task.priority
                                )}
                            </span>
                            `
                            : ""
                    }

                </div>

            </article>

        `
        ).join("");

}


// =========================================================
// DELETE TASK
// =========================================================

async function deleteTask(taskId) {

    if (
        !confirm(
            "Delete this task?"
        )
    ) {
        return;
    }


    try {

        const response =
            await fetch(
                `${API}/api/tasks/${taskId}`,
                {
                    method: "DELETE"
                }
            );


        if (!response.ok) {

            throw new Error(
                "Could not delete task."
            );

        }


        await loadTasks();


    } catch (error) {

        console.error(error);

        alert(
            "Unable to delete task."
        );

    }

}


// =========================================================
// CALENDAR
// =========================================================

calendarButton.addEventListener(
    "click",
    connectCalendar
);


async function connectCalendar() {

    try {

        const response =
            await fetch(
                `${API}/api/calendar/connect`
            );


        const data =
            await response.json();


        if (data.url) {

            window.location.href =
                data.url;

            return;

        }


        alert(
            data.message ||
            "Calendar connection is not available."
        );


    } catch (error) {

        console.error(error);

        alert(
            "Unable to connect Google Calendar."
        );

    }

}


// =========================================================
// CREATE CALENDAR EVENT
// =========================================================

async function createCalendarEvent() {

    if (!latestResult) {

        alert(
            "Analyze something first."
        );

        return;
    }


    const extraction =
        latestResult.extraction || {};


    const payload = {

        title:
            extraction.title ||
            "Screenshot-to-Task Event",

        description:
            extraction.description ||
            extraction.summary ||
            "",

        date:
            extraction.date ||
            extraction.event_date ||
            null,

        time:
            extraction.time ||
            extraction.event_time ||
            null,

        location:
            extraction.location ||
            null

    };


    try {

        setStatus(
            "Creating calendar event..."
        );


        const response =
            await fetch(
                `${API}/api/calendar/events`,
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body:
                        JSON.stringify(payload)
                }
            );


        const data =
            await response.json();


        if (!response.ok) {

            throw new Error(
                data.detail ||
                "Calendar event could not be created."
            );

        }


        setStatus(
            "Calendar event created successfully."
        );


        if (data.htmlLink) {

            window.open(
                data.htmlLink,
                "_blank"
            );

        }


    } catch (error) {

        console.error(error);

        alert(
            error.message ||
            "Unable to create calendar event."
        );

    }

}


// =========================================================
// REFRESH TASKS
// =========================================================

refreshButton.addEventListener(
    "click",
    loadTasks
);


// =========================================================
// KEYBOARD SHORTCUT
// Ctrl + Enter = Analyze pasted text
// =========================================================

textInput.addEventListener(
    "keydown",
    event => {

        if (
            event.ctrlKey &&
            event.key === "Enter"
        ) {

            analyzeInput();

        }

    }
);


// =========================================================
// INITIAL LOAD
// =========================================================

document.addEventListener(
    "DOMContentLoaded",
    () => {

        loadTasks();

    }
);