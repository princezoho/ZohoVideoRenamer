"""Generate the HTML review UI from a matches dataset."""
from __future__ import annotations

import json
import os
import re
from typing import Optional

from .matcher import Match
from .thumbnailer import safe_id


def _rel_or_none(path: Optional[str], start: str) -> Optional[str]:
    if not path:
        return None
    try:
        return os.path.relpath(path, start)
    except ValueError:
        return None


def build_renames_for_entry(
    base_name: str,
    videos: list[dict],
    stills: list[dict],
) -> list[dict]:
    """Pure-python mirror of the JS namesForEntry — kept here so the apply pipeline
    can also produce the same plan if the user wants to skip the browser step.
    """
    out: list[dict] = []
    base_name = (base_name or "").strip()
    if not base_name:
        return out
    multi = len(videos) > 1
    for i, v in enumerate(videos):
        suffix = f"-v{i+1}" if multi else ""
        out.append({"type": "video", "from": v["rel_path"], "to": _replace_basename(v["rel_path"], base_name + suffix)})
    # Multiple stills for one stub: first one keeps clean name, rest get -copy-N suffix
    copy_idx = 0
    used_in_folder: set[str] = set()
    for s in stills:
        folder = os.path.dirname(s["rel_path"])
        new_name = base_name
        if s.get("is_copy"):
            new_name = base_name + "-copy"
        ext = os.path.splitext(s["filename"])[1].lower() or ".png"
        candidate = new_name + ext
        full = os.path.join(folder, candidate)
        if full in used_in_folder:
            # Disambiguate
            copy_idx += 1
            candidate = f"{new_name}-{copy_idx+1}{ext}"
            full = os.path.join(folder, candidate)
        used_in_folder.add(full)
        out.append({"type": "still", "from": s["rel_path"], "to": full})
    return out


def _replace_basename(rel_path: str, new_stem: str) -> str:
    folder = os.path.dirname(rel_path)
    _, ext = os.path.splitext(rel_path)
    return os.path.join(folder, new_stem + ext)


def matches_to_ui_dataset(
    matches: list[Match],
    *,
    stills_root: str,
    videos_root: str,
    project_root: str,
    canonical_picker,  # callable(stills) -> Still | None
    suggested_names: Optional[dict[str, str]] = None,
) -> dict:
    """Convert Match objects into the JSON shape the HTML UI expects.

    All paths in the dataset are relative to `project_root` (so the HTML can
    load them via file:// from the project folder).
    """
    suggested_names = suggested_names or {}
    entries = []
    for m in matches:
        canon = canonical_picker(m.stills)
        sid = safe_id(m.stub)
        # Slim still records
        still_files = []
        for s in m.stills:
            still_files.append({
                "abs_path": s.abs_path,
                "rel_path": os.path.relpath(s.abs_path, project_root),
                "filename": s.filename,
                "is_copy": s.is_copy,
                "size": s.size,
            })
        # Video records with thumb path (will be filled in once thumbs exist)
        videos = []
        for v in m.videos:
            vid_safe = safe_id(os.path.splitext(v.filename)[0])
            videos.append({
                "abs_path": v.abs_path,
                "rel_path": os.path.relpath(v.abs_path, project_root),
                "filename": v.filename,
                "thumb": os.path.join("thumbs", "videos", vid_safe + ".jpg"),
            })
        entry = {
            "id": sid,
            "stub": m.stub,
            "suggested_name": suggested_names.get(sid, m.stub),
            "still_thumb": os.path.join("thumbs", "stills", sid + ".jpg") if canon else None,
            "canonical_still_rel": os.path.relpath(canon.abs_path, project_root) if canon else None,
            "all_still_files": still_files,
            "videos": videos,
        }
        entries.append(entry)
    return {"entries": entries}


def write_review_html(dataset: dict, out_path: str) -> None:
    """Write the self-contained review HTML with dataset inlined."""
    slim_json = json.dumps(dataset, separators=(",", ":"))
    html = _HTML_TEMPLATE.replace("__DATA__", slim_json)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)


