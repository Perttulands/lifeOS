/**
 * LifeOS Dashboard - Application Logic
 * =====================================
 * Handles data fetching, rendering, and interactions
 * for the LifeOS personal operating system dashboard.
 */

// === Configuration ===
const CONFIG = {
    API_BASE: '/api',
    REFRESH_INTERVAL: 5 * 60 * 1000, // 5 minutes
    ANIMATION_DURATION: 600,
    DEMO_MODE: false, // API is ready
};

// === State ===
const state = {
    selectedEnergy: null,
    currentMetric: 'sleep',
    sleepData: [],
    readinessData: [],
    energyData: [],
    brief: null,
    insights: [],
};

// === Initialization ===
document.addEventListener('DOMContentLoaded', () => {
    initializeApp();
});

async function initializeApp() {
    updateDateTime();
    setInterval(updateDateTime, 60000);

    setupEventListeners();
    await loadDashboardData();
}

// === Date & Time ===
function updateDateTime() {
    const now = new Date();
    const hour = now.getHours();

    // Set greeting based on time
    let greeting = 'Good evening';
    let icon = '🌙';

    if (hour >= 5 && hour < 12) {
        greeting = 'Good morning';
        icon = '🌅';
    } else if (hour >= 12 && hour < 17) {
        greeting = 'Good afternoon';
        icon = '☀️';
    } else if (hour >= 17 && hour < 21) {
        greeting = 'Good evening';
        icon = '🌆';
    }

    document.getElementById('greeting').textContent = greeting;
    document.getElementById('briefIcon').innerHTML = icon;

    // Format date
    const options = { weekday: 'long', month: 'short', day: 'numeric' };
    const dateStr = now.toLocaleDateString('en-US', options);
    document.getElementById('currentDate').textContent = dateStr;
}

// === Event Listeners ===
function setupEventListeners() {
    // Energy selector buttons
    const energyBtns = document.querySelectorAll('.energy-btn');
    energyBtns.forEach(btn => {
        btn.addEventListener('click', () => selectEnergy(btn));
    });

    // Log submit button
    document.getElementById('logSubmit').addEventListener('click', submitLog);

    // Refresh brief button
    document.getElementById('refreshBrief').addEventListener('click', refreshBrief);

    // Trend tabs
    const trendTabs = document.querySelectorAll('.trend-tab');
    trendTabs.forEach(tab => {
        tab.addEventListener('click', () => switchTrendMetric(tab));
    });

    // Note input - enable submit when energy is selected
    document.getElementById('noteInput').addEventListener('input', updateSubmitState);
}

// === Data Loading ===
async function loadDashboardData() {
    if (CONFIG.DEMO_MODE) {
        loadDemoData();
        return;
    }

    showLoadingState(true);

    try {
        // Fetch all data in parallel
        const [todayRes, sleepRes, readinessRes, patternsRes] = await Promise.all([
            fetch(`${CONFIG.API_BASE}/today`),
            fetch(`${CONFIG.API_BASE}/data/sleep?limit=7`),
            fetch(`${CONFIG.API_BASE}/data/readiness?limit=7`),
            fetch(`${CONFIG.API_BASE}/insights/patterns`),
        ]);

        // Check for errors
        if (!todayRes.ok || !sleepRes.ok || !readinessRes.ok) {
            throw new Error('API request failed');
        }

        const today = await todayRes.json();
        const sleepData = await sleepRes.json();
        const readinessData = await readinessRes.json();
        const patterns = patternsRes.ok ? await patternsRes.json() : [];

        // Transform sleep data for chart (reverse to chronological order)
        state.sleepData = sleepData.reverse().map(d => ({
            date: d.date,
            duration: d.value || 0,
            quality: d.metadata?.score || 70,
            deep: (d.metadata?.total_sleep_duration || 0) / 3600 * 0.2, // Approximate
            rem: (d.metadata?.total_sleep_duration || 0) / 3600 * 0.25,
        }));

        // Transform readiness data
        state.readinessData = readinessData.reverse().map(d => ({
            date: d.date,
            score: d.value || 0,
        }));

        // Generate energy data (we'll use journal entries or empty)
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
                text: 'No brief available yet. <a href="#" onclick="refreshBrief(); return false;">Generate one</a> or sync your Oura data first.',
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

        // If no patterns, show placeholder
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

function showLoadingState(loading) {
    const cards = document.querySelectorAll('.score-card, .brief-card, .trend-card');
    cards.forEach(card => {
        if (loading) {
            card.classList.add('loading');
        } else {
            card.classList.remove('loading');
        }
    });
}

function showErrorState(hasError) {
    const briefContent = document.getElementById('briefContent');
    if (hasError) {
        briefContent.innerHTML = `
            <p class="brief-text error-text">
                Unable to connect to the API.
                <a href="#" onclick="loadDashboardData(); return false;">Try again</a>
            </p>
        `;
    }
}

function formatTime(isoString) {
    if (!isoString) return 'Unknown';
    try {
        const date = new Date(isoString);
        return date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true });
    } catch {
        return 'Unknown';
    }
}

