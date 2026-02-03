/**
 * LifeOS Dashboard - Utility Functions
 */

/**
 * Animate a numeric value with easing
 */
export function animateValue(element, start, end, duration, formatter = null) {
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

export function easeOutCubic(t) {
    return 1 - Math.pow(1 - t, 3);
}

export function getQualityColor(score) {
    if (score >= 80) return '#10b981';
    if (score >= 60) return '#6366f1';
    if (score >= 40) return '#f59e0b';
    return '#ef4444';
}

export function getQualityLabel(score) {
    if (score >= 85) return 'Excellent';
    if (score >= 70) return 'Good';
    if (score >= 55) return 'Fair';
    if (score >= 40) return 'Low';
    return 'Poor';
}

export function getEnergyLabel(level) {
    const labels = ['', 'Very Low', 'Low', 'Moderate', 'Good', 'Excellent'];
    return labels[level] || '';
}

export function formatTime(isoString) {
    if (!isoString) return 'Unknown';
    try {
        const date = new Date(isoString);
        return date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true });
    } catch {
        return 'Unknown';
    }
}

export function formatChartDate(dateStr) {
    if (!dateStr) return '';
    const date = new Date(dateStr + 'T00:00:00');
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

export function extractTags(content) {
    const tags = [];
    if (content.toLowerCase().includes('sleep')) tags.push('sleep');
    if (content.toLowerCase().includes('energy')) tags.push('energy');
    if (content.toLowerCase().includes('readiness')) tags.push('readiness');
    if (content.toLowerCase().includes('pattern')) tags.push('pattern');
    return tags.slice(0, 3);
}

export function getPatternIcon(patternType) {
    const icons = {
        'correlation': '📊',
        'trend': '📈',
        'anomaly': '⚠️',
        'weekly': '📅',
    };
    return icons[patternType] || '💡';
}

export function showToast(message, type = 'info') {
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

/**
 * Update greeting and icon based on time of day
 */
export function updateDateTime() {
    const now = new Date();
    const hour = now.getHours();

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

    const options = { weekday: 'long', month: 'short', day: 'numeric' };
    const dateStr = now.toLocaleDateString('en-US', options);
    document.getElementById('currentDate').textContent = dateStr;
}
