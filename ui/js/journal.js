/**
 * LifeOS Dashboard - Mood/Energy Journal
 * Beautiful, frictionless journaling component
 */

import { CONFIG } from './config.js';
import { showToast } from './utils.js';

// Journal state
const journalState = {
    energy: 5,
    mood: 5,
    showMood: false,
    notes: '',
    selectedTags: [],
    recentEntries: [],
    isSubmitting: false
};

// Available tags
const JOURNAL_TAGS = [
    { id: 'work', emoji: '💼', label: 'Work' },
    { id: 'exercise', emoji: '🏃', label: 'Exercise' },
    { id: 'social', emoji: '👥', label: 'Social' },
    { id: 'rest', emoji: '😴', label: 'Rest' },
    { id: 'stress', emoji: '😰', label: 'Stress' },
    { id: 'creative', emoji: '🎨', label: 'Creative' },
    { id: 'focus', emoji: '🎯', label: 'Focus' },
    { id: 'nature', emoji: '🌳', label: 'Nature' }
];

// Energy level descriptions
const ENERGY_LABELS = {
    1: 'Exhausted',
    2: 'Very Low',
    3: 'Low',
    4: 'Below Avg',
    5: 'Average',
    6: 'Above Avg',
    7: 'Good',
    8: 'High',
    9: 'Very High',
    10: 'Peak'
};

// Mood level descriptions
const MOOD_LABELS = {
    1: 'Terrible',
    2: 'Very Bad',
    3: 'Bad',
    4: 'Low',
    5: 'Neutral',
    6: 'Okay',
    7: 'Good',
    8: 'Great',
    9: 'Excellent',
    10: 'Amazing'
};

/**
 * Initialize the journal component
 */
export function initJournal() {
    const container = document.getElementById('journalSection');
    if (!container) return;

    renderJournalComponent(container);
    setupJournalEventListeners();
    loadRecentEntries();
}

/**
 * Render the journal HTML
 */
function renderJournalComponent(container) {
    const now = new Date();
    const timeStr = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    container.innerHTML = `
        <div class="journal-card glass-card">
            <div class="journal-header">
                <div class="journal-title-group">
                    <h3 class="journal-title">
                        <span class="journal-title-icon">📝</span>
                        How are you feeling?
                    </h3>
                    <span class="journal-subtitle">Track your energy and mood</span>
                </div>
                <span class="journal-time">${timeStr}</span>
            </div>

            <div class="journal-body">
                <!-- Energy Slider -->
                <div class="journal-slider-section">
                    <div class="slider-header">
                        <span class="slider-label">
                            <span class="slider-label-icon">⚡</span>
                            Energy Level
                        </span>
                        <div class="slider-value">
                            <span class="slider-value-num" id="energyValueNum">${journalState.energy}</span>
                            <span class="slider-value-max">/10</span>
                        </div>
                    </div>
                    <div class="slider-track">
                        <div class="slider-fill" id="energySliderFill" style="width: ${(journalState.energy - 1) * 11.11}%"></div>
                        <input
                            type="range"
                            class="journal-slider"
                            id="energySlider"
                            min="1"
                            max="10"
                            value="${journalState.energy}"
                        >
                    </div>
                    <div class="emotion-labels">
                        <span class="emotion-label" data-level="low">Exhausted</span>
                        <span class="emotion-label" data-level="mid" id="energyLabel">${ENERGY_LABELS[journalState.energy]}</span>
                        <span class="emotion-label" data-level="high">Peak</span>
                    </div>
                </div>

                <!-- Mood Toggle & Slider -->
                <div class="mood-section">
                    <label class="mood-toggle">
                        <input type="checkbox" class="mood-toggle-checkbox" id="moodToggle">
                        <span class="mood-toggle-track"></span>
                        <span class="mood-toggle-label">Also track mood</span>
                    </label>

                    <div class="mood-slider-container" id="moodSliderContainer">
                        <div class="journal-slider-section">
                            <div class="slider-header">
                                <span class="slider-label">
                                    <span class="slider-label-icon">🎭</span>
                                    Mood Level
                                </span>
                                <div class="slider-value">
                                    <span class="slider-value-num" id="moodValueNum">${journalState.mood}</span>
                                    <span class="slider-value-max">/10</span>
                                </div>
                            </div>
                            <div class="slider-track">
                                <div class="slider-fill" id="moodSliderFill" style="width: ${(journalState.mood - 1) * 11.11}%"></div>
                                <input
                                    type="range"
                                    class="mood-slider"
                                    id="moodSlider"
                                    min="1"
                                    max="10"
                                    value="${journalState.mood}"
                                >
                            </div>
                            <div class="emotion-labels">
                                <span class="emotion-label" data-level="low">Terrible</span>
                                <span class="emotion-label" data-level="mid" id="moodLabel">${MOOD_LABELS[journalState.mood]}</span>
                                <span class="emotion-label" data-level="high">Amazing</span>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Tags -->
                <div class="journal-tags-section">
                    <span class="tags-label">What's happening? (optional)</span>
                    <div class="tags-container" id="tagsContainer">
                        ${JOURNAL_TAGS.map(tag => `
                            <button class="tag-btn" data-tag="${tag.id}">
                                <span class="tag-emoji">${tag.emoji}</span>${tag.label}
                            </button>
                        `).join('')}
                    </div>
                </div>

                <!-- Notes -->
                <div class="journal-notes-section">
                    <label class="notes-label" for="journalNotes">Notes (optional)</label>
                    <textarea
                        class="journal-notes"
                        id="journalNotes"
                        placeholder="How are you feeling? What's on your mind?"
                        rows="3"
                    ></textarea>
                </div>

                <!-- Submit Button -->
                <button class="journal-submit" id="journalSubmit">
                    <span class="journal-submit-text">Log Entry</span>
                    <span class="journal-submit-icon">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M5 12h14M12 5l7 7-7 7"/>
                        </svg>
                    </span>
                </button>
            </div>

            <!-- Recent Entries -->
            <div class="journal-recent" id="journalRecent" style="display: none;">
                <div class="journal-recent-header">
                    <span class="journal-recent-title">Recent entries</span>
                </div>
                <div class="journal-recent-list" id="journalRecentList">
                    <!-- Populated by JS -->
                </div>
            </div>
        </div>
    `;
}

