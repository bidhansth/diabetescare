document.addEventListener('DOMContentLoaded', () => {
  requireAdmin();
  setupLogout();

  const tabResources = document.getElementById('tabResources');
  const tabUsers = document.getElementById('tabUsers');
  const resSection = document.getElementById('resourcesSection');
  const usersSection = document.getElementById('usersSection');

  function showTab(section) {
    resSection.classList.toggle('d-none', section !== 'resources');
    usersSection.classList.toggle('d-none', section !== 'users');
    tabResources.classList.toggle('active', section === 'resources');
    tabUsers.classList.toggle('active', section === 'users');
    tabResources.classList.toggle('nav-link', true);
    tabUsers.classList.toggle('nav-link', true);
  }

  tabResources.addEventListener('click', (e) => { e.preventDefault(); showTab('resources'); });
  tabUsers.addEventListener('click', (e) => { e.preventDefault(); showTab('users'); loadUsers(); });

  // ── Storage health check ──
  const warningEl = document.getElementById('storageWarning');

  async function checkStorage() {
    try {
      const status = await get('/api/admin/storage-status');
      if (status.backend !== 's3') {
        warningEl.className = 'alert alert-danger';
        warningEl.textContent = 'Storage is set to "' + status.backend + '". Resources will not persist on EC2. Set STORAGE_BACKEND=s3 and configure an S3 bucket.';
        warningEl.classList.remove('d-none');
      } else if (!status.healthy) {
        warningEl.className = 'alert alert-danger';
        warningEl.textContent = 'S3 is misconfigured: ' + status.message + '. Uploads will fail until this is fixed.';
        warningEl.classList.remove('d-none');
      } else {
        warningEl.classList.add('d-none');
      }
    } catch (err) {
      // silently ignore — the page should still work
    }
  }

  async function loadUsers() {
    const loadingEl = document.getElementById('loadingUsers');
    const tableContainer = document.getElementById('usersTableContainer');
    const noUsers = document.getElementById('noUsers');
    const tbody = document.getElementById('usersBody');

    loadingEl.classList.remove('d-none');
    tableContainer.classList.add('d-none');
    noUsers.classList.add('d-none');

    try {
      const users = await get('/api/admin/users');
      loadingEl.classList.add('d-none');

      if (users.length === 0) {
        noUsers.classList.remove('d-none');
        return;
      }

      tableContainer.classList.remove('d-none');
      tbody.innerHTML = '';
      users.forEach(u => {
        const isAdmin = u.role === 'admin';
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td>${u.name}</td>
          <td>${u.email}</td>
          <td><span class="badge ${isAdmin ? 'bg-success' : 'bg-secondary'}">${u.role}</span></td>
          <td>${formatDate(u.createdAt)}</td>
          <td>
            ${isAdmin ? '' : `<button class="btn btn-sm btn-outline-success promote-btn" data-id="${u.userId}">Promote</button>`}
          </td>
        `;
        tbody.appendChild(tr);
      });

      tbody.querySelectorAll('.promote-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
          try {
            await apiRequest('PATCH', `/api/admin/users/${btn.dataset.id}/role`);
            loadUsers();
          } catch (err) {
            alert(err.message);
          }
        });
      });
    } catch (err) {
      loadingEl.innerHTML = `<span class="text-danger">${err.message}</span>`;
    }
  }

  const uploadForm = document.getElementById('uploadForm');
  const uploadError = document.getElementById('uploadError');

  uploadForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    uploadError.classList.add('d-none');

    const name = document.getElementById('resName').value.trim();
    const description = document.getElementById('resDescription').value.trim();
    const fileInput = document.getElementById('resFile');
    const file = fileInput.files[0];

    if (!name || !file) return;

    const formData = new FormData();
    formData.append('name', name);
    formData.append('description', description);
    formData.append('file', file);

    document.getElementById('uploadBtn').disabled = true;
    try {
      const token = getToken();
      const resp = await fetch('/api/resources', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body: formData,
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: 'Upload failed' }));
        throw new Error(err.detail || 'Upload failed');
      }
      uploadForm.reset();
      loadResources();
    } catch (err) {
      uploadError.textContent = err.message;
      uploadError.classList.remove('d-none');
    } finally {
      document.getElementById('uploadBtn').disabled = false;
    }
  });

  async function loadResources() {
    const loadingEl = document.getElementById('loadingResources');
    const tableContainer = document.getElementById('resTableContainer');
    const noResources = document.getElementById('noResources');
    const tbody = document.getElementById('resBody');

    loadingEl.classList.remove('d-none');
    tableContainer.classList.add('d-none');
    noResources.classList.add('d-none');

    try {
      const resources = await get('/api/resources');
      loadingEl.classList.add('d-none');

      if (resources.length === 0) {
        noResources.classList.remove('d-none');
        return;
      }

      tableContainer.classList.remove('d-none');
      tbody.innerHTML = '';
      resources.forEach(r => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td style="font-size:1.4rem;">${getFileTypeIcon(r.fileType)}</td>
          <td>${r.name}</td>
          <td><span class="badge bg-info">${r.fileType}</span></td>
          <td>${formatFileSize(r.fileSize)}</td>
          <td>${r.downloadCount}</td>
          <td>${formatDateTime(r.uploadedAt)}</td>
          <td><button class="btn btn-sm btn-outline-danger delete-btn" data-id="${r.resourceId}">Delete</button></td>
        `;
        tbody.appendChild(tr);
      });

      tbody.querySelectorAll('.delete-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
          if (!confirm('Delete this resource?')) return;
          try {
            await del(`/api/resources/${btn.dataset.id}`);
            loadResources();
          } catch (err) {
            alert(err.message);
          }
        });
      });
    } catch (err) {
      loadingEl.innerHTML = `<span class="text-danger">${err.message}</span>`;
    }
  }

  showTab('resources');
  checkStorage();
  loadResources();
});