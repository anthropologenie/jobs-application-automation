// Configuration
const DB_PATH = '../data/jobs-tracker.db';
const API_BASE_URL = 'http://localhost:8081';

// Global sources cache
let allSources = [];

// Initialize dashboard
document.addEventListener('DOMContentLoaded', () => {
  console.log('Dashboard initialized');
  loadDashboard();
  loadSources();

  // Auto-refresh every 15 minutes
  setInterval(loadDashboard, 15 * 60 * 1000);

  // Source dropdown change handler
  const sourceDropdown = document.getElementById('source');
  if (sourceDropdown) {
    sourceDropdown.addEventListener('change', handleSourceChange);
  }
});

// Main loader
async function loadDashboard() {
  try {
    await Promise.all([
      loadMetrics(),
      loadAgenda(),
      loadPipeline(),
      loadArchivedPipeline()
    ]);
    console.log('Dashboard data loaded');
  } catch (error) {
    console.error('Error loading dashboard:', error);
  }
}

// Refresh button
function refreshData() {
  console.log('Manual refresh triggered');
  loadDashboard();
}

// Load job sources dynamically
async function loadSources() {
  try {
    const response = await fetch(`${API_BASE_URL}/api/sources`);
    allSources = await response.json();

    const sourceDropdown = document.getElementById('source');
    if (!sourceDropdown) return;

    // Build dropdown options
    sourceDropdown.innerHTML = allSources.map(src =>
      `<option value="${src.source_name}">${src.source_name}</option>`
    ).join('') + '<option value="__ADD_NEW__">➕ Add New Source...</option>';

    console.log('Sources loaded:', allSources.length);
  } catch (error) {
    console.error('Error loading sources:', error);
    // Fallback to defaults if API fails
    const sourceDropdown = document.getElementById('source');
    if (sourceDropdown) {
      sourceDropdown.innerHTML = `
        <option value="LinkedIn">LinkedIn</option>
        <option value="Naukri">Naukri</option>
        <option value="Direct">Direct</option>
        <option value="Referral">Referral</option>
        <option value="Other">Other</option>
        <option value="__ADD_NEW__">➕ Add New Source...</option>
      `;
    }
  }
}

// Handle source dropdown change
function handleSourceChange(event) {
  const newSourceGroup = document.getElementById('new-source-group');
  const newSourceInput = document.getElementById('new-source-name');

  if (event.target.value === '__ADD_NEW__') {
    newSourceGroup.style.display = 'block';
    newSourceInput.required = true;
    newSourceInput.focus();
  } else {
    newSourceGroup.style.display = 'none';
    newSourceInput.required = false;
    newSourceInput.value = '';
  }
}

