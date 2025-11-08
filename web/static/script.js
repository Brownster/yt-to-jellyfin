// Tubarr Frontend Script

let subscriptionsCache = [];
const musicState = {
    albumTracks: [],
    playlistTracks: [],
    editing: null,
    pendingTags: {},
};
const musicJobPollers = new Map();

document.addEventListener('DOMContentLoaded', function() {
    // Initialize Bootstrap components
    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    const tooltipList = [...tooltipTriggerList].map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));
    
    // Navigation handling
    const navLinks = document.querySelectorAll('[data-section]');
    const sideNavLinks = document.querySelectorAll('.nav-link');
    const contentSections = document.querySelectorAll('.content-section');

    navLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const sectionId = this.getAttribute('data-section');

            // Update navigation active state
            sideNavLinks.forEach(navLink => navLink.classList.remove('active'));
            const activeLink = document.querySelector(`.nav-link[data-section="${sectionId}"]`);
            if (activeLink) {
                activeLink.classList.add('active');
            }

            // Show the correct section
            contentSections.forEach(section => {
                section.classList.remove('active');
                if (section.id === sectionId) {
                    section.classList.add('active');
                }
            });
            
            // Load data when navigating to certain sections
            if (sectionId === 'jobs') {
                loadJobs();
            } else if (sectionId === 'history') {
                loadHistory();
            } else if (sectionId === 'playlists') {
                loadPlaylists();
            } else if (sectionId === 'subscriptions') {
                loadSubscriptions();
            } else if (sectionId === 'settings') {
                loadSettings();
            } else if (sectionId === 'dashboard') {
                loadDashboard();
            }
        });
    });

    setupJobFilterControls();
    setupHistoryFilterControls();
    initializeMusicForms();
    initializeTipCallouts();

    // CRF sliders
    const crfSlider = document.getElementById('crf');
    const crfValue = document.getElementById('crf-value');
    if (crfSlider && crfValue) {
        crfSlider.addEventListener('input', function() {
            crfValue.textContent = this.value;
        });
    }

    const movieCrfSlider = document.getElementById('movie_crf');
    const movieCrfValue = document.getElementById('movie-crf-value');
    if (movieCrfSlider && movieCrfValue) {
        movieCrfSlider.addEventListener('input', function() {
            movieCrfValue.textContent = this.value;
        });
    }
    
    const defaultCrfSlider = document.getElementById('default_crf');
    const defaultCrfValue = document.getElementById('default-crf-value');
    if (defaultCrfSlider && defaultCrfValue) {
        defaultCrfSlider.addEventListener('input', function() {
            defaultCrfValue.textContent = this.value;
        });
    }

    const concurrencySlider = document.getElementById('max_concurrent_jobs');
    const concurrencyValue = document.getElementById('max-concurrent-value');
    if (concurrencySlider && concurrencyValue) {
        concurrencySlider.addEventListener('input', function() {
            concurrencyValue.textContent = this.value;
        });
    }

    const subscriptionsTableBody = document.querySelector('#subscriptions-table tbody');
    const subscriptionEditModalEl = document.getElementById('subscriptionEditModal');
    let editingSubscriptionId = null;

    function configureRetentionControls(selectId, inputId, helpId) {
        const select = document.getElementById(selectId);
        const input = document.getElementById(inputId);
        const help = helpId ? document.getElementById(helpId) : null;
        if (!select || !input) {
            return null;
        }

        const updateState = () => {
            const mode = select.value;
            if (mode === 'keep_all') {
                input.disabled = true;
                input.value = '';
                if (help) {
                    help.textContent = 'Keep every downloaded episode.';
                }
            } else if (mode === 'keep_episodes') {
                input.disabled = false;
                input.placeholder = 'e.g. 10';
                if (help) {
                    help.textContent = 'Keep only the most recent number of episodes.';
                }
            } else if (mode === 'keep_days') {
                input.disabled = false;
                input.placeholder = 'e.g. 10';
                if (help) {
                    help.textContent = 'Remove episodes older than the specified number of days.';
                }
            }
        };

        select.addEventListener('change', updateState);
        updateState();
        return { select, input };
    }

    function setupJobFilterControls() {
        const group = document.getElementById('job-type-filter');
        if (!group) {
            return;
        }
        group.addEventListener('click', event => {
            const button = event.target.closest('button[data-job-filter]');
            if (!button) {
                return;
            }
            group.querySelectorAll('button').forEach(btn => btn.classList.remove('active'));
            button.classList.add('active');
            const filter = button.getAttribute('data-job-filter');
            document.querySelectorAll('.job-panel').forEach(panel => {
                const type = panel.getAttribute('data-job-type');
                if (filter === 'all' || type === filter) {
                    panel.style.display = '';
                } else {
                    panel.style.display = 'none';
                }
            });
        });
    }

    function setupHistoryFilterControls() {
        const group = document.getElementById('history-type-filter');
        if (!group) {
            return;
        }
        group.addEventListener('click', event => {
            const button = event.target.closest('button[data-history-filter]');
            if (!button) {
                return;
            }
            group.querySelectorAll('button').forEach(btn => btn.classList.remove('active'));
            button.classList.add('active');
            const filter = button.getAttribute('data-history-filter');
            document.querySelectorAll('.history-panel').forEach(panel => {
                const type = panel.getAttribute('data-history-type');
                if (filter === 'all' || type === filter) {
                    panel.style.display = '';
                } else {
                    panel.style.display = 'none';
                }
            });
        });
    }

    function initializeMusicForms() {
        const singleForm = document.getElementById('music-single-form');
        if (singleForm) {
            singleForm.addEventListener('submit', handleMusicSingleSubmit);
        }

        const albumFetchBtn = document.getElementById('music_album_fetch');
        if (albumFetchBtn) {
            albumFetchBtn.addEventListener('click', handleMusicAlbumFetch);
        }

        const albumAddTrackBtn = document.getElementById('music_album_add_track');
        if (albumAddTrackBtn) {
            albumAddTrackBtn.addEventListener('click', () => {
                addMusicTrack('album');
            });
        }

        const albumForm = document.getElementById('music-album-form');
        if (albumForm) {
            albumForm.addEventListener('submit', handleMusicAlbumSubmit);
        }

        const playlistFetchBtn = document.getElementById('music_playlist_fetch');
        if (playlistFetchBtn) {
            playlistFetchBtn.addEventListener('click', handleMusicPlaylistFetch);
        }

        const playlistForm = document.getElementById('music-playlist-form');
        if (playlistForm) {
            playlistForm.addEventListener('submit', handleMusicPlaylistSubmit);
        }

        const trackSaveButton = document.getElementById('music_track_save');
        if (trackSaveButton) {
            trackSaveButton.addEventListener('click', saveMusicTrackModal);
        }

        const manageTagsButton = document.getElementById('music_track_manage_tags');
        if (manageTagsButton) {
            manageTagsButton.addEventListener('click', openMusicTagModal);
        }

        const tagAddButton = document.getElementById('music_tag_add');
        if (tagAddButton) {
            tagAddButton.addEventListener('click', addMusicTag);
        }

        const tagList = document.getElementById('music_tag_list');
        if (tagList) {
            tagList.addEventListener('click', handleMusicTagListClick);
        }

        const tagModalEl = document.getElementById('musicTagModal');
        if (tagModalEl) {
            tagModalEl.addEventListener('hidden.bs.modal', () => {
                const tagsInput = document.getElementById('music_track_tags');
                if (tagsInput) {
                    tagsInput.value = formatTags(musicState.pendingTags);
                }
            });
        }
    }

    if (subscriptionEditModalEl) {
        subscriptionEditModalEl.addEventListener('hidden.bs.modal', () => {
            editingSubscriptionId = null;
        });
    }
    
    // New Job Form Submission
    const newJobForm = document.getElementById('new-job-form');
    if (newJobForm) {
        const selectStartBtn = document.getElementById('select-start-btn');
        const playlistStartInput = document.getElementById('playlist_start');
        if (selectStartBtn) {
            selectStartBtn.addEventListener('click', function() {
                const url = document.getElementById('playlist_url').value.trim();
                if (!url) {
                    showToast('Error', 'Please enter playlist URL first');
                    return;
                }

                const originalHTML = selectStartBtn.innerHTML;
                selectStartBtn.disabled = true;
                selectStartBtn.innerHTML = `<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Loading...`;

                fetch(`/playlist_info?url=${encodeURIComponent(url)}`)
                    .then(r => r.json())
                    .then(videos => {
                        const container = document.getElementById('playlist-videos-container');
                        container.innerHTML = '';
                        videos.forEach(v => {
                            const div = document.createElement('div');
                            div.className = 'form-check';
                            div.innerHTML = `<input class="form-check-input" type="radio" name="startVideo" id="start-${v.index}" value="${v.index}"> <label class="form-check-label" for="start-${v.index}">${v.index}. ${v.title}</label>`;
                            container.appendChild(div);
                        });
                        const modal = new bootstrap.Modal(document.getElementById('playlistStartModal'));
                        modal.show();
                    })
                    .catch(() => showToast('Error', 'Failed to load playlist info'))
                    .finally(() => {
                        selectStartBtn.disabled = false;
                        selectStartBtn.innerHTML = originalHTML;
                    });
            });

            document.getElementById('confirm-start-video').addEventListener('click', function() {
                const selected = document.querySelector('input[name="startVideo"]:checked');
                if (selected) {
                    playlistStartInput.value = selected.value;
                }
                const modalEl = document.getElementById('playlistStartModal');
                const modal = bootstrap.Modal.getInstance(modalEl);
                modal.hide();
            });
        }

        newJobForm.addEventListener('submit', function(e) {
            e.preventDefault();

            const startDownloadBtn = document.getElementById('start-download-btn');
            const originalHTML = startDownloadBtn ? startDownloadBtn.innerHTML : '';
            if (startDownloadBtn) {
                startDownloadBtn.disabled = true;
                startDownloadBtn.innerHTML = `<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Starting...`;
            }

            const formData = new FormData();
            formData.append('playlist_url', document.getElementById('playlist_url').value);
            formData.append('show_name', document.getElementById('show_name').value);
            formData.append('season_num', document.getElementById('season_num').value);
            formData.append('episode_start', document.getElementById('episode_start').value);
            const playlistStartVal = document.getElementById('playlist_start').value;
            if (playlistStartVal) {
                formData.append('playlist_start', playlistStartVal);
            }
            const track = document.getElementById('track_playlist');
            formData.append('track_playlist', track && track.checked ? 'true' : 'false');
            const qualitySelect = document.getElementById('quality');
            if (qualitySelect) {
                formData.append('quality', qualitySelect.value);
            }
            const useH265Toggle = document.getElementById('use_h265');
            formData.append('use_h265', useH265Toggle && useH265Toggle.checked ? 'true' : 'false');
            const crfInput = document.getElementById('crf');
            if (crfInput) {
                formData.append('crf', crfInput.value);
            }

            // Send request to create job
            fetch('/jobs', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if (data.job_id) {
                    showToast('Success', 'Download job started successfully');
                    // Navigate to jobs section
                    document.querySelector('[data-section="jobs"]').click();
                } else {
                    showToast('Error', data.error || 'Failed to start download job');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showToast('Error', 'An error occurred while creating the job');
            })
            .finally(() => {
                if (startDownloadBtn) {
                    startDownloadBtn.disabled = false;
                    startDownloadBtn.innerHTML = originalHTML;
                }
            });
        });
    }

    const newMovieForm = document.getElementById('new-movie-form');
    if (newMovieForm) {
        newMovieForm.addEventListener('submit', function(e) {
            e.preventDefault();

            const startMovieBtn = document.getElementById('start-movie-btn');
            const originalHTML = startMovieBtn ? startMovieBtn.innerHTML : '';
            if (startMovieBtn) {
                startMovieBtn.disabled = true;
                startMovieBtn.innerHTML = `<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Starting...`;
            }

            const formData = new FormData();
            formData.append('video_url', document.getElementById('movie_url').value);
            formData.append('movie_name', document.getElementById('movie_name').value);
            const movieQuality = document.getElementById('movie_quality');
            if (movieQuality) {
                formData.append('quality', movieQuality.value);
            }
            const movieUseH265 = document.getElementById('movie_use_h265');
            formData.append('use_h265', movieUseH265 && movieUseH265.checked ? 'true' : 'false');
            const movieCrf = document.getElementById('movie_crf');
            if (movieCrf) {
                formData.append('crf', movieCrf.value);
            }

            fetch('/movies', {
                method: 'POST',
                body: formData
            })
            .then(r => r.json())
            .then(data => {
                if (data.job_id || data.job_ids) {
                    showToast('Success', 'Movie download queued successfully');
                    document.querySelector('[data-section="jobs"]').click();
                } else {
                    showToast('Error', data.error || 'Failed to start movie download');
                }
            })
            .catch(() => showToast('Error', 'An error occurred while creating the movie job'))
            .finally(() => {
                if (startMovieBtn) {
                    startMovieBtn.disabled = false;
                    startMovieBtn.innerHTML = originalHTML;
                }
            });
        });
    }

    fetch('/config')
        .then(response => response.json())
        .then(config => {
            const tvQuality = document.getElementById('quality');
            if (tvQuality && config.quality) {
                tvQuality.value = String(config.quality);
            }
            const tvUseH265 = document.getElementById('use_h265');
            if (tvUseH265) {
                tvUseH265.checked = config.use_h265 !== false;
            }
            const tvCrf = document.getElementById('crf');
            if (tvCrf) {
                const crfVal = config.crf || 28;
                tvCrf.value = crfVal;
                const crfLabel = document.getElementById('crf-value');
                if (crfLabel) {
                    crfLabel.textContent = crfVal;
                }
            }

            const movieQuality = document.getElementById('movie_quality');
            if (movieQuality && config.quality) {
                movieQuality.value = String(config.quality);
            }
            const movieUseH265Toggle = document.getElementById('movie_use_h265');
            if (movieUseH265Toggle) {
                movieUseH265Toggle.checked = config.use_h265 !== false;
            }
            const movieCrfInput = document.getElementById('movie_crf');
            if (movieCrfInput) {
                const crfVal = config.crf || 28;
                movieCrfInput.value = crfVal;
                const movieCrfLabel = document.getElementById('movie-crf-value');
                if (movieCrfLabel) {
                    movieCrfLabel.textContent = crfVal;
                }
            }
        })
        .catch(() => {});

    const subscriptionRetentionControls = configureRetentionControls('retention_type', 'retention_value', 'retention-value-help');
    const editRetentionControls = configureRetentionControls('edit_retention_type', 'edit_retention_value', 'edit-retention-help');

    const subscriptionForm = document.getElementById('subscription-form');
    if (subscriptionForm) {
        subscriptionForm.addEventListener('submit', function(e) {
            e.preventDefault();

            const submitBtn = document.getElementById('create-subscription-btn');
            const originalHTML = submitBtn ? submitBtn.innerHTML : '';
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerHTML = `<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Subscribing...`;
            }

            const payload = {
                channel_url: document.getElementById('channel_url').value.trim(),
                show_name: document.getElementById('subscription_show_name').value.trim(),
                retention_type: document.getElementById('retention_type').value
            };
            const retentionVal = document.getElementById('retention_value');
            if (retentionVal && !retentionVal.disabled && retentionVal.value) {
                payload.retention_value = retentionVal.value.trim();
            }

            fetch('/subscriptions', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(payload)
            })
                .then(r => r.json())
                .then(data => {
                    if (data.subscription_id) {
                        showToast('Success', 'Channel subscribed successfully');
                        subscriptionForm.reset();
                        if (subscriptionRetentionControls) {
                            subscriptionRetentionControls.select.value = 'keep_all';
                            subscriptionRetentionControls.select.dispatchEvent(new Event('change'));
                        }
                        loadSubscriptions();
                    } else {
                        showToast('Error', data.error || 'Failed to create subscription');
                    }
                })
                .catch(() => showToast('Error', 'Failed to create subscription'))
                .finally(() => {
                    if (submitBtn) {
                        submitBtn.disabled = false;
                        submitBtn.innerHTML = originalHTML;
                    }
                });
        });
    }

    const subscriptionEditForm = document.getElementById('subscription-edit-form');
    if (subscriptionEditForm && editRetentionControls) {
        subscriptionEditForm.addEventListener('submit', function(e) {
            e.preventDefault();
            if (!editingSubscriptionId) {
                return;
            }

            const payload = {
                show_name: document.getElementById('edit_subscription_show_name').value.trim(),
                retention_type: editRetentionControls.select.value,
                enabled: document.getElementById('edit_subscription_enabled').checked
            };
            if (!editRetentionControls.input.disabled && editRetentionControls.input.value) {
                payload.retention_value = editRetentionControls.input.value.trim();
            }

            fetch(`/subscriptions/${editingSubscriptionId}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(payload)
            })
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        showToast('Success', 'Subscription updated');
                        const modal = bootstrap.Modal.getInstance(subscriptionEditModalEl);
                        if (modal) {
                            modal.hide();
                        }
                        loadSubscriptions();
                    } else {
                        showToast('Error', data.error || 'Failed to update subscription');
                    }
                })
                .catch(() => showToast('Error', 'Failed to update subscription'));
        });
    }

    if (subscriptionsTableBody) {
        subscriptionsTableBody.addEventListener('click', function(event) {
            const button = event.target.closest('button[data-action]');
            if (!button) {
                return;
            }
            const id = button.getAttribute('data-id');
            const action = button.getAttribute('data-action');
            const subscription = subscriptionsCache.find(s => s.id === id);
            if (!subscription) {
                return;
            }

            if (action === 'edit') {
                if (!editRetentionControls) {
                    return;
                }
                editingSubscriptionId = id;
                document.getElementById('edit_subscription_show_name').value = subscription.show_name || '';
                const mode = (subscription.retention && subscription.retention.mode) || 'all';
                let selectValue = 'keep_all';
                if (mode === 'episodes') {
                    selectValue = 'keep_episodes';
                } else if (mode === 'days') {
                    selectValue = 'keep_days';
                }
                editRetentionControls.select.value = selectValue;
                editRetentionControls.select.dispatchEvent(new Event('change'));
                if (selectValue !== 'keep_all') {
                    editRetentionControls.input.value = subscription.retention && subscription.retention.value ? subscription.retention.value : '';
                } else {
                    editRetentionControls.input.value = '';
                }
                const enabledSwitch = document.getElementById('edit_subscription_enabled');
                if (enabledSwitch) {
                    enabledSwitch.checked = subscription.enabled !== false;
                }
                const modal = new bootstrap.Modal(subscriptionEditModalEl);
                modal.show();
            } else if (action === 'toggle') {
                const payload = { enabled: !(subscription.enabled !== false) };
                fetch(`/subscriptions/${id}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                })
                    .then(r => r.json())
                    .then(data => {
                        if (data.success) {
                            showToast('Success', payload.enabled ? 'Subscription resumed' : 'Subscription paused');
                            loadSubscriptions();
                        } else {
                            showToast('Error', data.error || 'Failed to update subscription');
                        }
                    })
                    .catch(() => showToast('Error', 'Failed to update subscription'));
            } else if (action === 'delete') {
                if (!confirm('Remove this subscription?')) {
                    return;
                }
                fetch(`/subscriptions/${id}`, { method: 'DELETE' })
                    .then(r => r.json())
                    .then(data => {
                        if (data.success) {
                            showToast('Success', 'Subscription removed');
                            loadSubscriptions();
                        } else {
                            showToast('Error', data.error || 'Failed to remove subscription');
                        }
                    })
                    .catch(() => showToast('Error', 'Failed to remove subscription'));
            }
        });
    }
    
    // Settings Form Submission
    const settingsForm = document.getElementById('settings-form');
    if (settingsForm) {
        // Toggle Jellyfin settings visibility based on enabled state
       const jellyfinEnabled = document.getElementById('jellyfin_enabled');
       const jellyfinSettings = document.querySelectorAll('.jellyfin-settings');
        const imdbEnabled = document.getElementById('imdb_enabled');
        const imdbSettings = document.querySelectorAll('.imdb-settings');
        const autoCheck = document.getElementById('auto_check_updates');
        const updateSchedule = document.querySelector('.update-schedule-settings');
        const useH265 = document.getElementById('default_use_h265');
        const concurrencyRow = document.querySelector('.h265-concurrency');

       function toggleJellyfinSettings() {
           const isEnabled = jellyfinEnabled.checked;
           jellyfinSettings.forEach(el => {
               if (isEnabled) {
                   el.style.display = 'flex';
               } else {
                   el.style.display = 'none';
               }
           });
       }

        function toggleImdbSettings() {
            const isEnabled = imdbEnabled.checked;
            imdbSettings.forEach(el => {
                if (isEnabled) {
                    el.style.display = 'flex';
                } else {
                    el.style.display = 'none';
                }
            });
        }

        function toggleUpdateSchedule() {
            if (autoCheck.checked) {
                updateSchedule.style.display = 'flex';
            } else {
                updateSchedule.style.display = 'none';
            }
        }

        function toggleConcurrency() {
            if (useH265.checked) {
                concurrencyRow.style.display = 'flex';
            } else {
                concurrencyRow.style.display = 'none';
            }
        }

        // Set initial state
       toggleJellyfinSettings();
        toggleImdbSettings();
       toggleUpdateSchedule();
       toggleConcurrency();

        // Add event listener for toggle
       jellyfinEnabled.addEventListener('change', toggleJellyfinSettings);
        imdbEnabled.addEventListener('change', toggleImdbSettings);
       autoCheck.addEventListener('change', toggleUpdateSchedule);
       useH265.addEventListener('change', toggleConcurrency);
        
        // Form submission handler
        settingsForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const settings = {
                output_dir: document.getElementById('output_dir').value,
                cookies_path: document.getElementById('cookies_path').value,
                quality: document.getElementById('default_quality').value,
                use_h265: document.getElementById('default_use_h265').checked,
                clean_filenames: document.getElementById('clean_filenames').checked,
                crf: document.getElementById('default_crf').value,
                web_port: document.getElementById('web_port').value,
                completed_jobs_limit: document.getElementById('completed_jobs_limit').value,
                max_concurrent_jobs: document.getElementById('max_concurrent_jobs').value,
                auto_check_updates: document.getElementById('auto_check_updates').checked,
                update_interval: document.getElementById('update_interval').value,
                // Jellyfin settings
                jellyfin_enabled: document.getElementById('jellyfin_enabled').checked,
                jellyfin_tv_path: document.getElementById('jellyfin_tv_path').value,
                jellyfin_host: document.getElementById('jellyfin_host').value,
                jellyfin_port: document.getElementById('jellyfin_port').value,
                jellyfin_api_key: document.getElementById('jellyfin_api_key').value,
                // IMDb settings
                imdb_enabled: document.getElementById('imdb_enabled').checked,
                imdb_api_key: document.getElementById('imdb_api_key').value
            };
            
            // Send request to update settings
            fetch('/config', {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(settings)
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showToast('Success', 'Settings updated successfully');
                } else {
                    showToast('Error', data.error || 'Failed to update settings');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showToast('Error', 'An error occurred while updating settings');
            });
        });
    }
    
    function triggerUpdateCheck() {
        fetch('/playlists/check', { method: 'POST' })
            .then(r => r.json())
            .then(data => {
                if (data.created_jobs && data.created_jobs.length > 0) {
                    showToast('Updates', `Created ${data.created_jobs.length} jobs`);
                    loadJobs();
                } else {
                    showToast('Info', 'No updates found');
                }
            })
            .catch(() => showToast('Error', 'Failed to check for updates'));
    }

    const checkPlaylistsBtn = document.getElementById('check-playlists');
    if (checkPlaylistsBtn) {
        checkPlaylistsBtn.addEventListener('click', triggerUpdateCheck);
    }

    const checkSubscriptionsBtn = document.getElementById('check-subscriptions');
    if (checkSubscriptionsBtn) {
        checkSubscriptionsBtn.addEventListener('click', triggerUpdateCheck);
    }

    // Header new download button
    const headerNewDownloadBtn = document.getElementById('header-new-download');
    if (headerNewDownloadBtn) {
        headerNewDownloadBtn.addEventListener('click', function() {
            document.querySelector('[data-section="new-job"]').click();
        });
    }

    // Load dashboard data by default
    loadDashboard();
    
    // Setup polling for active jobs
    setInterval(function() {
        if (document.querySelector('#jobs.active') ||
            document.querySelector('#dashboard.active') ||
            document.querySelector('#history.active')) {
            updateJobsData();
        }
        if (document.querySelector('#playlists.active')) {
            loadPlaylists();
        }
        if (document.querySelector('#subscriptions.active')) {
            loadSubscriptions();
        }
    }, 5000);
});

