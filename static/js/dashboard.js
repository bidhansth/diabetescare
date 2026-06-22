const TYPE_CONFIG = {
  glucose: { unit: 'mg/dL', label: 'Blood Glucose (mg/dL)', borderColor: '#2e7d32', icon: '🩸', title: 'Log Glucose' },
  meal: { unit: 'grams', label: 'Carbohydrates (grams)', borderColor: '#e65100', icon: '🍽️', title: 'Log Meal' },
  medication: { unit: 'mg', label: 'Dosage (mg)', borderColor: '#1565c0', icon: '💊', title: 'Log Medication' },
  exercise: { unit: 'minutes', label: 'Duration (minutes)', borderColor: '#6a1b9a', icon: '🏃', title: 'Log Exercise' }
};

let medicationsCache = [];
let selectedType = null;

async function loadDashboard() {
  try {
    const data = await get('/api/dashboard');

    document.getElementById('glucoseCount').textContent = data.todayCounts.glucose || 0;
    document.getElementById('mealCount').textContent = data.todayCounts.meal || 0;
    document.getElementById('medicationCount').textContent = data.todayCounts.medication || 0;
    document.getElementById('exerciseCount').textContent = data.todayCounts.exercise || 0;

    const latestEl = document.getElementById('latestGlucose');
    if (data.latestGlucose !== null) {
      latestEl.textContent = `${data.latestGlucose} ${data.latestGlucoseUnit || 'mg/dL'}`;
      latestEl.className = glucoseClass(data.latestGlucose);
      document.getElementById('latestGlucoseTime').textContent = formatDateTime(data.latestGlucoseTime);
    } else {
      latestEl.textContent = 'No readings';
      latestEl.className = '';
    }

    const entries = data.todayEntries || [];
    const loadingEl = document.getElementById('loadingEntries');
    const tableContainer = document.getElementById('entriesTableContainer');
    const noEntries = document.getElementById('noEntries');

    loadingEl.classList.add('d-none');

    if (entries.length === 0) {
      noEntries.classList.remove('d-none');
      tableContainer.classList.add('d-none');
    } else {
      tableContainer.classList.remove('d-none');
      noEntries.classList.add('d-none');
      const tbody = document.getElementById('entriesBody');
      tbody.innerHTML = '';
      entries.forEach(e => {
        const tr = document.createElement('tr');
        let valueDisplay = `${e.value} ${e.unit}`;
        if (e.type === 'medication' && e.medicationName) {
          valueDisplay = `${e.medicationName} — ${valueDisplay}`;
        }
        tr.innerHTML = `
          <td>${formatTime(e.timestamp)}</td>
          <td>${getEntryBadge(e.type)}</td>
          <td class="${e.type === 'glucose' ? glucoseClass(e.value) : ''}">${valueDisplay}</td>
          <td>${e.notes || ''}</td>
        `;
        tbody.appendChild(tr);
      });
    }
  } catch (err) {
    document.getElementById('loadingEntries').innerHTML = `<span class="text-danger">${err.message}</span>`;
  }
}

async function loadMedications() {
  try {
    medicationsCache = await get('/api/medications');
    const select = document.getElementById('medicationSelect');
    select.innerHTML = '<option value="">Select medication...</option>';
    medicationsCache.forEach(m => {
      const opt = document.createElement('option');
      opt.value = m.medicationId;
      opt.dataset.dosage = m.dosage;
      opt.textContent = `${m.name} (${m.dosage})`;
      select.appendChild(opt);
    });
  } catch (err) {
    console.error('Failed to load medications', err);
  }
}

function renderMedicationList() {
  const container = document.getElementById('medList');
  if (medicationsCache.length === 0) {
    container.innerHTML = '<p class="text-muted mb-0">No medications saved yet.</p>';
    return;
  }
  container.innerHTML = '';
  medicationsCache.forEach(m => {
    const div = document.createElement('div');
    div.className = 'd-flex justify-content-between align-items-center mb-1 p-2 rounded';
    div.style.background = '#f8f9fa';
    div.innerHTML = `
      <span><strong>${m.name}</strong> — ${m.dosage}</span>
      <button class="btn btn-sm btn-outline-danger delete-med" data-id="${m.medicationId}" style="line-height:1;">&times;</button>
    `;
    container.appendChild(div);
  });

  document.querySelectorAll('.delete-med').forEach(btn => {
    btn.addEventListener('click', async () => {
      await del('/api/medications/' + btn.dataset.id);
      await loadMedications();
      renderMedicationList();
    });
  });
}

function resetForm() {
  document.getElementById('quickForm').classList.add('d-none');
  document.querySelectorAll('.log-btn').forEach(b => b.style.borderColor = 'transparent');
  selectedType = null;
  document.getElementById('valueField').classList.remove('d-none');
  document.getElementById('medicationField').classList.add('d-none');
  document.getElementById('medicationSelect').value = '';
  document.getElementById('entryValue').value = '';
  document.getElementById('entryNotes').value = '';
  document.getElementById('entryError').classList.add('d-none');
}

