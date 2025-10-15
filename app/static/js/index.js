document.addEventListener('DOMContentLoaded', () => {
  const indicator = document.querySelector('[data-player-status]');
  const indicatorDot = indicator ? indicator.querySelector('[data-player-status-dot]') : null;
  const indicatorText = indicator ? indicator.querySelector('[data-player-status-text]') : null;
  const playlistName = indicator ? indicator.dataset.activePlaylist || null : null;
  const statusEndpoint = indicator ? indicator.dataset.statusEndpoint || null : null;

  const textClassesToReset = ['text-success', 'text-danger', 'text-muted'];
  const dotClassesToReset = ['bg-success', 'bg-danger', 'bg-secondary'];

  const modeConfig = {
    trigger: { text: 'Trigger-Video', textClass: 'text-danger', dotClass: 'bg-danger' },
    loop: { text: 'Loop-Video', textClass: 'text-success', dotClass: 'bg-success' },
    idle: { text: 'Keine Wiedergabe', textClass: 'text-muted', dotClass: 'bg-secondary' },
  };

  const applyMode = (mode) => {
    if (!indicator || !indicatorDot || !indicatorText) {
      return;
    }
    const config = modeConfig[mode] || modeConfig.idle;
    indicator.dataset.mode = mode;
    indicator.classList.remove(...textClassesToReset);
    indicator.classList.add(config.textClass);
    indicatorDot.classList.remove(...dotClassesToReset);
    indicatorDot.classList.add(config.dotClass);
    indicatorText.textContent = config.text;
  };

  const fetchStatus = async () => {
    if (!indicator || !statusEndpoint) {
      return;
    }
    try {
      const response = await fetch(statusEndpoint, {
        headers: { Accept: 'application/json' },
        cache: 'no-store',
      });
      if (!response.ok) {
        return;
      }
      const payload = await response.json();
      if (playlistName && payload.active_playlist && payload.active_playlist !== playlistName) {
        return;
      }
      const mode = payload.status && payload.status.mode ? payload.status.mode : 'idle';
      applyMode(mode);
    } catch (error) {
      // Ignoriere Netzwerkfehler, damit die UI responsiv bleibt.
    }
  };

  applyMode(indicator ? indicator.dataset.mode || 'idle' : 'idle');
  if (indicator && statusEndpoint) {
    fetchStatus();
    window.setInterval(fetchStatus, 3000);
  }

  const filterInput = document.querySelector('[data-playlist-filter]');
  const playlistItems = Array.from(document.querySelectorAll('[data-playlist-item]'));
  const emptyMessage = document.querySelector('[data-playlist-empty]');
  const countBadge = document.querySelector('[data-playlist-count]');

  const updateCountBadge = (visibleCount) => {
    if (!countBadge) {
      return;
    }
    const label = visibleCount === 1 ? 'Playlist' : 'Playlists';
    countBadge.textContent = `${visibleCount} ${label}`;
  };

  const applyFilter = () => {
    const query = (filterInput ? filterInput.value : '').trim().toLowerCase();
    let visibleCount = 0;
    playlistItems.forEach((item) => {
      const matches = !query || (item.dataset.playlistName || '').includes(query);
      item.classList.toggle('d-none', !matches);
      if (matches) {
        visibleCount += 1;
      }
    });
    if (emptyMessage) {
      emptyMessage.classList.toggle('d-none', visibleCount !== 0);
    }
    updateCountBadge(visibleCount);
  };

  if (filterInput) {
    filterInput.addEventListener('input', applyFilter);
  }

  applyFilter();
});