// Add new source to database
async function addNewSource(sourceName) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/add-source`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source_name: sourceName })
    });

    const result = await response.json();

    if (response.ok) {
      console.log('New source added:', result);
      await loadSources(); // Reload sources
      return result;
    } else {
      throw new Error(result.error || 'Failed to add source');
    }
  } catch (error) {
    console.error('Error adding source:', error);
    throw error;
  }
}

// Load metrics from database
async function loadMetrics() {
  try {
    const response = await fetch(`${API_BASE_URL}/api/metrics`);
    const metrics = await response.json();

    document.getElementById('active-count').textContent = metrics.active_count || 0;
    document.getElementById('interview-count').textContent = metrics.interview_count || 0;
    document.getElementById('remote-count').textContent = metrics.remote_count || 0;
    document.getElementById('priority-count').textContent = metrics.priority_count || 0;
  } catch (error) {
    console.error('Error loading metrics:', error);
    // Show error state
    document.getElementById('active-count').textContent = '--';
    document.getElementById('interview-count').textContent = '--';
    document.getElementById('remote-count').textContent = '--';
    document.getElementById('priority-count').textContent = '--';
  }
}

// Load today's agenda
async function loadAgenda() {
  try {
    const response = await fetch(`${API_BASE_URL}/api/todays-agenda`);
    const agenda = await response.json();
    renderAgenda(agenda);
  } catch (error) {
    console.error('Error loading agenda:', error);
    document.getElementById('today-agenda').innerHTML =
      '<p class="empty-state">Error loading agenda</p>';
  }
}

function renderAgenda(agenda) {
  const container = document.getElementById('today-agenda');
  
  if (!agenda || agenda.length === 0) {
    container.innerHTML = '<p class="empty-state">No interviews scheduled</p>';
    return;
  }
  
  container.innerHTML = agenda.map(item => `
    <div class="agenda-item">
      <div class="agenda-time">${item.time}</div>
      <div class="agenda-details">
        <div>
          <div class="agenda-company">${item.company}</div>
          <div class="agenda-role">${item.role}</div>
          ${item.meet_link ? `<a href="${item.meet_link}" target="_blank" style="color: #2563eb; text-decoration: none; font-size: 13px;">📹 Join Meeting</a>` : ''}
        </div>
        <span class="agenda-type">${item.type}</span>
      </div>
    </div>
  `).join('');
}

// Load pipeline
async function loadPipeline() {
  try {
    const response = await fetch(`${API_BASE_URL}/api/pipeline`);
    const pipeline = await response.json();
    renderPipeline(pipeline);
  } catch (error) {
    console.error('Error loading pipeline:', error);
    const tbody = document.getElementById('pipeline-body');
    tbody.innerHTML = '<tr><td colspan="7" class="empty-state">Error loading pipeline</td></tr>';
  }
}

function renderPipeline(opportunities) {
  const tbody = document.getElementById('pipeline-body');

  if (!opportunities || opportunities.length === 0) {
    tbody.innerHTML = '<tr><td colspan="8" class="empty-state">No active opportunities</td></tr>';
    return;
  }

  tbody.innerHTML = opportunities.map(opp => `
    <tr data-id="${opp.id}">
      <td><strong>${opp.company}</strong></td>
      <td>${opp.role}</td>
      <td>
        <select class="status-dropdown" onchange="updateStatus(${opp.id}, this.value)" data-original="${opp.status}">
          <option value="Lead" ${opp.status === 'Lead' ? 'selected' : ''}>Lead</option>
          <option value="Applied" ${opp.status === 'Applied' ? 'selected' : ''}>Applied</option>
          <option value="Screening" ${opp.status === 'Screening' ? 'selected' : ''}>Screening</option>
          <option value="Technical" ${opp.status === 'Technical' ? 'selected' : ''}>Technical</option>
          <option value="Manager" ${opp.status === 'Manager' ? 'selected' : ''}>Manager</option>
          <option value="Offer" ${opp.status === 'Offer' ? 'selected' : ''}>Offer</option>
          <option value="Rejected" ${opp.status === 'Rejected' ? 'selected' : ''}>Rejected</option>
          <option value="Declined" ${opp.status === 'Declined' ? 'selected' : ''}>Declined</option>
          <option value="Ghosted" ${opp.status === 'Ghosted' ? 'selected' : ''}>Ghosted</option>
          <option value="Accepted" ${opp.status === 'Accepted' ? 'selected' : ''}>Accepted</option>
        </select>
      </td>
      <td class="remote-badge">
        <span onclick="toggleRemote(${opp.id}, ${opp.is_remote ? 0 : 1})" style="cursor: pointer; font-size: 18px;" title="Click to toggle">
          ${opp.is_remote ? '✅' : '❌'}
        </span>
      </td>
      <td class="priority-${opp.priority.toLowerCase()}">${opp.priority}</td>
      <td>${opp.tech_stack || 'N/A'}</td>
      <td>${formatDate(opp.updated_at)}</td>
      <td>
        <button onclick="openNotesModal(${opp.id}, '${opp.company.replace(/'/g, "\\'")}', '${(opp.notes || '').replace(/'/g, "\\'").replace(/\n/g, '\\n')}')" class="btn-icon" title="Edit Notes">✏️</button>
        <button onclick="archiveOpportunity(${opp.id})" class="btn-icon" title="Archive">📦</button>
      </td>
    </tr>
  `).join('');
}

// Modal functions
function showAddModal() {
  document.getElementById('add-modal').style.display = 'block';
}

function closeAddModal() {
  document.getElementById('add-modal').style.display = 'none';
  document.getElementById('add-form').reset();
}

// Add new opportunity
async function addOpportunity(event) {
  event.preventDefault();

  let sourceValue = document.getElementById('source').value;

  // Handle adding new source
  if (sourceValue === '__ADD_NEW__') {
    const newSourceName = document.getElementById('new-source-name').value.trim();

    if (!newSourceName) {
      alert('Please enter a source name');
      return;
    }

    try {
      const result = await addNewSource(newSourceName);
      sourceValue = newSourceName;
      console.log('New source created:', result);
    } catch (error) {
      alert(`Failed to add new source: ${error.message}`);
      return;
    }
  }

  const formData = {
    company: document.getElementById('company').value,
    role: document.getElementById('role').value,
    source: sourceValue,
    is_remote: document.getElementById('is_remote').checked ? 1 : 0,
    tech_stack: document.getElementById('tech_stack').value,
    recruiter_contact: document.getElementById('recruiter_contact').value,
    notes: document.getElementById('notes').value,
    status: 'Lead',
    priority: document.getElementById('is_remote').checked ? 'High' : 'Medium'
  };

  console.log('Adding opportunity:', formData);

  try {
    const response = await fetch(`${API_BASE_URL}/api/add-opportunity`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(formData)
    });

    const result = await response.json();

    if (response.ok) {
      alert(`✅ Opportunity added successfully! (ID: ${result.id})`);
      closeAddModal();
      loadDashboard(); // Refresh data
    } else {
      alert(`❌ Error: ${result.error}`);
    }
  } catch (error) {
    console.error('Error adding opportunity:', error);
    alert('❌ Failed to add opportunity. Check if API server is running.');
  }
}

// Helper functions
function formatDate(dateString) {
  if (!dateString) return 'N/A';
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now - date;
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
  
  if (diffDays === 0) return 'Today';
  if (diffDays === 1) return 'Yesterday';
  if (diffDays < 7) return `${diffDays} days ago`;
  return date.toLocaleDateString('en-IN');
}

// Close modal when clicking outside
window.onclick = function(event) {
  const modal = document.getElementById('add-modal');
  if (event.target === modal) {
    closeAddModal();
  }
}

// ============================================================================
// SACRED WORK FUNCTIONS
// ============================================================================

async function loadSacredWorkStats() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/sacred-work-stats`);
        const stats = await response.json();

        document.getElementById('total-stones').textContent = stats.total_stones || 0;
        document.getElementById('total-sacred-hours').textContent = stats.total_hours || 0;
        document.getElementById('avg-stone-time').textContent = Math.round(stats.avg_minutes_per_stone || 0);

        if (stats.first_stone_date) {
            const first = new Date(stats.first_stone_date);
            const now = new Date();
            const days = Math.floor((now - first) / (1000 * 60 * 60 * 24)) + 1;
            document.getElementById('days-building').textContent = days;
        } else {
            document.getElementById('days-building').textContent = 0;
        }
    } catch (error) {
        console.error('Failed to load sacred work stats:', error);
    }
}

