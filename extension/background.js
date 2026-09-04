/**
 * Google Slides Remote Control Bridge - Background Service Worker
 * Versión 1.2
 */

let daemonHost = "127.0.0.1";
let daemonPort = 8766;
let daemonPin = "";
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
  if (!daemonPin) {
    isConnected = false;
    currentSessionState.pin = "----";
    console.log("[SlideBridge] Conexión en espera: PIN no configurado.");
    notifyTabsConnectionStatus(false, true);
    return;
  }

  const wsUrl = `ws://${daemonHost}:${daemonPort}`;
  try {
    ws = new WebSocket(wsUrl);
  } catch (err) {
    setTimeout(connectWebSocket, RECONNECT_INTERVAL_MS);
    return;
  }

  ws.onopen = () => {
    isConnected = true;
    console.log("[SlideBridge] Conectado al daemon en", wsUrl);

    // Enviar solicitud de emparejamiento con PIN obligatorio
    const pairMsg = {
      version: "1.2",
      sessionId: "default",
      source: "extension",
      type: "command",
      action: "PAIR_REQUEST",
      payload: {
        pin: daemonPin,
        deviceType: "extension",
        clientName: "Google Slides Extension"
      }
    };
    ws.send(JSON.stringify(pairMsg));

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
    if (daemonPin) {
      setTimeout(connectWebSocket, RECONNECT_INTERVAL_MS);
    }
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

function notifyTabsConnectionStatus(connected, requirePin = false, errorMsg = "") {
  chrome.tabs.query({ url: "*://docs.google.com/presentation/*" }, (tabs) => {
    tabs.forEach((tab) => {
      chrome.tabs.sendMessage(tab.id, {
        type: "DAEMON_STATUS",
        connected: connected,
        pin: currentSessionState.pin || daemonPin || "----",
        clientsCount: currentSessionState.connectedClients,
        requirePin: requirePin,
        errorMsg: errorMsg
      }).catch(() => {});
    });
  });
}

function handleDaemonMessage(msg) {
  if (msg.type === "error" && msg.payload?.code === "ERR_INVALID_PIN") {
    isConnected = false;
    console.warn("[SlideBridge] Daemon rechazó el PIN:", msg.payload?.message);
    notifyTabsConnectionStatus(false, true, "ERR_INVALID_PIN");
    if (ws) ws.close();
    return;
  }

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
      pin: currentSessionState.pin || daemonPin,
      clientsCount: currentSessionState.connectedClients
    });
    return true;
  }
  if (message.type === "GET_CONFIG_STATUS") {
    sendResponse({
      isConnected: isConnected,
      host: daemonHost,
      port: daemonPort,
      pin: daemonPin,
      clientsCount: currentSessionState.connectedClients
    });
    return true;
  }
  if (message.type === "CONFIG_UPDATED") {
    daemonHost = message.host || daemonHost;
    daemonPort = parseInt(message.port, 10) || daemonPort;
    daemonPin = message.pin !== undefined ? String(message.pin).trim() : daemonPin;
    currentSessionState.pin = daemonPin;
    console.log("[SlideBridge] Nueva configuración recibida. Reconectando a", daemonHost, daemonPort);
    if (ws) {
      ws.close();
    } else {
      connectWebSocket();
    }
    sendResponse({ status: "ok" });
    return true;
  }
});

function loadConfigAndConnect() {
  if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.sync) {
    chrome.storage.sync.get(["daemonHost", "daemonPort", "daemonPin"], (res) => {
      if (chrome.runtime.lastError || !res) {
        connectWebSocket();
        return;
      }
      if (res.daemonHost) daemonHost = res.daemonHost.trim();
      if (res.daemonPort) daemonPort = parseInt(res.daemonPort, 10);
      if (res.daemonPin !== undefined) daemonPin = String(res.daemonPin).trim();
      connectWebSocket();
    });
  } else {
    connectWebSocket();
  }
}

loadConfigAndConnect();

