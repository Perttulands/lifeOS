/**
 * LifeOS Dashboard - API & Data Loading
 */

import { CONFIG, state } from './config.js';
import { renderDashboard, renderBrief, renderEnergyCard } from './components.js';
import { formatTime, extractTags, getPatternIcon, showToast } from './utils.js';

/**
 * Show/hide loading state on cards
 */
export function showLoadingState(loading) {
    const cards = document.querySelectorAll('.score-card, .brief-card, .trend-card');
    cards.forEach(card => {
        if (loading) {
            card.classList.add('loading');
        } else {
            card.classList.remove('loading');
        }
    });
}

/**
 * Show error state in brief section
 */
export function showErrorState(hasError) {
    const briefContent = document.getElementById('briefContent');
    if (hasError) {
        briefContent.innerHTML = `
            <p class="brief-text error-text">
                Unable to connect to the API.
                <a href="#" onclick="window.loadDashboardData(); return false;">Try again</a>
                or <a href="#" onclick="window.enableDemoMode(); return false;">use demo mode</a>
            </p>
        `;
    }
}

/**
 * Enable demo mode
 */
export function enableDemoMode() {
    CONFIG.DEMO_MODE = true;
    loadDemoData();
    showToast('Demo mode enabled', 'info');
}

/**
 * Generate placeholder energy data
 */
function generateEnergyPlaceholder(days, todayLevel) {
    const data = [];
    for (let i = days - 1; i >= 0; i--) {
        const date = new Date();
        date.setDate(date.getDate() - i);
        data.push({
            date: date.toISOString().split('T')[0],
            level: i === 0 ? todayLevel : null,
        });
    }
    return data;
}

/**
 * Load all dashboard data from API
 */
export async function loadDashboardData() {
    if (CONFIG.DEMO_MODE) {
        loadDemoData();
        return;
    }

    showLoadingState(true);

    try {
        const [todayRes, sleepRes, readinessRes, activityRes, patternsRes] = await Promise.all([
            fetch(`${CONFIG.API_BASE}/today`),
            fetch(`${CONFIG.API_BASE}/data/sleep?limit=7`),
            fetch(`${CONFIG.API_BASE}/data/readiness?limit=7`),
            fetch(`${CONFIG.API_BASE}/data/activity?limit=7`),
            fetch(`${CONFIG.API_BASE}/insights/patterns`),
        ]);

        if (!todayRes.ok || !sleepRes.ok || !readinessRes.ok) {
            throw new Error('API request failed');
        }

        const today = await todayRes.json();
        const sleepData = await sleepRes.json();
        const readinessData = await readinessRes.json();
        const activityData = activityRes.ok ? await activityRes.json() : [];
        const patterns = patternsRes.ok ? await patternsRes.json() : [];

        // Transform sleep data
        state.sleepData = sleepData.reverse().map(d => ({
            date: d.date,
            duration: (d.metadata?.total_sleep_duration || 0) / 3600,
            quality: d.value || 0,
            deep: (d.metadata?.deep_sleep_duration || 0) / 100,
            rem: (d.metadata?.rem_sleep_duration || 0) / 100,
        }));

        // Transform readiness data
        state.readinessData = readinessData.reverse().map(d => ({
            date: d.date,
            score: d.value || 0,
        }));

        // Transform activity data
        state.activityData = activityData.reverse().map(d => ({
            date: d.date,
            score: d.value || 0,
            steps: d.metadata?.steps || 0,
            calories: d.metadata?.active_calories || 0,
        }));

        // Generate energy placeholder
        state.energyData = generateEnergyPlaceholder(7, today.energy_log?.level);

        // Transform brief
        if (today.brief && today.brief.content) {
            state.brief = {
                text: today.brief.content,
                generatedAt: formatTime(today.brief.generated_at),
                tags: extractTags(today.brief.content),
            };
        } else {
            state.brief = {
                text: 'No brief available yet. <a href="#" onclick="window.refreshBrief(); return false;">Generate one</a> or sync your Oura data first.',
                generatedAt: 'Not generated',
                tags: [],
            };
        }

        // Transform patterns to insights
        state.insights = patterns.slice(0, 3).map(p => ({
            icon: getPatternIcon(p.pattern_type),
            text: p.description,
            meta: `${p.pattern_type} • ${Math.round(p.confidence * 100)}% confidence`,
        }));

        if (state.insights.length === 0) {
            state.insights = [{
                icon: '💡',
                text: 'Insights will appear here once you have a few days of data.',
                meta: 'Keep syncing!',
            }];
        }

        showLoadingState(false);
        renderDashboard();

    } catch (error) {
        console.error('Failed to load dashboard data:', error);
        showLoadingState(false);
        showErrorState(true);
        showToast('Failed to load data. Check your connection.', 'error');
    }
}