// Initialize tip callouts with collapse functionality and localStorage persistence
function initializeTipCallouts() {
    const tipCallouts = document.querySelectorAll('.tip-callout');

    tipCallouts.forEach(tip => {
        const tipId = tip.dataset.tipId;
        const toggle = tip.querySelector('.tip-toggle');
        const title = tip.querySelector('h6');

        if (!tipId || !toggle) return;

        // Load collapsed state from localStorage
        const isCollapsed = localStorage.getItem(`tip-${tipId}-collapsed`) === 'true';
        if (isCollapsed) {
            tip.classList.add('collapsed');
        }

        // Toggle function
        const toggleTip = () => {
            const currentlyCollapsed = tip.classList.contains('collapsed');
            tip.classList.toggle('collapsed');
            localStorage.setItem(`tip-${tipId}-collapsed`, !currentlyCollapsed);
        };

        // Add click handlers
        toggle.addEventListener('click', toggleTip);
        title.addEventListener('click', toggleTip);
    });
}

function loadDashboard() {
    // Load jobs data
    fetch('/jobs')
        .then(response => response.json())
        .then(jobs => {
            updateDashboardStats(jobs);
            updateRecentJobs(jobs);
        })
        .catch(error => {
            console.error('Error fetching jobs:', error);
        });
    
    // Load media data for dashboard statistics
    fetch('/media')
        .then(response => response.json())
        .then(media => {
            updateMediaStats(media);
        })
        .catch(error => {
            console.error('Error fetching media:', error);
        });

    // Load movie data for dashboard statistics
    fetch('/movies')
        .then(response => response.json())
        .then(movies => {
            updateMovieStats(movies);
        })
        .catch(error => {
            console.error('Error fetching movies:', error);
        });
}

