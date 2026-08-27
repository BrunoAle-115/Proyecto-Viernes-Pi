/**
 * V.I.E.R.N.E.S. 2.0 - STARK INDUSTRIES HUD JAVASCRIPT CONTROLLER
 */

document.addEventListener("DOMContentLoaded", () => {
  // Elements
  const authOverlay = document.getElementById("auth-modal-overlay");
  const loginEmail = document.getElementById("login-email");
  const loginPassword = document.getElementById("login-password");
  const btnLoginSubmit = document.getElementById("btn-login-submit");
  const authErrorMsg = document.getElementById("auth-error-msg");
  const btnLogout = document.getElementById("btn-logout");

  const settingsOverlay = document.getElementById("settings-modal-overlay");
  const btnOpenSettings = document.getElementById("btn-open-settings");
  const btnCloseSettings = document.getElementById("btn-close-settings");
  const btnSaveSettings = document.getElementById("btn-save-settings");

  const cfgGeminiKey = document.getElementById("cfg-gemini-key");
  const cfgGeminiModel = document.getElementById("cfg-gemini-model");
  const cfgGithubToken = document.getElementById("cfg-github-token");
  const cfgGithubRepos = document.getElementById("cfg-github-repos");
  const cfgSipProvider = document.getElementById("cfg-sip-provider");
  const cfgCity = document.getElementById("cfg-city");

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

  const weatherTemp = document.getElementById("weather-temp");
  const weatherCity = document.getElementById("weather-city");
  const weatherCond = document.getElementById("weather-condition");
  const weatherApparent = document.getElementById("weather-apparent");
  const weatherHumidity = document.getElementById("weather-humidity");
  const rainAlertBadge = document.getElementById("rain-alert-badge");
  const hourlyForecast = document.getElementById("hourly-forecast");

  const newsList = document.getElementById("news-list");
  const memoryList = document.getElementById("memory-list");
  const deviceMatrix = document.getElementById("device-matrix");
  const emailList = document.getElementById("email-list");
  const githubList = document.getElementById("github-list");

  const promptInput = document.getElementById("prompt-input");
  const btnPromptSend = document.getElementById("btn-prompt-send");
  const btnTalkMic = document.getElementById("btn-talk-mic");
  const btnRescanNet = document.getElementById("btn-rescan-net");
  const btnMakeCall = document.getElementById("btn-make-call");
  const phoneInput = document.getElementById("phone-input");
  const btnAddMemory = document.getElementById("btn-add-memory");

  let currentAudioRms = 0.05;
  let isSpeaking = false;

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

    const baseAmp = isSpeaking ? 32 : Math.max(6, currentAudioRms * 85);
    const color = isSpeaking ? "#ffb700" : "#00f0ff";

    // Central Glowing Arc Core
    ctx.beginPath();
    ctx.arc(width / 2, centerY, isSpeaking ? 20 + Math.sin(phase) * 4 : 14 + currentAudioRms * 12, 0, Math.PI * 2);
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.shadowBlur = 14;
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

    // Harmonic Wave 2
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
    requestAnimationFrame(drawWaveform);
  }
  drawWaveform();

  // 3. Authentication Check
  async function checkAuth() {
    try {
      const res = await fetch("/api/auth/me");
      if (res.ok) {
        authOverlay.style.display = "none";
        loadAllData();
      } else {
        authOverlay.style.display = "flex";
      }
    } catch (e) {
      authOverlay.style.display = "flex";
    }
  }
  checkAuth();

  btnLoginSubmit.addEventListener("click", async () => {
    authErrorMsg.textContent = "";
    const email = loginEmail.value.trim();
    const password = loginPassword.value;

    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password })
      });
      const data = await res.json();
      if (res.ok) {
        authOverlay.style.display = "none";
        appendLog("AUTH", `Bienvenido señor Bruno (${email}). Acceso táctico concedido.`, "log-success");
        loadAllData();
      } else {
        authErrorMsg.textContent = data.detail || "Contraseña o correo incorrectos.";
      }
    } catch (err) {
      authErrorMsg.textContent = "Error conectando con el servidor de autenticación.";
    }
  });

  loginPassword.addEventListener("keydown", (e) => {
    if (e.key === "Enter") btnLoginSubmit.click();
  });

  btnLogout.addEventListener("click", async () => {
    await fetch("/api/auth/logout", { method: "POST" });
    authOverlay.style.display = "flex";
  });

  // 4. Settings Modal (.env live updates)
  btnOpenSettings.addEventListener("click", async () => {
    settingsOverlay.style.display = "flex";
    try {
      const res = await fetch("/api/settings");
      if (res.ok) {
        const s = await res.json();
        cfgGeminiKey.value = s.gemini_api_key_masked || "";
        cfgGeminiModel.value = s.gemini_model || "models/gemini-2.0-flash-exp";
        cfgGithubToken.value = s.github_token_masked || "";
        cfgGithubRepos.value = s.github_repos || "BrunoAle-115/Proyecto-Viernes-Pi";
        cfgSipProvider.value = s.sip_provider || "zadarma_chile";
        cfgCity.value = s.default_city || "santiago";
      }
    } catch (e) {
      console.error("Error cargando settings", e);
    }
  });

  btnCloseSettings.addEventListener("click", () => {
    settingsOverlay.style.display = "none";
  });

  btnSaveSettings.addEventListener("click", async () => {
    const payload = {
      gemini_api_key: cfgGeminiKey.value.trim(),
      gemini_model: cfgGeminiModel.value,
      github_token: cfgGithubToken.value.trim(),
      github_repos: cfgGithubRepos.value.trim(),
      sip_provider: cfgSipProvider.value,
      default_city: cfgCity.value
    };

    try {
      const res = await fetch("/api/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      appendLog("CONFIG", data.message || "Configuración .env guardada con éxito.", "log-success");
      settingsOverlay.style.display = "none";
      loadWeather();
    } catch (e) {
      alert("Error guardando configuraciones");
    }
  });

  // 5. Load Weather & Hourly Rain
  async function loadWeather() {
    try {
      const city = cfgCity ? cfgCity.value : "santiago";
      const res = await fetch(`/api/weather?city=${city}`);
      const w = await res.json();

      weatherTemp.textContent = `${w.current_temp}°C`;
      weatherCity.textContent = `${w.city}, Chile`;
      weatherCond.textContent = w.condition;
      weatherApparent.textContent = `${w.apparent_temp}°C`;
      weatherHumidity.textContent = `${w.humidity}%`;

      if (w.will_rain) {
        rainAlertBadge.textContent = `☔ LLUVIA (${w.max_rain_probability}%)`;
        rainAlertBadge.className = "header-badge badge-urgent";
      } else {
        rainAlertBadge.textContent = "SIN LLUVIA";
        rainAlertBadge.className = "header-badge badge-approved";
      }

      hourlyForecast.innerHTML = "";
      if (w.hourly && w.hourly.length > 0) {
        w.hourly.slice(0, 8).forEach((h) => {
          const chip = document.createElement("div");
          chip.className = "hourly-chip";
          chip.innerHTML = `
            <div>${h.time}</div>
            <div style="font-weight:700; color:#fff;">${h.temperature}°</div>
            <div class="hourly-chip-rain">☔ ${h.rain_prob}%</div>
          `;
          hourlyForecast.appendChild(chip);
        });
      }
    } catch (e) {
      console.error("Error cargando clima", e);
    }
  }

  // 6. Load Chilean News (T13 / BioBio)
  async function loadNews() {
    try {
      const res = await fetch("/api/news");
      const data = await res.json();
      newsList.innerHTML = "";

      if (!data.news || data.news.length === 0) {
        newsList.innerHTML = '<div class="empty-notice">No se pudieron sintonizar noticias en vivo.</div>';
        return;
      }

      data.news.forEach((n) => {
        const item = document.createElement("div");
        item.className = "news-item";
        item.innerHTML = `
          <div class="news-header">
            <span>${n.source}</span>
            <span>${n.pub_date ? n.pub_date.slice(0, 16) : 'Hoy'}</span>
          </div>
          <div class="news-title">${n.title}</div>
        `;
        newsList.appendChild(item);
      });
    } catch (e) {
      console.error("Error cargando noticias", e);
    }
  }

  // 7. Load Mini-RAG Personal Memory & Routines
  async function loadMemory() {
    try {
      const res = await fetch("/api/memory");
      const data = await res.json();
      memoryList.innerHTML = "";

      if (!data.memories || data.memories.length === 0) {
        memoryList.innerHTML = '<div class="empty-notice">No hay recuerdos registrados en el Mini-RAG.</div>';
        return;
      }

      data.memories.forEach((m) => {
        const item = document.createElement("div");
        item.className = "memory-item";
        item.innerHTML = `
          <div style="display:flex; justify-content:space-between;">
            <span class="memory-concept">// ${m.key_concept.toUpperCase()}</span>
            <span class="badge-approved" style="font-size:9px;">${m.category.toUpperCase()}</span>
          </div>
          <div style="color:var(--text-main); margin-top:3px;">${m.content}</div>
        `;
        memoryList.appendChild(item);
      });
    } catch (e) {
      console.error("Error cargando memoria", e);
    }
  }

  // 8. Load Discovered Devices Matrix
  async function loadDevices() {
    try {
      const res = await fetch("/api/devices");
      const devices = await res.json();
      deviceMatrix.innerHTML = "";

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

  // 9. Load Triaged Emails & GitHub PRs
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
          <div style="display:flex; justify-content:space-between;">
            <span style="color:var(--cyan-stark); font-weight:700;">${m.source}: ${m.sender.split("<")[0]}</span>
            <span class="badge-urgent">URGENTE</span>
          </div>
          <div style="color:#fff; font-weight:600;">${m.subject}</div>
          <div style="font-size:11px; color:var(--text-dim);">${m.snippet}</div>
        `;
        emailList.appendChild(item);
      });
    } catch (e) {}
  }

  async function loadGithub() {
    try {
      const res = await fetch("/api/github");
      const data = await res.json();
      githubList.innerHTML = "";

      if (!data.prs || data.prs.length === 0) {
        githubList.innerHTML = '<div class="empty-notice">No hay PRs abiertas en este momento.</div>';
        return;
      }

      data.prs.forEach((pr) => {
        const item = document.createElement("div");
        item.className = "pr-item";
        const isApproved = pr.status === "APPROVED";
        const badge = isApproved ? '<span class="badge-approved">✓ APROBADA</span>' : `<span class="header-badge">${pr.status}</span>`;

        item.innerHTML = `
          <div style="display:flex; justify-content:space-between;">
            <span style="color:var(--cyan-stark); font-weight:700;">${pr.repo} #${pr.number}</span>
            ${badge}
          </div>
          <div style="color:#fff;">${pr.title}</div>
          <div style="font-size:11px; color:var(--text-dim); margin-top:2px;">
            ${isApproved ? 'Aprobada por: ' + pr.approved_by.join(', ') : 'Revisión pendiente'}
          </div>
        `;
        githubList.appendChild(item);
      });
    } catch (e) {}
  }

  function loadAllData() {
    loadWeather();
    loadNews();
    loadMemory();
    loadDevices();
    loadEmails();
    loadGithub();
  }

  // 10. WebSocket Telemetry Stream
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
            voiceStateTag.textContent = "EN ESPERA // 'OYE VIERNES'";
            voiceStateTag.style.color = "var(--cyan-stark)";
          }
        } else if (msg.type === "event") {
          appendLog(msg.topic, JSON.stringify(msg.data), "log-info");
        }
      } catch (err) {}
    };

    ws.onclose = () => setTimeout(connectWs, 2000);
  }
  connectWs();

  function appendLog(topic, text, typeClass = "log-system") {
    const entry = document.createElement("div");
    entry.className = `log-entry ${typeClass}`;
    entry.textContent = `[${topic.toUpperCase()}] ${text}`;
    termLogs.appendChild(entry);
    termLogs.scrollTop = termLogs.scrollHeight;
  }

  // Handlers & Actions
  window.triggerWol = async (target) => {
    appendLog("WOL", `Transmitiendo Magic Packet a ${target}...`, "log-info");
    const res = await fetch("/api/wol", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target })
    });
    const data = await res.json();
    appendLog("WOL", data.message || "Paquete enviado.", "log-success");
    setTimeout(loadDevices, 3000);
  };

  window.toggleLight = async (target) => {
    const res = await fetch("/api/lights", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target, action: "toggle" })
    });
    const data = await res.json();
    appendLog("IOT", data.message, "log-success");
  };

  btnPromptSend.addEventListener("click", async () => {
    const text = promptInput.value.trim();
    if (!text) return;
    promptInput.value = "";
    appendLog("BRUNO", text, "log-info");

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
    appendLog("VOZ", "Reconocimiento de voz activo. Puedes hablar ahora.", "log-info");
    await fetch("/api/wakeword/trigger", { method: "POST" });
  });

  btnRescanNet.addEventListener("click", async () => {
    appendLog("RED", "Escaneando subred local con ARP...", "log-info");
    await fetch("/api/scan", { method: "POST" });
    await loadDevices();
  });

  btnMakeCall.addEventListener("click", async () => {
    const num = phoneInput.value.trim();
    if (!num) return;
    appendLog("SIP", `Marcando a celular ${num}...`, "log-info");
    const res = await fetch("/api/call", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ phone_number: num })
    });
    const data = await res.json();
    appendLog("SIP", data.message, "log-success");
  });

  btnAddMemory.addEventListener("click", async () => {
    const concept = prompt("Concepto o etiqueta de la memoria (ej: rutina_gym, comida_favorita):");
    if (!concept) return;
    const content = prompt(`Detalle a recordar para '${concept}':`);
    if (!content) return;

    await fetch("/api/memory", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ category: "routine", key_concept: concept, content })
    });
    appendLog("MEMORIA", `Nueva rutina guardada en Mini-RAG: ${concept}`, "log-success");
    loadMemory();
  });
});
