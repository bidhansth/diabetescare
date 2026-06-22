document.addEventListener('DOMContentLoaded', () => {
  requireAuth();
  setupLogout();

  const postId = new URLSearchParams(window.location.search).get('id');
  if (!postId) {
    window.location.href = '/static/forum.html';
    return;
  }

  const user = getUser();
  const loadingEl = document.getElementById('loadingPost');
  const contentEl = document.getElementById('postContent');
  const notFoundEl = document.getElementById('postNotFound');
  const commentsContainer = document.getElementById('commentsContainer');
  const commentForm = document.getElementById('commentForm');
  const commentBody = document.getElementById('commentBody');
  const parentCommentId = document.getElementById('parentCommentId');
  const replyInfo = document.getElementById('replyInfo');
  const replyTarget = document.getElementById('replyTarget');
  const cancelReply = document.getElementById('cancelReply');
  const reportModal = new bootstrap.Modal(document.getElementById('reportModal'));
  const reportTargetType = document.getElementById('reportTargetType');
  const reportTargetId = document.getElementById('reportTargetId');
  const reportReason = document.getElementById('reportReason');
  const reportForm = document.getElementById('reportForm');

  let post = null;
  let comments = [];

  cancelReply.addEventListener('click', () => {
    parentCommentId.value = '';
    replyInfo.classList.add('d-none');
    commentBody.focus();
  });

  // ── Report handling ──

  function openReport(targetType, targetId) {
    reportTargetType.value = targetType;
    reportTargetId.value = targetId;
    reportReason.value = '';
    document.getElementById('reportError').classList.add('d-none');
    reportModal.show();
  }

  reportForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    document.getElementById('reportError').classList.add('d-none');
    document.getElementById('submitReportBtn').disabled = true;

    try {
      const reason = reportReason.value.trim();
      if (!reason) return;

      const type = reportTargetType.value;
      const id = reportTargetId.value;

      if (type === 'post') {
        await apiRequest('POST', `/api/posts/${id}/report`, { reason });
      } else {
        await apiRequest('POST', `/api/posts/${postId}/comments/${id}/report`, { reason });
      }

      reportModal.hide();
    } catch (err) {
      const el = document.getElementById('reportError');
      el.textContent = err.message;
      el.classList.remove('d-none');
    } finally {
      document.getElementById('submitReportBtn').disabled = false;
    }
  });

  // ── Load post ──

  async function loadPost() {
    loadingEl.classList.remove('d-none');
    contentEl.classList.add('d-none');
    notFoundEl.classList.add('d-none');

    try {
      const resp = await apiRequest('GET', `/api/posts/${postId}`);
      loadingEl.classList.add('d-none');
      contentEl.classList.remove('d-none');

      post = resp;
      document.getElementById('postTopicBadge').textContent = post.topicName;
      document.getElementById('postTitle').textContent = post.title;
      document.getElementById('postAuthor').textContent = post.authorName;
      document.getElementById('postDate').textContent = formatDateTime(post.createdAt);
      document.getElementById('postBody').textContent = post.body;

      if (user.userId === post.authorId || user.role === 'admin') {
        document.getElementById('deletePostBtn').classList.remove('d-none');
      }
      document.getElementById('deletePostBtn').addEventListener('click', async () => {
        if (!confirm('Delete this post and all comments?')) return;
        try {
          await del(`/api/posts/${postId}`);
          window.location.href = '/static/forum.html';
        } catch (err) {
          alert(err.message);
        }
      });

      document.querySelector('.report-post-btn').addEventListener('click', () => {
        openReport('post', postId);
      });

      renderComments();
    } catch (err) {
      loadingEl.classList.add('d-none');
      notFoundEl.classList.remove('d-none');
    }
  }

  async function loadComments() {
    try {
      comments = await get(`/api/posts/${postId}/comments`);
    } catch (err) {
      comments = [];
    }
  }

  function buildCommentTree(flat) {
    const map = {};
    const roots = [];
    flat.forEach(c => {
      map[c.commentId] = { ...c, replies: [] };
    });
    flat.forEach(c => {
      if (c.parentCommentId && map[c.parentCommentId]) {
        map[c.parentCommentId].replies.push(map[c.commentId]);
      } else if (!c.parentCommentId) {
        roots.push(map[c.commentId]);
      }
    });
    return roots;
  }

  function renderCommentHtml(node, depth) {
    const margin = Math.min(depth * 24, 96);
    const isAuthor = user.userId === node.authorId || user.role === 'admin';
    const delBtn = isAuthor
      ? `<button class="btn btn-sm btn-outline-danger py-0 px-1 delete-comment" data-id="${node.commentId}" style="font-size:0.7rem;">Delete</button>`
      : '';

    let html = `
      <div class="mb-2" style="margin-left:${margin}px;">
        <div class="card border-light bg-light">
          <div class="card-body py-2 px-3">
            <div class="d-flex justify-content-between align-items-start">
              <small class="fw-semibold">${esc(node.authorName)}</small>
              <div>
                <small class="text-muted">${formatDateTime(node.createdAt)}</small>
                ${delBtn}
              </div>
            </div>
            <p class="mb-1 small" style="white-space:pre-wrap;">${esc(node.body)}</p>
            <button class="btn btn-sm btn-link text-muted py-0 px-0 reply-btn" data-id="${node.commentId}" data-name="${esc(node.authorName)}">Reply</button>
            <button class="btn btn-sm btn-link text-danger py-0 px-0 report-comment-btn" data-id="${node.commentId}">Report</button>
          </div>
        </div>
      </div>
    `;

    if (node.replies) {
      node.replies.forEach(r => {
        html += renderCommentHtml(r, depth + 1);
      });
    }

    return html;
  }

  function renderComments() {
    document.getElementById('commentCount').textContent = `${comments.length} Comment${comments.length !== 1 ? 's' : ''}`;

    if (comments.length === 0) {
      commentsContainer.innerHTML = '<p class="text-muted small">No comments yet.</p>';
      return;
    }

    const tree = buildCommentTree(comments);
    commentsContainer.innerHTML = tree.map(c => renderCommentHtml(c, 0)).join('');

    document.querySelectorAll('.reply-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        parentCommentId.value = btn.dataset.id;
        replyTarget.textContent = btn.dataset.name;
        replyInfo.classList.remove('d-none');
        commentBody.focus();
      });
    });

    document.querySelectorAll('.delete-comment').forEach(btn => {
      btn.addEventListener('click', async () => {
        const cid = btn.dataset.id;
        if (!confirm('Delete this comment and all replies?')) return;
        try {
          await del(`/api/posts/${postId}/comments/${cid}`);
          await loadComments();
          renderComments();
        } catch (err) {
          alert(err.message);
        }
      });
    });

    document.querySelectorAll('.report-comment-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        openReport('comment', btn.dataset.id);
      });
    });
  }

  commentForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    document.getElementById('commentError').classList.add('d-none');
    document.getElementById('submitCommentBtn').disabled = true;

    try {
      const body = commentBody.value.trim();
      if (!body) return;

      const payload = { body };
      if (parentCommentId.value) {
        payload.parentCommentId = parentCommentId.value;
      }

      await apiRequest('POST', `/api/posts/${postId}/comments`, payload);
      commentBody.value = '';
      parentCommentId.value = '';
      replyInfo.classList.add('d-none');

      await loadComments();
      renderComments();
    } catch (err) {
      const el = document.getElementById('commentError');
      el.textContent = err.message;
      el.classList.remove('d-none');
    } finally {
      document.getElementById('submitCommentBtn').disabled = false;
    }
  });

  function esc(s) {
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
  }

  loadPost().then(() => loadComments()).then(() => renderComments());
});