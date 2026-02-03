/**
 * LifeOS Dashboard - UI Component Rendering
 */

import { state } from './config.js';
import { renderSparkline, renderTrendChart } from './charts.js';
import {
    animateValue,
    getQualityColor,
    getQualityLabel,
    getEnergyLabel
} from './utils.js';

/**
 * Render all dashboard components
 */
export function renderDashboard() {
    renderBrief();
    renderSleepCard();
    renderReadinessCard();
    renderEnergyCard();
    renderTrendChart();
    renderInsights();
}

/**
 * Render the daily brief section
 */
export function renderBrief() {
    const briefContent = document.getElementById('briefContent');
    const briefTime = document.getElementById('briefTime');
    const briefTags = document.getElementById('briefTags');

    briefContent.innerHTML = `<p class="brief-text">${state.brief.text}</p>`;
    briefTime.textContent = `Generated at ${state.brief.generatedAt}`;

    briefTags.innerHTML = state.brief.tags
        .map(tag => `<span class="brief-tag">${tag}</span>`)
        .join('');
}

/**
 * Render the sleep score card
 */
export function renderSleepCard() {
    if (!state.sleepData || state.sleepData.length === 0) {
        document.querySelector('#sleepCard .value-main').textContent = '--';
        document.querySelector('#sleepCard .quality-label').textContent = 'No data';
        return;
    }

    const latest = state.sleepData[state.sleepData.length - 1];
    const avg = state.sleepData.reduce((sum, d) => sum + d.duration, 0) / state.sleepData.length;
    const diff = latest.duration - avg;

    // Animate value
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

/**
 * Render the readiness score card
 */
export function renderReadinessCard() {
    if (!state.readinessData || state.readinessData.length === 0) {
        document.querySelector('#readinessCard .value-main').textContent = '--';
        document.querySelector('#readinessCard .quality-label').textContent = 'No data';
        return;
    }

    const latest = state.readinessData[state.readinessData.length - 1];
    const avg = state.readinessData.reduce((sum, d) => sum + d.score, 0) / state.readinessData.length;
    const diff = latest.score - avg;

    // Animate value
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

/**
 * Render the energy level card
 */
export function renderEnergyCard() {
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

    // Sparkline
    const energyValues = state.energyData.map(d => d.level || 0);
    renderSparkline('energySparkline', energyValues, '#f59e0b');
}

/**
 * Render the insights section
 */
export function renderInsights() {
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
