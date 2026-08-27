/**
 * V.I.E.R.N.E.S. 2.0 - STARK INDUSTRIES HUD JAVASCRIPT CONTROLLER (SECURITY HARDENED)
 * Anti-XSS, Secure Authenticated WebSockets, Vector RAG Interface.
 */

// Utility: Anti-XSS HTML Sanitizer
function escapeHtml(str) {
  if (!str) return "";
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

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
  let authToken = localStorage.getItem("viernes_auth_token") || "";

  // --- STARK AUDIO PROCEDURAL SFX SYNTHESIZER (Web Audio API) ---
  const StarkAudio = {
    ctx: null,
    init() {
      if (!this.ctx) {
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        if (AudioCtx) this.ctx = new AudioCtx();
      }
    },
    playBlip(freq = 950, duration = 0.035) {
      try {
        this.init();
        if (!this.ctx) return;
        const osc = this.ctx.createOscillator();
        const gain = this.ctx.createGain();
        osc.type = "sine";
        osc.frequency.setValueAtTime(freq, this.ctx.currentTime);
        osc.frequency.exponentialRampToValueAtTime(freq * 1.4, this.ctx.currentTime + duration);
        gain.gain.setValueAtTime(0.06, this.ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, this.ctx.currentTime + duration);
        osc.connect(gain);
        gain.connect(this.ctx.destination);
        osc.start();
        osc.stop(this.ctx.currentTime + duration);
      } catch (e) {}
    },
    playSuccess() {
      this.playBlip(800, 0.04);
      setTimeout(() => this.playBlip(1200, 0.06), 45);
    },
    playAlert() {
      this.playBlip(400, 0.08);
      setTimeout(() => this.playBlip(320, 0.1), 80);
    }
  };

  // 1. Clock
  function updateClock() {
    const now = new Date();
    liveClock.textContent = now.toLocaleTimeString("es-CL", { hour12: false });
    liveDate.textContent = now.toLocaleDateString("es-CL", { weekday: "short", day: "numeric", month: "short", year: "numeric" }).toUpperCase() + " // SANTIAGO, CHILE";
  }
  setInterval(updateClock, 1000);
  updateClock();

  // 2. Quantum Arc Reactor Visualizer (Ultra-Optimized Lightweight Canvas)
  let phase = 0;
  let lastFrameTime = 0;
  function resizeCanvas() {
    const rect = canvas.getBoundingClientRect();
    const dpr = Math.min(window.devicePixelRatio || 1, 2); // Cap at 2x max to prevent 4k mobile lag
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);
  }
  window.addEventListener("resize", resizeCanvas, { passive: true });
  resizeCanvas();

  function drawWaveform(timestamp = 0) {
    if (authOverlay && authOverlay.style.display !== "none") {
      setTimeout(() => requestAnimationFrame(drawWaveform), 200);
      return;
    }
    if (document.hidden) {
      requestAnimationFrame(drawWaveform);
      return;
    }
    // Cap visualizer at 35 FPS to yield main-thread CPU cycles to pointer interactions (INP < 50ms)
    if (timestamp - lastFrameTime < 28) {
      requestAnimationFrame(drawWaveform);
      return;
    }
    lastFrameTime = timestamp;

    const rect = canvas.getBoundingClientRect();
    const width = rect.width;
    const height = rect.height;
    const cx = width / 2;
    const cy = height / 2;

    ctx.clearRect(0, 0, width, height);

    const baseColor = isSpeaking ? "#ffb700" : "#00f0ff";
    const glowColor = isSpeaking ? "rgba(255, 183, 0, 0.25)" : "rgba(0, 240, 255, 0.25)";

    // 1. Anillo Segmentado Arc Reactor
    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate(phase * 0.4);
    ctx.strokeStyle = baseColor;
    ctx.lineWidth = 1.5;

    const segments = 10;
    const ringRadius = 22 + currentAudioRms * 16;
    for (let i = 0; i < segments; i++) {
      const angle = (i * 2 * Math.PI) / segments;
      ctx.beginPath();
      ctx.arc(0, 0, ringRadius, angle, angle + 0.32);
      ctx.stroke();
    }

    // Anillo interno en contra-rotación
    ctx.rotate(-phase * 0.8);
    ctx.beginPath();
    ctx.arc(0, 0, 9 + (isSpeaking ? Math.sin(phase * 2) * 2.5 : currentAudioRms * 6), 0, Math.PI * 2);
    ctx.fillStyle = glowColor;
    ctx.fill();
    ctx.stroke();
    ctx.restore();

    // 2. Ondas Cuánticas Multicapa (Glow por multi-stroke de bajo costo)
    const baseAmp = isSpeaking ? 28 : Math.max(6, currentAudioRms * 80);
    const layers = [
      { color: baseColor, freq: 0.035, speed: 1.0, width: 1.8 },
      { color: "rgba(0, 255, 157, 0.7)", freq: 0.06, speed: -1.2, width: 1.0 }
    ];

    layers.forEach((l) => {
      ctx.beginPath();
      ctx.lineWidth = l.width;
      ctx.strokeStyle = l.color;

      for (let x = 0; x < width; x += 4) {
        const dist = Math.abs(x - cx) / (width * 0.5);
        const envelope = Math.max(0, 1 - dist * dist);
        const y = cy + Math.sin(x * l.freq + phase * l.speed) * baseAmp * envelope;
        if (x === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
    });

    phase += 0.06;
    requestAnimationFrame(drawWaveform);
  }
  requestAnimationFrame(drawWaveform);

  // Helper fetch with Auth Headers & 401 handling
  async function secureFetch(url, options = {}) {
    options.headers = options.headers || {};
    if (authToken) {
      options.headers["Authorization"] = `Bearer ${authToken}`;
    }
    const res = await fetch(url, options);
    if (res.status === 401) {
      authOverlay.style.display = "flex";
    }
    return res;
  }

  // 3. Authentication Check
  async function checkAuth() {
    try {
      const res = await secureFetch("/api/auth/me");
      if (res.ok) {
        authOverlay.style.display = "none";
        loadAllData();
        connectWs();
      } else {
        authOverlay.style.display = "flex";
      }
    } catch (e) {
      authOverlay.style.display = "flex";
    }
  }
  checkAuth();

  window.handleLoginSubmit = async () => {
    const errorEl = document.getElementById("auth-error-msg");
    const emailEl = document.getElementById("login-email");
    const passEl = document.getElementById("login-password");
    const submitBtn = document.getElementById("btn-login-submit");
    const overlay = document.getElementById("auth-modal-overlay");

    if (errorEl) errorEl.textContent = "";
    const email = (emailEl ? emailEl.value : "").trim();
    const password = passEl ? passEl.value : "";

    if (!email || !password) {
      if (errorEl) errorEl.textContent = "Por favor ingresa correo y contraseña.";
      return;
    }

    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.textContent = "AUTENTICANDO...";
    }

    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        authToken = data.token;
        localStorage.setItem("viernes_auth_token", authToken);
        if (overlay) overlay.style.display = "none";
        appendLog("AUTH", `Bienvenido señor Bruno (${escapeHtml(email)}). Acceso táctico concedido.`, "log-success");
        loadAllData();
        connectWs();
      } else {
        if (errorEl) errorEl.textContent = data.detail || "Contraseña o correo no autorizados.";
      }
    } catch (err) {
      if (errorEl) errorEl.textContent = "Error conectando con el servidor de autenticación.";
    } finally {
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.textContent = "INICIAR SESIÓN EN V.I.E.R.N.E.S.";
      }
    }
  };

  if (btnLoginSubmit) {
    btnLoginSubmit.addEventListener("click", (e) => {
      e.preventDefault();
      window.handleLoginSubmit();
    });
  }

  if (loginPassword) {
    loginPassword.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        window.handleLoginSubmit();
      }
    });
  }

  btnLogout.addEventListener("click", async () => {
    await fetch("/api/auth/logout", { method: "POST" });
    authToken = "";
    localStorage.removeItem("viernes_auth_token");
    authOverlay.style.display = "flex";
    if (ws) ws.close();
  });

  // 4. Settings Modal (.env live updates)
  btnOpenSettings.addEventListener("click", async () => {
    settingsOverlay.style.display = "flex";
    try {
      const res = await secureFetch("/api/settings");
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
      const res = await secureFetch("/api/settings", {
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
      const res = await fetch(`/api/weather?city=${encodeURIComponent(city)}`);
      const w = await res.json();

      weatherTemp.textContent = `${w.current_temp}°C`;
      weatherCity.textContent = `${escapeHtml(w.city)}, Chile`;
      weatherCond.textContent = escapeHtml(w.condition);
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
            <div>${escapeHtml(h.time)}</div>
            <div style="font-weight:700; color:#fff;">${escapeHtml(String(h.temperature))}°</div>
            <div class="hourly-chip-rain">☔ ${escapeHtml(String(h.rain_prob))}%</div>
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
            <span>${escapeHtml(n.source)}</span>
            <span>${escapeHtml(n.pub_date ? n.pub_date.slice(0, 16) : 'Hoy')}</span>
          </div>
          <div class="news-title">${escapeHtml(n.title)}</div>
        `;
        newsList.appendChild(item);
      });
    } catch (e) {
      console.error("Error cargando noticias", e);
    }
  }

  // 7. Load Vector RAG Personal Memory & Routines
  async function loadMemory() {
    try {
      const res = await secureFetch("/api/memory");
      const data = await res.json();
      memoryList.innerHTML = "";

      if (!data.memories || data.memories.length === 0) {
        memoryList.innerHTML = '<div class="empty-notice">No hay recuerdos registrados en el Vector RAG.</div>';
        return;
      }

      data.memories.forEach((m) => {
        const item = document.createElement("div");
        item.className = "memory-item";
        item.innerHTML = `
          <div style="display:flex; justify-content:space-between;">
            <span class="memory-concept">// ${escapeHtml(m.key_concept.toUpperCase())}</span>
            <span class="badge-approved" style="font-size:9px;">${escapeHtml(m.category.toUpperCase())}</span>
          </div>
          <div style="color:var(--text-main); margin-top:3px;">${escapeHtml(m.content)}</div>
        `;
        memoryList.appendChild(item);
      });
    } catch (e) {
      console.error("Error cargando memoria vectorial", e);
    }
  }

  // 8. Load Discovered Devices Matrix (WiZ, AC, WoL, IoT)
  async function loadDevices() {
    try {
      const res = await secureFetch("/api/devices");
      const devices = await res.json();
      deviceMatrix.innerHTML = "";

      devices.forEach((dev) => {
        const card = document.createElement("div");
        card.className = "device-card";
        card.style.flexDirection = "column";
        card.style.alignItems = "stretch";
        card.style.gap = "6px";

        const isOnline = dev.status === "online";
        const statusBadge = isOnline ? '<span style="color:var(--green-matrix)">● ONLINE</span>' : '<span style="color:var(--text-dim)">○ OFFLINE</span>';

        let actionControls = "";
        if (dev.wol_enabled || dev.type === "desktop") {
          actionControls = `
            <div style="display:flex; justify-content:flex-end;">
              <button class="btn-wol" onclick="triggerWol('${escapeHtml(dev.ip)}')">ENCENDER WOL</button>
            </div>
          `;
        } else if (dev.type === "wiz_light" || dev.type === "light") {
          actionControls = `
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:6px;">
              <button class="btn-light-toggle" onclick="toggleLight('${escapeHtml(dev.ip)}')">ON / OFF</button>
              <button class="btn-palette" onclick="getLightStatus('${escapeHtml(dev.ip)}')">📊 PALETA ACTUAL</button>
              <div class="palette-group">
                <button class="btn-palette warm" onclick="setLightPalette('${escapeHtml(dev.ip)}', 'cálida')">Cálida</button>
                <button class="btn-palette cool" onclick="setLightPalette('${escapeHtml(dev.ip)}', 'fría')">Fría</button>
                <button class="btn-palette" onclick="setLightPalette('${escapeHtml(dev.ip)}', 'día')">Día</button>
                <button class="btn-palette relax" onclick="setLightPalette('${escapeHtml(dev.ip)}', 'relax')">Relax</button>
                <button class="btn-palette party" onclick="setLightPalette('${escapeHtml(dev.ip)}', 'fiesta')">Fiesta</button>
                <button class="btn-palette" style="border-color:#00f0ff; color:#00f0ff;" onclick="setLightPalette('${escapeHtml(dev.ip)}', 'cyan')">Cyan</button>
                <button class="btn-palette" style="border-color:#ffb700; color:#ffb700;" onclick="setLightPalette('${escapeHtml(dev.ip)}', 'oro')">Oro</button>
              </div>
            </div>
          `;
        } else if (dev.type === "air_conditioner") {
          actionControls = `
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:6px;">
              <button class="btn-light-toggle" onclick="setAcControl('${escapeHtml(dev.ip)}', true, 22, 'cool')">❄️ FRÍO 22°C</button>
              <button class="btn-palette warm" onclick="setAcControl('${escapeHtml(dev.ip)}', true, 24, 'heat')">🔥 CALOR 24°C</button>
              <button class="btn-palette" onclick="setAcControl('${escapeHtml(dev.ip)}', false, 22, 'cool')">APAGAR</button>
              <div class="ac-controls">
                <button class="btn-ac-temp" onclick="setAcControl('${escapeHtml(dev.ip)}', true, 18, 'cool')">18°</button>
                <button class="btn-ac-temp" onclick="setAcControl('${escapeHtml(dev.ip)}', true, 20, 'cool')">20°</button>
                <button class="btn-ac-temp" onclick="setAcControl('${escapeHtml(dev.ip)}', true, 22, 'cool')">22°</button>
                <button class="btn-ac-temp" onclick="setAcControl('${escapeHtml(dev.ip)}', true, 24, 'cool')">24°</button>
              </div>
            </div>
          `;
        }

        card.innerHTML = `
          <div style="display:flex; justify-content:space-between; align-items:center;">
            <div class="device-info">
              <div class="device-name">${escapeHtml(dev.alias)} ${statusBadge}</div>
              <div class="device-sub">IP: ${escapeHtml(dev.ip)} | MAC: ${escapeHtml(dev.mac || "Auto-Resolv")} | ${escapeHtml(dev.vendor || "IoT")}</div>
            </div>
          </div>
          ${actionControls}
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
      const res = await secureFetch("/api/emails");
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
            <span style="color:var(--cyan-stark); font-weight:700;">${escapeHtml(m.source)}: ${escapeHtml(m.sender.split("<")[0])}</span>
            <span class="badge-urgent">URGENTE</span>
          </div>
          <div style="color:#fff; font-weight:600;">${escapeHtml(m.subject)}</div>
          <div style="font-size:11px; color:var(--text-dim);">${escapeHtml(m.snippet)}</div>
        `;
        emailList.appendChild(item);
      });
    } catch (e) {}
  }

  async function loadGithub() {
    try {
      const res = await secureFetch("/api/github");
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
        const badge = isApproved ? '<span class="badge-approved">✓ APROBADA</span>' : `<span class="header-badge">${escapeHtml(pr.status)}</span>`;

        item.innerHTML = `
          <div style="display:flex; justify-content:space-between;">
            <span style="color:var(--cyan-stark); font-weight:700;">${escapeHtml(pr.repo)} #${pr.number}</span>
            ${badge}
          </div>
          <div style="color:#fff;">${escapeHtml(pr.title)}</div>
          <div style="font-size:11px; color:var(--text-dim); margin-top:2px;">
            ${isApproved ? 'Aprobada por: ' + escapeHtml(pr.approved_by.join(', ')) : 'Revisión pendiente'}
          </div>
        `;
        githubList.appendChild(item);
      });
    } catch (e) {}
  }

  function loadAllData() {
    Promise.allSettled([
      loadWeather(),
      loadNews(),
      loadMemory(),
      loadDevices(),
      loadEmails(),
      loadGithub()
    ]);
  }

  // 10. Authenticated WebSocket Telemetry Stream (Anti-Hijacking)
  let ws;
  function connectWs() {
    if (ws && ws.readyState === WebSocket.OPEN) return;
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const tokenQuery = authToken ? `?token=${encodeURIComponent(authToken)}` : "";
    ws = new WebSocket(`${protocol}//${window.location.host}/ws${tokenQuery}`);

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === "telemetry") {
          const t = msg.data;
          const newTemp = `${t.cpu.temperature_c}°C`;
          if (cpuTemp.textContent !== newTemp) cpuTemp.textContent = newTemp;
          const newLoad = `${Math.round(t.cpu.percent)}%`;
          if (cpuLoad.textContent !== newLoad) cpuLoad.textContent = newLoad;
          const newRam = `${Math.round(t.ram.percent)}%`;
          if (ramUsage.textContent !== newRam) ramUsage.textContent = newRam;
          const newIp = `IP: ${escapeHtml(t.local_ip)}`;
          if (hostIp.textContent !== newIp) hostIp.textContent = newIp;

          currentAudioRms = t.audio_rms || 0.02;
          const newSpeaking = t.is_speaking || false;
          if (isSpeaking !== newSpeaking) {
            isSpeaking = newSpeaking;
            if (isSpeaking) {
              voiceStateTag.textContent = "TRANSMITIENDO VOZ";
              voiceStateTag.style.color = "var(--gold-stark)";
            } else {
              voiceStateTag.textContent = "EN ESPERA // 'OYE VIERNES'";
              voiceStateTag.style.color = "var(--cyan-stark)";
            }
          }
        } else if (msg.type === "event") {
          appendLog(msg.topic, JSON.stringify(msg.data), "log-info");
        }
      } catch (err) {}
    };

    ws.onclose = () => {
      // Reintentar solo si está autenticado
      if (authToken) setTimeout(connectWs, 3000);
    };
  }

  function appendLog(topic, text, typeClass = "log-system") {
    // Mantener un máximo de 40 logs para evitar fugas de memoria y lag de scroll
    while (termLogs.children.length >= 40) {
      termLogs.removeChild(termLogs.firstChild);
    }
    const entry = document.createElement("div");
    entry.className = `log-entry ${typeClass}`;
    entry.textContent = `[${escapeHtml(topic.toUpperCase())}] ${text}`;
    termLogs.appendChild(entry);
    termLogs.scrollTop = termLogs.scrollHeight;
  }

  // Handlers & Actions
  window.triggerWol = async (target) => {
    appendLog("WOL", `Transmitiendo Magic Packet a ${target}...`, "log-info");
    const res = await secureFetch("/api/wol", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target })
    });
    const data = await res.json();
    appendLog("WOL", data.message || "Paquete enviado.", "log-success");
    setTimeout(loadDevices, 3000);
  };

  window.toggleLight = async (target) => {
    const res = await secureFetch("/api/lights", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target, action: "toggle" })
    });
    const data = await res.json();
    appendLog("IOT", data.message, "log-success");
  };

  window.setLightPalette = async (target, palette) => {
    appendLog("WIZ", `Configurando paleta '${palette}' en luz ${target}...`, "log-info");
    const res = await secureFetch("/api/lights", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target, action: "palette", palette: palette })
    });
    const data = await res.json();
    appendLog("WIZ", data.message, "log-success");
  };

  window.getLightStatus = async (target) => {
    appendLog("WIZ", `Consultando estado getPilot en ${target}...`, "log-info");
    const res = await secureFetch(`/api/lights/status?target=${encodeURIComponent(target)}`);
    const data = await res.json();
    appendLog("WIZ", data.summary || "Luz WiZ no responde.", data.online ? "log-success" : "log-warn");
  };

  window.setAcControl = async (target, power, temp, mode) => {
    const act = power ? `Ajustando AC a ${temp}°C (${mode})...` : "Apagando Aire Acondicionado...";
    appendLog("AIRSYS", act, "log-info");
    const res = await secureFetch("/api/ac", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target, power, temperature: temp, mode: mode, fan_speed: "auto" })
    });
    const data = await res.json();
  window.triggerFrutifantastico = async () => {
    appendLog("FIESTA", "🍓🎉 ¡ACTIVANDO MODO FRUTIFANTÁSTICO! (WiZ Fiesta + The Weeknd en Google TV/Home)...", "log-warn");
    const res = await secureFetch("/api/macro/frutifantastico", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ track: "blinding_lights" })
    });
    const data = await res.json();
    appendLog("VIERNES", data.report || "Modo Frutifantástico activo.", "log-success");
  };

  const btnFrutifantastico = document.getElementById("btn-frutifantastico");
  if (btnFrutifantastico) {
    btnFrutifantastico.addEventListener("click", () => {
      window.triggerFrutifantastico();
    });
  }

  btnPromptSend.addEventListener("click", async () => {
    const text = promptInput.value.trim();
    if (!text) return;
    promptInput.value = "";
    appendLog("BRUNO", text, "log-info");

    const res = await secureFetch("/api/prompt", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt: text })
    });
    const data = await res.json();
    appendLog("VIERNES", data.response, "log-system");
    loadMemory(); // Actualizar recuerdos si se auto-alimentó la DB vectorial
  });

  promptInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") btnPromptSend.click();
  });

  btnTalkMic.addEventListener("click", async () => {
    appendLog("VOZ", "Reconocimiento de voz activo. Puedes hablar ahora.", "log-info");
    await secureFetch("/api/wakeword/trigger", { method: "POST" });
  });

  btnRescanNet.addEventListener("click", async () => {
    appendLog("RED", "Iniciando Reconocimiento Rápido Nmap + NetBIOS en subred activa...", "log-info");
    await secureFetch("/api/scan", { method: "POST" });
    await loadDevices();
    appendLog("RED", "✓ Reconocimiento de red completado y matriz actualizada.", "log-success");
  });

  btnMakeCall.addEventListener("click", async () => {
    const num = phoneInput.value.trim();
    if (!num) return;
    appendLog("SIP", `Marcando a celular ${num}...`, "log-info");
    const res = await secureFetch("/api/call", {
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

    await secureFetch("/api/memory", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ category: "routine", key_concept: concept, content })
    });
    appendLog("MEMORIA", `Nueva rutina vectorizada en RAG: ${concept}`, "log-success");
    loadMemory();
  });
});