function loadJobs() {
    fetch('/jobs')
        .then(response => response.json())
        .then(jobs => {
            const musicJobs = jobs.filter(j => j.media_type === 'music');
            const movieJobs = jobs.filter(j => j.media_type === 'movie');
            const tvJobs = jobs.filter(j => j.media_type !== 'movie' && j.media_type !== 'music');
            updateJobsTable(tvJobs);
            updateMovieJobsTable(movieJobs);
            updateMusicJobsTable(musicJobs);
        })
        .catch(error => {
            console.error('Error fetching jobs:', error);
        });
}

function updateJobsData() {
    fetch('/jobs')
        .then(response => response.json())
        .then(jobs => {
            const musicJobs = jobs.filter(j => j.media_type === 'music');
            const movieJobs = jobs.filter(j => j.media_type === 'movie');
            const tvJobs = jobs.filter(j => j.media_type !== 'movie' && j.media_type !== 'music');
            if (document.querySelector('#jobs:not(.d-none)')) {
                updateJobsTable(tvJobs);
                updateMovieJobsTable(movieJobs);
                updateMusicJobsTable(musicJobs);
            }
            if (document.querySelector('#dashboard:not(.d-none)')) {
                updateDashboardStats(jobs);
                updateRecentJobs(jobs);
                fetch('/media')
                    .then(response => response.json())
                    .then(updateMediaStats)
                    .catch(error => console.error('Error fetching media:', error));
                fetch('/movies')
                    .then(response => response.json())
                    .then(updateMovieStats)
                    .catch(error => console.error('Error fetching movies:', error));
            }
            if (document.querySelector('#history:not(.d-none)')) {
                loadHistory();
            }
            
            // Check if job details modal is open
            const modal = document.getElementById('jobDetailModal');
            if (modal && modal.classList.contains('show')) {
                const jobId = modal.getAttribute('data-job-id');
                if (jobId) {
                    const job = jobs.find(j => j.job_id === jobId);
                    if (job) {
                        updateJobDetailModal(job);
                    }
                }
            }
        })
        .catch(error => {
            console.error('Error fetching jobs:', error);
        });
}

function loadPlaylists() {
    fetch('/playlists')
        .then(r => r.json())
        .then(list => updatePlaylistsTable(list))
        .catch(err => console.error('Error fetching playlists:', err));
}

function updatePlaylistsTable(data) {
    const tbody = document.querySelector('#playlists-table tbody');
    tbody.innerHTML = '';
    if (data.length === 0) {
        const row = document.createElement('tr');
        row.innerHTML = '<td colspan="6" class="text-center">No playlists</td>';
        tbody.appendChild(row);
        return;
    }
    data.forEach(p => {
        const row = document.createElement('tr');
        const link = `<a href="${p.url}" target="_blank">${p.url}</a>`;
        const toggle = `<div class="form-check form-switch"><input class="form-check-input playlist-toggle" type="checkbox" data-id="${p.id}" ${p.enabled ? 'checked' : ''}></div>`;
        const actions = `<button class="btn btn-sm btn-danger remove-playlist" data-id="${p.id}"><i class="bi bi-trash"></i></button>`;
        row.innerHTML = `<td>${p.show_name}</td><td>${p.season_num}</td><td>${p.last_episode}</td><td>${link}</td><td>${toggle}</td><td>${actions}</td>`;
        tbody.appendChild(row);
    });

    tbody.querySelectorAll('.playlist-toggle').forEach(el => {
        el.addEventListener('change', function() {
            const pid = this.getAttribute('data-id');
            fetch(`/playlists/${pid}`, {
                method: 'PUT',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({enabled: this.checked})
            }).then(r => r.json()).then(d => {
                if (!d.success) {
                    showToast('Error', d.error || 'Failed to update playlist');
                    this.checked = !this.checked;
                }
            }).catch(() => {
                showToast('Error', 'Failed to update playlist');
                this.checked = !this.checked;
            });
        });
    });

    tbody.querySelectorAll('.remove-playlist').forEach(btn => {
        btn.addEventListener('click', function() {
            if (!confirm('Remove this playlist?')) return;
            const pid = this.getAttribute('data-id');
            fetch(`/playlists/${pid}`, {method: 'DELETE'})
                .then(r => r.json())
                .then(d => {
                    if (d.success) {
                        loadPlaylists();
                    } else {
                        showToast('Error', d.error || 'Failed to remove playlist');
                    }
                })
                .catch(() => showToast('Error', 'Failed to remove playlist'));
        });
    });
}

