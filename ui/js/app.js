/**
 * LifeOS Dashboard - Main Application
 * ====================================
 * Entry point that initializes all modules.
 */

import { state } from './config.js';
import { updateDateTime } from './utils.js';
import { renderTrendChart } from './charts.js';
import {
    loadDashboardData,
    refreshBrief,
    submitLog,
    updateSubmitState,
    enableDemoMode
} from './api.js';
import { setupSettingsListeners } from './settings.js';
import { checkOnboarding } from './onboarding.js';

// === Initialization ===
document.addEventListener('DOMContentLoaded', () => {
    initializeApp();
});

async function initializeApp() {
    updateDateTime();
    setInterval(updateDateTime, 60000);

    setupEventListeners();
    setupSettingsListeners();
    await loadDashboardData();

    // Check if first-run onboarding is needed
    await checkOnboarding();
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

    // Note input
    document.getElementById('noteInput').addEventListener('input', updateSubmitState);
}

// === Interactions ===
function selectEnergy(btn) {
    document.querySelectorAll('.energy-btn').forEach(b => b.classList.remove('selected'));
    btn.classList.add('selected');
    state.selectedEnergy = parseInt(btn.dataset.value);
    updateSubmitState();
}

function switchTrendMetric(tab) {
    document.querySelectorAll('.trend-tab').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    state.currentMetric = tab.dataset.metric;
    renderTrendChart();
}

// === Resize Handler ===
let resizeTimeout;
window.addEventListener('resize', () => {
    clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(() => {
        renderTrendChart();
    }, 250);
});

// === Export functions to window for inline handlers ===
window.loadDashboardData = loadDashboardData;
window.refreshBrief = refreshBrief;
window.enableDemoMode = enableDemoMode;
