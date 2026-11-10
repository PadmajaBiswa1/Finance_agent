document.addEventListener("DOMContentLoaded", () => {
  const fileInput = document.getElementById("file-input");
  const secondFileInput = document.getElementById("second-file-input");
  const dropZone = document.getElementById("drop-zone");
  const fileInfo = document.getElementById("file-info");
  const selectedFileName = document.getElementById("selected-file-name");
  const clearFileBtn = document.getElementById("clear-file");
  const chatForm = document.getElementById("chat-form");
  const userInput = document.getElementById("user-input");
  const chatStream = document.getElementById("chat-stream");
  const sendBtn = document.getElementById("send-btn");
  const periodInput = document.getElementById("period-input");
  const businessNameInput = document.getElementById("business-name-input");
  const compPeriodInput = document.getElementById("comp-period-input");
  const officialUrlInput = document.getElementById("official-url-input");

  let activeFile = null;

  // File drag & drop handling
  dropZone.addEventListener("click", () => fileInput.click());
  fileInput.addEventListener("change", (e) => {
    if (e.target.files.length > 0) {
      setFile(e.target.files[0]);
    }
  });

  dropZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropZone.classList.add("dragover");
  });

  dropZone.addEventListener("dragleave", () => {
    dropZone.classList.remove("dragover");
  });

  dropZone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropZone.classList.remove("dragover");
    if (e.dataTransfer.files.length > 0) {
      setFile(e.dataTransfer.files[0]);
    }
  });

  clearFileBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    activeFile = null;
    fileInput.value = "";
    fileInfo.classList.add("hidden");
    dropZone.classList.remove("hidden");
  });

  function setFile(file) {
    activeFile = file;
    selectedFileName.textContent = `${file.name} (${(file.size / 1024).toFixed(0)} KB)`;
    fileInfo.classList.remove("hidden");
  }

  // Quick suggestion chips & hero cards
  document.querySelectorAll(".chip, .quick-card").forEach((btn) => {
    btn.addEventListener("click", () => {
      const prompt = btn.getAttribute("data-prompt");
      if (prompt) {
        userInput.value = prompt;
        userInput.focus();
      }
    });
  });

  // Sample data loaders
  document.getElementById("btn-sample-pnl").addEventListener("click", async () => {
    userInput.value = "Analyze the uploaded FY 2023-24 P&L statement. Compute Gross Profit, EBITDA, Operating Profit, PAT, and profitability margins.";
    selectedFileName.textContent = "sample_sme_pnl_fy24.csv (Server Sample)";
    fileInfo.classList.remove("hidden");
  });

  document.getElementById("btn-sample-bs").addEventListener("click", () => {
    userInput.value = "Audit our FY 2023-24 Balance Sheet. Check if Total Assets balance with Liabilities & Equity, and calculate the Current Ratio and Working Capital.";
    selectedFileName.textContent = "sample_sme_balancesheet_fy24.xlsx (Server Sample)";
    fileInfo.classList.remove("hidden");
  });

  document.getElementById("btn-sample-cf").addEventListener("click", () => {
    userInput.value = "Review our Cash Flow Statement for FY 2023-24. Verify if Net Cash Flow equals Operating + Investing + Financing cash flows, and check closing balance reconciliation.";
    selectedFileName.textContent = "sample_sme_cashflow_fy24.pdf (Server Sample)";
    fileInfo.classList.remove("hidden");
  });

  // Auto-resize textarea
  userInput.addEventListener("input", () => {
    userInput.style.height = "auto";
    userInput.style.height = Math.min(userInput.scrollHeight, 120) + "px";
  });

  userInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      chatForm.dispatchEvent(new Event("submit"));
    }
  });

  // Chat submission
  chatForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const query = userInput.value.trim();
    if (!query) return;

    // Remove welcome hero once chat starts
    const hero = document.querySelector(".welcome-hero");
    if (hero) hero.remove();

    appendUserMessage(query, activeFile ? activeFile.name : null);
    userInput.value = "";
    userInput.style.height = "auto";
    sendBtn.disabled = true;

    const loadingCardId = appendLoadingMessage();

    try {
      const formData = new FormData();
      formData.append("message", query);
      if (activeFile) {
        formData.append("file", activeFile);
      }
      if (secondFileInput.files.length > 0) {
        formData.append("second_file", secondFileInput.files[0]);
      }
      formData.append("period", periodInput.value || "FY 2023-24");
      formData.append("business_name", businessNameInput.value || "Indian SME Enterprise");
      if (compPeriodInput.value) {
        formData.append("comparison_period", compPeriodInput.value);
      }
      if (officialUrlInput.value) {
        formData.append("official_url", officialUrlInput.value);
      }
      formData.append("generate_report", "true");

      const response = await fetch("/api/chat", {
        method: "POST",
        body: formData,
      });

      const data = await response.json();
      removeElement(loadingCardId);

      if (response.ok) {
        appendAssistantMessage(data);
        updateTelemetry();
      } else {
        appendErrorMessage(data.detail || "Error processing request.");
      }
    } catch (err) {
      removeElement(loadingCardId);
      appendErrorMessage(`Network error: ${err.message}`);
    } finally {
      sendBtn.disabled = false;
      chatStream.scrollTop = chatStream.scrollHeight;
    }
  });

  function appendUserMessage(text, filename) {
    const card = document.createElement("div");
    card.className = "chat-card user-card";
    card.innerHTML = `
      <div class="card-header">
        <div class="avatar"><i class="fa-solid fa-user"></i></div>
        <div class="header-text">
          <h4>You</h4>
          <span class="timestamp">${new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</span>
        </div>
      </div>
      <div class="card-body">
        <p>${escapeHtml(text)}</p>
        ${filename ? `<div class="tool-pill" style="margin-top:6px; background:rgba(255,255,255,0.2); color:#fff; border-color:transparent;"><i class="fa-solid fa-paperclip"></i> ${escapeHtml(filename)}</div>` : ""}
      </div>
    `;
    chatStream.appendChild(card);
    chatStream.scrollTop = chatStream.scrollHeight;
  }

  function appendLoadingMessage() {
    const id = "loading-" + Date.now();
    const card = document.createElement("div");
    card.id = id;
    card.className = "chat-card assistant-card";
    card.innerHTML = `
      <div class="card-header">
        <div class="avatar"><i class="fa-solid fa-robot"></i></div>
        <div class="header-text">
          <h4>Analyzing...</h4>
        </div>
      </div>
      <div class="card-body">
        <p style="color:#64748b;"><i class="fa-solid fa-spinner fa-spin"></i> Processing financial statements with Decimal arithmetic...</p>
      </div>
    `;
    chatStream.appendChild(card);
    chatStream.scrollTop = chatStream.scrollHeight;
    return id;
  }

  function appendAssistantMessage(data) {
    const card = document.createElement("div");
    card.className = "chat-card assistant-card";

    let toolsHtml = "";
    if (data.tools_executed && data.tools_executed.length > 0) {
      toolsHtml = `
        <div class="tools-badge-container">
          <span style="font-size:0.68rem; color:#94a3b8; font-weight:600; margin-right:4px;">Pipeline:</span>
          ${data.tools_executed.map(t => `<span class="tool-pill"><i class="fa-solid fa-check"></i> ${t}</span>`).join(" ")}
        </div>
      `;
    }

    let warningsHtml = "";
    if (data.data_quality_warnings && data.data_quality_warnings.length > 0) {
      warningsHtml = `
        <div class="warning-callout">
          <strong><i class="fa-solid fa-triangle-exclamation"></i> Notice:</strong>
          <ul>
            ${data.data_quality_warnings.map(w => `<li>${escapeHtml(w)}</li>`).join("")}
          </ul>
        </div>
      `;
    }

    let reportDownloadsHtml = "";
    if (data.report) {
      reportDownloadsHtml = `
        <div class="report-downloads-box">
          <span style="font-size:0.72rem; color:#64748b; font-weight:600;">Report:</span>
          ${data.report.download_url_html ? `<a href="${data.report.download_url_html}" target="_blank" class="btn-download"><i class="fa-solid fa-arrow-up-right-from-square"></i> View</a>` : ""}
          ${data.report.download_url_markdown ? `<a href="${data.report.download_url_markdown}" download class="btn-download"><i class="fa-solid fa-file-arrow-down"></i> Markdown</a>` : ""}
          ${data.report.download_url_json ? `<a href="${data.report.download_url_json}" download class="btn-download"><i class="fa-solid fa-code"></i> JSON</a>` : ""}
        </div>
      `;
    }

    card.innerHTML = `
      <div class="card-header">
        <div class="avatar"><i class="fa-solid fa-robot"></i></div>
        <div class="header-text">
          <h4>FinanceAgent</h4>
          <span class="timestamp">${new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</span>
        </div>
      </div>
      <div class="card-body">
        ${toolsHtml}
        ${warningsHtml}
        <div class="answer-text">${formatMarkdown(data.answer)}</div>
        ${reportDownloadsHtml}
      </div>
    `;
    chatStream.appendChild(card);
    chatStream.scrollTop = chatStream.scrollHeight;
  }

  function appendErrorMessage(errorText) {
    const card = document.createElement("div");
    card.className = "chat-card assistant-card";
    card.style.borderColor = "#fca5a5";
    card.innerHTML = `
      <div class="card-header">
        <div class="avatar" style="background:#fee2e2; color:#dc2626;"><i class="fa-solid fa-circle-exclamation"></i></div>
        <div class="header-text">
          <h4>Notice</h4>
        </div>
      </div>
      <div class="card-body">
        <p style="color:#b91c1c;">${escapeHtml(errorText)}</p>
      </div>
    `;
    chatStream.appendChild(card);
  }

  async function updateTelemetry() {
    try {
      const resp = await fetch("/api/telemetry");
      if (resp.ok) {
        const stats = await resp.json();
        document.getElementById("stat-requests").textContent = stats.total_requests || 0;
        document.getElementById("stat-tokens").textContent = formatNumber(stats.total_tokens || 0);
        document.getElementById("stat-latency").textContent = `${stats.avg_latency_ms || 0} ms`;
        document.getElementById("stat-savings").textContent = `${formatNumber(stats.total_saved_tokens || 0)}`;
      }
    } catch (e) {
      // Ignore telemetry fetch errors
    }
  }

  function formatNumber(num) {
    if (num >= 1000000) return (num / 1000000).toFixed(1) + "M";
    if (num >= 1000) return (num / 1000).toFixed(1) + "k";
    return num.toLocaleString();
  }

  function removeElement(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
  }

  function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  function formatMarkdown(text) {
    if (!text) return "";

    // If answer contains raw JSON, parse and render as table instead of raw code
    if (text.includes("Financial analysis completed successfully") && text.includes("{")) {
      const jsonStart = text.indexOf("{");
      const jsonStr = text.substring(jsonStart);
      try {
        const obj = JSON.parse(jsonStr);
        let out = `<p><strong>Analysis Summary:</strong></p>`;
        if (obj.computed_profit_metrics) {
          out += `<table><thead><tr><th>Metric</th><th>Amount (INR)</th></tr></thead><tbody>`;
          for (const [k, v] of Object.entries(obj.computed_profit_metrics)) {
            if (k !== "Formulas") out += `<tr><td>${k}</td><td><strong>₹ ${v}</strong></td></tr>`;
          }
          out += `</tbody></table>`;
        }
        if (obj.computed_financial_ratios) {
          out += `<table><thead><tr><th>Ratio</th><th>Value</th></tr></thead><tbody>`;
          for (const [k, v] of Object.entries(obj.computed_financial_ratios)) {
            if (k !== "Formulas" && v !== "unavailable") out += `<tr><td>${k}</td><td><strong>${v}</strong></td></tr>`;
          }
          out += `</tbody></table>`;
        }
        return out;
      } catch (e) {}
    }

    let s = escapeHtml(text);

    // Markdown tables parsing
    s = s.replace(/((?:\|[^\n]+\|\r?\n)+)/g, (match) => {
      const lines = match.trim().split("\n");
      if (lines.length < 2) return match;
      let html = "<table>";
      let isHeader = true;
      for (const line of lines) {
        if (line.includes("---")) {
          isHeader = false;
          continue;
        }
        const cells = line.split("|").filter((_, i, arr) => i > 0 && i < arr.length - 1);
        const tag = isHeader ? "th" : "td";
        html += "<tr>" + cells.map(c => `<${tag}>${c.trim()}</${tag}>`).join("") + "</tr>";
      }
      html += "</table>";
      return html;
    });

    // Bold
    s = s.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
    // Bullet points
    s = s.replace(/^•\s+(.*)$/gm, "<li>$1</li>");
    s = s.replace(/^-\s+(.*)$/gm, "<li>$1</li>");
    // Markdown headers
    s = s.replace(/^### (.*$)/gm, "<h4 style='margin:10px 0 4px;'>$1</h4>");
    s = s.replace(/^## (.*$)/gm, "<h3 style='margin:12px 0 6px;'>$1</h3>");
    // Line breaks
    s = s.replace(/\n\n/g, "<br><br>");

    return s;
  }

  // Update telemetry on load
  updateTelemetry();
});
