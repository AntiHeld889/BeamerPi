(() => {
  const storageKey = 'beamerpi-theme';

  const applyTheme = (theme) => {
    const normalized = theme === 'dark' ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', normalized);
    document.documentElement.style.colorScheme = normalized;

    const toggleButton = document.querySelector('[data-theme-toggle]');
    if (!toggleButton) {
      return;
    }

    const icon = toggleButton.querySelector('.theme-toggle-icon');
    const label = toggleButton.querySelector('.theme-toggle-label');
    if (icon && label) {
      if (normalized === 'dark') {
        icon.textContent = '🌙';
        label.textContent = 'Dark Mode';
      } else {
        icon.textContent = '🌞';
        label.textContent = 'Light Mode';
      }
    }
  };

  const getStoredTheme = () => {
    try {
      return window.localStorage.getItem(storageKey);
    } catch (error) {
      return null;
    }
  };

  const rememberTheme = (theme) => {
    try {
      window.localStorage.setItem(storageKey, theme);
    } catch (error) {
      // Ignoriere Speicherfehler (z. B. privater Modus).
    }
  };

  const resolvePreferredTheme = () => {
    const stored = getStoredTheme();
    if (stored) {
      return stored;
    }
    if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
      return 'dark';
    }
    return 'light';
  };

  const setupMediaListener = () => {
    if (!window.matchMedia) {
      return;
    }
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    const handleChange = (event) => {
      if (getStoredTheme()) {
        return;
      }
      applyTheme(event.matches ? 'dark' : 'light');
    };
    if (typeof mediaQuery.addEventListener === 'function') {
      mediaQuery.addEventListener('change', handleChange);
    } else if (typeof mediaQuery.addListener === 'function') {
      mediaQuery.addListener(handleChange);
    }
  };

  document.addEventListener('DOMContentLoaded', () => {
    applyTheme(resolvePreferredTheme());
    setupMediaListener();

    const toggleButton = document.querySelector('[data-theme-toggle]');
    if (toggleButton) {
      toggleButton.addEventListener('click', () => {
        const nextTheme = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
        applyTheme(nextTheme);
        rememberTheme(nextTheme);
      });
    }
  });
})();