/**
 * Setup event listeners
 */
function setupJournalEventListeners() {
    // Energy slider
    const energySlider = document.getElementById('energySlider');
    if (energySlider) {
        energySlider.addEventListener('input', (e) => {
            journalState.energy = parseInt(e.target.value);
            updateEnergyDisplay();
        });
    }

    // Mood toggle
    const moodToggle = document.getElementById('moodToggle');
    if (moodToggle) {
        moodToggle.addEventListener('change', (e) => {
            journalState.showMood = e.target.checked;
            const container = document.getElementById('moodSliderContainer');
            if (container) {
                container.classList.toggle('visible', journalState.showMood);
            }
        });
    }

    // Mood slider
    const moodSlider = document.getElementById('moodSlider');
    if (moodSlider) {
        moodSlider.addEventListener('input', (e) => {
            journalState.mood = parseInt(e.target.value);
            updateMoodDisplay();
        });
    }

    // Tags
    const tagsContainer = document.getElementById('tagsContainer');
    if (tagsContainer) {
        tagsContainer.addEventListener('click', (e) => {
            const tagBtn = e.target.closest('.tag-btn');
            if (tagBtn) {
                const tagId = tagBtn.dataset.tag;
                toggleTag(tagId);
                tagBtn.classList.toggle('selected');
            }
        });
    }

    // Notes
    const notesInput = document.getElementById('journalNotes');
    if (notesInput) {
        notesInput.addEventListener('input', (e) => {
            journalState.notes = e.target.value;
        });
    }

    // Submit
    const submitBtn = document.getElementById('journalSubmit');
    if (submitBtn) {
        submitBtn.addEventListener('click', submitJournalEntry);
    }
}

/**
 * Update energy display
 */
function updateEnergyDisplay() {
    const valueNum = document.getElementById('energyValueNum');
    const fill = document.getElementById('energySliderFill');
    const label = document.getElementById('energyLabel');

    if (valueNum) valueNum.textContent = journalState.energy;
    if (fill) fill.style.width = `${(journalState.energy - 1) * 11.11}%`;
    if (label) label.textContent = ENERGY_LABELS[journalState.energy];
}

/**
 * Update mood display
 */
function updateMoodDisplay() {
    const valueNum = document.getElementById('moodValueNum');
    const fill = document.getElementById('moodSliderFill');
    const label = document.getElementById('moodLabel');

    if (valueNum) valueNum.textContent = journalState.mood;
    if (fill) fill.style.width = `${(journalState.mood - 1) * 11.11}%`;
    if (label) label.textContent = MOOD_LABELS[journalState.mood];
}

/**
 * Toggle a tag selection
 */
