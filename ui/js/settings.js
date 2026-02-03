/**
 * LifeOS Dashboard - Settings Modal
 */

import { CONFIG, settingsState } from './config.js';
import { showToast } from './utils.js';

// Track active backfill polling
let backfillPollInterval = null;

/**
 * Setup all settings-related event listeners
 */
export function setupSettingsListeners() {
    const settingsBtn = document.getElementById('settingsBtn');
    if (!settingsBtn) return; // Settings button not in DOM yet

    settingsBtn.addEventListener('click', openSettings);

    document.getElementById('closeSettings').addEventListener('click', closeSettings);
    document.getElementById('cancelSettings').addEventListener('click', closeSettings);
    document.getElementById('settingsModal').addEventListener('click', (e) => {
        if (e.target.id === 'settingsModal') closeSettings();
    });

    document.getElementById('saveSettings').addEventListener('click', saveSettings);

    document.getElementById('quietHoursEnabled').addEventListener('change', (e) => {
        const range = document.getElementById('quietHoursRange');
        range.style.opacity = e.target.checked ? '1' : '0.5';
        range.style.pointerEvents = e.target.checked ? 'auto' : 'none';
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && document.getElementById('settingsModal').classList.contains('visible')) {
            closeSettings();
        }
    });

    // Backfill buttons
    const backfillOuraBtn = document.getElementById('backfillOuraBtn');
    const backfillCalendarBtn = document.getElementById('backfillCalendarBtn');

    if (backfillOuraBtn) {
        backfillOuraBtn.addEventListener('click', () => startBackfill('oura'));
    }
    if (backfillCalendarBtn) {
        backfillCalendarBtn.addEventListener('click', () => startBackfill('calendar'));
    }
}

/**
 * Open the settings modal
 */
export async function openSettings() {
    const modal = document.getElementById('settingsModal');

    try {
        const [settingsRes, timezonesRes] = await Promise.all([
            fetch(`${CONFIG.API_BASE}/settings`),
            fetch(`${CONFIG.API_BASE}/settings/timezones`)
        ]);

        if (!settingsRes.ok) throw new Error('Failed to load settings');

        const settings = await settingsRes.json();
        const tzData = timezonesRes.ok ? await timezonesRes.json() : { timezones: ['UTC'] };

        settingsState.original = settings;
        settingsState.current = JSON.parse(JSON.stringify(settings));
        settingsState.timezones = tzData.timezones;

        populateSettingsForm(settings, tzData.timezones);
    } catch (error) {
        console.error('Failed to load settings:', error);
        populateSettingsForm({
            user_name: 'User',
            timezone: 'UTC',
            notifications: {
                quiet_hours_enabled: true,
                quiet_hours_start: '23:00',
                quiet_hours_end: '08:00'
            },
            integrations: {
                oura_configured: false,
                ai_configured: false,
                telegram_configured: false,
                discord_configured: false
            },
            ai_model: 'gpt-4o-mini'
        }, ['UTC']);
    }

    modal.classList.add('visible');
    document.body.style.overflow = 'hidden';

    // Load token stats in background
    loadTokenStats();

    // Load backfill status
    loadBackfillStatus();
}

/**
 * Load and display token usage stats
 */
async function loadTokenStats() {
    try {
        const res = await fetch(`${CONFIG.API_BASE}/stats/summary`);
        if (!res.ok) {
            throw new Error('Failed to load stats');
        }

        const stats = await res.json();

        // Update summary values
        document.getElementById('tokenCostToday').textContent =
            `$${stats.today?.cost_usd?.toFixed(4) || '0.00'}`;
        document.getElementById('tokenCostMonth').textContent =
            `$${stats.last_30_days?.cost_usd?.toFixed(2) || '0.00'}`;
        document.getElementById('tokenCallsMonth').textContent =
            stats.last_30_days?.calls?.toLocaleString() || '0';

        // Load feature breakdown
        const breakdownRes = await fetch(`${CONFIG.API_BASE}/stats/by-feature?days=30`);
        if (breakdownRes.ok) {
            const features = await breakdownRes.json();
            renderTokenBreakdown(features);
        }
    } catch (error) {
        console.error('Failed to load token stats:', error);
        // Show placeholder
        document.getElementById('tokenCostToday').textContent = '--';
        document.getElementById('tokenCostMonth').textContent = '--';
        document.getElementById('tokenCallsMonth').textContent = '--';
        document.getElementById('tokenBreakdown').innerHTML =
            '<p class="token-breakdown-empty">Unable to load usage data</p>';
    }
}

/**
 * Render token breakdown by feature
 */