function escapeHtml(value) {
    if (value === undefined || value === null) {
        return '';
    }
    return value
        .toString()
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function formatRetention(retention) {
    if (!retention || retention.mode === 'all') {
        return 'Keep all episodes';
    }
    if (retention.mode === 'episodes') {
        return `Keep last ${retention.value} episodes`;
    }
    if (retention.mode === 'days') {
        return `Keep last ${retention.value} days`;
    }
    return 'Custom';
}

function loadSubscriptions() {
    fetch('/subscriptions')
        .then(r => r.json())
        .then(list => {
            subscriptionsCache = Array.isArray(list) ? list : [];
            updateSubscriptionsTable(subscriptionsCache);
        })
        .catch(err => console.error('Error fetching subscriptions:', err));
}

function updateSubscriptionsTable(data) {
    const container = document.getElementById('subscriptions-container');
    if (!container) {
        return;
    }
    container.innerHTML = '';
    if (!data || data.length === 0) {
        container.innerHTML = '<p class="text-gray-400 text-center py-4">No channel subscriptions</p>';
        return;
    }

    data.forEach(sub => {
        const showName = escapeHtml(sub.show_name || '');
        const channelUrl = escapeHtml(sub.url || '');
        const retentionText = formatRetention(sub.retention);
        const lastEpisode = sub.last_episode || 0;
        const enabled = sub.enabled !== false;
        const statusText = enabled ? 'Active' : 'Paused';
        const statusColor = enabled ? 'text-green-400' : 'text-gray-400';
        const safeHref = encodeURI(sub.url || '');

        const card = document.createElement('div');
        card.className = 'subscription-card';
        card.innerHTML = `
            <div class="subscription-header">
                <div class="flex-1">
                    <div class="d-flex align-items-center gap-2 mb-1">
                        <h3 class="subscription-name mb-0">${showName}</h3>
                    </div>
                    <p class="subscription-channel mb-2"><a href="${safeHref}" target="_blank" rel="noopener noreferrer" class="text-gray-400">${channelUrl}</a></p>
                    <div class="d-flex align-items-center gap-3 text-sm text-gray-400">
                        <span>Last Episode: ${lastEpisode}</span>
                    </div>
                </div>
                <div class="d-flex align-items-center gap-2">
                    <button type="button" class="btn-icon" data-action="edit" data-id="${sub.id}" title="Edit subscription">
                        <i class="bi bi-pencil"></i>
                    </button>
                    <button type="button" class="btn-icon" data-action="delete" data-id="${sub.id}" title="Delete subscription">
                        <i class="bi bi-trash"></i>
                    </button>
                </div>
            </div>

            <div class="subscription-stats">
                <div class="stat-item">
                    <div class="stat-label">Retention</div>
                    <div class="stat-value">${escapeHtml(retentionText)}</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Auto Download</div>
                    <div class="stat-value">${enabled ? 'Enabled' : 'Disabled'}</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Status</div>
                    <div class="stat-value ${statusColor}">${statusText}</div>
                </div>
            </div>

            <div class="subscription-actions">
                <button type="button" class="btn btn-secondary btn-action" data-action="check" data-id="${sub.id}">
                    <i class="bi bi-arrow-clockwise"></i>
                    Check Now
                </button>
                <button type="button" class="btn btn-primary btn-action" data-action="toggle" data-id="${sub.id}">
                    <i class="bi ${enabled ? 'bi-pause-circle' : 'bi-play-circle'}"></i>
                    ${enabled ? 'Pause' : 'Resume'}
                </button>
            </div>
        `;
        container.appendChild(card);
    });

    // Attach event listeners to all buttons
    container.addEventListener('click', function(event) {
        const button = event.target.closest('button[data-action]');
        if (!button) return;

        const action = button.getAttribute('data-action');
        const id = button.getAttribute('data-id');
        const subscription = subscriptionsCache.find(s => s.id === id);
        if (!subscription) return;

        if (action === 'edit') {
            const editRetentionControls = { select: document.getElementById('edit_retention_type'), input: document.getElementById('edit_retention_value') };
            if (!editRetentionControls.select || !editRetentionControls.input) return;

            window.editingSubscriptionId = id;
            document.getElementById('edit_subscription_show_name').value = subscription.show_name || '';
            const mode = (subscription.retention && subscription.retention.mode) || 'all';
            let selectValue = 'keep_all';
            if (mode === 'episodes') selectValue = 'keep_episodes';
            else if (mode === 'days') selectValue = 'keep_days';

            editRetentionControls.select.value = selectValue;
            editRetentionControls.select.dispatchEvent(new Event('change'));
            if (selectValue !== 'keep_all') {
                editRetentionControls.input.value = subscription.retention && subscription.retention.value ? subscription.retention.value : '';
            }
            document.getElementById('edit_subscription_enabled').checked = subscription.enabled !== false;
            new bootstrap.Modal(document.getElementById('subscriptionEditModal')).show();
        } else if (action === 'toggle') {
            const payload = { enabled: !(subscription.enabled !== false) };
            fetch(`/subscriptions/${id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            })
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        showToast('Success', payload.enabled ? 'Subscription resumed' : 'Subscription paused');
                        loadSubscriptions();
                    } else {
                        showToast('Error', data.error || 'Failed to update subscription');
                    }
                })
                .catch(() => showToast('Error', 'Failed to update subscription'));
        } else if (action === 'delete') {
            if (!confirm('Remove this subscription?')) return;
            fetch(`/subscriptions/${id}`, { method: 'DELETE' })
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        showToast('Success', 'Subscription removed');
                        loadSubscriptions();
                    } else {
                        showToast('Error', data.error || 'Failed to remove subscription');
                    }
                })
                .catch(() => showToast('Error', 'Failed to remove subscription'));
        } else if (action === 'check') {
            fetch('/playlists/check', { method: 'POST' })
                .then(r => r.json())
                .then(data => {
                    if (data.created_jobs && data.created_jobs.length > 0) {
                        showToast('Updates', `Created ${data.created_jobs.length} jobs`);
                    } else {
                        showToast('Info', 'No updates found');
                    }
                })
                .catch(() => showToast('Error', 'Failed to check for updates'));
        }
    });
}

function updateJobsTable(jobs) {
    const jobsTable = document.getElementById('jobs-table').querySelector('tbody');
    jobsTable.innerHTML = '';
    
    if (jobs.length === 0) {
        const row = document.createElement('tr');
        row.innerHTML = '<td colspan="7" class="text-center">No jobs found</td>';
        jobsTable.appendChild(row);
        return;
    }
    
    // Sort jobs by creation date, newest first
    jobs.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
    
    jobs.forEach(job => {
        const row = document.createElement('tr');
        
        // Short ID display
        const shortId = job.job_id.substring(0, 8);
        
        // Status badge
        const statusClass = getStatusBadgeClass(job.status);
        
        // Additional status info
        let statusInfo = '';
        if (job.current_stage && job.current_stage !== job.status && job.current_stage !== 'waiting') {
            statusInfo = `<br><small>${job.detailed_status || ''}</small>`;
        }
        
        // Progress display
        let progressDisplay = `
            <div class="progress">
                <div class="progress-bar" role="progressbar" style="width: ${job.progress}%" 
                    aria-valuenow="${job.progress}" aria-valuemin="0" aria-valuemax="100">
                    ${Math.round(job.progress)}%
                </div>
            </div>
        `;
        
        // Add file progress display if available
        if (job.total_files && job.total_files > 0) {
            progressDisplay += `
                <small class="d-block mt-1 text-muted">
                    ${job.processed_files || 0} / ${job.total_files} files
                </small>
            `;
        }
        
        // Add current file if available
        if (job.current_file && job.status !== 'completed' && job.status !== 'failed') {
            progressDisplay += `
                <small class="d-block text-truncate" style="max-width: 200px;" title="${job.current_file}">
                    ${job.current_file}
                </small>
            `;
        }

        // Show remaining queue if available
        if (job.remaining_files && job.remaining_files.length > 0 && job.status !== 'completed' && job.status !== 'failed') {
            const preview = job.remaining_files.slice(0, 3).join(', ');
            const title = job.remaining_files.join(', ');
            progressDisplay += `
                <small class="d-block text-muted text-truncate" style="max-width: 200px;" title="${title}">
                    Next: ${preview}${job.remaining_files.length > 3 ? '...' : ''}
                </small>
            `;
        }
        
        const canCancel = !['completed', 'failed', 'cancelled'].includes(job.status);
        const cancelBtn = canCancel ? `
                <button class="btn btn-sm btn-danger cancel-job" data-job-id="${job.job_id}">
                    <i class="bi bi-x-circle"></i>
                </button>` : '';

        row.innerHTML = `
            <td title="${job.job_id}">${shortId}...</td>
            <td>${job.show_name}</td>
            <td>${job.season_num}</td>
            <td><span class="badge ${statusClass}">${job.status}</span>${statusInfo}</td>
            <td>${progressDisplay}</td>
            <td>${formatDate(job.created_at)}</td>
            <td>
                <button class="btn btn-sm btn-info view-job" data-job-id="${job.job_id}">
                    <i class="bi bi-eye"></i>
                </button>
                ${cancelBtn}
            </td>
        `;
        
        jobsTable.appendChild(row);
    });
    
    // Add event listeners to view buttons
    document.querySelectorAll('.view-job').forEach(btn => {
        btn.addEventListener('click', function() {
            const jobId = this.getAttribute('data-job-id');
            showJobDetails(jobId);
        });
    });

    // Add event listeners to cancel buttons
    document.querySelectorAll('.cancel-job').forEach(btn => {
        btn.addEventListener('click', function() {
            const jobId = this.getAttribute('data-job-id');
            if (confirm('Cancel this job?')) {
                fetch(`/jobs/${jobId}`, { method: 'DELETE' })
                    .then(r => {
                        if (r.ok) {
                            showToast('Success', 'Job cancelled');
                            updateJobsData();
                        } else {
                            r.json().then(d => {
                                showToast('Error', d.error || 'Failed to cancel job');
                            });
                        }
                    })
                    .catch(() => showToast('Error', 'Failed to cancel job'));
            }
        });
    });
}

function updateMovieJobsTable(jobs) {
    const table = document.getElementById('movie-jobs-table').querySelector('tbody');
    table.innerHTML = '';

    if (jobs.length === 0) {
        const row = document.createElement('tr');
        row.innerHTML = '<td colspan="6" class="text-center">No jobs found</td>';
        table.appendChild(row);
        return;
    }

    jobs.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));

    jobs.forEach(job => {
        const row = document.createElement('tr');
        const shortId = job.job_id.substring(0, 8);
        const statusClass = getStatusBadgeClass(job.status);

        let progressDisplay = `
            <div class="progress">
                <div class="progress-bar" role="progressbar" style="width: ${job.progress}%"
                    aria-valuenow="${job.progress}" aria-valuemin="0" aria-valuemax="100">
                    ${Math.round(job.progress)}%
                </div>
            </div>`;

        if (job.current_file && job.status !== 'completed' && job.status !== 'failed') {
            progressDisplay += `
                <small class="d-block text-truncate" style="max-width: 200px;" title="${job.current_file}">
                    ${job.current_file}
                </small>
            `;
        }

        const canCancel = !['completed', 'failed', 'cancelled'].includes(job.status);
        const cancelBtn = canCancel ? `
                <button class="btn btn-sm btn-danger cancel-job" data-job-id="${job.job_id}">
                    <i class="bi bi-x-circle"></i>
                </button>` : '';

        row.innerHTML = `
            <td title="${job.job_id}">${shortId}...</td>
            <td>${job.movie_name}</td>
            <td><span class="badge ${statusClass}">${job.status}</span></td>
            <td>${progressDisplay}</td>
            <td>${formatDate(job.created_at)}</td>
            <td>
                <button class="btn btn-sm btn-info view-job" data-job-id="${job.job_id}">
                    <i class="bi bi-eye"></i>
                </button>
                ${cancelBtn}
            </td>
        `;

        table.appendChild(row);
    });

    document.querySelectorAll('#movie-jobs-table .view-job').forEach(btn => {
        btn.addEventListener('click', function() {
            const jobId = this.getAttribute('data-job-id');
            showJobDetails(jobId);
        });
    });

    document.querySelectorAll('#movie-jobs-table .cancel-job').forEach(btn => {
        btn.addEventListener('click', function() {
            const jobId = this.getAttribute('data-job-id');
            if (confirm('Cancel this job?')) {
                fetch(`/jobs/${jobId}`, { method: 'DELETE' })
                    .then(r => {
                        if (r.ok) {
                            showToast('Success', 'Job cancelled');
                            updateJobsData();
                        } else {
                            r.json().then(d => {
                                showToast('Error', d.error || 'Failed to cancel job');
                            });
                        }
                    })
                    .catch(() => showToast('Error', 'Failed to cancel job'));
            }
        });
    });
}

function updateMusicJobsTable(jobs) {
    const tableEl = document.getElementById('music-jobs-table');
    if (!tableEl) {
        return;
    }
    const tbody = tableEl.querySelector('tbody');
    tbody.innerHTML = '';

    if (!jobs || jobs.length === 0) {
        const row = document.createElement('tr');
        row.innerHTML = '<td colspan="7" class="text-center">No jobs found</td>';
        tbody.appendChild(row);
        return;
    }

    jobs.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));

    jobs.forEach(job => {
        const row = document.createElement('tr');
        const shortId = job.job_id.substring(0, 8);
        const statusClass = getStatusBadgeClass(job.status);
        const request = job.music_request || {};
        const collection = request.collection || {};
        const tracks = Array.isArray(request.tracks) ? request.tracks : [];
        const jobType = (request.job_type || 'music').toString();
        const displayType = jobType.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
        const collectionName = request.display_name || collection.title || job.show_name || 'Music';

        let progressDisplay = `
            <div class="progress">
                <div class="progress-bar" role="progressbar" style="width: ${job.progress}%"
                    aria-valuenow="${job.progress}" aria-valuemin="0" aria-valuemax="100">
                    ${Math.round(job.progress)}%
                </div>
            </div>`;

        if (tracks.length) {
            progressDisplay += `
                <small class="d-block text-muted">${job.processed_files || 0} / ${tracks.length} tracks</small>
            `;
        }

        if (job.current_file && job.status !== 'completed' && job.status !== 'failed') {
            progressDisplay += `
                <small class="d-block text-truncate" style="max-width: 200px;" title="${job.current_file}">
                    ${job.current_file}
                </small>
            `;
        }

        const canCancel = !['completed', 'failed', 'cancelled'].includes(job.status);
        const cancelBtn = canCancel ? `
                <button class="btn btn-sm btn-danger cancel-job" data-job-id="${job.job_id}">
                    <i class="bi bi-x-circle"></i>
                </button>` : '';

        row.innerHTML = `
            <td title="${job.job_id}">${shortId}...</td>
            <td>${escapeHtml(collectionName)}</td>
            <td>${escapeHtml(displayType)}</td>
            <td><span class="badge ${statusClass}">${job.status}</span></td>
            <td>${progressDisplay}</td>
            <td>${formatDate(job.created_at)}</td>
            <td>
                <button class="btn btn-sm btn-info view-job" data-job-id="${job.job_id}">
                    <i class="bi bi-eye"></i>
                </button>
                ${cancelBtn}
            </td>
        `;

        tbody.appendChild(row);
    });

    tbody.querySelectorAll('.cancel-job').forEach(btn => {
        btn.addEventListener('click', function() {
            const jobId = this.getAttribute('data-job-id');
            if (confirm('Cancel this job?')) {
                fetch(`/jobs/${jobId}`, { method: 'DELETE' })
                    .then(r => {
                        if (r.ok) {
                            showToast('Success', 'Job cancelled');
                            updateJobsData();
                        } else {
                            r.json().then(d => {
                                showToast('Error', d.error || 'Failed to cancel job');
                            });
                        }
                    })
                    .catch(() => showToast('Error', 'Failed to cancel job'));
            }
        });
    });

    tbody.querySelectorAll('.view-job').forEach(btn => {
        btn.addEventListener('click', function() {
            const jobId = this.getAttribute('data-job-id');
            showJobDetails(jobId);
        });
    });
}

function loadHistory() {
    fetch('/history')
        .then(response => response.json())
        .then(jobs => {
            const musicJobs = jobs.filter(j => j.media_type === 'music');
            const movieJobs = jobs.filter(j => j.media_type === 'movie');
            const tvJobs = jobs.filter(j => j.media_type !== 'movie' && j.media_type !== 'music');
            updateHistoryTable(tvJobs);
            updateMovieHistoryTable(movieJobs);
            updateMusicHistoryTable(musicJobs);
        })
        .catch(error => {
            console.error('Error fetching history:', error);
        });
}

function updateHistoryTable(jobs) {
    const histTable = document.getElementById('history-table').querySelector('tbody');
    histTable.innerHTML = '';

    if (jobs.length === 0) {
        const row = document.createElement('tr');
        row.innerHTML = '<td colspan="7" class="text-center">No jobs found</td>';
        histTable.appendChild(row);
        return;
    }

    jobs.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));

    jobs.forEach(job => {
        const row = document.createElement('tr');
        const shortId = job.job_id.substring(0, 8);
        const statusClass = getStatusBadgeClass(job.status);
        let progressDisplay = `
            <div class="progress">
                <div class="progress-bar" role="progressbar" style="width: ${job.progress}%"
                    aria-valuenow="${job.progress}" aria-valuemin="0" aria-valuemax="100">
                    ${Math.round(job.progress)}%
                </div>
            </div>`;

        row.innerHTML = `
            <td title="${job.job_id}">${shortId}...</td>
            <td>${job.show_name}</td>
            <td>${job.season_num}</td>
            <td><span class="badge ${statusClass}">${job.status}</span></td>
            <td>${progressDisplay}</td>
            <td>${formatDate(job.created_at)}</td>
            <td>
                <button class="btn btn-sm btn-info view-job" data-job-id="${job.job_id}">
                    <i class="bi bi-eye"></i>
                </button>
            </td>`;

        histTable.appendChild(row);
    });

    document.querySelectorAll('#history-table .view-job').forEach(btn => {
        btn.addEventListener('click', function() {
            const jobId = this.getAttribute('data-job-id');
            showJobDetails(jobId);
        });
    });
}

function updateMovieHistoryTable(jobs) {
    const table = document.getElementById('movie-history-table').querySelector('tbody');
    table.innerHTML = '';

    if (jobs.length === 0) {
        const row = document.createElement('tr');
        row.innerHTML = '<td colspan="6" class="text-center">No jobs found</td>';
        table.appendChild(row);
        return;
    }

    jobs.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));

    jobs.forEach(job => {
        const row = document.createElement('tr');
        const shortId = job.job_id.substring(0, 8);
        const statusClass = getStatusBadgeClass(job.status);
        let progressDisplay = `
            <div class="progress">
                <div class="progress-bar" role="progressbar" style="width: ${job.progress}%"
                    aria-valuenow="${job.progress}" aria-valuemin="0" aria-valuemax="100">
                    ${Math.round(job.progress)}%
                </div>
            </div>`;

        row.innerHTML = `
            <td title="${job.job_id}">${shortId}...</td>
            <td>${job.movie_name}</td>
            <td><span class="badge ${statusClass}">${job.status}</span></td>
            <td>${progressDisplay}</td>
            <td>${formatDate(job.created_at)}</td>
            <td>
                <button class="btn btn-sm btn-info view-job" data-job-id="${job.job_id}">
                    <i class="bi bi-eye"></i>
                </button>
            </td>`;

        table.appendChild(row);
    });

    document.querySelectorAll('#movie-history-table .view-job').forEach(btn => {
        btn.addEventListener('click', function() {
            const jobId = this.getAttribute('data-job-id');
            showJobDetails(jobId);
        });
    });
}

function updateMusicHistoryTable(jobs) {
    const tableEl = document.getElementById('music-history-table');
    if (!tableEl) {
        return;
    }
    const tbody = tableEl.querySelector('tbody');
    tbody.innerHTML = '';

    if (!jobs || jobs.length === 0) {
        const row = document.createElement('tr');
        row.innerHTML = '<td colspan="7" class="text-center">No jobs found</td>';
        tbody.appendChild(row);
        return;
    }

    jobs.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));

    jobs.forEach(job => {
        const row = document.createElement('tr');
        const shortId = job.job_id.substring(0, 8);
        const statusClass = getStatusBadgeClass(job.status);
        const request = job.music_request || {};
        const collection = request.collection || {};
        const jobType = (request.job_type || 'music').toString();
        const displayType = jobType.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
        const collectionName = request.display_name || collection.title || job.show_name || 'Music';

        let progressDisplay = `
            <div class="progress">
                <div class="progress-bar" role="progressbar" style="width: ${job.progress}%"
                    aria-valuenow="${job.progress}" aria-valuemin="0" aria-valuemax="100">
                    ${Math.round(job.progress)}%
                </div>
            </div>`;

        row.innerHTML = `
            <td title="${job.job_id}">${shortId}...</td>
            <td>${escapeHtml(collectionName)}</td>
            <td>${escapeHtml(displayType)}</td>
            <td><span class="badge ${statusClass}">${job.status}</span></td>
            <td>${progressDisplay}</td>
            <td>${formatDate(job.updated_at || job.created_at)}</td>
            <td>
                <button class="btn btn-sm btn-info view-job" data-job-id="${job.job_id}">
                    <i class="bi bi-eye"></i>
                </button>
            </td>`;

        tbody.appendChild(row);
    });

    tbody.querySelectorAll('.view-job').forEach(btn => {
        btn.addEventListener('click', function() {
            const jobId = this.getAttribute('data-job-id');
            showJobDetails(jobId);
        });
    });
}

function handleMusicSingleSubmit(event) {
    event.preventDefault();
    const submitButton = document.getElementById('music-single-submit');
    toggleButtonLoading(submitButton, true, 'Queuing...');

    const url = document.getElementById('music_single_url').value.trim();
    const title = document.getElementById('music_single_title').value.trim();
    const artist = document.getElementById('music_single_artist').value.trim();
    if (!url || !title || !artist) {
        toggleButtonLoading(submitButton, false);
        showToast('Error', 'Track URL, title, and artist are required.');
        return;
    }

    const album = document.getElementById('music_single_album').value.trim();
    const year = document.getElementById('music_single_year').value.trim();
    const trackNo = document.getElementById('music_single_track').value.trim();
    const discNo = document.getElementById('music_single_disc').value.trim();
    const genres = parseGenresInput(document.getElementById('music_single_genres').value);
    const tags = parseTagInput(document.getElementById('music_single_tags').value);
    const cover = document.getElementById('music_single_cover').value.trim();

    const track = serializeMusicTrack(
        {
            title,
            artist,
            album,
            year,
            track_number: toOptionalNumber(trackNo),
            disc_number: toOptionalNumber(discNo) || 1,
            genres,
            tags,
            cover,
            source_url: url,
        },
        0,
    );

    const payload = {
        job_type: 'single',
        source_url: url,
        display_name: title,
        collection: {
            title: album || title,
            artist,
            year: year || '',
            genres,
            cover_url: cover,
        },
        tracks: [track],
    };

    postMusicJob(payload, () => {
        event.currentTarget.reset();
    }).finally(() => {
        toggleButtonLoading(submitButton, false);
    });
}

function handleMusicAlbumFetch() {
    const fetchButton = document.getElementById('music_album_fetch');
    const urlInput = document.getElementById('music_album_url');
    if (!urlInput) {
        return;
    }
    const url = urlInput.value.trim();
    if (!url) {
        showToast('Error', 'Enter an album or playlist URL.');
        return;
    }

    toggleButtonLoading(fetchButton, true, 'Fetching...');
    fetch(`/music/playlists/info?url=${encodeURIComponent(url)}`)
        .then(r => r.json())
        .then(info => {
            if (info.error) {
                showToast('Error', info.error);
                return;
            }
            document.getElementById('music_album_title').value = info.title || document.getElementById('music_album_title').value;
            document.getElementById('music_album_artist').value = info.uploader || document.getElementById('music_album_artist').value;
            if (info.thumbnail) {
                document.getElementById('music_album_cover').value = info.thumbnail;
            }
            const firstEntry = (info.entries || [])[0] || {};
            if (firstEntry.release_year) {
                document.getElementById('music_album_year').value = firstEntry.release_year;
            }
            musicState.albumTracks = (info.entries || []).map((entry, idx) =>
                normalizeMusicEntry(entry, idx + 1, info.title || '')
            );
            renderMusicTrackTable('album');
            showToast('Success', `Loaded ${musicState.albumTracks.length} tracks`);
        })
        .catch(() => showToast('Error', 'Failed to fetch playlist metadata'))
        .finally(() => toggleButtonLoading(fetchButton, false));
}

function handleMusicAlbumSubmit(event) {
    event.preventDefault();
    const submitButton = document.getElementById('music-album-submit');
    toggleButtonLoading(submitButton, true, 'Queuing...');

    const url = document.getElementById('music_album_url').value.trim();
    const title = document.getElementById('music_album_title').value.trim();
    const artist = document.getElementById('music_album_artist').value.trim();
    if (!url || !title || !artist) {
        toggleButtonLoading(submitButton, false);
        showToast('Error', 'Album URL, title, and artist are required.');
        return;
    }

    if (!musicState.albumTracks.length) {
        toggleButtonLoading(submitButton, false);
        showToast('Error', 'Add at least one track to the album.');
        return;
    }

    const year = document.getElementById('music_album_year').value.trim();
    const genres = parseGenresInput(document.getElementById('music_album_genre').value);
    const cover = document.getElementById('music_album_cover').value.trim();
    const embedCover = document.getElementById('music_album_embed_cover').checked;

    const payload = {
        job_type: 'album',
        source_url: url,
        display_name: title,
        collection: {
            title,
            artist,
            year: year || '',
            genres,
            cover_url: cover,
            embed_cover: embedCover,
        },
        tracks: musicState.albumTracks.map((track, idx) => serializeMusicTrack(track, idx)),
    };

    postMusicJob(payload, () => {
        event.currentTarget.reset();
        musicState.albumTracks = [];
        renderMusicTrackTable('album');
    }).finally(() => toggleButtonLoading(submitButton, false));
}

function handleMusicPlaylistFetch() {
    const fetchButton = document.getElementById('music_playlist_fetch');
    const urlInput = document.getElementById('music_playlist_url');
    if (!urlInput) {
        return;
    }
    const url = urlInput.value.trim();
    if (!url) {
        showToast('Error', 'Enter a playlist URL to inspect.');
        return;
    }

    toggleButtonLoading(fetchButton, true, 'Inspecting...');
    fetch(`/music/playlists/info?url=${encodeURIComponent(url)}`)
        .then(r => r.json())
        .then(info => {
            if (info.error) {
                showToast('Error', info.error);
                return;
            }
            document.getElementById('music_playlist_title').value = info.title || document.getElementById('music_playlist_title').value;
            document.getElementById('music_playlist_owner').value = info.uploader || document.getElementById('music_playlist_owner').value;
            if (info.thumbnail) {
                document.getElementById('music_playlist_cover').value = info.thumbnail;
            }
            let entries = info.entries || [];
            const limitValue = document.getElementById('music_playlist_limit').value.trim();
            const limit = limitValue ? parseInt(limitValue, 10) : null;
            if (limit && Number.isFinite(limit)) {
                entries = entries.slice(0, limit);
            }
            musicState.playlistTracks = entries.map((entry, idx) =>
                normalizeMusicEntry(entry, idx + 1, info.title || '')
            );
            renderMusicTrackTable('playlist');
            showToast('Success', `Loaded ${musicState.playlistTracks.length} tracks`);
        })
        .catch(() => showToast('Error', 'Failed to inspect playlist'))
        .finally(() => toggleButtonLoading(fetchButton, false));
}

function handleMusicPlaylistSubmit(event) {
    event.preventDefault();
    const submitButton = document.getElementById('music-playlist-submit');
    toggleButtonLoading(submitButton, true, 'Queuing...');

    const url = document.getElementById('music_playlist_url').value.trim();
    const title = document.getElementById('music_playlist_title').value.trim();
    if (!url || !title) {
        toggleButtonLoading(submitButton, false);
        showToast('Error', 'Playlist URL and collection name are required.');
        return;
    }

    if (!musicState.playlistTracks.length) {
        toggleButtonLoading(submitButton, false);
        showToast('Error', 'Load the playlist to populate tracks before submitting.');
        return;
    }

    const owner = document.getElementById('music_playlist_owner').value.trim();
    const variant = document.getElementById('music_playlist_variant').value;
    const limitValue = document.getElementById('music_playlist_limit').value.trim();
    const limit = limitValue ? parseInt(limitValue, 10) : null;
    const cover = document.getElementById('music_playlist_cover').value.trim();
    const includeFuture = document.getElementById('music_playlist_include_future').checked;

    const payload = {
        job_type: variant || 'playlist',
        source_url: url,
        display_name: title,
        collection: {
            title,
            owner,
            cover_url: cover,
            variant,
            include_future: includeFuture,
            limit: limit || null,
        },
        tracks: musicState.playlistTracks.map((track, idx) => serializeMusicTrack(track, idx)),
    };

    postMusicJob(payload, () => {
        event.currentTarget.reset();
        musicState.playlistTracks = [];
        renderMusicTrackTable('playlist');
    }).finally(() => toggleButtonLoading(submitButton, false));
}

function addMusicTrack(type, track = null) {
    const list = getMusicTrackState(type);
    const baseAlbum = type === 'album' ? document.getElementById('music_album_title')?.value.trim() : document.getElementById('music_playlist_title')?.value.trim();
    const nextIndex = list.length + 1;
    const newTrack = track || {
        title: `Track ${nextIndex}`,
        artist: '',
        album: baseAlbum || '',
        track_number: nextIndex,
        disc_number: 1,
        duration: null,
        genres: [],
        tags: {},
        year: '',
        source_url: '',
        thumbnail: '',
    };
    list.push(newTrack);
    renderMusicTrackTable(type);
}

function getMusicTrackState(type) {
    return type === 'playlist' ? musicState.playlistTracks : musicState.albumTracks;
}

function renderMusicTrackTable(type) {
    const containerId = type === 'playlist' ? 'music-playlist-tracks' : 'music-album-tracks';
    const container = document.getElementById(containerId);
    if (!container) {
        return;
    }
    const tracks = getMusicTrackState(type);
    if (!tracks.length) {
        container.innerHTML = '<p class="text-muted mb-0">No tracks available. Fetch metadata or add tracks manually.</p>';
        return;
    }

    const table = document.createElement('table');
    table.className = 'table table-sm align-middle';
    table.innerHTML = `
        <thead>
            <tr>
                <th>#</th>
                <th>Track</th>
                <th>Album</th>
                <th>Duration</th>
                <th>Tags</th>
                <th>Actions</th>
            </tr>
        </thead>
        <tbody></tbody>
    `;

    const tbody = table.querySelector('tbody');
    tracks.forEach((track, index) => {
        const row = document.createElement('tr');
        const tagsCount = track.tags ? Object.keys(track.tags).length : 0;
        row.innerHTML = `
            <td>${index + 1}</td>
            <td>
                <div class="fw-semibold">${escapeHtml(track.title || `Track ${index + 1}`)}</div>
                <small class="text-muted">${escapeHtml(track.artist || '')}</small>
            </td>
            <td>${escapeHtml(track.album || '')}</td>
            <td>${track.duration ? formatDuration(track.duration) : '—'}</td>
            <td>${tagsCount} tag${tagsCount === 1 ? '' : 's'}</td>
            <td>
                <div class="btn-group btn-group-sm" role="group">
                    <button class="btn btn-outline-secondary" data-action="edit" data-index="${index}" data-type="${type}"><i class="bi bi-pencil"></i></button>
                    <button class="btn btn-outline-danger" data-action="remove" data-index="${index}" data-type="${type}"><i class="bi bi-trash"></i></button>
                </div>
            </td>
        `;
        tbody.appendChild(row);
    });

    container.innerHTML = '';
    container.appendChild(table);

    tbody.querySelectorAll('button[data-action="edit"]').forEach(btn => {
        btn.addEventListener('click', () => {
            const index = parseInt(btn.getAttribute('data-index'), 10);
            openMusicTrackModal(type, index);
        });
    });

    tbody.querySelectorAll('button[data-action="remove"]').forEach(btn => {
        btn.addEventListener('click', () => {
            const index = parseInt(btn.getAttribute('data-index'), 10);
            const list = getMusicTrackState(type);
            list.splice(index, 1);
            renderMusicTrackTable(type);
        });
    });
}

function openMusicTrackModal(type, index) {
    const tracks = getMusicTrackState(type);
    const track = tracks[index];
    if (!track) {
        return;
    }
    musicState.editing = { type, index };
    musicState.pendingTags = { ...(track.tags || {}) };

    document.getElementById('music_track_index').value = index;
    document.getElementById('music_track_title').value = track.title || '';
    document.getElementById('music_track_artist').value = track.artist || '';
    document.getElementById('music_track_album').value = track.album || '';
    document.getElementById('music_track_year').value = track.year || '';
    document.getElementById('music_track_number').value = track.track_number || index + 1;
    document.getElementById('music_track_disc').value = track.disc_number || 1;
    document.getElementById('music_track_duration').value = track.duration || '';
    document.getElementById('music_track_genres').value = (track.genres || []).join('; ');
    document.getElementById('music_track_tags').value = formatTags(track.tags || {});
    document.getElementById('music_track_notes').value = track.notes || '';

    renderMusicTagList();
    const modal = new bootstrap.Modal(document.getElementById('musicTrackModal'));
    modal.show();
}

function saveMusicTrackModal() {
    if (!musicState.editing) {
        return;
    }
    const { type, index } = musicState.editing;
    const tracks = getMusicTrackState(type);
    const track = tracks[index];
    if (!track) {
        return;
    }

    track.title = document.getElementById('music_track_title').value.trim() || track.title;
    track.artist = document.getElementById('music_track_artist').value.trim();
    track.album = document.getElementById('music_track_album').value.trim();
    track.year = document.getElementById('music_track_year').value.trim();
    track.track_number = toOptionalNumber(document.getElementById('music_track_number').value.trim()) || index + 1;
    track.disc_number = toOptionalNumber(document.getElementById('music_track_disc').value.trim()) || 1;
    track.duration = toOptionalNumber(document.getElementById('music_track_duration').value.trim());
    track.genres = parseGenresInput(document.getElementById('music_track_genres').value);
    track.tags = parseTagInput(document.getElementById('music_track_tags').value);
    track.notes = document.getElementById('music_track_notes').value.trim();

    renderMusicTrackTable(type);

    const modalEl = document.getElementById('musicTrackModal');
    const modal = bootstrap.Modal.getInstance(modalEl);
    if (modal) {
        modal.hide();
    }
    musicState.editing = null;
}

function openMusicTagModal() {
    const modal = new bootstrap.Modal(document.getElementById('musicTagModal'));
    renderMusicTagList();
    modal.show();
}

function addMusicTag() {
    const keyInput = document.getElementById('music_tag_key');
    const valueInput = document.getElementById('music_tag_value');
    const key = keyInput.value.trim();
    const value = valueInput.value.trim();
    if (!key || !value) {
        showToast('Error', 'Tag key and value are required.');
        return;
    }
    musicState.pendingTags[key] = value;
    keyInput.value = '';
    valueInput.value = '';
    renderMusicTagList();
    document.getElementById('music_track_tags').value = formatTags(musicState.pendingTags);
}

function handleMusicTagListClick(event) {
    const button = event.target.closest('button[data-remove-tag]');
    if (!button) {
        return;
    }
    const key = button.getAttribute('data-remove-tag');
    delete musicState.pendingTags[key];
    renderMusicTagList();
    document.getElementById('music_track_tags').value = formatTags(musicState.pendingTags);
}

function renderMusicTagList() {
    const list = document.getElementById('music_tag_list');
    if (!list) {
        return;
    }
    const entries = Object.entries(musicState.pendingTags || {});
    if (!entries.length) {
        list.innerHTML = '<li class="list-group-item text-muted">No tags</li>';
        return;
    }
    list.innerHTML = '';
    entries.forEach(([key, value]) => {
        const item = document.createElement('li');
        item.className = 'list-group-item d-flex justify-content-between align-items-center';
        item.innerHTML = `
            <span><strong>${escapeHtml(key)}</strong>: ${escapeHtml(value)}</span>
            <button class="btn btn-sm btn-outline-danger" type="button" data-remove-tag="${escapeHtml(key)}">
                <i class="bi bi-x"></i>
            </button>
        `;
        list.appendChild(item);
    });
}

function parseGenresInput(value) {
    return value
        .split(';')
        .map(v => v.trim())
        .filter(Boolean);
}

function parseTagInput(value) {
    const tags = {};
    value
        .split(';')
        .map(v => v.trim())
        .filter(Boolean)
        .forEach(entry => {
            const [key, ...rest] = entry.split('=');
            if (!key || !rest.length) {
                return;
            }
            const tagValue = rest.join('=').trim();
            if (tagValue) {
                tags[key.trim()] = tagValue;
            }
        });
    return tags;
}

function formatTags(tags) {
    return Object.entries(tags || {})
        .map(([key, value]) => `${key}=${value}`)
        .join('; ');
}

function serializeMusicTrack(track, index) {
    return {
        title: track.title || `Track ${index + 1}`,
        artist: track.artist || '',
        album: track.album || '',
        track_number: toOptionalNumber(track.track_number) || index + 1,
        disc_number: toOptionalNumber(track.disc_number) || 1,
        duration: toOptionalNumber(track.duration),
        genres: Array.isArray(track.genres) ? track.genres : [],
        tags: track.tags || {},
        year: track.year || '',
        notes: track.notes || '',
        source_url: track.source_url || '',
        thumbnail: track.thumbnail || '',
    };
}

function normalizeMusicEntry(entry, index, fallbackAlbum) {
    return {
        title: entry.title || `Track ${index}`,
        artist: entry.artist || entry.channel || entry.uploader || '',
        album: entry.album || fallbackAlbum || '',
        track_number: entry.track_number || index,
        disc_number: entry.disc_number || 1,
        duration: entry.duration || null,
        genres: [],
        tags: {},
        year: entry.release_year || '',
        source_url: entry.webpage_url || entry.url || '',
        thumbnail: entry.thumbnail || '',
    };
}

function postMusicJob(payload, onSuccess) {
    return fetch('/music/jobs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    })
        .then(r => r.json())
        .then(data => {
            if (data.job_id) {
                showToast('Success', 'Music job queued');
                startMusicJobPolling(data.job_id);
                if (typeof onSuccess === 'function') {
                    onSuccess(data.job_id);
                }
                const jobsLink = document.querySelector('[data-section="jobs"]');
                if (jobsLink) {
                    jobsLink.click();
                }
            } else {
                showToast('Error', data.error || 'Failed to queue music job');
            }
            return data;
        })
        .catch(() => {
            showToast('Error', 'Failed to queue music job');
        })
        .finally(() => {
            updateJobsData();
        });
}

function toggleButtonLoading(button, loading, text = 'Loading...') {
    if (!button) {
        return;
    }
    if (loading) {
        if (!button.dataset.originalText) {
            button.dataset.originalText = button.innerHTML;
        }
        button.disabled = true;
        button.innerHTML = `<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> ${text}`;
    } else {
        button.disabled = false;
        if (button.dataset.originalText) {
            button.innerHTML = button.dataset.originalText;
            delete button.dataset.originalText;
        }
    }
}

function toOptionalNumber(value) {
    if (value === null || value === undefined) {
        return null;
    }
    const trimmed = value.toString().trim();
    if (!trimmed) {
        return null;
    }
    const parsed = parseInt(trimmed, 10);
    return Number.isFinite(parsed) ? parsed : null;
}

function showJobDetails(jobId) {
    fetch(`/jobs/${jobId}`)
        .then(response => response.json())
        .then(job => {
            const modal = document.getElementById('jobDetailModal');
            modal.setAttribute('data-job-id', jobId);
            
            updateJobDetailModal(job);
            
            const modalObj = new bootstrap.Modal(modal);
            modalObj.show();
        })
        .catch(error => {
            console.error('Error fetching job details:', error);
            showToast('Error', 'Failed to load job details');
        });
}

function updateJobDetailModal(job) {
    document.getElementById('detail-show-name').textContent = job.show_name;
    document.getElementById('detail-season').textContent = job.season_num;
    document.getElementById('detail-episode-start').textContent = job.episode_start;
    document.getElementById('detail-movie-name').textContent = job.movie_name || '';

    const movieField = document.getElementById('detail-movie-field');
    const showField = document.getElementById('detail-show-name').parentElement;
    const seasonField = document.getElementById('detail-season').parentElement;
    const episodeField = document.getElementById('detail-episode-start').parentElement;

    if (job.media_type === 'movie') {
        movieField.style.display = 'block';
        showField.style.display = 'none';
        seasonField.style.display = 'none';
        episodeField.style.display = 'none';
    } else {
        movieField.style.display = 'none';
        showField.style.display = 'block';
        seasonField.style.display = 'block';
        episodeField.style.display = 'block';
    }
    
    const statusBadge = document.getElementById('detail-status');
    statusBadge.textContent = job.status;
    statusBadge.className = 'badge ' + getStatusBadgeClass(job.status);
    
    document.getElementById('detail-created').textContent = formatDate(job.created_at);
    document.getElementById('detail-updated').textContent = formatDate(job.updated_at);
    
    const urlElem = document.getElementById('detail-url');
    urlElem.textContent = job.playlist_url;
    urlElem.href = job.playlist_url;
    
    // Update detailed status elements
    const stageIcons = {
        'waiting': 'bi-hourglass',
        'downloading': 'bi-cloud-download',
        'processing_metadata': 'bi-file-earmark-text',
        'converting': 'bi-film',
        'generating_artwork': 'bi-images',
        'creating_nfo': 'bi-filetype-xml',
        'completed': 'bi-check-circle',
        'failed': 'bi-exclamation-triangle'
    };
    
    const stageNames = {
        'waiting': 'Waiting',
        'downloading': 'Downloading',
        'processing_metadata': 'Processing Metadata',
        'converting': 'Converting Video',
        'generating_artwork': 'Generating Artwork',
        'creating_nfo': 'Creating NFO Files',
        'completed': 'Completed',
        'failed': 'Failed'
    };
    
    // Set stage icon
    const stageIcon = document.getElementById('detail-stage-icon');
    const iconClass = stageIcons[job.current_stage] || 'bi-arrow-repeat';
    stageIcon.innerHTML = `<i class="bi ${iconClass}"></i>`;
    
    // Set stage name
    const stageName = document.getElementById('detail-stage-name');
    stageName.textContent = stageNames[job.current_stage] || 'Processing';
    
    // Set status text
    const statusText = document.getElementById('detail-status-text');
    statusText.textContent = job.detailed_status || 'Working on files...';
    
    // Set file progress
    document.getElementById('detail-file-progress').textContent = job.processed_files || 0;
    document.getElementById('detail-file-total').textContent = job.total_files || 0;
    
    // Set current file
    document.getElementById('detail-current-file').textContent = job.current_file || '';

    // Show remaining queue
    const queueEl = document.getElementById('detail-queue');
    if (job.remaining_files && job.remaining_files.length > 0) {
        queueEl.textContent = 'Next: ' + job.remaining_files.join(', ');
    } else {
        queueEl.textContent = '';
    }
    
    // Update progress bars
    const mainProgressBar = document.getElementById('detail-progress-bar');
    mainProgressBar.style.width = `${job.progress}%`;
    mainProgressBar.textContent = `${Math.round(job.progress)}%`;
    
    const stageProgressBar = document.getElementById('detail-stage-progress-bar');
    stageProgressBar.style.width = `${job.stage_progress}%`;
    stageProgressBar.textContent = `${Math.round(job.stage_progress)}%`;
    
    // Update alert color based on status
    const alertElement = document.querySelector('.alert');
    
    // Remove existing status classes
    alertElement.classList.remove('alert-info', 'alert-success', 'alert-warning', 'alert-danger');
    
    // Add appropriate class based on job status
    if (job.status === 'completed') {
        alertElement.classList.add('alert-success');
    } else if (job.status === 'failed') {
        alertElement.classList.add('alert-danger');
    } else if (job.status === 'queued') {
        alertElement.classList.add('alert-warning');
    } else {
        alertElement.classList.add('alert-info');
    }
    
    // Update log messages
    const logContainer = document.getElementById('detail-log');
    logContainer.innerHTML = '';
    
    job.messages.forEach(msg => {
        logContainer.innerHTML += `<div>[${msg.time}] ${msg.text}</div>`;
    });
    
    // Scroll to bottom of log
    logContainer.scrollTop = logContainer.scrollHeight;

    // Toggle cancel button visibility
    const cancelBtn = document.getElementById('cancel-job-btn');
    if (cancelBtn) {
        if (['completed', 'failed', 'cancelled'].includes(job.status)) {
            cancelBtn.style.display = 'none';
        } else {
            cancelBtn.style.display = 'inline-block';
            cancelBtn.onclick = function() {
                if (confirm('Cancel this job?')) {
                    fetch(`/jobs/${job.job_id}`, { method: 'DELETE' })
                        .then(r => {
                            if (r.ok) {
                                showToast('Success', 'Job cancelled');
                                updateJobsData();
                                const modalEl = document.getElementById('jobDetailModal');
                                const modalObj = bootstrap.Modal.getInstance(modalEl);
                                modalObj.hide();
                            } else {
                                r.json().then(d => showToast('Error', d.error || 'Failed to cancel job'));
                            }
                        })
                        .catch(() => showToast('Error', 'Failed to cancel job'));
                }
            };
        }
    }
}

function getMediaTypeMeta(job) {
    if (job.media_type === 'movie') {
        return { icon: 'bi-film', title: job.movie_name || 'Movie job' };
    }
    if (job.media_type === 'music') {
        const request = job.music_request || {};
        const collection = request.collection || {};
        const title = request.display_name || collection.title || job.show_name || 'Music job';
        return { icon: 'bi-music-note-beamed', title };
    }
    return { icon: 'bi-tv', title: job.show_name || 'TV job' };
}

function buildJobSubtitle(job) {
    if (job.media_type === 'music') {
        const request = job.music_request || {};
        const typeLabel = (request.job_type || 'music').replace(/_/g, ' ');
        const tracks = Array.isArray(request.tracks)
            ? request.tracks.length
            : job.remaining_files
            ? job.remaining_files.length
            : 0;
        return `${typeLabel} • ${tracks} track${tracks === 1 ? '' : 's'}`;
    }
    if (job.media_type === 'movie') {
        return 'Movie download';
    }
    return `Season ${job.season_num || ''}`.trim();
}

function formatDuration(seconds) {
    const value = Number(seconds);
    if (!Number.isFinite(value) || value <= 0) {
        return '—';
    }
    const mins = Math.floor(value / 60);
    const secs = Math.round(value % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
}

function startMusicJobPolling(jobId) {
    if (musicJobPollers.has(jobId)) {
        return;
    }
    const timer = setInterval(() => {
        fetch(`/music/jobs/${jobId}`)
            .then(r => r.json())
            .then(job => {
                if (job.error) {
                    stopMusicJobPolling(jobId);
                    return;
                }
                updateJobsData();
                if (['completed', 'failed', 'cancelled'].includes(job.status)) {
                    stopMusicJobPolling(jobId);
                }
            })
            .catch(() => {
                stopMusicJobPolling(jobId);
            });
    }, 5000);
    musicJobPollers.set(jobId, timer);
}

function stopMusicJobPolling(jobId) {
    const timer = musicJobPollers.get(jobId);
    if (timer) {
        clearInterval(timer);
        musicJobPollers.delete(jobId);
    }
}

function loadSettings() {
    fetch('/config')
        .then(response => response.json())
        .then(config => {
            // Populate settings form with current values
            document.getElementById('output_dir').value = config.output_dir || '';
            document.getElementById('default_quality').value = config.quality || '1080';
            document.getElementById('default_use_h265').checked = config.use_h265 !== false;
            const useH265Elem = document.getElementById('default_use_h265');
            document.getElementById('clean_filenames').checked = config.clean_filenames !== false;
            document.getElementById('default_crf').value = config.crf || 28;
            document.getElementById('default-crf-value').textContent = config.crf || 28;
            document.getElementById('web_port').value = config.web_port || 8000;
            document.getElementById('completed_jobs_limit').value = config.completed_jobs_limit || 10;
            document.getElementById('max_concurrent_jobs').value = config.max_concurrent_jobs || 1;
            document.getElementById('max-concurrent-value').textContent = config.max_concurrent_jobs || 1;
            document.getElementById('auto_check_updates').checked = config.update_checker_enabled === true;
            document.getElementById('update_interval').value = config.update_checker_interval || 60;
            
            // Cookies file settings
            const cookiesInput = document.getElementById('cookies_path');
            cookiesInput.value = config.cookies_path || config.cookies || '';
            
            // Add indication if cookies file was specified but not found
            const cookiesPathExists = !!config.cookies;
            const cookiesPathSpecified = !!config.cookies_path;
            
            if (cookiesPathSpecified && !cookiesPathExists) {
                cookiesInput.classList.add('is-invalid');
                // Check if feedback element already exists
                let feedbackEl = cookiesInput.parentNode.querySelector('.invalid-feedback');
                if (!feedbackEl) {
                    feedbackEl = document.createElement('div');
                    feedbackEl.className = 'invalid-feedback';
                    cookiesInput.parentNode.appendChild(feedbackEl);
                }
                feedbackEl.textContent = 'Cookies file not found at this location';
            } else {
                cookiesInput.classList.remove('is-invalid');
                const feedbackEl = cookiesInput.parentNode.querySelector('.invalid-feedback');
                if (feedbackEl) {
                    feedbackEl.remove();
                }
            }
            
            // Jellyfin settings
            const jellyfinEnabled = document.getElementById('jellyfin_enabled');
            jellyfinEnabled.checked = config.jellyfin_enabled === true;
            document.getElementById('jellyfin_tv_path').value = config.jellyfin_tv_path || '';
            document.getElementById('jellyfin_host').value = config.jellyfin_host || '';
            document.getElementById('jellyfin_port').value = config.jellyfin_port || '8096';
            document.getElementById('jellyfin_api_key').value = config.jellyfin_api_key || '';

            // IMDb settings
            const imdbEnabled = document.getElementById('imdb_enabled');
            imdbEnabled.checked = config.imdb_enabled === true;
            document.getElementById('imdb_api_key').value = config.imdb_api_key || '';

            // Trigger the toggle to show/hide Jellyfin settings
            if (jellyfinEnabled) {
                const event = new Event('change');
                jellyfinEnabled.dispatchEvent(event);
            }
            if (imdbEnabled) {
                const e2 = new Event('change');
                imdbEnabled.dispatchEvent(e2);
            }
            if (autoCheck) {
                const ev2 = new Event('change');
                autoCheck.dispatchEvent(ev2);
            }
            if (useH265Elem) {
                const ev3 = new Event('change');
                useH265Elem.dispatchEvent(ev3);
            }
        })
        .catch(error => {
            console.error('Error fetching config:', error);
        });
}

function updateDashboardStats(jobs) {
    const activeJobs = jobs.filter(job => !['completed', 'failed'].includes(job.status)).length;
    document.getElementById('active-jobs').textContent = activeJobs;
}

function updateMediaStats(media) {
    let totalShows = 0;
    let totalEpisodes = 0;
    let totalSize = 0;
    
    media.forEach(show => {
        totalShows++;
        show.seasons.forEach(season => {
            totalEpisodes += season.episodes.length;
            season.episodes.forEach(ep => {
                totalSize += ep.size;
            });
        });
    });
    
    document.getElementById('total-shows').textContent = totalShows;
    document.getElementById('total-episodes').textContent = totalEpisodes;
    document.getElementById('storage-used').textContent = formatFileSize(totalSize);
}

function updateMovieStats(movies) {
    const totalMovies = movies.length;
    document.getElementById('total-movies').textContent = totalMovies;
}

function updateRecentJobs(jobs) {
    const container = document.getElementById('recent-activity-jobs');
    if (!container) return;

    container.innerHTML = '';

    if (!jobs || jobs.length === 0) {
        container.innerHTML = '<p class="text-gray-400 text-center py-3">No jobs found</p>';
        return;
    }

    const sortedJobs = [...jobs].sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
    const recentJobs = sortedJobs.slice(0, 5);

    recentJobs.forEach(job => {
        const statusClass = getStatusBadgeClass(job.status);
        const { icon, title } = getMediaTypeMeta(job);
        const subtitle = buildJobSubtitle(job);
        const item = document.createElement('div');
        item.className = 'activity-item';
        item.innerHTML = `
            <div class="activity-icon">
                <i class="bi ${icon}"></i>
            </div>
            <div class="flex-1">
                <p class="item-title">${escapeHtml(title)}</p>
                <p class="item-subtitle">${escapeHtml(subtitle)}</p>
            </div>
            <div class="text-end">
                <span class="badge ${statusClass}">${escapeHtml(job.status)}</span>
                <p class="item-meta mt-1">${formatDate(job.created_at)}</p>
            </div>
        `;
        container.appendChild(item);
    });
}

// Utility functions
function getStatusBadgeClass(status) {
    const statusMap = {
        'completed': 'badge-completed',
        'queued': 'badge-queued',
        'failed': 'badge-failed',
        'in_progress': 'badge-in_progress',
        'downloading': 'badge-downloading',
        'converting': 'badge-converting',
        'processing_metadata': 'badge-processing_metadata',
        'generating_artwork': 'badge-generating_artwork',
        'creating_nfo': 'badge-creating_nfo'
    };
    
    return statusMap[status] || 'bg-secondary';
}

function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleString();
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function showToast(title, message) {
    const toastEl = document.getElementById('liveToast');
    document.getElementById('toast-title').textContent = title;
    document.getElementById('toast-message').textContent = message;
    
    const toast = new bootstrap.Toast(toastEl);
    toast.show();
}