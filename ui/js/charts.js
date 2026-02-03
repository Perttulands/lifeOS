/**
 * LifeOS Dashboard - Chart Rendering
 */

import { state } from './config.js';
import { formatChartDate } from './utils.js';

/**
 * Render a sparkline chart
 */
export function renderSparkline(containerId, data, color) {
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

/**
 * Setup tooltip interactions for chart points
 */
function setupChartTooltips(container) {
    const tooltip = container.querySelector('#chartTooltip');
    const points = container.querySelectorAll('.chart-point');

    points.forEach(point => {
        point.addEventListener('mouseenter', (e) => {
            const date = point.dataset.date;
            const value = point.dataset.value;
            const formattedDate = formatChartDate(date);

            tooltip.innerHTML = `
                <div class="tooltip-date">${formattedDate}</div>
                <div class="tooltip-value">${value}</div>
            `;
            tooltip.classList.add('visible');

            const rect = point.getBoundingClientRect();
            const containerRect = container.getBoundingClientRect();
            tooltip.style.left = `${rect.left - containerRect.left + rect.width / 2}px`;
            tooltip.style.top = `${rect.top - containerRect.top - 10}px`;
        });

        point.addEventListener('mouseleave', () => {
            tooltip.classList.remove('visible');
        });
    });
}

/**
 * Render the main trend chart
 */
export function renderTrendChart() {
    const container = document.getElementById('trendChart');
    const legend = document.getElementById('trendLegend');

    let data, color, label, sourceData, valueFormatter;

    switch (state.currentMetric) {
        case 'sleep':
            sourceData = state.sleepData || [];
            data = sourceData.map(d => d.duration);
            color = '#6366f1';
            label = 'Sleep (hours)';
            valueFormatter = (val) => `${val.toFixed(1)}h`;
            break;
        case 'readiness':
            sourceData = state.readinessData || [];
            data = sourceData.map(d => d.score);
            color = '#10b981';
            label = 'Readiness Score';
            valueFormatter = (val) => Math.round(val);
            break;
        case 'activity':
            sourceData = state.activityData || [];
            data = sourceData.map(d => d.score);
            color = '#f59e0b';
            label = 'Activity Score';
            valueFormatter = (val) => Math.round(val);
            break;
        case 'energy':
            sourceData = state.energyData || [];
            data = sourceData.map(d => d.level || 0);
            color = '#f97316';
            label = 'Energy Level';
            valueFormatter = (val) => Math.round(val);
            break;
        default:
            sourceData = state.sleepData || [];
            data = sourceData.map(d => d.duration);
            color = '#6366f1';
            label = 'Sleep (hours)';
            valueFormatter = (val) => `${val.toFixed(1)}h`;
    }

    // Handle empty data
    if (!data || data.length === 0 || data.every(d => d === 0)) {
        container.innerHTML = `
            <div class="chart-empty">
                <p>No ${state.currentMetric} data available yet. Sync your Oura data to see trends.</p>
            </div>
        `;
        legend.innerHTML = '';
        return;
    }

    const width = container.clientWidth || 600;
    const height = 160;
    const padding = { top: 20, right: 20, bottom: 30, left: 45 };

    const chartWidth = width - padding.left - padding.right;
    const chartHeight = height - padding.top - padding.bottom;

    // Filter out zero values for min/max calculation
    const nonZeroData = data.filter(d => d > 0);
    const dataMin = nonZeroData.length > 0 ? Math.min(...nonZeroData) : 0;
    const dataMax = nonZeroData.length > 0 ? Math.max(...nonZeroData) : 1;
    const min = dataMin * 0.9;
    const max = dataMax * 1.1;
    const range = max - min || 1;

    // Day labels from source data
    const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
    const dayLabels = sourceData.map(d => {
        const date = new Date(d.date + 'T00:00:00');
        return days[date.getDay()];
    });

    // Generate path points
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
        const formatted = valueFormatter(val);
        return `<text x="${padding.left - 8}" y="${y}" text-anchor="end" dominant-baseline="middle" class="chart-label">${formatted}</text>`;
    }).join('');

    // X-axis labels
    const xLabels = dayLabels.map((day, i) => {
        const x = padding.left + (i / (data.length - 1)) * chartWidth;
        return `<text x="${x}" y="${height - 8}" text-anchor="middle" class="chart-label">${day}</text>`;
    }).join('');

    // Dots with hover areas
    const dots = points.map((p, i) => {
        const dateStr = sourceData[i]?.date || '';
        const formattedValue = valueFormatter(p.val);
        return `
            <g class="chart-point" data-date="${dateStr}" data-value="${formattedValue}">
                <circle cx="${p.x}" cy="${p.y}" r="12" fill="transparent" class="chart-dot-hover"/>
                <circle cx="${p.x}" cy="${p.y}" r="4" fill="${color}" class="chart-dot" style="animation-delay: ${i * 100}ms"/>
            </g>
        `;
    }).join('');

    container.innerHTML = `
        <div class="chart-tooltip" id="chartTooltip"></div>
        <svg width="100%" height="${height}" viewBox="0 0 ${width} ${height}">
            <style>
                .chart-label { font-size: 11px; fill: #64748b; font-family: 'JetBrains Mono', monospace; }
                .chart-dot { opacity: 0; animation: fadeIn 0.3s ease forwards; transition: r 0.15s ease; }
                .chart-dot-hover { cursor: pointer; }
                .chart-point:hover .chart-dot { r: 6; }
                @keyframes fadeIn { to { opacity: 1; } }
            </style>
            <defs>
                <linearGradient id="chartGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stop-color="${color}" stop-opacity="0.2"/>
                    <stop offset="100%" stop-color="${color}" stop-opacity="0"/>
                </linearGradient>
            </defs>
            <line x1="${padding.left}" y1="${padding.top}" x2="${padding.left}" y2="${height - padding.bottom}" stroke="#1e293b" stroke-width="1"/>
            <line x1="${padding.left}" y1="${height - padding.bottom}" x2="${width - padding.right}" y2="${height - padding.bottom}" stroke="#1e293b" stroke-width="1"/>
            <path d="${areaPath}" fill="url(#chartGrad)"/>
            <path d="${linePath}" fill="none" stroke="${color}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="filter: drop-shadow(0 0 6px ${color}60)"/>
            ${yLabels}
            ${xLabels}
            ${dots}
        </svg>
    `;

    setupChartTooltips(container);

    legend.innerHTML = `
        <div class="legend-item">
            <span class="legend-dot" style="background: ${color}"></span>
            <span>${label}</span>
        </div>
    `;
}
