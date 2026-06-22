const API_BASE = window.location.origin;

function getToken() {
  return localStorage.getItem('diabetescare_token');
}

function getUser() {
  const raw = localStorage.getItem('diabetescare_user');
  return raw ? JSON.parse(raw) : null;
}

function setAuth(token, user) {
  localStorage.setItem('diabetescare_token', token);
  localStorage.setItem('diabetescare_user', JSON.stringify(user));
}

function clearAuth() {
  localStorage.removeItem('diabetescare_token');
  localStorage.removeItem('diabetescare_user');
}

async function apiRequest(method, path, body) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json' }
  };
  const token = getToken();
  if (token) {
    opts.headers['Authorization'] = `Bearer ${token}`;
  }
  if (body) {
    opts.body = JSON.stringify(body);
  }
  const resp = await fetch(`${API_BASE}${path}`, opts);
  if (resp.status === 401 && !window.location.pathname.includes('index.html')) {
    clearAuth();
    window.location.href = '/static/index.html';
    throw new Error('Unauthorized');
  }
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    const msg = Array.isArray(err.detail) ? err.detail[0]?.msg || err.detail[0] : err.detail;
    throw new Error(msg || 'Request failed');
  }
  return resp.json();
}

function get(path, params) {
  const qs = params ? '?' + new URLSearchParams(params).toString() : '';
  return apiRequest('GET', path + qs);
}

function post(path, body) {
  return apiRequest('POST', path, body);
}

function del(path) {
  return apiRequest('DELETE', path);
}

function localDatetimeString() {
  const now = new Date();
  const pad = (n) => n.toString().padStart(2, '0');
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}T${pad(now.getHours())}:${pad(now.getMinutes())}`;
}

function formatDateTime(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function formatDate(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleDateString();
}

function formatTime(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function getEntryBadge(type) {
  const labels = { glucose: 'Glucose', meal: 'Meal', medication: 'Medication', exercise: 'Exercise' };
  return `<span class="entry-type-badge badge-${type}">${labels[type] || type}</span>`;
}

function glucoseClass(value) {
  if (value < 70) return 'glucose-low';
  if (value > 180) return 'glucose-high';
  if (value > 140) return 'glucose-borderline';
  return 'glucose-normal';
}

function requireAuth() {
  if (!getToken()) {
    window.location.href = '/static/index.html';
  }
}

function requireAdmin() {
  requireAuth();
  const user = getUser();
  if (!user || user.role !== 'admin') {
    window.location.href = '/static/dashboard.html';
  }
}

function setupLogout() {
  const btn = document.getElementById('logoutBtn');
  if (btn) {
    btn.addEventListener('click', () => {
      clearAuth();
      window.location.href = '/static/index.html';
    });
  }
}

function formatFileSize(bytes) {
  if (bytes === 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return (bytes / Math.pow(1024, i)).toFixed(1) + ' ' + units[i];
}

const FILE_TYPE_ICONS = {
  pdf: '📄',
  image: '🖼️',
  video: '🎬',
  word: '📝',
};

function getFileTypeIcon(fileType) {
  return FILE_TYPE_ICONS[fileType] || '📁';
}

function esc(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}
