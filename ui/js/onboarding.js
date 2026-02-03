/**
 * LifeOS Dashboard - Onboarding Flow
 * First-run wizard that guides users through setup
 */

import { CONFIG } from './config.js';
import { showToast } from './utils.js';

// Onboarding state
let onboardingState = {
    status: null,
    currentStep: 0,
    testingStep: null
};

/**
 * Check onboarding status and show wizard if needed
 */
export async function checkOnboarding() {
    try {
        const res = await fetch(`${CONFIG.API_BASE}/onboarding/status`);
        if (!res.ok) return;

        const status = await res.json();
        onboardingState.status = status;

        // Show onboarding if first run and not complete
        if (status.is_first_run && !status.setup_complete) {
            showOnboardingModal(status);
        }
    } catch (error) {
        console.error('Failed to check onboarding status:', error);
    }
}

/**
 * Show the onboarding modal
 */
function showOnboardingModal(status) {
    const modal = document.getElementById('onboardingModal');
    if (!modal) return;

    // Update progress
    updateProgress(status.progress_percent);

    // Render steps
    renderSteps(status.steps);

    // Setup event listeners
    setupOnboardingListeners();

    // Show modal
    modal.classList.add('visible');
    document.body.style.overflow = 'hidden';
}

/**
 * Update progress bar
 */
function updateProgress(percent) {
    const fill = document.getElementById('onboardingProgressFill');
    const text = document.getElementById('onboardingProgressText');

    if (fill) fill.style.width = `${percent}%`;
    if (text) text.textContent = `${percent}% complete`;
}

/**
 * Render onboarding steps
 */
function renderSteps(steps) {
    const container = document.getElementById('onboardingSteps');
    if (!container) return;

    const html = steps.map((step, index) => {
        const statusClass = getStepClass(step.status);
        const icon = getStepIcon(step.status);

        return `
            <div class="onboarding-step ${statusClass}" data-step-id="${step.id}">
                <div class="step-icon">
                    ${icon}
                </div>
                <div class="step-content">
                    <div class="step-title">${step.title}</div>
                    <p class="step-description">${step.description}</p>
                    ${renderStepStatus(step)}
                    ${renderStepActions(step)}
                </div>
            </div>
        `;
    }).join('');

    container.innerHTML = html;

    // Attach test button listeners
    container.querySelectorAll('.step-test-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const stepId = e.target.closest('.onboarding-step').dataset.stepId;
            testConnection(stepId);
        });
    });
}

/**
 * Get CSS class for step status
 */
function getStepClass(status) {
    switch (status) {
        case 'completed': return 'completed';
        case 'error': return 'error';
        case 'in_progress': return 'active';
        case 'pending': return '';
        case 'skipped': return 'completed';
        default: return '';
    }
}

/**
 * Get icon HTML for step status
 */
function getStepIcon(status) {
    switch (status) {
        case 'completed':
        case 'skipped':
            return '<svg class="checkmark" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><path d="M20 6L9 17l-5-5"/></svg>';
        case 'error':
            return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12"/></svg>';
        case 'in_progress':
            return '<span class="spinner"></span>';
        default:
            return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/></svg>';
    }
}

/**
 * Render step status text
 */
function renderStepStatus(step) {
    if (step.status === 'completed') {
        return '<div class="step-status success">Connected</div>';
    }
    if (step.status === 'skipped') {
        return '<div class="step-status">Skipped (optional)</div>';
    }
    if (step.status === 'error' && step.error_message) {
        return `
            <div class="step-error">
                <div class="step-error-message">${step.error_message}</div>
            </div>
        `;
    }
    return '';
}

/**
 * Render step action buttons
 */
function renderStepActions(step) {
    if (step.status === 'completed' || step.status === 'skipped') {
        return '';
    }

    let html = '';

    // Test button for testable steps
    if (step.id === 'oura' || step.id === 'ai') {
        html += `
            <button class="step-test-btn" data-test="${step.id}">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M22 12h-4l-3 9L9 3l-3 9H2"/>
                </svg>
                Test Connection
            </button>
        `;
    }

    // Help link
    if (step.help_url) {
        html += `
            <a href="${step.help_url}" target="_blank" class="step-help">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="10"/>
                    <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/>
                    <line x1="12" y1="17" x2="12.01" y2="17"/>
                </svg>
                Get help
            </a>
        `;
    }

    return html;
}

/**
 * Test a service connection
 */
