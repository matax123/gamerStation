const gameInput = document.getElementById("gameInput");
const gameSearch = document.getElementById("gameSearch");
const games = document.getElementById("games");
const backendUrl = "http://localhost:8400";

// estado global para recarga sin refresh
let swiper = null;
let gamesDisplayed = [];
let coverPollInterval = null;

async function loadImages() {
  let result = await fetch(backendUrl + '/get-images', { method: 'POST' });
  let images = await result.json();
  return images;
}

async function loadGames() {
  let result = await fetch(backendUrl + '/get-games', { method: 'POST' });
  let raw = await result.json();
  // Normalizar: backend nuevo devuelve [{platform,file,path,name}], legacy devuelve [string]
  if (!Array.isArray(raw)) return [];
  if (raw.length === 0) return [];
  if (typeof raw[0] === 'string') {
    return raw.map(f => ({ platform: 'UNKNOWN', file: f, path: `games/${f}`, name: splitByLastDot(f)[0] }));
  }
  return raw;
}

function generateSlide(url, game) {
  url = "../img/" + url;
  const badge = game && game.platform && game.platform !== 'UNKNOWN' ? `<span class="slide-badge">${game.platform}</span>` : '';
  const title = game ? game.name : '';
  return `
    <div class="swiper-slide" data-platform="${game ? game.platform : ''}" data-path="${game ? game.path : ''}">
      <img src="${url}" alt="${title}">
      ${badge}
    </div>
  `
}

const SERIAL_TITLES_JS = {
  "SLUS-20946": "Grand Theft Auto - San Andreas",
  "SLUS-20062": "Grand Theft Auto - Vice City",
  "SLUS-20552": "Grand Theft Auto III",
};
function cleanRomName(name) {
  let n = splitByLastDot(name)[0];
  n = n.replace(/\(.*?\)/g, '').replace(/\[.*?\]/g, '');
  n = n.replace(/\s+/g, ' ').trim();
  return n;
}
function resolveTitle(file) {
  const clean = cleanRomName(file);
  const key = clean.toUpperCase();
  if (/^[A-Z]{4}-\d{4,5}$/.test(key) && SERIAL_TITLES_JS[key]) return SERIAL_TITLES_JS[key];
  return clean;
}

async function generateSlides(images, games) {
  const swiperWrapper = document.querySelector('.swiper-wrapper');
  swiperWrapper.innerHTML = '';
  if (games.length === 0) {
    swiperWrapper.innerHTML = '<p class="no-games-msg">Sin juegos — configura un engine y su carpeta de ROMs en ⚙</p>';
    return [];
  }
  // mapa imagen limpia -> archivo original
  const imgMap = new Map();
  images.forEach(img => {
    const clean = cleanRomName(img).toLowerCase();
    if (!imgMap.has(clean)) imgMap.set(clean, img);
    // también mapear nombre exacto sin limpiar por si acaso
    imgMap.set(splitByLastDot(img)[0].toLowerCase(), img);
  });

  let html = '';
  const gamesDisplayed = [];
  games.forEach(g => {
    const cleanGame = cleanRomName(g.file).toLowerCase();
    const cleanName = cleanRomName(g.name).toLowerCase();
    const title = resolveTitle(g.file).toLowerCase();
    let img = imgMap.get(cleanGame) || imgMap.get(cleanName) || imgMap.get(title) || null;
    if (!img) {
      for (const [k, v] of imgMap.entries()) {
        if (k === cleanGame || cleanGame === k || k === title) { img = v; break; }
      }
    }
    if (img) {
      html += generateSlide(img, g);
    } else {
      html += `<div class="swiper-slide slide-noimg" data-platform="${g.platform}" data-path="${g.path}"><div class="slide-noimg-inner"><span class="slide-platform">${g.platform}</span><span class="slide-title">${resolveTitle(g.file)}</span></div></div>`;
    }
    gamesDisplayed.push(g);
  });

  swiperWrapper.innerHTML = html;
  return gamesDisplayed;
}


