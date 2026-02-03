/**
 * LifeOS Dashboard - Settings Modal
 */

import { CONFIG, settingsState } from './config.js';
import { showToast } from './utils.js';

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
