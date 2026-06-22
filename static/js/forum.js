document.addEventListener('DOMContentLoaded', () => {
  requireAuth();
  setupLogout();

  const postsList = document.getElementById('postsList');
  const loadingEl = document.getElementById('loadingPosts');
  const noPosts = document.getElementById('noPosts');
  const topicFilter = document.getElementById('topicFilter');
  const postTopic = document.getElementById('postTopic');
  const newPostForm = document.getElementById('newPostForm');

  let topics = [];

  async function loadTopics() {
    topics = await get('/api/topics');
    const render = (sel) => {
      sel.innerHTML = '<option value="">All Topics</option>';
      topics.forEach(t => {
        const opt = document.createElement('option');
        opt.value = t.topicId;
        opt.textContent = t.name;
        sel.appendChild(opt);
      });
    };
    render(topicFilter);
    render(postTopic);
    postTopic.querySelector('option[value=""]').textContent = 'Select a topic';
  }

  async function loadPosts() {
    loadingEl.classList.remove('d-none');
    noPosts.classList.add('d-none');
    postsList.innerHTML = '';

    const topic = topicFilter.value;
    const params = {};
    if (topic) params.topic = topic;

    try {
      const posts = topic ? await get('/api/posts', params) : await get('/api/posts');
      loadingEl.classList.add('d-none');

      if (posts.length === 0) {
        noPosts.classList.remove('d-none');
        return;
      }

      posts.forEach(p => {
        const card = document.createElement('div');
        card.className = 'card mb-2';
        card.innerHTML = `
          <div class="card-body py-3">
            <div class="d-flex justify-content-between align-items-start">
              <div>
                <span class="badge bg-info me-1">${esc(p.topicName)}</span>
                <a href="/static/post.html?id=${p.postId}" class="text-decoration-none fw-semibold fs-5">${esc(p.title)}</a>
              </div>
              <small class="text-muted text-nowrap ms-2">${formatDate(p.createdAt)}</small>
            </div>
            <p class="text-muted small mb-0 mt-1">
              by ${esc(p.authorName)} &middot; ${p.commentCount} comment${p.commentCount !== 1 ? 's' : ''}
            </p>
          </div>
        `;
        postsList.appendChild(card);
      });
    } catch (err) {
      loadingEl.innerHTML = `<span class="text-danger">${err.message}</span>`;
    }
  }

  topicFilter.addEventListener('change', loadPosts);

  newPostForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    document.getElementById('postError').classList.add('d-none');
    document.getElementById('submitPostBtn').disabled = true;

    try {
      const topicId = document.getElementById('postTopic').value;
      const title = document.getElementById('postTitle').value.trim();
      const body = document.getElementById('postBody').value.trim();

      if (!topicId || !title || !body) return;

      const created = await post('/api/posts', { topicId, title, body });
      bootstrap.Modal.getInstance(document.getElementById('newPostModal')).hide();
      newPostForm.reset();
      loadPosts();
    } catch (err) {
      const el = document.getElementById('postError');
      el.textContent = err.message;
      el.classList.remove('d-none');
    } finally {
      document.getElementById('submitPostBtn').disabled = false;
    }
  });

  // Reset form when modal opens
  document.getElementById('newPostModal').addEventListener('hidden.bs.modal', () => {
    newPostForm.reset();
    document.getElementById('postError').classList.add('d-none');
  });

  function esc(s) {
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
  }

  loadTopics().then(loadPosts);
});