function toggleTag(tagId) {
    const idx = journalState.selectedTags.indexOf(tagId);
    if (idx === -1) {
        journalState.selectedTags.push(tagId);
    } else {
        journalState.selectedTags.splice(idx, 1);
    }
}

/**
 * Submit journal entry
 */
async function submitJournalEntry() {
    if (journalState.isSubmitting) return;

    const submitBtn = document.getElementById('journalSubmit');
    const submitText = submitBtn.querySelector('.journal-submit-text');
    const card = document.querySelector('.journal-card');

    journalState.isSubmitting = true;
    submitBtn.disabled = true;
    submitText.textContent = 'Logging...';

    try {
        const payload = {
            energy: journalState.energy,
            mood: journalState.showMood ? journalState.mood : null,
            notes: journalState.notes.trim() || null,
            tags: journalState.selectedTags
        };

        if (!CONFIG.DEMO_MODE) {
            const response = await fetch(`${CONFIG.API_BASE}/journal/log`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                throw new Error('Failed to log entry');
            }

            const data = await response.json();
            addRecentEntry(data);
        } else {
            // Demo mode - simulate success
            await new Promise(resolve => setTimeout(resolve, 500));
            addRecentEntry({
                id: Date.now(),
                time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
                energy: journalState.energy,
                mood: journalState.showMood ? journalState.mood : null,
                notes: journalState.notes.trim() || null
            });
        }

        // Success animation
        card.classList.add('success');
        setTimeout(() => card.classList.remove('success'), 500);

        // Reset form
        resetJournalForm();
        showToast('Entry logged!', 'success');

    } catch (error) {
        console.error('Failed to log journal entry:', error);
        showToast('Failed to log entry. Try again.', 'error');
    } finally {
        journalState.isSubmitting = false;
        submitBtn.disabled = false;
        submitText.textContent = 'Log Entry';
    }
}

/**
 * Reset the journal form
 */
function resetJournalForm() {
    journalState.energy = 5;
    journalState.mood = 5;
    journalState.notes = '';
    journalState.selectedTags = [];

    const energySlider = document.getElementById('energySlider');
    const moodSlider = document.getElementById('moodSlider');
    const notesInput = document.getElementById('journalNotes');

    if (energySlider) energySlider.value = 5;
    if (moodSlider) moodSlider.value = 5;
    if (notesInput) notesInput.value = '';

    // Deselect all tags
    document.querySelectorAll('.tag-btn.selected').forEach(btn => {
        btn.classList.remove('selected');
    });

    updateEnergyDisplay();
    updateMoodDisplay();
}

/**
 * Load recent entries from API
 */
async function loadRecentEntries() {
    try {
        if (!CONFIG.DEMO_MODE) {
            const response = await fetch(`${CONFIG.API_BASE}/journal/today`);
            if (response.ok) {
                journalState.recentEntries = await response.json();
                renderRecentEntries();
            }
        }
    } catch (error) {
        console.error('Failed to load recent entries:', error);
    }
}

/**
 * Add entry to recent list
 */
function addRecentEntry(entry) {
    journalState.recentEntries.unshift(entry);
    if (journalState.recentEntries.length > 5) {
        journalState.recentEntries.pop();
    }
    renderRecentEntries();
}

/**
 * Render recent entries
 */
function renderRecentEntries() {
    const container = document.getElementById('journalRecent');
    const list = document.getElementById('journalRecentList');

    if (!container || !list) return;

    if (journalState.recentEntries.length === 0) {
        container.style.display = 'none';
        return;
    }

    container.style.display = 'block';

    list.innerHTML = journalState.recentEntries.slice(0, 3).map(entry => `
        <div class="journal-recent-entry">
            <span class="journal-recent-time">${entry.time || formatTime(entry.created_at)}</span>
            <div class="journal-recent-values">
                <span class="journal-recent-value">
                    <span class="value-icon">⚡</span>
                    <span class="value-num">${entry.energy}</span>
                </span>
                ${entry.mood ? `
                    <span class="journal-recent-value">
                        <span class="value-icon">🎭</span>
                        <span class="value-num">${entry.mood}</span>
                    </span>
                ` : ''}
            </div>
            ${entry.notes ? `<span class="journal-recent-note">${entry.notes}</span>` : ''}
        </div>
    `).join('');
}

/**
 * Format ISO timestamp to time string
 */
function formatTime(isoString) {
    if (!isoString) return '';
    const date = new Date(isoString);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

// Export for use in main app
export { journalState, JOURNAL_TAGS, ENERGY_LABELS, MOOD_LABELS };
