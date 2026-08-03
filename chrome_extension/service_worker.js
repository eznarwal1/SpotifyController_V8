const BRIDGE = "http://127.0.0.1:8765";
const states = new Map();
let syncTimer = null;

function scheduleSync() {
  clearTimeout(syncTimer);
  syncTimer = setTimeout(syncBridge, 100);
}

chrome.runtime.onMessage.addListener((message, sender) => {
  if (message?.type !== "media_status" || !sender.tab?.id) {
    return;
  }

  const hasRelevantMedia =
    Boolean(message.has_media) ||
    Boolean(message.playing) ||
    Boolean(sender.tab.audible);

  if (!hasRelevantMedia) {
    states.delete(sender.tab.id);
    scheduleSync();
    return;
  }

  states.set(sender.tab.id, {
    tab_id: sender.tab.id,
    window_id: sender.tab.windowId || 0,
    title: message.document_title || sender.tab.title || "",
    url: message.url || sender.tab.url || "",
    favicon_url: sender.tab.favIconUrl || "",
    playing: Boolean(message.playing),
    muted: Boolean(message.muted),
    position_seconds: Number(message.position_seconds || 0),
    duration_seconds: Number(message.duration_seconds || 0),
    media_title: message.media_title || "",
    media_artist: message.media_artist || "",
    media_album: message.media_album || "",
    discord_call_active: Boolean(message.discord_call_active),
    discord_muted: Boolean(message.discord_muted),
    discord_deafened: Boolean(message.discord_deafened),
    discord_evidence: message.discord_evidence || "",
    queue_source: message.queue_source || "",
    queue_available: Boolean(message.queue_available),
    queue_status: message.queue_status || "",
    queue_items: Array.isArray(message.queue_items)
      ? message.queue_items.slice(0, 30)
      : [],
  });

  scheduleSync();
});

chrome.tabs.onRemoved.addListener((tabId) => {
  states.delete(tabId);
  scheduleSync();
});

async function syncBridge() {
  try {
    await fetch(`${BRIDGE}/tabs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        tabs: Array.from(states.values()),
      }),
    });
  } catch {
    // The companion may not be running yet.
  }
}

async function pollCommands() {
  try {
    const response = await fetch(`${BRIDGE}/commands`, {
      cache: "no-store",
    });
    const payload = await response.json();
    const commands = payload.commands || {};

    for (const [tabIdText, tabCommands] of Object.entries(commands)) {
      const tabId = Number(tabIdText);

      for (const command of tabCommands) {
        try {
          await chrome.tabs.sendMessage(tabId, {
            type: "media_command",
            command,
          });
        } catch {
          // The tab may have closed or disallow content scripts.
        }
      }
    }
  } catch {
    // The companion may not be running yet.
  }
}

setInterval(syncBridge, 1000);
setInterval(pollCommands, 500);
syncBridge();
pollCommands();
