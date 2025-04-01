// YT-to-Jellyfin Frontend Script

document.addEventListener('DOMContentLoaded', function() {
    // Initialize Bootstrap components
    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    const tooltipList = [...tooltipTriggerList].map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));
    
    // Navigation handling
    const navLinks = document.querySelectorAll('.nav-link');
    const contentSections = document.querySelectorAll('.content-section');
    
    navLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const sectionId = this.getAttribute('data-section');
            
            // Update navigation active state
            navLinks.forEach(navLink => navLink.classList.remove('active'));
            this.classList.add('active');
            
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
            } else if (sectionId === 'media') {
                loadMedia();
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
    
    // New Job Form Submission
    const newJobForm = document.getElementById('new-job-form');
    if (newJobForm) {
        newJobForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const formData = new FormData();
            formData.append('playlist_url', document.getElementById('playlist_url').value);
            formData.append('show_name', document.getElementById('show_name').value);
            formData.append('season_num', document.getElementById('season_num').value);
            formData.append('episode_start', document.getElementById('episode_start').value);
            
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
            });
        });
    }
    
    // Settings Form Submission
    const settingsForm = document.getElementById('settings-form');
    if (settingsForm) {
        // Toggle Jellyfin settings visibility based on enabled state
        const jellyfinEnabled = document.getElementById('jellyfin_enabled');
        const jellyfinSettings = document.querySelectorAll('.jellyfin-settings');
        
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
        
        // Set initial state
        toggleJellyfinSettings();
        
        // Add event listener for toggle
        jellyfinEnabled.addEventListener('change', toggleJellyfinSettings);
        
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
    
    // Load dashboard data by default
    loadDashboard();
    
    // Setup polling for active jobs
    setInterval(function() {
        if (document.querySelector('#jobs:not(.d-none)') || document.querySelector('#dashboard:not(.d-none)')) {
            updateJobsData();
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
}

function loadJobs() {
    fetch('/jobs')
        .then(response => response.json())
        .then(jobs => {
            updateJobsTable(jobs);
        })
        .catch(error => {
            console.error('Error fetching jobs:', error);
        });
}

function updateJobsData() {
    fetch('/jobs')
        .then(response => response.json())
        .then(jobs => {
            if (document.querySelector('#jobs:not(.d-none)')) {
                updateJobsTable(jobs);
            }
            if (document.querySelector('#dashboard:not(.d-none)')) {
                updateDashboardStats(jobs);
                updateRecentJobs(jobs);
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
}

function loadMedia() {
    fetch('/media')
        .then(response => response.json())
        .then(media => {
            displayMediaLibrary(media);
        })
        .catch(error => {
            console.error('Error fetching media:', error);
        });
}

function displayMediaLibrary(media) {
    const mediaContainer = document.getElementById('media-container');
    mediaContainer.innerHTML = '';
    
    if (media.length === 0) {
        mediaContainer.innerHTML = '<div class="alert alert-info">No media found in library</div>';
        return;
    }
    
    media.forEach(show => {
        const showCard = document.createElement('div');
        showCard.className = 'card shadow mb-4';
        
        showCard.innerHTML = `
            <div class="card-header py-3 d-flex justify-content-between align-items-center">
                <h6 class="m-0 font-weight-bold">${show.name}</h6>
                <span class="badge bg-secondary">${show.seasons.length} Seasons</span>
            </div>
            <div class="card-body">
                <div class="row seasons-container-${show.name.replace(/[^a-zA-Z0-9]/g, '_')}">
                    ${show.seasons.map(season => createSeasonCard(season)).join('')}
                </div>
            </div>
        `;
        
        mediaContainer.appendChild(showCard);
    });
    
    // Add click handlers for season cards
    document.querySelectorAll('.season-card').forEach(card => {
        card.addEventListener('click', function() {
            const seasonId = this.getAttribute('data-season-id');
            const episodeContainer = document.getElementById(`episode-container-${seasonId}`);
            
            // Toggle visibility
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
    
    return `
        <div class="col-md-6 col-lg-4 mb-4">
            <div class="card media-card">
                <div class="season-poster-container">
                    <div class="season-poster bg-secondary d-flex align-items-center justify-content-center">
                        <i class="bi bi-film text-white" style="font-size: 3rem;"></i>
                    </div>
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
            <td>${episode.name}</td>
            <td>${size}</td>
            <td>${formatDate(episode.modified)}</td>
        </tr>
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
            document.getElementById('clean_filenames').checked = config.clean_filenames !== false;
            document.getElementById('default_crf').value = config.crf || 28;
            document.getElementById('default-crf-value').textContent = config.crf || 28;
            document.getElementById('web_port').value = config.web_port || 8000;
            document.getElementById('completed_jobs_limit').value = config.completed_jobs_limit || 10;
            
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