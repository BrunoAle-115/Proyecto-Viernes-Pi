/**
 * V.I.E.R.N.E.S. - STARK INDUSTRIES HUD JAVASCRIPT CONTROLLER
 */

document.addEventListener("DOMContentLoaded", () => {
  // Elements
  const liveClock = document.getElementById("live-clock");
  const liveDate = document.getElementById("live-date");
  const cpuTemp = document.getElementById("cpu-temp");
  const cpuLoad = document.getElementById("cpu-load");
  const ramUsage = document.getElementById("ram-usage");
  const hostIp = document.getElementById("host-ip");
  const voiceStateTag = document.getElementById("voice-state-tag");
  const canvas = document.getElementById("waveform-canvas");
  const ctx = canvas.getContext("2d");
  const termLogs = document.getElementById("terminal-logs");
  const deviceMatrix = document.getElementById("device-matrix");
  const emailList = document.getElementById("email-list");
  const githubList = document.getElementById("github-list");
  const promptInput = document.getElementById("prompt-input");
  const btnPromptSend = document.getElementById("btn-prompt-send");
  const btnTalkMic = document.getElementById("btn-talk-mic");
  const btnRescanNet = document.getElementById("btn-rescan-net");
  const btnMakeCall = document.getElementById("btn-make-call");
  const phoneInput = document.getElementById("phone-input");

  let currentAudioRms = 0.05;
  let isSpeaking = false;
  let animationFrameId = null;

  // 1. Clock
  function updateClock() {
    const now = new Date();
    liveClock.textContent = now.toLocaleTimeString("es-CL", { hour12: false });
    liveDate.textContent = now.toLocaleDateString("es-CL", { weekday: "short", day: "numeric", month: "short", year: "numeric" }).toUpperCase() + " // SANTIAGO, CHILE";
  }
  setInterval(updateClock, 1000);
  updateClock();

  // 2. Holographic Waveform Visualizer
  let phase = 0;
  function drawWaveform() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const width = canvas.width;
    const height = canvas.height;
    const centerY = height / 2;

    const baseAmp = isSpeaking ? 35 : Math.max(8, currentAudioRms * 90);
    const color = isSpeaking ? "#ffb700" : "#00f0ff";

    // Draw central glowing rings
    ctx.beginPath();
    ctx.arc(width / 2, centerY, isSpeaking ? 22 + Math.sin(phase) * 5 : 16 + currentAudioRms * 15, 0, Math.PI * 2);
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.shadowBlur = 15;
    ctx.shadowColor = color;
    ctx.stroke();

    // Wave 1
    ctx.beginPath();
    ctx.lineWidth = 2;
    ctx.strokeStyle = color;
    for (let x = 0; x < width; x++) {
      const distFromCenter = Math.abs(x - width / 2) / (width / 2);
      const envelope = Math.max(0, 1 - distFromCenter);
      const y = centerY + Math.sin(x * 0.04 + phase) * baseAmp * envelope;
      if (x === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();

    // Wave 2 (Harmonic)
    ctx.beginPath();
    ctx.lineWidth = 1;
    ctx.strokeStyle = "rgba(0, 255, 157, 0.6)";
    for (let x = 0; x < width; x++) {
      const distFromCenter = Math.abs(x - width / 2) / (width / 2);
      const envelope = Math.max(0, 1 - distFromCenter);
      const y = centerY + Math.cos(x * 0.08 - phase * 1.5) * (baseAmp * 0.5) * envelope;
      if (x === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();

    phase += 0.08;
    animationFrameId = requestAnimationFrame(drawWaveform);
  }
  drawWaveform();

  // 3. WebSocket Connection for Telemetry & Events
  let ws;
  function connectWs() {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    ws = new WebSocket(`${protocol}//${window.location.host}/ws`);

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === "telemetry") {
          const t = msg.data;
          cpuTemp.textContent = `${t.cpu.temperature_c}°C`;
          cpuLoad.textContent = `${Math.round(t.cpu.percent)}%`;
          ramUsage.textContent = `${Math.round(t.ram.percent)}%`;
          hostIp.textContent = `IP: ${t.local_ip}`;
          currentAudioRms = t.audio_rms || 0.02;
          isSpeaking = t.is_speaking || false;
          
          if (isSpeaking) {
            voiceStateTag.textContent = "TRANSMITIENDO VOZ";
            voiceStateTag.style.color = "var(--gold-stark)";
          } else {
            voiceStateTag.textContent = "EN ESPERA / ESCUCHANDO";
            voiceStateTag.style.color = "var(--cyan-stark)";
          }
        } else if (msg.type === "event") {
          appendLog(msg.topic, JSON.stringify(msg.data), "log-info");
        }
      } catch (err) {
        console.error("WS Parse error", err);
      }
    };

    ws.onclose = () => {
      setTimeout(connectWs, 2000);
    };
  }
  connectWs();

  function appendLog(topic, text, typeClass = "log-system") {
    const entry = document.createElement("div");
    entry.className = `log-entry ${typeClass}`;
    entry.textContent = `[${topic.toUpperCase()}] ${text}`;
    termLogs.appendChild(entry);
    termLogs.scrollTop = termLogs.scrollHeight;
  }

  // 4. Load Discovered Devices Matrix
  async function loadDevices() {
    try {
      const res = await fetch("/api/devices");
      const devices = await res.json();
      deviceMatrix.innerHTML = "";

      if (devices.length === 0) {
        deviceMatrix.innerHTML = '<div class="empty-notice">No se encontraron dispositivos en la red. Presiona "Escanear Red".</div>';
        return;
      }

      devices.forEach((dev) => {
        const card = document.createElement("div");
        card.className = "device-card";
        const isOnline = dev.status === "online";
        const statusBadge = isOnline ? '<span style="color:var(--green-matrix)">● ONLINE</span>' : '<span style="color:var(--text-dim)">○ OFFLINE</span>';

        let actionBtn = "";
        if (dev.wol_enabled || dev.type === "desktop") {
          actionBtn = `<button class="btn-wol" onclick="triggerWol('${dev.ip}')">ENCENDER WOL</button>`;
        } else if (dev.type === "light") {
          actionBtn = `<button class="btn-light-toggle" onclick="toggleLight('${dev.ip}')">LUCES ON/OFF</button>`;
        }

        card.innerHTML = `
          <div class="device-info">
            <div class="device-name">${dev.alias} ${statusBadge}</div>
            <div class="device-sub">IP: ${dev.ip} | MAC: ${dev.mac || "Auto-Resolv"} | ${dev.vendor || "IoT"}</div>
          </div>
          <div>${actionBtn}</div>
        `;
        deviceMatrix.appendChild(card);
      });
    } catch (e) {
      console.error("Error cargando dispositivos", e);
    }
  }
  loadDevices();

  // 5. Load Triaged Emails
  async function loadEmails() {
    try {
      const res = await fetch("/api/emails");
      const data = await res.json();
      emailList.innerHTML = "";

      const all = [...(data.gmail || []), ...(data.zoho || [])];
      document.getElementById("mail-count-badge").textContent = `${all.length} URGENTES`;

      if (all.length === 0) {
        emailList.innerHTML = '<div class="empty-notice">✓ Bandeja limpia. Sin correos urgentes pendientes.</div>';
        return;
      }

      all.forEach((m) => {
        const item = document.createElement("div");
        item.className = "mail-item";
        item.innerHTML = `
          <div class="mail-item-header">
            <span class="mail-sender">${m.source}: ${m.sender.split("<")[0]}</span>
            <span class="badge-urgent">URGENTE</span>
          </div>
          <div style="font-weight:600; color:#fff;">${m.subject}</div>
          <div style="font-size:11px; color:var(--text-dim); margin-top:2px;">${m.snippet}</div>
        `;
        emailList.appendChild(item);
      });
    } catch (e) {
      console.error("Error cargando correos", e);
    }
  }
  loadEmails();

  // 6. Load GitHub PRs
  async function loadGithub() {
    try {
      const res = await fetch("/api/github");
      const data = await res.json();
      githubList.innerHTML = "";

      if (!data.prs || data.prs.length === 0) {
        githubList.innerHTML = '<div class="empty-notice">No hay Pull Requests abiertas actualmente.</div>';
        return;
      }

      data.prs.forEach((pr) => {
        const item = document.createElement("div");
        item.className = "pr-item";
        const isApproved = pr.status === "APPROVED";
        const badge = isApproved 
          ? '<span class="badge-approved">✓ APROBADA</span>' 
          : `<span class="header-badge">${pr.status}</span>`;

        item.innerHTML = `
          <div class="pr-item-header">
            <span class="pr-title">${pr.repo} #${pr.number}</span>
            ${badge}
          </div>
          <div style="color:#fff;">${pr.title}</div>
          <div style="font-size:11px; color:var(--text-dim); margin-top:3px;">
            ${isApproved ? 'Aprobada por: ' + pr.approved_by.join(', ') : 'Revisión pendiente'}
          </div>
        `;
        githubList.appendChild(item);
      });
    } catch (e) {
      console.error("Error cargando GitHub", e);
    }
  }
  loadGithub();

  // 7. Actions & Handlers
  window.triggerWol = async (target) => {
    appendLog("WOL", `Transmitiendo Magic Packet a ${target}...`, "log-info");
    try {
      const res = await fetch("/api/wol", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target })
      });
      const data = await res.json();
      appendLog("WOL", data.message || "Paquete enviado con éxito.", "log-success");
      setTimeout(loadDevices, 3000);
    } catch (err) {
      appendLog("WOL", `Fallo: ${err}`, "log-warn");
    }
  };

  window.toggleLight = async (target) => {
    try {
      const res = await fetch("/api/lights", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target, action: "toggle" })
      });
      const data = await res.json();
      appendLog("IOT", data.message, "log-success");
    } catch (err) {
      appendLog("IOT", `Fallo: ${err}`, "log-warn");
    }
  };

  btnPromptSend.addEventListener("click", async () => {
    const text = promptInput.value.trim();
    if (!text) return;
    promptInput.value = "";
    appendLog("USUARIO", text, "log-info");

    const res = await fetch("/api/prompt", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt: text })
    });
    const data = await res.json();
    appendLog("VIERNES", data.response, "log-system");
  });

  promptInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") btnPromptSend.click();
  });

  btnTalkMic.addEventListener("click", async () => {
    appendLog("VOZ", "Activando reconocimiento de voz...", "log-info");
    await fetch("/api/wakeword/trigger", { method: "POST" });
  });

  btnRescanNet.addEventListener("click", async () => {
    appendLog("RED", "Iniciando escaneo activo ARP/Nmap de la subred...", "log-info");
    await fetch("/api/scan", { method: "POST" });
    await loadDevices();
  });

  btnMakeCall.addEventListener("click", async () => {
    const num = phoneInput.value.trim();
    if (!num) return;
    appendLog("SIP", `Originando llamada a ${num}...`, "log-info");
    const res = await fetch("/api/call", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ phone_number: num })
    });
    const data = await res.json();
    appendLog("SIP", data.message, "log-success");
  });
});