# ---------------------------------------------------------------------------
# HTML template
# ---------------------------------------------------------------------------

_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>ZohoVideoRenamer — Review</title>
<style>
  :root {
    --bg: #1a1a1d; --panel: #25252a; --panel2: #2e2e35; --border: #3a3a44;
    --text: #e8e8ec; --muted: #9a9aa6; --accent: #d8a14a; --accent2: #e6b35a;
    --good: #6ec077; --bad: #d97a6c; --warn: #d4b04a; --skip: #6a8bcc;
  }
  * { box-sizing: border-box; }
  html, body { height: 100%; margin: 0; }
  body { background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; font-size: 14px; overflow: hidden; }
  #app { display: grid; grid-template-columns: 280px 1fr; height: 100vh; }
  .sidebar { background: var(--panel); border-right: 1px solid var(--border); overflow-y: auto; display: flex; flex-direction: column; }
  .sidebar-header { padding: 16px; border-bottom: 1px solid var(--border); background: var(--panel2); }
  .sidebar-header h1 { margin: 0 0 8px; font-size: 15px; font-weight: 600; color: var(--accent); }
  .progress { font-size: 12px; color: var(--muted); }
  .progress-bar { background: var(--border); height: 4px; border-radius: 2px; margin-top: 6px; overflow: hidden; }
  .progress-fill { background: var(--accent); height: 100%; transition: width 0.3s; }
  .filter { padding: 12px 16px; border-bottom: 1px solid var(--border); }
  .filter input { width: 100%; padding: 6px 8px; background: var(--bg); color: var(--text); border: 1px solid var(--border); border-radius: 4px; font-size: 12px; }
  .filter-buttons { display: flex; gap: 4px; margin-top: 8px; }
  .filter-btn { flex: 1; padding: 4px 6px; font-size: 11px; background: var(--bg); color: var(--muted); border: 1px solid var(--border); border-radius: 3px; cursor: pointer; }
  .filter-btn.active { background: var(--accent); color: #1a1a1d; border-color: var(--accent); }
  .entry-list { flex: 1; overflow-y: auto; }
  .entry-item { padding: 8px 12px; cursor: pointer; border-bottom: 1px solid var(--border); display: flex; align-items: center; gap: 8px; font-size: 12px; }
  .entry-item:hover { background: var(--panel2); }
  .entry-item.active { background: var(--accent); color: #1a1a1d; }
  .entry-item .status { width: 14px; text-align: center; }
  .entry-item .stub { flex: 1; font-family: monospace; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .entry-item .vcount { color: var(--muted); font-size: 11px; }
  .entry-item.active .vcount { color: #1a1a1d; }
  .main { overflow-y: auto; padding: 24px; }
  .breadcrumb { color: var(--muted); font-size: 12px; margin-bottom: 4px; font-family: monospace; }
  .entry-title { font-size: 18px; font-weight: 600; margin: 0 0 16px; }
  .preview-row { display: grid; grid-template-columns: minmax(280px, 1fr) 2fr; gap: 24px; margin-bottom: 24px; }
  .still-box, .video-box { background: var(--panel); border-radius: 8px; padding: 16px; }
  .still-box h3, .video-box h3 { margin: 0 0 12px; font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em; color: var(--muted); }
  .still-preview { width: 100%; border-radius: 4px; display: block; cursor: zoom-in; }
  .still-file-list { margin-top: 10px; font-size: 11px; list-style: none; padding: 0; color: var(--muted); }
  .still-file-list li { padding: 3px 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .still-file-list li .tag { display: inline-block; padding: 1px 5px; border-radius: 3px; font-size: 10px; font-weight: 600; background: var(--border); color: var(--text); margin-right: 5px; }
  .video-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 12px; }
  .video-card { background: var(--panel2); border-radius: 6px; padding: 8px; cursor: pointer; position: relative; border: 2px solid transparent; transition: opacity .15s, border-color .15s; user-select: none; }
  .video-card:hover { border-color: var(--accent); }
  .video-card.excluded { opacity: 0.32; border-color: var(--bad); background: rgba(217,122,108,0.08); }
  .video-card.excluded:hover { opacity: 0.55; }
  .video-card .include-toggle { position: absolute; top: 8px; left: 8px; background: var(--good); color: #0f1a10; padding: 2px 7px; border-radius: 3px; font-size: 11px; font-weight: 700; pointer-events: none; }
  .video-card.excluded .include-toggle { background: var(--bad); color: white; }
  .video-card video, .video-card img { width: 100%; border-radius: 4px; display: block; }
  .video-card .vname { font-size: 10px; color: var(--muted); word-break: break-all; margin-top: 6px; line-height: 1.3; max-height: 50px; overflow: hidden; }
  .video-card.excluded .vname { text-decoration: line-through; }
  .video-card .vbadge { position: absolute; top: 8px; right: 8px; background: rgba(0,0,0,0.7); color: white; padding: 2px 8px; border-radius: 3px; font-size: 11px; font-weight: 600; }
  .video-card .play-btn { position: absolute; bottom: 28px; right: 12px; background: rgba(0,0,0,0.7); color: white; padding: 3px 6px; border-radius: 3px; font-size: 10px; border: none; cursor: pointer; z-index: 2; }
  .form-row { background: var(--panel); border-radius: 8px; padding: 20px; margin-bottom: 24px; }
  .form-row label { display: block; font-size: 12px; color: var(--muted); margin-bottom: 6px; text-transform: uppercase; letter-spacing: 0.05em; }
  .name-input { width: 100%; padding: 10px 14px; background: var(--bg); color: var(--text); border: 1px solid var(--border); border-radius: 6px; font-size: 16px; font-family: monospace; font-weight: 600; }
  .name-input:focus { outline: none; border-color: var(--accent); }
  .name-hint { font-size: 11px; color: var(--muted); margin-top: 6px; }
  .preview-renames { margin-top: 14px; padding: 12px; background: var(--bg); border-radius: 4px; font-size: 11px; font-family: monospace; color: var(--muted); max-height: 160px; overflow-y: auto; }
  .preview-renames .arrow { color: var(--accent); }
  .preview-renames .new { color: var(--good); }
  .actions { display: flex; gap: 10px; margin-top: 16px; }
  .btn { padding: 10px 18px; border: none; border-radius: 6px; font-size: 13px; font-weight: 600; cursor: pointer; font-family: inherit; }
  .btn-approve { background: var(--good); color: #0f1a10; }
  .btn-approve:hover { filter: brightness(1.1); }
  .btn-skip { background: var(--skip); color: white; }
  .btn-flag { background: var(--warn); color: #1a1a0f; }
  .btn-reset { background: var(--bad); color: white; }
  .btn-secondary { background: var(--panel2); color: var(--text); }
  .nav { display: flex; gap: 12px; justify-content: center; margin-top: 24px; }
  .keyboard-hints { text-align: center; margin-top: 12px; color: var(--muted); font-size: 11px; }
  .keyboard-hints kbd { display: inline-block; padding: 1px 6px; background: var(--panel); border: 1px solid var(--border); border-radius: 3px; font-family: monospace; margin: 0 2px; }
  .export-bar { padding: 16px; border-top: 1px solid var(--border); background: var(--panel2); }
  .export-bar button { width: 100%; padding: 8px; background: var(--accent); color: #1a1a1d; border: none; border-radius: 4px; font-weight: 600; cursor: pointer; font-size: 13px; }
  .toast { position: fixed; bottom: 24px; right: 24px; padding: 12px 20px; background: var(--panel2); border-radius: 6px; border: 1px solid var(--border); font-size: 13px; box-shadow: 0 4px 16px rgba(0,0,0,0.4); opacity: 0; transition: opacity 0.3s; pointer-events: none; }
  .toast.show { opacity: 1; }
  .modal { position: fixed; inset: 0; background: rgba(0,0,0,0.85); display: none; align-items: center; justify-content: center; z-index: 100; }
  .modal.show { display: flex; }
  .modal img, .modal video { max-width: 95vw; max-height: 95vh; border-radius: 4px; }
  .badge { font-size: 10px; padding: 2px 6px; border-radius: 3px; background: var(--panel2); color: var(--muted); font-weight: 600; text-transform: uppercase; }
  .badge.approved { background: var(--good); color: #0f1a10; }
  .badge.flagged { background: var(--warn); color: #1a1a0f; }
  .badge.skipped { background: var(--skip); color: white; }
  .empty { text-align: center; color: var(--muted); padding: 60px 20px; }
</style>
</head>
<body>
<div id="app">
  <aside class="sidebar">
    <div class="sidebar-header">
      <h1>ZohoVideoRenamer</h1>
      <div class="progress">
        <span id="progress-text">0 of 0 reviewed</span>
        <div class="progress-bar"><div class="progress-fill" id="progress-fill"></div></div>
      </div>
    </div>
    <div class="filter">
      <input type="text" id="filter-input" placeholder="Search stubs / names...">
      <div class="filter-buttons">
        <button class="filter-btn active" data-filter="all">All</button>
        <button class="filter-btn" data-filter="pending">Pending</button>
        <button class="filter-btn" data-filter="approved">Approved</button>
        <button class="filter-btn" data-filter="flagged">Flagged</button>
      </div>
    </div>
    <div class="entry-list" id="entry-list"></div>
    <div class="export-bar">
      <button id="export-btn">Export approvals (JSON)</button>
      <button id="reset-btn" style="margin-top:8px;background:var(--bad);color:white;">Reset all decisions</button>
    </div>
  </aside>
  <main class="main" id="main-content"><div class="empty">Loading...</div></main>
</div>
<div class="toast" id="toast"></div>
<div class="modal" id="modal" onclick="closeModal()"></div>

<script>
const DATA = __DATA__;
const STATE_KEY = 'zvr_state_v1';
let state = {};
try { const raw = localStorage.getItem(STATE_KEY); if (raw) state = JSON.parse(raw); } catch (e) { state = {}; }

let currentIndex = 0;
let filteredEntries = DATA.entries.slice();
let activeFilter = 'all';
let searchTerm = '';

function saveState() { localStorage.setItem(STATE_KEY, JSON.stringify(state)); }
function showToast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg; t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 1500);
}

function applyFilter() {
  const term = searchTerm.trim().toLowerCase();
  filteredEntries = DATA.entries.filter(e => {
    const s = state[e.id];
    if (activeFilter === 'pending' && (s && s.status === 'approved')) return false;
    if (activeFilter === 'approved' && (!s || s.status !== 'approved')) return false;
    if (activeFilter === 'flagged' && (!s || s.status !== 'flagged')) return false;
    if (term) {
      const name = (s && s.name) || '';
      return e.stub.toLowerCase().includes(term) || name.toLowerCase().includes(term) ||
             (e.suggested_name || '').toLowerCase().includes(term);
    }
    return true;
  });
  if (currentIndex >= filteredEntries.length) currentIndex = Math.max(0, filteredEntries.length - 1);
  renderSidebar();
  render();
}

function renderSidebar() {
  const list = document.getElementById('entry-list');
  list.innerHTML = '';
  filteredEntries.forEach((e, i) => {
    const s = state[e.id];
    const div = document.createElement('div');
    div.className = 'entry-item' + (i === currentIndex ? ' active' : '');
    let icon = '·';
    if (s) {
      if (s.status === 'approved') icon = '✓';
      else if (s.status === 'flagged') icon = '⚐';
      else if (s.status === 'skipped') icon = '~';
    }
    div.innerHTML = `<span class="status">${icon}</span><span class="stub">${e.stub}</span><span class="vcount">${e.videos.length}</span>`;
    div.onclick = () => { currentIndex = i; render(); };
    list.appendChild(div);
  });
  const approved = Object.values(state).filter(s => s.status === 'approved').length;
  document.getElementById('progress-text').textContent = `${approved} of ${DATA.entries.length} approved`;
  document.getElementById('progress-fill').style.width = (100 * approved / DATA.entries.length) + '%';
}

function getExcluded(entry) {
  const s = state[entry.id] || {};
  return new Set(s.excluded || []);
}
function isExcluded(entry, videoFilename) {
  return getExcluded(entry).has(videoFilename);
}
function includedVideos(entry) {
  const excl = getExcluded(entry);
  return entry.videos.filter(v => !excl.has(v.filename));
}
function toggleVideo(entryId, videoFilename, event) {
  if (event) { event.stopPropagation(); }
  state[entryId] = state[entryId] || {};
  state[entryId].excluded = state[entryId].excluded || [];
  const arr = state[entryId].excluded;
  const idx = arr.indexOf(videoFilename);
  if (idx >= 0) arr.splice(idx, 1); else arr.push(videoFilename);
  saveState();
  render();
}

function namesForEntry(entry, baseName) {
  baseName = (baseName || '').trim();
  if (!baseName) return [];
  const out = [];
  const included = includedVideos(entry);
  const multi = included.length > 1;
  included.forEach((v, i) => {
    const suffix = multi ? `-v${i+1}` : '';
    const folder = v.rel_path.split('/').slice(0, -1).join('/');
    const ext = v.filename.match(/\.[^.]+$/)[0];
    out.push({type:'video', from: v.rel_path, to: (folder ? folder + '/' : '') + baseName + suffix + ext});
  });
  // Stills: same folder collisions handled by appending -copy / -copy-N
  const usedTargets = new Set();
  let copyIdx = 0;
  entry.all_still_files.forEach(s => {
    const folder = s.rel_path.split('/').slice(0, -1).join('/');
    const ext = s.filename.match(/\.[^.]+$/)[0] || '.png';
    let stem = baseName;
    if (s.is_copy) stem = baseName + '-copy';
    let candidate = (folder ? folder + '/' : '') + stem + ext;
    while (usedTargets.has(candidate)) {
      copyIdx++;
      candidate = (folder ? folder + '/' : '') + `${stem}-${copyIdx+1}` + ext;
    }
    usedTargets.add(candidate);
    out.push({type:'still', from: s.rel_path, to: candidate});
  });
  return out;
}

function render() {
  const main = document.getElementById('main-content');
  if (filteredEntries.length === 0) {
    main.innerHTML = '<div class="empty">No entries match.</div>';
    return;
  }
  const entry = filteredEntries[currentIndex];
  const s = state[entry.id] || {};
  const initialName = s.name || entry.suggested_name || entry.stub;

  let stillFiles = '';
  entry.all_still_files.forEach(f => {
    const tag = f.is_copy ? 'copy' : 'original';
    stillFiles += `<li><span class="tag">${tag}</span>${f.rel_path}</li>`;
  });

  // Build video cards. Each card has an include/exclude toggle so the user
  // can keep correct matches and reject wrong ones within the same entry.
  // v1/v2 numbering uses the INCLUDED-only index, not the raw match index.
  const includedOnly = includedVideos(entry);
  const includedFilenames = new Set(includedOnly.map(v => v.filename));
  let videoCards = '';
  entry.videos.forEach((v, i) => {
    const included = includedFilenames.has(v.filename);
    const includedIdx = included ? includedOnly.indexOf(v) : -1;
    const vSuffix = !included
      ? "(excluded — will not be renamed)"
      : (includedOnly.length > 1 ? `-v${includedIdx+1}` : "(no suffix)");
    const safeFilename = v.filename.replace(/'/g,"\\\\'").replace(/"/g,'&quot;');
    videoCards += `
      <div class="video-card ${included ? '' : 'excluded'}" onclick="toggleVideo('${entry.id}', '${safeFilename}', event)" title="${included ? 'Click to exclude this video' : 'Click to include this video'}">
        <span class="include-toggle">${included ? '✓ KEEP' : '✗ EXCLUDED'}</span>
        <span class="vbadge">${i+1}${entry.videos.length > 1 ? `/${entry.videos.length}` : ''}</span>
        <img src="${v.thumb}" loading="lazy" alt="" onclick="event.stopPropagation(); zoomImage(this.src);">
        <button class="play-btn" onclick="event.stopPropagation(); playVideo('${v.rel_path.replace(/'/g,"&apos;")}');">▶ play</button>
        <div class="vname">${v.filename}</div>
        <div style="font-size:11px;color:${included ? 'var(--accent)' : 'var(--bad)'};margin-top:4px;font-family:monospace;">→ ${vSuffix}</div>
      </div>`;
  });

  const renames = namesForEntry(entry, initialName);
  const renamesHTML = renames.map(r =>
    `<div><span class="from">${r.from}</span> <span class="arrow">→</span> <span class="new">${r.to}</span></div>`
  ).join('');

  let badges = '';
  if (s.status === 'approved') badges = '<span class="badge approved">Approved</span>';
  else if (s.status === 'flagged') badges = '<span class="badge flagged">Flagged</span>';
  else if (s.status === 'skipped') badges = '<span class="badge skipped">Skipped</span>';

  main.innerHTML = `
    <div class="breadcrumb">${currentIndex+1} of ${filteredEntries.length}  ·  stub: <strong>${entry.stub}</strong>  ${badges}</div>
    <h2 class="entry-title">${initialName}</h2>
    <div class="preview-row">
      <div class="still-box">
        <h3>Still Frame</h3>
        ${entry.still_thumb
          ? `<img class="still-preview" src="${entry.still_thumb}" onclick="zoomImage('${entry.still_thumb}')" alt="">`
          : '<div class="empty">No still preview available</div>'}
        <ul class="still-file-list">${stillFiles}</ul>
      </div>
      <div class="video-box">
        <h3>Matched Videos (${includedOnly.length === entry.videos.length ? entry.videos.length : `${includedOnly.length} of ${entry.videos.length} kept`}) <span style="color:var(--muted);text-transform:none;font-weight:400;letter-spacing:0;font-size:11px;">— click a card to exclude wrong matches</span></h3>
        <div class="video-grid">${videoCards}</div>
      </div>
    </div>
    <div class="form-row">
      <label>New base name (hyphenated, e.g. <code>mountain-pink-clouds</code>)</label>
      <input id="name-input" class="name-input" value="${initialName.replace(/"/g,'&quot;')}" autocomplete="off" spellcheck="false">
      <div class="name-hint">Final filename preview (videos get -v1, -v2... when multiple exist; stills with 'copy' get -copy suffix):</div>
      <div class="preview-renames" id="preview-renames">${renamesHTML}</div>
      <div class="actions">
        <button class="btn btn-approve" onclick="approve()">Approve ↩</button>
        <button class="btn btn-skip" onclick="skip()">Skip (s)</button>
        <button class="btn btn-flag" onclick="flag()">Flag (f)</button>
        <button class="btn btn-reset" onclick="resetEntry()">Reset</button>
      </div>
    </div>
    <div class="nav">
      <button class="btn btn-secondary" onclick="goPrev()">← Prev (p)</button>
      <button class="btn btn-secondary" onclick="goNext()">Next → (n)</button>
    </div>
    <div class="keyboard-hints"><kbd>Enter</kbd> approve · <kbd>S</kbd> skip · <kbd>F</kbd> flag · <kbd>P</kbd> prev · <kbd>N</kbd> next</div>
  `;

  const ni = document.getElementById('name-input');
  ni.addEventListener('input', () => {
    const previewEl = document.getElementById('preview-renames');
    const renames = namesForEntry(entry, ni.value);
    previewEl.innerHTML = renames.map(r =>
      `<div><span class="from">${r.from}</span> <span class="arrow">→</span> <span class="new">${r.to}</span></div>`
    ).join('');
  });
  ni.focus();
  ni.select();
  renderSidebar();
}

function approve() {
  const entry = filteredEntries[currentIndex];
  const name = document.getElementById('name-input').value.trim();
  if (!name) { showToast('Enter a name first'); return; }
  if (!/^[a-z0-9][a-z0-9\-]*$/i.test(name)) { showToast('Use only letters, numbers, hyphens.'); return; }
  state[entry.id] = { status: 'approved', name: name.toLowerCase(), ts: Date.now() };
  saveState(); showToast('Approved: ' + name); goNext(true);
}
function skip() {
  const entry = filteredEntries[currentIndex];
  state[entry.id] = { status: 'skipped', name: state[entry.id]?.name, ts: Date.now() };
  saveState(); goNext(true);
}
function flag() {
  const entry = filteredEntries[currentIndex];
  const name = document.getElementById('name-input').value.trim();
  state[entry.id] = { status: 'flagged', name: name, ts: Date.now() };
  saveState(); goNext(true);
}
function resetEntry() { delete state[filteredEntries[currentIndex].id]; saveState(); render(); }
function goNext(skipApproved = false) {
  if (skipApproved) {
    for (let i = currentIndex + 1; i < filteredEntries.length; i++) {
      const s = state[filteredEntries[i].id];
      if (!s || s.status !== 'approved') { currentIndex = i; render(); return; }
    }
  }
  if (currentIndex < filteredEntries.length - 1) { currentIndex++; render(); }
  else { showToast('End of list.'); }
}
function goPrev() { if (currentIndex > 0) { currentIndex--; render(); } }
function zoomImage(src) { const m = document.getElementById('modal'); m.innerHTML = `<img src="${src}">`; m.classList.add('show'); }
function playVideo(rel) { const m = document.getElementById('modal'); m.innerHTML = `<video src="${rel}" controls autoplay loop></video>`; m.classList.add('show'); }
function closeModal() { const m = document.getElementById('modal'); m.classList.remove('show'); m.innerHTML = ''; }

document.getElementById('export-btn').onclick = () => {
  const out = [];
  DATA.entries.forEach(e => {
    const s = state[e.id];
    if (s && s.status === 'approved') {
      out.push({ id: e.id, stub: e.stub, status: s.status, name: s.name,
                 renames: namesForEntry(e, s.name) });
    }
  });
  const flagged = [];
  DATA.entries.forEach(e => {
    const s = state[e.id];
    if (s && s.status === 'flagged') {
      flagged.push({ id: e.id, stub: e.stub, status: s.status, name: s.name || '' });
    }
  });
  const blob = new Blob([JSON.stringify({approved: out, flagged: flagged, exported_at: new Date().toISOString()}, null, 2)], {type:'application/json'});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = 'rename-approvals.json'; a.click();
  showToast(`Exported ${out.length} approvals (${flagged.length} flagged)`);
};
document.getElementById('reset-btn').onclick = () => {
  if (confirm('Wipe ALL decisions? This cannot be undone.')) { state = {}; saveState(); render(); showToast('All decisions cleared.'); }
};
document.getElementById('filter-input').addEventListener('input', (e) => { searchTerm = e.target.value; applyFilter(); });
document.querySelectorAll('.filter-btn').forEach(btn => {
  btn.onclick = () => {
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    activeFilter = btn.dataset.filter; applyFilter();
  };
});
document.addEventListener('keydown', (e) => {
  if (e.target.tagName === 'INPUT') { if (e.key === 'Enter') { e.preventDefault(); approve(); } return; }
  if (document.getElementById('modal').classList.contains('show')) { if (e.key === 'Escape') closeModal(); return; }
  if (e.key === 'n' || e.key === 'ArrowRight') goNext();
  else if (e.key === 'p' || e.key === 'ArrowLeft') goPrev();
  else if (e.key === 's') skip();
  else if (e.key === 'f') flag();
});

applyFilter();
render();
</script>
</body>
</html>
"""
