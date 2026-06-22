const TYPE_CONFIG = {
  glucose: { unit: 'mg/dL', label: 'Blood Glucose (mg/dL)', borderColor: '#2e7d32' },
  meal: { unit: 'grams', label: 'Carbohydrates (grams)', borderColor: '#e65100' },
  medication: { unit: 'mg', label: 'Dosage (mg)', borderColor: '#1565c0' },
  exercise: { unit: 'minutes', label: 'Duration (minutes)', borderColor: '#6a1b9a' }
};

document.addEventListener('DOMContentLoaded', () => {
  requireAuth();
  setupLogout();

  let selectedType = null;
  const typeBtns = document.querySelectorAll('.type-btn');
  const valueInput = document.getElementById('entryValue');
  const valueLabel = document.getElementById('valueLabel');
  const timestampInput = document.getElementById('entryTimestamp');
  const form = document.getElementById('entryForm');
  const errorDiv = document.getElementById('entryError');
  const successDiv = document.getElementById('entrySuccess');
  const submitBtn = document.getElementById('entrySubmitBtn');

  timestampInput.value = localDatetimeString();

  typeBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const type = btn.dataset.type;
      const config = TYPE_CONFIG[type];

      typeBtns.forEach(b => b.style.borderColor = 'transparent');

      btn.style.borderColor = config.borderColor;

      selectedType = type;
      valueLabel.textContent = config.label;
      valueInput.disabled = false;
      valueInput.focus();
      submitBtn.disabled = false;
    });
  });

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!selectedType) return;

    errorDiv.classList.add('d-none');
    successDiv.classList.add('d-none');
    submitBtn.disabled = true;

    const body = {
      type: selectedType,
      value: parseFloat(valueInput.value),
      unit: TYPE_CONFIG[selectedType].unit,
      notes: document.getElementById('entryNotes').value || null,
      timestamp: timestampInput.value ? new Date(timestampInput.value).toISOString() : null
    };

    try {
      await post('/api/entries', body);
      successDiv.textContent = 'Entry saved successfully!';
      successDiv.classList.remove('d-none');
      valueInput.value = '';
      document.getElementById('entryNotes').value = '';
      timestampInput.value = localDatetimeString();
      selectedType = null;
      typeBtns.forEach(b => b.style.borderColor = 'transparent');
      valueInput.disabled = true;
      submitBtn.disabled = true;
      setTimeout(() => {
        window.location.href = '/static/dashboard.html';
      }, 1500);
    } catch (err) {
      errorDiv.textContent = err.message;
      errorDiv.classList.remove('d-none');
    } finally {
      submitBtn.disabled = false;
    }
  });
});
