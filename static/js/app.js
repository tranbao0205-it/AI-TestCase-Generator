'use strict';

    let currentConvId    = null;   // active conversation ID
    let currentTCData    = null;   // latest test-case JSON from AI
    let uploadedContent  = null;   // text content of uploaded spec file
    let uploadedFilename = null;   // display name of uploaded file
    let uploadedImages   = [];     // list of base64 image_blocks for Vision API
    let uploadedImagePreviews = []; // list of {filename, dataUrl} for chat bubble thumbnails
    let pendingContextAction = null; // { kind: 'image'|'send', data?, message? } đang chờ user chọn 1/2/3
    let waitingContextChoice = false; // chờ 1=Phân tích độc lập, 2=Chỉ màn hình này, 3=Tiếp tục workflow
    let contextMode = null; // null | 'new' | 'screen_only' | 'workflow'
    let skipContextPromptOnce = false; // bỏ qua hỏi lại đúng 1 lần sau khi đã chọn 1/2/3
    let allConversations = []; // cache toàn bộ lịch sử để filter theo ô tìm kiếm
    const tcSnapshots = new Map(); // snapshot_id -> testcase JSON
    let activeSnapshotId = null;   // snapshot đang preview/xuất/chỉnh sửa
    let loadingMsgTimer  = null;
    let loadingStepTimer = null;
    const PENDING_UPLOAD_KEY = 'wtc_pending_upload_v1';
    const CURRENT_CONV_KEY   = 'wtc_current_conv_v1';
    document.addEventListener('DOMContentLoaded', async () => {
      injectImagePreviewStyles();
      injectPreviewEditStyles();
      checkStatus();
      loadHistory();
      await _restoreActiveConversation();
      _restorePendingUpload();
      setInterval(checkStatus, 30_000);
    });

    async function _restoreActiveConversation() {
      let convId = null;
      try { convId = sessionStorage.getItem(CURRENT_CONV_KEY); } catch { return; }
      if (!convId) return;
      try {
        const res  = await fetch(`/api/history/${Number(convId)}`);
        const data = await res.json();
        if (!data.messages || !data.messages.length) {
          // Conversation không còn tồn tại/đã bị xoá -> dọn key, giữ welcome screen
          try { sessionStorage.removeItem(CURRENT_CONV_KEY); } catch { /* ignore */ }
          return;
        }
        await loadConv(Number(convId));
      } catch {
        try { sessionStorage.removeItem(CURRENT_CONV_KEY); } catch { /* ignore */ }
      }
    }
    function applyAIFaceStatus(isOnline) {
      const cls = isOnline ? 'online' : 'offline';
      document.querySelectorAll('.logo-icon, .welcome-icon').forEach(el => {
        el.classList.remove('online', 'offline');
        el.classList.add(cls);
      });
    }
    function injectImagePreviewStyles() {
      if (document.getElementById('img-preview-styles')) return;
      const style = document.createElement('style');
      style.id = 'img-preview-styles';
      style.textContent = `
        .msg-images {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
          margin-bottom: 6px;
        }
        .upload-banner-thumb {
          width: 28px;
          height: 28px;
          border-radius: 6px;
          object-fit: cover;
          flex-shrink: 0;
        }
        .msg-img-thumb {
          max-width: 220px;
          max-height: 220px;
          border-radius: 10px;
          object-fit: cover;
          cursor: zoom-in;
          border: 1px solid rgba(0,0,0,0.08);
          box-shadow: 0 1px 4px rgba(0,0,0,0.12);
        }
        .msg-img-fallback {
          display: flex;
          align-items: center;
          gap: 6px;
          padding: 8px 12px;
          border-radius: 10px;
          background: rgba(0,0,0,0.05);
          font-size: 13px;
          color: #64748B;
        }
        .img-preview-overlay {
          position: fixed;
          inset: 0;
          background: rgba(0,0,0,0.8);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 9999;
          cursor: zoom-out;
          padding: 24px;
        }
        .img-preview-overlay img {
          max-width: 90vw;
          max-height: 90vh;
          border-radius: 8px;
          box-shadow: 0 8px 32px rgba(0,0,0,0.4);
        }
      `;
      document.head.appendChild(style);
    }

    // CSS phụ trợ cho preview. Phần modal đầy đủ nằm trong style.css.
    function injectPreviewEditStyles() {
      if (document.getElementById('preview-edit-styles')) return;
      const style = document.createElement('style');
      style.id = 'preview-edit-styles';
      style.textContent = `
        .mod-title-right { display:flex; align-items:center; gap:10px; }
        .btn-tc-add, .btn-tc-edit {
          display:inline-flex; align-items:center; justify-content:center; gap:5px;
          border-radius:6px; cursor:pointer; font-family:inherit;
          transition:background .15s,color .15s,border-color .15s;
        }
        .btn-tc-add {
          padding:4px 10px; font-size:11px; font-weight:600;
          background:#EFF6FF; color:var(--c-primary,#2563EB);
          border:1px solid var(--c-primary,#2563EB);
        }
        .btn-tc-add:hover { background:var(--c-primary,#2563EB); color:#fff; }
        .btn-tc-edit, .btn-tc-del {
          width:28px; height:28px; border:none; background:transparent;
          color:#64748B; font-size:12px;
        }
        .btn-tc-edit:hover { background:#DBEAFE; color:#1D4ED8; }
        .btn-tc-del:hover { background:#FEE2E2; color:#DC2626; }
      `;
      document.head.appendChild(style);
    }

    // ── API status ────────────────────────────────────────────────────────────────
    async function checkStatus() {
      const dot = document.getElementById('statusDot');
      // Chèn icon fa-robot một lần duy nhất (nếu chưa có), đồng bộ với logo/welcome.
      if (dot && !dot.querySelector('i')) {
        dot.innerHTML = '<i class="fas fa-robot"></i>';
      }
      try {
        const res  = await fetch('/api/status');
        const data = await res.json();
        const txt  = document.getElementById('statusText');
        if (data.status === 'online') {
          dot.className = 'status-dot online';
          txt.textContent = 'Online';
          applyAIFaceStatus(true);
        } else {
          dot.className = 'status-dot offline';
          txt.textContent = 'Offline – Thiếu API key';
          applyAIFaceStatus(false);
        }
      } catch {
        dot.className = 'status-dot offline';
        document.getElementById('statusText').textContent = 'Offline';
        applyAIFaceStatus(false);
      }
    }

    // ── History ───────────────────────────────────────────────────────────────────
    async function loadHistory() {
      try {
        const res  = await fetch('/api/history');
        const data = await res.json();
        renderConversations(data.conversations || []);
        renderFiles(data.files || []);
      } catch { /* silent */ }
    }

    function cleanTitle(title) {
      if (!title) return 'Cuộc trò chuyện';
      // Xóa IMAGE_GUIDE prefix nếu có
      const cleaned = title
        .replace(/[\s\S]*=== HƯỚNG DẪN PHÂN TÍCH ẢNH ===[\s\S]*/i, '')
        .replace(/^=== HƯỚNG DẪN[\s\S]*/i, '')
        .trim();
      return cleaned || '📷 Phân tích ảnh giao diện';
    }

    function renderConversations(list) {
      allConversations = list || [];
      const term = (document.getElementById('convSearchInput')?.value || '').trim().toLowerCase();
      const filtered = term
        ? allConversations.filter(c => cleanTitle(c.title).toLowerCase().includes(term))
        : allConversations;

      const el = document.getElementById('conversationList');
      if (!filtered.length) {
        el.innerHTML = `<div class="sb-empty">${term ? 'Không tìm thấy cuộc trò chuyện nào' : 'Chưa có lịch sử'}</div>`;
        return;
      }

      const groups = groupByDate(filtered);
      el.innerHTML = groups.map(g => `
        <div class="conv-group-label">${esc(g.label)}</div>
        ${g.items.map(c => renderConvItem(c)).join('')}
      `).join('');
    }

    function renderConvItem(c) {
      const displayTitle = cleanTitle(c.title);
      const tcBadge = (c.test_case_count != null)
        ? `<span class="conv-tc-badge">${c.test_case_count} TC</span>`
        : '';
      return `
        <div class="conv-item ${c.id === currentConvId ? 'active' : ''}"
             onclick="loadConv(${c.id})">
          <i class="fas fa-comment-dots"></i>
          <span class="conv-title" title="${esc(displayTitle)}">${esc(displayTitle)}</span>
          ${tcBadge}
          <span class="conv-time">${fmtDate(c.created_at)}</span>
        </div>`;
    }
    function groupByDate(list) {
      const startOf = d => { const x = new Date(d); x.setHours(0,0,0,0); return x; };
      const today = startOf(new Date());
      const yesterday = new Date(today); yesterday.setDate(today.getDate() - 1);
      const weekAgo = new Date(today); weekAgo.setDate(today.getDate() - 7);

      const buckets = { today: [], yesterday: [], week: [], older: [] };
      list.forEach(c => {
        const d = c.created_at ? startOf(new Date(c.created_at)) : null;
        if (!d || isNaN(d)) { buckets.older.push(c); return; }
        if (d.getTime() === today.getTime()) buckets.today.push(c);
        else if (d.getTime() === yesterday.getTime()) buckets.yesterday.push(c);
        else if (d.getTime() > weekAgo.getTime()) buckets.week.push(c);
        else buckets.older.push(c);
      });

      return [
        { label: 'Hôm nay',    items: buckets.today },
        { label: 'Hôm qua',    items: buckets.yesterday },
        { label: 'Tuần này',   items: buckets.week },
        { label: 'Cũ hơn',     items: buckets.older },
      ].filter(g => g.items.length);
    }

    function filterConversations() {
      renderConversations(allConversations);
    }

    function renderFiles(list) {
      const el = document.getElementById('fileList');
      if (!list.length) {
        el.innerHTML = '<div class="sb-empty">Chưa có file nào</div>';
        return;
      }
      el.innerHTML = list.map(f => `
        <div class="file-item">
          <div class="fi-name"><i class="fas fa-file-excel"></i>
            <span title="${esc(f.filename)}">${esc(shortenFilename(f.filename))}</span></div>
          <div class="fi-meta">
            <span>${fmtDate(f.created_at)}</span>
            <span>${f.test_case_count} TC</span>
          </div>
          <div class="fi-actions">
            <button class="btn-fi btn-fi-dl"  onclick="dlFile('${esc(f.filename)}')">
              <i class="fas fa-download"></i> Tải
            </button>
            <button class="btn-fi btn-fi-del" onclick="delFile('${esc(f.filename)}', this)">
              <i class="fas fa-trash"></i> Xóa
            </button>
          </div>
        </div>
      `).join('');
    }

    // ── Load conversation ─────────────────────────────────────────────────────────
    async function loadConv(convId) {
      try {
        const res  = await fetch(`/api/history/${convId}`);
        const data = await res.json();

        currentConvId = convId;
        _persistCurrentConv();
        uploadedContent  = null;
        uploadedFilename = null;
        uploadedImages   = [];
        uploadedImagePreviews = [];
        document.getElementById('uploadBanner').style.display = 'none';
        _clearPendingUploadStorage();
        const chatArea = document.getElementById('chatArea');
        chatArea.innerHTML = '';
        tcSnapshots.clear();
        activeSnapshotId = null;
        let lastImages = [];
        for (const msg of (data.messages || [])) {
          if (msg.role === 'user') {
            // Ảnh đã tự động lưu ở backend (filename) -> phục vụ lại qua /uploads/
            lastImages = (msg.images || []).map(fn => ({
              filename: fn,
              dataUrl: `/uploads/${encodeURIComponent(fn)}`,
            }));
            appendUserMsg(msg.content, false, lastImages);
          } else if (msg.role === 'assistant') {
            try {
              const parsed = JSON.parse(msg.content);
              const snapshotId = Number(msg.id);
              tcSnapshots.set(snapshotId, parsed);
              currentTCData = parsed;
              activeSnapshotId = snapshotId;
              appendAssistantMsg(parsed, false, lastImages, snapshotId, msg.excel_file || null);
            } catch {
              appendErrMsg(msg.content);
            }
          }
        }
        document.querySelectorAll('.conv-item').forEach(el => el.classList.remove('active'));
        document.querySelectorAll('.conv-item').forEach(el => {
          if (el.getAttribute('onclick') === `loadConv(${convId})`) el.classList.add('active');
        });

        scrollBottom();
      } catch {
        toast('Không thể tải lịch sử cuộc trò chuyện', 'error');
      }
    }
    function newConversation() {
      currentConvId   = null;
      currentTCData   = null;
      tcSnapshots.clear();
      activeSnapshotId = null;
      uploadedContent  = null;
      uploadedFilename = null;
      uploadedImages   = [];
      uploadedImagePreviews = [];
      pendingContextAction = null;
      waitingContextChoice = false;
      contextMode = null;
      skipContextPromptOnce = false;
      _clearPendingUploadStorage();
      try { sessionStorage.removeItem(CURRENT_CONV_KEY); } catch { /* ignore */ }
      document.getElementById('uploadContextModal').style.display = 'none';
      document.getElementById('diffProjectModal').style.display = 'none';

      document.getElementById('chatArea').innerHTML = buildWelcome();
      document.getElementById('previewPanel').style.display = 'none';
      document.getElementById('uploadBanner').style.display = 'none';
      document.getElementById('fileInput').value = '';
      document.getElementById('cameraInput').value = '';

      document.querySelectorAll('.conv-item').forEach(el => el.classList.remove('active'));
      document.getElementById('msgInput').focus();
    }

    function buildWelcome() {
      return `
        <div class="welcome" id="welcomeScreen">
          <div class="welcome-icon"><i class="fas fa-robot"></i></div>
          <h2>Chào mừng đến với AI Test Case Generator</h2>
          <p>Mô tả website và tôi sẽ tự động sinh bộ test case chi tiết</p>

          <div class="section-label">Gợi ý nhanh</div>
          <div class="examples">
            <div class="example-card" onclick="useExample(this)">
              <div class="example-icon domain-school"><i class="fas fa-graduation-cap"></i></div>
              <span>Website quản lý trường học: đăng nhập, quản lý sinh viên, lớp học, môn học, điểm</span></div>
            <div class="example-card" onclick="useExample(this)">
              <div class="example-icon domain-hospital"><i class="fas fa-hospital"></i></div>
              <span>Website quản lý bệnh viện: quản lý bệnh nhân, lịch khám, thanh toán</span></div>
            <div class="example-card" onclick="useExample(this)">
              <div class="example-icon domain-bank"><i class="fas fa-building-columns"></i></div>
              <span>Website quản lý ngân hàng: đăng nhập, chuyển khoản,lịch sử giao dịch, xem báo cáo.</span></div>
          </div>
        </div>`;
    }
    async function sendMsg() {
      const input = document.getElementById('msgInput');
      const msg = input.value.trim();

      // Khi đang chờ lựa chọn, 1/2/3 là COMMAND nội bộ, tuyệt đối không gửi sang AI.
      if (waitingContextChoice) {
        if (!['1', '2', '3'].includes(msg)) {
          toast('Vui lòng chỉ nhập 1, 2 hoặc 3', 'warning');
          input.focus();
          return;
        }
        input.value = '';
        input.style.height = 'auto';
        updateCharCount();
        await handleContextChoice(msg);
        return;
      }

      if (!msg && !uploadedContent && !uploadedImages.length) return;

      if (shouldAskResetContinue() && !skipContextPromptOnce) {
        pendingContextAction = {
          kind: 'send',
          message: msg,
          uploadedContent,
          uploadedFilename,
          uploadedImages: [...uploadedImages],
          uploadedImagePreviews: [...uploadedImagePreviews],
        };
        input.value = '';
        input.style.height = 'auto';
        updateCharCount();
        askContextChoiceInChat();
        return;
      }

      skipContextPromptOnce = false;
      await doSendMsg();
    }
    function _parseSSEBlock(rawEvent) {
      let eventName = 'message';
      const dataLines = [];
      for (const line of rawEvent.split('\n')) {
        if (line.startsWith('event:')) {
          eventName = line.slice(6).trim();
        } else if (line.startsWith('data:')) {
          dataLines.push(line.slice(5).replace(/^ /, ''));
        }
      }
      if (!dataLines.length) return null;
      return { event: eventName, data: dataLines.join('\n') };
    }
    async function _consumeChatSSE(body, onProgress, onError) {
      const reader = body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';
      let resultData = null;
      let errorMsg = null;

      while (true) {
        const { done, value } = await reader.read();
        if (value) buffer += decoder.decode(value, { stream: true });

        let sepIdx;
        while ((sepIdx = buffer.indexOf('\n\n')) !== -1) {
          const rawEvent = buffer.slice(0, sepIdx);
          buffer = buffer.slice(sepIdx + 2);
          const parsed = _parseSSEBlock(rawEvent);
          if (!parsed) continue;

          if (parsed.event === 'progress') {
            try { onProgress(JSON.parse(parsed.data)); } catch { /* event lỗi định dạng — bỏ qua, không chặn stream */ }
          } else if (parsed.event === 'result') {
            try { resultData = JSON.parse(parsed.data); }
            catch { errorMsg = 'Kết quả trả về không hợp lệ (JSON lỗi).'; }
          } else if (parsed.event === 'error') {
            try { errorMsg = (JSON.parse(parsed.data) || {}).message || 'Lỗi không xác định.'; }
            catch { errorMsg = 'Lỗi không xác định.'; }
            if (onError) onError(errorMsg);
          }
        }
        if (done) break;
      }
      return { data: resultData, error: errorMsg };
    }
    let currentChatAbortController = null;
    async function doSendMsg() {
      const input = document.getElementById('msgInput');
      let msg = input.value.trim();
      if (!msg && !uploadedContent && !uploadedImages.length) return;
      if (uploadedContent) {
        const fileNote = `[Tài liệu đặc tả: "${uploadedFilename}"]\n${uploadedContent}`;
        msg = msg ? `${msg}\n\n${fileNote}` : fileNote;
      }
      if (uploadedImages.length && !msg) {
        msg = 'Phân tích giao diện';
      }

      const typedText = input.value.trim();
      const displayMsg = typedText || (uploadedImages.length ? '' : `📎 ${uploadedFilename || 'Ảnh đính kèm'}`);
      input.value = '';
      input.style.height = 'auto';
      updateCharCount();

      const imageBlocksToSend = uploadedImages.length ? [...uploadedImages] : null;
      // Ảnh để hiển thị thumbnail thật trong bubble chat của user
      const imagePreviewsToShow = uploadedImagePreviews.length ? [...uploadedImagePreviews] : [];
      // Xóa upload banner ngay (UX), nhưng giữ uploadedImages đến khi fetch xong
      const hadUpload = !!(uploadedContent || uploadedImages.length);
      if (hadUpload) {
        document.getElementById('uploadBanner').style.display = 'none';
        document.getElementById('fileInput').value = '';
        document.getElementById('cameraInput').value = '';
      }

      // Remove welcome screen
      const ws = document.getElementById('welcomeScreen');
      if (ws) ws.remove();
      appendUserMsg(displayMsg, true, imagePreviewsToShow);
      const typingId = showTyping();
      document.getElementById('btnSend').disabled = true;
      showLoading();
      if (currentChatAbortController) currentChatAbortController.abort();
      const abortController = new AbortController();
      currentChatAbortController = abortController;

      try {
        const res = await fetch('/api/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            message: msg,
            display_message: displayMsg,
            conversation_id: currentConvId,
            context_mode: contextMode || 'new',
            image_blocks: imageBlocksToSend,
            // Tự động lưu ảnh: gửi kèm tên file (đã lưu sẵn ở /api/upload) để
            // backend gắn với message, phục vụ khôi phục lại khi load conversation.
            image_filenames: imagePreviewsToShow.length
              ? imagePreviewsToShow.map(p => p.filename)
              : null,
          }),
          signal: abortController.signal,
        });
        if (!res.ok) {
          let serverMsg = '';
          try { serverMsg = (await res.json()).error; } catch { /* body không phải JSON */ }
          throw new Error(serverMsg || `HTTP ${res.status}`);
        }

        const data = await res.json();
        console.log('API /api/chat response:', data);

        removeTyping(typingId);
        hideLoading();
        if (!data || data.error || !data.test_cases) {
          const msgErr = (data && data.error) || 'Không nhận được kết quả từ server.';
          appendErrMsg(msgErr);
          toast(msgErr, 'error');
        } else {
          currentConvId = data.conversation_id;
          currentTCData = data.test_cases;
          activeSnapshotId = Number(data.snapshot_id);
          tcSnapshots.set(activeSnapshotId, data.test_cases);
          _persistCurrentConv();
          // Reset upload state chỉ sau khi fetch thành công
          uploadedContent  = null;
          uploadedFilename = null;
          uploadedImages   = [];
          uploadedImagePreviews = [];
          _clearPendingUploadStorage();
          appendAssistantMsg(data.test_cases, true, imagePreviewsToShow, activeSnapshotId, null);
          contextMode = null;

          // Cập nhật title conversation = project_name của AI
          const projectName = cleanProjectName(data.test_cases?.project_name);
          if (projectName && currentConvId) {
            fetch(`/api/history/${currentConvId}/title`, {
              method: 'PATCH',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ title: projectName }),
            }).catch(() => {/* silent */});
          }

          loadHistory();
        }
      } catch (err) {
        removeTyping(typingId);
        hideLoading();
        if (err.name !== 'AbortError') {
          const realMsg = err.message && !/^HTTP \d+$/.test(err.message)
            ? err.message
            : 'Lỗi kết nối đến server. Vui lòng thử lại.';
          appendErrMsg(realMsg);
          toast(realMsg, 'error');
        }
      } finally {
        if (currentChatAbortController === abortController) {
          currentChatAbortController = null;
        }
        document.getElementById('btnSend').disabled = false;
        document.getElementById('msgInput').focus();
      }
    }

    // ── Append messages ───────────────────────────────────────────────────────────
    function cleanUserMsg(text) {
      if (!text) return '';
      // Xóa IMAGE_GUIDE khỏi nội dung hiển thị, giữ lại phần text thuần của user
      return text.replace(/\s*===\s*HƯỚNG DẪN PHÂN TÍCH ẢNH\s*===[\s\S]*/i, '').trim()
             || '📷 Ảnh giao diện';
    }

    function cleanProjectName(name) {
      if (!name) return '';
      return name
        .replace(/[\s\S]*===\s*HƯỚNG DẪN PHÂN TÍCH ẢNH\s*===[\s\S]*/i, '')
        .replace(/^===.*?===/i, '')
        .replace(/^(Phân tích toàn bộ|Tạo NHIỀU chức năng|Yêu cầu BẮT BUỘC)[\s\S]*/i, '')
        .trim()
        || 'My Project';
    }

    function appendUserMsg(text, animate = true, images = []) {
      const ca = document.getElementById('chatArea');
      const d  = document.createElement('div');
      d.className = `msg user${animate ? '' : ' instant'}`;
      const display = cleanUserMsg(text);

      const imagesHtml = (images && images.length)
        ? `<div class="msg-images">
            ${images.map(img => img.dataUrl
              ? `<img src="${esc(img.dataUrl)}" alt="${esc(img.filename || 'Ảnh đính kèm')}"
                      class="msg-img-thumb" onclick="openImagePreview('${esc(img.dataUrl)}')" />`
              : `<div class="msg-img-fallback"><i class="fas fa-image"></i> ${esc(img.filename || 'Ảnh')}</div>`
            ).join('')}
          </div>`
        : '';
      const bubbleHtml = display ? `<div class="bubble">${esc(display)}</div>` : '';

      d.innerHTML = `
        <div class="msg-avatar"><i class="fas fa-user"></i></div>
        <div class="msg-content">
          ${imagesHtml}
          ${bubbleHtml}
          <div class="msg-time">${now()}</div>
        </div>`;
      ca.appendChild(d);
      scrollBottom();
    }

    // Xem ảnh phóng to khi click vào thumbnail trong chat
    function openImagePreview(dataUrl) {
      const overlay = document.createElement('div');
      overlay.className = 'img-preview-overlay';
      overlay.onclick = () => overlay.remove();
      overlay.innerHTML = `<img src="${esc(dataUrl)}" alt="Xem ảnh" />`;
      document.body.appendChild(overlay);
    }

    function appendAssistantMsg(tcData, animate = true, images = [], snapshotId = null, excelFile = null) {
      snapshotId = snapshotId != null ? Number(snapshotId) : null;
      if (snapshotId != null) tcSnapshots.set(snapshotId, tcData);
      const modules    = tcData.modules || {};
      const displayGroups = buildDisplayGroups(modules);
      const modCount   = displayGroups.length;
      const totalTC    = Object.values(modules).reduce((s, a) => s + a.length, 0);
      const projName   = cleanProjectName(tcData.project_name) || 'Project';

      // Thumbnail ảnh đã được AI phân tích để sinh ra bộ TC này — hiện lại ở
      // bubble AI cho user dễ đối chiếu, không chỉ ở bubble user nữa.
      const imagesHtml = (images && images.length)
        ? `<div class="msg-images">
            ${images.map(img => img.dataUrl
              ? `<img src="${esc(img.dataUrl)}" alt="${esc(img.filename || 'Ảnh đã phân tích')}"
                      class="msg-img-thumb" onclick="openImagePreview('${esc(img.dataUrl)}')" />`
              : `<div class="msg-img-fallback"><i class="fas fa-image"></i> ${esc(img.filename || 'Ảnh')}</div>`
            ).join('')}
          </div>`
        : '';

      const ca = document.getElementById('chatArea');
      const d  = document.createElement('div');
      d.className = 'msg assistant';
      d.innerHTML = `
        <div class="msg-avatar"><i class="fas fa-robot"></i></div>
        <div class="msg-content">
          ${imagesHtml}
          <div class="bubble">
            <strong>✅ Sinh test case thành công!</strong><br>
            Dự án: <strong>${esc(projName)}</strong><br>
            ${esc(tcData.description || 'Đã phân tích và tạo bộ test case chi tiết.')}
          </div>
          <div class="tc-summary">
            <span class="badge badge-mod"><i class="fas fa-layer-group"></i> ${modCount} chức năng</span>
            <span class="badge badge-tc"><i class="fas fa-list-check"></i> ${totalTC} test cases</span>
          </div>
          <div class="msg-actions">
            <button class="btn-ma btn-ma-preview" onclick="showPreview(${snapshotId == null ? 'null' : snapshotId})">
              <i class="fas fa-eye"></i> Xem preview
            </button>
            <button class="btn-ma btn-ma-excel" onclick="generateExcel(${snapshotId == null ? 'null' : snapshotId})">
              <i class="fas fa-file-excel"></i> Tạo file Excel
            </button>
            ${excelFile ? `<a class="btn-ma btn-ma-excel" href="/download/${encodeURIComponent(excelFile)}" download>
              <i class="fas fa-download"></i> Tải Excel phiên bản này
            </a>` : ''}
          </div>
          <div class="msg-time">${now()}</div>
        </div>`;
      ca.appendChild(d);
      scrollBottom();
    }

    function appendErrMsg(msg) {
      const ca = document.getElementById('chatArea');
      const d  = document.createElement('div');
      d.className = 'msg error';
      d.innerHTML = `
        <div class="msg-avatar"><i class="fas fa-triangle-exclamation"></i></div>
        <div class="msg-content">
          <div class="bubble">⚠️ ${esc(msg)}</div>
          <div class="msg-time">${now()}</div>
        </div>`;
      ca.appendChild(d);
      scrollBottom();
    }

    function appendDownloadMsg(filename, dlUrl) {
      const ca = document.getElementById('chatArea');
      const d  = document.createElement('div');
      d.className = 'msg assistant';
      d.innerHTML = `
        <div class="msg-avatar" style="background:linear-gradient(135deg,#16A34A,#15803D)">
          <i class="fas fa-file-excel"></i>
        </div>
        <div class="msg-content">
          <div class="bubble">
            <strong>📊 File Excel đã sẵn sàng!</strong><br>
            <small style="color:#64748B">${esc(filename)}</small>
          </div>
          <div class="msg-actions" style="margin-top:8px">
            <a href="${dlUrl}" download class="btn-download">
              <i class="fas fa-download"></i> Tải xuống file Excel
            </a>
          </div>
          <div class="msg-time">${now()}</div>
        </div>`;
      ca.appendChild(d);
      scrollBottom();
    }

    // ── Typing indicator ──────────────────────────────────────────────────────────
    function showTyping() {
      const id = `ty_${Date.now()}`;
      const ca = document.getElementById('chatArea');
      const d  = document.createElement('div');
      d.id = id;
      d.className = 'msg assistant';
      d.innerHTML = `
        <div class="msg-avatar"><i class="fas fa-robot"></i></div>
        <div class="msg-content">
          <div class="typing"><div class="t-dot"></div><div class="t-dot"></div><div class="t-dot"></div></div>
        </div>`;
      ca.appendChild(d);
      scrollBottom();
      return id;
    }

    function removeTyping(id) {
      const el = document.getElementById(id);
      if (el) el.remove();
    }
    function splitModuleOutcome(name) {
      const trimmed = String(name || '').trim();
      const lower = trimmed.toLowerCase();
      // Thứ tự quan trọng: "không thành công" phải kiểm tra TRƯỚC "thành
      // công" vì nó chứa "thành công" như hậu tố con. Đồng bộ với
      // _OUTCOME_SUFFIXES / get_base_module_name() ở app.py.
      if (lower.endsWith(' không thành công')) {
        return { base: trimmed.slice(0, -(' không thành công'.length)).trim(), group: 'failure' };
      }
      if (lower.endsWith(' thất bại')) {
        return { base: trimmed.slice(0, -(' thất bại'.length)).trim(), group: 'failure' };
      }
      if (lower.endsWith(' thành công')) {
        return { base: trimmed.slice(0, -(' thành công'.length)).trim(), group: 'success' };
      }
      return { base: trimmed, group: 'other' };
    }

    function buildDisplayGroups(modules) {
      const order = [];
      const groupMap = new Map();
      for (const [modName, tcs] of Object.entries(modules)) {
        if (!Array.isArray(tcs)) continue;
        const { base, group } = splitModuleOutcome(modName);
        if (!groupMap.has(base)) {
          groupMap.set(base, { success: null, failure: null, others: [] });
          order.push(base);
        }
        const g = groupMap.get(base);
        if (group === 'success' && !g.success) g.success = { modName, tcs };
        else if (group === 'failure' && !g.failure) g.failure = { modName, tcs };
        else g.others.push({ modName, tcs });
      }

      return order.map(base => {
        const g = groupMap.get(base);
        const rows = [];
        // Đồng bộ Chức năng = tên chức năng GỐC (base, đã gộp thành công/
        // không thành công) cho MỌI testcase trong nhóm — mutate thẳng vào
        // object tc thật (cùng reference với currentTCData.modules), để
        // popup chỉnh sửa/lưu thay đổi/xuất Excel đều thấy dữ liệu nhất
        // quán. KHÔNG đụng vào tc.title (title vẫn giữ "... thành công" /
        // "... không thành công").
        const syncModuleFields = (tc) => {
          if (tc && typeof tc === 'object') {
            tc.module = base;
            tc['chức năng'] = base;
            tc.feature = base;
          }
          return tc;
        };
        if (g.success) g.success.tcs.forEach((tc, idx) => rows.push({ tc: syncModuleFields(tc), sourceModule: g.success.modName, sourceIndex: idx }));
        if (g.failure) g.failure.tcs.forEach((tc, idx) => rows.push({ tc: syncModuleFields(tc), sourceModule: g.failure.modName, sourceIndex: idx }));
        g.others.forEach(o => o.tcs.forEach((tc, idx) => rows.push({ tc: syncModuleFields(tc), sourceModule: o.modName, sourceIndex: idx })));
        const defaultAddModule =
          (g.success && g.success.modName) ||
          (g.failure && g.failure.modName) ||
          (g.others[0] && g.others[0].modName) ||
          base;
        return { displayName: base, rows, defaultAddModule };
      });
    }

    // ── Preview panel: thêm/sửa bằng modal; chọn dòng rồi xóa ở đầu chức năng ─────────
    function showPreview(snapshotId = activeSnapshotId) {
      if (snapshotId != null) {
        snapshotId = Number(snapshotId);
        const snapshotData = tcSnapshots.get(snapshotId);
        if (!snapshotData) {
          toast('Không tìm thấy dữ liệu của phiên bản testcase này', 'error');
          return;
        }
        activeSnapshotId = snapshotId;
        currentTCData = snapshotData;
      }
      if (!currentTCData) return;
      const panel = document.getElementById('previewPanel');
      const body  = document.getElementById('previewBody');
      const modules = currentTCData.modules || {};
      const displayGroups = buildDisplayGroups(modules);
      let html = '';

      for (const group of displayGroups) {
        html += `
          <div class="mod-preview" data-add-mod="${escAttr(group.defaultAddModule)}">
            <div class="mod-title">
              <span>${esc(group.displayName)}</span>
              <span class="mod-title-right">
                <span class="tc-count">${group.rows.length} test cases</span>
                <button class="btn-tc-add" title="Thêm testcase mới"><i class="fas fa-plus"></i> Thêm testcase</button>
                <button class="btn-tc-delete-selected" title="Xóa testcase đã chọn"><i class="fas fa-trash"></i> Xóa testcase</button>
              </span>
            </div>
            <table class="preview-tbl">
              <thead><tr>
                <th style="width:32px">STT</th><th>Mã TC</th><th>Chức năng</th>
                <th>Tình huống</th><th style="width:120px;min-width:120px">Ưu tiên</th><th>Loại test</th><th style="width:84px">Trạng thái</th><th style="width:82px">Thao tác</th>
              </tr></thead>
              <tbody>
                ${group.rows.map((r, i) => renderTcRow(r.tc, i, r.sourceModule, r.sourceIndex, group.displayName)).join('')}
              </tbody>
            </table>
          </div>`;
      }
      body.innerHTML = html || '<div class="sb-empty">Chưa có test case</div>';
      panel.style.display = 'flex';
      panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      bindPreviewEditEvents();
    }
    const TEST_TYPE_OPTS = [
      'Kiểm thử chức năng',
      'Kiểm thử dương',
      'Kiểm thử âm',
      'Kiểm thử xác thực',
      'Kiểm thử biên',
      'Kiểm thử giao diện',
      'Kiểm thử phân quyền',
      'Kiểm thử bảo mật',
      'Kiểm thử tích hợp',
    ];
    const TEST_TYPE_DEFAULT = 'Kiểm thử chức năng';
    const PRIORITY_OPTS = ['Cao', 'Trung bình', 'Thấp'];
    const STATUS_OPTS = ['Chưa chạy', 'Đạt', 'Không đạt', 'Chờ xử lý'];

    const TC_FIELD_DEFAULTS = {
      id: '', module: '', feature: '', title: '', scenario: '', description: '',
      given: '', when: '', then: '', precondition: '', steps: '', test_data: '',
      expected_result: '', priority: 'Trung bình', test_type: TEST_TYPE_DEFAULT,
      actual_result: '', status: 'Chưa chạy', note: '',
    };

    let editingTcState = null; // { mode:'add'|'edit', moduleName, index }
    let pendingDeleteTc = null; // { moduleName, index }

    // State cho tính năng "Sinh lại" (regenerate theo phạm vi) — xem
    // openRegenerateScopeModal()/confirmRegenerate(). moduleName/testcaseId
    // luôn là tên chức năng GỐC (không hậu tố thành công/không thành công),
    // vì đây là phạm vi mà backend enforce khi ép lại module/chức năng/feature.
    let regenerateContext = {
      testcaseId: null,
      moduleName: null,
      currentTestcase: null,
      allTestcasesInModule: [],
      selectedScope: 'single_testcase',
    };
    let regenerateInFlight = false;

    function normalizePriority(value) {
      const map = { High:'Cao', Medium:'Trung bình', Low:'Thấp', Cao:'Cao', 'Trung bình':'Trung bình', Thấp:'Thấp' };
      return map[value] || 'Trung bình';
    }

    function normalizeStatus(value) {
      const map = {
        'Not Run':'Chưa chạy', Passed:'Đạt', Failed:'Không đạt', Pending:'Chờ xử lý',
        'Chưa chạy':'Chưa chạy', Đạt:'Đạt', 'Không đạt':'Không đạt', 'Chờ xử lý':'Chờ xử lý'
      };
      return map[value] || 'Chưa chạy';
    }

    function normalizeTestType(value) {
      const aliases = {
        'chức năng':'Kiểm thử chức năng', 'kiểm thử chức năng':'Kiểm thử chức năng',
        'dương':'Kiểm thử dương', 'positive':'Kiểm thử dương', 'kiểm thử dương':'Kiểm thử dương',
        'âm':'Kiểm thử âm', 'negative':'Kiểm thử âm', 'kiểm thử âm':'Kiểm thử âm',
        'xác thực':'Kiểm thử xác thực', 'validation':'Kiểm thử xác thực', 'kiểm thử xác thực':'Kiểm thử xác thực',
        'biên':'Kiểm thử biên', 'boundary':'Kiểm thử biên', 'kiểm thử biên':'Kiểm thử biên',
        'giao diện':'Kiểm thử giao diện', 'ui':'Kiểm thử giao diện', 'kiểm thử giao diện':'Kiểm thử giao diện',
        'phân quyền':'Kiểm thử phân quyền', 'permission':'Kiểm thử phân quyền', 'kiểm thử phân quyền':'Kiểm thử phân quyền',
        'bảo mật':'Kiểm thử bảo mật', 'security':'Kiểm thử bảo mật', 'kiểm thử bảo mật':'Kiểm thử bảo mật',
        'tích hợp':'Kiểm thử tích hợp', 'integration':'Kiểm thử tích hợp', 'kiểm thử tích hợp':'Kiểm thử tích hợp',
      };
      const raw = String(value || '').trim();
      if (TEST_TYPE_OPTS.includes(raw)) return raw;
      return aliases[raw.toLowerCase()] || TEST_TYPE_DEFAULT;
    }

    function testTypeClass(v) {
      const map = {
        'Kiểm thử chức năng':'tt-chuc-nang', 'Kiểm thử dương':'tt-duong',
        'Kiểm thử âm':'tt-am', 'Kiểm thử xác thực':'tt-xac-thuc',
        'Kiểm thử biên':'tt-bien', 'Kiểm thử giao diện':'tt-giao-dien',
        'Kiểm thử phân quyền':'tt-phan-quyen', 'Kiểm thử bảo mật':'tt-bao-mat',
        'Kiểm thử tích hợp':'tt-tich-hop',
      };
      return map[normalizeTestType(v)] || 'tt-chuc-nang';
    }

    function getDisplayFeatureName(tc, sourceModule) {
      const rawName =
        tc.feature ||
        tc.module ||
        tc.function_name ||
        tc.chuc_nang ||
        tc['chức năng'] ||
        sourceModule ||
        '';
      return String(rawName)
        .replace(/\s+không\s+thành\s+công\s*$/i, '')
        .replace(/\s+thành\s+công\s*$/i, '')
        .trim() || 'Chưa xác định';
    }

    function renderTcRow(tc, i, sourceModule, sourceIndex, moduleName) {
      const pri = normalizePriority(tc.priority);
      const status = normalizeStatus(tc.status);
      const testType = normalizeTestType(tc.test_type);
      // Cột "Chức năng" của TỪNG DÒNG lấy theo bucket gốc (sourceModule,
      // ví dụ "Đăng nhập thành công" / "Đăng nhập không thành công") —
      // KHÔNG dùng moduleName (tên đã gộp nhóm, không hậu tố) nữa, để mỗi
      // dòng hiển thị đúng chức năng gốc mà nó thuộc về. moduleName chỉ
      // còn dùng làm fallback nếu sourceModule rỗng.
      const displayFeature = sourceModule || moduleName || getDisplayFeatureName(tc, sourceModule);
      return `
        <tr data-idx="${sourceIndex}" data-mod="${escAttr(sourceModule)}">
          <td style="text-align:center">${i + 1}</td>
          <td>${esc(tc.id || '')}</td>
          <td>${esc(displayFeature)}</td>
          <td class="scenario-cell">${esc(tc.scenario || tc.title || tc.description || 'Chưa có tình huống').replace(/\r?\n/g, '<br>')}</td>
          <td><span class="tc-pill priority-${escAttr(pri.toLowerCase().replace(/\s+/g,'-'))}">${esc(pri)}</span></td>
          <td><span class="tc-pill ${testTypeClass(testType)}">${esc(testType)}</span></td>
          <td><span class="tc-pill status-${escAttr(status.toLowerCase().replace(/\s+/g,'-'))}">${esc(status)}</span></td>
          <td class="tc-actions-cell">
            <button class="btn-tc-edit" title="Chỉnh sửa testcase"><i class="fas fa-pen"></i></button>
          </td>
        </tr>`;
    }

    let previewEditBound = false;
    function bindPreviewEditEvents() {
      if (previewEditBound) return;
      previewEditBound = true;
      const body = document.getElementById('previewBody');
      body.addEventListener('click', (e) => {
        const row = e.target.closest('tr');
        const moduleBox = e.target.closest('.mod-preview');
        if (!moduleBox) return;

        if (e.target.closest('.btn-tc-edit')) {
          if (row) openTestCaseModal('edit', row.dataset.mod, Number(row.dataset.idx));
          return;
        }
        if (e.target.closest('.btn-tc-add')) {
          openTestCaseModal('add', moduleBox.dataset.addMod, null);
          return;
        }
        if (e.target.closest('.btn-tc-delete-selected')) {
          const selectedRow = moduleBox.querySelector('tbody tr.tc-row-selected');
          if (!selectedRow) {
            toast('Hãy chọn một testcase trong chức năng trước khi xóa', 'warning');
            return;
          }
          deleteTestCaseRow(selectedRow.dataset.mod, Number(selectedRow.dataset.idx));
          return;
        }
        if (row && !e.target.closest('button')) {
          moduleBox.querySelectorAll('tbody tr.tc-row-selected')
            .forEach(item => item.classList.remove('tc-row-selected'));
          row.classList.add('tc-row-selected');
        }
      });
    }

    function syncEditsFromDOM() {
      // Đảm bảo module/chức năng/feature đã đồng bộ về tên chức năng gốc
      // TRƯỚC khi xuất Excel, kể cả khi người dùng chưa từng mở Preview
      // (buildDisplayGroups mutate thẳng tc object bên trong
      // currentTCData.modules, không tạo bản sao).
      if (currentTCData?.modules) buildDisplayGroups(currentTCData.modules);
      return currentTCData;
    }

    function buildNextTcId() {
      let maxNum = 0;
      Object.values(currentTCData?.modules || {}).forEach(list => {
        (list || []).forEach(tc => {
          const m = String(tc.id || '').match(/(\d+)$/);
          if (m) maxNum = Math.max(maxNum, Number(m[1]));
        });
      });
      return `TC_${String(maxNum + 1).padStart(3, '0')}`;
    }

    function getTcFormValue(field) {
      const el = document.getElementById(`tcForm_${field}`);
      return el ? el.value.trim() : '';
    }

    function setTcFormValue(field, value) {
      const el = document.getElementById(`tcForm_${field}`);
      if (el) el.value = value == null ? '' : String(value);
    }

    function openTestCaseModal(mode, moduleName, index = null) {
      if (!currentTCData?.modules?.[moduleName]) return;
      // Chức năng hiển thị trong popup PHẢI là tên chức năng GỐC, bỏ hậu
      // tố "thành công"/"không thành công" — hậu tố đó chỉ thuộc về title,
      // không thuộc về module/chức năng (xem splitModuleOutcome).
      const baseModuleName = splitModuleOutcome(moduleName).base || moduleName;
      const source = mode === 'edit'
        ? currentTCData.modules[moduleName][index]
        : { ...TC_FIELD_DEFAULTS, id: buildNextTcId(), module: baseModuleName, feature: baseModuleName };
      if (!source) return;

      editingTcState = { mode, moduleName, index };
      document.getElementById('testCaseModalTitle').textContent = mode === 'edit' ? 'Chỉnh sửa Test Case' : 'Thêm Test Case';
      document.getElementById('testCaseModalModeHint').textContent = mode === 'edit'
        ? `Đang chỉnh sửa ${source.id || ''}`
        : `Thêm vào chức năng: ${baseModuleName}`;

      Object.keys(TC_FIELD_DEFAULTS).forEach(field => {
        let value = source[field];
        if (field === 'priority') value = normalizePriority(value);
        if (field === 'status') value = normalizeStatus(value);
        if (field === 'test_type') value = normalizeTestType(value);
        setTcFormValue(field, value ?? TC_FIELD_DEFAULTS[field]);
      });
      // Ưu tiên đọc: tc["chức năng"] || tc.module || tên chức năng gốc của
      // module hiện tại. KHÔNG bao giờ lấy tc.title cho field Chức năng.
      setTcFormValue('module', source['chức năng'] || source.module || baseModuleName);
      setTcFormValue('feature', source['chức năng'] || source.feature || source.module || baseModuleName);
      document.getElementById('testCaseFormError').style.display = 'none';
      document.getElementById('testCaseModal').style.display = 'flex';
      setTimeout(() => document.getElementById('tcForm_title')?.focus(), 50);
    }

    function closeTestCaseModal() {
      document.getElementById('testCaseModal').style.display = 'none';
      editingTcState = null;
    }

    function collectTestCaseForm() {
      const tc = {};
      Object.keys(TC_FIELD_DEFAULTS).forEach(field => { tc[field] = getTcFormValue(field); });
      tc.priority = normalizePriority(tc.priority);
      tc.status = normalizeStatus(tc.status);
      tc.test_type = normalizeTestType(tc.test_type);
      // module và feature PHẢI là cùng 1 giá trị Chức năng — không để 2 ô
      // input tách rời sinh ra dữ liệu lệch nhau (feature != module).
      tc.feature = tc.module;
      return tc;
    }

    function validateTestCaseForm(tc) {
      const missing = [];
      if (!tc.id) missing.push('Mã TC');
      if (!tc.module) missing.push('Chức năng');
      if (!tc.scenario && !tc.title) missing.push('Tình huống hoặc Tiêu đề');
      if (!tc.steps) missing.push('Các bước thực hiện');
      if (!tc.expected_result) missing.push('Kết quả mong đợi');
      if (missing.length) return `Vui lòng nhập: ${missing.join(', ')}.`;
      return '';
    }

    // Xác định module/bucket sẽ lưu TC vào. Chức năng hiển thị trong popup
    // luôn là tên GỐC (không hậu tố), nhưng bucket lưu trữ bên trong vẫn
    // cần tách theo thành công/không thành công (dùng cho gộp rowspan
    // Preview/Excel) — nếu người dùng không thực sự đổi sang MỘT chức
    // năng khác (chỉ là tên gốc trùng với bucket hiện tại), phải giữ
    // nguyên bucket cũ để KHÔNG tạo module mới trùng chức năng gốc.
    function resolveSaveTargetModule(typedModule, currentModuleName) {
      const typed = String(typedModule || '').trim();
      if (!typed) return currentModuleName;
      const typedBase = splitModuleOutcome(typed).base;
      const current = splitModuleOutcome(currentModuleName);
      if (current.group !== 'other' && typedBase === current.base) {
        return currentModuleName;
      }
      return typed;
    }

    function saveTestCaseModal(triggerRegenerate = false) {
      if (!editingTcState || !currentTCData) return;
      const tc = collectTestCaseForm();
      const error = validateTestCaseForm(tc);
      const errEl = document.getElementById('testCaseFormError');
      if (error) {
        errEl.textContent = error;
        errEl.style.display = 'block';
        return;
      }

      const { mode, moduleName, index } = editingTcState;
      const targetModule = resolveSaveTargetModule(tc.module, moduleName);
      if (!currentTCData.modules[targetModule]) currentTCData.modules[targetModule] = [];

      let merged = tc;
      let savedIndex = index;
      if (mode === 'edit') {
        const original = currentTCData.modules[moduleName][index] || {};
        merged = { ...original, ...tc }; // giữ lại mọi key metadata chưa hiển thị trong form
        if (targetModule !== moduleName) {
          currentTCData.modules[moduleName].splice(index, 1);
          currentTCData.modules[targetModule].push(merged);
          if (!currentTCData.modules[moduleName].length) delete currentTCData.modules[moduleName];
          savedIndex = currentTCData.modules[targetModule].length - 1;
        } else {
          currentTCData.modules[moduleName][index] = merged;
          savedIndex = index;
        }
      } else {
        merged = { ...TC_FIELD_DEFAULTS, ...tc };
        currentTCData.modules[targetModule].push(merged);
        savedIndex = currentTCData.modules[targetModule].length - 1;
      }

      if (triggerRegenerate) {
        if (mode !== 'edit') {
          toast('Chỉ có thể "Sinh lại" cho testcase đã tồn tại, không áp dụng khi thêm mới', 'warning');
          return;
        }
        showPreview(activeSnapshotId);
        openRegenerateScopeModal(targetModule, savedIndex);
        return;
      }

      closeTestCaseModal();
      showPreview(activeSnapshotId);
      toast(mode === 'edit' ? 'Đã cập nhật testcase — nhớ bấm "Lưu thay đổi"' : 'Đã thêm testcase — nhớ bấm "Lưu thay đổi"', 'success');
    }

    // ── Sinh lại testcase theo phạm vi ───────────────────────────────────────
    function openRegenerateScopeModal(moduleName, index) {
      const tc = currentTCData?.modules?.[moduleName]?.[index];
      if (!tc) { toast('Không tìm thấy testcase để sinh lại', 'error'); return; }
      regenerateContext = {
        testcaseId: tc.id,
        moduleName,
        currentTestcase: structuredClone(tc),
        allTestcasesInModule: structuredClone(currentTCData.modules[moduleName]),
        selectedScope: 'single_testcase',
      };
      document.getElementById('regenScopeSingle').checked = true;
      const btn = document.getElementById('btnRegenConfirm');
      if (btn) { btn.disabled = false; btn.innerHTML = '<i class="fas fa-rotate"></i> Sinh lại'; }
      document.getElementById('regenerateScopeModal').style.display = 'flex';
    }

    function closeRegenerateScopeModal() {
      if (regenerateInFlight) return; // không cho đóng giữa chừng khi đang gọi API
      document.getElementById('regenerateScopeModal').style.display = 'none';
    }

    async function confirmRegenerate() {
      if (regenerateInFlight) return; // chống bấm nhiều lần → chỉ 1 request
      if (!currentConvId) {
        toast('Cần lưu cuộc trò chuyện trước khi sinh lại testcase', 'warning');
        return;
      }
      const scope = document.querySelector('input[name="regenScope"]:checked')?.value || 'single_testcase';
      regenerateContext.selectedScope = scope;
      const { moduleName, testcaseId, currentTestcase, allTestcasesInModule } = regenerateContext;

      const payload = scope === 'single_testcase'
        ? { scope, module_name: moduleName, testcase_id: testcaseId, testcase: currentTestcase, snapshot_id: activeSnapshotId }
        : { scope, module_name: moduleName, testcases: allTestcasesInModule, snapshot_id: activeSnapshotId };

      regenerateInFlight = true;
      const btn = document.getElementById('btnRegenConfirm');
      const cancelBtn = document.getElementById('btnRegenCancel');
      if (btn) { btn.disabled = true; btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Đang sinh lại…'; }
      if (cancelBtn) cancelBtn.disabled = true;

      try {
        const res = await fetch(`/api/history/${currentConvId}/test-cases/regenerate`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (!res.ok || !data.success) throw new Error(data.error || 'Sinh lại thất bại');

        currentTCData = data.test_cases;
        if (data.snapshot_id != null) {
          activeSnapshotId = Number(data.snapshot_id);
          tcSnapshots.set(activeSnapshotId, currentTCData);
        }
        document.getElementById('regenerateScopeModal').style.display = 'none';
        closeTestCaseModal();
        showPreview(activeSnapshotId);
        loadHistory();
        toast(
          scope === 'single_testcase'
            ? `Đã sinh lại testcase ${testcaseId}`
            : `Đã sinh lại toàn bộ chức năng "${moduleName}"`,
          'success'
        );
      } catch (err) {
        // Lỗi: giữ nguyên testcase cũ, không đóng modal, báo lỗi rõ ràng.
        toast('Sinh lại thất bại: ' + (err.message || 'lỗi không xác định'), 'error');
      } finally {
        regenerateInFlight = false;
        if (btn) { btn.disabled = false; btn.innerHTML = '<i class="fas fa-rotate"></i> Sinh lại'; }
        if (cancelBtn) cancelBtn.disabled = false;
      }
    }
    function addTestCaseRow(modName) {
      openTestCaseModal('add', modName, null);
    }

    function deleteTestCaseRow(modName, idx) {
      if (!currentTCData?.modules?.[modName]?.[idx]) return;
      pendingDeleteTc = { moduleName: modName, index: idx };
      const tc = currentTCData.modules[modName][idx];
      const label = document.getElementById('deleteTcLabel');
      if (label) label.textContent = `${tc.id || ''}${tc.title || tc.scenario ? ' — ' + (tc.title || tc.scenario) : ''}`;
      document.getElementById('deleteTcConfirmModal').style.display = 'flex';
    }

    function closeDeleteTcConfirm() {
      document.getElementById('deleteTcConfirmModal').style.display = 'none';
      pendingDeleteTc = null;
    }

    function confirmDeleteTc() {
      if (!pendingDeleteTc || !currentTCData) return;
      const { moduleName, index } = pendingDeleteTc;
      const list = currentTCData.modules?.[moduleName];
      if (!list?.[index]) return closeDeleteTcConfirm();
      list.splice(index, 1);
      if (!list.length) delete currentTCData.modules[moduleName];
      closeDeleteTcConfirm();
      showPreview(activeSnapshotId);
      toast('Đã xóa testcase — nhớ bấm "Lưu thay đổi"', 'success');
    }

    async function saveTestCaseEdits() {
      if (!currentTCData) { toast('Chưa có dữ liệu test case', 'warning'); return; }
      syncEditsFromDOM();

      if (!currentConvId) {
        toast('Đã giữ thay đổi tạm thời; chưa có cuộc trò chuyện để lưu vào cơ sở dữ liệu', 'warning');
        return;
      }

      const btn = document.getElementById('btnSaveEdits');
      if (btn) btn.disabled = true;
      try {
        const res = await fetch(`/api/history/${currentConvId}/test-cases`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ test_cases: currentTCData, snapshot_id: activeSnapshotId }),
        });
        const data = await res.json();
        if (!res.ok || !data.success) throw new Error(data.error || 'Lưu thất bại');
        if (activeSnapshotId != null) tcSnapshots.set(Number(activeSnapshotId), currentTCData);

        // Backend đã tự động tạo 1 file Excel MỚI (filename + download_url
        // riêng theo timestamp) ngay sau khi lưu — hiển thị đúng thông báo
        // và nút tải trỏ về file MỚI này, không dùng lại link Excel cũ.
        toast(data.message || 'Đã lưu thay đổi và tạo file Excel mới', 'success');
        if (data.download_url) {
          appendDownloadMsg(data.filename, data.download_url);
        }
        loadHistory();
      } catch (err) {
        toast('Lưu thay đổi thất bại: ' + (err.message || 'lỗi không xác định'), 'error');
      } finally {
        if (btn) btn.disabled = false;
      }
    }

    function closePreview() {
      document.getElementById('previewPanel').style.display = 'none';
    }

    // ── Excel generation ──────────────────────────────────────────────────────────
    function generateExcel(snapshotId = activeSnapshotId) {
      if (snapshotId != null) {
        snapshotId = Number(snapshotId);
        const snapshotData = tcSnapshots.get(snapshotId);
        if (!snapshotData) {
          toast('Không tìm thấy dữ liệu của phiên bản testcase này', 'error');
          return;
        }
        activeSnapshotId = snapshotId;
        currentTCData = snapshotData;
      }
      if (!currentTCData) { toast('Chưa có dữ liệu test case', 'warning'); return; }
      syncEditsFromDOM(); // đảm bảo file Excel xuất ra phản ánh đúng các sửa đổi tay gần nhất trong preview
      document.getElementById('projName').value = cleanProjectName(currentTCData.project_name) || 'Tên Dự Án';
      document.getElementById('modalWrap').style.display = 'flex';
    }
    async function doGenerateExcel() {
      const projName = document.getElementById('projName').value.trim() || 'My Project';
      closeModal();
      toast('Đang tạo file Excel…', 'info');

      try {
        const res  = await fetch('/api/generate-excel', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            test_cases: currentTCData,
            project_name: projName,
            conversation_id: currentConvId,
            snapshot_id: activeSnapshotId,
          }),
        });
        const data = await res.json();

        if (data.error) {
          toast(data.error, 'error');
        } else {
          toast(`File Excel đã được tạo thành công! (${data.total_tc} test cases)`, 'success');
          appendDownloadMsg(data.filename, data.download_url);
          loadHistory();
        }
      } catch {
        toast('Lỗi khi tạo file Excel', 'error');
      }
    }
    function _persistPendingUpload() {
      try {
        if (!uploadedContent && !uploadedImages.length) {
          sessionStorage.removeItem(PENDING_UPLOAD_KEY);
          return;
        }
        sessionStorage.setItem(PENDING_UPLOAD_KEY, JSON.stringify({
          convId: currentConvId,
          uploadedContent,
          uploadedFilename,
          uploadedImages,
          uploadedImagePreviews,
        }));
      } catch {
      }
    }

    function _persistCurrentConv() {
      try {
        if (currentConvId) sessionStorage.setItem(CURRENT_CONV_KEY, String(currentConvId));
        else sessionStorage.removeItem(CURRENT_CONV_KEY);
      } catch { /* ignore */ }
    }

    function _clearPendingUploadStorage() {
      try { sessionStorage.removeItem(PENDING_UPLOAD_KEY); } catch { /* ignore */ }
    }
    function _restorePendingUpload() {
      try {
        const raw = sessionStorage.getItem(PENDING_UPLOAD_KEY);
        if (!raw) return;
        const s = JSON.parse(raw);
        if (s.convId !== currentConvId) { _clearPendingUploadStorage(); return; }

        uploadedContent  = s.uploadedContent || null;
        uploadedFilename = s.uploadedFilename || null;
        uploadedImages   = Array.isArray(s.uploadedImages) ? s.uploadedImages : [];
        uploadedImagePreviews = Array.isArray(s.uploadedImagePreviews) ? s.uploadedImagePreviews : [];

        if (!uploadedContent && !uploadedImages.length) return;

        const thumb = document.getElementById('uploadBannerThumb');
        const icon  = document.getElementById('uploadBannerIcon');

        if (uploadedImages.length) {
          const previewUrl = uploadedImagePreviews[uploadedImagePreviews.length - 1]?.dataUrl || null;
          if (previewUrl) {
            thumb.src = previewUrl; thumb.style.display = 'inline-block'; icon.style.display = 'none';
          } else {
            thumb.style.display = 'none'; icon.style.display = 'inline-block'; icon.className = 'fas fa-images';
          }
          const label = uploadedImages.length > 1 ? `🖼️ ${uploadedImages.length} ảnh đính kèm` : `🖼️ ${uploadedFilename}`;
          document.getElementById('uploadFilename').textContent = label;
        } else {
          thumb.style.display = 'none';
          icon.style.display = 'inline-block';
          icon.className = 'fas fa-file-alt';
          document.getElementById('uploadFilename').textContent = uploadedFilename;
        }
        document.getElementById('uploadBanner').style.display = 'flex';
        toast('Đã khôi phục tệp đính kèm đang chờ gửi', 'info');
      } catch {
        _clearPendingUploadStorage();
      }
    }
    async function handleUpload(e) {
      const file = e.target.files[0];
      if (!file) return;
      await uploadFile(file);
    }
    async function handlePasteImage(e) {
      const items = e.clipboardData?.items;
      if (!items || !items.length) return;

      for (const item of items) {
        if (item.type && item.type.startsWith('image/')) {
          const blob = item.getAsFile();
          if (!blob) continue;
          e.preventDefault(); // chặn dán "ảnh" dưới dạng ký tự linh tinh vào textarea
          const ext = (item.type.split('/')[1] || 'png').replace('jpeg', 'jpg');
          const file = new File([blob], `pasted-image-${Date.now()}.${ext}`, { type: item.type });
          await uploadFile(file);
          break;
        }
      }
    }
    async function uploadFile(file) {
      const allowed = ['.txt', '.docx', '.pdf', '.md', '.xlsx', '.xlsm', '.xls',
                       '.jpg', '.jpeg', '.png', '.gif', '.webp'];
      const ext = '.' + file.name.split('.').pop().toLowerCase();

      if (!allowed.includes(ext)) {
        toast('Chỉ hỗ trợ: .txt, .docx, .pdf, .md, .xlsx, .jpg, .jpeg, .png, .webp', 'error');
        document.getElementById('fileInput').value = '';
        document.getElementById('cameraInput').value = '';
        return;
      }
      if (file.size > 16 * 1024 * 1024) {
        toast('File quá lớn. Giới hạn 16 MB', 'error');
        document.getElementById('fileInput').value = '';
        document.getElementById('cameraInput').value = '';
        return;
      }

      const fd = new FormData();
      fd.append('file', file);
      toast('Đang đọc file…', 'info');

      try {
        const res  = await fetch('/api/upload', { method: 'POST', body: fd });
        const data = await res.json();

        if (data.error) {
          toast(data.error, 'error');
        } else if (data.is_image) {
          if (_filenameMismatchesProject(data.filename)) {
            openImageMismatchModal(data);
          } else {
            _continueImageUploadFlow(data);
          }
        } else {
          uploadedContent  = data.full_content;
          uploadedFilename = data.filename;
          document.getElementById('uploadBannerThumb').style.display = 'none';
          document.getElementById('uploadBannerIcon').style.display = 'inline-block';
          document.getElementById('uploadBannerIcon').className = 'fas fa-file-alt';
          document.getElementById('uploadFilename').textContent = data.filename;
          document.getElementById('uploadBanner').style.display = 'flex';
          toast(`Đã đọc "${data.filename}" (${data.char_count.toLocaleString()} ký tự)`, 'success');
          _persistPendingUpload();
        }
      } catch {
        toast('Lỗi khi đọc file', 'error');
      }
    }
    function applyImageUpload(data) {
      uploadedImages.push(data.image_block);
      // Lưu data URL riêng để render thumbnail thật trong bubble chat / banner
      const previewUrl = data.image_block?.image_url?.url || null;
      uploadedImagePreviews.push({ filename: data.filename, dataUrl: previewUrl });
      uploadedFilename = data.filename;
      const imgCount = uploadedImages.length;
      const label = imgCount > 1 ? `🖼️ ${imgCount} ảnh đính kèm` : `🖼️ ${data.filename}`;

      const thumb = document.getElementById('uploadBannerThumb');
      const icon  = document.getElementById('uploadBannerIcon');
      if (previewUrl) {
        // Hiện ảnh thật thay vì icon — ưu tiên thumbnail của ảnh mới nhất
        thumb.src = previewUrl;
        thumb.style.display = 'inline-block';
        icon.style.display = 'none';
      } else {
        thumb.style.display = 'none';
        icon.style.display = 'inline-block';
        icon.className = 'fas fa-images';
      }
      document.getElementById('uploadFilename').textContent = label;
      document.getElementById('uploadBanner').style.display = 'flex';
      toast(`Đã đính kèm ảnh "${data.filename}" (tổng ${imgCount} ảnh)`, 'success');
      _persistPendingUpload();
    }
    const _STOPWORDS_VI = new Set([
      'và', 'các', 'của', 'cho', 'theo', 'trang', 'giao', 'diện', 'ảnh', 'ứng',
      'dụng', 'dự', 'án', 'website', 'web', 'hệ', 'thống', 'quản', 'lý', 'chức',
      'năng', 'module', 'người', 'dùng', 'role', 'admin', 'employee', 'user',
      'đăng', 'nhập', 'xuất', 'ký', 'thêm', 'mới', 'sửa', 'cập', 'nhật', 'xóa',
      'xoá', 'tìm', 'kiếm', 'danh', 'sách', 'phân', 'trang', 'màn', 'hình',
      'với', 'là', 'có', 'không', 'được', 'này', 'đó', 'một', 'khi', 'để',
    ]);

    function _extractSignificantWords(text) {
      if (!text) return new Set();
      const words = text.toLowerCase().split(/[^\p{L}\p{N}]+/u).filter(w => w.length >= 3);
      return new Set(words.filter(w => !_STOPWORDS_VI.has(w)));
    }
    const _CONTINUATION_SIGNAL_PATTERNS = [
      /^\s*th[êe]m\s+ch[uứ]c\s+n[aă]ng/i,
      /^\s*b[ổo]\s*sung/i,
      /^\s*th[êe]m\s+m[àa]n\s+h[ìi]nh/i,
      /^\s*th[êe]m\s+module/i,
      /^\s*ti[ếe]p\s+t[ụu]c/i,
    ];

    function _looksLikeContinuationIntent(newText) {
      const t = (newText || '').trim();
      if (!t) return false;
      return _CONTINUATION_SIGNAL_PATTERNS.some((re) => re.test(t));
    }
    function _looksLikeDifferentProject(newText) {
      if (!currentTCData) return false;
      if (_looksLikeContinuationIntent(newText)) return false;
      const oldText = `${currentTCData.project_name || ''} ${currentTCData.description || ''}`;
      const oldWords = _extractSignificantWords(oldText);
      const newWords = _extractSignificantWords(newText);
      if (oldWords.size < 1 || newWords.size < 1) return false;
      let overlap = 0;
      for (const w of newWords) if (oldWords.has(w)) overlap++;
      const union = new Set([...oldWords, ...newWords]).size;
      const jaccard = union ? overlap / union : 0;
      return jaccard < 0.12;
    }
    function _stripVietnameseDiacritics(str) {
      return String(str)
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .replace(/đ/g, 'd')
        .replace(/Đ/g, 'D');
    }

    const _STOPWORDS_VI_ASCII = new Set([..._STOPWORDS_VI].map(_stripVietnameseDiacritics));

    function _normalizedWords(text) {
      if (!text) return new Set();
      const ascii = _stripVietnameseDiacritics(text.toLowerCase());
      const words = ascii.split(/[^a-z0-9]+/).filter(w => w.length >= 3);
      return new Set(words.filter(w => !_STOPWORDS_VI_ASCII.has(w)));
    }

    function _filenameSignificantWords(filename) {
      const base = String(filename || '').replace(/\.[a-z0-9]+$/i, '').replace(/[_\-]+/g, ' ');
      return _normalizedWords(base);
    }
    function _filenameMismatchesProject(filename) {
      const projectName = currentTCData?.project_name;
      if (!projectName) return false; // chưa có project nào đang mở -> không cảnh báo
      const projWords = _normalizedWords(projectName);
      const fileWords = _filenameSignificantWords(filename);
      if (projWords.size < 1 || fileWords.size < 1) return false;
      for (const w of fileWords) {
        if (projWords.has(w)) return false; // có ít nhất 1 từ trùng -> coi là khớp
      }
      return true;
    }

    let pendingMismatchImage = null; // data trả về từ /api/upload đang chờ user xác nhận

    function openImageMismatchModal(data) {
      pendingMismatchImage = data;
      const projectName = cleanProjectName(currentTCData?.project_name) || 'Dự án hiện tại';
      document.getElementById('imgMismatchProject').textContent  = projectName;
      document.getElementById('imgMismatchFilename').textContent = data.filename;
      document.getElementById('imgMismatchModal').style.display = 'flex';
    }
    function imgMismatchUseAnyway() {
      const data = pendingMismatchImage;
      pendingMismatchImage = null;
      document.getElementById('imgMismatchModal').style.display = 'none';
      if (!data) return;
      _continueImageUploadFlow(data);
    }
    function imgMismatchChooseAnother() {
      pendingMismatchImage = null;
      document.getElementById('imgMismatchModal').style.display = 'none';
      document.getElementById('fileInput').value = '';
      document.getElementById('cameraInput').value = '';
    }
    function _continueImageUploadFlow(data) {
      if (shouldAskResetContinue()) {
        pendingContextAction = { kind: 'image', data };
        askContextChoiceInChat();
      } else {
        applyImageUpload(data);
      }
    }
    function shouldAskResetContinue() {
      return !!(currentConvId && currentTCData && currentTCData.modules &&
                Object.keys(currentTCData.modules).length > 0);
    }

    function askContextChoiceInChat() {
      if (waitingContextChoice) return;
      waitingContextChoice = true;

      const ca = document.getElementById('chatArea');
      const d = document.createElement('div');
      d.className = 'msg assistant';
      d.innerHTML = `
        <div class="msg-avatar"><i class="fas fa-robot"></i></div>
        <div class="msg-content">
          <div class="bubble">
            <strong>Chọn phạm vi phân tích cho màn hình mới</strong><br><br>
            <strong>1. Phân tích độc lập</strong><br>
            Tạo bộ testcase mới, không sử dụng dữ liệu trước đó.<br><br>
            <strong>2. Chỉ phân tích màn hình này</strong><br>
            Tham khảo ngữ cảnh trước để hiểu nghiệp vụ, nhưng chỉ sinh testcase cho màn hình vừa gửi; không gộp testcase.<br><br>
            <strong>3. Tiếp tục workflow</strong><br>
            Nối màn hình mới vào luồng hiện tại và giữ toàn bộ testcase của workflow.<br><br>
            Nhập <strong>1</strong>, <strong>2</strong> hoặc <strong>3</strong>.
          </div>
          <div class="msg-time">${now()}</div>
        </div>`;
      ca.appendChild(d);
      scrollBottom();

      const input = document.getElementById('msgInput');
      input.placeholder = 'Nhập 1, 2 hoặc 3…';
      input.focus();
    }

    async function handleContextChoice(choice) {
      if (!waitingContextChoice || !pendingContextAction) return;
      const action = pendingContextAction;
      pendingContextAction = null;
      waitingContextChoice = false;
      const input = document.getElementById('msgInput');
      input.placeholder = 'Nhập mô tả website, chức năng, role người dùng hoặc tải ảnh giao diện…';
      if (choice === '1') {
        contextMode = 'new';
        _doReset();
        if (action.kind === 'send') {
          uploadedContent = action.uploadedContent || null;
          uploadedFilename = action.uploadedFilename || null;
          uploadedImages = Array.isArray(action.uploadedImages) ? [...action.uploadedImages] : [];
          uploadedImagePreviews = Array.isArray(action.uploadedImagePreviews)
            ? [...action.uploadedImagePreviews] : [];
        }
        appendContextChoiceMessage('1', 'Bắt đầu mới');
      } else if (choice === '2') {
        contextMode = 'screen_only';
        appendContextChoiceMessage('2', 'Chỉ phân tích màn hình này');
      } else {
        contextMode = 'workflow';
        appendContextChoiceMessage('3', 'Tiếp tục workflow');
      }
      if (action.kind === 'image') {
        applyImageUpload(action.data);
        skipContextPromptOnce = true;
        toast('Đã chọn chế độ. Bạn có thể nhập mô tả rồi bấm Gửi.', 'success');
      } else {
        input.value = action.message || '';
        onInputChange(input);
        skipContextPromptOnce = true;
        await doSendMsg();
      }
    }

    function appendContextChoiceMessage(number, label) {
      appendUserMsg(number, true, []);
      const ca = document.getElementById('chatArea');
      const d = document.createElement('div');
      d.className = 'msg assistant';
      d.innerHTML = `
        <div class="msg-avatar"><i class="fas fa-robot"></i></div>
        <div class="msg-content">
          <div class="bubble">✅ Đã chọn: <strong>${esc(label)}</strong>.</div>
          <div class="msg-time">${now()}</div>
        </div>`;
      ca.appendChild(d);
      scrollBottom();
    }
    function openContextModal(kind, data) {
      pendingContextAction = { kind, data, message: document.getElementById('msgInput')?.value.trim() || '' };
      askContextChoiceInChat();
    }
    function closeUploadContextModal() {
      waitingContextChoice = false;
      pendingContextAction = null;
      const el = document.getElementById('uploadContextModal');
      if (el) el.style.display = 'none';
    }
    function confirmReset() { handleContextChoice('1'); }
    function confirmContinueAction() { handleContextChoice('3'); }
    function _doReset() {
      currentConvId    = null;
      currentTCData    = null;
      uploadedContent  = null;
      uploadedFilename = null;
      uploadedImages   = [];
      uploadedImagePreviews = [];
      _clearPendingUploadStorage();
      try { sessionStorage.removeItem(CURRENT_CONV_KEY); } catch { /* ignore */ }
      document.getElementById('previewPanel').style.display = 'none';
      toast('Đã bắt đầu phiên mới — testcase cũ không được dùng làm ngữ cảnh', 'info');
    }

    function _finishContextAction(kind, data, wasReset) {
      if (kind === 'image') {
        applyImageUpload(data);
        skipContextPromptOnce = true;
      } else {
        doSendMsg();
      }
    }
    function openDiffProjectModal(kind) {
      const titleEl = document.getElementById('diffProjectTitle');
      if (titleEl) {
        titleEl.textContent = kind === 'image'
          ? 'Bạn đang gửi ảnh của website khác.'
          : 'Nội dung bạn gửi có vẻ thuộc website khác.';
      }
      document.getElementById('diffProjectModal').style.display = 'flex';
    }

    function closeDiffProjectModal() {
      document.getElementById('diffProjectModal').style.display = 'none';
      if (pendingContextAction?.kind === 'image') {
        document.getElementById('fileInput').value = '';
        document.getElementById('cameraInput').value = '';
      }
      pendingContextAction = null;
    }
    function diffProjectChooseNew() {
      if (!pendingContextAction) return;
      const { kind, data } = pendingContextAction;
      pendingContextAction = null;
      document.getElementById('diffProjectModal').style.display = 'none';
      _doReset();
      _finishContextAction(kind, data, true);
    }
    function diffProjectChooseMerge() {
      if (!pendingContextAction) return;
      const { kind, data } = pendingContextAction;
      pendingContextAction = null;
      document.getElementById('diffProjectModal').style.display = 'none';
      _finishContextAction(kind, data, false);
    }

    function clearUpload() {
      uploadedContent  = null;
      uploadedFilename = null;
      uploadedImages   = [];
      uploadedImagePreviews = [];
      skipContextPromptOnce = false;
      document.getElementById('uploadBanner').style.display = 'none';
      document.getElementById('uploadBannerThumb').style.display = 'none';
      document.getElementById('uploadBannerThumb').src = '';
      document.getElementById('uploadBannerIcon').style.display = 'inline-block';
      document.getElementById('fileInput').value = '';
      document.getElementById('cameraInput').value = '';
      _clearPendingUploadStorage();
    }
    function dlFile(filename) {
      window.open(`/download/${encodeURIComponent(filename)}`, '_blank');
    }
    async function delFile(filename, btn) {
      if (!confirm(`Xóa file "${filename}"?`)) return;
      btn.disabled = true;
      try {
        const res  = await fetch(`/api/files/${encodeURIComponent(filename)}`, { method: 'DELETE' });
        const data = await res.json();
        if (data.error) { toast(data.error, 'error'); }
        else            { toast('Đã xóa file', 'success'); loadHistory(); }
      } catch {
        toast('Lỗi khi xóa file', 'error');
      } finally {
        btn.disabled = false;
      }
    }
    const STAGE_LABELS = {
      analyze_request:      'Phân tích yêu cầu',
      scan_image:           'Phân tích giao diện từ ảnh',
      rule_engine:           'Áp dụng Rule Engine và RAG',
      generate_ai:           'AI đang sinh Test Case',
      merge_batches:         'Gộp kết quả các batch',
      coverage_1:            'Coverage Checker (chức năng)',
      coverage_round_1:      'Coverage Checker vòng 1',
      repair_missing_cases:  'Đang bổ sung phần thiếu',
      coverage_round_2:      'Coverage Checker vòng 2',
      normalize:             'Chuẩn hóa Test Case',
      complete:              'Hoàn thành',
    };
    function showLoading() {
      const msgEl   = document.getElementById('loadingMsg');
      const overlay = document.getElementById('loadingOverlay');
      const container = document.getElementById('progressSteps');
      if (container) container.innerHTML = ''; // reset — step sẽ được tạo động theo event thật
      if (msgEl) msgEl.textContent = 'Vui lòng chờ trong giây lát';
      overlay.style.display = 'flex';
    }

    function _progressSetIcon(el, iconClass) {
      const i = el.querySelector('i');
      if (i) i.className = `fas ${iconClass}`;
    }
    function _progressEnsureStep(stage) {
      const container = document.getElementById('progressSteps');
      if (!container) return null;
      let el = container.querySelector(`[data-stage="${stage}"]`);
      if (!el) {
        el = document.createElement('div');
        el.className = 'step pending';
        el.dataset.stage = stage;
        el.innerHTML =
          '<i class="fas fa-circle"></i>' +
          `<span class="step-label">${STAGE_LABELS[stage] || stage}</span>` +
          '<span class="step-msg"></span>';
        container.appendChild(el);
      }
      return el;
    }
    function _progressMarkActive(el, message) {
      document.querySelectorAll('#progressSteps .step.active').forEach(other => {
        if (other !== el) _progressMarkDone(other);
      });
      el.classList.remove('pending', 'done', 'error');
      el.classList.add('active');
      _progressSetIcon(el, 'fa-spinner fa-spin');
      const msgSpan = el.querySelector('.step-msg');
      if (msgSpan && message) msgSpan.textContent = message;
    }

    function _progressMarkDone(el, message) {
      el.classList.remove('active', 'pending', 'error');
      el.classList.add('done');
      _progressSetIcon(el, 'fa-circle-check');
      const msgSpan = el.querySelector('.step-msg');
      if (msgSpan && message) msgSpan.textContent = message;
    }

    function _progressMarkError(el, message) {
      el.classList.remove('active', 'pending', 'done');
      el.classList.add('error');
      _progressSetIcon(el, 'fa-circle-xmark');
      const msgSpan = el.querySelector('.step-msg');
      if (msgSpan) msgSpan.textContent = message || 'Đã xảy ra lỗi';
    }
    function handleProgressEvent(evt) {
      if (!evt || !evt.stage) return;
      const el = _progressEnsureStep(evt.stage);
      if (!el) return;
      const msgEl = document.getElementById('loadingMsg');
      if (msgEl && evt.message) msgEl.textContent = evt.message;
      if (evt.status === 'done') {
        _progressMarkDone(el, evt.message);
      } else {
        _progressMarkActive(el, evt.message);
      }
    }
    function handleProgressErrorEvent(message) {
      const activeEl = document.querySelector('#progressSteps .step.active');
      if (activeEl) _progressMarkError(activeEl, message);
    }

    function hideLoading() {
      document.getElementById('loadingOverlay').style.display = 'none';
      clearInterval(loadingMsgTimer);
      clearInterval(loadingStepTimer);
      loadingMsgTimer  = null;
      loadingStepTimer = null;
    }

    // ── Modal ─────────────────────────────────────────────────────────────────────
    function closeModal() {
      document.getElementById('modalWrap').style.display = 'none';
    }

    // ── Toast ─────────────────────────────────────────────────────────────────────
    function toast(msg, type = 'info') {
      const icons = { success:'fa-circle-check', error:'fa-circle-xmark',
                      warning:'fa-triangle-exclamation', info:'fa-circle-info' };
      const box = document.getElementById('toastBox');
      const t   = document.createElement('div');
      t.className = `toast ${type}`;
      t.innerHTML = `<i class="fas ${icons[type] || icons.info}"></i><span>${esc(msg)}</span>`;
      box.appendChild(t);
      setTimeout(() => {
        t.style.transition = 'all .3s ease';
        t.style.opacity    = '0';
        t.style.transform  = 'translateX(110%)';
        setTimeout(() => t.remove(), 300);
      }, 3200);
    }

    // ── Sidebar toggle ────────────────────────────────────────────────────────────
    function toggleSidebar() {
      const sb = document.getElementById('sidebar');
      if (window.innerWidth <= 768) {
        sb.classList.toggle('mobile-open');
      } else {
        sb.classList.toggle('collapsed');
      }
    }

    // Close mobile sidebar when clicking outside
    document.addEventListener('click', e => {
      const sb = document.getElementById('sidebar');
      if (window.innerWidth <= 768 &&
          sb.classList.contains('mobile-open') &&
          !sb.contains(e.target) &&
          !e.target.closest('.btn-menu')) {
        sb.classList.remove('mobile-open');
      }
    });

    // ── Input helpers ─────────────────────────────────────────────────────────────
    function useExample(el) {
      const inp = document.getElementById('msgInput');
      inp.value = el.querySelector('span').textContent;
      inp.focus();
      onInputChange(inp);
    }

    function handleKey(e) {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMsg();
      }
    }

    function onInputChange(el) {
      // Auto-resize textarea
      el.style.height = 'auto';
      el.style.height = Math.min(el.scrollHeight, 200) + 'px';
      updateCharCount();
    }

    function updateCharCount() {
      const v = document.getElementById('msgInput').value.length;
      document.getElementById('charCount').textContent = `${v.toLocaleString()} ký tự`;
    }

    document.addEventListener('DOMContentLoaded', () => {
      const inp = document.getElementById('msgInput');
      if (inp) inp.addEventListener('input', updateCharCount);
      if (inp) inp.addEventListener('paste', handlePasteImage);
    });
    let __resizeInputTimer = null;
    window.addEventListener('resize', () => {
      clearTimeout(__resizeInputTimer);
      __resizeInputTimer = setTimeout(() => {
        const inp = document.getElementById('msgInput');
        if (inp) onInputChange(inp);
      }, 100);
    });

    // ── Keyboard shortcuts ────────────────────────────────────────────────────────
    document.addEventListener('keydown', e => {
      if (e.key === 'Escape') { closeModal(); }
    });

    // ── Utilities ─────────────────────────────────────────────────────────────────
    function scrollBottom() {
      const ca = document.getElementById('chatArea');
      if (ca) setTimeout(() => { ca.scrollTop = ca.scrollHeight; }, 80);
    }

    function esc(str) {
      if (str == null) return '';
      const d = document.createElement('div');
      d.appendChild(document.createTextNode(String(str)));
      return d.innerHTML;
    }
   
    // Escape an toàn để nhúng vào giá trị attribute HTML (esc() không escape
    // dấu nháy nên không đủ an toàn khi dùng trong data-mod="...").
    function escAttr(str) {
      return esc(str).replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }

    function truncate(str, n) {
      return str.length > n ? str.slice(0, n) + '…' : str;
    }

    function shortenFilename(name) {
      return name.length > 28 ? name.slice(0, 25) + '…' : name;
    }

    function fmtDate(str) {
      if (!str) return '';
      try {
        return new Date(str).toLocaleDateString('vi-VN', { day:'2-digit', month:'2-digit', year:'2-digit' });
      } catch { return ''; }
    }

    function now() {
      return new Date().toLocaleTimeString('vi-VN', { hour:'2-digit', minute:'2-digit' });
    }

    function sleep(ms) {
      return new Promise(r => setTimeout(r, ms));
    }