/**
 * Refresh the daily brief
 */
export async function refreshBrief() {
    const btn = document.getElementById('refreshBrief');
    btn.disabled = true;

    try {
        if (!CONFIG.DEMO_MODE) {
            const res = await fetch(`${CONFIG.API_BASE}/insights/brief?generate=true`);

            if (!res.ok) {
                throw new Error('Failed to generate brief');
            }

            const data = await res.json();

            if (data && data.content) {
                state.brief = {
                    text: data.content,
                    generatedAt: formatTime(data.created_at),
                    tags: extractTags(data.content),
                };
            } else {
                throw new Error('No brief data returned');
            }
        } else {
            await new Promise(resolve => setTimeout(resolve, 1000));
        }

        renderBrief();
        showToast('Brief refreshed!', 'success');
    } catch (error) {
        console.error('Failed to refresh brief:', error);
        showToast('Failed to refresh brief. Need Oura data first?', 'error');
    } finally {
        btn.disabled = false;
    }
}

/**
 * Submit energy log
 */
export async function submitLog() {
    const note = document.getElementById('noteInput').value.trim();

    if (state.selectedEnergy === null) return;

    const submitBtn = document.getElementById('logSubmit');
    submitBtn.disabled = true;
    submitBtn.querySelector('.submit-text').textContent = 'Logging...';

    try {
        if (!CONFIG.DEMO_MODE) {
            const response = await fetch(`${CONFIG.API_BASE}/log`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    energy: state.selectedEnergy,
                    notes: note || null,
                }),
            });

            if (!response.ok) {
                throw new Error('Failed to log');
            }
        }

        // Update local state
        state.energyData[state.energyData.length - 1].level = state.selectedEnergy;
        renderEnergyCard();

        // Reset form
        document.querySelectorAll('.energy-btn').forEach(b => b.classList.remove('selected'));
        document.getElementById('noteInput').value = '';
        state.selectedEnergy = null;

        showToast('Logged!', 'success');
    } catch (error) {
        console.error('Failed to submit log:', error);
        showToast('Failed to log. Try again.', 'error');
    } finally {
        submitBtn.disabled = false;
        submitBtn.querySelector('.submit-text').textContent = 'Log';
        updateSubmitState();
    }
}

/**
 * Update submit button state
 */
export function updateSubmitState() {
    const submitBtn = document.getElementById('logSubmit');
    submitBtn.disabled = state.selectedEnergy === null;
}

// === Demo Data Generation ===

function generateSleepData(days) {
    const data = [];
    for (let i = days - 1; i >= 0; i--) {
        const date = new Date();
        date.setDate(date.getDate() - i);
        data.push({
            date: date.toISOString().split('T')[0],
            duration: 5.5 + Math.random() * 2.5,
            quality: 60 + Math.random() * 35,
            deep: 0.8 + Math.random() * 0.8,
            rem: 1.0 + Math.random() * 1.0,
        });
    }
    return data;
}

function generateReadinessData(days) {
    const data = [];
    for (let i = days - 1; i >= 0; i--) {
        const date = new Date();
        date.setDate(date.getDate() - i);
        data.push({
            date: date.toISOString().split('T')[0],
            score: 55 + Math.random() * 40,
        });
    }
    return data;
}

function generateEnergyData(days) {
    const data = [];
    for (let i = days - 1; i >= 0; i--) {
        const date = new Date();
        date.setDate(date.getDate() - i);
        const hasData = Math.random() > 0.2;
        data.push({
            date: date.toISOString().split('T')[0],
            level: hasData ? Math.ceil(Math.random() * 5) : null,
        });
    }
    return data;
}

export function loadDemoData() {
    state.sleepData = generateSleepData(7);
    state.readinessData = generateReadinessData(7);
    state.energyData = generateEnergyData(7);

    state.brief = {
        text: `You got <strong>6 hours 42 minutes</strong> of sleep last night — that's <span class="brief-highlight">48 minutes below</span> your weekly average. Your deep sleep was solid at 1h 23m, but REM was a bit low. Consider an earlier bedtime tonight to catch up. Your readiness score of <strong>72</strong> suggests you're good for focused work this morning, but maybe skip that intense workout.`,
        generatedAt: '7:00 AM',
        tags: ['sleep-debt', 'low-rem', 'readiness-good'],
    };

    state.insights = [
        {
            icon: '💡',
            text: 'Your deep sleep increases by 18% when you stop screen time 1 hour before bed.',
            meta: 'Pattern detected from 14 days of data',
        },
        {
            icon: '📈',
            text: 'Your average readiness score improved 8 points this week compared to last.',
            meta: 'Weekly trend',
        },
        {
            icon: '⚡',
            text: 'You report highest energy on days following 7+ hours of sleep.',
            meta: 'Correlation found',
        },
    ];

    renderDashboard();
}
