// Configuration
const DB_PATH = '../data/jobs-tracker.db';

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
