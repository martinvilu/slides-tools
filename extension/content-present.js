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
    pinDesc.textContent = "Ingresá el PIN: ";
    const pinStrong = document.createElement("strong");
    pinStrong.style.color = "#fbbc04";
    pinStrong.style.fontSize = "18px";
    pinStrong.textContent = currentPin;
    pinDesc.appendChild(pinStrong);

    const box = document.createElement("div");
    box.className = "slide-bridge-qr-code-box";
    const qrSvg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    qrSvg.setAttribute("viewBox", "0 0 100 100");
    qrSvg.setAttribute("width", "160");
    qrSvg.setAttribute("height", "160");

    const addRect = (x, y, w, h, fill) => {
      const r = document.createElementNS("http://www.w3.org/2000/svg", "rect");
      r.setAttribute("x", x);
      r.setAttribute("y", y);
      r.setAttribute("width", w);
      r.setAttribute("height", h);
      r.setAttribute("fill", fill);
      qrSvg.appendChild(r);
    };

    addRect("0", "0", "100", "100", "#ffffff");
    addRect("10", "10", "30", "30", "#000000");
    addRect("15", "15", "20", "20", "#ffffff");
    addRect("20", "20", "10", "10", "#000000");
    addRect("60", "10", "30", "30", "#000000");
    addRect("65", "15", "20", "20", "#ffffff");
    addRect("70", "20", "10", "10", "#000000");
    addRect("10", "60", "30", "30", "#000000");
    addRect("15", "65", "20", "20", "#ffffff");
    addRect("20", "70", "10", "10", "#000000");
    addRect("50", "50", "10", "10", "#000000");
    addRect("65", "65", "15", "15", "#000000");
    box.appendChild(qrSvg);

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
