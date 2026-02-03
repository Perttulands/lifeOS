/**
 * LifeOS Dashboard - Configuration & State
 */

export const CONFIG = {
    API_BASE: '/api',
    REFRESH_INTERVAL: 5 * 60 * 1000, // 5 minutes
    ANIMATION_DURATION: 600,
    DEMO_MODE: false, // API is ready
};

export const state = {
    selectedEnergy: null,
    currentMetric: 'sleep',
    sleepData: [],
    readinessData: [],
    activityData: [],
    energyData: [],
    brief: null,
    insights: [],
};

export const settingsState = {
    original: null,
    current: null,
    timezones: []
};