function renderTokenBreakdown(features) {
    const container = document.getElementById('tokenBreakdown');

    if (!features || features.length === 0) {
        container.innerHTML = '<p class="token-breakdown-empty">No AI usage recorded yet</p>';
        return;
    }

    const html = features.map(f => `
        <div class="token-breakdown-item">
            <span class="token-feature-name">${formatFeatureName(f.feature)}</span>
            <span class="token-feature-cost">$${f.total_cost_usd.toFixed(4)} (${f.total_calls} calls)</span>
        </div>
    `).join('');

    container.innerHTML = html;
}

/**
 * Format feature name for display
 */
function formatFeatureName(feature) {
    const names = {
        'daily_brief': 'Daily Brief',
        'weekly_review': 'Weekly Review',
        'energy_prediction': 'Energy Prediction',
        'pattern_detection': 'Pattern Detection',
        'capture': 'Quick Capture',
        'other': 'Other'
    };
    return names[feature] || feature.replace(/_/g, ' ');
}

/**
 * Populate the settings form with data
 */
function populateSettingsForm(settings, timezones) {
    document.getElementById('userName').value = settings.user_name || '';

    const tzSelect = document.getElementById('userTimezone');
    tzSelect.innerHTML = timezones.map(tz =>
        `<option value="${tz}" ${tz === settings.timezone ? 'selected' : ''}>${tz}</option>`
    ).join('');

    const quietEnabled = settings.notifications?.quiet_hours_enabled ?? true;
    document.getElementById('quietHoursEnabled').checked = quietEnabled;
    document.getElementById('quietHoursStart').value = settings.notifications?.quiet_hours_start || '23:00';
    document.getElementById('quietHoursEnd').value = settings.notifications?.quiet_hours_end || '08:00';

    const range = document.getElementById('quietHoursRange');
    range.style.opacity = quietEnabled ? '1' : '0.5';
    range.style.pointerEvents = quietEnabled ? 'auto' : 'none';

    const integrations = settings.integrations || {};
    updateIntegrationStatus('ouraStatus', integrations.oura_configured);
    updateIntegrationStatus('aiStatus', integrations.ai_configured);
    updateIntegrationStatus('telegramStatus', integrations.telegram_configured);
    updateIntegrationStatus('discordStatus', integrations.discord_configured);

    const aiModel = document.getElementById('aiModel');
    if (integrations.ai_configured && settings.ai_model) {
        aiModel.textContent = settings.ai_model;
        aiModel.style.display = 'block';
    } else {
        aiModel.style.display = 'none';
    }
}

/**
 * Update integration status display
 */
function updateIntegrationStatus(elementId, configured) {
    const el = document.getElementById(elementId);
    if (configured) {
        el.textContent = 'Connected';
        el.classList.add('configured');
    } else {
        el.textContent = 'Not configured';
        el.classList.remove('configured');
    }
}

/**
 * Close the settings modal
 */
export function closeSettings() {
    const modal = document.getElementById('settingsModal');
    modal.classList.remove('visible');
    document.body.style.overflow = '';
    stopBackfillPolling();
}

/**
 * Save settings to the API
 */
export async function saveSettings() {
    const saveBtn = document.getElementById('saveSettings');
    saveBtn.disabled = true;
    saveBtn.textContent = 'Saving...';

    try {
        const updates = {
            user_name: document.getElementById('userName').value.trim() || 'User',
            timezone: document.getElementById('userTimezone').value,
            quiet_hours_enabled: document.getElementById('quietHoursEnabled').checked,
            quiet_hours_start: document.getElementById('quietHoursStart').value,
            quiet_hours_end: document.getElementById('quietHoursEnd').value
        };

        const response = await fetch(`${CONFIG.API_BASE}/settings`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(updates)
        });

        if (!response.ok) throw new Error('Failed to save settings');

        const newSettings = await response.json();
        settingsState.original = newSettings;
        settingsState.current = JSON.parse(JSON.stringify(newSettings));

        closeSettings();
        showToast('Settings saved!', 'success');
    } catch (error) {
        console.error('Failed to save settings:', error);
        showToast('Failed to save settings', 'error');
    } finally {
        saveBtn.disabled = false;
        saveBtn.textContent = 'Save Changes';
    }
}

/**
 * Load and display backfill status
 */
