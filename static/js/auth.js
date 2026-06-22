const NAME_RE = /^[a-zA-Z\s]+$/;
const PASSWORD_RE = /^(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]).{6,}$/;

function hideErrors(container) {
  container.querySelectorAll('.text-danger').forEach(el => el.classList.add('d-none'));
}

function showError(id, msg) {
  const el = document.getElementById(id);
  el.textContent = msg;
  el.classList.remove('d-none');
}

async function loadCarousel() {
  try {
    const slides = await get('/api/carousel');
    const inner = document.getElementById('carouselInner');
    const indicators = document.getElementById('carouselIndicators');

    if (!slides || slides.length === 0) return;

    inner.innerHTML = '';
    indicators.innerHTML = '';

    slides.forEach((slide, idx) => {
      const indicator = document.createElement('button');
      indicator.type = 'button';
      indicator.dataset.bsSlideTo = idx;
      indicator.className = idx === 0 ? 'active' : '';
      indicator.setAttribute('aria-label', `Slide ${idx + 1}`);
      indicators.appendChild(indicator);

      const item = document.createElement('div');
      item.className = `carousel-item${idx === 0 ? ' active' : ''}`;

      const img = document.createElement('img');
      img.src = slide.imageUrl;
      img.className = 'd-block w-100 carousel-img';
      img.alt = slide.caption || 'DiabetesCare slide';
      item.appendChild(img);

      if (slide.caption) {
        const caption = document.createElement('div');
        caption.className = 'carousel-caption d-none d-md-block';
        caption.innerHTML = `<h5>${esc(slide.caption)}</h5>`;
        item.appendChild(caption);
      }

      inner.appendChild(item);
    });
  } catch (err) {
    // silently ignore carousel load errors
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const loginForm = document.getElementById('loginForm');
  const signupForm = document.getElementById('signupForm');
  const signupError = document.getElementById('signupError');

  if (getToken()) {
    const user = getUser();
    if (user && user.role === 'admin') {
      window.location.href = '/static/admin/index.html';
      return;
    }
    if (!user || !user.role) {
      clearAuth();
      window.location.href = '/static/index.html';
      return;
    }
    window.location.href = '/static/dashboard.html';
    return;
  }

  loadCarousel();

  loginForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    hideErrors(loginForm);

    const email = document.getElementById('loginEmail').value.trim();
    const password = document.getElementById('loginPassword').value;

    let valid = true;
    if (!email || !email.includes('@')) {
      showError('loginEmailError', 'Please enter a valid email');
      valid = false;
    }
    if (!password) {
      showError('loginPasswordError', 'Please enter your password');
      valid = false;
    }
    if (!valid) return;

    document.getElementById('loginBtn').disabled = true;
    try {
      const data = await post('/api/auth/login', { email, password });
      setAuth(data.token, { userId: data.userId, name: data.name, email: data.email, role: data.role });
      if (data.role === 'admin') {
        window.location.href = '/static/admin/index.html';
      } else {
        window.location.href = '/static/dashboard.html';
      }
    } catch (err) {
      showError('loginEmailError', err.message);
    } finally {
      document.getElementById('loginBtn').disabled = false;
    }
  });

  signupForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    hideErrors(signupForm);
    signupError.classList.add('d-none');

    const name = document.getElementById('signupName').value.trim();
    const email = document.getElementById('signupEmail').value.trim();
    const password = document.getElementById('signupPassword').value;

    let valid = true;

    if (!NAME_RE.test(name)) {
      showError('nameError', 'Name must only contain letters and spaces');
      valid = false;
    }

    if (!email || !email.includes('@')) {
      showError('emailError', 'Please enter a valid email');
      valid = false;
    }

    if (!PASSWORD_RE.test(password)) {
      showError('passwordError', 'Password must be at least 6 characters, with 1 uppercase, 1 number, and 1 special character');
      valid = false;
    }

    if (!valid) return;

    document.getElementById('signupBtn').disabled = true;
    try {
      const data = await post('/api/auth/signup', { name, email, password });
      setAuth(data.token, { userId: data.userId, name: data.name, email: data.email, role: data.role });
      window.location.href = '/static/dashboard.html';
    } catch (err) {
      signupError.textContent = err.message;
      signupError.classList.remove('d-none');
    } finally {
      document.getElementById('signupBtn').disabled = false;
    }
  });
});
