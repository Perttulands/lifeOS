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

// Realistic curated sleep data with a narrative
function generateSleepData(days) {
    // Curated data that tells a story: recovery from poor sleep mid-week
    const curatedDurations = [7.2, 6.8, 5.5, 6.1, 7.4, 7.8, 7.1];
    const curatedQualities = [82, 78, 58, 65, 85, 89, 84];

    const data = [];
    for (let i = days - 1; i >= 0; i--) {
        const date = new Date();
        date.setDate(date.getDate() - i);
        const idx = days - 1 - i;
        data.push({
            date: date.toISOString().split('T')[0],
            duration: curatedDurations[idx] || 7.0,
            quality: curatedQualities[idx] || 75,
            deep: 0.9 + (curatedQualities[idx] / 100) * 0.6,
            rem: 1.0 + (curatedQualities[idx] / 100) * 0.8,
        });
    }
    return data;
}

// Realistic readiness data that correlates with sleep
function generateReadinessData(days) {
    const curatedScores = [78, 74, 52, 61, 82, 88, 85];

    const data = [];
    for (let i = days - 1; i >= 0; i--) {
        const date = new Date();
        date.setDate(date.getDate() - i);
        const idx = days - 1 - i;
        data.push({
            date: date.toISOString().split('T')[0],
            score: curatedScores[idx] || 75,
        });
    }
    return data;
}

// Activity data with realistic patterns
function generateActivityData(days) {
    const curatedScores = [72, 85, 45, 68, 78, 92, 74];
    const curatedSteps = [8500, 12400, 3200, 7800, 9200, 15600, 8900];

    const data = [];
    for (let i = days - 1; i >= 0; i--) {
        const date = new Date();
        date.setDate(date.getDate() - i);
        const idx = days - 1 - i;
        data.push({
            date: date.toISOString().split('T')[0],
            score: curatedScores[idx] || 70,
            steps: curatedSteps[idx] || 8000,
            calories: Math.round(curatedSteps[idx] * 0.05) || 400,
        });
    }
    return data;
}

// Energy self-reports that tell a user story
function generateEnergyData(days) {
    const curatedLevels = [4, 4, 2, 3, 4, 5, 4];

    const data = [];
    for (let i = days - 1; i >= 0; i--) {
        const date = new Date();
        date.setDate(date.getDate() - i);
        const idx = days - 1 - i;
        data.push({
            date: date.toISOString().split('T')[0],
            level: curatedLevels[idx],
        });
    }
    return data;
}

export function loadDemoData() {
    state.sleepData = generateSleepData(7);
    state.readinessData = generateReadinessData(7);
    state.activityData = generateActivityData(7);
    state.energyData = generateEnergyData(7);

    // Compelling brief that showcases the product value
    state.brief = {
        text: `<strong>Good news:</strong> You bounced back well from that rough Wednesday. Last night's <strong>7h 6m of sleep</strong> (84% quality) puts you <span class="brief-highlight">+18 minutes above</span> your weekly average.

Your <strong>readiness score of 85</strong> suggests today is ideal for deep work or that challenging workout you've been putting off.

<em>One pattern I've noticed:</em> Your energy dips on days after less than 6 hours of sleep. Tonight's goal: lights out by 11 PM to keep this momentum going.`,
        generatedAt: '7:00 AM',
        tags: ['recovery', 'high-readiness', 'deep-work-day'],
    };

    // Insights that feel genuinely useful
    state.insights = [
        {
            icon: '🌙',
            text: 'Your deep sleep increases by <strong>23%</strong> when you avoid screens 1+ hours before bed. You\'ve done this 4 of the last 7 nights.',
            meta: 'Sleep pattern • High confidence',
        },
        {
            icon: '📈',
            text: 'This week\'s readiness average: <strong>74</strong> (up from 68 last week). The biggest factor? Consistent 7+ hour sleep nights.',
            meta: 'Weekly progress • Trending up',
        },
        {
            icon: '⚡',
            text: 'Wednesday\'s low energy (2/5) followed your shortest sleep night. Your body needs 7+ hours to feel your best.',
            meta: 'Sleep-energy correlation • 14 data points',
        },
    ];

    // Add demo mode indicator
    showDemoBanner();

    renderDashboard();
}

/**
 * Show demo mode banner
 */
function showDemoBanner() {
    // Remove existing banner if present
    const existing = document.querySelector('.demo-banner');
    if (existing) existing.remove();

    const banner = document.createElement('div');
    banner.className = 'demo-banner';
    banner.innerHTML = `
        <span class="demo-banner-icon">✨</span>
        <span class="demo-banner-text">Demo Mode — Showing sample data</span>
        <button class="demo-banner-close" onclick="this.parentElement.remove()">×</button>
    `;
    document.body.prepend(banner);
}
