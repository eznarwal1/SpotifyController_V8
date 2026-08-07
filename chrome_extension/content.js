(() => {
  const REPORT_INTERVAL_MS = 250;

  function finiteNumber(value) {
    return Number.isFinite(value) ? value : 0;
  }

  function mediaElements() {
    return Array.from(document.querySelectorAll("audio, video"));
  }

  function chooseMediaElement() {
    const elements = mediaElements();

    const playing = elements.find(
      (element) =>
        !element.paused &&
        !element.ended &&
        element.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA
    );

    if (playing) {
      return playing;
    }

    return elements
      .filter((element) => finiteNumber(element.duration) > 0)
      .sort(
        (left, right) =>
          finiteNumber(right.currentTime) - finiteNumber(left.currentTime)
      )[0] || null;
  }

  function mediaMetadata() {
    const metadata = navigator.mediaSession?.metadata;

    return {
      title: metadata?.title || "",
      artist: metadata?.artist || "",
      album: metadata?.album || "",
    };
  }

  function normalizedText(value) {
    return String(value || "")
      .replace(/\s+/g, " ")
      .trim()
      .toLowerCase();
  }

  function normalizedLabel(element) {
    return normalizedText(
      element?.getAttribute("aria-label") ||
      element?.getAttribute("title") ||
      element?.textContent ||
      ""
    );
  }

  function isVisible(element) {
    if (!(element instanceof HTMLElement)) {
      return false;
    }

    const style = getComputedStyle(element);
    const rect = element.getBoundingClientRect();

    return (
      style.display !== "none" &&
      style.visibility !== "hidden" &&
      Number(style.opacity || "1") > 0 &&
      rect.width >= 8 &&
      rect.height >= 8
    );
  }

  function discordInteractiveElements() {
    if (!location.hostname.endsWith("discord.com")) {
      return [];
    }

    return Array.from(
      document.querySelectorAll(
        [
          "button",
          "[role='button']",
          "[aria-label]",
          "[title]",
          "[data-state]",
        ].join(",")
      )
    ).filter(isVisible);
  }

  function candidateScore(element) {
    const rect = element.getBoundingClientRect();
    const centerY = rect.top + rect.height / 2;
    const centerX = rect.left + rect.width / 2;

    let score = centerY * 10 + centerX;

    if (rect.width <= 100 && rect.height <= 100) {
      score += 5000;
    }

    if (element.tagName === "BUTTON") {
      score += 1000;
    }

    return score;
  }

  function labelsFor(kind) {
    return {
      mute: [
        "mute",
        "unmute",
        "mute microphone",
        "unmute microphone",
      ],
      deafen: [
        "deafen",
        "undeafen",
        "deafen audio",
        "undeafen audio",
      ],
      disconnect: [
        "disconnect",
        "disconnect from voice",
        "disconnect quietly",
        "leave call",
        "leave voice",
        "hang up",
      ],
    }[kind] || [];
  }

  function findDiscordButton(kind) {
    const labels = labelsFor(kind);
    const elements = discordInteractiveElements();

    const exact = elements
      .filter((element) => labels.includes(normalizedLabel(element)))
      .sort((left, right) => candidateScore(right) - candidateScore(left));

    if (exact.length > 0) {
      return exact[0];
    }

    return (
      elements
        .filter((element) => {
          const label = normalizedLabel(element);
          return labels.some((candidate) => label.includes(candidate));
        })
        .sort((left, right) => candidateScore(right) - candidateScore(left))[0]
      || null
    );
  }

  function activeButtonState(button) {
    if (!button) return false;

    return (
      button.getAttribute("aria-pressed") === "true" ||
      button.getAttribute("aria-checked") === "true" ||
      ["checked", "on", "active", "selected"].includes(
        button.getAttribute("data-state")
      )
    );
  }

  function visibleDiscordText() {
    if (!location.hostname.endsWith("discord.com")) {
      return "";
    }

    const candidates = Array.from(
      document.querySelectorAll(
        [
          "[aria-label]",
          "[role='status']",
          "[role='region']",
          "[data-text-variant]",
          "section",
          "div",
          "span",
        ].join(",")
      )
    )
      .filter(isVisible)
      .filter((element) => {
        const rect = element.getBoundingClientRect();
        return rect.width < 900 && rect.height < 300;
      })
      .slice(-800);

    return normalizedText(
      candidates
        .map((element) =>
          element.getAttribute("aria-label") ||
          element.textContent ||
          ""
        )
        .join(" ")
    );
  }

  function hasVoiceConnectionText(text) {
    const connectedPhrases = [
      "voice connected",
      "rtc connected",
      "connected to voice",
      "connected to channel",
      "voice connection",
      "disconnect from voice",
      "leave voice",
      "leave call",
    ];

    return connectedPhrases.some((phrase) => text.includes(phrase));
  }

  function discordStatus() {
    if (!location.hostname.endsWith("discord.com")) {
      return {
        callActive: false,
        muted: false,
        deafened: false,
        evidence: "not_discord",
      };
    }

    const muteButton = findDiscordButton("mute");
    const deafenButton = findDiscordButton("deafen");
    const disconnectButton = findDiscordButton("disconnect");
    const pageText = visibleDiscordText();

    /*
     * Discord's DOM varies across accounts and updates. A call is accepted
     * when either:
     *   1. A visible Disconnect/Leave/Hang Up control exists; or
     *   2. The page visibly reports a voice/RTC connection and the normal
     *      mute/deafen controls are present.
     *
     * Requiring only the Disconnect button was too strict and caused false
     * "Voice Disconnected" states.
     */
    const callFromDisconnect = Boolean(disconnectButton);
    const callFromStatusText =
      hasVoiceConnectionText(pageText) &&
      Boolean(muteButton) &&
      Boolean(deafenButton);

    const callActive = callFromDisconnect || callFromStatusText;

    if (!callActive) {
      return {
        callActive: false,
        muted: false,
        deafened: false,
        evidence: "no_call_evidence",
      };
    }

    const muteLabel = normalizedLabel(muteButton);
    const deafenLabel = normalizedLabel(deafenButton);

    const muted =
      muteLabel.includes("unmute") ||
      activeButtonState(muteButton);

    const deafened =
      deafenLabel.includes("undeafen") ||
      activeButtonState(deafenButton);

    return {
      callActive: true,
      muted,
      deafened,
      evidence: callFromDisconnect
        ? "disconnect_control"
        : "voice_status_text",
    };
  }

  let lastDiscordDebugState = "";

  function logDiscordState(status) {
    const current = JSON.stringify(status);

    if (current !== lastDiscordDebugState) {
      lastDiscordDebugState = current;
      console.info(
        "[Universal Media Controller] Discord state",
        status
      );
    }
  }


  function uniqueText(items, limit = 30) {
    const result = [];
    const seen = new Set();

    for (const item of items) {
      const text = String(item || "")
        .replace(/\s+/g, " ")
        .trim();

      if (!text) continue;

      const key = text.toLowerCase();
      if (seen.has(key)) continue;

      seen.add(key);
      result.push(text);

      if (result.length >= limit) break;
    }

    return result;
  }

    function spotifyQueueButton() {
    const selectors = [
      '[data-testid="control-button-queue"]',
      'button[aria-label="Queue"]',
      'button[aria-label*="queue" i]',
      '[role="button"][aria-label*="queue" i]',
    ];

    for (const selector of selectors) {
      const button = document.querySelector(selector);

      if (
        button instanceof HTMLElement &&
        isVisible(button)
      ) {
        return button;
      }
    }

    return null;
  }

  function spotifyQueuePanel() {
    /*
     * Current Spotify Web queue structure:
     *
     * aside[aria-label="Queue"]
     *   ul[role="treegrid"]
     *     li[role="row"]
     *
     * Never fall back to playlists, recommendations, or the entire document.
     */
    const selectors = [
      'aside[aria-label="Queue"]',
      'aside[aria-label="Your queue"]',
      'aside[aria-label*="queue" i]',
    ];

    for (const selector of selectors) {
      const panel = document.querySelector(selector);

      if (
        panel instanceof HTMLElement &&
        isVisible(panel)
      ) {
        return panel;
      }
    }

    return null;
  }

  function cleanSpotifyText(value) {
    return String(value || "")
      .replace(/\s+/g, " ")
      .trim();
  }

  function spotifyQueueTitle(row) {
    const selectors = [
      '[class*="legacy-list-row__header"] p span',
      '[class*="legacy-list-row__header"] p',
      '[class*="legacy-list-row__header"]',
      '[class*="list-row-title"] span',
      '[class*="list-row-title"]',
      'p[class*="title"] span',
      'p[class*="title"]',
    ];

    for (const selector of selectors) {
      const element = row.querySelector(selector);
      const text = cleanSpotifyText(element?.textContent);

      if (text) {
        return text;
      }
    }

    return "";
  }

    function spotifyQueueArtist(row, title) {
    const titleElement =
      row.querySelector(
        '[class*="legacy-list-row__header"]'
      ) ||
      row.querySelector(
        '[class*="list-row-title"]'
      );

    const candidates = [];

    for (const element of row.querySelectorAll(
      [
        'a[href*="/artist/"]',
        '[class*="legacy-list-row__subheader"]',
        '[class*="list-row-subtitle"]',
        '[class*="secondary"]',
        "p",
        "span",
      ].join(",")
    )) {
      if (
        !(element instanceof HTMLElement) ||
        !isVisible(element)
      ) {
        continue;
      }

      if (
        titleElement &&
        (
          element === titleElement ||
          titleElement.contains(element)
        )
      ) {
        continue;
      }

      let text = cleanSpotifyText(element.textContent);

      if (
        !text ||
        text === title ||
        text.length > 160 ||
        /^\d+:\d+$/.test(text) ||
        /^(play|pause|more|remove|save|add)$/i.test(text)
      ) {
        continue;
      }

      if (
        text.startsWith(title) ||
        title.startsWith(text)
      ) {
        continue;
      }

      // Spotify prefixes video queue entries with:
      // "Music video • Artist"
      text = text
        .replace(
          /^music video\s*[•·\-–—|:]\s*/i,
          ""
        )
        .trim();

      if (text) {
        candidates.push(text);
      }
    }

    const ignored = new Set([
      "now playing",
      "next in queue",
      "next up",
      "queue",
      "music video",
    ]);

    return (
      uniqueText(candidates, 15).find((text) => {
        return (
          text &&
          !ignored.has(text.toLowerCase())
        );
      }) || ""
    );
  }

  function spotifyTrackText(row) {
    const title = spotifyQueueTitle(row);

    if (!title) {
      return "";
    }

    const artist = spotifyQueueArtist(row, title);

    return artist
      ? `${title} - ${artist}`
      : title;
  }

    function spotifyQueueRows() {
    const panel = spotifyQueuePanel();

    if (!(panel instanceof HTMLElement)) {
      return [];
    }

    /*
     * Spotify uses separate treegrids for:
     *   - the currently playing track;
     *   - the upcoming queue.
     *
     * Read every visible row in the Queue sidebar instead of selecting only
     * the first treegrid.
     */
    const allRows = Array.from(
      panel.querySelectorAll('li[role="row"]')
    ).filter((row) => {
      return (
        row instanceof HTMLElement &&
        isVisible(row)
      );
    });

    const rows = allRows
      .map((row) => {
        return {
          row,
          text: spotifyTrackText(row),
        };
      })
      .filter((entry) => entry.text);

    /*
     * Remove the current song when Spotify includes it before the upcoming
     * queue. Do not assume it is the only treegrid.
     */
    const currentTitle = cleanSpotifyText(
      navigator.mediaSession?.metadata?.title
    ).toLowerCase();

    if (currentTitle) {
      const currentIndex = rows.findIndex((entry) => {
        const title = entry.text
          .split(" - ", 1)[0]
          .trim()
          .toLowerCase();

        return title === currentTitle;
      });

      if (currentIndex >= 0) {
        rows.splice(currentIndex, 1);
      }
    }

    return rows;
  }

  function spotifyQueueItems() {
    return spotifyQueueRows()
      .map((entry) => entry.text)
      .slice(0, 250);
  }


  function youtubeQueueItems() {
    const texts = [];

    const selectors = [
      "ytd-playlist-panel-video-renderer #video-title",
      "ytd-compact-video-renderer #video-title",
      "ytd-watch-next-secondary-results-renderer #video-title",
    ];

    for (const selector of selectors) {
      for (const element of document.querySelectorAll(selector)) {
        if (element instanceof HTMLElement && isVisible(element)) {
          texts.push(element.textContent || "");
        }
      }
    }

    return uniqueText(texts, 30);
  }


  function queueSnapshot() {
    if (location.hostname.includes("open.spotify.com")) {
      const items = spotifyQueueItems();
      const panel = spotifyQueuePanel();

      return {
        source: "Spotify Web",
        available: items.length > 0,
        status: items.length > 0
          ? `Spotify Web queue: ${items.length} items`
          : (
              panel
                ? "Spotify queue panel is open but no rows were exposed"
                : "Open Spotify Web Queue, then leave the panel visible"
            ),
        items,
      };
    }

    if (location.hostname.includes("youtube.com")) {
      const items = youtubeQueueItems();

      return {
        source: "YouTube",
        available: items.length > 0,
        status: items.length > 0
          ? `YouTube queue: ${items.length} items`
          : "No visible playlist or Up Next items",
        items,
      };
    }

    return {
      source: "",
      available: false,
      status: "Queue unavailable for this source",
      items: [],
    };
  }

  function queueItems() {
    return queueSnapshot().items;
  }

  function snapshot() {
    const element = chooseMediaElement();
    const metadata = mediaMetadata();
    const discord = discordStatus();
    const queue = queueSnapshot();
    logDiscordState(discord);

    return {
      type: "media_status",
      has_media: Boolean(element) || discord.callActive,
      playing: Boolean(element && !element.paused && !element.ended),
      muted: Boolean(element?.muted),
      position_seconds: finiteNumber(element?.currentTime),
      duration_seconds: finiteNumber(element?.duration),
      media_title: metadata.title,
      media_artist: metadata.artist,
      media_album: metadata.album,
      document_title: document.title || "",
      url: location.href,
      discord_call_active: discord.callActive,
      discord_muted: discord.muted,
      discord_deafened: discord.deafened,
      discord_evidence: discord.evidence || "",
      queue_source: queue.source,
      queue_available: queue.available,
      queue_status: queue.status,
      queue_items: queue.items,
    };
  }

  function clickFirst(selectors) {
    for (const selector of selectors) {
      const button = document.querySelector(selector);
      if (button instanceof HTMLElement) {
        button.click();
        return true;
      }
    }
    return false;
  }

  function queueElements() {
    if (location.hostname.includes("youtube.com")) {
      return Array.from(
        document.querySelectorAll(
          [
            "ytd-playlist-panel-video-renderer",
            "ytd-compact-video-renderer",
            "ytd-watch-next-secondary-results-renderer ytd-compact-video-renderer",
          ].join(",")
        )
      ).filter(isVisible);
    }

    if (location.hostname.includes("open.spotify.com")) {
      return spotifyQueueRows().map(
        (entry) => entry.row
      );
    }
    return [];
  }

  async function ensureSpotifyQueueVisible() {
    if (!location.hostname.includes("open.spotify.com")) {
      return;
    }

    if (spotifyQueuePanel()) {
      return;
    }

    const button = spotifyQueueButton();

    if (button) {
      button.click();
      await new Promise((resolve) => setTimeout(resolve, 350));
    }
  }

  async function activateQueueItem(index) {
    await ensureSpotifyQueueVisible();

    const elements = queueElements();
    const target = elements[index];

    if (!(target instanceof HTMLElement)) {
      return false;
    }

    const clickable =
      target.querySelector(
        [
          '[class*="legacy-list-row__interactive"]',
          "[role='button']",
          "button",
          "a[href]",
        ].join(",")
      ) || target;

    if (!(clickable instanceof HTMLElement)) {
      return false;
    }

    clickable.scrollIntoView({
      block: "center",
      behavior: "auto",
    });

    clickable.click();
    return true;
  }

  async function handleCommand(command) {
    if (command.startsWith("queue_play:")) {
      const index = Number(command.split(":", 2)[1]);
      return (
        Number.isInteger(index) &&
        index >= 0 &&
        await activateQueueItem(index)
      );
    }

    if (command === "discord_mute") {
      if (!discordStatus().callActive) return false;
      const button = findDiscordButton("mute");
      if (!button) return false;
      button.click();
      return true;
    }

    if (command === "discord_deafen") {
      if (!discordStatus().callActive) return false;
      const button = findDiscordButton("deafen");
      if (!button) return false;
      button.click();
      return true;
    }

    const element = chooseMediaElement();

    if (command === "play_pause") {
      if (!element) {
        return false;
      }

      if (element.paused) {
        try {
          await element.play();
          return true;
        } catch {
          return false;
        }
      }

      element.pause();
      return true;
    }

    if (command === "next") {
      return clickFirst([
        ".ytp-next-button",
        '[data-testid="control-button-skip-forward"]',
        ".skipControl__next",
        '[aria-label*="Next"]',
      ]);
    }

    if (command === "previous") {
      return clickFirst([
        ".ytp-prev-button",
        '[data-testid="control-button-skip-back"]',
        ".skipControl__previous",
        '[aria-label*="Previous"]',
      ]);
    }

    if (command === "mute") {
      if (!element) {
        return false;
      }
      element.muted = !element.muted;
      return true;
    }

    return false;
  }

  try {
    if (chrome?.runtime?.id) {
      chrome.runtime.onMessage.addListener(
        (message, _sender, sendResponse) => {
          if (message?.type !== "media_command") {
            return;
          }

          handleCommand(String(message.command || ""))
            .then((ok) => sendResponse({ ok }))
            .catch(() => sendResponse({ ok: false }));

          return true;
        }
      );
    }
  } catch {
    // The old content script can briefly remain after an unpacked extension
    // reload. The reporting loop below will stop itself in that case.
  }

  let stopped = false;
  let reportTimer = null;
  let observer = null;

  function extensionContextAvailable() {
    try {
      return Boolean(chrome?.runtime?.id);
    } catch {
      return false;
    }
  }

  function stopReporting() {
    if (stopped) {
      return;
    }

    stopped = true;

    if (reportTimer !== null) {
      clearInterval(reportTimer);
      reportTimer = null;
    }

    if (observer !== null) {
      observer.disconnect();
      observer = null;
    }
  }

  function report() {
    if (stopped) {
      return;
    }

    if (!extensionContextAvailable()) {
      stopReporting();
      return;
    }

    let message;

    try {
      message = snapshot();
    } catch (error) {
      console.warn(
        "[Universal Media Controller] Could not read media state:",
        error
      );
      return;
    }

    try {
      const pending = chrome.runtime.sendMessage(message);

      if (pending && typeof pending.catch === "function") {
        pending.catch((error) => {
          const detail = String(error?.message || error || "");

          if (
            detail.includes("Extension context invalidated") ||
            !extensionContextAvailable()
          ) {
            stopReporting();
          }
        });
      }
    } catch (error) {
      const detail = String(error?.message || error || "");

      if (
        detail.includes("Extension context invalidated") ||
        !extensionContextAvailable()
      ) {
        stopReporting();
        return;
      }

      console.warn(
        "[Universal Media Controller] Could not send media state:",
        error
      );
    }
  }

  observer = new MutationObserver(() => {
    report();
  });

  observer.observe(document.documentElement, {
    subtree: true,
    childList: true,
    attributes: true,
    attributeFilter: [
      "aria-label",
      "aria-pressed",
      "aria-checked",
      "data-state",
      "title",
      "class",
    ],
  });

  report();
  reportTimer = setInterval(report, REPORT_INTERVAL_MS);
})();
