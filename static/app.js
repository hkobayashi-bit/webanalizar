// Base path (auto-detect from current URL)
const BASE = window.location.pathname.replace(/\/$/, '');

// State
let currentJobId = null;
let selectedFile = null;
let allResults = [];
let techCounts = {};

// Tab switching
function switchTab(tab) {
  document.querySelectorAll('.input-tabs button').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
  if (tab === 'single') {
    document.querySelector('.input-tabs button:nth-child(1)').classList.add('active');
    document.getElementById('tab-single').classList.add('active');
  } else {
    document.querySelector('.input-tabs button:nth-child(2)').classList.add('active');
    document.getElementById('tab-csv').classList.add('active');
  }
}

// File handling
function onFileSelect(input) {
  if (input.files.length > 0) {
    selectedFile = input.files[0];
    document.getElementById('file-name').textContent = selectedFile.name;
    document.getElementById('btn-upload').disabled = false;
  }
}

// Drag & drop
const dropZone = document.getElementById('drop-zone');
dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('dragover'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.classList.remove('dragover');
  if (e.dataTransfer.files.length > 0) {
    selectedFile = e.dataTransfer.files[0];
    document.getElementById('file-name').textContent = selectedFile.name;
    document.getElementById('btn-upload').disabled = false;
    document.getElementById('csv-file').files = e.dataTransfer.files;
  }
});

// Enter key for URL input
document.getElementById('url-input').addEventListener('keydown', e => {
  if (e.key === 'Enter') scanSingle();
});