async function loadBackfillStatus() {
    try {
        const res = await fetch(`${CONFIG.API_BASE}/backfill/status`);
        if (!res.ok) throw new Error('Failed to load backfill status');

        const data = await res.json();
        const summary = data.data_summary;

        // Update record counts
        document.getElementById('ouraRecordCount').textContent =
            `${summary.oura?.record_count?.toLocaleString() || 0} records`;
        document.getElementById('calendarEventCount').textContent =
            `${summary.calendar?.event_count?.toLocaleString() || 0} events`;

        // Check if any backfill is in progress
        if (data.in_progress?.oura) {
            showBackfillProgress('oura', data.in_progress.oura);
            startBackfillPolling('oura');
        } else if (data.in_progress?.calendar) {
            showBackfillProgress('calendar', data.in_progress.calendar);
            startBackfillPolling('calendar');
        } else {
            hideBackfillProgress();
        }
    } catch (error) {
        console.error('Failed to load backfill status:', error);
        document.getElementById('ouraRecordCount').textContent = '-- records';
        document.getElementById('calendarEventCount').textContent = '-- events';
    }
}

/**
 * Start a backfill operation
 */
async function startBackfill(source) {
    const ouraBtn = document.getElementById('backfillOuraBtn');
    const calendarBtn = document.getElementById('backfillCalendarBtn');

    // Disable buttons
    ouraBtn.disabled = true;
    calendarBtn.disabled = true;

    try {
        const endpoint = source === 'oura'
            ? `${CONFIG.API_BASE}/backfill/oura?days=90`
            : `${CONFIG.API_BASE}/backfill/calendar?days_back=90&days_forward=30`;

        const res = await fetch(endpoint, { method: 'POST' });

        if (!res.ok) {
            const error = await res.json();
            throw new Error(error.detail || 'Failed to start backfill');
        }

        const progress = await res.json();
        showBackfillProgress(source, progress);
        startBackfillPolling(source);

        showToast(`Started ${source} import`, 'success');
    } catch (error) {
        console.error('Failed to start backfill:', error);
        showToast(error.message || 'Failed to start import', 'error');
        ouraBtn.disabled = false;
        calendarBtn.disabled = false;
    }
}

/**
 * Show backfill progress UI
 */
function showBackfillProgress(source, progress) {
    const container = document.getElementById('backfillProgress');
    const label = document.getElementById('backfillProgressLabel');
    const percent = document.getElementById('backfillProgressPercent');
    const fill = document.getElementById('backfillProgressFill');
    const detail = document.getElementById('backfillProgressDetail');

    container.style.display = 'block';

    const sourceName = source === 'oura' ? 'Oura' : 'Calendar';
    label.textContent = `Importing ${sourceName} data...`;
    percent.textContent = `${Math.round(progress.percent_complete)}%`;
    fill.style.width = `${progress.percent_complete}%`;

    if (progress.current_date) {
        detail.textContent = `Processing: ${progress.current_date} | ${progress.records_synced} records`;
    } else {
        detail.textContent = `${progress.records_synced} records synced`;
    }
}

/**
 * Hide backfill progress UI
 */
function hideBackfillProgress() {
    const container = document.getElementById('backfillProgress');
    if (container) {
        container.style.display = 'none';
    }

    // Re-enable buttons
    const ouraBtn = document.getElementById('backfillOuraBtn');
    const calendarBtn = document.getElementById('backfillCalendarBtn');
    if (ouraBtn) ouraBtn.disabled = false;
    if (calendarBtn) calendarBtn.disabled = false;
}

/**
 * Start polling for backfill progress
 */
function startBackfillPolling(source) {
    // Clear any existing poll
    if (backfillPollInterval) {
        clearInterval(backfillPollInterval);
    }

    backfillPollInterval = setInterval(async () => {
        try {
            const res = await fetch(`${CONFIG.API_BASE}/backfill/progress/${source}`);
            if (!res.ok) throw new Error('Failed to get progress');

            const progress = await res.json();

            if (progress.status === 'completed' || progress.status === 'failed' || progress.status === 'partial') {
                // Backfill finished
                clearInterval(backfillPollInterval);
                backfillPollInterval = null;

                if (progress.status === 'completed' || progress.status === 'partial') {
                    showToast(`${source === 'oura' ? 'Oura' : 'Calendar'} import complete: ${progress.records_synced} records`, 'success');
                } else {
                    showToast(`Import failed: ${progress.errors?.[0] || 'Unknown error'}`, 'error');
                }

                hideBackfillProgress();
                loadBackfillStatus(); // Refresh counts
            } else if (progress.status === 'in_progress') {
                showBackfillProgress(source, progress);
            }
        } catch (error) {
            console.error('Failed to poll backfill progress:', error);
        }
    }, 2000); // Poll every 2 seconds
}

/**
 * Stop backfill polling (called when modal closes)
 */
function stopBackfillPolling() {
    if (backfillPollInterval) {
        clearInterval(backfillPollInterval);
        backfillPollInterval = null;
    }
}
