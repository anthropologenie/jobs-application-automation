// Configuration
const DB_PATH = '../data/jobs-tracker.db';
const API_BASE_URL = 'http://localhost:8081';

// Initialize dashboard
document.addEventListener('DOMContentLoaded', () => {
  console.log('Dashboard initialized');
  loadDashboard();
  
  // Auto-refresh every 15 minutes
  setInterval(loadDashboard, 15 * 60 * 1000);
});

// Main loader
async function loadDashboard() {
  try {
    await Promise.all([
      loadMetrics(),
      loadAgenda(),
      loadPipeline()
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

// Load metrics from database
async function loadMetrics() {
  // Direct SQLite queries (will be replaced with n8n webhooks later)
  try {
    // For now, use placeholder data since we can't directly query SQLite from browser
    // These will be replaced with n8n webhook calls
    
    // Simulated data - replace with actual webhook calls
    document.getElementById('active-count').textContent = '8';
    document.getElementById('interview-count').textContent = '3';
    document.getElementById('remote-count').textContent = '6';
    document.getElementById('priority-count').textContent = '4';
  } catch (error) {
    console.error('Error loading metrics:', error);
  }
}

// Load today's agenda
async function loadAgenda() {
  try {
    // This will call n8n webhook: /webhook/todays-agenda
    // For now, use test data
    
    const testAgenda = [
      {
        time: '10:00 AM',
        company: 'Company A',
        role: 'QA Lead',
        type: 'Screening',
        meet_link: null
      },
      {
        time: '02:00 PM',
        company: 'Company B',
        role: 'ETL Test Engineer',
        type: 'Technical',
        meet_link: null
      }
    ];
    
    renderAgenda(testAgenda);
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
    // This will call n8n webhook: /webhook/pipeline
    // For now, use test data
    
    const testPipeline = [
      {
        id: 1,
        company: 'Company A',
        role: 'QA Lead',
        status: 'Screening',
        is_remote: 1,
        priority: 'High',
        tech_stack: 'AWS, Python, ETL',
        updated_at: new Date().toISOString()
      },
      {
        id: 2,
        company: 'Company B',
        role: 'ETL Test Engineer',
        status: 'Technical',
        is_remote: 1,
        priority: 'High',
        tech_stack: 'Snowflake, AWS Glue',
        updated_at: new Date(Date.now() - 86400000).toISOString()
      },
      {
        id: 3,
        company: 'Company C',
        role: 'Senior QA Automation',
        status: 'Screening',
        is_remote: 1,
        priority: 'Medium',
        tech_stack: 'Python, Selenium',
        updated_at: new Date(Date.now() - 43200000).toISOString()
      },
      {
        id: 4,
        company: 'TechCorp India',
        role: 'QA Lead',
        status: 'Lead',
        is_remote: 1,
        priority: 'High',
        tech_stack: 'AWS',
        updated_at: new Date().toISOString()
      },
      {
        id: 5,
        company: 'CloudFirst Solutions',
        role: 'ETL Testing Specialist',
        status: 'Lead',
        is_remote: 1,
        priority: 'High',
        tech_stack: 'Snowflake',
        updated_at: new Date().toISOString()
      }
    ];
    
    renderPipeline(testPipeline);
  } catch (error) {
    console.error('Error loading pipeline:', error);
  }
}

function renderPipeline(opportunities) {
  const tbody = document.getElementById('pipeline-body');
  
  if (!opportunities || opportunities.length === 0) {
    tbody.innerHTML = '<tr><td colspan="7" class="empty-state">No active opportunities</td></tr>';
    return;
  }
  
  tbody.innerHTML = opportunities.map(opp => `
    <tr>
      <td><strong>${opp.company}</strong></td>
      <td>${opp.role}</td>
      <td><span class="status-badge status-${opp.status.toLowerCase()}">${opp.status}</span></td>
      <td class="remote-badge">${opp.is_remote ? '✅' : '❌'}</td>
      <td class="priority-${opp.priority.toLowerCase()}">${opp.priority}</td>
      <td>${opp.tech_stack || 'N/A'}</td>
      <td>${formatDate(opp.updated_at)}</td>
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
  
  const formData = {
    company: document.getElementById('company').value,
    role: document.getElementById('role').value,
    source: document.getElementById('source').value,
    is_remote: document.getElementById('is_remote').checked ? 1 : 0,
    tech_stack: document.getElementById('tech_stack').value,
    recruiter_phone: document.getElementById('recruiter_phone').value,
    notes: document.getElementById('notes').value,
    status: 'Lead',
    priority: document.getElementById('is_remote').checked ? 'High' : 'Medium'
  };
  
  console.log('Adding opportunity:', formData);
  
  // This will call n8n webhook: /webhook/add-opportunity
  // For now, just show success message
  alert('Opportunity added! (Will integrate with n8n webhook)');
  closeAddModal();
  
  // Refresh dashboard
  loadDashboard();
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
        });
    });
});