async function loadSacredWorkProgress() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/sacred-work-progress`);
        const stones = await response.json();

        const stonesList = document.getElementById('stones-list');

        if (stones.length === 0) {
            stonesList.innerHTML = '<p style="text-align: center; color: #888; padding: 2rem;">No stones placed yet. Begin with Stone 1.</p>';
            return;
        }

        stonesList.innerHTML = '';

        stones.forEach(stone => {
            const stoneCard = document.createElement('div');
            stoneCard.className = 'stone-card';
            const statusClass = stone.status === 'Complete' ? 'status-complete' : 'status-progress';

            stoneCard.innerHTML = `
                <div class="stone-header">
                    <div class="stone-number">Stone ${stone.stone_number}</div>
                    <div class="stone-status ${statusClass}">${stone.status}</div>
                </div>
                <div class="stone-title">${stone.stone_title}</div>
                <div class="stone-meta">
                    <span class="stone-date">📅 ${stone.date}</span>
                    <span class="stone-duration">⏱️ ${stone.time_spent_minutes} min</span>
                </div>
                <div class="stone-what-built">${stone.what_built}</div>
                ${stone.insights ? `<div class="stone-insights"><strong>💡 Insights:</strong> ${stone.insights}</div>` : ''}
            `;
            stonesList.appendChild(stoneCard);
        });
    } catch (error) {
        console.error('Failed to load sacred work progress:', error);
    }
}

document.addEventListener('DOMContentLoaded', function() {
    const sacredWorkForm = document.getElementById('sacred-work-form');

    if (sacredWorkForm) {
        sacredWorkForm.addEventListener('submit', async (e) => {
            e.preventDefault();

            const data = {
                stone_number: parseInt(document.getElementById('stone-number').value),
                stone_title: document.getElementById('stone-title').value,
                time_spent_minutes: parseInt(document.getElementById('stone-time').value),
                what_built: document.getElementById('what-built').value,
                insights: document.getElementById('insights').value || null,
                next_stone: document.getElementById('next-stone').value || null,
                felt_sense: document.getElementById('felt-sense').value || null
            };

            try {
                const response = await fetch(`${API_BASE_URL}/api/add-sacred-work`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });

                const result = await response.json();

                if (response.ok) {
                    alert(`Sacred stone ${data.stone_number} placed! 🌺`);
                    sacredWorkForm.reset();
                    loadSacredWorkStats();
                    loadSacredWorkProgress();
                } else {
                    alert(result.error || 'Failed to place stone');
                }
            } catch (error) {
                alert('Network error: ' + error.message);
            }
        });
    }

    // Tab switching logic
    const tabLinks = document.querySelectorAll('.tab-link');
    tabLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();

            // Get target tab ID
            const tabId = e.target.getAttribute('href').substring(1);

            // Remove active class from all links
            tabLinks.forEach(l => l.classList.remove('active'));

            // Add active class to clicked link
            e.target.classList.add('active');

            // Hide all tab contents
            document.querySelectorAll('.tab-content').forEach(content => {
                content.style.display = 'none';
            });

            // Show target tab content
            const targetTab = document.getElementById(tabId);
            if (targetTab) {
                targetTab.style.display = 'block';
            }

            // Load sacred work data if switching to that tab
            if (tabId === 'sacred-work') {
                loadSacredWorkStats();
                loadSacredWorkProgress();
            }

            // Load scraped jobs data if switching to job-matches tab
            if (tabId === 'job-matches') {
                loadScrapedJobs();
            }
        });
    });
});

// ============================================================================
// ARCHIVED PIPELINE FUNCTIONS
// ============================================================================

async function loadArchivedPipeline() {
  try {
    const response = await fetch(`${API_BASE_URL}/api/archived-pipeline`);
    const archived = await response.json();
    renderArchivedPipeline(archived);
  } catch (error) {
    console.error('Error loading archived pipeline:', error);
    const tbody = document.getElementById('archived-body');
    tbody.innerHTML = '<tr><td colspan="7" class="empty-state">Error loading archived opportunities</td></tr>';
  }
}

function renderArchivedPipeline(opportunities) {
  const tbody = document.getElementById('archived-body');

  if (!opportunities || opportunities.length === 0) {
    tbody.innerHTML = '<tr><td colspan="8" class="empty-state">No archived opportunities</td></tr>';
    return;
  }

  tbody.innerHTML = opportunities.map(opp => `
    <tr data-id="${opp.id}">
      <td><strong>${opp.company}</strong></td>
      <td>${opp.role}</td>
      <td>
        <select class="status-dropdown" onchange="updateStatus(${opp.id}, this.value)" data-original="${opp.status}">
          <option value="Lead" ${opp.status === 'Lead' ? 'selected' : ''}>Lead</option>
          <option value="Applied" ${opp.status === 'Applied' ? 'selected' : ''}>Applied</option>
          <option value="Screening" ${opp.status === 'Screening' ? 'selected' : ''}>Screening</option>
          <option value="Technical" ${opp.status === 'Technical' ? 'selected' : ''}>Technical</option>
          <option value="Manager" ${opp.status === 'Manager' ? 'selected' : ''}>Manager</option>
          <option value="Offer" ${opp.status === 'Offer' ? 'selected' : ''}>Offer</option>
          <option value="Rejected" ${opp.status === 'Rejected' ? 'selected' : ''}>Rejected</option>
          <option value="Declined" ${opp.status === 'Declined' ? 'selected' : ''}>Declined</option>
          <option value="Ghosted" ${opp.status === 'Ghosted' ? 'selected' : ''}>Ghosted</option>
          <option value="Accepted" ${opp.status === 'Accepted' ? 'selected' : ''}>Accepted</option>
        </select>
      </td>
      <td class="remote-badge">
        <span onclick="toggleRemote(${opp.id}, ${opp.is_remote ? 0 : 1})" style="cursor: pointer; font-size: 18px;" title="Click to toggle">
          ${opp.is_remote ? '✅' : '❌'}
        </span>
      </td>
      <td class="priority-${opp.priority.toLowerCase()}">${opp.priority}</td>
      <td>${opp.tech_stack || 'N/A'}</td>
      <td>${formatDate(opp.updated_at)}</td>
      <td>
        <button onclick="openNotesModal(${opp.id}, '${opp.company.replace(/'/g, "\\'")}', '${(opp.notes || '').replace(/'/g, "\\'").replace(/\n/g, '\\n')}')" class="btn-icon" title="Edit Notes">✏️</button>
        <button onclick="deleteOpportunity(${opp.id})" class="btn-icon" title="Delete">🗑️</button>
      </td>
    </tr>
  `).join('');
}

// ============================================================================
// INLINE EDITING FUNCTIONS
// ============================================================================

async function updateStatus(oppId, newStatus) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/update-opportunity/${oppId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: newStatus })
    });

    const result = await response.json();

    if (response.ok) {
      console.log('Status updated successfully:', result);
      showToast(`Status updated to ${newStatus}`, 'success');
      // Reload pipelines to show changes
      await Promise.all([loadPipeline(), loadArchivedPipeline(), loadMetrics()]);
    } else {
      showToast(`Error updating status: ${result.error}`, 'error');
      // Revert dropdown
      loadPipeline();
    }
  } catch (error) {
    console.error('Error updating status:', error);
    showToast('Failed to update status. Check if API server is running.', 'error');
    loadPipeline();
  }
}

async function toggleRemote(oppId, newValue) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/update-opportunity/${oppId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ is_remote: newValue })
    });

    const result = await response.json();

    if (response.ok) {
      console.log('Remote status updated successfully:', result);
      showToast(`Remote status updated to ${newValue ? 'Remote' : 'On-site'}`, 'success');
      // Reload pipeline to show changes
      await Promise.all([loadPipeline(), loadArchivedPipeline()]);
    } else {
      showToast(`Error updating remote status: ${result.error}`, 'error');
    }
  } catch (error) {
    console.error('Error updating remote status:', error);
    showToast('Failed to update remote status. Check if API server is running.', 'error');
  }
}

async function archiveOpportunity(oppId) {
  if (!confirm('Archive this opportunity? It will move to the Archived Pipeline section.')) {
    return;
  }

  try {
    const response = await fetch(`${API_BASE_URL}/api/update-opportunity/${oppId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: 'Declined' })
    });

    const result = await response.json();

    if (response.ok) {
      showToast('Opportunity archived successfully!', 'success');
      // Reload both pipelines
      await Promise.all([loadPipeline(), loadArchivedPipeline()]);
    } else {
      showToast(`Error archiving opportunity: ${result.error}`, 'error');
    }
  } catch (error) {
    console.error('Error archiving opportunity:', error);
    showToast('Failed to archive opportunity. Check if API server is running.', 'error');
  }
}