function initSwiper() {
  if (swiper) { try { swiper.destroy(true, true); } catch(e) {} swiper = null; }
  // Coverflow siempre — es el efecto 3D con sombras de 1.2
  swiper = new Swiper('.swiper-container', {
    slidesPerView: 3,
    slidesPerGroup: 1,
    spaceBetween: 20,
    centeredSlides: true,
    loop: gamesDisplayed.length > 3,
    loopAdditionalSlides: 2,
    loopedSlides: 2,
    effect: 'coverflow',
    coverflowEffect: {
      rotate: 30,
      stretch: 0,
      depth: 120,
      modifier: 1,
      slideShadows: true,
    },
    navigation: {
      nextEl: '.swiper-button-next',
      prevEl: '.swiper-button-prev',
    },
    initialSlide: 1,
  });
}

function startCoverPolling(initialImages, initialGames) {
  if (coverPollInterval) clearInterval(coverPollInterval);
  let lastCount = initialImages.length;
  let checks = 0;
  coverPollInterval = setInterval(async () => {
    checks++;
    try {
      const freshImages = await loadImages();
      if (freshImages.length > lastCount) {
        console.log(`[cover] nuevas carátulas ${lastCount} -> ${freshImages.length}, recargando`);
        lastCount = freshImages.length;
        const games = initialGames || await loadGames();
        gamesDisplayed = await generateSlides(freshImages, games);
        initSwiper();
      }
      // parar tras 30s (15 checks cada 2s)
      if (checks >= 15) {
        clearInterval(coverPollInterval);
        coverPollInterval = null;
      }
    } catch (e) {
      console.error('[cover poll]', e);
    }
  }, 2000);
}

async function reloadGames() {
  try {
    const images = await loadImages();
    const games = await loadGames();
    gamesDisplayed = await generateSlides(images, games);
    initSwiper();
    console.log('[reloadGames] juegos recargados:', gamesDisplayed.length);
    startCoverPolling(images, games);
  } catch (e) {
    console.error('[reloadGames]', e);
  }
}
window.reloadGames = reloadGames;

document.addEventListener('DOMContentLoaded', async () => {
  const images = await loadImages();
  const games = await loadGames();
  gamesDisplayed = await generateSlides(images, games);
  initSwiper();
  startCoverPolling(images, games);




  let axis = {};
  let buttons = {};
  let websocket;
  let inputLocked = false;
  let prevButton0 = 0;
  let pollInterval = null;

  function startGamePolling() {
    if (pollInterval) clearInterval(pollInterval);
    pollInterval = setInterval(async () => {
      const running = await checkGameOpened();
      if (!running) {
        inputLocked = false;
        clearInterval(pollInterval);
        pollInterval = null;
        console.log('[input] desbloqueado, juego cerrado');
      } else {
        console.log('[input] juego sigue abierto, input bloqueado');
      }
    }, 1000);
  }

  // Al iniciar, si ya hay un juego abierto, bloquear input
  checkGameOpened().then(running => {
    if (running) {
      inputLocked = true;
      console.log('[input] juego ya abierto al iniciar, bloqueando input');
      startGamePolling();
    }
  });

  function connectWebSocket() {
    websocket = new WebSocket("ws://localhost:8401");

    websocket.onopen = (event) => {
      console.log("WebSocket connected!");
    };

    websocket.onmessage = async (event) => {
      try {
        let input = JSON.parse(event.data);
        if (input.type === "axis") axis[input.axis] = input.value;
        if (input.type === "button") buttons[input.button] = input.value;

        // Si el input está bloqueado, ignorar todo hasta que el juego cierre
        if (inputLocked) return;

        // Navegación con debounce simple (solo si no está bloqueado)
        if (axis[0] < -0.5) {
          swiper?.slidePrev();
        } else if (axis[0] > 0.5) {
          swiper?.slideNext();
        }

        // Detección de flanco: solo al presionar (0 -> 1), no mientras se mantiene
        const isPressed = buttons[0] === 1;
        const wasPressed = prevButton0 === 1;
        prevButton0 = buttons[0] === 1 ? 1 : 0;

        if (isPressed && !wasPressed) {
          // Bloquear inmediatamente para evitar doble lanzamiento
          inputLocked = true;

          const game = indexToGame(swiper.realIndex, gamesDisplayed);
          console.log('[input] lanzando juego', game);
          const result = await openGame(game);
          // Si el backend rechazó por alreadyRunning, mantener bloqueo
          // Si fue exitoso, también mantener bloqueo hasta que cierre
          // Si hubo error y no está corriendo nada, desbloquear
          if (result && result.alreadyRunning) {
            console.log('[input] backend: ya hay juego en ejecución');
          } else if (result && result.error && !result.alreadyRunning) {
            console.log('[input] error al lanzar, desbloqueando', result.error);
            inputLocked = false;
            return;
          }
          startGamePolling();
        }
      } catch (error) {
        console.error("JSON parsing error:", error, event.data);
      }
    };

    websocket.onclose = (event) => {
      setTimeout(connectWebSocket, 1000);
    };

    websocket.onerror = (error) => {
      console.error("WebSocket error:", error);
    };
  }

  connectWebSocket();

  async function checkGameOpened() {
    let result = await fetch(backendUrl + '/check-game', { method: 'POST' });
    let gameOpened = await result.text();
    if(gameOpened == "false") return false;
    else return true;
  }
});




