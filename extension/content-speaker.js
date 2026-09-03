/**
 * Google Slides Bridge - Content Script: Ventana de Vista de Orador (Speaker Notes Popup)
 * Extracción de notas ricas, temporizador nativo e inyección de toolbar de diagnóstico
 */

(function () {
  "use strict";

  // Ejecutar únicamente en la ventana de notas del presentador
  function isPresenterWindow() {
    return window.location.href.includes("presenter") || Boolean(document.querySelector(".punch-speaker-notes-text"));
  }

  let isInitialized = false;
  let daemonConnected = false;
  let currentPin = "----";
  let currentClientsCount = 0;
  let speakerDockElement = null;

  function initSpeakerNotes() {
    if (isInitialized) return;
    if (!isPresenterWindow()) return;
    isInitialized = true;

    renderSpeakerDock();
    setupObservers();
    reportSpeakerStateToBackground();
  }

  // ---------------------------------------------------------------------------
  // Extracción de Notas y Temporizador Nativo (Sección 5.2)
  // ---------------------------------------------------------------------------

  function extractSpeakerNotes() {
    const notesEl = document.querySelector(".punch-speaker-notes-text");
    if (!notesEl) {
      return { hasNotes: false, currentSlideNotes: "" };
    }
    const cleanText = notesEl.innerText ? notesEl.innerText.trim() : "";
    return {
      hasNotes: cleanText.length > 0,
      currentSlideNotes: cleanText
    };
  }

  function extractNativeTimer() {
    const timerEl = document.querySelector(".punch-speaker-notes-timer-value");
    if (!timerEl) {
      return { elapsedSeconds: 0, formattedTime: "00:00", isPaused: false };
    }

    const formatted = timerEl.textContent.trim() || "00:00";
    const parts = formatted.split(":").map((p) => parseInt(p, 10));
    let seconds = 0;
    if (parts.length === 2) {
      seconds = (parts[0] || 0) * 60 + (parts[1] || 0);
    } else if (parts.length === 3) {
      seconds = (parts[0] || 0) * 3600 + (parts[1] || 0) * 60 + (parts[2] || 0);
    }

    // Comprobar si el botón de pausa está en estado pausado o detenido
    const pauseBtn = document.querySelector(
      'button[aria-label*="Pause" i], button[aria-label*="Pausa" i], button[aria-label*="Resume" i], button[aria-label*="Reanudar" i]'
    );
    const isPaused = pauseBtn ? (pauseBtn.getAttribute("aria-label") || "").toLowerCase().includes("reanudar") : false;

    return {
      elapsedSeconds: seconds,
      formattedTime: formatted,
      isPaused: isPaused
    };
  }

  function reportSpeakerStateToBackground() {
    const notes = extractSpeakerNotes();
    const timer = extractNativeTimer();

    // Intentar leer número de slide en vista de orador
    let currentSlide = 1;
    let totalSlides = 1;
    const slideInfo = document.querySelector(".punch-viewer-speaker-slide-info");
    if (slideInfo && slideInfo.textContent) {
      const m = slideInfo.textContent.match(/(\d+)\s*\/\s*(\d+)/);
      if (m) {
        currentSlide = parseInt(m[1], 10);
        totalSlides = parseInt(m[2], 10);
      }
    }

    chrome.runtime.sendMessage({
      type: "UPDATE_PRESENTATION_STATE",
      data: {
        isPresenting: true,
        presentationMode: "presenter_view",
        currentSlide: currentSlide,
        totalSlides: totalSlides,
        speakerNotes: notes,
        timer: timer
      }
    }).catch(() => {});
  }

  // ---------------------------------------------------------------------------
  // Control de Temporizador Nativo
  // ---------------------------------------------------------------------------

  function handleTimerReset() {
    const resetBtn = document.querySelector(
      'button[aria-label*="Reset" i], button[aria-label*="Reiniciar" i]'
    );
    if (resetBtn) {
      resetBtn.click();
      return true;
    }
    return false;
  }

  function handleTimerTogglePause() {
    const pauseBtn = document.querySelector(
      'button[aria-label*="Pause" i], button[aria-label*="Pausa" i], button[aria-label*="Resume" i], button[aria-label*="Reanudar" i]'
    );
    if (pauseBtn) {
      pauseBtn.click();
      return true;
    }
    return false;
  }

  // ---------------------------------------------------------------------------
  // Barra Superior en Vista de Orador (Sección 3.2)
  // ---------------------------------------------------------------------------

  function renderSpeakerDock() {
    if (speakerDockElement) return;

    speakerDockElement = document.createElement("div");
    speakerDockElement.className = "slide-bridge-speaker-dock";
    speakerDockElement.id = "slide-bridge-speaker-dock";

    speakerDockElement.innerHTML = `
      <div class="left-group">
        <span class="slide-bridge-dot ${daemonConnected ? "" : "disconnected"}" id="speaker-bridge-dot"></span>
        <strong>Google Slides Bridge</strong>
        <span style="color: #9aa0a6;">| Vista de Orador</span>
      </div>
      <div class="right-group">
        <span id="speaker-bridge-clients">${currentClientsCount} disp. conectados</span>
        <span class="slide-bridge-pin-badge" id="speaker-bridge-pin">PIN: ${currentPin}</span>
      </div>
    `;

    document.body.prepend(speakerDockElement);
    // Ajustar padding superior del cuerpo para que no tape los controles
    document.body.style.paddingTop = "38px";
  }

  function updateSpeakerDockUI() {
    const dot = document.getElementById("speaker-bridge-dot");
    if (dot) {
      dot.className = "slide-bridge-dot " + (daemonConnected ? "" : "disconnected");
    }
    const clients = document.getElementById("speaker-bridge-clients");
    if (clients) {
      clients.textContent = `${currentClientsCount} disp. conectados`;
    }
    const pin = document.getElementById("speaker-bridge-pin");
    if (pin) {
      pin.textContent = `PIN: ${currentPin}`;
    }
  }

  function setupObservers() {
    const observer = new MutationObserver(() => {
      reportSpeakerStateToBackground();
    });

    observer.observe(document.body, {
      childList: true,
      subtree: true,
      characterData: true
    });
  }

  // ---------------------------------------------------------------------------
  // Manejo de Mensajes desde Background
  // ---------------------------------------------------------------------------

  chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    if (msg.type === "DAEMON_STATUS") {
      daemonConnected = msg.connected;
      currentPin = msg.pin || "----";
      currentClientsCount = msg.clientsCount || 0;
      updateSpeakerDockUI();
      sendResponse({ received: true });
      return true;
    }

    if (msg.action === "TIMER_RESET") {
      const ok = handleTimerReset();
      reportSpeakerStateToBackground();
      sendResponse({ status: ok ? "ok" : "button_not_found" });
      return true;
    }

    if (msg.action === "TIMER_TOGGLE_PAUSE") {
      const ok = handleTimerTogglePause();
      reportSpeakerStateToBackground();
      sendResponse({ status: ok ? "ok" : "button_not_found" });
      return true;
    }
  });

  // Consultar estado inicial
  chrome.runtime.sendMessage({ type: "GET_DAEMON_INFO" }, (res) => {
    if (chrome.runtime.lastError || !res) return;
    daemonConnected = res.isConnected;
    currentPin = res.pin || "----";
    currentClientsCount = res.clientsCount || 0;
    updateSpeakerDockUI();
  });

  window.addEventListener("DOMContentLoaded", initSpeakerNotes);
  if (document.body) {
    setTimeout(initSpeakerNotes, 500);
  }

  setInterval(reportSpeakerStateToBackground, 1000);
})();
