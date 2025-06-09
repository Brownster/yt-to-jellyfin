// Tubarr Frontend Script

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
                section.classList.add('d-none');
                if (section.id === sectionId) {
                    section.classList.remove('d-none');
                }
            });
            
            // Load data when navigating to certain sections
            if (sectionId === 'jobs') {
                loadJobs();
            } else if (sectionId === 'history') {
                loadHistory();
            } else if (sectionId === 'media') {
                loadMedia();
            } else if (sectionId === 'playlists') {
                loadPlaylists();
            } else if (sectionId === 'settings') {
                loadSettings();
            } else if (sectionId === 'dashboard') {
                loadDashboard();
            }
        });
    });
    
    // CRF sliders
    const crfSlider = document.getElementById('crf');
    const crfValue = document.getElementById('crf-value');
    if (crfSlider && crfValue) {
        crfSlider.addEventListener('input', function() {
            crfValue.textContent = this.value;
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
    
    // Settings Form Submission
    const settingsForm = document.getElementById('settings-form');
    if (settingsForm) {
        // Toggle Jellyfin settings visibility based on enabled state
        const jellyfinEnabled = document.getElementById('jellyfin_enabled');
        const jellyfinSettings = document.querySelectorAll('.jellyfin-settings');
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
        toggleUpdateSchedule();
        toggleConcurrency();

        // Add event listener for toggle
        jellyfinEnabled.addEventListener('change', toggleJellyfinSettings);
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
                jellyfin_api_key: document.getElementById('jellyfin_api_key').value
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
    
    // Refresh Media button
    const refreshMediaBtn = document.getElementById('refresh-media');
    if (refreshMediaBtn) {
        refreshMediaBtn.addEventListener('click', function() {
            loadMedia();
        });
    }

    const checkPlaylistsBtn = document.getElementById('check-playlists');
    if (checkPlaylistsBtn) {
        checkPlaylistsBtn.addEventListener('click', function() {
            fetch('/playlists/check', {method: 'POST'})
                .then(r => r.json())
                .then(data => {
                    if (data.created_jobs && data.created_jobs.length > 0) {
                        showToast('Updates', `Created ${data.created_jobs.length} jobs`);
                        loadJobs();
                    } else {
                        showToast('Info', 'No updates found');
                    }
                })
                .catch(() => showToast('Error', 'Failed to check playlists'));
        });
    }
    
    // Load dashboard data by default
    loadDashboard();
    
    // Setup polling for active jobs
    setInterval(function() {
        if (document.querySelector('#jobs:not(.d-none)') ||
            document.querySelector('#dashboard:not(.d-none)') ||
            document.querySelector('#history:not(.d-none)')) {
            updateJobsData();
        }
        if (document.querySelector('#playlists:not(.d-none)')) {
            loadPlaylists();
        }
    }, 5000);
});

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
    
    // Load media data
    fetch('/media')
        .then(response => response.json())
        .then(media => {
            updateMediaStats(media);
            updateRecentMedia(media);
        })
        .catch(error => {
            console.error('Error fetching media:', error);
        });

    // Load movie data
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
            const tvJobs = jobs.filter(j => j.media_type !== 'movie');
            const movieJobs = jobs.filter(j => j.media_type === 'movie');
            updateJobsTable(tvJobs);
            updateMovieJobsTable(movieJobs);
        })
        .catch(error => {
            console.error('Error fetching jobs:', error);
        });
}