// ── Settings / .conf ──────────────────────────────────────────
const PLATFORMS = ["NES", "SNES", "GBA", "PS1", "PS2", "WIIU", "SWITCH"];
let appConfig = { engines: { NES: "", SNES: "", GBA: "", PS1: "", PS2: "", WIIU: "", SWITCH: "" }, romFolders: { NES: "", SNES: "", GBA: "", PS1: "", PS2: "", WIIU: "", SWITCH: "" } };

function normalizeConfig(raw) {
  if (!raw) return { engines: { NES: "", SNES: "", GBA: "", PS1: "", PS2: "", WIIU: "", SWITCH: "" }, romFolders: { NES: "", SNES: "", GBA: "", PS1: "", PS2: "", WIIU: "", SWITCH: "" } };
  let engines = raw.engines;
  let roms = raw.romFolders;
  if (Array.isArray(engines)) engines = {};
  if (Array.isArray(roms)) roms = {};
  if (!engines || typeof engines !== "object") engines = {};
  if (!roms || typeof roms !== "object") roms = {};
  const normEngines = {};
  const normRoms = {};
  PLATFORMS.forEach(p => { normEngines[p] = engines[p] || ""; normRoms[p] = roms[p] || ""; });
  return { engines: normEngines, romFolders: normRoms };
}

async function loadConfig() {
  try {
    const r = await fetch(backendUrl + '/config');
    const data = await r.json();
    appConfig = normalizeConfig(data);
  } catch (e) {
    console.error('loadConfig', e);
    appConfig = { engines: { NES: "", SNES: "", GBA: "", PS1: "", PS2: "", WIIU: "", SWITCH: "" }, romFolders: { NES: "", SNES: "", GBA: "", PS1: "", PS2: "", WIIU: "", SWITCH: "" } };
  }
  renderConfig();
}

function renderConfig() {
  const engGrid = document.getElementById('enginesList');
  if (!engGrid) return;

  engGrid.innerHTML = '';
  PLATFORMS.forEach(platform => {
    const exePath = appConfig.engines[platform] || "";
    const romPath = appConfig.romFolders[platform] || "";
    const hasExe = !!exePath;
    const hasRom = !!romPath;
    const row = document.createElement('div');
    row.className = 'engine-row';
    row.innerHTML = `
      <span class="engine-label">${platform}</span>
      <div class="engine-fields">
        <div class="engine-field">
          <span class="engine-path ${hasExe ? 'has-value' : 'empty'}" title="${exePath}">${hasExe ? exePath : 'Sin .exe'}</span>
          <button class="engine-btn" data-exe="${platform}">${hasExe ? 'Cambiar .exe' : 'Seleccionar .exe'}</button>
          ${hasExe ? `<button class="engine-clear" data-clear-exe="${platform}" title="Quitar .exe">✕</button>` : ''}
        </div>
        <div class="engine-field">
          <span class="engine-path ${hasRom ? 'has-value' : 'empty'}" title="${romPath}">${hasRom ? romPath : 'Sin carpeta ROMs'}</span>
          <button class="engine-btn engine-btn-rom" data-rom="${platform}">${hasRom ? 'Cambiar carpeta' : 'Seleccionar carpeta'}</button>
          ${hasRom ? `<button class="engine-clear" data-clear-rom="${platform}" title="Quitar carpeta">✕</button>` : ''}
        </div>
      </div>
    `;
    engGrid.appendChild(row);
  });

  engGrid.querySelectorAll('[data-exe]').forEach(btn => {
    btn.addEventListener('click', async () => {
      const platform = btn.dataset.exe;
      try {
        const r = await fetch(backendUrl + '/browse-file', { method: 'POST' });
        const { path } = await r.json();
        if (path) { appConfig.engines[platform] = path; renderConfig(); }
      } catch (e) { console.error(e); }
    });
  });
  engGrid.querySelectorAll('[data-clear-exe]').forEach(btn => {
    btn.addEventListener('click', () => {
      appConfig.engines[btn.dataset.clearExe] = "";
      renderConfig();
    });
  });
  engGrid.querySelectorAll('[data-rom]').forEach(btn => {
    btn.addEventListener('click', async () => {
      const platform = btn.dataset.rom;
      try {
        const r = await fetch(backendUrl + '/browse-folder', { method: 'POST' });
        const { path } = await r.json();
        if (path) { appConfig.romFolders[platform] = path; renderConfig(); }
      } catch (e) { console.error(e); }
    });
  });
  engGrid.querySelectorAll('[data-clear-rom]').forEach(btn => {
    btn.addEventListener('click', () => {
      appConfig.romFolders[btn.dataset.clearRom] = "";
      renderConfig();
    });
  });
}