async function deleteOpportunity(oppId) {
  if (!confirm('⚠️ DELETE this opportunity permanently? This cannot be undone!')) {
    return;
  }

  // Note: Since we don't have a DELETE endpoint, we'll just mark it as Declined
  // In the future, you could add a DELETE endpoint to api-server.py
  showToast('Delete functionality requires a DELETE endpoint. For now, archive the opportunity instead.', 'error');
}

// ============================================================================
// TOAST NOTIFICATION SYSTEM
// ============================================================================

function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;

  const icon = type === 'success' ? '✅' : type === 'error' ? '❌' : 'ℹ️';
  toast.innerHTML = `
    <span class="toast-icon">${icon}</span>
    <span class="toast-message">${message}</span>
  `;

  container.appendChild(toast);

  // Trigger animation
  setTimeout(() => toast.classList.add('show'), 10);

  // Auto-remove after 4 seconds
  setTimeout(() => {
    toast.classList.remove('show');
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// ============================================================================
// NOTES MODAL FUNCTIONS
// ============================================================================

function openNotesModal(oppId, company, notes) {
  document.getElementById('notes-modal').style.display = 'block';
  document.getElementById('notes-opp-id').value = oppId;
  document.getElementById('notes-company').value = company;
  document.getElementById('notes-text').value = notes || '';
}

function closeNotesModal() {
  document.getElementById('notes-modal').style.display = 'none';
  document.getElementById('notes-form').reset();
}

async function saveNotes(event) {
  event.preventDefault();

  const oppId = document.getElementById('notes-opp-id').value;
  const notes = document.getElementById('notes-text').value;

  try {
    const response = await fetch(`${API_BASE_URL}/api/update-opportunity/${oppId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ notes: notes })
    });

    const result = await response.json();

    if (response.ok) {
      showToast('Notes saved successfully!', 'success');
      closeNotesModal();
      // Reload pipeline to show updated data
      await Promise.all([loadPipeline(), loadArchivedPipeline()]);
    } else {
      showToast(`Error saving notes: ${result.error}`, 'error');
    }
  } catch (error) {
    console.error('Error saving notes:', error);
    showToast('Failed to save notes. Check if API server is running.', 'error');
  }
}

// Close modals on outside click
window.onclick = function(event) {
  const addModal = document.getElementById('add-modal');
  const notesModal = document.getElementById('notes-modal');

  if (event.target === addModal) {
    closeAddModal();
  }
  if (event.target === notesModal) {
    closeNotesModal();
  }
}

// ============================================================================
// JOB MATCHES FUNCTIONALITY
// ============================================================================

async function loadScrapedJobs() {
  const minScore = document.getElementById('score-filter')?.value || 60;

  try {
    const response = await fetch(`${API_BASE_URL}/api/scraped-jobs?min_score=${minScore}&limit=100`);
    const data = await response.json();

    if (data.success) {
      renderScrapedJobs(data.jobs);
      await loadScrapedJobsStats();
      document.getElementById('jobs-count').textContent = `${data.count} jobs loaded`;
    } else {
      console.error('Failed to load scraped jobs:', data.error);
      showErrorMessage('Failed to load jobs');
    }
  } catch (error) {
    console.error('Error loading scraped jobs:', error);
    showErrorMessage('Error connecting to API');
  }
}

async function loadScrapedJobsStats() {
  try {
    const response = await fetch(`${API_BASE_URL}/api/scraped-jobs/stats`);
    const data = await response.json();

    if (data.success) {
      const stats = data.stats;
      document.getElementById('scraped-total').textContent = stats.total_jobs || 0;
      document.getElementById('scraped-excellent').textContent = stats.excellent || 0;

      // High fit includes both excellent and high_fit
      const totalHighFit = (stats.excellent || 0) + (stats.high_fit || 0);
      document.getElementById('scraped-high-fit').textContent = totalHighFit;

      document.getElementById('scraped-medium').textContent = stats.medium_fit || 0;

      const avgScore = stats.avg_score ? stats.avg_score.toFixed(1) : '0';
      document.getElementById('scraped-avg-score').textContent = avgScore + '%';
    }
  } catch (error) {
    console.error('Error loading stats:', error);
  }
}

function renderScrapedJobs(jobs) {
  const tbody = document.getElementById('scraped-jobs-body');

  if (!jobs || jobs.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="7" style="padding: 40px; text-align: center; color: #666;">
          No jobs found matching your criteria.<br>
          <small>Try lowering the minimum score filter or run the scraper to get new jobs.</small>
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = jobs.map(job => {
    // Determine score styling
    let scoreColor, scoreBg, scoreLabel;
    if (job.match_score >= 85) {
      scoreColor = '#155724'; scoreBg = '#d4edda'; scoreLabel = 'EXCELLENT';
    } else if (job.match_score >= 75) {
      scoreColor = '#0c5460'; scoreBg = '#d1ecf1'; scoreLabel = 'HIGH_FIT';
    } else if (job.match_score >= 65) {
      scoreColor = '#856404'; scoreBg = '#fff3cd'; scoreLabel = 'MEDIUM';
    } else if (job.match_score >= 40) {
      scoreColor = '#856404'; scoreBg = '#ffeaa7'; scoreLabel = 'LOW_FIT';
    } else {
      scoreColor = '#721c24'; scoreBg = '#f8d7da'; scoreLabel = 'NO_FIT';
    }

    // Parse matched skills from JSON string
    let matchedSkills = [];
    try {
      matchedSkills = JSON.parse(job.matched_skills || '[]');
    } catch (e) {
      matchedSkills = [];
    }

    // Format matched skills (show first 3)
    const skillsList = matchedSkills.map(s => s.skill || s);
    const skillsPreview = skillsList.slice(0, 3).join(', ');
    const skillsTooltip = skillsList.join(', ');
    const moreSkills = skillsList.length > 3 ? ` (+${skillsList.length - 3} more)` : '';

    // Parse red flags from JSON string
    let redFlags = [];
    try {
      redFlags = JSON.parse(job.red_flags || '[]');
    } catch (e) {
      redFlags = [];
    }

    // Format red flags
    const redFlagsCount = redFlags.length;
    const redFlagsTooltip = redFlags.map(f => f.flag || f).join(', ');
    const redFlagsDisplay = redFlagsCount > 0
      ? `<span style="color: #dc3545; cursor: help;" title="${redFlagsTooltip}">⚠️ ${redFlagsCount}</span>`
      : '<span style="color: #28a745;">✅</span>';

    return `
      <tr style="border-bottom: 1px solid #dee2e6;">
        <td style="padding: 12px;">
          <div style="background: ${scoreBg}; color: ${scoreColor}; padding: 8px; border-radius: 6px; text-align: center; min-width: 80px;">
            <strong style="font-size: 18px; display: block;">${job.match_score}%</strong>
            <small style="font-size: 11px; text-transform: uppercase;">${scoreLabel}</small>
          </div>
        </td>
        <td style="padding: 12px;">
          <strong style="color: #333;">${job.company}</strong>
          <br>
          <small style="color: #666; font-size: 12px;">📍 ${job.source}</small>
        </td>
        <td style="padding: 12px;">
          <div style="font-weight: 500; color: #333; margin-bottom: 4px;">${job.job_title}</div>
          ${job.salary_range ? `<small style="color: #28a745; font-weight: 500;">💰 ${job.salary_range}</small>` : ''}
        </td>
        <td style="padding: 12px;">
          <span style="color: #666;">${job.location || 'Remote'}</span>
        </td>
        <td style="padding: 12px;" title="${skillsTooltip}">
          ${skillsPreview || '<span style="color: #999;">None matched</span>'}
          ${moreSkills ? `<br><small style="color: #666;">${moreSkills}</small>` : ''}
        </td>
        <td style="padding: 12px; text-align: center;">
          ${redFlagsDisplay}
        </td>
        <td style="padding: 12px;">
          <div style="display: flex; gap: 8px; flex-direction: column;">
            <button onclick="window.open('${job.job_url}', '_blank')"
                    style="padding: 6px 12px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 13px; font-weight: 500;">
              🔗 View Job
            </button>
            ${!job.imported_to_opportunities ? `
              <button onclick="importScrapedJob(${job.id}, '${job.company.replace(/'/g, "\\'")}', '${job.job_title.replace(/'/g, "\\'")}')"
                      style="padding: 6px 12px; background: #28a745; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 13px; font-weight: 500;">
                ➕ Import
              </button>
            ` : '<span style="color: #28a745; font-size: 13px; font-weight: 500;">✓ Imported</span>'}
          </div>
        </td>
      </tr>
    `;
  }).join('');
}

function runScraper() {
  const message = `To scrape new jobs, run this command in your terminal:

python3 scrapers/remoteok_integration.py

After scraping completes, click "Refresh Jobs" to see the new results.`;

  alert(message);
}

function importScrapedJob(jobId, company, title) {
  // Placeholder for import functionality
  const message = `Import functionality coming soon!

This will add:
${company} - ${title}

...to your opportunities pipeline.`;

  alert(message);
}

function showErrorMessage(message) {
  console.error(message);
  const tbody = document.getElementById('scraped-jobs-body');
  if (tbody) {
    tbody.innerHTML = `
      <tr>
        <td colspan="7" style="padding: 40px; text-align: center; color: #dc3545;">
          ❌ ${message}
        </td>
      </tr>
    `;
  }
}

// Add event listener for score filter changes (must run after DOM is loaded)
document.addEventListener('DOMContentLoaded', function() {
  const scoreFilter = document.getElementById('score-filter');
  if (scoreFilter) {
    scoreFilter.addEventListener('change', loadScrapedJobs);
  }
});
