document.addEventListener('DOMContentLoaded', async () => {
  requireAuth();
  setupLogout();

  try {
    const alerts = await get('/api/entries/alerts');
    const loadingEl = document.getElementById('loadingAlerts');
    const tableContainer = document.getElementById('alertsTableContainer');
    const noAlerts = document.getElementById('noAlerts');

    loadingEl.classList.add('d-none');

    if (alerts.length === 0) {
      noAlerts.classList.remove('d-none');
      return;
    }

    tableContainer.classList.remove('d-none');
    const tbody = document.getElementById('alertsBody');
    alerts.forEach(a => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${formatDateTime(a.timestamp)}</td>
        <td><span class="badge bg-${a.level === 'high' ? 'danger' : 'warning'}">${a.level}</span></td>
        <td class="${a.level === 'high' ? 'glucose-high' : 'glucose-low'}">${a.value} ${a.unit}</td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    document.getElementById('loadingAlerts').innerHTML = `<span class="text-danger">${err.message}</span>`;
  }
});