// Single URL scan
async function scanSingle() {
  const url = document.getElementById('url-input').value.trim();
  if (!url) return;

  const btn = document.getElementById('btn-scan');
  btn.disabled = true;
  btn.textContent = 'スキャン中...';

  document.getElementById('single-result').style.display = 'none';

  try {
    const form = new FormData();
    form.append('url', url);
    const resp = await fetch(`${BASE}/api/scan-single`, { method: 'POST', body: form });
    const data = await resp.json();

    if (!resp.ok) {
      alert(data.detail || 'エラーが発生しました');
      return;
    }

    showSingleResult(data);
  } catch (e) {
    alert('通信エラー: ' + e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = 'スキャン';
  }
}

function showSingleResult(data) {
  const el = document.getElementById('single-result');
  el.style.display = 'block';
  document.getElementById('single-url').textContent = data.url;

  const container = document.getElementById('single-techs');
  container.innerHTML = '';

  if (data.status !== 'success') {
    container.innerHTML = `<p class="status-error">エラー: ${data.error_message || data.status}</p>`;
    return;
  }

  if (data.technologies.length === 0) {
    container.innerHTML = '<p style="color:#888">技術が検出されませんでした</p>';
    return;
  }

  data.technologies.forEach(tech => {
    const div = document.createElement('div');
    div.className = 'tech-item';
    div.innerHTML = `
      <div class="tech-name">${esc(tech.name)}</div>
      <div class="tech-cats">${tech.categories.map(c => esc(c)).join(', ')}</div>
      ${tech.version ? `<div class="tech-ver">v${esc(tech.version)}</div>` : ''}
    `;
    container.appendChild(div);
  });
}

// CSV batch scan
async function scanCSV() {
  if (!selectedFile) return;

  const btn = document.getElementById('btn-upload');
  btn.disabled = true;
  btn.textContent = 'アップロード中...';

  // Reset
  allResults = [];
  techCounts = {};
  document.getElementById('results-body').innerHTML = '';

  try {
    const form = new FormData();
    form.append('file', selectedFile);
    const resp = await fetch(`${BASE}/api/scan`, { method: 'POST', body: form });
    const data = await resp.json();

    if (!resp.ok) {
      alert(data.detail || 'エラーが発生しました');
      btn.disabled = false;
      btn.textContent = 'アップロード & スキャン';
      return;
    }

    currentJobId = data.job_id;
    const total = data.total;

    // Show progress
    document.getElementById('progress-section').style.display = 'block';
    document.getElementById('results-section').style.display = 'block';
    document.getElementById('summary-section').style.display = 'grid';
    document.getElementById('single-result').style.display = 'none';

    btn.textContent = 'スキャン中...';

    // SSE
    const source = new EventSource(`${BASE}/api/jobs/${currentJobId}/stream`);
    source.onmessage = (event) => {
      const msg = JSON.parse(event.data);

      if (msg.done) {
        source.close();
        btn.disabled = false;
        btn.textContent = 'アップロード & スキャン';
        updateProgress(total, total);
        return;
      }

      allResults.push(msg.result);
      updateProgress(msg.completed, msg.total);
      addResultRow(msg.completed, msg.result);
      updateSummary();
    };

    source.onerror = () => {
      source.close();
      btn.disabled = false;
      btn.textContent = 'アップロード & スキャン';
    };

  } catch (e) {
    alert('通信エラー: ' + e.message);
    btn.disabled = false;
    btn.textContent = 'アップロード & スキャン';
  }
}

function updateProgress(completed, total) {
  const pct = total > 0 ? Math.round((completed / total) * 100) : 0;
  document.getElementById('progress-bar').style.width = pct + '%';
  document.getElementById('progress-count').textContent = `${completed} / ${total}`;
  document.getElementById('progress-percent').textContent = pct + '%';
}

function addResultRow(index, result) {
  const tbody = document.getElementById('results-body');
  const tr = document.createElement('tr');

  const statusClass = 'status-' + result.status;
  const techTags = result.technologies.map(t => {
    const catClass = getCatClass(t.categories);
    const ver = t.version ? ` v${esc(t.version)}` : '';
    return `<span class="tech-tag ${catClass}">${esc(t.name)}${ver}</span>`;
  }).join('');

  tr.innerHTML = `
    <td>${index}</td>
    <td class="url-cell"><a href="${esc(result.url)}" target="_blank">${esc(result.url)}</a></td>
    <td class="${statusClass}">${esc(result.status)}</td>
    <td>${techTags || (result.error_message ? `<span style="color:#c62828">${esc(result.error_message)}</span>` : '-')}</td>
  `;
  tbody.appendChild(tr);

  // Scroll to bottom
  const wrapper = tbody.closest('.table-wrapper');
  wrapper.scrollTop = wrapper.scrollHeight;
}

function updateSummary() {
  const total = allResults.length;
  const success = allResults.filter(r => r.status === 'success').length;
  const allTechs = new Set();
  techCounts = {};

  allResults.forEach(r => {
    r.technologies.forEach(t => {
      allTechs.add(t.name);
      techCounts[t.name] = (techCounts[t.name] || 0) + 1;
    });
  });

  document.getElementById('sum-total').textContent = total;
  document.getElementById('sum-success').textContent = success;
  document.getElementById('sum-techs').textContent = allTechs.size;

  // Most common tech
  let topTech = '-';
  let topCount = 0;
  for (const [name, count] of Object.entries(techCounts)) {
    if (count > topCount) { topTech = name; topCount = count; }
  }
  document.getElementById('sum-top-tech').textContent = topTech;
  document.getElementById('sum-top-tech').style.fontSize = topTech.length > 10 ? '18px' : '32px';
}

function getCatClass(categories) {
  for (const c of categories) {
    const lower = c.toLowerCase();
    if (lower.includes('cms')) return 'cat-cms';
    if (lower.includes('analytics')) return 'cat-analytics';
    if (lower.includes('crm')) return 'cat-crm';
    if (lower.includes('advertising') || lower.includes('marketing')) return 'cat-advertising';
    if (lower.includes('framework')) return 'cat-framework';
    if (lower.includes('web server') || lower.includes('server')) return 'cat-server';
    if (lower.includes('javascript')) return 'cat-js';
  }
  return 'cat-default';
}

function exportCSV() {
  if (!currentJobId) return;
  window.location.href = `${BASE}/api/jobs/${currentJobId}/export`;
}

function esc(str) {
  if (!str) return '';
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}
