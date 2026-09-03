/**
 * Google Slides Remote Control Bridge - Background Service Worker
 * Versión 1.2
 */

const DAEMON_WS_URL = "ws://127.0.0.1:8766";
const RECONNECT_INTERVAL_MS = 3000;

let ws = null;
let isConnected = false;
let currentSessionState = {
  presentationTitle: "",
  isPresenting: false,
  presentationMode: "standard",
  currentSlide: 1,
  totalSlides: 1,
  isBlackout: false,
  isWhiteout: false,
  isLaserActive: false,
  timer: { elapsedSeconds: 0, formattedTime: "00:00", isPaused: false },
  speakerNotes: { hasNotes: false, currentSlideNotes: "" },
  connectedClients: 0,
  pin: ""
};

function connectWebSocket() {
  try {
    ws = new WebSocket(DAEMON_WS_URL);
  } catch (err) {
    setTimeout(connectWebSocket, RECONNECT_INTERVAL_MS);
    return;
  }

  ws.onopen = () => {
    isConnected = true;
    console.log("[SlideBridge] Conectado al daemon en", DAEMON_WS_URL);
    // Enviar estado inicial
    sendStateSync();
    notifyTabsConnectionStatus(true);
  };

  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data);
      handleDaemonMessage(msg);
    } catch (e) {
      console.warn("[SlideBridge] Error procesando mensaje de daemon:", e);
    }
  };

  ws.onclose = () => {
    isConnected = false;
    ws = null;
    notifyTabsConnectionStatus(false);
    setTimeout(connectWebSocket, RECONNECT_INTERVAL_MS);
  };

  ws.onerror = () => {
    if (ws) ws.close();
  };
}

function sendStateSync() {
  if (!ws || !isConnected) return;
  const msg = {
    version: "1.2",
    sessionId: "default",
    source: "extension",
    type: "state",
    action: "STATE_SYNC",
    payload: currentSessionState
  };
  ws.send(JSON.stringify(msg));
}

function notifyTabsConnectionStatus(connected) {
  chrome.tabs.query({ url: "*://docs.google.com/presentation/*" }, (tabs) => {
    tabs.forEach((tab) => {
      chrome.tabs.sendMessage(tab.id, {
        type: "DAEMON_STATUS",
        connected: connected,
        pin: currentSessionState.pin,
        clientsCount: currentSessionState.connectedClients
      }).catch(() => {});
    });
  });
}

function handleDaemonMessage(msg) {
  if (msg.action === "STATE_SYNC") {
    if (msg.payload.pin) currentSessionState.pin = msg.payload.pin;
    if (typeof msg.payload.connectedClients === "number") {
      currentSessionState.connectedClients = msg.payload.connectedClients;
    }
    notifyTabsConnectionStatus(isConnected);
    return;
  }

  if (msg.type === "command") {
    const reqId = msg.payload?.requestId;
    chrome.tabs.query({ active: true, url: "*://docs.google.com/presentation/*" }, (tabs) => {
      // Si no hay tab activa con URL de presentación, consultar cualquier tab de presentación
      const targetTabs = tabs.length > 0 ? tabs : null;
      if (!targetTabs) {
        chrome.tabs.query({ url: "*://docs.google.com/presentation/*" }, (allTabs) => {
          dispatchCommandToTabs(allTabs, msg, reqId);
        });
      } else {
        dispatchCommandToTabs(targetTabs, msg, reqId);
      }
    });
  }
}

function dispatchCommandToTabs(tabs, msg, reqId) {
  if (!tabs || tabs.length === 0) {
    sendAck(msg.action, "failed", "No hay pestañas de Google Slides abiertas", reqId);
    return;
  }

  let handled = false;
  tabs.forEach((tab) => {
    chrome.tabs.sendMessage(tab.id, msg, (response) => {
      if (chrome.runtime.lastError) return;
      if (response && !handled) {
        handled = true;
        sendAck(msg.action, response.status || "ok", response.details, reqId);
      }
    });
  });

  // Timeout de respaldo por si ningún tab respondió explícitamente
  setTimeout(() => {
    if (!handled) {
      sendAck(msg.action, "ok", "dispatched_to_tabs", reqId);
    }
  }, 350);
}

function sendAck(action, status, details, requestId) {
  if (!ws || !isConnected) return;
  const ack = {
    version: "1.2",
    sessionId: "default",
    source: "extension",
    type: "ack",
    action: action,
    payload: {
      action: action,
      status: status,
      details: details,
      requestId: requestId
    }
  };
  ws.send(JSON.stringify(ack));
}

// Escuchar mensajes internos desde los Content Scripts
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "UPDATE_PRESENTATION_STATE") {
    Object.assign(currentSessionState, message.data);
    sendStateSync();
    sendResponse({ received: true });
    return true;
  }
  if (message.type === "GET_DAEMON_INFO") {
    sendResponse({
      isConnected: isConnected,
      pin: currentSessionState.pin,
      clientsCount: currentSessionState.connectedClients
    });
    return true;
  }
});

connectWebSocket();
