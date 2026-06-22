const TYPE_LABELS = { glucose: 'Glucose', meal: 'Meal', medication: 'Medication', exercise: 'Exercise' };
const LIMIT = 50;
let currentLimit = LIMIT;
let glucoseChartInstance = null;

document.addEventListener('DOMContentLoaded', async () => {
  requireAuth();
  setupLogout();

  const params = new URLSearchParams(window.location.search);
  const entryType = params.get('type') || 'glucose';
  const pageTitle = document.getElementById('pageTitle');
  pageTitle.innerHTML = `<span class="entry-type-badge badge-${entryType}">${TYPE_LABELS[entryType]}</span> History`;

  document.querySelectorAll('.type-tab').forEach(a => {
    if (a.dataset.type === entryType) {
      a.classList.remove('btn-outline-secondary');
      a.classList.add('btn-primary');
    }
  });

  const filterFrom = document.getElementById('filterFrom');
  const filterTo = document.getElementById('filterTo');
  const filterBtn = document.getElementById('filterBtn');
  const loadMoreBtn = document.getElementById('loadMoreBtn');

  async function loadHistory(append = false) {
    const loadingEl = document.getElementById('loadingHistory');
    const tableContainer = document.getElementById('historyTableContainer');
    const noHistory = document.getElementById('noHistory');
    const tbody = document.getElementById('historyBody');

    if (!append) {
      loadingEl.classList.remove('d-none');
      tableContainer.classList.add('d-none');
      noHistory.classList.add('d-none');
    }

    const qParams = { limit: currentLimit, type: entryType };
    if (filterFrom.value) qParams.from = filterFrom.value;
    if (filterTo.value) qParams.to = filterTo.value;

    try {
      const entries = await get('/api/entries', qParams);
      loadingEl.classList.add('d-none');

      if (entries.length === 0 && !append) {
        noHistory.classList.remove('d-none');
        tableContainer.classList.add('d-none');
        loadMoreBtn.classList.add('d-none');
        document.getElementById('chartCard')?.classList.add('d-none');
        return;
      }

      tableContainer.classList.remove('d-none');
      if (!append) tbody.innerHTML = '';

      entries.forEach(e => {
        let valueDisplay = `${e.value} ${e.unit}`;
        if (e.type === 'medication' && e.medicationName) {
          valueDisplay = `${e.medicationName} — ${valueDisplay}`;
        }
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td>${formatDateTime(e.timestamp)}</td>
          <td class="${e.type === 'glucose' ? glucoseClass(e.value) : ''}">${valueDisplay}</td>
          <td>${e.notes || ''}</td>
        `;
        tbody.appendChild(tr);
      });

      loadMoreBtn.classList.toggle('d-none', entries.length < currentLimit);

      if (entryType === 'glucose' && entries.length > 0) {
        renderGlucoseChart(entries);
      } else if (glucoseChartInstance) {
        glucoseChartInstance.destroy();
        glucoseChartInstance = null;
        document.getElementById('chartCard')?.classList.add('d-none');
      } else {
        document.getElementById('chartCard')?.classList.add('d-none');
      }
    } catch (err) {
      loadingEl.innerHTML = `<span class="text-danger">${err.message}</span>`;
    }
  }

  function renderGlucoseChart(entries) {
    const chartCard = document.getElementById('chartCard');
    chartCard.classList.remove('d-none');

    if (glucoseChartInstance) {
      glucoseChartInstance.destroy();
    }

    const sorted = [...entries].reverse();
    const labels = sorted.map(e => {
      const d = new Date(e.timestamp);
      return d.toLocaleDateString([], { month: 'short', day: 'numeric' }) + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    });
    const values = sorted.map(e => e.value);

    const ctx = document.getElementById('glucoseChart').getContext('2d');
    glucoseChartInstance = new Chart(ctx, {
      type: 'line',
      data: {
        labels,
        datasets: [{
          label: 'Glucose (mg/dL)',
          data: values,
          borderColor: '#1F6C75',
          backgroundColor: 'rgba(31, 108, 117, 0.08)',
          fill: true,
          tension: 0.3,
          pointBackgroundColor: values.map(v => {
            if (v < 70 || v > 180) return '#dc3545';
            if (v > 140) return '#ffc107';
            return '#198754';
          }),
          pointBorderColor: '#fff',
          pointBorderWidth: 1,
          pointRadius: 5,
          pointHoverRadius: 7,
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (ctx) => `${ctx.parsed.y} mg/dL`
            }
          }
        },
        scales: {
          y: {
            beginAtZero: true,
            title: { display: true, text: 'mg/dL' }
          },
          x: {
            ticks: { maxRotation: 45, font: { size: 10 } }
          }
        }
      }
    });
  }

  filterBtn.addEventListener('click', () => {
    currentLimit = LIMIT;
    loadHistory(false);
  });

  loadMoreBtn.addEventListener('click', () => {
    currentLimit += LIMIT;
    loadHistory(true);
  });

  await loadHistory();
});
