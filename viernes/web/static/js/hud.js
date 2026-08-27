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
  const cfgGoogleClientId = document.getElementById("cfg-google-client-id");
  const cfgGoogleClientSecret = document.getElementById("cfg-google-client-secret");

  const liveClock = document.getElementById("live-clock");
  const liveDate = document.getElementById("live-date");
  const cpuTemp = document.getElementById("cpu-temp");
  const cpuLoad = document.getElementById("cpu-load");
  const ramUsage = document.getElementById("ram-usage");
  const hostIp = document.getElementById("host-ip");
  const voiceStateTag = document.getElementById("voice-state-tag");
  const canvas = document.getElementById("waveform-canvas");
  const ctx = canvas ? canvas.getContext("2d") : null;
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
      if (this.ctx && this.ctx.state === "suspended") {
        this.ctx.resume().catch(() => {});
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
          cfgGeminiModel.innerHTML = '<option value="models/gemini-2.0-flash-exp">Gemini 2.0 Flash [⚡ LIVE AUDIO WS]</option>';
          return;
        }

        const liveGroup = document.createElement("optgroup");
        liveGroup.label = "⚡ MODELOS STREAMING / LIVE VOICE (WebSocket Multimodal)";

        const reasoningGroup = document.createElement("optgroup");
        reasoningGroup.label = "🧠 MODELOS DE RAZONAMIENTO Y CÓDIGO (Thinking / Pro)";

        const standardGroup = document.createElement("optgroup");
        standardGroup.label = "📝 MODELOS RÁPIDOS Y TEXTO (REST Multimodal)";

        models.forEach((m) => {
          const opt = document.createElement("option");
          opt.value = m.id;
          opt.textContent = m.displayName || m.id;
          if (m.id === previousSelection || m.is_active || (m.clean_id && previousSelection.endsWith(m.clean_id))) {
            opt.selected = true;
          }

          if (m.is_live_capable) {
            liveGroup.appendChild(opt);
          } else if (m.category === "reasoning" || m.category === "thinking" || m.category === "pro") {
            reasoningGroup.appendChild(opt);
          } else {
            standardGroup.appendChild(opt);
          }
        });

        if (liveGroup.children.length > 0) cfgGeminiModel.appendChild(liveGroup);
        if (reasoningGroup.children.length > 0) cfgGeminiModel.appendChild(reasoningGroup);
        if (standardGroup.children.length > 0) cfgGeminiModel.appendChild(standardGroup);
      } else {
        cfgGeminiModel.innerHTML = '<option value="models/gemini-2.0-flash-exp">Gemini 2.0 Flash [⚡ LIVE AUDIO WS]</option>';
      }
    } catch (err) {
      cfgGeminiModel.innerHTML = '<option value="models/gemini-2.0-flash-exp">Gemini 2.0 Flash [⚡ LIVE AUDIO WS] (Fallback)</option>';
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
        if (cfgGoogleClientId) cfgGoogleClientId.value = s.google_client_id_masked || "";
        if (cfgGoogleClientSecret) cfgGoogleClientSecret.value = s.google_client_secret_masked || "";
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
      gemini_api_key: cfgGeminiKey ? cfgGeminiKey.value.trim() : "",
      gemini_model: cfgGeminiModel ? cfgGeminiModel.value : "",
      github_token: cfgGithubToken ? cfgGithubToken.value.trim() : "",
      github_repos: cfgGithubRepos ? cfgGithubRepos.value.trim() : "",
      sip_provider: cfgSipProvider ? cfgSipProvider.value : "zadarma_chile",
      default_city: cfgCity ? cfgCity.value : "santiago",
      google_client_id: cfgGoogleClientId ? cfgGoogleClientId.value.trim() : "",
      google_client_secret: cfgGoogleClientSecret ? cfgGoogleClientSecret.value.trim() : ""
    };

    try {
      const res = await secureFetch("/api/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (res.ok) {
        appendLog("CONFIG", data.message || "Configuración .env guardada con éxito.", "log-success");
        StarkAudio.playSuccess();
        settingsOverlay.style.display = "none";
        loadWeather();
        checkGoogleLinkStatus();
      } else {
        appendLog("CONFIG", data.detail || data.error || "Error al actualizar configuración.", "log-warn");
        StarkAudio.playAlert();
      }
    } catch (e) {
      appendLog("CONFIG", "Error de red al guardar configuración.", "log-warn");
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

  // 10. Authenticated WebSocket Telemetry & Live Voice Stream
  let ws;
  function connectWs() {
    if (ws && ws.readyState === WebSocket.OPEN) return;
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const tokenQuery = authToken ? `?token=${encodeURIComponent(authToken)}` : "";
    ws = new WebSocket(`${protocol}//${window.location.host}/ws${tokenQuery}`);

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);

        // 1. Telemetría de hardware
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

          // Si el audio local no está sobreescribiendo el RMS, usar el del servidor
          if (!window._isLocalAudioActive) {
            currentAudioRms = t.audio_rms || 0.02;
          }
          const newSpeaking = t.is_speaking || false;
          if (isSpeaking !== newSpeaking && !window._isLiveAudioPlaying) {
            isSpeaking = newSpeaking;
            if (isSpeaking) {
              voiceStateTag.textContent = "TRANSMITIENDO VOZ";
              voiceStateTag.style.color = "var(--gold-stark)";
            } else if (!window._isLiveSessionActive) {
              voiceStateTag.textContent = "EN ESPERA // 'OYE VIERNES'";
              voiceStateTag.style.color = "var(--cyan-stark)";
            }
          }
        }
        // 2. Chunks de audio PCM 24kHz desde Gemini Live WebSocket
        else if (msg.type === "audio_out" && msg.data) {
          if (window.liveAudioPlayer) {
            window.liveAudioPlayer.playChunk(msg.data);
          }
        }
        // 3. Interrupción del usuario (Barge-in)
        else if (msg.type === "interrupted") {
          if (window.liveAudioPlayer) {
            window.liveAudioPlayer.stopAll();
          }
          if (voiceStateTag) {
            voiceStateTag.textContent = "🎙️ ESCUCHANDO TU VOZ...";
            voiceStateTag.style.color = "var(--cyan-stark)";
          }
        }
        // 4. Fin de turno de habla de Gemini
        else if (msg.type === "turn_complete") {
          if (window._isLiveSessionActive && voiceStateTag) {
            voiceStateTag.textContent = "🔴 CONVERSACIÓN ACTIVA // HABLA LIBREMENTE";
            voiceStateTag.style.color = "var(--cyan-stark)";
          }
        }
        // 5. Transcripción o respuestas de texto
        else if (msg.type === "model_text" && msg.text) {
          appendLog("VIERNES", msg.text, "log-system");
        }
        else if (msg.type === "prompt_response" && msg.response) {
          appendLog("VIERNES", msg.response, "log-system");
        }
        // 6. Eventos del EventBus
        else if (msg.type === "event") {
          if (msg.topic === "ai/text_response" && msg.data?.text) {
            appendLog("VIERNES", msg.data.text, "log-system");
          } else {
            appendLog(msg.topic, JSON.stringify(msg.data), "log-info");
          }
        }
      } catch (err) {
        console.debug("Error procesando frame WS:", err);
      }
    };

    ws.onclose = () => {
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

  // =========================================================================
  // --- GEMINI LIVE MULTIMODAL DUPLEX AUDIO ENGINE (STARK INDUSTRIES) ---
  // =========================================================================

  // 1. REPRODUCTOR DE AUDIO STREAMING (PCM 16-BIT 24kHz DE GEMINI LIVE)
  class LiveAudioPlayer {
    constructor() {
      this.audioCtx = null;
      this.nextStartTime = 0;
      this.activeSources = [];
      this.sampleRate = 24000;
    }

    init() {
      if (!this.audioCtx || this.audioCtx.state === "closed") {
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        this.audioCtx = new AudioCtx({ sampleRate: this.sampleRate });
      }
      if (this.audioCtx.state === "suspended") {
        this.audioCtx.resume();
      }
    }

    playChunk(base64Data) {
      try {
        this.init();
        if (!base64Data) return;

        const binaryString = atob(base64Data);
        const len = binaryString.length;
        const bytes = new Uint8Array(len);
        for (let i = 0; i < len; i++) {
          bytes[i] = binaryString.charCodeAt(i);
        }

        const int16 = new Int16Array(bytes.buffer);
        const numSamples = int16.length;
        if (numSamples === 0) return;

        const float32 = new Float32Array(numSamples);
        let sumSquares = 0;
        for (let i = 0; i < numSamples; i++) {
          const val = int16[i] / 32768.0;
          float32[i] = val;
          sumSquares += val * val;
        }

        // Modulación visual del Arc Reactor (en dorado)
        const rms = Math.sqrt(sumSquares / numSamples);
        currentAudioRms = Math.min(0.95, Math.max(0.1, rms * 4.0));
        window._isLiveAudioPlaying = true;
        isSpeaking = true;
        if (voiceStateTag) {
          voiceStateTag.textContent = "VIERNES // TRANSMITIENDO VOZ";
          voiceStateTag.style.color = "var(--gold-stark)";
        }

        const audioBuffer = this.audioCtx.createBuffer(1, numSamples, this.sampleRate);
        audioBuffer.getChannelData(0).set(float32);

        const source = this.audioCtx.createBufferSource();
        source.buffer = audioBuffer;
        source.connect(this.audioCtx.destination);

        const now = this.audioCtx.currentTime;
        if (this.nextStartTime < now) {
          this.nextStartTime = now + 0.02; // 20ms buffer para evitar chasquidos
        }

        source.start(this.nextStartTime);
        this.nextStartTime += audioBuffer.duration;

        this.activeSources.push(source);
        source.onended = () => {
          const idx = this.activeSources.indexOf(source);
          if (idx !== -1) this.activeSources.splice(idx, 1);
          if (this.activeSources.length === 0) {
            window._isLiveAudioPlaying = false;
            isSpeaking = false;
            currentAudioRms = 0.02;
            if (voiceStateTag && window._isLiveSessionActive) {
              voiceStateTag.textContent = "🔴 CONVERSACIÓN EN VIVO // HABLA LIBREMENTE";
              voiceStateTag.style.color = "var(--cyan-stark)";
            }
          }
        };
      } catch (err) {
        console.warn("LiveAudioPlayer error:", err);
      }
    }

    stopAll() {
      for (const src of this.activeSources) {
        try {
          src.stop();
        } catch (e) {}
      }
      this.activeSources = [];
      window._isLiveAudioPlaying = false;
      isSpeaking = false;
      if (this.audioCtx) {
        this.nextStartTime = this.audioCtx.currentTime;
      }
    }
  }

  window.liveAudioPlayer = new LiveAudioPlayer();

  // 2. CAPTURADOR DE AUDIO STREAMING (PCM 16-BIT 16kHz PARA GEMINI LIVE)
  class LiveAudioRecorder {
    constructor(onChunkCallback, onRmsCallback) {
      this.onChunk = onChunkCallback;
      this.onRms = onRmsCallback;
      this.audioCtx = null;
      this.mediaStream = null;
      this.processor = null;
      this.isRecording = false;
    }

    async start() {
      if (this.isRecording) return true;
      try {
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        this.audioCtx = new AudioCtx({ sampleRate: 16000 });
        if (this.audioCtx.state === "suspended") {
          await this.audioCtx.resume();
        }

        this.mediaStream = await navigator.mediaDevices.getUserMedia({
          audio: {
            sampleRate: 16000,
            channelCount: 1,
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true
          }
        });

        const source = this.audioCtx.createMediaStreamSource(this.mediaStream);
        // ScriptProcessorNode 1024 muestras (~64ms latencia ultra-baja)
        this.processor = this.audioCtx.createScriptProcessor(1024, 1, 1);

        this.processor.onaudioprocess = (e) => {
          if (!this.isRecording) return;
          const inputData = e.inputBuffer.getChannelData(0);

          let sum = 0;
          for (let i = 0; i < inputData.length; i++) {
            sum += inputData[i] * inputData[i];
          }
          const rms = Math.sqrt(sum / inputData.length);
          if (this.onRms) this.onRms(rms);

          // Conversión Float32 a Int16 Little Endian
          const pcm16 = new Int16Array(inputData.length);
          for (let i = 0; i < inputData.length; i++) {
            let s = Math.max(-1, Math.min(1, inputData[i]));
            pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
          }

          let binary = "";
          const bytes = new Uint8Array(pcm16.buffer);
          const len = bytes.byteLength;
          for (let i = 0; i < len; i++) {
            binary += String.fromCharCode(bytes[i]);
          }
          const b64 = btoa(binary);

          if (this.onChunk) {
            this.onChunk(b64);
          }
        };

        source.connect(this.processor);
        this.processor.connect(this.audioCtx.destination);
        this.isRecording = true;
        return true;
      } catch (err) {
        console.error("Error al iniciar micrófono:", err);
        return false;
      }
    }

    stop() {
      this.isRecording = false;
      if (this.processor) {
        try {
          this.processor.disconnect();
        } catch (e) {}
        this.processor = null;
      }
      if (this.mediaStream) {
        try {
          this.mediaStream.getTracks().forEach((t) => t.stop());
        } catch (e) {}
        this.mediaStream = null;
      }
      if (this.audioCtx) {
        try {
          this.audioCtx.close();
        } catch (e) {}
        this.audioCtx = null;
      }
    }
  }

  // 3. GESTIÓN DE SESIÓN DE VOZ EN VIVO (MANOS LIBRES / CONVERSACIONAL)
  window._isLiveSessionActive = false;
  window._isLocalAudioActive = false;
  window._isLiveAudioPlaying = false;

  const liveAudioRecorder = new LiveAudioRecorder(
    (b64Chunk) => {
      // Enviar frame de audio PCM 16kHz al WebSocket
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
          type: "audio_in",
          data: b64Chunk
        }));
      }
    },
    (rms) => {
      // Si el usuario está hablando (RMS alto), modular el Arc Reactor
      if (rms > 0.03 && !window._isLiveAudioPlaying) {
        window._isLocalAudioActive = true;
        currentAudioRms = Math.min(0.95, rms * 4.5);
      } else {
        window._isLocalAudioActive = false;
      }
    }
  );

  async function toggleLiveVoiceSession() {
    if (window._isLiveSessionActive) {
      // Detener sesión
      liveAudioRecorder.stop();
      window._isLiveSessionActive = false;
      window.liveAudioPlayer.stopAll();

      if (btnTalkMic) {
        btnTalkMic.classList.remove("is-listening");
        const txt = btnTalkMic.querySelector(".btn-mic-text") || btnTalkMic.querySelector("span") || btnTalkMic;
        if (txt) txt.textContent = "HABLAR CON V.I.E.R.N.E.S.";
      }
      if (voiceStateTag) {
        voiceStateTag.textContent = "EN ESPERA // 'OYE VIERNES'";
        voiceStateTag.style.color = "var(--cyan-stark)";
      }
      appendLog("VOZ", "Sesión de voz en vivo pausada.", "log-info");
    } else {
      // Iniciar sesión
      // Asegurar que el AudioContext de reproducción esté desbloqueado por la interacción del usuario
      window.liveAudioPlayer.init();

      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "start_live_session" }));
      } else {
        connectWs();
      }

      const ok = await liveAudioRecorder.start();
      if (ok) {
        window._isLiveSessionActive = true;
        StarkAudio.playSuccess();

        if (btnTalkMic) {
          btnTalkMic.classList.add("is-listening");
          const txt = btnTalkMic.querySelector(".btn-mic-text") || btnTalkMic.querySelector("span") || btnTalkMic;
          if (txt) txt.textContent = "🔴 CONVERSACIÓN EN VIVO (HABLANDO)";
        }
        if (voiceStateTag) {
          voiceStateTag.textContent = "🔴 CONVERSACIÓN EN VIVO // HABLA LIBREMENTE";
          voiceStateTag.style.color = "var(--red-alert)";
        }
        appendLog("VOZ", "🎙️ Transmisión de voz en vivo activada: Gemini Live te escucha en tiempo real.", "log-success");
      } else {
        appendLog("VOZ", "No se pudo acceder al micrófono. Verifica los permisos en la barra de URL.", "log-warn");
        StarkAudio.playAlert();
      }
    }
  }

  if (btnTalkMic) {
    btnTalkMic.addEventListener("click", toggleLiveVoiceSession);
  }

  // 4. ENVÍO DE PROMPT DE TEXTO
  btnPromptSend?.addEventListener("click", async () => {
    const text = promptInput ? promptInput.value.trim() : "";
    if (!text) return;
    promptInput.value = "";
    appendLog("BRUNO", text, "log-info");
    StarkAudio.playBlip(800, 0.04);

    if (btnPromptSend) {
      btnPromptSend.disabled = true;
      btnPromptSend.textContent = "...";
    }

    // Si WebSocket está conectado, enviar por WS
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "prompt", prompt: text }));
      if (btnPromptSend) {
        btnPromptSend.disabled = false;
        btnPromptSend.textContent = "ENVIAR";
      }
    } else {
      try {
        const res = await secureFetch("/api/prompt", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ prompt: text })
        });
        const data = await res.json();
        if (res.ok && data && data.response) {
          appendLog("VIERNES", data.response, "log-system");
        }
      } catch (e) {
        appendLog("VIERNES", "Error al enviar comando.", "log-warn");
      } finally {
        if (btnPromptSend) {
          btnPromptSend.disabled = false;
          btnPromptSend.textContent = "ENVIAR";
        }
      }
    }
    loadMemory();
  });

  promptInput?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") btnPromptSend?.click();
  });

  btnRescanNet?.addEventListener("click", async () => {
    appendLog("RED", "Iniciando Reconocimiento Rápido Nmap + NetBIOS en subred activa...", "log-info");
    await secureFetch("/api/scan", { method: "POST" });
    await loadDevices();
    appendLog("RED", "✓ Reconocimiento de red completado y matriz actualizada.", "log-success");
  });

  btnMakeCall?.addEventListener("click", async () => {
    const num = phoneInput ? phoneInput.value.trim() : "";
    if (!num) return;
    appendLog("SIP", `Marcando a celular ${num}...`, "log-info");
    try {
      const res = await secureFetch("/api/call", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone_number: num })
      });
      const data = await res.json();
      appendLog("SIP", data.message || "Llamada SIP enviada.", res.ok ? "log-success" : "log-warn");
    } catch (e) {
      appendLog("SIP", "Error al iniciar llamada SIP.", "log-warn");
    }
  });

  btnAddMemory?.addEventListener("click", async () => {
    const concept = prompt("Concepto o etiqueta de la memoria (ej: cafe_favorito, stack_tecnologico):");
    if (!concept) return;
    const content = prompt(`Detalle a recordar para '${concept}':`);
    if (!content) return;

    try {
      await secureFetch("/api/memory", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ category: "preference", key_concept: concept, content })
      });
      appendLog("MEMORIA", `Nueva preferencia vectorizada en RAG: ${concept}`, "log-success");
      loadMemory();
    } catch (e) {
      appendLog("MEMORIA", "Error guardando memoria en vector RAG.", "log-warn");
    }
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
      appendLog("REMOTE", data.message || `Comando '${command}' ejecutado en ${targetIp}`, res.ok ? "log-info" : "log-warn");
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

  // Navegación por Teclado Físico (D-Pad protegida)
  window.addEventListener("keydown", (e) => {
    // Si hay un modal abierto o el foco está en un input/textarea, ignorar teclas de TV
    const activeEl = document.activeElement;
    if (activeEl && ["INPUT", "TEXTAREA", "SELECT"].includes(activeEl.tagName)) return;

    const authModal = document.getElementById("auth-modal-overlay");
    const settingsModal = document.getElementById("settings-modal-overlay");
    const emailModal = document.getElementById("email-reader-modal-overlay");

    if (authModal && !authModal.classList.contains("authenticated")) return;
    if (settingsModal && settingsModal.style.display === "flex") return;
    if (emailModal && emailModal.style.display === "flex") return;

    if (e.key === "ArrowUp") { e.preventDefault(); document.getElementById("btn-dpad-up")?.click(); }
    else if (e.key === "ArrowDown") { e.preventDefault(); document.getElementById("btn-dpad-down")?.click(); }
    else if (e.key === "ArrowLeft") { e.preventDefault(); document.getElementById("btn-dpad-left")?.click(); }
    else if (e.key === "ArrowRight") { e.preventDefault(); document.getElementById("btn-dpad-right")?.click(); }
    else if (e.key === "Enter" && !e.repeat && document.getElementById("btn-dpad-ok")) {
      document.getElementById("btn-dpad-ok")?.click();
    }
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

    const elSender = document.getElementById("modal-mail-sender");
    const elSubject = document.getElementById("modal-mail-subject");
    const elDate = document.getElementById("modal-mail-date");
    const elContent = document.getElementById("modal-mail-content");

    if (elSender) elSender.textContent = emailData.sender || "Desconocido";
    if (elSubject) elSubject.textContent = emailData.subject || "(Sin Asunto)";
    if (elDate) elDate.textContent = emailData.date || new Date().toLocaleString();
    if (elContent) elContent.textContent = emailData.snippet || emailData.body || "Sin contenido disponible.";

    const fullText = `${emailData.subject || ''} ${emailData.snippet || ''} ${emailData.body || ''}`;
    const detectedOtp = (emailData.otp && emailData.otp.code) ? emailData.otp.code : extractOtpCode(fullText);
    const otpBanner = document.getElementById("otp-tactical-banner");
    const otpValEl = document.getElementById("otp-code-value");

    if (detectedOtp && otpBanner && otpValEl) {
      otpBanner.style.display = "flex";
      otpValEl.textContent = detectedOtp;
      StarkAudio.playAlert();
    } else if (otpBanner) {
      otpBanner.style.display = "none";
    }

    emailModalOverlay.style.display = "flex";
  };

  btnCloseEmailModal?.addEventListener("click", () => emailModalOverlay.style.display = "none");
  btnCloseEmailModalFooter?.addEventListener("click", () => emailModalOverlay.style.display = "none");

  btnCopyOtp?.addEventListener("click", async () => {
    const code = document.getElementById("otp-code-value")?.textContent;
    if (!code) return;

    let copySuccess = false;
    if (navigator.clipboard && navigator.clipboard.writeText) {
      try {
        await navigator.clipboard.writeText(code);
        copySuccess = true;
      } catch (e) {}
    }

    // Fallback táctico si Clipboard API está restringida
    if (!copySuccess) {
      try {
        const tempTa = document.createElement("textarea");
        tempTa.value = code;
        tempTa.style.position = "fixed";
        tempTa.style.opacity = "0";
        document.body.appendChild(tempTa);
        tempTa.select();
        document.execCommand("copy");
        document.body.removeChild(tempTa);
        copySuccess = true;
      } catch (e) {}
    }

    if (copySuccess) {
      StarkAudio.playSuccess();
      const btnText = document.getElementById("btn-copy-otp-text");
      if (btnText) {
        const orig = btnText.textContent;
        btnText.textContent = "✓ ¡CÓDIGO COPIADO!";
        setTimeout(() => btnText.textContent = orig, 2500);
      }
      appendLog("AUTH/OTP", `Código de seguridad ${code} copiado al portapapeles.`, "log-success");
    } else {
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