function extractTags(content) {
    // Extract meaningful tags from brief content
    const tags = [];
    if (content.toLowerCase().includes('sleep')) tags.push('sleep');
    if (content.toLowerCase().includes('energy')) tags.push('energy');
    if (content.toLowerCase().includes('readiness')) tags.push('readiness');
    if (content.toLowerCase().includes('pattern')) tags.push('pattern');
    return tags.slice(0, 3);
}

function getPatternIcon(patternType) {
    const icons = {
        'correlation': '📊',
        'trend': '📈',
        'anomaly': '⚠️',
        'weekly': '📅',
    };
    return icons[patternType] || '💡';
}

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

// === Demo Data ===
function loadDemoData() {
    // Generate realistic demo data
    const today = new Date();

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

function generateSleepData(days) {
    const data = [];
    for (let i = days - 1; i >= 0; i--) {
        const date = new Date();
        date.setDate(date.getDate() - i);
        data.push({
            date: date.toISOString().split('T')[0],
            duration: 5.5 + Math.random() * 2.5, // 5.5 to 8 hours
            quality: 60 + Math.random() * 35, // 60-95
            deep: 0.8 + Math.random() * 0.8, // 0.8 to 1.6 hours
            rem: 1.0 + Math.random() * 1.0, // 1 to 2 hours
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
            score: 55 + Math.random() * 40, // 55-95
        });
    }
    return data;
}

function generateEnergyData(days) {
    const data = [];
    for (let i = days - 1; i >= 0; i--) {
        const date = new Date();
        date.setDate(date.getDate() - i);
        // Some days have no data (null)
        const hasData = Math.random() > 0.2;
        data.push({
            date: date.toISOString().split('T')[0],
            level: hasData ? Math.ceil(Math.random() * 5) : null,
        });
    }
    return data;
}

// === Rendering ===
function renderDashboard() {
    renderBrief();
    renderSleepCard();
    renderReadinessCard();
    renderEnergyCard();
    renderTrendChart();
    renderInsights();
}

function renderBrief() {
    const briefContent = document.getElementById('briefContent');
    const briefTime = document.getElementById('briefTime');
    const briefTags = document.getElementById('briefTags');

    briefContent.innerHTML = `<p class="brief-text">${state.brief.text}</p>`;
    briefTime.textContent = `Generated at ${state.brief.generatedAt}`;

    briefTags.innerHTML = state.brief.tags
        .map(tag => `<span class="brief-tag">${tag}</span>`)
        .join('');
}

function renderSleepCard() {
    const latest = state.sleepData[state.sleepData.length - 1];
    const avg = state.sleepData.reduce((sum, d) => sum + d.duration, 0) / state.sleepData.length;
    const diff = latest.duration - avg;

    // Animate the value
    const valueEl = document.querySelector('#sleepCard .value-main');
    animateValue(valueEl, 0, latest.duration, 1000, (val) => {
        const hours = Math.floor(val);
        const minutes = Math.round((val - hours) * 60);
        return `${hours}h ${minutes.toString().padStart(2, '0')}m`;
    });

    // Quality bar
    const qualityBar = document.querySelector('#sleepCard .quality-bar');
    const qualityLabel = document.querySelector('#sleepCard .quality-label');
    const qualityPercent = latest.quality;

    setTimeout(() => {
        qualityBar.style.setProperty('--quality-percent', `${qualityPercent}%`);
        qualityBar.style.setProperty('--quality-color', getQualityColor(qualityPercent));
    }, 300);

    qualityLabel.textContent = getQualityLabel(qualityPercent);

    // Delta
    const deltaEl = document.querySelector('#sleepDelta .delta-indicator');
    const deltaSign = diff >= 0 ? '+' : '';
    const diffMinutes = Math.round(Math.abs(diff) * 60);
    deltaEl.textContent = `${deltaSign}${diff >= 0 ? '' : '-'}${diffMinutes}m`;
    deltaEl.className = `delta-indicator ${diff >= 0 ? 'positive' : 'negative'}`;

    // Sparkline
    renderSparkline('sleepSparkline', state.sleepData.map(d => d.duration), '#6366f1');
}

function renderReadinessCard() {
    const latest = state.readinessData[state.readinessData.length - 1];
    const avg = state.readinessData.reduce((sum, d) => sum + d.score, 0) / state.readinessData.length;
    const diff = latest.score - avg;

    // Animate the value
    const valueEl = document.querySelector('#readinessCard .value-main');
    animateValue(valueEl, 0, Math.round(latest.score), 1000);

    // Quality bar
    const qualityBar = document.querySelector('#readinessCard .quality-bar');
    const qualityLabel = document.querySelector('#readinessCard .quality-label');

    setTimeout(() => {
        qualityBar.style.setProperty('--quality-percent', `${latest.score}%`);
        qualityBar.style.setProperty('--quality-color', getQualityColor(latest.score));
    }, 300);

    qualityLabel.textContent = getQualityLabel(latest.score);

    // Delta
    const deltaEl = document.querySelector('#readinessDelta .delta-indicator');
    const deltaSign = diff >= 0 ? '+' : '';
    deltaEl.textContent = `${deltaSign}${Math.round(diff)}`;
    deltaEl.className = `delta-indicator ${diff >= 0 ? 'positive' : 'negative'}`;

    // Sparkline
    renderSparkline('readinessSparkline', state.readinessData.map(d => d.score), '#10b981');
}

function renderEnergyCard() {
    const todayEnergy = state.energyData[state.energyData.length - 1];
    const dots = document.querySelectorAll('.energy-dot');
    const levelText = document.getElementById('energyLevel');

    dots.forEach((dot, i) => {
        dot.classList.remove('active');
        if (todayEnergy.level && i < todayEnergy.level) {
            setTimeout(() => dot.classList.add('active'), i * 100);
        }
    });

    if (todayEnergy.level) {
        levelText.textContent = getEnergyLabel(todayEnergy.level);
    } else {
        levelText.textContent = 'Not logged today';
    }

    // Sparkline (filter out nulls for display)
    const energyValues = state.energyData.map(d => d.level || 0);
    renderSparkline('energySparkline', energyValues, '#f59e0b');
}

function renderSparkline(containerId, data, color) {
    const container = document.getElementById(containerId);
    if (!container || !data.length) return;

    const width = 80;
    const height = 24;
    const padding = 2;

    const min = Math.min(...data);
    const max = Math.max(...data);
    const range = max - min || 1;

    const points = data.map((val, i) => {
        const x = padding + (i / (data.length - 1)) * (width - padding * 2);
        const y = height - padding - ((val - min) / range) * (height - padding * 2);
        return `${x},${y}`;
    }).join(' ');

    container.innerHTML = `
        <svg width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">
            <defs>
                <linearGradient id="sparkGrad-${containerId}" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stop-color="${color}" stop-opacity="0.3"/>
                    <stop offset="100%" stop-color="${color}" stop-opacity="0"/>
                </linearGradient>
            </defs>
            <polygon
                points="${padding},${height - padding} ${points} ${width - padding},${height - padding}"
                fill="url(#sparkGrad-${containerId})"
            />
            <polyline
                points="${points}"
                fill="none"
                stroke="${color}"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
                style="filter: drop-shadow(0 0 4px ${color}40)"
            />
        </svg>
    `;
}

function renderTrendChart() {
    const container = document.getElementById('trendChart');
    const legend = document.getElementById('trendLegend');

    let data, color, label;

    switch (state.currentMetric) {
        case 'sleep':
            data = state.sleepData.map(d => d.duration);
            color = '#6366f1';
            label = 'Sleep (hours)';
            break;
        case 'readiness':
            data = state.readinessData.map(d => d.score);
            color = '#10b981';
            label = 'Readiness Score';
            break;
        case 'energy':
            data = state.energyData.map(d => d.level || 0);
            color = '#f59e0b';
            label = 'Energy Level';
            break;
    }

    const width = container.clientWidth || 600;
    const height = 160;
    const padding = { top: 20, right: 20, bottom: 30, left: 40 };

    const chartWidth = width - padding.left - padding.right;
    const chartHeight = height - padding.top - padding.bottom;

    const min = Math.min(...data) * 0.9;
    const max = Math.max(...data) * 1.1;
    const range = max - min || 1;

    const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
    const dayLabels = state.sleepData.map(d => {
        const date = new Date(d.date);
        return days[date.getDay()];
    });

    // Generate path
    const points = data.map((val, i) => {
        const x = padding.left + (i / (data.length - 1)) * chartWidth;
        const y = padding.top + chartHeight - ((val - min) / range) * chartHeight;
        return { x, y, val };
    });

    const linePath = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ');
    const areaPath = `M ${padding.left} ${height - padding.bottom} ` +
        points.map(p => `L ${p.x} ${p.y}`).join(' ') +
        ` L ${width - padding.right} ${height - padding.bottom} Z`;

    // Y-axis labels
    const yLabels = [min, (min + max) / 2, max].map(val => {
        const y = padding.top + chartHeight - ((val - min) / range) * chartHeight;
        const formatted = state.currentMetric === 'sleep'
            ? `${val.toFixed(1)}h`
            : Math.round(val);
        return `<text x="${padding.left - 8}" y="${y}" text-anchor="end" dominant-baseline="middle" class="chart-label">${formatted}</text>`;
    }).join('');

    // X-axis labels
    const xLabels = dayLabels.map((day, i) => {
        const x = padding.left + (i / (data.length - 1)) * chartWidth;
        return `<text x="${x}" y="${height - 8}" text-anchor="middle" class="chart-label">${day}</text>`;
    }).join('');

    // Dots
    const dots = points.map((p, i) => `
        <circle
            cx="${p.x}"
            cy="${p.y}"
            r="4"
            fill="${color}"
            class="chart-dot"
            style="animation-delay: ${i * 100}ms"
        />
    `).join('');

    container.innerHTML = `
        <svg width="100%" height="${height}" viewBox="0 0 ${width} ${height}">
            <style>
                .chart-label { font-size: 11px; fill: #64748b; font-family: 'JetBrains Mono', monospace; }
                .chart-dot { opacity: 0; animation: fadeIn 0.3s ease forwards; }
                @keyframes fadeIn { to { opacity: 1; } }
            </style>
            <defs>
                <linearGradient id="chartGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stop-color="${color}" stop-opacity="0.2"/>
                    <stop offset="100%" stop-color="${color}" stop-opacity="0"/>
                </linearGradient>
            </defs>
            <!-- Grid lines -->
            <line x1="${padding.left}" y1="${padding.top}" x2="${padding.left}" y2="${height - padding.bottom}"
                  stroke="#1e293b" stroke-width="1"/>
            <line x1="${padding.left}" y1="${height - padding.bottom}" x2="${width - padding.right}" y2="${height - padding.bottom}"
                  stroke="#1e293b" stroke-width="1"/>
            <!-- Area -->
            <path d="${areaPath}" fill="url(#chartGrad)"/>
            <!-- Line -->
            <path d="${linePath}" fill="none" stroke="${color}" stroke-width="2.5"
                  stroke-linecap="round" stroke-linejoin="round"
                  style="filter: drop-shadow(0 0 6px ${color}60)"/>
            <!-- Labels -->
            ${yLabels}
            ${xLabels}
            <!-- Dots -->
            ${dots}
        </svg>
    `;

    // Legend
    legend.innerHTML = `
        <div class="legend-item">
            <span class="legend-dot" style="background: ${color}"></span>
            <span>${label}</span>
        </div>
    `;
}

function renderInsights() {
    const container = document.getElementById('insightsList');

    container.innerHTML = state.insights.map((insight, i) => `
        <div class="insight-card glass-card" style="animation-delay: ${i * 100}ms">
            <div class="insight-icon">${insight.icon}</div>
            <div class="insight-content">
                <p class="insight-text">${insight.text}</p>
                <span class="insight-meta">${insight.meta}</span>
            </div>
        </div>
    `).join('');
}

// === Interactions ===
function selectEnergy(btn) {
    // Remove selection from all
    document.querySelectorAll('.energy-btn').forEach(b => b.classList.remove('selected'));

    // Select clicked
    btn.classList.add('selected');
    state.selectedEnergy = parseInt(btn.dataset.value);

    updateSubmitState();
}

function updateSubmitState() {
    const submitBtn = document.getElementById('logSubmit');
    submitBtn.disabled = state.selectedEnergy === null;
}

async function submitLog() {
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

async function refreshBrief() {
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
            // Simulate refresh in demo mode
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

function switchTrendMetric(tab) {
    document.querySelectorAll('.trend-tab').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    state.currentMetric = tab.dataset.metric;
    renderTrendChart();
}

// === Utilities ===
function animateValue(element, start, end, duration, formatter = null) {
    const startTime = performance.now();

    function update(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const eased = easeOutCubic(progress);
        const current = start + (end - start) * eased;

        if (formatter) {
            element.textContent = formatter(current);
        } else {
            element.textContent = Math.round(current);
        }

        if (progress < 1) {
            requestAnimationFrame(update);
        }
    }

    requestAnimationFrame(update);
}

function easeOutCubic(t) {
    return 1 - Math.pow(1 - t, 3);
}

function getQualityColor(score) {
    if (score >= 80) return '#10b981';
    if (score >= 60) return '#6366f1';
    if (score >= 40) return '#f59e0b';
    return '#ef4444';
}

function getQualityLabel(score) {
    if (score >= 85) return 'Excellent';
    if (score >= 70) return 'Good';
    if (score >= 55) return 'Fair';
    if (score >= 40) return 'Low';
    return 'Poor';
}

function getEnergyLabel(level) {
    const labels = ['', 'Very Low', 'Low', 'Moderate', 'Good', 'Excellent'];
    return labels[level] || '';
}

function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        <span class="toast-icon">${type === 'success' ? '✓' : type === 'error' ? '✕' : 'ℹ'}</span>
        <span>${message}</span>
    `;

    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100px)';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// === Resize Handler ===
let resizeTimeout;
window.addEventListener('resize', () => {
    clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(() => {
        renderTrendChart();
    }, 250);
});
