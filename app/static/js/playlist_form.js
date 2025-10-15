document.addEventListener('DOMContentLoaded', () => {
  const playlistEditor = document.querySelector('[data-playlist-editor]');
  if (!playlistEditor) {
    return;
  }

  const searchInput = document.querySelector('[data-video-search-input]');
  const clearButton = document.querySelector('[data-video-search-clear]');
  const resultsWrapper = document.querySelector('[data-video-search-results]');
  const resultsList = document.querySelector('[data-video-search-results-list]');
  const noResultsAlert = document.querySelector('[data-video-search-no-results]');

  const fileEntries = Array.from(document.querySelectorAll('[data-video-entry]')).map((entry) => {
    const checkbox = entry.querySelector('input[name="videos"]');
    return {
      element: entry,
      checkbox,
      path: entry.dataset.videoPath || '',
      name: entry.dataset.videoName || entry.dataset.videoPath || '',
      previewSrc: entry.dataset.videoSrc || '',
    };
  });

  const fileEntryMap = new Map(
    fileEntries.filter((entry) => entry.path).map((entry) => [entry.path, entry])
  );

  const selectedList = document.querySelector('[data-selected-videos-list]');
  const selectedEmptyState = document.querySelector('[data-selected-videos-empty]');
  const selectedCount = document.querySelector('[data-selected-videos-count]');
  const selectedEntryMap = new Map();
  const orderedInputsContainer = document.querySelector('[data-selected-videos-inputs]');
  const selectedListInitialOrder = (() => {
    if (!selectedList || !selectedList.dataset.initialOrder) {
      return [];
    }
    try {
      return JSON.parse(selectedList.dataset.initialOrder);
    } catch (error) {
      return [];
    }
  })();

  const updateSelectedSummary = () => {
    if (!selectedList) {
      return;
    }
    const itemCount = selectedList.querySelectorAll('[data-selected-video-item]').length;
    if (selectedEmptyState) {
      selectedEmptyState.classList.toggle('d-none', itemCount > 0);
    }
    if (selectedCount) {
      const label = itemCount === 1 ? '1 Video' : `${itemCount} Videos`;
      selectedCount.textContent = label;
    }
  };

  const refreshOrderedInputs = () => {
    if (!orderedInputsContainer || !selectedList) {
      return;
    }
    orderedInputsContainer.innerHTML = '';
    const items = Array.from(selectedList.querySelectorAll('[data-selected-video-item]'));
    items.forEach((item) => {
      const path = item.dataset.selectedVideoItem || '';
      if (!path) {
        return;
      }
      const input = document.createElement('input');
      input.type = 'hidden';
      input.name = 'ordered_videos';
      input.value = path;
      orderedInputsContainer.appendChild(input);
    });
  };

  const updateReorderControls = () => {
    if (!selectedList) {
      return;
    }
    const items = Array.from(selectedList.querySelectorAll('[data-selected-video-item]'));
    items.forEach((item, index) => {
      const moveUpButton = item.querySelector('[data-move-up]');
      const moveDownButton = item.querySelector('[data-move-down]');
      if (moveUpButton) {
        moveUpButton.disabled = index === 0;
      }
      if (moveDownButton) {
        moveDownButton.disabled = index === items.length - 1;
      }
    });
  };

  const moveSelectedItem = (item, direction) => {
    if (!selectedList) {
      return;
    }
    if (direction < 0) {
      const previous = item.previousElementSibling;
      if (!previous) {
        return;
      }
      selectedList.insertBefore(item, previous);
    } else if (direction > 0) {
      const next = item.nextElementSibling;
      if (!next) {
        return;
      }
      selectedList.insertBefore(item, next.nextSibling);
    }
    refreshOrderedInputs();
    updateReorderControls();
    updateSelectedSummary();
  };

  const buildSelectedListItem = (entry) => {
    const item = document.createElement('li');
    item.className = 'list-group-item d-flex align-items-start align-items-lg-center justify-content-between gap-2 flex-wrap';
    item.dataset.selectedVideoItem = entry.path || '';

    const info = document.createElement('div');
    info.className = 'flex-grow-1';

    const title = document.createElement('div');
    title.className = 'fw-semibold text-truncate';
    title.textContent = entry.name || entry.path || '';
    info.append(title);

    const actions = document.createElement('div');
    actions.className = 'd-flex align-items-center gap-2 flex-shrink-0 flex-wrap justify-content-end';

    const reorderGroup = document.createElement('div');
    reorderGroup.className = 'btn-group btn-group-sm';

    const moveUpButton = document.createElement('button');
    moveUpButton.type = 'button';
    moveUpButton.className = 'btn btn-outline-secondary';
    moveUpButton.dataset.moveUp = 'true';
    moveUpButton.innerHTML = '<span aria-hidden="true">▲</span><span class="visually-hidden">Nach oben</span>';
    moveUpButton.addEventListener('click', () => {
      moveSelectedItem(item, -1);
      moveUpButton.focus({ preventScroll: true });
    });

    const moveDownButton = document.createElement('button');
    moveDownButton.type = 'button';
    moveDownButton.className = 'btn btn-outline-secondary';
    moveDownButton.dataset.moveDown = 'true';
    moveDownButton.innerHTML = '<span aria-hidden="true">▼</span><span class="visually-hidden">Nach unten</span>';
    moveDownButton.addEventListener('click', () => {
      moveSelectedItem(item, 1);
      moveDownButton.focus({ preventScroll: true });
    });

    reorderGroup.append(moveUpButton, moveDownButton);
    actions.append(reorderGroup);

    if (entry.previewSrc) {
      const previewButton = document.createElement('button');
      previewButton.type = 'button';
      previewButton.className = 'btn btn-sm btn-outline-secondary';
      previewButton.textContent = 'Vorschau';
      previewButton.dataset.previewTrigger = 'true';
      previewButton.dataset.videoName = entry.name || entry.path || '';
      previewButton.dataset.videoPath = entry.path || '';
      previewButton.dataset.videoSrc = entry.previewSrc;
      actions.append(previewButton);
    }

    const removeButton = document.createElement('button');
    removeButton.type = 'button';
    removeButton.className = 'btn btn-sm btn-outline-danger';
    removeButton.textContent = 'Entfernen';
    removeButton.addEventListener('click', () => {
      if (entry.checkbox) {
        entry.checkbox.checked = false;
        entry.checkbox.dispatchEvent(new Event('change', { bubbles: true }));
      }
    });
    actions.append(removeButton);

    item.append(info, actions);
    return item;
  };

  const syncSelectedEntry = (entry) => {
    if (!selectedList || !entry.path || !entry.checkbox) {
      return;
    }

    const existingItem = selectedEntryMap.get(entry.path);
    if (entry.checkbox.checked) {
      if (!existingItem) {
        const item = buildSelectedListItem(entry);
        selectedEntryMap.set(entry.path, item);
        selectedList.appendChild(item);
      }
    } else if (existingItem) {
      existingItem.remove();
      selectedEntryMap.delete(entry.path);
    }

    updateSelectedSummary();
    refreshOrderedInputs();
    updateReorderControls();
  };

  const applyInitialOrder = () => {
    if (!selectedList) {
      return;
    }
    if (selectedListInitialOrder.length === 0) {
      refreshOrderedInputs();
      updateReorderControls();
      updateSelectedSummary();
      return;
    }
    const itemsByPath = new Map(
      Array.from(selectedList.querySelectorAll('[data-selected-video-item]')).map((item) => [
        item.dataset.selectedVideoItem || '',
        item,
      ])
    );
    selectedListInitialOrder.forEach((path) => {
      const item = itemsByPath.get(path);
      if (item) {
        selectedList.appendChild(item);
      }
    });
    refreshOrderedInputs();
    updateReorderControls();
    updateSelectedSummary();
  };

  let activePreviewEntry = null;

  const highlightPreviewEntry = (path) => {
    if (!path) {
      return;
    }

    const entry = fileEntryMap.get(path);
    if (!entry) {
      return;
    }

    if (activePreviewEntry && activePreviewEntry.element !== entry.element) {
      activePreviewEntry.element.classList.remove('preview-active');
    }

    entry.element.classList.add('preview-active');
    activePreviewEntry = entry;
  };

  const previewModal = document.querySelector('[data-preview-modal]');
  const previewVideo = previewModal ? previewModal.querySelector('[data-preview-video]') : null;
  const previewTitle = previewModal ? previewModal.querySelector('[data-preview-title]') : null;
  const previewCloseButtons = previewModal ? previewModal.querySelectorAll('[data-preview-close]') : [];

  const isPreviewOpen = () => previewModal && !previewModal.classList.contains('d-none');

  const closePreview = () => {
    if (!previewModal) {
      return;
    }
    if (previewVideo) {
      previewVideo.pause();
      previewVideo.removeAttribute('src');
      previewVideo.load();
    }
    previewModal.classList.add('d-none');
    document.body.classList.remove('overflow-hidden');
  };

  const openPreview = (videoName, videoSrc, videoPath = '') => {
    if (!previewModal || !previewVideo || !videoSrc) {
      return;
    }
    if (previewTitle) {
      const title = videoName ? `Vorschau: ${videoName}` : 'Vorschau';
      previewTitle.textContent = title;
    }
    previewVideo.src = videoSrc;
    previewVideo.load();
    highlightPreviewEntry(videoPath);
    previewModal.classList.remove('d-none');
    document.body.classList.add('overflow-hidden');
    const playPromise = previewVideo.play();
    if (playPromise && typeof playPromise.catch === 'function') {
      playPromise.catch(() => {});
    }
  };

  previewCloseButtons.forEach((button) => {
    button.addEventListener('click', () => {
      closePreview();
    });
  });

  if (previewModal) {
    previewModal.addEventListener('click', (event) => {
      if (event.target === previewModal) {
        closePreview();
      }
    });
  }

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && isPreviewOpen()) {
      closePreview();
    }
  });

  document.addEventListener('click', (event) => {
    const trigger = event.target instanceof HTMLElement ? event.target.closest('[data-preview-trigger]') : null;
    if (!trigger) {
      return;
    }
    event.preventDefault();
    const videoName = trigger.dataset.videoName || '';
    const videoSrc = trigger.dataset.videoSrc || '';
    const videoPath = trigger.dataset.videoPath || '';
    const closestEntry = trigger.closest('[data-video-entry]');
    if (closestEntry && closestEntry.dataset.videoPath) {
      highlightPreviewEntry(closestEntry.dataset.videoPath);
    } else {
      highlightPreviewEntry(videoPath);
    }
    openPreview(videoName, videoSrc, videoPath);
  });

  const updateFolderState = (folderElement, expanded) => {
    folderElement.classList.toggle('collapsed', !expanded);
    folderElement.classList.toggle('expanded', expanded);
    const toggle = folderElement.querySelector('.folder-toggle');
    if (toggle) {
      toggle.setAttribute('aria-expanded', expanded ? 'true' : 'false');
    }
  };

  const folderElements = Array.from(document.querySelectorAll('.video-tree [data-folder]'));
  folderElements.forEach((folder) => {
    const toggle = folder.querySelector('.folder-toggle');
    if (!toggle) {
      return;
    }
    updateFolderState(folder, false);
    toggle.addEventListener('click', (event) => {
      event.preventDefault();
      const expanded = folder.classList.contains('collapsed');
      updateFolderState(folder, expanded);
    });
    toggle.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        const expanded = folder.classList.contains('collapsed');
        updateFolderState(folder, expanded);
      }
    });
  });

  const expandAllButton = document.querySelector('[data-video-folders-expand]');
  const collapseAllButton = document.querySelector('[data-video-folders-collapse]');

  if (expandAllButton) {
    expandAllButton.addEventListener('click', () => {
      folderElements.forEach((folder) => updateFolderState(folder, true));
    });
  }

  if (collapseAllButton) {
    collapseAllButton.addEventListener('click', () => {
      folderElements.forEach((folder) => updateFolderState(folder, false));
    });
  }

  if (!searchInput || !resultsWrapper || !resultsList) {
    return;
  }

  const revealEntry = (entryElement) => {
    let folder = entryElement.parentElement.closest('.folder');
    while (folder) {
      updateFolderState(folder, true);
      folder = folder.parentElement.closest('.folder');
    }
    entryElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
    const checkbox = entryElement.querySelector('input[name="videos"]');
    if (checkbox) {
      checkbox.focus({ preventScroll: true });
    }
  };

  const buildResultItem = (entry) => {
    const item = document.createElement('li');
    item.className = 'list-group-item d-flex align-items-center justify-content-between gap-2';

    const label = document.createElement('label');
    label.className = 'form-check-label flex-grow-1 d-flex align-items-center gap-2 mb-0';

    const mirrorCheckbox = document.createElement('input');
    mirrorCheckbox.type = 'checkbox';
    mirrorCheckbox.className = 'form-check-input';
    mirrorCheckbox.checked = entry.checkbox ? entry.checkbox.checked : false;

    mirrorCheckbox.addEventListener('change', () => {
      if (entry.checkbox) {
        entry.checkbox.checked = mirrorCheckbox.checked;
        entry.checkbox.dispatchEvent(new Event('change', { bubbles: true }));
      }
    });

    const textSpan = document.createElement('span');
    textSpan.className = 'flex-grow-1';
    textSpan.textContent = entry.path;

    label.append(mirrorCheckbox, textSpan);

    const actions = document.createElement('div');
    actions.className = 'd-flex align-items-center gap-2';

    if (entry.previewSrc) {
      const previewButton = document.createElement('button');
      previewButton.type = 'button';
      previewButton.className = 'btn btn-sm btn-outline-secondary';
      previewButton.textContent = 'Vorschau';
      previewButton.dataset.previewTrigger = 'true';
      previewButton.dataset.videoName = entry.name || entry.path;
      previewButton.dataset.videoPath = entry.path || '';
      previewButton.dataset.videoSrc = entry.previewSrc;
      actions.append(previewButton);
    }

    const showButton = document.createElement('button');
    showButton.type = 'button';
    showButton.className = 'btn btn-sm btn-outline-primary';
    showButton.textContent = 'Anzeigen';
    showButton.addEventListener('click', () => {
      revealEntry(entry.element);
    });

    actions.append(showButton);

    item.append(label, actions);
    return item;
  };

  const clearResults = () => {
    resultsList.innerHTML = '';
    resultsWrapper.classList.add('d-none');
    if (noResultsAlert) {
      noResultsAlert.classList.add('d-none');
    }
  };

  const updateResults = () => {
    const query = (searchInput.value || '').trim().toLowerCase();
    if (!query) {
      clearResults();
      return;
    }

    const matches = fileEntries.filter((entry) => entry.path.toLowerCase().includes(query));
    resultsList.innerHTML = '';

    if (matches.length === 0) {
      resultsWrapper.classList.remove('d-none');
      resultsList.classList.add('d-none');
      if (noResultsAlert) {
        noResultsAlert.classList.remove('d-none');
      }
      return;
    }

    resultsWrapper.classList.remove('d-none');
    resultsList.classList.remove('d-none');
    if (noResultsAlert) {
      noResultsAlert.classList.add('d-none');
    }

    matches.forEach((entry) => {
      resultsList.appendChild(buildResultItem(entry));
    });
  };

  searchInput.addEventListener('input', updateResults);

  fileEntries.forEach((entry) => {
    if (entry.checkbox) {
      entry.checkbox.addEventListener('change', () => {
        syncSelectedEntry(entry);
        if ((searchInput.value || '').trim()) {
          updateResults();
        }
      });
      syncSelectedEntry(entry);
    }
  });

  applyInitialOrder();

  if (clearButton) {
    clearButton.addEventListener('click', () => {
      searchInput.value = '';
      clearResults();
      searchInput.focus();
    });
  }
});
