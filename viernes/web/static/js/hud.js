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
  let cWidth = 300, cHeight = 80;
  function resizeCanvas() {
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    cWidth = rect.width;
    cHeight = rect.height;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = cWidth * dpr;
    canvas.height = cHeight * dpr;
    if (ctx) ctx.scale(dpr, dpr);
  }
  window.addEventListener("resize", resizeCanvas, { passive: true });
  resizeCanvas();

  function drawWaveform(timestamp = 0) {
    if (authOverlay && !authOverlay.classList.contains("authenticated")) {
      setTimeout(() => requestAnimationFrame(drawWaveform), 250);
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

    const width = cWidth;
    const height = cHeight;
    const cx = width / 2;
    const cy = height / 2;

    if (!ctx) return;
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
    options.credentials = "include"; // Enviar cookies de sesión HTTPOnly
    if (authToken) {
      options.headers["Authorization"] = `Bearer ${authToken}`;
    }
    const res = await fetch(url, options);
    if (res.status === 401) {
      authToken = "";
      localStorage.removeItem("viernes_auth_token");
      if (authOverlay) authOverlay.classList.remove("authenticated");
    }
    return res;
  }

  const sessionUserBadge = document.getElementById("session-user-badge");

  // 3. Authentication Check
  async function checkAuth() {
    try {
      const res = await secureFetch("/api/auth/me");
      if (res.ok) {
        const authData = await res.json();
        const email = (authData.user && authData.user.email) ? authData.user.email : "BRUNO";
        if (sessionUserBadge) {
          sessionUserBadge.textContent = `👤 ${escapeHtml(email.split('@')[0].toUpperCase())}`;
          sessionUserBadge.style.display = "inline-block";
        }
        if (authOverlay) authOverlay.classList.add("authenticated");
        loadAllData();
        connectWs();
      } else {
        authToken = "";
        localStorage.removeItem("viernes_auth_token");
        if (sessionUserBadge) sessionUserBadge.style.display = "none";
        if (authOverlay) authOverlay.classList.remove("authenticated");
      }
    } catch (e) {
      authToken = "";
      localStorage.removeItem("viernes_auth_token");
      if (sessionUserBadge) sessionUserBadge.style.display = "none";
      if (authOverlay) authOverlay.classList.remove("authenticated");
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
        credentials: "include",
        body: JSON.stringify({ email, password })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        authToken = data.token;
        localStorage.setItem("viernes_auth_token", authToken);
        if (sessionUserBadge) {
          sessionUserBadge.textContent = `👤 ${escapeHtml(email.split('@')[0].toUpperCase())}`;
          sessionUserBadge.style.display = "inline-block";
        }
        if (overlay) overlay.classList.add("authenticated");
        appendLog("AUTH", `Bienvenido señor Bruno (${escapeHtml(email)}). Acceso táctico concedido.`, "log-success");
        loadAllData();
        connectWs();
      } else {
        if (errorEl) errorEl.textContent = data.detail || "Contraseña o correo no válidos.";
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

  btnLogout.addEventListener("click", async () => {
    try {
      await fetch("/api/auth/logout", { method: "POST", credentials: "include" });
    } catch (e) {}
    authToken = "";
    localStorage.removeItem("viernes_auth_token");
    if (sessionUserBadge) sessionUserBadge.style.display = "none";
    if (authOverlay) authOverlay.classList.remove("authenticated");
    if (ws) ws.close();
  });

  // 4. Settings Modal (.env live updates)
  const btnFetchModels = document.getElementById("btn-fetch-models");

  async function fetchAndPopulateGeminiModels(customKey = "", selectedModel = "") {
    if (!cfgGeminiModel) return;
    const previousSelection = selectedModel || cfgGeminiModel.value;
    cfgGeminiModel.innerHTML = '<option value="">Consultando catálogo oficial de Google AI Studio...</option>';

    try {
      const queryKey = customKey && !customKey.includes("...") ? `?api_key=${encodeURIComponent(customKey)}` : "";
      const res = await secureFetch(`/api/gemini/models${queryKey}`);
      if (res.ok) {
        const data = await res.json();
        const models = data.models || [];
        cfgGeminiModel.innerHTML = "";

        if (models.length === 0) {
          cfgGeminiModel.innerHTML = '<option value="models/gemini-2.0-flash-exp">Gemini 2.0 Flash (Predefinido)</option>';
          return;
        }

        models.forEach((m) => {
          const opt = document.createElement("option");
          opt.value = m.id;
          const liveTag = m.is_live_capable ? " [⚡ LIVE STREAMING]" : "";
          opt.textContent = `${m.displayName}${liveTag}`;
          if (m.id === previousSelection || m.is_active || (m.clean_id && previousSelection.endsWith(m.clean_id))) {
            opt.selected = true;
          }
          cfgGeminiModel.appendChild(opt);
        });
      } else {
        cfgGeminiModel.innerHTML = '<option value="models/gemini-2.0-flash-exp">Gemini 2.0 Flash (Predefinido)</option>';
      }
    } catch (err) {
      cfgGeminiModel.innerHTML = '<option value="models/gemini-2.0-flash-exp">Gemini 2.0 Flash (Fallback)</option>';
    }
  }

  if (btnFetchModels) {
    btnFetchModels.addEventListener("click", () => {
      const keyVal = cfgGeminiKey.value.trim();
      fetchAndPopulateGeminiModels(keyVal);
    });
  }

  let keyDebounceTimer = null;
  if (cfgGeminiKey) {
    cfgGeminiKey.addEventListener("input", () => {
      clearTimeout(keyDebounceTimer);
      const val = cfgGeminiKey.value.trim();
      if (val.length > 25 && !val.includes("...")) {
        keyDebounceTimer = setTimeout(() => {
          fetchAndPopulateGeminiModels(val);
        }, 600);
      }
    });
  }

  btnOpenSettings.addEventListener("click", async () => {
    settingsOverlay.style.display = "flex";
    try {
      const res = await secureFetch("/api/settings");
      if (res.ok) {
        const s = await res.json();
        cfgGeminiKey.value = s.gemini_api_key_masked || "";
        cfgGithubToken.value = s.github_token_masked || "";
        cfgGithubRepos.value = s.github_repos || "BrunoAle-115/Proyecto-Viernes-Pi";
        cfgSipProvider.value = s.sip_provider || "zadarma_chile";
        cfgCity.value = s.default_city || "santiago";
        await fetchAndPopulateGeminiModels("", s.gemini_model);
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
        item.style.cursor = "pointer";
        const otpBadge = m.otp ? `<span class="badge-approved" style="background:rgba(255,183,0,0.2);color:var(--gold-stark);border-color:var(--gold-stark);">⚡ OTP: ${escapeHtml(m.otp.code)}</span>` : '<span class="badge-urgent">URGENTE</span>';
        
        item.innerHTML = `
          <div style="display:flex; justify-content:space-between; align-items:center;">
            <span style="color:var(--cyan-stark); font-weight:700;">${escapeHtml(m.source)}: ${escapeHtml(m.sender.split("<")[0])}</span>
            ${otpBadge}
          </div>
          <div style="color:#fff; font-weight:600; margin-top:2px;">${escapeHtml(m.subject)}</div>
          <div style="font-size:11px; color:var(--text-dim); margin-top:2px;">${escapeHtml(m.snippet)}</div>
        `;
        item.addEventListener("click", () => {
          if (window.openEmailModal) window.openEmailModal(m);
        });
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
  window.loadAllData = loadAllData;

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
  window.connectWs = connectWs;

  function appendLog(topic, text, typeClass = "log-system") {
    if (!termLogs) return;
    while (termLogs.children.length >= 40) {
      termLogs.removeChild(termLogs.firstChild);
    }
    const entry = document.createElement("div");
    entry.className = `log-entry ${typeClass}`;
    entry.textContent = `[${escapeHtml(topic.toUpperCase())}] ${text}`;
    termLogs.appendChild(entry);
    requestAnimationFrame(() => {
      termLogs.scrollTop = termLogs.scrollHeight;
    });
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
    appendLog("AIRSYS", data.message || "AC actualizado.", "log-success");
  };

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

  // --- SÍNTESIS DE VOZ PROCEDURAL Y WEB SPEECH API ---
  function speakText(text) {
    if (!window.speechSynthesis) return;
    try {
      window.speechSynthesis.cancel();
      const cleanText = text.replace(/\[.*?\]/g, "").replace(/[*_#`]/g, "").trim();
      if (!cleanText) return;

      const utterance = new SpeechSynthesisUtterance(cleanText);
      utterance.lang = "es-CL";
      utterance.rate = 1.04;
      utterance.pitch = 1.0;

      const voices = window.speechSynthesis.getVoices();
      const spanishVoice = voices.find(v => (v.lang.includes("es") && (v.name.includes("Female") || v.name.includes("Helena") || v.name.includes("Sabina") || v.name.includes("Google") || v.name.includes("Paulina") || v.name.includes("Monica")))) || voices.find(v => v.lang.includes("es"));
      if (spanishVoice) utterance.voice = spanishVoice;

      utterance.onstart = () => {
        isSpeaking = true;
        if (voiceStateTag) {
          voiceStateTag.textContent = "VIERNES // TRANSMITIENDO VOZ";
          voiceStateTag.style.color = "var(--gold-stark)";
        }
      };

      utterance.onend = () => {
        isSpeaking = false;
        if (voiceStateTag) {
          voiceStateTag.textContent = "EN ESPERA // 'OYE VIERNES'";
          voiceStateTag.style.color = "var(--cyan-stark)";
        }
      };

      utterance.onerror = () => {
        isSpeaking = false;
      };

      window.speechSynthesis.speak(utterance);
    } catch (e) {}
  }

  // --- RECONOCIMIENTO DE VOZ POR MICRÓFONO EN EL NAVEGADOR ---
  let recognition = null;
  const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (SpeechRec) {
    recognition = new SpeechRec();
    recognition.lang = "es-CL";
    recognition.continuous = false;
    recognition.interimResults = false;

    recognition.onstart = () => {
      btnTalkMic.textContent = "🎙️ ESCUCHANDO...";
      btnTalkMic.style.background = "rgba(255, 51, 102, 0.35)";
      btnTalkMic.style.borderColor = "var(--red-alert)";
      if (voiceStateTag) {
        voiceStateTag.textContent = "ESCUCHANDO ORDEN...";
        voiceStateTag.style.color = "var(--red-alert)";
      }
      StarkAudio.playBlip(600, 0.05);
    };

    recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript;
      if (transcript && promptInput) {
        promptInput.value = transcript;
        btnPromptSend.click();
      }
    };

    recognition.onerror = (e) => {
      btnTalkMic.textContent = "🎙️ HABLAR / MICRÓFONO";
      btnTalkMic.style.background = "";
      btnTalkMic.style.borderColor = "";
      appendLog("VOZ", "No se detectó audio en el micrófono del navegador.", "log-warn");
    };

    recognition.onend = () => {
      btnTalkMic.textContent = "🎙️ HABLAR / MICRÓFONO";
      btnTalkMic.style.background = "";
      btnTalkMic.style.borderColor = "";
      if (voiceStateTag && !isSpeaking) {
        voiceStateTag.textContent = "EN ESPERA // 'OYE VIERNES'";
        voiceStateTag.style.color = "var(--cyan-stark)";
      }
    };
  }

  btnPromptSend.addEventListener("click", async () => {
    const text = promptInput.value.trim();
    if (!text) return;
    promptInput.value = "";
    appendLog("BRUNO", text, "log-info");
    StarkAudio.playBlip(750, 0.04);

    btnPromptSend.disabled = true;
    btnPromptSend.textContent = "...";

    try {
      const res = await secureFetch("/api/prompt", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: text })
      });
      const data = await res.json();
      if (data && data.response) {
        appendLog("VIERNES", data.response, "log-system");
        speakText(data.response);
      }
      loadMemory();
    } catch (e) {
      appendLog("VIERNES", "Error al procesar comando con el núcleo de IA.", "log-warn");
    } finally {
      btnPromptSend.disabled = false;
      btnPromptSend.textContent = "ENVIAR";
    }
  });

  promptInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") btnPromptSend.click();
  });

  btnTalkMic.addEventListener("click", async () => {
    if (recognition) {
      try {
        recognition.start();
        appendLog("VOZ", "Micrófono del navegador activado. Habla ahora...", "log-info");
      } catch (err) {
        recognition.stop();
      }
    } else {
      appendLog("VOZ", "Activando escucha permanente en Raspberry Pi 5...", "log-info");
    }
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
    const concept = prompt("Concepto o etiqueta de la memoria (ej: cafe_favorito, stack_tecnologico):");
    if (!concept) return;
    const content = prompt(`Detalle a recordar para '${concept}':`);
    if (!content) return;

    await secureFetch("/api/memory", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ category: "preference", key_concept: concept, content })
    });
    appendLog("MEMORIA", `Nueva preferencia vectorizada en RAG: ${concept}`, "log-success");
    loadMemory();
  });

  // =========================================================================
  // 11. CONTROL REMOTO ANDROID TV, GOOGLE TV Y CAST
  // =========================================================================
  async function sendTvCommand(command, extraPayload = {}) {
    const targetIpEl = document.getElementById("tv-target-ip");
    const targetIp = targetIpEl ? targetIpEl.value : "192.168.100.25";
    StarkAudio.playBlip(850, 0.03);

    try {
      const payload = { target_ip: targetIp, command: command, ...extraPayload };
      const res = await secureFetch("/api/tv/remote", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      appendLog("REMOTE", data.message || `Comando '${command}' ejecutado en ${targetIp}`, "log-info");
    } catch (e) {
      appendLog("REMOTE", `Fallo al enviar comando '${command}' a ${targetIp}`, "log-warn");
    }
  }
  window.sendTvCommand = sendTvCommand;

  // D-Pad y Botones de Navegación
  document.getElementById("btn-dpad-up")?.addEventListener("click", () => sendTvCommand("dpad_up"));
  document.getElementById("btn-dpad-down")?.addEventListener("click", () => sendTvCommand("dpad_down"));
  document.getElementById("btn-dpad-left")?.addEventListener("click", () => sendTvCommand("dpad_left"));
  document.getElementById("btn-dpad-right")?.addEventListener("click", () => sendTvCommand("dpad_right"));
  document.getElementById("btn-dpad-ok")?.addEventListener("click", () => sendTvCommand("select"));

  document.getElementById("btn-tv-back")?.addEventListener("click", () => sendTvCommand("back"));
  document.getElementById("btn-tv-home")?.addEventListener("click", () => sendTvCommand("home"));
  document.getElementById("btn-tv-menu")?.addEventListener("click", () => sendTvCommand("menu"));
  document.getElementById("btn-tv-power")?.addEventListener("click", () => sendTvCommand("power_toggle"));
  document.getElementById("btn-tv-mute")?.addEventListener("click", () => sendTvCommand("mute"));

  document.getElementById("btn-tv-vol-up")?.addEventListener("click", () => sendTvCommand("volume_up"));
  document.getElementById("btn-tv-vol-down")?.addEventListener("click", () => sendTvCommand("volume_down"));
  document.getElementById("btn-tv-play-pause")?.addEventListener("click", () => sendTvCommand("play_pause"));

  // Lanzadores de Apps Rápidos
  document.getElementById("btn-app-yt-theweeknd")?.addEventListener("click", () => {
    sendTvCommand("play_youtube", { youtube_id: "4NRXx6U8ABQ" });
  });
  document.getElementById("btn-app-netflix")?.addEventListener("click", () => sendTvCommand("launch_app", { app_id: "netflix" }));
  document.getElementById("btn-app-prime")?.addEventListener("click", () => sendTvCommand("launch_app", { app_id: "prime_video" }));
  document.getElementById("btn-app-spotify")?.addEventListener("click", () => sendTvCommand("launch_app", { app_id: "spotify" }));

  // Navegación por Teclado Físico (D-Pad)
  window.addEventListener("keydown", (e) => {
    if (["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName)) return;
    if (e.key === "ArrowUp") { e.preventDefault(); document.getElementById("btn-dpad-up")?.click(); }
    else if (e.key === "ArrowDown") { e.preventDefault(); document.getElementById("btn-dpad-down")?.click(); }
    else if (e.key === "ArrowLeft") { e.preventDefault(); document.getElementById("btn-dpad-left")?.click(); }
    else if (e.key === "ArrowRight") { e.preventDefault(); document.getElementById("btn-dpad-right")?.click(); }
  });

  // =========================================================================
  // 12. MODAL DE LECTURA DE CORREO & EXTRACTOR TÁCTICO OTP
  // =========================================================================
  const emailModalOverlay = document.getElementById("email-reader-modal-overlay");
  const btnCloseEmailModal = document.getElementById("btn-close-email-modal");
  const btnCloseEmailModalFooter = document.getElementById("btn-close-email-modal-footer");
  const btnCopyOtp = document.getElementById("btn-copy-otp-code");

  function extractOtpCode(text) {
    if (!text) return null;
    const contextRegex = /(?:código|code|otp|verification|verificación|passcode|token|clave)[^\w\d]{1,10}(\d{4,8})\b/i;
    const match = text.match(contextRegex);
    if (match && match[1]) return match[1];

    const standaloneRegex = /\b(\d{6}|\d{8})\b/;
    const mStandalone = text.match(standaloneRegex);
    if (mStandalone && mStandalone[1]) return mStandalone[1];
    return null;
  }

  window.openEmailModal = function(emailData) {
    if (!emailModalOverlay) return;
    StarkAudio.playBlip(1050, 0.04);

    document.getElementById("modal-mail-sender").textContent = emailData.sender || "Desconocido";
    document.getElementById("modal-mail-subject").textContent = emailData.subject || "(Sin Asunto)";
    document.getElementById("modal-mail-date").textContent = emailData.date || new Date().toLocaleString();
    document.getElementById("modal-mail-content").textContent = emailData.snippet || emailData.body || "Sin contenido disponible.";

    const fullText = `${emailData.subject} ${emailData.snippet || ''} ${emailData.body || ''}`;
    const detectedOtp = (emailData.otp && emailData.otp.code) ? emailData.otp.code : extractOtpCode(fullText);
    const otpBanner = document.getElementById("otp-tactical-banner");
    const otpValEl = document.getElementById("otp-code-value");

    if (detectedOtp) {
      otpBanner.style.display = "flex";
      otpValEl.textContent = detectedOtp;
      StarkAudio.playAlert();
    } else {
      otpBanner.style.display = "none";
    }

    emailModalOverlay.style.display = "flex";
  };

  btnCloseEmailModal?.addEventListener("click", () => emailModalOverlay.style.display = "none");
  btnCloseEmailModalFooter?.addEventListener("click", () => emailModalOverlay.style.display = "none");

  btnCopyOtp?.addEventListener("click", async () => {
    const code = document.getElementById("otp-code-value")?.textContent;
    if (!code) return;

    try {
      await navigator.clipboard.writeText(code);
      StarkAudio.playSuccess();
      const btnText = document.getElementById("btn-copy-otp-text");
      if (btnText) {
        const orig = btnText.textContent;
        btnText.textContent = "✓ ¡CÓDIGO COPIADO!";
        setTimeout(() => btnText.textContent = orig, 2500);
      }
      appendLog("AUTH/OTP", `Código de seguridad ${code} copiado al portapapeles.`, "log-success");
    } catch (e) {
      appendLog("AUTH/OTP", "No se pudo acceder al portapapeles del sistema.", "log-warn");
    }
  });

  // =========================================================================
  // 13. VINCULACIÓN GOOGLE OAUTH2 WORKSPACE & GMAIL
  // =========================================================================
  async function checkGoogleLinkStatus() {
    const statusBtn = document.getElementById("btn-google-auth-header");
    const statusText = document.getElementById("google-auth-status-text");
    const cfgName = document.getElementById("cfg-google-account-name");

    try {
      const res = await secureFetch("/api/auth/google/status");
      if (res.ok) {
        const data = await res.json();
        if (data.linked) {
          if (statusBtn) {
            statusBtn.className = "btn-google-sync linked";
            statusText.textContent = "🟢 GOOGLE VINCULADO";
          }
          if (cfgName) cfgName.textContent = `ESTADO: VINCULADO (${data.email || 'brunourrea502@gmail.com'})`;
          return;
        }
      }
    } catch (e) {}

    if (statusBtn) {
      statusBtn.className = "btn-google-sync unlinked";
      statusText.textContent = "🔴 VINCULAR GOOGLE";
    }
    if (cfgName) cfgName.textContent = "ESTADO: NO VINCULADO (OAuth2 Requerido)";
  }

  function initiateGoogleOAuth() {
    StarkAudio.playBlip(900, 0.04);
    appendLog("OAUTH", "Iniciando flujo de autorización Google Workspace / Gmail...", "log-info");
    
    window.open("/api/auth/google/login", "GoogleOAuth", "width=550,height=650,menubar=no,toolbar=no");

    window.addEventListener("message", (event) => {
      if (event.data && event.data.type === "GOOGLE_AUTH_SUCCESS") {
        appendLog("OAUTH", "✓ Cuenta de Google vinculada exitosamente con V.I.E.R.N.E.S.", "log-success");
        StarkAudio.playSuccess();
        checkGoogleLinkStatus();
        loadEmails();
      }
    }, { once: true });
  }

  document.getElementById("btn-google-auth-header")?.addEventListener("click", initiateGoogleOAuth);
  document.getElementById("btn-trigger-google-oauth")?.addEventListener("click", initiateGoogleOAuth);

  // Inicializar estado de Google al arrancar
  checkGoogleLinkStatus();
});
