document.addEventListener('DOMContentLoaded', () => {
  requireAdmin();
  setupLogout();

  const tabResources = document.getElementById('tabResources');
  const tabCarousel = document.getElementById('tabCarousel');
  const tabReports = document.getElementById('tabReports');
  const tabTopics = document.getElementById('tabTopics');
  const tabUsers = document.getElementById('tabUsers');
  const resSection = document.getElementById('resourcesSection');
  const carouselSection = document.getElementById('carouselSection');
  const reportsSection = document.getElementById('reportsSection');
  const topicsSection = document.getElementById('topicsSection');
  const usersSection = document.getElementById('usersSection');

  function showTab(section) {
    resSection.classList.toggle('d-none', section !== 'resources');
    carouselSection.classList.toggle('d-none', section !== 'carousel');
    reportsSection.classList.toggle('d-none', section !== 'reports');
    topicsSection.classList.toggle('d-none', section !== 'topics');
    usersSection.classList.toggle('d-none', section !== 'users');
    tabResources.classList.toggle('active', section === 'resources');
    tabCarousel.classList.toggle('active', section === 'carousel');
    tabReports.classList.toggle('active', section === 'reports');
    tabTopics.classList.toggle('active', section === 'topics');
    tabUsers.classList.toggle('active', section === 'users');
  }

  tabResources.addEventListener('click', (e) => { e.preventDefault(); showTab('resources'); });
  tabCarousel.addEventListener('click', (e) => { e.preventDefault(); showTab('carousel'); loadCarouselSlides(); });
  tabReports.addEventListener('click', (e) => { e.preventDefault(); showTab('reports'); loadReports(); });
  tabTopics.addEventListener('click', (e) => { e.preventDefault(); showTab('topics'); loadTopics(); });
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
      // silently ignore
    }
  }

  // ── Carousel ──

  const carouselForm = document.getElementById('carouselUploadForm');
  const carouselUploadError = document.getElementById('carouselUploadError');

  carouselForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    carouselUploadError.classList.add('d-none');

    const caption = document.getElementById('carouselCaption').value.trim();
    const fileInput = document.getElementById('carouselFile');
    const file = fileInput.files[0];

    if (!file) return;

    const formData = new FormData();
    formData.append('caption', caption);
    formData.append('file', file);

    document.getElementById('carouselUploadBtn').disabled = true;
    try {
      const token = getToken();
      const resp = await fetch('/api/carousel', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body: formData,
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: 'Upload failed' }));
        throw new Error(err.detail || 'Upload failed');
      }
      carouselForm.reset();
      loadCarouselSlides();
    } catch (err) {
      carouselUploadError.textContent = err.message;
      carouselUploadError.classList.remove('d-none');
    } finally {
      document.getElementById('carouselUploadBtn').disabled = false;
    }
  });

  async function loadCarouselSlides() {
    const loadingEl = document.getElementById('loadingCarousel');
    const tableContainer = document.getElementById('carouselTableContainer');
    const noCarousel = document.getElementById('noCarousel');
    const grid = document.getElementById('carouselGrid');

    loadingEl.classList.remove('d-none');
    tableContainer.classList.add('d-none');
    noCarousel.classList.add('d-none');

    try {
      const slides = await get('/api/carousel');
      loadingEl.classList.add('d-none');

      if (slides.length === 0) {
        noCarousel.classList.remove('d-none');
        return;
      }

      tableContainer.classList.remove('d-none');
      grid.innerHTML = '';
      slides.forEach((s, i) => {
        const col = document.createElement('div');
        col.className = 'col-md-4 col-sm-6';
        const canUp = i > 0;
        const canDown = i < slides.length - 1;
        col.innerHTML = `
          <div class="card">
            <img src="${esc(s.imageUrl)}" class="card-img-top" style="height:180px;object-fit:cover;" alt="${esc(s.caption || 'Slide')}">
            <div class="card-body p-2">
              <p class="card-text small mb-1">${esc(s.caption || '(no caption)')}</p>
              <small class="text-muted">Position: ${s.position}</small>
              <div class="mt-2">
                <button class="btn btn-sm btn-outline-secondary move-slide-btn" data-id="${s.slideId}" data-dir="up" ${canUp ? '' : 'disabled'} title="Move up">&uarr;</button>
                <button class="btn btn-sm btn-outline-secondary move-slide-btn" data-id="${s.slideId}" data-dir="down" ${canDown ? '' : 'disabled'} title="Move down">&darr;</button>
                <button class="btn btn-sm btn-outline-danger float-end delete-slide-btn" data-id="${s.slideId}">Delete</button>
              </div>
            </div>
          </div>
        `;
        grid.appendChild(col);
      });

      grid.querySelectorAll('.delete-slide-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
          if (!confirm('Delete this slide?')) return;
          try {
            await del(`/api/carousel/${btn.dataset.id}`);
            loadCarouselSlides();
          } catch (err) {
            alert(err.message);
          }
        });
      });

      grid.querySelectorAll('.move-slide-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
          const id = btn.dataset.id;
          const dir = btn.dataset.dir;
          const idx = slides.findIndex(s => s.slideId === id);
          if (idx === -1) return;
          const swapIdx = dir === 'up' ? idx - 1 : idx + 1;
          if (swapIdx < 0 || swapIdx >= slides.length) return;
          [slides[idx], slides[swapIdx]] = [slides[swapIdx], slides[idx]];
          const newOrder = slides.map(s => s.slideId);
          try {
            await apiRequest('PATCH', '/api/carousel/reorder', { slideIds: newOrder });
            loadCarouselSlides();
          } catch (err) {
            alert(err.message);
          }
        });
      });
    } catch (err) {
      loadingEl.innerHTML = `<span class="text-danger">${err.message}</span>`;
    }
  }

  // ── Reports ──

  const reportStatusFilter = document.getElementById('reportStatusFilter');

  reportStatusFilter.addEventListener('change', loadReports);

  async function loadReports() {
    const loadingEl = document.getElementById('loadingReports');
    const tableContainer = document.getElementById('reportsTableContainer');
    const noReports = document.getElementById('noReports');
    const tbody = document.getElementById('reportsBody');

    loadingEl.classList.remove('d-none');
    tableContainer.classList.add('d-none');
    noReports.classList.add('d-none');

    try {
      const status = reportStatusFilter.value;
      const params = {};
      if (status) params.status = status;
      const reports = await get('/api/admin/reports', params);
      loadingEl.classList.add('d-none');

      if (reports.length === 0) {
        noReports.classList.remove('d-none');
        return;
      }

      tableContainer.classList.remove('d-none');
      tbody.innerHTML = '';
      reports.forEach(r => {
        const isPending = r.status === 'pending';
        const badgeClass = r.status === 'pending' ? 'bg-warning text-dark' : r.status === 'resolved' ? 'bg-success' : 'bg-secondary';
        const targetLabel = r.targetType === 'post' ? 'Post' : 'Comment';
        const viewLink = `/static/post.html?id=${r.postId}`;

        let actions = '';
        if (isPending) {
          actions = `
            <button class="btn btn-sm btn-outline-success resolve-btn me-1" data-id="${r.reportId}" data-action="resolved">Resolve</button>
            <button class="btn btn-sm btn-outline-secondary dismiss-btn me-1" data-id="${r.reportId}" data-action="dismissed">Dismiss</button>
            <a href="${viewLink}" target="_blank" class="btn btn-sm btn-outline-info">View</a>
          `;
        } else {
          actions = `<span class="text-muted small">${r.resolvedAt ? formatDate(r.resolvedAt) : ''}</span>`;
        }

        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td><span class="badge bg-info">${targetLabel}</span></td>
          <td>${esc(r.reason)}</td>
          <td>${esc(r.reportedByName)}</td>
          <td>${formatDateTime(r.createdAt)}</td>
          <td><span class="badge ${badgeClass}">${r.status}</span></td>
          <td class="text-nowrap">${actions}</td>
        `;
        tbody.appendChild(tr);
      });

      tbody.querySelectorAll('.resolve-btn, .dismiss-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
          try {
            await apiRequest('PATCH', `/api/admin/reports/${btn.dataset.id}`, { status: btn.dataset.action });
            loadReports();
          } catch (err) {
            alert(err.message);
          }
        });
      });
    } catch (err) {
      loadingEl.innerHTML = `<span class="text-danger">${err.message}</span>`;
    }
  }

  // ── Topics ──

  const topicForm = document.getElementById('topicForm');
  const topicName = document.getElementById('topicName');
  const topicError = document.getElementById('topicError');

  topicForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    topicError.classList.add('d-none');
    document.getElementById('addTopicBtn').disabled = true;

    try {
      const name = topicName.value.trim();
      if (!name) return;
      await apiRequest('POST', '/api/admin/topics', { name });
      topicName.value = '';
      loadTopics();
    } catch (err) {
      topicError.textContent = err.message;
      topicError.classList.remove('d-none');
    } finally {
      document.getElementById('addTopicBtn').disabled = false;
    }
  });

  async function loadTopics() {
    const loadingEl = document.getElementById('loadingTopics');
    const tableContainer = document.getElementById('topicsTableContainer');
    const noTopics = document.getElementById('noTopics');
    const tbody = document.getElementById('topicsBody');

    loadingEl.classList.remove('d-none');
    tableContainer.classList.add('d-none');
    noTopics.classList.add('d-none');

    try {
      const topics = await get('/api/topics');
      loadingEl.classList.add('d-none');

      if (topics.length === 0) {
        noTopics.classList.remove('d-none');
        return;
      }

      tableContainer.classList.remove('d-none');
      tbody.innerHTML = '';
      topics.forEach(t => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td>${esc(t.name)}</td>
          <td>${formatDate(t.createdAt)}</td>
          <td>
            <button class="btn btn-sm btn-outline-danger delete-topic-btn" data-id="${t.topicId}">Delete</button>
          </td>
        `;
        tbody.appendChild(tr);
      });

      tbody.querySelectorAll('.delete-topic-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
          if (!confirm('Delete this topic? Posts using it will still exist.')) return;
          try {
            await del(`/api/admin/topics/${btn.dataset.id}`);
            loadTopics();
          } catch (err) {
            alert(err.message);
          }
        });
      });
    } catch (err) {
      loadingEl.innerHTML = `<span class="text-danger">${err.message}</span>`;
    }
  }

  // ── Users ──

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
          <td>${esc(u.name)}</td>
          <td>${esc(u.email)}</td>
          <td><span class="badge ${isAdmin ? 'bg-success' : 'bg-secondary'}">${esc(u.role)}</span></td>
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

  // ── Resources upload ──

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
          <td>${esc(r.name)}</td>
          <td><span class="badge bg-info">${esc(r.fileType)}</span></td>
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

  function esc(s) {
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
  }

  showTab('resources');
  checkStorage();
  loadResources();
});
