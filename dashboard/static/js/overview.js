(() => {
  "use strict";

  const endpoints = window.__SENTINEL_OVERVIEW_ENDPOINTS || {};
  const streamUrl = endpoints.stream;
  const apiUrl = endpoints.api;
  const incidentDetailBase = endpoints.incidentDetailBase || "/incidents";

  const SEV_BADGE = {
    CRITICAL: '<span class="badge bg-danger">CRITICAL</span>',
    HIGH: '<span class="badge bg-warning text-dark">HIGH</span>',
    MEDIUM: '<span class="badge bg-primary">MEDIUM</span>',
    WARNING: '<span class="badge bg-info text-dark">WARNING</span>',
    LOW: '<span class="badge bg-light text-dark border">LOW</span>',
    INFO: '<span class="badge bg-light text-dark border">INFO</span>',
  };

  let evtSource = null;
  let pollTimer = null;
  let currentInterval = parseInt(localStorage.getItem("sentinel_sse_interval") || "30", 10);

  const sel = document.getElementById("interval-select");
  const statusBadge = document.getElementById("stream-status");
  const lastUpdEl = document.getElementById("last-updated");

  if (!statusBadge) return;

  if (sel) {
    sel.value = String(currentInterval);
    sel.addEventListener("change", () => {
      currentInterval = parseInt(sel.value, 10);
      localStorage.setItem("sentinel_sse_interval", sel.value);
      stopAll();
      startSSE();
    });
  }

  function startSSE() {
    if (!window.EventSource || !streamUrl) {
      startPolling();
      return;
    }

    evtSource = new EventSource(`${streamUrl}?interval=${currentInterval}`);
    evtSource.onopen = () => setStatus("success", "ao vivo");
    evtSource.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        if (data && data.devices) applyData(data);
      } catch (_error) {
        setStatus("warning", "dados inválidos");
      }
    };
    evtSource.onerror = () => {
      setStatus("warning", "reconectando...");
      evtSource.close();
      evtSource = null;
      setTimeout(startPolling, 5000);
    };
  }

  function startPolling() {
    if (evtSource || !apiUrl) return;
    setStatus("secondary", "polling");
    fetchNow();
    pollTimer = setInterval(fetchNow, currentInterval * 1000);
  }

  function fetchNow() {
    fetch(apiUrl)
      .then((response) => response.json())
      .then((data) => {
        applyData(data);
        setStatus("secondary", "polling");
      })
      .catch(() => setStatus("danger", "erro"));
  }

  function stopAll() {
    if (evtSource) {
      evtSource.close();
      evtSource = null;
    }
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  }

  function applyData(data) {
    setText("kpi-devices-total", data.devices.total);
    setText("kpi-devices-healthy", data.devices.healthy);
    setText("kpi-devices-incident", data.devices.with_incident);
    setText("kpi-inc-open", data.incidents.open);
    setText("kpi-inc-critical", data.incidents.critical);
    setText("kpi-inc-high", data.incidents.high);
    setText("kpi-inc-warning", data.incidents.warning);
    setText("kpi-inc-info", data.incidents.info);
    setText("kpi-remed-pending", data.remediation.pending_approval);
    setText("kpi-remed-executed", data.remediation.executed_today);
    setText("kpi-mtta", data.slo.mtta_minutes != null ? data.slo.mtta_minutes : "--");
    setText("kpi-mttr", data.slo.mttr_minutes != null ? data.slo.mttr_minutes : "--");
    updateRecentTable(data.recent_incidents || []);

    if (lastUpdEl) {
      lastUpdEl.textContent = new Date().toLocaleTimeString("pt-BR");
    }
  }

  function setText(id, value) {
    const element = document.getElementById(id);
    if (element) element.textContent = value;
  }

  function updateRecentTable(rows) {
    const tbody = document.getElementById("recent-incidents-tbody");
    const empty = document.getElementById("recent-incidents-empty");
    const wrap = document.getElementById("recent-incidents-table-wrap");

    if (!tbody) return;

    if (!rows.length) {
      if (empty) empty.classList.remove("d-none");
      if (wrap) wrap.classList.add("d-none");
      return;
    }

    if (empty) empty.classList.add("d-none");
    if (wrap) wrap.classList.remove("d-none");

    tbody.innerHTML = rows
      .map((incident) => {
        const severity = String(incident.severity || "").toUpperCase();
        const badge =
          SEV_BADGE[severity] ||
          `<span class="badge bg-light text-dark border">${incident.severity || "--"}</span>`;
        const timestamp = String(incident.timestamp || "--").replace("T", " ").slice(0, 19);
        return `
          <tr>
            <td><a href="${incidentDetailBase}/${incident.id}">#${incident.id}</a></td>
            <td>${incident.device_id || "--"}</td>
            <td>${incident.customer_id || "--"}</td>
            <td>${badge}</td>
            <td>${incident.category || "--"}</td>
            <td>${timestamp}</td>
            <td><span class="badge bg-secondary">${incident.status || "--"}</span></td>
          </tr>
        `;
      })
      .join("");
  }

  function setStatus(color, text) {
    statusBadge.className = `badge bg-${color}`;
    statusBadge.innerHTML = `<i id="stream-status-icon" class="bi bi-circle-fill me-1"></i>${text}`;
  }

  startSSE();
})();
