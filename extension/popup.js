/**
 * Panel de Configuración de Puerto y PIN - Slides Bridge
 */

document.addEventListener("DOMContentLoaded", () => {
  const hostInput = document.getElementById("cfg-host");
  const portInput = document.getElementById("cfg-port");
  const pinInput = document.getElementById("cfg-pin");
  const saveBtn = document.getElementById("btn-save");
  const statusMsg = document.getElementById("status-msg");
  const connDot = document.getElementById("conn-dot");
  const connText = document.getElementById("conn-text");

  // 1. Cargar configuración guardada
  if (chrome.storage && chrome.storage.sync) {
    chrome.storage.sync.get(["daemonHost", "daemonPort", "daemonPin"], (items) => {
      if (items) {
        if (items.daemonHost) hostInput.value = items.daemonHost;
        if (items.daemonPort) portInput.value = items.daemonPort;
        if (items.daemonPin !== undefined) pinInput.value = items.daemonPin;
      }
    });
  }

  // 2. Consultar estado al background service worker
  function checkStatus() {
    chrome.runtime.sendMessage({ type: "GET_CONFIG_STATUS" }, (res) => {
      if (chrome.runtime.lastError || !res) {
        connDot.className = "dot";
        connText.textContent = "Desconectado del daemon";
        return;
      }

      if (res.isConnected) {
        connDot.className = "dot connected";
        connText.textContent = `Conectado (${res.host}:${res.port})`;
      } else {
        connDot.className = "dot";
        connText.textContent = "Desconectado del daemon";
      }
    });
  }

  checkStatus();

  // 3. Guardar y notificar reconexión
  saveBtn.addEventListener("click", () => {
    const host = (hostInput.value || "127.0.0.1").trim();
    const port = parseInt(portInput.value || "8766", 10);
    const pin = (pinInput.value || "").trim();

    if (isNaN(port) || port < 1024 || port > 65535) {
      statusMsg.textContent = "Puerto inválido (1024 - 65535)";
      statusMsg.className = "status-msg error";
      return;
    }

    if (chrome.storage && chrome.storage.sync) {
      chrome.storage.sync.set({
        daemonHost: host,
        daemonPort: port,
        daemonPin: pin
      }, () => {
        statusMsg.textContent = "Configuración guardada. Reconectando...";
        statusMsg.className = "status-msg success";

        // Notificar a background service worker
        chrome.runtime.sendMessage({
          type: "CONFIG_UPDATED",
          host: host,
          port: port,
          pin: pin
        }, () => {
          setTimeout(checkStatus, 1200);
        });
      });
    }
  });
});
