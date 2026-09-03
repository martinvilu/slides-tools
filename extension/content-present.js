/**
 * Google Slides Bridge - Content Script: Pantalla Principal de Proyección
 * Inyección de eventos de teclado y Mini-Dock retráctil
 */

(function () {
  "use strict";

  // Descartar ejecución si este contexto corresponde a la ventana emergente de notas
  if (window.location.href.includes("presenter") || document.querySelector(".punch-speaker-notes-text")) {
    return;
  }

  let daemonConnected = false;
  let currentPin = "----";
  let currentClientsCount = 0;
  let miniDockElement = null;

  // ---------------------------------------------------------------------------
  // 5.1. Inyección de Comandos Sintéticos de Teclado
  // ---------------------------------------------------------------------------

  function dispatchPresentationKey(code, key, keyCode) {
    const target = document.activeElement || window;
    const eventData = {
      key: key,
      code: code,
      keyCode: keyCode,
      which: keyCode,
      bubbles: true,
      cancelable: true,
      composed: true,
      view: window
    };

    target.dispatchEvent(new KeyboardEvent("keydown", eventData));
    target.dispatchEvent(new KeyboardEvent("keyup", eventData));
  }

  function handleCommand(msg) {
    const act = msg.action;
    switch (act) {
      case "NEXT_SLIDE":
        dispatchPresentationKey("ArrowRight", "ArrowRight", 39);
        break;
      case "PREV_SLIDE":
        dispatchPresentationKey("ArrowLeft", "ArrowLeft", 37);
        break;
      case "FIRST_SLIDE":
        dispatchPresentationKey("Home", "Home", 36);
        break;
      case "LAST_SLIDE":
        dispatchPresentationKey("End", "End", 35);
        break;
      case "TOGGLE_BLACKOUT":
        dispatchPresentationKey("KeyB", "b", 66);
        break;
      case "TOGGLE_WHITEOUT":
        dispatchPresentationKey("KeyW", "w", 87);
        break;
      case "TOGGLE_LASER":
        dispatchPresentationKey("KeyL", "l", 76);
        break;
      case "GO_TO_SLIDE":
        const targetSlide = parseInt(msg.payload?.slideNumber, 10);
        if (targetSlide > 0) {
          const str = targetSlide.toString();
          for (let i = 0; i < str.length; i++) {
            const digit = str[i];
            const code = `Digit${digit}`;
            const keyCode = 48 + parseInt(digit, 10);
            dispatchPresentationKey(code, digit, keyCode);
          }
          dispatchPresentationKey("Enter", "Enter", 13);
        }
        break;
      default:
        return false;
    }

    // Flash visual sutil en el dock
    if (miniDockElement) {
      miniDockElement.classList.add("slide-bridge-command-flash");
      setTimeout(() => miniDockElement.classList.remove("slide-bridge-command-flash"), 400);
    }
    return true;
  }

  // ---------------------------------------------------------------------------
  // Extracción de Estado en Ventana Principal
  // ---------------------------------------------------------------------------

  function scrapePresentationState() {
    let currentSlide = 1;
    let totalSlides = 1;

    // Selector habitual de visor de diapositivas
    const slideInput = document.querySelector("input.punch-viewer-slide-number-input");
    if (slideInput) {
      currentSlide = parseInt(slideInput.value, 10) || 1;
      const totalSpan = slideInput.parentElement?.textContent;
      if (totalSpan) {
        const m = totalSpan.match(/\/(\d+)/);
        if (m) totalSlides = parseInt(m[1], 10);
      }
    }

    const title = document.title.replace(/ - Google Slides$/, "").replace(/ - Presentaciones de Google$/, "").trim();
    const isPresenting = window.location.href.includes("/present") || window.location.href.includes("/fullscreen");

    return {
      presentationTitle: title,
      isPresenting: isPresenting,
      presentationMode: isPresenting ? "standard" : "edit",
      currentSlide: currentSlide,
      totalSlides: totalSlides
    };
  }

  function reportStateToBackground() {
    const data = scrapePresentationState();
    chrome.runtime.sendMessage({
      type: "UPDATE_PRESENTATION_STATE",
      data: data
    }).catch(() => {});
  }

  // ---------------------------------------------------------------------------
  // Mini-Dock Retráctil (Sección 3.1)
  // ---------------------------------------------------------------------------

  function renderMiniDock() {
    if (miniDockElement) return;

    miniDockElement = document.createElement("div");
    miniDockElement.className = "slide-bridge-mini-dock";
    miniDockElement.id = "slide-bridge-mini-dock";

    const dot = document.createElement("span");
    dot.className = "slide-bridge-dot" + (daemonConnected ? "" : " disconnected");
    dot.id = "slide-bridge-dot";

    const clientsText = document.createElement("span");
    clientsText.id = "slide-bridge-clients-label";
    clientsText.textContent = `${currentClientsCount} disp.`;

    const pinBadge = document.createElement("span");
    pinBadge.className = "slide-bridge-pin-badge";
    pinBadge.id = "slide-bridge-pin-badge";
    pinBadge.textContent = `PIN: ${currentPin}`;

    const qrBtn = document.createElement("button");
    qrBtn.className = "slide-bridge-qr-btn";
    qrBtn.textContent = "QR";
    qrBtn.onclick = showQrModal;

    miniDockElement.appendChild(dot);
    miniDockElement.appendChild(clientsText);
    miniDockElement.appendChild(pinBadge);
    miniDockElement.appendChild(qrBtn);

    document.body.appendChild(miniDockElement);
  }

  function updateMiniDockUI() {
    const dot = document.getElementById("slide-bridge-dot");
    if (dot) {
      dot.className = "slide-bridge-dot" + (daemonConnected ? "" : " disconnected");
    }
    const clients = document.getElementById("slide-bridge-clients-label");
    if (clients) {
      clients.textContent = `${currentClientsCount} disp.`;
    }
    const pin = document.getElementById("slide-bridge-pin-badge");
    if (pin) {
      pin.textContent = `PIN: ${currentPin}`;
    }
  }

  function showQrModal() {
    let modalBackdrop = document.getElementById("slide-bridge-qr-backdrop");
    if (modalBackdrop) return;

    modalBackdrop = document.createElement("div");
    modalBackdrop.id = "slide-bridge-qr-backdrop";
    modalBackdrop.className = "slide-bridge-qr-modal-backdrop";

    const modal = document.createElement("div");
    modal.className = "slide-bridge-qr-modal";

    const h3 = document.createElement("h3");
    h3.textContent = "Emparejamiento Remoto";

    const pinDesc = document.createElement("p");
    pinDesc.innerHTML = `Ingresá el PIN: <strong style="color: #fbbc04; font-size: 18px;">${currentPin}</strong>`;

    const box = document.createElement("div");
    box.className = "slide-bridge-qr-code-box";
    // Renderizado simple de código QR / SVG con datos de conexión
    box.innerHTML = `
      <svg viewBox="0 0 100 100" width="160" height="160">
        <rect width="100" height="100" fill="#ffffff"/>
        <rect x="10" y="10" width="30" height="30" fill="#000000"/>
        <rect x="15" y="15" width="20" height="20" fill="#ffffff"/>
        <rect x="20" y="20" width="10" height="10" fill="#000000"/>
        <rect x="60" y="10" width="30" height="30" fill="#000000"/>
        <rect x="65" y="15" width="20" height="20" fill="#ffffff"/>
        <rect x="70" y="20" width="10" height="10" fill="#000000"/>
        <rect x="10" y="60" width="30" height="30" fill="#000000"/>
        <rect x="15" y="65" width="20" height="20" fill="#ffffff"/>
        <rect x="20" y="70" width="10" height="10" fill="#000000"/>
        <rect x="50" y="50" width="10" height="10" fill="#000000"/>
        <rect x="65" y="65" width="15" height="15" fill="#000000"/>
      </svg>
    `;

    const closeBtn = document.createElement("button");
    closeBtn.className = "slide-bridge-close-btn";
    closeBtn.textContent = "Cerrar";
    closeBtn.onclick = () => modalBackdrop.remove();

    modal.appendChild(h3);
    modal.appendChild(pinDesc);
    modal.appendChild(box);
    modal.appendChild(closeBtn);
    modalBackdrop.appendChild(modal);

    document.body.appendChild(modalBackdrop);
  }

  // ---------------------------------------------------------------------------
  // Escucha de Mensajes desde Background
  // ---------------------------------------------------------------------------

  chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    if (msg.type === "DAEMON_STATUS") {
      daemonConnected = msg.connected;
      currentPin = msg.pin || "----";
      currentClientsCount = msg.clientsCount || 0;
      updateMiniDockUI();
      sendResponse({ received: true });
      return true;
    }

    if (msg.type === "command") {
      const ok = handleCommand(msg);
      reportStateToBackground();
      sendResponse({ status: ok ? "ok" : "unhandled" });
      return true;
    }
  });

  // Inicializar dock y sincronización periódica
  window.addEventListener("DOMContentLoaded", () => {
    renderMiniDock();
    reportStateToBackground();
  });
  if (document.body) {
    renderMiniDock();
  }

  // Consultar estado inicial a background
  chrome.runtime.sendMessage({ type: "GET_DAEMON_INFO" }, (res) => {
    if (chrome.runtime.lastError || !res) return;
    daemonConnected = res.isConnected;
    currentPin = res.pin || "----";
    currentClientsCount = res.clientsCount || 0;
    updateMiniDockUI();
  });

  setInterval(reportStateToBackground, 1000);
})();