async function saveConfig() {
  const status = document.getElementById('settingsStatus');
  try {
    const r = await fetch(backendUrl + '/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(appConfig)
    });
    if (!r.ok) throw new Error(await r.text());
    if (status) { status.textContent = 'Guardado ✓'; setTimeout(() => status.textContent = '', 2000); }
    // recargar juegos sin refresh completo
    await reloadGames();
    // cerrar modal tras guardar
    setTimeout(() => closeSettings(), 400);
  } catch (e) {
    console.error(e);
    if (status) status.textContent = 'Error al guardar';
  }
}

function openSettings() {
  console.log('openSettings');
  const m = document.getElementById('settingsModal');
  if (m) { m.classList.remove('hidden'); m.style.display = 'flex'; }
  loadConfig();
}
function closeSettings() {
  console.log('closeSettings');
  const m = document.getElementById('settingsModal');
  if (m) { m.classList.add('hidden'); m.style.display = 'none'; }
}
window.openSettings = openSettings;
window.closeSettings = closeSettings;

function initSettings() {
  console.log('initSettings', document.readyState);
  const btn = document.getElementById('settingsBtn');
  const closeBtn = document.getElementById('settingsClose');
  const overlay = document.querySelector('.settings-overlay');
  const saveBtn = document.getElementById('settingsSave');
  console.log('settings elements', { btn, closeBtn, overlay, saveBtn });
  if (!btn) { console.error('settingsBtn no encontrado'); return; }
  btn.addEventListener('click', openSettings);
  closeBtn?.addEventListener('click', closeSettings);
  overlay?.addEventListener('click', closeSettings);
  saveBtn?.addEventListener('click', saveConfig);
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeSettings(); });
  loadConfig();
}
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initSettings);
} else {
  initSettings();
}

//META FUNCTIONS
function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function splitByLastDot(str) {
  const lastDotIndex = str.lastIndexOf('.');

  if (lastDotIndex === -1) {
    // No dot found, return the original string and an empty string
    return [str, ""];
  }

  const beforeLastDot = str.substring(0, lastDotIndex);
  const afterLastDot = str.substring(lastDotIndex + 1);

  return [beforeLastDot, afterLastDot];
}

function indexToGame(index, gamesDisplayed) {
  if (!gamesDisplayed || gamesDisplayed.length === 0) return null;
  const n = gamesDisplayed.length;
  const normalized = ((index % n) + n) % n;
  console.log(`indexToGame: realIndex=${index} -> ${normalized}`, gamesDisplayed[normalized]);
  return gamesDisplayed[normalized];
}

async function openGame(game) {
  let payload;
  if (typeof game === 'string') {
    payload = { file_name: game };
  } else if (game && game.path && game.platform) {
    payload = { file_path: game.path, platform: game.platform };
  } else if (game && game.file) {
    payload = { file_name: game.file };
  } else {
    console.error('openGame: game inválido', game);
    return { error: 'game inválido' };
  }
  try {
    const r = await fetch(backendUrl + '/open-file', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await r.json().catch(() => ({}));
    if (data && data.error) return data;
    return data;
  } catch (e) {
    console.error('openGame fetch error', e);
    return { error: String(e) };
  }
}

