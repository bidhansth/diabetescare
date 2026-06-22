document.addEventListener('DOMContentLoaded', () => {
  requireAuth();
  setupLogout();

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
          <td>
            <div class="fw-semibold">${r.name}</div>
            ${r.description ? `<small class="text-muted">${r.description}</small>` : ''}
          </td>
          <td><span class="badge bg-info">${r.fileType}</span></td>
          <td>${formatFileSize(r.fileSize)}</td>
          <td>${formatDate(r.uploadedAt)}</td>
          <td><a href="/api/resources/${r.resourceId}/download?token=${getToken()}" class="btn btn-sm btn-primary">Download</a></td>
        `;
        tbody.appendChild(tr);
      });
    } catch (err) {
      loadingEl.innerHTML = `<span class="text-danger">${err.message}</span>`;
    }
  }

  loadResources();
});
