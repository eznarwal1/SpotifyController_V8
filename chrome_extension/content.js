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
      if (button instanceof HTMLElement && isVisible(button)) {
        return button;
      }
    }

    return null;
  }

  function spotifyQueuePanel() {
    const selectors = [
      '[data-testid="queue"]',
      '[data-testid="queue-panel"]',
      '[aria-label="Queue"]',
      '[aria-label*="queue" i]',
      'aside',
    ];

    for (const selector of selectors) {
      for (const candidate of document.querySelectorAll(selector)) {
        if (!(candidate instanceof HTMLElement) || !isVisible(candidate)) {
          continue;
        }

        const text = (candidate.textContent || "").toLowerCase();
        const hasTracks = Boolean(
          candidate.querySelector(
            [
              '[data-testid="tracklist-row"]',
              'a[href*="/track/"]',
              '[role="row"]',
            ].join(",")
          )
        );

        if (hasTracks && (text.includes("next") || text.includes("queue"))) {
          return candidate;
        }
      }
    }

    return null;
  }

  function cleanSpotifyText(value) {
    return String(value || "")
      .replace(/\s+/g, " ")
      .trim();
  }

  function spotifyTrackText(row) {
    /*
     * Prefer anchors identified by their Spotify URL. Some data-testid
     * elements wrap both the title and artist, which produced strings such as
     * "SongArtist" or "Song Artist - Artist".
     */
    const trackLinks = Array.from(
      row.querySelectorAll('a[href*="/track/"]')
    ).filter((element) => {
      return (
        element instanceof HTMLElement &&
        isVisible(element) &&
        cleanSpotifyText(element.textContent)
      );
    });

    const title =
      cleanSpotifyText(trackLinks[0]?.textContent) ||
      cleanSpotifyText(
        row.querySelector(
          '[data-testid="track-name"]'
        )?.textContent
      );

    const artistLinks = Array.from(
      row.querySelectorAll('a[href*="/artist/"]')
    ).filter((element) => {
      return (
        element instanceof HTMLElement &&
        isVisible(element)
      );
    });

    const artists = uniqueText(
      artistLinks
        .map((element) =>
          cleanSpotifyText(element.textContent)
        )
        .filter((artist) => {
          return (
            artist &&
            artist.toLowerCase() !== title.toLowerCase()
          );
        }),
      5
    );

    let artist = artists.join(", ");

    /*
     * Fallback only to an artist-specific test ID. Never use the full row or
     * a generic wrapper because those frequently contain the title directly
     * before the artist.
     */
    if (!artist) {
      artist = cleanSpotifyText(
        row.querySelector(
          '[data-testid="track-row-artist-name-link"]'
        )?.textContent
      );
    }

    // Guard against wrappers returning "SongArtist" or "Song Artist".
    if (title && artist) {
      const compactTitle = title
        .replace(/\s+/g, "")
        .toLowerCase();
      const compactArtist = artist
        .replace(/\s+/g, "")
        .toLowerCase();

      if (compactArtist.startsWith(compactTitle)) {
        const originalWithoutTitle = artist
          .slice(title.length)
          .replace(/^[\s\-–—|•·:]+/, "")
          .trim();

        if (originalWithoutTitle) {
          artist = originalWithoutTitle;
        }
      }
    }

    if (title && artist) {
      return `${title} - ${artist}`;
    }

    if (title) {
      return title;
    }

    return "";
  }


  function spotifyQueueRoots() {
    const roots = [];

    const explicit = document.querySelectorAll(
      [
        '[data-testid="queue"]',
        '[data-testid="queue-panel"]',
        '[aria-label="Queue"]',
        '[aria-label*="queue" i]',
      ].join(",")
    );

    for (const element of explicit) {
      if (
        element instanceof HTMLElement &&
        isVisible(element)
      ) {
        roots.push(element);
      }
    }

    // Spotify frequently renders the queue in the right sidebar without a
    // stable queue test ID. Add visible sidebars that contain track links.
    for (const element of document.querySelectorAll("aside, section")) {
      if (
        element instanceof HTMLElement &&
        isVisible(element) &&
        element.querySelector('a[href*="/track/"]')
      ) {
        roots.push(element);
      }
    }

    return roots.length ? roots : [document];
  }

  function spotifyQueueItems() {
    const results = [];
    const visitedRows = new Set();

    for (const root of spotifyQueueRoots()) {
      const trackLinks = root.querySelectorAll(
        'a[href*="/track/"]'
      );

      for (const trackLink of trackLinks) {
        if (
          !(trackLink instanceof HTMLElement) ||
          !isVisible(trackLink)
        ) {
          continue;
        }

        const row =
          trackLink.closest(
            [
              '[data-testid="tracklist-row"]',
              '[role="row"]',
              'li',
            ].join(",")
          ) || trackLink.parentElement;

        if (
          !(row instanceof HTMLElement) ||
          visitedRows.has(row)
        ) {
          continue;
        }

        visitedRows.add(row);

        const text = spotifyTrackText(row);

        if (text) {
          results.push(text);
        }
      }
    }

    return uniqueText(results, 30);
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
      const panel = spotifyQueuePanel();
      const root = panel || document;

      return Array.from(
        root.querySelectorAll(
          [
            '[data-testid="tracklist-row"]',
            '[role="row"]',
          ].join(",")
        )
      ).filter((row) => {
        return (
          row instanceof HTMLElement &&
          isVisible(row) &&
          Boolean(
            row.querySelector(
              [
                '[data-testid="internal-track-link"]',
                'a[href*="/track/"]',
              ].join(",")
            )
          )
        );
      });
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
          '[data-testid="internal-track-link"]',
          'a[href*="/track/"]',
          "button",
          "[role='button']",
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