document.addEventListener('DOMContentLoaded', () => {
  requireAuth();
  setupLogout();

  const user = getUser();
  document.getElementById('welcomeMsg').textContent = `Welcome, ${user.name}!`;

  const logBtns = document.querySelectorAll('.log-btn');
  const form = document.getElementById('entryForm');
  const valueInput = document.getElementById('entryValue');
  const valueLabel = document.getElementById('valueLabel');
  const unitDisplay = document.getElementById('entryUnitDisplay');
  const timestampInput = document.getElementById('entryTimestamp');
  const notesInput = document.getElementById('entryNotes');
  const errorDiv = document.getElementById('entryError');
  const submitBtn = document.getElementById('entrySubmitBtn');
  const cancelBtn = document.getElementById('cancelBtn');
  const medicationField = document.getElementById('medicationField');
  const medicationSelect = document.getElementById('medicationSelect');
  const manageMedsBtn = document.getElementById('manageMedsBtn');
  const formHeader = document.getElementById('formHeader');
  const typeIcon = document.getElementById('selectedTypeIcon');
  const typeTitle = document.getElementById('selectedTypeTitle');

  const valueField = document.getElementById('valueField');
  const qtyMinus = document.getElementById('qtyMinus');
  const qtyPlus = document.getElementById('qtyPlus');
  const qtyInput = document.getElementById('qtyInput');
  const computedDosage = document.getElementById('computedDosage');

  let selectedType = null;

  function parseDosage(str) {
    const m = str.match(/^[\d.]+/);
    return m ? parseFloat(m[0]) : 0;
  }

  function updateComputedDosage() {
    const sel = medicationSelect;
    if (!sel.value) {
      computedDosage.textContent = '';
      return;
    }
    const qty = parseFloat(qtyInput.value) || 1;
    const dosageNum = parseDosage(sel.selectedOptions[0].dataset.dosage);
    computedDosage.textContent = `= ${qty} \u00d7 ${dosageNum} = ${qty * dosageNum} mg`;
  }

  logBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const type = btn.dataset.type;
      const config = TYPE_CONFIG[type];

      logBtns.forEach(b => b.style.borderColor = 'transparent');
      btn.style.borderColor = config.borderColor;

      selectedType = type;
      typeIcon.textContent = config.icon;
      typeTitle.textContent = config.title;
      valueLabel.textContent = config.label;
      unitDisplay.textContent = config.unit;
      valueInput.value = '';
      notesInput.value = '';
      timestampInput.value = localDatetimeString();
      errorDiv.classList.add('d-none');
      document.getElementById('quickForm').classList.remove('d-none');

      if (type === 'medication') {
        valueField.classList.add('d-none');
        medicationField.classList.remove('d-none');
        qtyInput.value = '1';
        computedDosage.textContent = '';
        loadMedications();
      } else {
        valueField.classList.remove('d-none');
        medicationField.classList.add('d-none');
        medicationSelect.value = '';
        valueInput.focus();
      }
    });
  });

  cancelBtn.addEventListener('click', resetForm);

  manageMedsBtn.addEventListener('click', () => {
    renderMedicationList();
    const modal = new bootstrap.Modal(document.getElementById('medicationsModal'));
    modal.show();
  });

  medicationSelect.addEventListener('change', updateComputedDosage);

  qtyMinus.addEventListener('click', () => {
    let v = parseFloat(qtyInput.value) || 1;
    if (v > 0.5) {
      qtyInput.value = Math.max(0.5, v - 0.5);
      updateComputedDosage();
    }
  });

  qtyPlus.addEventListener('click', () => {
    let v = parseFloat(qtyInput.value) || 1;
    qtyInput.value = v + 0.5;
    updateComputedDosage();
  });

  document.getElementById('addMedBtn').addEventListener('click', async () => {
    const name = document.getElementById('newMedName').value.trim();
    const dosage = document.getElementById('newMedDosage').value.trim();
    const medError = document.getElementById('medError');
    medError.classList.add('d-none');
    if (!name || !dosage) {
      medError.textContent = 'Both name and dosage are required.';
      medError.classList.remove('d-none');
      return;
    }
    try {
      await post('/api/medications', { name, dosage });
      document.getElementById('newMedName').value = '';
      document.getElementById('newMedDosage').value = '';
      await loadMedications();
      renderMedicationList();
    } catch (err) {
      medError.textContent = err.message;
      medError.classList.remove('d-none');
    }
  });

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!selectedType) return;
    errorDiv.classList.add('d-none');
    submitBtn.disabled = true;

    let value;
    if (selectedType === 'medication') {
      if (!medicationSelect.value) {
        errorDiv.textContent = 'Please select a medication.';
        errorDiv.classList.remove('d-none');
        submitBtn.disabled = false;
        return;
      }
      const qty = parseFloat(qtyInput.value) || 1;
      const dosageNum = parseDosage(medicationSelect.selectedOptions[0].dataset.dosage);
      value = qty * dosageNum;
    } else {
      value = parseFloat(valueInput.value);
      if (!value || value <= 0) {
        errorDiv.textContent = 'Please enter a valid value.';
        errorDiv.classList.remove('d-none');
        submitBtn.disabled = false;
        return;
      }
    }

    const body = {
      type: selectedType,
      value,
      unit: TYPE_CONFIG[selectedType].unit,
      notes: notesInput.value || null,
      timestamp: timestampInput.value ? new Date(timestampInput.value).toISOString() : null
    };

    if (selectedType === 'medication' && medicationSelect.value) {
      body.medicationId = medicationSelect.value;
    }

    try {
      await post('/api/entries', body);
      resetForm();
      document.getElementById('loadingEntries').classList.remove('d-none');
      document.getElementById('entriesTableContainer').classList.add('d-none');
      document.getElementById('noEntries').classList.add('d-none');
      await loadDashboard();
    } catch (err) {
      errorDiv.textContent = err.message;
      errorDiv.classList.remove('d-none');
    } finally {
      submitBtn.disabled = false;
    }
  });

  loadDashboard();
});
