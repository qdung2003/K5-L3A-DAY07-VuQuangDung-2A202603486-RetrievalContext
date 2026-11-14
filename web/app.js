const $ = id => document.getElementById(id);
let questions = [], busy = false, activeTab = 'sources';
const esc = value => String(value ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
function setMode() {
  const live = $('mode').value === 'live';
  $('modeBadge').textContent = live ? 'Live model · dùng API' : 'Trace đã lưu';
  $('modeBadge').classList.toggle('live', live);
  $('modeNote').textContent = live ? 'Gửi câu hỏi và đoạn tài liệu đến model đã cấu hình; có thể phát sinh phí API.' : 'Xem lại lượt chạy đã nộp, không gọi API mới.';
}
function renderExamples() {
  const filter = $('filterQuestions').value.toLowerCase();
  const items = questions.filter(q => `${q.id} ${q.question}`.toLowerCase().includes(filter));
  $('examples').innerHTML = items.length ? items.map(q => `<button type="button" class="example${q.question === $('question').value ? ' active' : ''}" data-id="${esc(q.id)}"><div class="example-meta"><span>${esc(q.id)}</span><span>${esc(q.split)}</span><span class="type ${q.status === 'abstain' ? 'abstain' : ''}">${q.status === 'abstain' ? 'Thiếu bằng chứng' : 'Có bằng chứng'}</span></div>${esc(q.question)}</button>`).join('') : '<p class="subtle">Không có câu hỏi phù hợp.</p>';
  $('examples').querySelectorAll('button').forEach(button => button.addEventListener('click', () => {
    if (busy) return;
    $('question').value = questions.find(q => q.id === button.dataset.id).question;
    renderExamples(); ask();
    if (innerWidth < 720) $('question').scrollIntoView({block:'center'});
  }));
}
function tab(name) {
  activeTab = name;
  ['sources', 'trace'].forEach(item => {
    $(`${item}Tab`).setAttribute('aria-selected', String(item === name));
    $(`${item}Panel`).hidden = item !== name;
  });
}
function sourceHref(value) { try { const url = new URL(value); return url.protocol === 'https:' || url.protocol === 'http:' ? esc(url.href) : '#'; } catch { return '#'; } }
function render(data) {
  $('answerSection').hidden = false; $('empty').hidden = true;
  $('answerTitle').textContent = data.status === 'abstain' ? 'Không đủ bằng chứng' : 'Câu trả lời có nguồn';
  $('answerTitle').classList.toggle('abstain', data.status === 'abstain');
  $('runLabel').textContent = data.mode === 'live' ? 'Lượt gọi model mới' : `Trace đã lưu · ${data.query_id || ''}`;
  const sources = data.sources || [];
  const byId = new Map(sources.map(s => [s.id, s]));
  $('answer').innerHTML = esc(data.answer).replace(/\[([a-f0-9]{64})\]/g, (match, id) => byId.has(id) ? `<button class="citation" type="button" data-source="${id}" title="${esc(byId.get(id).page)}">[Nguồn ${byId.get(id).rank}]</button>` : match);
  $('answer').querySelectorAll('.citation').forEach(button => button.addEventListener('click', () => {
    tab('sources');
    const source = document.getElementById(`source-${button.dataset.source}`);
    source.scrollIntoView({block:'center', behavior:matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth'});
    source.classList.add('highlight'); setTimeout(() => source.classList.remove('highlight'), 1800);
  }));
  const searches = data.searches || [];
  const tokenCount = Number(data.usage?.input_tokens || 0) + Number(data.usage?.output_tokens || 0);
  $('runStats').innerHTML = `<span>Model <b>${esc(data.config.model)}</b></span><span><b>${(Number(data.elapsed_ms || 0) / 1000).toFixed(2)} s</b>${data.mode === 'saved' ? ' · lần chạy gốc' : ''}</span><span><b>${tokenCount.toLocaleString('vi-VN')}</b> token</span><span><b>${searches.length}</b> lượt search</span>`;
  $('sourceCount').textContent = sources.length; $('searchCount').textContent = searches.length;
  $('sources').innerHTML = sources.map(s => `<article class="source ${(data.citations || []).includes(s.id) ? 'cited' : ''}" id="source-${esc(s.id)}"><div class="source-top"><span class="source-number">${s.rank}</span><a href="${sourceHref(s.source)}" target="_blank" rel="noopener noreferrer">${esc(s.page)}</a>${(data.citations || []).includes(s.id) ? '<span class="cited-label">Đã trích dẫn</span>' : ''}<span class="source-score">RRF ${Number(s.score || 0).toFixed(4)}</span></div><div class="source-url">${esc(s.source)}</div><p class="source-text">${esc(s.text)}</p><details><summary>Chunk ID</summary><code>${esc(s.id)}</code></details></article>`).join('') || '<p class="subtle">Không có nguồn trong context cuối.</p>';
  $('traceRows').innerHTML = searches.map((s, i) => `<div class="trace-row"><strong>LƯỢT TÌM ${i + 1}</strong><p class="trace-query">${esc(s.query)}</p><span class="trace-meta">${s.result_count} kết quả · ${s.context_ids.length} đoạn trong context</span><details><summary>Context gửi model</summary><pre class="context-text">${esc(s.context)}</pre></details></div>`).join('') || '<p class="subtle">Không có lượt search.</p>';
  tab(activeTab);
}
async function ask() {
  const question = $('question').value.trim(); if (!question || busy) return;
  const mode = $('mode').value;
  busy = true; $('ask').disabled = true; $('mode').disabled = true; $('question').readOnly = true;
  $('feedback').hidden = true; $('loading').hidden = false; $('answerSection').hidden = true; $('empty').hidden = true;
  $('askLabel').textContent = 'Đang xử lý'; $('loadingNote').textContent = mode === 'live' ? 'Model đang gọi công cụ tìm kiếm. Lần đầu có thể cần tải encoder vào bộ nhớ.' : 'Đang đọc trace đã lưu.';
  try {
    const response = await fetch('/api/ask', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({question, mode})});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Không tải được kết quả.');
    render(data);
  } catch(error) { $('feedback').textContent = error.message; $('feedback').hidden = false; }
  finally { busy = false; $('ask').disabled = false; $('mode').disabled = false; $('question').readOnly = false; $('loading').hidden = true; $('askLabel').textContent = 'Gửi câu hỏi'; }
}
$('askForm').addEventListener('submit', e => { e.preventDefault(); ask(); });
$('mode').addEventListener('change', setMode);
$('filterQuestions').addEventListener('input', renderExamples);
$('mobileQuestion').addEventListener('change', () => {
  const question = questions.find(q => q.id === $('mobileQuestion').value);
  if (question && !busy) { $('question').value = question.question; renderExamples(); ask(); }
});
$('sourcesTab').addEventListener('click', () => tab('sources')); $('traceTab').addEventListener('click', () => tab('trace'));
$('question').addEventListener('keydown', e => { if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { e.preventDefault(); ask(); } });
(async function init() {
  try { const response = await fetch('/api/questions'); if (!response.ok) throw new Error('Không tải được câu hỏi.'); const data = await response.json(); questions = data.questions; $('questionCount').textContent = data.saved_trace_count; $('mobileQuestion').innerHTML += questions.map(q => `<option value="${esc(q.id)}">${esc(q.id)} · ${esc(q.question)}</option>`).join(''); renderExamples(); }
  catch(error) { $('feedback').textContent = error.message; $('feedback').hidden = false; }
  setMode();
})();