function updateJobsData() {
    fetch('/jobs')
        .then(response => response.json())
        .then(jobs => {
            const tvJobs = jobs.filter(j => j.media_type !== 'movie');
            const movieJobs = jobs.filter(j => j.media_type === 'movie');
            if (document.querySelector('#jobs:not(.d-none)')) {
                updateJobsTable(tvJobs);
                updateMovieJobsTable(movieJobs);
            }
            if (document.querySelector('#dashboard:not(.d-none)')) {
                updateDashboardStats(jobs);
                updateRecentJobs(jobs);
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

function loadHistory() {
    fetch('/history')
        .then(response => response.json())
        .then(jobs => {
            const tvJobs = jobs.filter(j => j.media_type !== 'movie');
            const movieJobs = jobs.filter(j => j.media_type === 'movie');
            updateHistoryTable(tvJobs);
            updateMovieHistoryTable(movieJobs);
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

function loadMedia() {
    Promise.all([
        fetch('/media').then(r => r.json()),
        fetch('/movies').then(r => r.json())
    ])
        .then(([media, movies]) => {
            displayMediaLibrary(media, movies);
        })
        .catch(error => {
            console.error('Error fetching media:', error);
        });
}

function displayMediaLibrary(media, movies) {
    const tvContainer = document.getElementById('media-tv-container');
    tvContainer.innerHTML = '';

    if (media.length === 0) {
        tvContainer.innerHTML = '<div class="alert alert-info">No TV shows found in library</div>';
    } else {
        const row = document.createElement('div');
        row.className = 'row';

        media.forEach(show => {
            const showId = show.name.replace(/[^a-zA-Z0-9]/g, '_');
            const totalEpisodes = show.episode_count || 0;
            const posterUrl = show.poster ? `/media_files/${encodeURIComponent(show.poster)}` : null;

            const col = document.createElement('div');
            col.className = 'col-sm-6 col-md-4 col-lg-3 mb-4';
            col.innerHTML = `
                <div class="card h-100 show-card" data-show-id="${showId}">
                    <div class="show-poster-container position-relative">
                        ${posterUrl ? `<img src="${posterUrl}" class="show-poster" alt="${show.name}">` : `<div class="show-poster bg-secondary d-flex align-items-center justify-content-center"><i class="bi bi-tv text-white" style="font-size: 3rem;"></i></div>`}
                        <span class="badge bg-primary position-absolute top-0 end-0 m-2">${totalEpisodes}</span>
                    </div>
                    <div class="card-body text-center">
                        <h5 class="card-title">${show.name}</h5>
                    </div>
                </div>`;

            const seasonsRow = document.createElement('div');
            seasonsRow.className = 'col-12 d-none';
            seasonsRow.id = `show-seasons-${showId}`;
            seasonsRow.innerHTML = `<div class="row mt-2">${show.seasons.map(season => createSeasonCard(season)).join('')}</div>`;
            row.appendChild(col);
            row.appendChild(seasonsRow);
        });

        tvContainer.appendChild(row);
    }

    const movieContainer = document.getElementById('media-movie-container');
    movieContainer.innerHTML = '';

    if (movies.length === 0) {
        movieContainer.innerHTML = '<div class="alert alert-info">No movies found in library</div>';
    } else {
        const movieRow = document.createElement('div');
        movieRow.className = 'row';
        movies.forEach(movie => {
            movieRow.innerHTML += createMovieCard(movie);
        });
        movieContainer.appendChild(movieRow);
    }

    document.querySelectorAll('.show-card').forEach(card => {
        card.addEventListener('click', function() {
            const showId = this.getAttribute('data-show-id');
            const seasonsContainer = document.getElementById(`show-seasons-${showId}`);
            if (seasonsContainer) {
                seasonsContainer.classList.toggle('d-none');
            }
        });
    });

    document.querySelectorAll('.season-card').forEach(card => {
        card.addEventListener('click', function() {
            const seasonId = this.getAttribute('data-season-id');
            const episodeContainer = document.getElementById(`episode-container-${seasonId}`);

            if (episodeContainer.classList.contains('d-none')) {
                episodeContainer.classList.remove('d-none');
                this.querySelector('.toggle-icon').classList.replace('bi-plus', 'bi-dash');
            } else {
                episodeContainer.classList.add('d-none');
                this.querySelector('.toggle-icon').classList.replace('bi-dash', 'bi-plus');
            }
        });
    });
}

function createSeasonCard(season) {
    const seasonId = season.name.replace(/[^a-zA-Z0-9]/g, '_');
    const episodeCount = season.episodes.length;
    const posterUrl = season.poster ? `/media_files/${encodeURIComponent(season.poster)}` : null;

    return `
        <div class="col-md-6 col-lg-4 mb-4">
            <div class="card media-card">
                <div class="season-poster-container">
                    ${posterUrl ? `<img src="${posterUrl}" class="season-poster" alt="${season.name}">` : `<div class="season-poster bg-secondary d-flex align-items-center justify-content-center"><i class="bi bi-film text-white" style="font-size: 3rem;"></i></div>`}
                </div>
                <div class="card-body">
                    <h5 class="card-title">${season.name}</h5>
                    <p class="card-text">${episodeCount} Episodes</p>
                    <div class="d-grid">
                        <button class="btn btn-outline-primary season-card" data-season-id="${seasonId}">
                            <i class="bi bi-plus toggle-icon"></i> Episode List
                        </button>
                    </div>
                </div>
                <div id="episode-container-${seasonId}" class="d-none">
                    <div class="episode-table-container">
                        <table class="table table-sm">
                            <thead>
                                <tr>
                                    <th>#</th>
                                    <th>Episode</th>
                                    <th>Size</th>
                                    <th>Modified</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${season.episodes.map(ep => createEpisodeRow(ep)).join('')}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    `;
}

function createEpisodeRow(episode) {
    const size = formatFileSize(episode.size);

    return `
        <tr>
            <td>${episode.episode_num !== null && episode.episode_num !== undefined ? episode.episode_num : ''}</td>
            <td>${episode.name}</td>
            <td>${size}</td>
            <td>${formatDate(episode.modified)}</td>
        </tr>
    `;
}

function createMovieCard(movie) {
    const posterUrl = movie.poster ? `/media_files/${encodeURIComponent(movie.poster)}` : null;
    const size = formatFileSize(movie.size);

    return `
        <div class="col-sm-6 col-md-4 col-lg-3 mb-4">
            <div class="card movie-card h-100">
                <div class="season-poster-container">
                    ${posterUrl ? `<img src="${posterUrl}" class="season-poster" alt="${movie.name}">` : `<div class="season-poster bg-secondary d-flex align-items-center justify-content-center"><i class="bi bi-film text-white" style="font-size: 3rem;"></i></div>`}
                </div>
                <div class="card-body">
                    <h5 class="card-title">${movie.name}</h5>
                    <p class="card-text">${size}<br>${formatDate(movie.modified)}</p>
                </div>
            </div>
        </div>
    `;
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
            
            // Trigger the toggle to show/hide Jellyfin settings
            if (jellyfinEnabled) {
                const event = new Event('change');
                jellyfinEnabled.dispatchEvent(event);
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
    const recentJobsTable = document.getElementById('recent-jobs-table').querySelector('tbody');
    recentJobsTable.innerHTML = '';
    
    if (jobs.length === 0) {
        const row = document.createElement('tr');
        row.innerHTML = '<td colspan="4" class="text-center">No jobs found</td>';
        recentJobsTable.appendChild(row);
        return;
    }
    
    // Sort jobs by creation date, newest first
    jobs.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
    
    // Take only first 5
    const recentJobs = jobs.slice(0, 5);
    
    recentJobs.forEach(job => {
        const row = document.createElement('tr');
        
        // Status badge
        const statusClass = getStatusBadgeClass(job.status);
        
        row.innerHTML = `
            <td>${job.show_name}</td>
            <td>${job.season_num}</td>
            <td><span class="badge ${statusClass}">${job.status}</span></td>
            <td>${formatDate(job.created_at)}</td>
        `;
        
        recentJobsTable.appendChild(row);
    });
}

function updateRecentMedia(media) {
    const recentMediaTable = document.getElementById('recent-media-table').querySelector('tbody');
    recentMediaTable.innerHTML = '';
    
    if (media.length === 0) {
        const row = document.createElement('tr');
        row.innerHTML = '<td colspan="4" class="text-center">No media found</td>';
        recentMediaTable.appendChild(row);
        return;
    }
    
    // Flatten all seasons
    let allSeasons = [];
    media.forEach(show => {
        show.seasons.forEach(season => {
            allSeasons.push({
                show: show.name,
                ...season
            });
        });
    });
    
    // Sort by latest modified episode
    allSeasons.sort((a, b) => {
        const aLatest = a.episodes.length > 0 ? 
            Math.max(...a.episodes.map(e => new Date(e.modified).getTime())) : 0;
        const bLatest = b.episodes.length > 0 ? 
            Math.max(...b.episodes.map(e => new Date(e.modified).getTime())) : 0;
        return bLatest - aLatest;
    });
    
    // Take only first 5
    const recentSeasons = allSeasons.slice(0, 5);
    
    recentSeasons.forEach(season => {
        const row = document.createElement('tr');
        
        // Find latest episode modified date
        const latestDate = season.episodes.length > 0 ?
            Math.max(...season.episodes.map(e => new Date(e.modified).getTime())) : 0;
        
        row.innerHTML = `
            <td>${season.show}</td>
            <td>${season.name}</td>
            <td>${season.episodes.length}</td>
            <td>${latestDate ? formatDate(new Date(latestDate).toISOString()) : 'N/A'}</td>
        `;
        
        recentMediaTable.appendChild(row);
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