async function testConnection(service) {
    const stepEl = document.querySelector(`[data-step-id="${service}"]`);
    if (!stepEl) return;

    // Update UI to show testing
    const btn = stepEl.querySelector('.step-test-btn');
    if (btn) {
        btn.innerHTML = '<span class="spinner"></span> Testing...';
        btn.disabled = true;
        btn.classList.add('testing');
    }

    try {
        const res = await fetch(`${CONFIG.API_BASE}/onboarding/test/${service}`, {
            method: 'POST'
        });

        const result = await res.json();

        if (result.connected) {
            // Success
            stepEl.classList.remove('error');
            stepEl.classList.add('completed');
            stepEl.querySelector('.step-icon').innerHTML = getStepIcon('completed');

            const statusEl = stepEl.querySelector('.step-status, .step-error');
            if (statusEl) {
                statusEl.outerHTML = '<div class="step-status success">Connected</div>';
            } else {
                stepEl.querySelector('.step-content').insertAdjacentHTML(
                    'beforeend',
                    '<div class="step-status success">Connected</div>'
                );
            }

            // Remove test button
            if (btn) btn.remove();

            showToast(`${service === 'oura' ? 'Oura' : 'AI'} connected successfully!`, 'success');

            // Refresh status
            refreshOnboardingStatus();
        } else {
            // Failed
            stepEl.classList.add('error');
            stepEl.querySelector('.step-icon').innerHTML = getStepIcon('error');

            // Show error details
            let errorHtml = `
                <div class="step-error">
                    <div class="step-error-message">${result.message}</div>
            `;

            if (result.fix_suggestions && result.fix_suggestions.length > 0) {
                errorHtml += '<ul class="step-suggestions">';
                result.fix_suggestions.forEach(s => {
                    errorHtml += `<li>${s}</li>`;
                });
                errorHtml += '</ul>';
            }

            errorHtml += '</div>';

            const existingError = stepEl.querySelector('.step-error');
            if (existingError) {
                existingError.outerHTML = errorHtml;
            } else {
                const statusEl = stepEl.querySelector('.step-status');
                if (statusEl) {
                    statusEl.outerHTML = errorHtml;
                } else {
                    stepEl.querySelector('.step-content').insertAdjacentHTML('beforeend', errorHtml);
                }
            }

            // Reset button
            if (btn) {
                btn.innerHTML = `
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M22 12h-4l-3 9L9 3l-3 9H2"/>
                    </svg>
                    Test Again
                `;
                btn.disabled = false;
                btn.classList.remove('testing');
            }
        }
    } catch (error) {
        console.error('Test connection error:', error);
        showToast('Connection test failed', 'error');

        // Reset button
        if (btn) {
            btn.innerHTML = `
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M22 12h-4l-3 9L9 3l-3 9H2"/>
                </svg>
                Test Again
            `;
            btn.disabled = false;
            btn.classList.remove('testing');
        }
    }
}

/**
 * Refresh onboarding status from API
 */
async function refreshOnboardingStatus() {
    try {
        const res = await fetch(`${CONFIG.API_BASE}/onboarding/status`);
        if (!res.ok) return;

        const status = await res.json();
        onboardingState.status = status;

        updateProgress(status.progress_percent);

        // Check if complete
        if (status.setup_complete) {
            showToast('Setup complete! Welcome to LifeOS.', 'success');
            closeOnboarding();
        }
    } catch (error) {
        console.error('Failed to refresh status:', error);
    }
}

/**
 * Setup event listeners for onboarding modal
 */
function setupOnboardingListeners() {
    const skipBtn = document.getElementById('onboardingSkip');
    const continueBtn = document.getElementById('onboardingContinue');

    if (skipBtn) {
        skipBtn.addEventListener('click', skipOnboarding);
    }

    if (continueBtn) {
        continueBtn.addEventListener('click', continueOnboarding);
    }

    // Close on escape
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            const modal = document.getElementById('onboardingModal');
            if (modal && modal.classList.contains('visible')) {
                skipOnboarding();
            }
        }
    });
}

/**
 * Skip onboarding (user can continue later)
 */
function skipOnboarding() {
    closeOnboarding();
    showToast('You can complete setup anytime via Settings', 'info');
}

/**
 * Continue/complete onboarding
 */
async function continueOnboarding() {
    const status = onboardingState.status;

    // If not complete, show what needs to be done
    if (status && !status.setup_complete) {
        const pendingRequired = status.steps.filter(s =>
            s.required && s.status !== 'completed'
        );

        if (pendingRequired.length > 0) {
            showToast(`Please configure ${pendingRequired[0].title} first`, 'warning');
            return;
        }
    }

    // Mark complete
    try {
        const res = await fetch(`${CONFIG.API_BASE}/onboarding/complete`, {
            method: 'POST'
        });

        if (res.ok) {
            const result = await res.json();
            closeOnboarding();
            showToast(result.message, 'success');
        }
    } catch (error) {
        console.error('Failed to complete onboarding:', error);
        closeOnboarding();
    }
}

/**
 * Close the onboarding modal
 */
function closeOnboarding() {
    const modal = document.getElementById('onboardingModal');
    if (modal) {
        modal.classList.remove('visible');
        document.body.style.overflow = '';
    }
}

/**
 * Manually open onboarding (from settings)
 */
export function openOnboarding() {
    checkOnboarding();
}
