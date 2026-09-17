#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv, json
from pathlib import Path
from typing import Dict, List

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>PhosphoFill 3Dmol Comparison</title>
<script src="https://code.jquery.com/jquery-3.7.1.min.js"></script>
<script src="https://unpkg.com/3dmol@2.4.2/build/3Dmol-min.js"></script>
<script>
/* Fallback chain if unpkg fails */
if (typeof $3Dmol === 'undefined') {
  var s = document.createElement('script');
  s.src = 'https://cdnjs.cloudflare.com/ajax/libs/3Dmol/2.4.2/3Dmol-min.js';
  document.head.appendChild(s);
}
</script>
<style>
:root { --bg:#f5f6f8; --panel:#ffffff; --border:#d9dce3; --text:#1f2937; --muted:#6b7280; --warning:#b45309; }
html,body { margin:0; padding:0; background:var(--bg); color:var(--text); font-family:Arial,Helvetica,sans-serif; height:100%; }
.app { display:grid; grid-template-columns:320px 1fr; grid-template-rows:100vh; }
.sidebar { overflow-y:auto; overflow-x:hidden; background:var(--panel); border-right:1px solid var(--border); padding:14px 14px 18px 14px; box-sizing:border-box; }
.main { display:grid; grid-template-rows:minmax(0,1fr) minmax(0,1fr); gap:10px; padding:10px; box-sizing:border-box; height:100vh; overflow:hidden; }
.viewer-card { background:var(--panel); border:1px solid var(--border); border-radius:8px; overflow:hidden; display:grid; grid-template-rows:36px 1fr; }
.viewer-title { display:flex; align-items:center; justify-content:space-between; padding:0 12px; font-size:14px; font-weight:700; border-bottom:1px solid var(--border); }
.viewer { width:100%; height:100%; min-height:0; position:relative; }
/* Custom maximize button */
.max-btn { background:none; border:none; cursor:pointer; font-size:15px; padding:2px 6px; color:var(--muted); line-height:1; margin-left:8px; }
.max-btn:hover { color:var(--text); }
/* Fullscreen overlay — position:fixed keeps grid untouched */
.fs-host { position:fixed; inset:0; z-index:10020; background:var(--bg); padding:0; margin:0; display:none; }
.fs-host.active { display:block; }
.fs-host .viewer-card { border-radius:0; border:none; width:100vw; height:100vh; min-height:100vh; }
.small-note { font-size:12px; color:var(--muted); }
h1 { font-size:20px; margin:0 0 8px 0; }
h2 { font-size:14px; margin:16px 0 8px 0; }

/* ── Confidence badge ── */
.confidence-badge {
  display:inline-flex; align-items:center; justify-content:center;
  width:52px; height:52px; border-radius:50%; font-size:20px; font-weight:800;
  color:#fff; margin:4px 8px 4px 0; flex-shrink:0;
  box-shadow:0 2px 8px rgba(0,0,0,0.18); transition:background 0.3s;
}
.confidence-badge.tier-high { background:linear-gradient(135deg,#059669,#10b981); }
.confidence-badge.tier-moderate { background:linear-gradient(135deg,#d97706,#f59e0b); }
.confidence-badge.tier-low { background:linear-gradient(135deg,#dc2626,#ef4444); }
.confidence-badge.tier-unknown { background:#9ca3af; }
.confidence-row { display:flex; align-items:center; margin-bottom:8px; }
.confidence-text { font-size:13px; line-height:1.35; }
.confidence-text .tier-label { font-weight:700; font-size:14px; }

/* ── Visual traffic light ── */
.traffic-light { display:inline-flex; align-items:center; gap:6px; }
.traffic-dot {
  width:18px; height:18px; border-radius:50%; border:2px solid rgba(0,0,0,0.12);
  box-shadow:inset 0 1px 3px rgba(0,0,0,0.15);
}
.traffic-dot.green { background:radial-gradient(circle at 35% 35%,#6ee7b7,#059669); }
.traffic-dot.amber { background:radial-gradient(circle at 35% 35%,#fcd34d,#d97706); }
.traffic-dot.red { background:radial-gradient(circle at 35% 35%,#fca5a5,#dc2626); }
.traffic-dot.unknown { background:#d1d5db; }
.traffic-label { font-weight:700; font-size:13px; text-transform:capitalize; }

/* ── Prescan animation modal ── */
.prescan-modal {
  display:none; position:fixed; inset:0; z-index:10000;
  background:rgba(15,23,42,0.8); backdrop-filter:blur(4px);
  justify-content:center; align-items:center;
}
.prescan-modal.open { display:flex; }
.prescan-panel {
  background:#fff; border-radius:14px; width:min(780px,94vw); max-height:90vh;
  overflow-y:auto; box-shadow:0 12px 48px rgba(0,0,0,0.3); padding:24px;
}
.prescan-panel h3 { margin:0 0 12px 0; font-size:16px; }
.prescan-controls { display:flex; align-items:center; gap:10px; margin:12px 0; }
.prescan-controls button { font-size:13px; padding:6px 14px; border-radius:6px; border:1px solid var(--border); background:#f8fafc; cursor:pointer; }
.prescan-controls button:hover { background:#e2e8f0; }
.prescan-controls .step-label { font-size:14px; font-weight:700; min-width:80px; text-align:center; }
.polar-chart-wrap { display:flex; justify-content:center; margin:12px 0; }
.prescan-stats { display:grid; grid-template-columns:1fr 1fr 1fr; gap:8px; font-size:12px; margin-top:10px; }
.prescan-stat { background:#f1f5f9; border-radius:6px; padding:8px; text-align:center; }
.prescan-stat .ps-val { font-size:16px; font-weight:700; }
.prescan-stat .ps-label { color:var(--muted); margin-top:2px; }
.alignment-modal {
  display:none; position:fixed; inset:0; z-index:10000;
  background:rgba(15,23,42,0.76); backdrop-filter:blur(4px);
  justify-content:center; align-items:center; padding:18px; box-sizing:border-box;
}
.alignment-modal.open { display:flex; }
.alignment-panel { width:min(1280px,96vw); height:min(860px,92vh); display:grid; }
.alignment-panel .viewer-card { width:100%; height:100%; min-height:0; }
.close-btn { background:none; border:none; font-size:20px; cursor:pointer; color:var(--muted); padding:0 2px; line-height:1; }
.close-btn:hover { color:var(--text); background:none; }
.select-row,.btn-row { display:flex; gap:8px; margin-bottom:10px; }
.select-row { max-width:100%; overflow:hidden; }
select,button { font-size:12px; padding:6px 8px; border-radius:6px; border:1px solid var(--border); background:white; }
select { max-width:100%; overflow:hidden; text-overflow:ellipsis; box-sizing:border-box; }
button { cursor:pointer; }
button:hover { background:#f8fafc; }
.metric-grid { display:grid; grid-template-columns:1fr 1fr; gap:8px 10px; font-size:13px; }
.metric { border:1px solid var(--border); border-radius:6px; padding:8px; background:#fafafa; }
.metric .label { color:var(--muted); font-size:12px; margin-bottom:4px; }
.flag-list { margin:8px 0 0 18px; padding:0; }
.legend { display:grid; gap:6px; font-size:12px; }
.legend-item { display:flex; align-items:center; gap:8px; }
.swatch { width:14px; height:14px; border-radius:3px; border:1px solid #cbd5e1; }
.codebox { margin-top:6px; padding:8px; background:#f8fafc; border:1px solid var(--border); border-radius:6px; font-size:12px; white-space:pre-wrap; word-break:break-word; }
#status { margin-top:8px; font-size:12px; color:var(--warning); }
#contactDetails { max-height:200px; overflow-y:auto; }
/* Toggle group for contact display mode */
.toggle-group { display:flex; gap:0; margin-bottom:10px; }
.toggle-group button { border-radius:0; border-right-width:0; font-size:11px; padding:5px 10px; }
.toggle-group button:first-child { border-radius:6px 0 0 6px; }
.toggle-group button:last-child { border-radius:0 6px 6px 0; border-right-width:1px; }
.toggle-group button.active { background:#e0e7ff; border-color:#818cf8; color:#4338ca; font-weight:700; }
/* Info icon & tooltip */
.metric .label { position:relative; display:flex; align-items:flex-start; gap:4px; }
.info-icon {
  display:inline-flex; align-items:center; justify-content:center;
  width:14px; height:14px; min-width:14px; border-radius:50%;
  background:#e2e8f0; color:#64748b; font-size:9px; font-weight:700;
  font-style:italic; font-family:Georgia,serif; cursor:help;
  line-height:1; margin-top:1px; flex-shrink:0;
}
.info-icon:hover { background:#cbd5e1; color:#334155; }
.metric-tip {
  display:none; position:fixed; z-index:10000;
  background:#1e293b; color:#f1f5f9; font-size:12px; line-height:1.45;
  padding:10px 12px; border-radius:8px; max-width:280px; min-width:180px;
  box-shadow:0 4px 16px rgba(0,0,0,0.25);
  pointer-events:none; font-weight:400; font-style:normal;
}
.metric-tip .tip-title { font-weight:700; margin-bottom:4px; color:#ffffff; font-size:12px; }
.metric-tip .tip-calc { color:#94a3b8; margin-top:4px; font-size:11px; }
.metric-tip .tip-interpret { color:#a5f3fc; margin-top:4px; font-size:11px; }

.poseBtn.active { background:#e0e7ff; border-color:#818cf8; color:#4338ca; font-weight:700; }
.poseBtn:disabled { opacity:0.45; cursor:not-allowed; background:#f3f4f6; color:#9ca3af; }

</style>
</head>
<body>
<div class="app">
  <aside class="sidebar">
    <h1>PhosphoFill</h1>
    <div class="small-note">Single-protein structural comparison with PhosphoFill-identified contacts.</div>
    <h2>Controls</h2>
    <div class="select-row"><select id="siteSelect" style="flex:1;"></select></div>
    <div class="btn-row"><button id="prevBtn">Previous</button><button id="nextBtn">Next</button></div>
    <h2>Candidate poses</h2>
    <div class="btn-row" id="poseButtons"><button class="poseBtn active" data-pose="1">PF1</button><button class="poseBtn" data-pose="2">PF2</button><button class="poseBtn" data-pose="3">PF3</button></div>
    <div class="small-note">Switch between PhosphoFill candidate structures for the current site.</div>
    <div class="btn-row"><button id="showAlignmentBtn">View alignment</button></div>
    <div id="alignmentNote" class="small-note" style="display:none;">Alignment opens as a pop-up overlay for the selected PhosphoFill candidate.</div>
    <h2>Display</h2>
    <div class="toggle-group" id="contactToggle">
      <button class="active" data-mode="residue">Residue</button>
      <button data-mode="sidechain">Sidechain</button>
      <button data-mode="atomic">Atomic</button>
    </div>
    <div class="small-note">Residue: full residue sticks. Sidechain: hide backbone. Atomic: nearest-contact atoms as spheres with distance dashes.</div>
    <h2>Current site</h2>
    <div id="siteMeta" class="codebox">Loading...</div>

    <h2>PhosphoFill Confidence</h2>
    <div class="confidence-row">
      <div id="confidenceBadge" class="confidence-badge tier-unknown">?</div>
      <div class="confidence-text">
        <div id="confidenceTier" class="tier-label">Loading...</div>
        <div id="confidenceDetail" class="small-note"></div>
      </div>
    </div>

    <h2 style="display:flex;align-items:center;gap:6px;">Summary <span class="info-icon" id="summaryInfo">i</span></h2>
    <div id="overallInterpretation" class="metric"><div class="label">Overall interpretation</div><div id="overallInterpretationText">-</div></div>

    <h2>Phospho Quality</h2>
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:8px;">
      <div class="traffic-light">
        <div id="trafficDot" class="traffic-dot unknown"></div>
        <span id="trafficLabel" class="traffic-label">-</span>
      </div>
      <button id="prescanBtn" style="font-size:11px;padding:4px 10px;border-radius:6px;border:1px solid var(--border);background:#f0f9ff;cursor:pointer;display:none;" title="View 360° phosphate rotamer scan">&#x25B6; Rotamer scan</button>
    </div>
    <h2>Metrics</h2>
    <div class="metric-grid">
      <div class="metric"><div class="label">Local C&alpha; RMSD</div><div id="m_local_ca_rmsd">-</div></div>
      <div class="metric"><div class="label">pLDDT site</div><div id="m_plddt_site">-</div></div>
      <div class="metric"><div class="label">pLDDT window mean</div><div id="m_plddt_window">-</div></div>
      <div class="metric"><div class="label">Clashes before / after</div><div id="m_clashes">-</div></div>
      <div class="metric"><div class="label">Nearest distance before / after</div><div id="m_distances">-</div></div>
      <div class="metric"><div class="label">Electrostatic (weighted) before / after</div><div id="m_electrostatic">-</div></div>
      <div class="metric"><div class="label">Salt bridges before / after</div><div id="m_salt_bridges">-</div></div>
      <div class="metric"><div class="label">H-bonds before / after</div><div id="m_hbonds">-</div></div>
      <div class="metric"><div class="label">Polar contacts before / after</div><div id="m_polar_contacts">-</div></div>
      <div class="metric"><div class="label">SASA before / after</div><div id="m_sasa">-</div></div>
      <div class="metric"><div class="label">SASA shared atoms before / after</div><div id="m_sasa_shared">-</div></div>
      <div class="metric"><div class="label">SASA delta</div><div id="m_sasa_delta">-</div></div>
      <div class="metric"><div class="label">Neighbor SASA delta</div><div id="m_neighbor_sasa_delta">-</div></div>
      <div class="metric"><div class="label">Exposure class</div><div id="m_exposure">-</div></div>
      <div class="metric"><div class="label">Contact residues before / after</div><div id="m_contacts_count">-</div></div>
      <div class="metric"><div class="label">CB neighborhood (8&Aring;) before / after</div><div id="m_cb_neighborhood">-</div></div>
    </div>
    <div id="saltBridgeDetails" class="codebox" style="font-size:12px;display:none;margin-top:6px;"></div>
    <div id="cbNeighborhoodDetails" class="codebox" style="font-size:12px;display:none;margin-top:6px;"></div>
    <h2 style="display:flex;align-items:center;gap:6px;">Contact details <span class="info-icon" id="contactDetailsInfo">i</span></h2>
    <div id="contactDetails" class="codebox" style="font-size:12px;">-</div>
    <h2>Interpretation flags</h2>
    <ul id="flagList" class="flag-list"></ul>
    <h2>Color legend</h2>
    <div class="legend">
      <div class="legend-item"><span class="swatch" style="background:#9e9e9e;"></span> Unmodified cartoon (grey)</div>
      <div class="legend-item"><span class="swatch" style="background:#90caf9;"></span> Modified cartoon (light blue)</div>
      <div class="legend-item"><span class="swatch" style="background:#ef4444;"></span> Phosphosite (red sticks)</div>
      <div class="legend-item"><span class="swatch" style="background:#d97706;"></span> Lost contacts (orange)</div>
      <div class="legend-item"><span class="swatch" style="background:#059669;"></span> Gained contacts (green)</div>
      <div class="legend-item"><span class="swatch" style="background:#7c3aed;"></span> Maintained contacts (purple)</div>
    </div>
    <div class="small-note" style="margin-top:8px;">Dashed lines show nearest-atom distances (&Aring;) between phosphosite and each contact residue. Only PhosphoFill-identified contacts are displayed.</div>
    <h2>Files</h2>
    <div class="codebox" id="fileBox"></div>
    <div id="status"></div>
    <div class="small-note" style="margin-top:10px;">Keyboard: left/right arrow to move between sites. Escape exits fullscreen or closes pop-ups.</div>
  </aside>
  <main class="main">
    <section id="unmod-card" class="viewer-card">
      <div class="viewer-title"><span>Unmodified</span><span><span class="small-note">grey &middot; before contacts</span><button class="max-btn" onclick="toggleFullscreen('unmod')" title="Maximize unmodified">&#x26F6;</button></span></div>
      <div id="viewer-unmod" class="viewer"></div>
    </section>
    <section id="mod-card" class="viewer-card">
      <div class="viewer-title"><span>Modified <span id="modPoseTitle" class="small-note">PF1</span></span><span><span class="small-note">blue &middot; after contacts</span><button class="max-btn" onclick="toggleFullscreen('mod')" title="Maximize modified">&#x26F6;</button></span></div>
      <div id="viewer-mod" class="viewer"></div>
    </section>
  </main>
</div>

<div id="fullscreenHost" class="fs-host"></div>

<div id="alignmentModal" class="alignment-modal">
  <div class="alignment-panel">
    <section id="overlay-card" class="viewer-card">
      <div class="viewer-title"><span>Alignment comparison <span id="overlayPoseTitle" class="small-note">PF1 vs unmodified</span></span><span><span class="small-note">all contact categories</span><button class="max-btn" onclick="toggleFullscreen('alignment')" title="Maximize alignment">&#x26F6;</button><button class="close-btn" onclick="closeAlignmentModal()" title="Close alignment">&times;</button></span></div>
      <div id="viewer-overlay" class="viewer"></div>
    </section>
  </div>
</div>

<!-- Prescan animation modal -->
<div id="prescanModal" class="prescan-modal">
  <div class="prescan-panel">
    <div style="display:flex;justify-content:space-between;align-items:center;">
      <h3 id="prescanTitle">360° Phosphate Rotamer Scan</h3>
      <button onclick="closePrescanModal()" style="background:none;border:none;font-size:20px;cursor:pointer;color:var(--muted);">&times;</button>
    </div>
    <div class="small-note" style="margin-bottom:10px;">Step through all PO₃ orientations around the bridging bond. The schematic shows the parent residue sidechain in grey sticks, with the phosphate group (orange P, red O atoms) rotating at the attachment point and contacts to neighboring residues. Red dashed = clash, green dashed = polar contact.</div>
    <div class="polar-chart-wrap"><canvas id="polarCanvas" width="420" height="420"></canvas></div>
    <div style="display:flex;gap:16px;justify-content:center;font-size:11px;color:#64748b;margin:-4px 0 8px 0;">
      <span><span style="display:inline-block;width:10px;height:2px;background:#9ca3af;vertical-align:middle;"></span> parent residue</span>
      <span><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#f97316;vertical-align:middle;"></span> P</span>
      <span><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#ef4444;vertical-align:middle;"></span> O atoms</span>
      <span style="color:#dc2626;">--- clash</span>
      <span style="color:#059669;">--- polar contact</span>
      <span style="color:#94a3b8;">--- nearby</span>
      <span style="color:#f59e0b;">★ best</span>
    </div>
    <div class="prescan-controls">
      <button id="psFirst">&#x23EE; First</button>
      <button id="psPrev">&#x25C0; Prev</button>
      <span id="psStepLabel" class="step-label">0° / 360°</span>
      <button id="psNext">Next &#x25B6;</button>
      <button id="psLast">Last &#x23ED;</button>
      <button id="psPlay">&#x25B6; Play</button>
    </div>
    <div id="psFrameInfo" class="codebox" style="font-size:12px;margin-top:8px;">Select a site with prescan data.</div>
    <div class="prescan-stats" id="psStats"></div>
  </div>
</div>

<script>
"use strict";

/* ══════════════════════════════════════
   DATA
   ══════════════════════════════════════ */
var REPORT = __REPORT_JSON__;
var FILES  = __FILES_JSON__;

var state = {
  index: 0,
  viewers: {},
  cifData: {},
  displayMode: 'residue',
  prescanFrames: {},    /* site_label -> [{angle, clash_score, contact_bonus, total_score, n_clashing, coords}, ...] */
  prescanIndex: 0,
  prescanPlaying: false,
  prescanTimer: null,
  poseIndex: 1,
  alignmentMode: false,
  fmtUn: 'cif'
};

var COLORS = {
  unmodCartoon:      '#9e9e9e',
  modCartoon:        '#90caf9',
  siteRed:           '#ef4444',
  contactLost:       '#d97706',
  contactGained:     '#059669',
  contactMaintained: '#7c3aed'
};

function currentBaseRow() { return REPORT.sites[state.index] || null; }
function currentPoseKey() { return 'pf' + String(state.poseIndex); }
function currentModifiedFile() { return FILES[currentPoseKey()] || FILES.modified || FILES.pf1; }
function poseFileForIndex(idx) {
  var key = 'pf' + String(idx);
  if (FILES[key]) return FILES[key];
  if (idx === 1) return FILES.modified || FILES.pf1 || '';
  return '';
}
function currentDisplayRow() {
  var base = currentBaseRow();
  if (!base) return null;
  var poseKey = currentPoseKey();
  var cand = base[poseKey + '_row'];
  if (cand && typeof cand === 'object') {
    var merged = Object.assign({}, base, cand);
    merged._pose_path = base[poseKey + '_path'] || currentModifiedFile();
    merged._pose_rank = state.poseIndex;
    return merged;
  }
  var merged = Object.assign({}, base);
  merged.phosphofill_confidence = base[poseKey + '_confidence'] || base.phosphofill_confidence;
  merged.confidence_tier = base[poseKey + '_tier'] || base.confidence_tier;
  merged.phospho_quality_label = base[poseKey + '_quality'] || base.phospho_quality_label;
  merged.overall_interpretation = base[poseKey + '_overall_interpretation'] || base.overall_interpretation;
  if (base[poseKey + '_clashes_after']) merged.clash_count_after = base[poseKey + '_clashes_after'];
  if (base[poseKey + '_nearest_contact_after']) merged.nearest_contact_distance_after = base[poseKey + '_nearest_contact_after'];
  merged._pose_path = base[poseKey + '_path'] || currentModifiedFile();
  merged._pose_rank = state.poseIndex;
  return merged;
}
function syncPoseButtons() {
  document.querySelectorAll('.poseBtn').forEach(function(btn) {
    btn.classList.toggle('active', parseInt(btn.getAttribute('data-pose'), 10) === state.poseIndex);
  });
  var m = document.getElementById('modPoseTitle'); if (m) m.textContent = 'PF' + state.poseIndex;
  var o = document.getElementById('overlayPoseTitle'); if (o) o.textContent = 'PF' + state.poseIndex + ' vs unmodified';
}
function updateAvailablePoseButtons() {
  var firstAvailable = null;
  document.querySelectorAll('.poseBtn').forEach(function(btn) {
    var idx = parseInt(btn.getAttribute('data-pose'), 10);
    var available = !!poseFileForIndex(idx);
    btn.disabled = !available;
    btn.style.display = available ? '' : 'none';
    if (available && firstAvailable === null) firstAvailable = idx;
  });
  if (!poseFileForIndex(state.poseIndex) && firstAvailable !== null) state.poseIndex = firstAvailable;
  syncPoseButtons();
}
function loadPoseModels() {
  var modKey = currentPoseKey();
  var modText = state.cifData[modKey] || state.cifData.mod;
  var modFile = currentModifiedFile();
  if (!modText) throw new Error('Missing structure text for ' + modKey + ' (' + modFile + ')');
  var fmt2 = modFile.match(/\.(cif|mmcif)$/i) ? 'cif' : 'pdb';
  state.viewers.mod.removeAllModels();
  state.viewers.overlay.removeAllModels();
  state.viewers.mod.addModel(modText, fmt2);
  state.viewers.overlay.addModel(state.cifData.unmod, state.fmtUn);
  state.viewers.overlay.addModel(modText, fmt2);
  syncPoseButtons();
}

/* ══════════════════════════════════════
   METRIC INFO TOOLTIPS
   ══════════════════════════════════════ */
var METRIC_INFO = {
  overallInterpretationText: {
    title: 'Overall Interpretation',
    desc: 'A human-readable summary sentence describing the phosphorylation site quality and notable features.',
    calc: 'Generated from the combination of phospho quality label, clash status, electrostatic environment, salt bridges, and pLDDT confidence.',
    interpret: 'Read as a plain-language verdict. Key phrases: "well accommodated" = good fit, "clashing" = steric problems, "salt-bridge stabilization" = favorable ionic interaction.'
  },
  m_local_ca_rmsd: {
    title: 'Local C\u03B1 RMSD',
    desc: 'Backbone displacement around the site after phosphate grafting, measured over a sequence window of C\u03B1 atoms.',
    calc: 'RMSD of C\u03B1 atoms within the analysis window between unmodified and modified structures (Kabsch-aligned).',
    interpret: 'Values near 0 \u00C5 mean no backbone distortion. Values above ~0.5 \u00C5 suggest the phosphate is forcing conformational strain.'
  },
  m_plddt_site: {
    title: 'pLDDT Site',
    desc: 'AlphaFold per-residue confidence score at the phosphorylation site.',
    calc: 'Extracted directly from the B-factor column of the AlphaFold model (pLDDT mapped to 0\u2013100).',
    interpret: 'Very high (>90): excellent. Confident (70\u201390): reliable. Low (50\u201370): caution. Very low (<50): structure may be unreliable here.'
  },
  m_plddt_window: {
    title: 'pLDDT Window Mean',
    desc: 'Average pLDDT confidence over the sequence window surrounding the phosphosite.',
    calc: 'Mean of pLDDT values for residues within \u00B15 positions of the site.',
    interpret: 'A high window mean confirms the local fold is well-predicted. Low values mean even the neighborhood is uncertain.'
  },
  m_clashes: {
    title: 'Steric Clashes',
    desc: 'Number of atom pairs between the phosphosite and neighbors with van der Waals overlap.',
    calc: 'Count of non-bonded heavy-atom pairs closer than the sum of their vdW radii minus a tolerance (\u22480.4 \u00C5).',
    interpret: 'Before/after comparison. An increase means the phosphate group introduced new steric conflicts. Zero clashes is ideal.'
  },
  m_distances: {
    title: 'Nearest Contact Distance',
    desc: 'Closest interatomic distance between the phosphosite and any neighboring residue.',
    calc: 'Minimum heavy-atom pairwise distance between the site and all non-bonded neighbors.',
    interpret: 'Values < 2.0 \u00C5 indicate steric clashes. 2.5\u20133.5 \u00C5 is typical for H-bonds and salt bridges. > 4 \u00C5 means no close contacts.'
  },
  m_electrostatic: {
    title: 'Electrostatic Score (Weighted)',
    desc: 'Distance-weighted electrostatic complementarity of the site with its charged neighbors.',
    calc: 'Sum of (charge_i \u00D7 charge_j / distance) for all charged atom pairs involving the phosphosite within a cutoff radius.',
    interpret: 'Positive values = favorable (opposite charges nearby, e.g. phosphate near Arg/Lys). Negative = unfavorable (like charges repelling). Zero = no charged neighbors.'
  },
  m_salt_bridges: {
    title: 'Salt Bridges',
    desc: 'Formal ionic interactions between oppositely charged groups within ~4 \u00C5.',
    calc: 'Count of Arg/Lys\u2013phosphate or Asp/Glu\u2013Arg/Lys pairs where charged atoms are \u2264 4.0 \u00C5 apart.',
    interpret: 'Salt bridges after phosphorylation suggest the phosphate is stabilized by a nearby basic residue. More = better accommodation.'
  },
  m_hbonds: {
    title: 'Hydrogen Bonds',
    desc: 'H-bonds passing both distance and angle criteria between the site and neighbors.',
    calc: 'Donor\u2013acceptor distance \u2264 3.5 \u00C5 AND donor\u2013H\u2013acceptor angle \u2265 120\u00B0.',
    interpret: 'H-bonds indicate specific, directional stabilization. An increase after modification means the phosphate is forming favorable polar interactions.'
  },
  m_polar_contacts: {
    title: 'Polar Contacts',
    desc: 'Broader count of polar atom pairs close enough to potentially interact, without strict angle criteria.',
    calc: 'Pairs of N/O/S atoms between site and neighbors within 3.5 \u00C5 (no angle check).',
    interpret: 'A superset of H-bonds. Useful when H positions are uncertain. More polar contacts = more potential for stabilizing interactions.'
  },
  m_sasa: {
    title: 'SASA (Total)',
    desc: 'Solvent Accessible Surface Area of the entire residue.',
    calc: 'Shrake\u2013Rupley rolling-probe calculation (1.4 \u00C5 probe) over all atoms of the residue in context of the full structure.',
    interpret: 'An increase is expected since the phosphate adds atoms. A decrease might indicate the site is being buried by conformational changes.'
  },
  m_sasa_shared: {
    title: 'SASA Shared Atoms',
    desc: 'SASA of only the atoms present in both unmodified and modified residue (excludes phosphate atoms).',
    calc: 'Same Shrake\u2013Rupley calculation, but restricted to the non-phosphate atoms that exist in both forms.',
    interpret: 'A decrease means the phosphate or rearranging neighbors are shielding the original sidechain. Indicates how much the local environment changed.'
  },
  m_sasa_delta: {
    title: 'SASA Delta',
    desc: 'Net change in total solvent-accessible surface area.',
    calc: 'SASA_modified \u2212 SASA_unmodified.',
    interpret: 'Positive = more exposed overall. Negative = more buried. Large positive values suggest the phosphate protrudes into solvent.'
  },
  m_neighbor_sasa_delta: {
    title: 'Neighbor SASA Delta',
    desc: 'Change in solvent exposure of surrounding residues after phosphorylation.',
    calc: 'Sum of \u0394SASA for all residues within the contact radius, excluding the phosphosite itself.',
    interpret: 'Negative values mean neighbors lost solvent access (phosphate is occluding them). Large negative = significant packing changes.'
  },
  m_exposure: {
    title: 'Exposure Class',
    desc: 'Categorical classification of the site as exposed, partially buried, or buried.',
    calc: 'Based on SASA thresholds: exposed (> 40 \u00C5\u00B2), partially buried (15\u201340 \u00C5\u00B2), buried (< 15 \u00C5\u00B2).',
    interpret: 'Exposed sites tolerate phosphates more easily. Buried phosphosites often have clashes and poor accommodation.'
  },
  m_contacts_count: {
    title: 'Contact Residues',
    desc: 'Number of neighboring residues within the contact distance cutoff. Before and after contacts are both measured from all heavy atoms of the residue for a fair comparison.',
    calc: 'Count of residues with at least one heavy atom within the PhosphoFill contact radius (default 4.0 \u00C5) of any heavy atom on the site residue.',
    interpret: 'An increase suggests the phosphate reaches additional neighbors. Compare lost/gained/maintained in the contact details panel below.'
  },
  m_cb_neighborhood: {
    title: 'CB Neighborhood',
    desc: 'Number of residues whose CB atom (or CA for glycine) is within 8 \u00C5 of the site CB. A rotamer-independent measure of local packing density.',
    calc: 'Count of residues with CB\u2013CB distance \u2264 8.0 \u00C5 from the site residue, measured in each structure independently.',
    interpret: 'Before/after comparison. A change means the backbone environment shifted during minimization. Stable values mean only sidechain rearrangement occurred.'
  }
};

/* Shared tooltip element */
var _tipEl = null;
function getTooltipEl() {
  if (!_tipEl) {
    _tipEl = document.createElement('div');
    _tipEl.className = 'metric-tip';
    document.body.appendChild(_tipEl);
  }
  return _tipEl;
}

function initMetricTooltips() {
  var metrics = document.querySelectorAll('.metric');
  metrics.forEach(function(m) {
    /* Find the value div with id starting with m_ */
    var valDiv = m.querySelector('[id^="m_"]');
    if (!valDiv) return;
    var info = METRIC_INFO[valDiv.id];
    if (!info) return;

    /* Create info icon */
    var icon = document.createElement('span');
    icon.className = 'info-icon';
    icon.textContent = 'i';
    icon.setAttribute('aria-label', info.title);

    /* Append icon to the label div */
    var labelDiv = m.querySelector('.label');
    if (!labelDiv) return;
    labelDiv.appendChild(icon);

    /* Hover events */
    icon.addEventListener('mouseenter', function(e) {
      var tip = getTooltipEl();
      tip.innerHTML =
        '<div class="tip-title">' + info.title + '</div>' +
        '<div>' + info.desc + '</div>' +
        '<div class="tip-calc">\u2699 ' + info.calc + '</div>' +
        '<div class="tip-interpret">\u2192 ' + info.interpret + '</div>';
      tip.style.display = 'block';

      /* Position near the icon */
      var rect = icon.getBoundingClientRect();
      var tipW = 280;
      var left = rect.right + 8;
      /* If overflows right edge, show to the left */
      if (left + tipW > window.innerWidth) {
        left = rect.left - tipW - 8;
      }
      /* If overflows left, just clamp */
      if (left < 4) left = 4;
      var top = rect.top - 8;
      /* Don't overflow bottom */
      if (top + 200 > window.innerHeight) {
        top = window.innerHeight - 220;
      }
      if (top < 4) top = 4;
      tip.style.left = left + 'px';
      tip.style.top = top + 'px';
    });

    icon.addEventListener('mouseleave', function() {
      getTooltipEl().style.display = 'none';
    });
  });
}

function initSectionTooltips() {
  var tips = {
    contactDetailsInfo: {
      title: 'Atomic contacts vs CB distances',
      desc: 'Contact residues are detected at the atomic level: any neighboring residue with at least one heavy atom within the contact radius (default 4.0 \u00C5) of any heavy atom on the site residue.',
      calc: 'Lost/gained/maintained is a set comparison of residue labels between unmodified and modified structures. Both use all heavy atoms for a fair comparison.',
      interpret: 'The CB distances shown below each contact indicate the backbone-level proximity. Small CB deltas (\u0394 near 0) mean the backbone stayed put and the contact change is due to sidechain/phosphate atoms. Large CB deltas mean the backbone itself shifted.'
    },
    summaryInfo: {
      title: 'PhosphoFill Quality Summary',
      desc: 'The confidence score (0\u2013100) combines six weighted components: pLDDT trust, steric fit, energy strain, rotational freedom, electrostatic compatibility, and structural stability.',
      calc: 'Score = 0.20\u00D7pLDDT + 0.25\u00D7steric + 0.20\u00D7strain + 0.10\u00D7freedom + 0.15\u00D7electro + 0.10\u00D7stability. The traffic light derives from clashes, strain, prescan freedom, and backbone RMSD.',
      interpret: 'High (\u226570): phosphate fits well. Moderate (40\u201369): some issues but plausible. Low (<40): significant steric or environmental problems. Click the Rotamer Scan button to see the full 360\u00B0 clash profile.'
    }
  };
  Object.keys(tips).forEach(function(id) {
    var icon = document.getElementById(id);
    if (!icon) return;
    var info = tips[id];
    icon.addEventListener('mouseenter', function(e) {
      var tip = getTooltipEl();
      tip.innerHTML =
        '<div class="tip-title">' + info.title + '</div>' +
        '<div>' + info.desc + '</div>' +
        '<div class="tip-calc">\u2699 ' + info.calc + '</div>' +
        '<div class="tip-interpret">\u2192 ' + info.interpret + '</div>';
      tip.style.display = 'block';
      var rect = icon.getBoundingClientRect();
      var left = rect.right + 8;
      if (left + 280 > window.innerWidth) left = rect.left - 288;
      if (left < 4) left = 4;
      var top = rect.top - 8;
      if (top + 200 > window.innerHeight) top = window.innerHeight - 220;
      if (top < 4) top = 4;
      tip.style.left = left + 'px';
      tip.style.top = top + 'px';
    });
    icon.addEventListener('mouseleave', function() {
      getTooltipEl().style.display = 'none';
    });
  });
}

/* ══════════════════════════════════════
   FULLSCREEN TOGGLE
   ══════════════════════════════════════ */
var fsState = { active: null, restoreParent: null, restoreNext: null, node: null };

function _restoreFullscreenNode() {
  if (!fsState.node || !fsState.restoreParent) return;
  var host = document.getElementById('fullscreenHost');
  host.className = 'fs-host';
  if (fsState.restoreNext && fsState.restoreNext.parentNode === fsState.restoreParent) {
    fsState.restoreParent.insertBefore(fsState.node, fsState.restoreNext);
  } else {
    fsState.restoreParent.appendChild(fsState.node);
  }
  fsState.node = null;
  fsState.restoreParent = null;
  fsState.restoreNext = null;
}

function resizeAllViewers() {
  Object.keys(state.viewers).forEach(function(k) {
    try { state.viewers[k].resize(); state.viewers[k].render(); } catch(e) {}
  });
}

function fullscreenTarget(which) {
  var targets = {
    unmod: document.getElementById('unmod-card'),
    mod: document.getElementById('mod-card'),
    alignment: document.getElementById('overlay-card')
  };
  return targets[which] || null;
}

function toggleFullscreen(which) {
  var host = document.getElementById('fullscreenHost');

  if (fsState.active === which) {
    _restoreFullscreenNode();
    fsState.active = null;
  } else {
    if (fsState.active) _restoreFullscreenNode();
    var node = fullscreenTarget(which);
    if (!node) return;
    fsState.restoreParent = node.parentNode;
    fsState.restoreNext = node.nextSibling;
    fsState.node = node;
    host.className = 'fs-host active';
    host.appendChild(node);
    fsState.active = which;
  }

  setTimeout(resizeAllViewers, 50);
  setTimeout(resizeAllViewers, 250);
}
document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape' && fsState.active) toggleFullscreen(fsState.active);
  else if (e.key === 'Escape' && document.getElementById('alignmentModal').classList.contains('open')) closeAlignmentModal();
});

/* ══════════════════════════════════════
   PARSING HELPERS
   ══════════════════════════════════════ */
function _objectToLabel(obj) {
  if (obj == null) return '';
  if (typeof obj === 'string' || typeof obj === 'number' || typeof obj === 'boolean') return String(obj);
  if (Array.isArray(obj)) return obj.map(_objectToLabel).filter(Boolean).join(';');
  if (obj.label) return String(obj.label);
  if (obj.residue_label) return String(obj.residue_label);
  if (obj.partner_resname && obj.partner_chain && obj.partner_resseq != null) return String(obj.partner_resname) + ' ' + String(obj.partner_chain) + ':' + String(obj.partner_resseq) + (obj.partner_icode || '');
  if (obj.resname && obj.chain && obj.resseq != null) return String(obj.resname) + ' ' + String(obj.chain) + ':' + String(obj.resseq) + (obj.icode || '');
  if (obj.chain && obj.resno != null) return String(obj.chain) + ':' + String(obj.resno);
  try { return JSON.stringify(obj); } catch(e) { return String(obj); }
}

function asText(value) {
  if (value == null) return '';
  if (Array.isArray(value)) return value.map(_objectToLabel).filter(Boolean).join(';');
  if (typeof value === 'object') return _objectToLabel(value);
  return String(value);
}

function asCount(value) {
  if (value == null || value === '') return '-';
  if (Array.isArray(value)) return String(value.length);
  if (typeof value === 'object') {
    if (typeof value.count === 'number') return String(value.count);
    return '1';
  }
  return String(value);
}

function splitSemi(value) {
  var text = asText(value);
  if (!text || !text.trim()) return [];
  return text.split(';').map(function(s){ return String(s).trim(); }).filter(Boolean);
}

function parseResidueList(value) {
  if (Array.isArray(value)) {
    return value.map(_objectToLabel).map(function(s){ return String(s).trim(); }).filter(Boolean);
  }
  return splitSemi(value);
}

function parseSiteLabel(label) {
  var parts = String(label).split(':');
  if (parts.length === 2) return { chain: parts[0].trim(), resno: parseInt(parts[1], 10) };
  return null;
}

/**
 * Parse a contact residue identifier.
 * Handles:  "A:123"  "LYS A:123"  "A:123(LYS)"  "A:123 LYS"
 */
function parseContactId(text) {
  text = String(text).trim();
  var m = text.match(/([A-Za-z])\s*:\s*(-?\d+)/);
  if (m) return { chain: m[1], resno: parseInt(m[2], 10), label: text };
  return null;
}

/* ══════════════════════════════════════
   GEOMETRY HELPERS
   ══════════════════════════════════════ */
function atomDist(a, b) {
  var dx = a.x - b.x, dy = a.y - b.y, dz = a.z - b.z;
  return Math.sqrt(dx*dx + dy*dy + dz*dz);
}

function nearestPair(atomsA, atomsB) {
  var best = { dist: Infinity, a: null, b: null };
  for (var i = 0; i < atomsA.length; i++) {
    for (var j = 0; j < atomsB.length; j++) {
      var d = atomDist(atomsA[i], atomsB[j]);
      if (d < best.dist) best = { dist: d, a: atomsA[i], b: atomsB[j] };
    }
  }
  return best;
}

function midpoint(a, b) {
  return { x: (a.x+b.x)/2, y: (a.y+b.y)/2, z: (a.z+b.z)/2 };
}

var BACKBONE_ATOMS = { N:1, CA:1, C:1, O:1, H:1, HA:1, HA2:1, HA3:1, HN:1 };

/* ══════════════════════════════════════
   SIDEBAR
   ══════════════════════════════════════ */
function setStatus(msg) { document.getElementById('status').textContent = msg || ''; }

function updateSidebar(row, baseRow) {
  baseRow = baseRow || row;
  document.getElementById('siteMeta').textContent =
    baseRow.site_label + '  (' + baseRow.residue_name_original + ' → ' + baseRow.residue_name_modified + ')' +
    '\nViewing: PF' + state.poseIndex + (baseRow.selected_rank ? (' | selected rank: PF' + baseRow.selected_rank) : '');
  document.getElementById('overallInterpretationText').textContent = row.overall_interpretation || '-';
  document.getElementById('m_plddt_site').textContent = (row.plddt_site || '-') + (row.plddt_class ? (' (' + row.plddt_class + ')') : '');
  document.getElementById('m_plddt_window').textContent = row.plddt_window_mean || '-';
  document.getElementById('m_clashes').textContent = (row.clash_count_before || '-') + ' / ' + (row.clash_count_after || '-');
  document.getElementById('m_distances').textContent = (row.nearest_contact_distance_before || '-') + ' Å / ' + (row.nearest_contact_distance_after || '-') + ' Å';
  document.getElementById('m_electrostatic').textContent =
    (row.electrostatic_score_weighted_before || row.electrostatic_score_before || '-') + ' / ' +
    (row.electrostatic_score_weighted_after || row.electrostatic_score_after || '-');
  document.getElementById('m_salt_bridges').textContent = asCount(row.salt_bridges_before || row.salt_bridge_count_before) + ' / ' + asCount(row.salt_bridges_after || row.salt_bridge_count_after);
  document.getElementById('m_hbonds').textContent = asCount(row.hydrogen_bonds_before || row.hydrogen_bond_count_before) + ' / ' + asCount(row.hydrogen_bonds_after || row.hydrogen_bond_count_after);
  document.getElementById('m_polar_contacts').textContent = asCount(row.polar_contacts_before || row.polar_contact_count_before || row.candidate_hbond_contacts_before) + ' / ' + asCount(row.polar_contacts_after || row.polar_contact_count_after || row.candidate_hbond_contacts_after);
  document.getElementById('m_sasa').textContent = (row.sasa_unmodified || '-') + ' / ' + (row.sasa_modified || '-');
  document.getElementById('m_sasa_shared').textContent = (row.sasa_shared_atoms_before || '-') + ' / ' + (row.sasa_shared_atoms_after || '-');
  document.getElementById('m_sasa_delta').textContent = row.sasa_delta || '-';
  document.getElementById('m_neighbor_sasa_delta').textContent = row.neighbor_sasa_delta || '-';
  document.getElementById('m_local_ca_rmsd').textContent = row.local_ca_rmsd ? (row.local_ca_rmsd + ' Å') : '-';

  var conf = parseInt(row.phosphofill_confidence, 10);
  var confBadge = document.getElementById('confidenceBadge');
  var confTier = (row.confidence_tier || 'unknown').toLowerCase();
  confBadge.textContent = isNaN(conf) ? '?' : conf;
  confBadge.className = 'confidence-badge tier-' + confTier;
  document.getElementById('confidenceTier').textContent = isNaN(conf) ? 'Not available' : ('PF' + state.poseIndex + ' ' + confTier.charAt(0).toUpperCase() + confTier.slice(1) + ' confidence');
  document.getElementById('confidenceDetail').textContent = isNaN(conf) ? '' : ('Score ' + conf + '/100' + (row._pose_path ? (' | ' + String(row._pose_path).split('/').pop()) : ''));

  var pqLabel = (row.phospho_quality_label || 'unknown').toLowerCase();
  var dot = document.getElementById('trafficDot');
  dot.className = 'traffic-dot ' + pqLabel;
  var labelMap = { green:'Well accommodated', amber:'Partially accommodated', red:'Poorly accommodated', unknown:'Unknown' };
  document.getElementById('trafficLabel').textContent = labelMap[pqLabel] || pqLabel;
  document.getElementById('trafficLabel').style.color = { green:'#059669', amber:'#b45309', red:'#dc2626' }[pqLabel] || 'var(--muted)';

  var hasPrescan = baseRow.prescan_n_total_steps && parseInt(baseRow.prescan_n_total_steps, 10) > 0;
  document.getElementById('prescanBtn').style.display = hasPrescan ? 'inline-block' : 'none';
  document.getElementById('m_exposure').textContent = (row.exposure_class_unmodified || '-') + ' / ' + (row.exposure_class_modified || '-');

  var sbDetailsEl = document.getElementById('saltBridgeDetails');
  var sbDetailsText = asText(row.salt_bridge_details_after);
  if (sbDetailsText && sbDetailsText.trim()) {
    sbDetailsEl.style.display = 'block';
    sbDetailsEl.textContent = 'Salt bridges after: ' + sbDetailsText;
  } else { sbDetailsEl.style.display = 'none'; }

  var beforeResidues = parseResidueList(row.nearby_contact_residues_before);
  var afterResidues  = parseResidueList(row.nearby_contact_residues_after);
  document.getElementById('m_contacts_count').textContent = beforeResidues.length + ' / ' + afterResidues.length;
  document.getElementById('m_cb_neighborhood').textContent = (row.cb_neighborhood_before || '-') + ' / ' + (row.cb_neighborhood_after || '-');

  var atomicBeforeSet = {}; var atomicAfterSet = {}; beforeResidues.forEach(function(r){atomicBeforeSet[r]=true;}); afterResidues.forEach(function(r){atomicAfterSet[r]=true;});
  function parseCbNeighList(value) { return splitSemi(value).map(function(s){ s=String(s).trim(); if(!s) return null; var m=s.match(/^(.+?)\s+([\d.]+)A$/); if(m) return {label:m[1].trim(), dist:m[2]}; return {label:s, dist:'?'}; }).filter(Boolean); }
  var cbNeighBefore = parseCbNeighList(row.cb_neighborhood_residues_before);
  var cbNeighAfter = parseCbNeighList(row.cb_neighborhood_residues_after);
  var cbNeighMap = {}; cbNeighBefore.forEach(function(n){ cbNeighMap[n.label] = { label:n.label, distBefore:n.dist, distAfter:null }; }); cbNeighAfter.forEach(function(n){ if (cbNeighMap[n.label]) cbNeighMap[n.label].distAfter=n.dist; else cbNeighMap[n.label] = { label:n.label, distBefore:null, distAfter:n.dist }; });
  var cbEl = document.getElementById('cbNeighborhoodDetails'); var cbKeys = Object.keys(cbNeighMap);
  if (cbKeys.length > 0) {
    cbKeys.sort(function(a,b){ var da = cbNeighMap[a].distAfter || cbNeighMap[a].distBefore || '99'; var db = cbNeighMap[b].distAfter || cbNeighMap[b].distBefore || '99'; return parseFloat(da)-parseFloat(db); });
    var cbHtml = '<div style="margin-bottom:4px;font-weight:700;font-size:12px;">CB neighborhood (8\u00C5) \u2014 ' + cbKeys.length + ' residues</div>';
    cbKeys.forEach(function(label){ var n=cbNeighMap[label]; var inBefore=atomicBeforeSet[label]; var inAfter=atomicAfterSet[label]; var color,tag; if(inBefore&&inAfter){color='#7c3aed';tag='maintained';} else if(inBefore&&!inAfter){color='#d97706';tag='lost';} else if(!inBefore&&inAfter){color='#059669';tag='gained';} else {color='#6b7280';tag='neighbor';} var distParts=[]; if(n.distBefore) distParts.push(n.distBefore+'\u00C5 before'); if(n.distAfter) distParts.push(n.distAfter+'\u00C5 after'); if(n.distBefore&&n.distAfter){ var delta=(parseFloat(n.distAfter)-parseFloat(n.distBefore)).toFixed(2); var sign = delta >= 0 ? '+' : ''; distParts.push('\u0394'+sign+delta+'\u00C5'); } cbHtml += '<div style="display:flex;align-items:baseline;gap:6px;margin:2px 0;"><span style="color:'+color+';font-weight:600;font-size:12px;">'+label+'</span><span style="font-size:10px;color:'+color+';opacity:0.7;">('+tag+')</span></div>'; if (distParts.length>0) cbHtml += '<div style="margin-left:12px;font-size:11px;color:#6b7280;">'+distParts.join(' | ')+'</div>'; });
    cbEl.innerHTML = cbHtml; cbEl.style.display='block';
  } else cbEl.style.display='none';

  var cbBefore={}, cbAfter={}; splitSemi(row.cb_contact_distances_before).forEach(function(s){ s=String(s).trim(); if(!s) return; var m=s.match(/(\S+)\s+(\S+:\d+)\s+([\d.]+)A/); if(m) cbBefore[m[1]+' '+m[2]] = m[3]; }); splitSemi(row.cb_contact_distances_after).forEach(function(s){ s=String(s).trim(); if(!s) return; var m=s.match(/(\S+)\s+(\S+:\d+)\s+([\d.]+)A/); if(m) cbAfter[m[1]+' '+m[2]] = m[3]; });
  var lost = beforeResidues.filter(function(r){return !atomicAfterSet[r];}); var gained = afterResidues.filter(function(r){return !atomicBeforeSet[r];}); var shared = beforeResidues.filter(function(r){return atomicAfterSet[r];});
  function cbTag(label, mapBefore, mapAfter) { var b=mapBefore[label], a=mapAfter[label]; if(!b&&!a) return ''; var parts=[]; if(b) parts.push('CB '+b+'\u00C5 before'); if(a) parts.push('CB '+a+'\u00C5 after'); if(b&&a){ var delta=(parseFloat(a)-parseFloat(b)).toFixed(2); var sign = delta >= 0 ? '+' : ''; parts.push('\u0394'+sign+delta+'\u00C5'); } return '<div style="margin-left:24px;font-size:11px;color:#6b7280;">'+parts.join(' | ')+'</div>'; }
  var html=''; html += '<div style="margin-bottom:4px;"><strong>'+baseRow.site_label+'</strong> ('+baseRow.residue_name_original+' \u2192 '+baseRow.residue_name_modified+') | Viewing PF'+state.poseIndex+'</div>'; html += '<div style="margin-bottom:4px;">Nearest distance: <strong>'+(row.nearest_contact_distance_before || '-')+' \u00C5</strong> (before) / <strong>'+(row.nearest_contact_distance_after || '-')+' \u00C5</strong> (after)</div>';
  if(lost.length>0){ html += '<div style="margin:6px 0 2px 0;color:#d97706;font-weight:700;">\u25CF Lost contacts ('+lost.length+')</div>'; lost.forEach(function(r){ html += '<div style="margin-left:12px;color:#d97706;">'+r+'</div>' + cbTag(r,cbBefore,cbAfter); }); }
  if(gained.length>0){ html += '<div style="margin:6px 0 2px 0;color:#059669;font-weight:700;">\u25CF Gained contacts ('+gained.length+')</div>'; gained.forEach(function(r){ html += '<div style="margin-left:12px;color:#059669;">'+r+'</div>' + cbTag(r,cbBefore,cbAfter); }); }
  if(shared.length>0){ html += '<div style="margin:6px 0 2px 0;color:#7c3aed;font-weight:700;">\u25CF Maintained contacts ('+shared.length+')</div>'; shared.forEach(function(r){ html += '<div style="margin-left:12px;color:#7c3aed;">'+r+'</div>' + cbTag(r,cbBefore,cbAfter); }); }
  if(lost.length===0 && gained.length===0 && shared.length===0){ html += '<div style="color:#6b7280;">No contact residues reported for this site.</div>'; }
  if(beforeResidues.length>0 || afterResidues.length>0){ html += '<div style="margin-top:6px;padding-top:4px;border-top:1px solid #e5e7eb;font-size:11px;color:#6b7280;">Total: '+beforeResidues.length+' before, '+afterResidues.length+' after'; if(lost.length>0) html += ' | '+lost.length+' lost'; if(gained.length>0) html += ' | '+gained.length+' gained'; if(shared.length>0) html += ' | '+shared.length+' maintained'; html += '</div>'; }
  document.getElementById('contactDetails').innerHTML = html;

  var flags = splitSemi(row.interpretation_flags); var ul = document.getElementById('flagList'); ul.innerHTML=''; flags.forEach(function(f){ var li=document.createElement('li'); li.textContent=f; ul.appendChild(li); });

  document.getElementById('fileBox').textContent = 'Unmodified: ' + FILES.unmodified + '\nPF1: ' + (FILES.pf1 || '-') + '\nPF2: ' + (FILES.pf2 || '-') + '\nPF3: ' + (FILES.pf3 || '-') + '\nSelected: ' + (FILES.modified || '-') + '\nSelection JSON: ' + (FILES.selection_json || '-');
}

function fillSelector() {
  var sel = document.getElementById('siteSelect'); sel.innerHTML = '';
  REPORT.sites.forEach(function(row, i) {
    var opt = document.createElement('option');
    opt.value = String(i);
    var conf = row.phosphofill_confidence;
    var confStr = conf ? (' [' + conf + '/100]') : '';
    opt.textContent = row.site_label + confStr + '  |  ' + row.overall_interpretation;
    sel.appendChild(opt);
  });
  sel.value = String(state.index);
}

/* ══════════════════════════════════════
   CONTACT CATEGORIZATION
   ══════════════════════════════════════ */
function categorizeContacts(row) {
  var before = parseResidueList(row.nearby_contact_residues_before).map(parseContactId).filter(Boolean);
  var after  = parseResidueList(row.nearby_contact_residues_after).map(parseContactId).filter(Boolean);

  var beforeMap = {}, afterMap = {};
  before.forEach(function(r) { beforeMap[r.chain + ':' + r.resno] = r; });
  after.forEach(function(r)  { afterMap[r.chain + ':' + r.resno]  = r; });

  var lost = before.filter(function(r) { return !afterMap[r.chain + ':' + r.resno]; });
  var gained = after.filter(function(r) { return !beforeMap[r.chain + ':' + r.resno]; });
  var maintained = before.filter(function(r) { return !!afterMap[r.chain + ':' + r.resno]; });

  lost.forEach(function(r) { r.color = COLORS.contactLost; r.category = 'lost'; });
  gained.forEach(function(r) { r.color = COLORS.contactGained; r.category = 'gained'; });
  maintained.forEach(function(r) { r.color = COLORS.contactMaintained; r.category = 'maintained'; });

  return { lost: lost, gained: gained, maintained: maintained };
}

/* ══════════════════════════════════════
   3Dmol DRAWING — core contact renderer
   ══════════════════════════════════════ */

/**
 * Draw the phosphosite + a list of contact residues + distance dashes.
 *
 * @param {object} viewer     3Dmol viewer
 * @param {number} modelIdx   model index (0 for single panels, 0/1 for overlay)
 * @param {object} site       { chain, resno }
 * @param {array}  contacts   [{ chain, resno, label, color, category }, ...]
 * @param {string} mode       'residue' | 'sidechain' | 'atomic'
 */
function drawContacts(viewer, modelIdx, site, contacts, mode) {
  var model = viewer.getModel(modelIdx);
  if (!model) return;

  /* ── Phosphosite sticks ── */
  var siteSel = { model: modelIdx, chain: site.chain, resi: site.resno };
  if (mode === 'sidechain') {
    viewer.addStyle(
      Object.assign({}, siteSel, { not: { atom: ['N','CA','C','O'] } }),
      { stick: { color: COLORS.siteRed, radius: 0.18 } }
    );
  } else {
    viewer.addStyle(siteSel, { stick: { color: COLORS.siteRed, radius: 0.18 } });
  }

  /* Site label at CA */
  var siteCAs = model.selectedAtoms({ chain: site.chain, resi: site.resno, atom: 'CA' });
  if (siteCAs.length > 0) {
    viewer.addLabel(site.chain + ':' + site.resno, {
      position: siteCAs[0], fontSize: 11, fontColor: COLORS.siteRed,
      backgroundColor: 'rgba(255,255,255,0.85)', showBackground: true,
      borderColor: COLORS.siteRed, borderThickness: 1
    });
  }

  /* Heavy atoms of the phosphosite (for distance calc) */
  var siteAtoms = model.selectedAtoms({ chain: site.chain, resi: site.resno })
    .filter(function(a) { return a.elem !== 'H'; });

  /* ── Each contact residue ── */
  contacts.forEach(function(c) {
    var cSel = { model: modelIdx, chain: c.chain, resi: c.resno };

    /* Stick representation */
    if (mode === 'sidechain') {
      viewer.addStyle(
        Object.assign({}, cSel, { not: { atom: ['N','CA','C','O'] } }),
        { stick: { color: c.color, radius: 0.14 } }
      );
    } else if (mode === 'atomic') {
      /* In atomic mode we start with thin sticks, then highlight nearest atoms */
      viewer.addStyle(cSel, { stick: { color: c.color, radius: 0.06, opacity: 0.4 } });
    } else {
      viewer.addStyle(cSel, { stick: { color: c.color, radius: 0.14 } });
    }

    /* Nearest-atom pair & distance dash */
    var cAtoms = model.selectedAtoms({ chain: c.chain, resi: c.resno })
      .filter(function(a) { return a.elem !== 'H'; });
    var pair = nearestPair(siteAtoms, cAtoms);

    if (pair.a && pair.b) {
      /* In atomic mode, highlight the two nearest atoms as spheres */
      if (mode === 'atomic') {
        viewer.addStyle(
          { model: modelIdx, serial: pair.b.serial },
          { sphere: { color: c.color, radius: 0.4 } }
        );
        viewer.addStyle(
          { model: modelIdx, serial: pair.a.serial },
          { sphere: { color: COLORS.siteRed, radius: 0.4 } }
        );
      }

      /* Dashed cylinder between nearest atoms */
      viewer.addCylinder({
        start: { x: pair.a.x, y: pair.a.y, z: pair.a.z },
        end:   { x: pair.b.x, y: pair.b.y, z: pair.b.z },
        radius: 0.04, color: c.color,
        fromCap: 1, toCap: 1,
        dashed: true, dashLength: 0.2, gapLength: 0.12
      });

      /* Distance label at midpoint */
      var mid = midpoint(pair.a, pair.b);
      viewer.addLabel(pair.dist.toFixed(1) + '\u00C5', {
        position: mid, fontSize: 10, fontColor: '#ffffff',
        backgroundColor: c.color, showBackground: true,
        backgroundOpacity: 0.85, borderThickness: 0, inFront: true
      });
    }

    /* Residue name label at CA */
    var cCAs = model.selectedAtoms({ chain: c.chain, resi: c.resno, atom: 'CA' });
    if (cCAs.length > 0) {
      viewer.addLabel(c.label, {
        position: cCAs[0], fontSize: 10, fontColor: c.color,
        backgroundColor: 'rgba(255,255,255,0.85)', showBackground: true,
        borderColor: c.color, borderThickness: 1
      });
    }
  });
}

/**
 * Build a zoom selection encompassing the site + its contacts.
 */
function buildZoomSel(site, contacts, modelIdx) {
  var sels = [{ model: modelIdx, chain: site.chain, resi: site.resno }];
  contacts.forEach(function(c) {
    sels.push({ model: modelIdx, chain: c.chain, resi: c.resno });
  });
  return sels.length === 1 ? sels[0] : { or: sels };
}

/* ══════════════════════════════════════
   PANEL RENDERERS
   ══════════════════════════════════════ */

/**
 * Unmodified panel.
 *   Primary contacts: lost (orange) + maintained (purple) — these were the before-contacts.
 *   Ghost context: gained (green, faint) — shows where future contacts will form.
 */
function renderUnmodPanel(site, cat) {
  var v = state.viewers.unmod;
  v.removeAllShapes(); v.removeAllLabels();
  v.setStyle({}, { cartoon: { color: COLORS.unmodCartoon, opacity: 0.85 } });

  var primary = cat.lost.concat(cat.maintained);
  drawContacts(v, 0, site, primary, state.displayMode);

  /* Gained as ghost context */
  cat.gained.forEach(function(c) {
    v.addStyle(
      { chain: c.chain, resi: c.resno },
      { stick: { color: COLORS.contactGained, radius: 0.07, opacity: 0.25 } }
    );
  });

  v.zoomTo(buildZoomSel(site, primary.concat(cat.gained), 0));
  v.render();
}

/**
 * Modified panel.
 *   Primary contacts: gained (green) + maintained (purple) — these are the after-contacts.
 *   Ghost context: lost (orange, faint) — shows where old contacts used to be.
 */
function renderModPanel(site, cat) {
  var v = state.viewers.mod;
  v.removeAllShapes(); v.removeAllLabels();
  v.setStyle({}, { cartoon: { color: COLORS.modCartoon, opacity: 0.85 } });

  var primary = cat.gained.concat(cat.maintained);
  drawContacts(v, 0, site, primary, state.displayMode);

  /* Lost as ghost context */
  cat.lost.forEach(function(c) {
    v.addStyle(
      { chain: c.chain, resi: c.resno },
      { stick: { color: COLORS.contactLost, radius: 0.07, opacity: 0.25 } }
    );
  });

  v.zoomTo(buildZoomSel(site, primary.concat(cat.lost), 0));
  v.render();
}

/**
 * Overlay panel — both structures, all contact categories.
 *   Model 0 = unmodified (grey cartoon).
 *   Model 1 = modified (blue cartoon).
 *   Lost contacts drawn from model 0 (they existed before, not after).
 *   Gained + maintained drawn from model 1 (current state).
 */
function renderOverlayPanel(site, cat) {
  var v = state.viewers.overlay;
  v.removeAllShapes(); v.removeAllLabels();
  v.setStyle({ model: 0 }, { cartoon: { color: COLORS.unmodCartoon, opacity: 0.55 } });
  v.setStyle({ model: 1 }, { cartoon: { color: COLORS.modCartoon, opacity: 0.55 } });

  /* Lost from model 0 */
  if (cat.lost.length > 0) {
    drawContacts(v, 0, site, cat.lost, state.displayMode);
  }

  /* Gained + maintained from model 1 */
  var afterContacts = cat.gained.concat(cat.maintained);
  if (afterContacts.length > 0) {
    drawContacts(v, 1, site, afterContacts, state.displayMode);
  }

  /* Also show the site from both models */
  v.addStyle({ model: 0, chain: site.chain, resi: site.resno },
    { stick: { color: COLORS.siteRed, radius: 0.14, opacity: 0.5 } });
  v.addStyle({ model: 1, chain: site.chain, resi: site.resno },
    { stick: { color: COLORS.siteRed, radius: 0.18 } });

  /* Zoom to encompass everything */
  var allContacts = cat.lost.concat(cat.gained).concat(cat.maintained);
  var sels = [
    { model: 0, chain: site.chain, resi: site.resno },
    { model: 1, chain: site.chain, resi: site.resno }
  ];
  allContacts.forEach(function(c) {
    sels.push({ chain: c.chain, resi: c.resno });
  });
  v.zoomTo({ or: sels });
  v.render();
}

/* ══════════════════════════════════════
   SITE HIGHLIGHTING (entry point)
   ══════════════════════════════════════ */
function highlightSite(row) {
  var site = parseSiteLabel(row.site_label);
  if (!site) return;
  var cat = categorizeContacts(row);
  renderUnmodPanel(site, cat);
  renderModPanel(site, cat);
  renderOverlayPanel(site, cat);
}

function refreshCurrentSite() {
  var baseRow = currentBaseRow();
  var row = currentDisplayRow();
  if (!row || !baseRow) return;
  document.getElementById('siteSelect').value = String(state.index);
  setStatus('Highlighting ' + baseRow.site_label + ' (PF' + state.poseIndex + ')...');
  try { loadPoseModels(); updateSidebar(row, baseRow); highlightSite(row); } catch(e) { console.warn('highlight error:', e); setStatus('ERROR: ' + e.message); return; }
  setStatus('Selected: ' + baseRow.site_label + ' | PF' + state.poseIndex + ' | ' + (row.overall_interpretation || ''));
}

function nextSite(delta) {
  var n = REPORT.sites.length;
  state.index = (state.index + delta + n) % n;
  refreshCurrentSite();
}

function openAlignmentModal() {
  var modal = document.getElementById('alignmentModal');
  modal.classList.add('open');
  state.alignmentMode = true;
  var btn = document.getElementById('showAlignmentBtn');
  if (btn) btn.textContent = 'Alignment open';

  var row = currentDisplayRow();
  if (row && state.viewers.overlay) {
    var site = parseSiteLabel(row.site_label);
    if (site) renderOverlayPanel(site, categorizeContacts(row));
  }
  setTimeout(resizeAllViewers, 50);
  setTimeout(resizeAllViewers, 250);
}

function closeAlignmentModal() {
  if (fsState.active === 'alignment') {
    _restoreFullscreenNode();
    fsState.active = null;
  }
  document.getElementById('alignmentModal').classList.remove('open');
  state.alignmentMode = false;
  var btn = document.getElementById('showAlignmentBtn');
  if (btn) btn.textContent = 'View alignment';
  setTimeout(resizeAllViewers, 50);
}

/* ══════════════════════════════════════
   PRESCAN ANIMATION MODAL
   ══════════════════════════════════════ */

function openPrescanModal() {
  var row = REPORT.sites[state.index];
  if (!row) return;
  var siteKey = row.site_label;
  var siteData = state.prescanFrames[siteKey];

  /* Handle both old format (array) and new format (bundle with neighbors) */
  var frames, neighbors, residueName;
  if (!siteData) {
    alert('No prescan frame data available for ' + siteKey + '.\n\nTo enable the rotamer scan animation:\n1. Re-run the grafting with graft_phospho_openmm_v2.py (generates .prescan_frames.json)\n2. Re-run the viz script with: --prescan-frames <path_to_prescan_frames.json>');
    return;
  }
  if (Array.isArray(siteData)) {
    /* Old format: just an array of frames */
    frames = siteData;
    neighbors = [];
    residueName = row.residue_name_modified || '?';
  } else {
    /* New bundle format */
    frames = siteData.frames || [];
    neighbors = siteData.neighbors || [];
    residueName = siteData.residue || row.residue_name_modified || '?';
  }
  if (frames.length === 0) {
    alert('No frames in prescan data for ' + siteKey);
    return;
  }

  state.prescanIndex = 0;
  state._prescanFrames = frames;
  state._prescanNeighbors = neighbors;
  state._prescanResidue = residueName;
  state._prescanSiteLabel = siteKey;
  document.getElementById('prescanTitle').textContent =
    '360\u00B0 Rotamer Scan \u2014 ' + siteKey + ' (' + residueName + ')';
  document.getElementById('prescanModal').classList.add('open');
  drawPrescanSchematic(frames, neighbors, 0, residueName);
  updatePrescanFrame2(frames, 0);
  renderPrescanStats(row, frames);
}

function closePrescanModal() {
  document.getElementById('prescanModal').classList.remove('open');
  if (state.prescanTimer) { clearInterval(state.prescanTimer); state.prescanTimer = null; }
  state.prescanPlaying = false;
  var playBtn = document.getElementById('psPlay');
  if (playBtn) playBtn.textContent = '\u25B6 Play';
}

function updatePrescanFrame2(frames, idx) {
  var f = frames[idx];
  if (!f) return;
  var total = frames.length;
  document.getElementById('psStepLabel').textContent =
    f.angle + '\u00B0  (' + (idx + 1) + '/' + total + ')';

  /* Frame info with contacts */
  var clashColor = f.n_clashing === 0 ? '#059669' : f.n_clashing <= 2 ? '#d97706' : '#dc2626';
  var html = '<span style="color:' + clashColor + ';font-weight:700;">' + f.n_clashing + ' clashing atoms</span>';
  html += ' &nbsp;|&nbsp; clash: ' + f.clash_score.toFixed(2);
  html += ' &nbsp;|&nbsp; contacts: ' + f.contact_bonus.toFixed(2);
  html += ' &nbsp;|&nbsp; total: <strong>' + f.total_score.toFixed(2) + '</strong>';
  if (f.contacts && f.contacts.length > 0) {
    html += '<div style="margin-top:6px;font-size:11px;">';
    f.contacts.slice(0, 8).forEach(function(c) {
      var col = c.clash ? '#dc2626' : (c.dist < 3.5 ? '#059669' : '#6b7280');
      var tag = c.clash ? 'CLASH' : (c.dist < 3.5 ? 'contact' : 'nearby');
      html += '<span style="color:' + col + ';">' + c.res + ' ' + c.n_atom + '\u2194' + c.po3 + ' ' + c.dist + '\u00C5 <em>(' + tag + ')</em></span> &nbsp; ';
    });
    html += '</div>';
  }
  document.getElementById('psFrameInfo').innerHTML = html;

  /* Redraw schematic */
  drawPrescanSchematic(state._prescanFrames, state._prescanNeighbors, idx, state._prescanResidue);
}

function prescanStep(delta) {
  var frames = state._prescanFrames;
  if (!frames || frames.length === 0) return;
  state.prescanIndex = (state.prescanIndex + delta + frames.length) % frames.length;
  updatePrescanFrame2(frames, state.prescanIndex);
}

function togglePrescanPlay() {
  var frames = state._prescanFrames;
  if (!frames || frames.length === 0) return;
  var playBtn = document.getElementById('psPlay');
  if (state.prescanPlaying) {
    clearInterval(state.prescanTimer); state.prescanTimer = null;
    state.prescanPlaying = false;
    playBtn.textContent = '\u25B6 Play';
  } else {
    state.prescanPlaying = true;
    playBtn.textContent = '\u23F8 Pause';
    state.prescanTimer = setInterval(function() {
      prescanStep(1);
      if (state.prescanIndex === 0 && state.prescanPlaying) {
        clearInterval(state.prescanTimer); state.prescanTimer = null;
        state.prescanPlaying = false;
        playBtn.textContent = '\u25B6 Play';
      }
    }, 500);
  }
}

function renderPrescanStats(row, frames) {
  var nZero = parseInt(row.prescan_n_zero_clash || '0', 10);
  var nTotal = parseInt(row.prescan_n_total_steps || frames.length, 10);
  var arc = row.prescan_zero_clash_arc || '0';
  var pct = nTotal > 0 ? Math.round(100 * nZero / nTotal) : 0;
  var html = '';
  html += '<div class="prescan-stat"><div class="ps-val">' + nZero + '/' + nTotal + '</div><div class="ps-label">Zero-clash orientations</div></div>';
  html += '<div class="prescan-stat"><div class="ps-val">' + pct + '%</div><div class="ps-label">Clash-free fraction</div></div>';
  html += '<div class="prescan-stat"><div class="ps-val">' + arc + '\u00B0</div><div class="ps-label">Largest clash-free arc</div></div>';
  document.getElementById('psStats').innerHTML = html;
}

function drawResidueBond(ctx, p1, p2, width, color) {
  ctx.beginPath();
  ctx.moveTo(p1[0], p1[1]);
  ctx.lineTo(p2[0], p2[1]);
  ctx.strokeStyle = color || '#9ca3af';
  ctx.lineWidth = width || 4;
  ctx.lineCap = 'round';
  ctx.stroke();
}

function drawResidueAtom(ctx, pos, label, radius, fill) {
  ctx.beginPath();
  ctx.arc(pos[0], pos[1], radius, 0, Math.PI * 2);
  ctx.fillStyle = fill || '#cbd5e1';
  ctx.fill();
  ctx.strokeStyle = '#ffffff';
  ctx.lineWidth = 1;
  ctx.stroke();
  if (label) {
    ctx.fillStyle = '#334155';
    ctx.font = 'bold 8px Arial';
    ctx.textAlign = 'center';
    ctx.fillText(label, pos[0], pos[1] + 3);
  }
}

function drawParentResidueSchematic(ctx, cx, cy, residueName) {
  var greyBond = '#9ca3af';
  var greyAtom = '#d1d5db';
  var darkText = '#475569';
  var O = [cx, cy];
  function pt(dx, dy) { return [cx + dx, cy + dy]; }

  if (residueName === 'SEP' || residueName === 'SER') {
    var CB = pt(-28, 18), CA = pt(-56, 34);
    drawResidueBond(ctx, O, CB, 5, greyBond);
    drawResidueBond(ctx, CB, CA, 5, greyBond);
    drawResidueAtom(ctx, O, 'OG', 7, greyAtom);
    drawResidueAtom(ctx, CB, 'CB', 7, greyAtom);
    drawResidueAtom(ctx, CA, 'CA', 7, greyAtom);
    ctx.fillStyle = darkText; ctx.font = '11px Arial'; ctx.textAlign = 'center';
    ctx.fillText('Ser sidechain', cx - 48, cy + 56);
    return;
  }

  if (residueName === 'TPO' || residueName === 'THR') {
    var CB = pt(-30, 8), CA = pt(-58, -8), CG2 = pt(-52, 34);
    drawResidueBond(ctx, O, CB, 5, greyBond);
    drawResidueBond(ctx, CB, CA, 5, greyBond);
    drawResidueBond(ctx, CB, CG2, 5, greyBond);
    drawResidueAtom(ctx, O, 'OG1', 7, greyAtom);
    drawResidueAtom(ctx, CB, 'CB', 7, greyAtom);
    drawResidueAtom(ctx, CA, 'CA', 7, greyAtom);
    drawResidueAtom(ctx, CG2, 'CG2', 7, greyAtom);
    ctx.fillStyle = darkText; ctx.font = '11px Arial'; ctx.textAlign = 'center';
    ctx.fillText('Thr sidechain', cx - 48, cy + 56);
    return;
  }

  if (residueName === 'PTR' || residueName === 'TYR') {
    var CZ = pt(-26, 0), CE1 = pt(-46, -12), CD1 = pt(-66, -2), CG = pt(-66, 22), CD2 = pt(-46, 34), CE2 = pt(-26, 24);
    drawResidueBond(ctx, O, CZ, 5, greyBond);
    drawResidueBond(ctx, CZ, CE1, 4, greyBond);
    drawResidueBond(ctx, CE1, CD1, 4, greyBond);
    drawResidueBond(ctx, CD1, CG, 4, greyBond);
    drawResidueBond(ctx, CG, CD2, 4, greyBond);
    drawResidueBond(ctx, CD2, CE2, 4, greyBond);
    drawResidueBond(ctx, CE2, CZ, 4, greyBond);
    drawResidueAtom(ctx, O, 'OH', 7, greyAtom);
    [CZ, CE1, CD1, CG, CD2, CE2].forEach(function(pos) { drawResidueAtom(ctx, pos, '', 5.5, greyAtom); });
    ctx.fillStyle = darkText; ctx.font = '11px Arial'; ctx.textAlign = 'center';
    ctx.fillText('Tyr sidechain', cx - 48, cy + 56);
    return;
  }

  drawResidueAtom(ctx, O, '', 7, greyAtom);
}

/* ── 2D Residue + PO₃ schematic (canvas) ── */
function drawPrescanSchematic(frames, neighbors, highlightIndex, residueName) {
  var canvas = document.getElementById('polarCanvas');
  var ctx = canvas.getContext('2d');
  var w = canvas.width, h = canvas.height;
  var cx = w / 2, cy = h / 2;
  ctx.clearRect(0, 0, w, h);

  var f = frames[highlightIndex];
  if (!f) return;

  /* Find best frame for star marker */
  var bestIdx = 0, bestScore = Infinity;
  frames.forEach(function(fr, i) {
    if (fr.total_score < bestScore) { bestScore = fr.total_score; bestIdx = i; }
  });

  /* Scale: find max extent of PO3 2d coords + neighbors to fit canvas */
  var maxExtent = 3.0;
  if (f.po3_2d) {
    Object.values(f.po3_2d).forEach(function(xy) {
      maxExtent = Math.max(maxExtent, Math.abs(xy[0]), Math.abs(xy[1]));
    });
  }
  neighbors.forEach(function(n) {
    maxExtent = Math.max(maxExtent, Math.abs(n.x), Math.abs(n.y));
  });
  var scale = (Math.min(cx, cy) - 50) / (maxExtent * 1.2);

  function toCanvas(x2d, y2d) {
    return [cx + x2d * scale, cy - y2d * scale];
  }

  /* ── Draw faint angle ring ── */
  ctx.strokeStyle = '#e2e8f0'; ctx.lineWidth = 0.5;
  ctx.beginPath(); ctx.arc(cx, cy, Math.min(cx, cy) - 40, 0, Math.PI * 2); ctx.stroke();

  /* ── Draw neighbor residues ── */
  var neighborPositions = {};
  neighbors.forEach(function(n) {
    var pos = toCanvas(n.x, n.y);
    neighborPositions[n.label] = pos;

    /* Circle */
    ctx.beginPath();
    ctx.arc(pos[0], pos[1], 20, 0, Math.PI * 2);
    ctx.fillStyle = '#f1f5f9';
    ctx.strokeStyle = '#94a3b8';
    ctx.lineWidth = 1.5;
    ctx.fill(); ctx.stroke();

    /* Label */
    ctx.fillStyle = '#334155';
    ctx.font = 'bold 10px Arial';
    ctx.textAlign = 'center';
    ctx.fillText(n.short, pos[0], pos[1] + 3);
  });

  /* ── Draw parent residue schematic at attachment point ── */
  drawParentResidueSchematic(ctx, cx, cy, residueName);

  /* Residue label at center-top */
  ctx.fillStyle = '#475569'; ctx.font = '11px Arial'; ctx.textAlign = 'center';
  ctx.fillText(residueName, cx, cy - 14);

  /* ── Draw PO3 group ── */
  if (f.po3_2d) {
    var po3keys = Object.keys(f.po3_2d);
    var pPos = f.po3_2d['P'] ? toCanvas(f.po3_2d['P'][0], f.po3_2d['P'][1]) : null;

    /* Bond from origin to P */
    if (pPos) {
      ctx.beginPath();
      ctx.moveTo(cx, cy); ctx.lineTo(pPos[0], pPos[1]);
      ctx.strokeStyle = '#475569'; ctx.lineWidth = 2; ctx.stroke();
    }

    /* Draw O atoms and bonds from P */
    po3keys.forEach(function(name) {
      var xy = f.po3_2d[name];
      var pos = toCanvas(xy[0], xy[1]);

      if (name !== 'P' && pPos) {
        /* Bond P -> O */
        ctx.beginPath();
        ctx.moveTo(pPos[0], pPos[1]); ctx.lineTo(pos[0], pos[1]);
        ctx.strokeStyle = '#475569'; ctx.lineWidth = 1.5; ctx.stroke();
      }

      /* Atom circle */
      var radius = name === 'P' ? 10 : 7;
      var color = name === 'P' ? '#f97316' : '#ef4444';
      ctx.beginPath();
      ctx.arc(pos[0], pos[1], radius, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.fill();
      ctx.strokeStyle = '#fff'; ctx.lineWidth = 1; ctx.stroke();

      /* Atom label */
      ctx.fillStyle = '#fff'; ctx.font = 'bold 8px Arial'; ctx.textAlign = 'center';
      ctx.fillText(name, pos[0], pos[1] + 3);
    });

    /* ── Draw contact/clash lines to neighbors ── */
    if (f.contacts) {
      /* Group contacts by neighbor: keep shortest per neighbor */
      var bestContact = {};
      f.contacts.forEach(function(c) {
        if (!bestContact[c.res] || c.dist < bestContact[c.res].dist) {
          bestContact[c.res] = c;
        }
      });

      Object.values(bestContact).forEach(function(c) {
        var nPos = neighborPositions[c.res];
        var po3Pos = f.po3_2d[c.po3] ? toCanvas(f.po3_2d[c.po3][0], f.po3_2d[c.po3][1]) : null;
        if (!nPos || !po3Pos) return;

        /* Dashed line */
        ctx.beginPath();
        ctx.setLineDash(c.clash ? [4, 3] : [6, 4]);
        ctx.moveTo(po3Pos[0], po3Pos[1]);
        ctx.lineTo(nPos[0], nPos[1]);
        ctx.strokeStyle = c.clash ? '#dc2626' : (c.dist < 3.5 ? '#059669' : '#94a3b8');
        ctx.lineWidth = c.clash ? 2 : 1.5;
        ctx.stroke();
        ctx.setLineDash([]);

        /* Distance label at midpoint */
        var mx = (po3Pos[0] + nPos[0]) / 2;
        var my = (po3Pos[1] + nPos[1]) / 2;
        ctx.fillStyle = c.clash ? '#dc2626' : (c.dist < 3.5 ? '#059669' : '#6b7280');
        ctx.font = '9px Arial'; ctx.textAlign = 'center';
        ctx.fillText(c.dist + '\u00C5', mx, my - 4);

        /* Highlight neighbor circle if clashing */
        if (c.clash) {
          ctx.beginPath();
          ctx.arc(nPos[0], nPos[1], 22, 0, Math.PI * 2);
          ctx.strokeStyle = '#dc2626'; ctx.lineWidth = 2.5; ctx.stroke();
        } else if (c.dist < 3.5) {
          ctx.beginPath();
          ctx.arc(nPos[0], nPos[1], 22, 0, Math.PI * 2);
          ctx.strokeStyle = '#059669'; ctx.lineWidth = 2; ctx.stroke();
        }
      });
    }
  } else {
    /* Fallback: old format without po3_2d — draw simple angle indicator */
    var angle = (f.angle - 90) * Math.PI / 180;
    var R = Math.min(cx, cy) - 50;
    ctx.strokeStyle = '#1e293b'; ctx.lineWidth = 2;
    ctx.beginPath(); ctx.moveTo(cx, cy);
    ctx.lineTo(cx + R * 0.6 * Math.cos(angle), cy + R * 0.6 * Math.sin(angle));
    ctx.stroke();
    ctx.fillStyle = '#f97316'; ctx.font = 'bold 12px Arial'; ctx.textAlign = 'center';
    ctx.fillText('PO\u2083', cx + R * 0.4 * Math.cos(angle), cy + R * 0.4 * Math.sin(angle));
  }

  /* ── Best orientation star ── */
  if (highlightIndex === bestIdx) {
    ctx.fillStyle = '#f59e0b'; ctx.font = 'bold 18px Arial'; ctx.textAlign = 'left';
    ctx.fillText('\u2605 best', 8, 20);
  }

  /* ── Step indicator ── */
  ctx.fillStyle = '#94a3b8'; ctx.font = '11px Arial'; ctx.textAlign = 'right';
  ctx.fillText(f.angle + '\u00B0', w - 8, 18);
}


/* ══════════════════════════════════════
   MAIN INITIALIZATION
   ══════════════════════════════════════ */
async function main() {
  setStatus('Initializing...');
  fillSelector();
  initMetricTooltips();
  initSectionTooltips();

  /* Navigation controls */
  document.getElementById('siteSelect').addEventListener('change', function(e) {
    state.index = Number(e.target.value || 0); refreshCurrentSite();
  });
  document.getElementById('prevBtn').addEventListener('click', function() { nextSite(-1); });
  document.getElementById('nextBtn').addEventListener('click', function() { nextSite(1); });
  document.getElementById('showAlignmentBtn').addEventListener('click', openAlignmentModal);
  document.getElementById('alignmentModal').addEventListener('click', function(e) {
    if (e.target === this) closeAlignmentModal();
  });
  window.addEventListener('keydown', function(e) {
    if (e.key === 'ArrowLeft') nextSite(-1);
    if (e.key === 'ArrowRight') nextSite(1);
  });

  /* Display mode toggle */
  document.querySelectorAll('#contactToggle button').forEach(function(btn) {
    btn.addEventListener('click', function() {
      document.querySelectorAll('#contactToggle button').forEach(function(b) {
        b.classList.remove('active');
      });
      btn.classList.add('active');
      state.displayMode = btn.getAttribute('data-mode');
      refreshCurrentSite();
    });
  });

  /* Candidate pose buttons */
  updateAvailablePoseButtons();
  document.querySelectorAll('.poseBtn').forEach(function(btn) {
    btn.addEventListener('click', function() {
      if (btn.disabled) return;
      var nextPose = parseInt(btn.getAttribute('data-pose'), 10);
      if (!nextPose || nextPose === state.poseIndex) return;
      state.poseIndex = nextPose;
      if (!state.viewers.mod) {
        syncPoseButtons();
        return;
      }
      refreshCurrentSite();
    });
  });

  /* Prescan modal controls */
  document.getElementById('prescanBtn').addEventListener('click', openPrescanModal);
  document.getElementById('psFirst').addEventListener('click', function() { state.prescanIndex = 0; var f = state._prescanFrames; if (f && f.length) updatePrescanFrame2(f, 0); });
  document.getElementById('psPrev').addEventListener('click', function() { prescanStep(-1); });
  document.getElementById('psNext').addEventListener('click', function() { prescanStep(1); });
  document.getElementById('psLast').addEventListener('click', function() { var f = state._prescanFrames; if (f && f.length) { state.prescanIndex = f.length - 1; updatePrescanFrame2(f, state.prescanIndex); } });
  document.getElementById('psPlay').addEventListener('click', togglePrescanPlay);
  document.getElementById('prescanModal').addEventListener('click', function(e) {
    if (e.target === this) closePrescanModal();
  });
  window.addEventListener('keydown', function(e) {
    if (e.key === 'Escape' && document.getElementById('prescanModal').classList.contains('open')) {
      closePrescanModal();
    }
  });

  /* Prescan frames: embedded by Python if available, otherwise fetched */
  /* __PRESCAN_FRAMES_INJECT__ */

  /* If no frames were embedded, the rotamer scan button stays hidden.
     Re-run the viz script with --prescan-frames to enable it. */
  if (Object.keys(state.prescanFrames).length > 0) {
    console.log('Prescan frames available for', Object.keys(state.prescanFrames).length, 'sites');
  }

  /* Show file info early (before anything that might fail) */
  document.getElementById('fileBox').textContent =
    'Unmodified: ' + FILES.unmodified +
    '\nModified: ' + FILES.modified +
    '\nReport rows: ' + REPORT.sites.length;

  /* Check that 3Dmol loaded — wait up to 5s for async fallback */
  var waitAttempts = 0;
  while (typeof $3Dmol === 'undefined' && waitAttempts < 25) {
    await new Promise(function(r) { setTimeout(r, 200); });
    waitAttempts++;
    if (waitAttempts % 5 === 0) setStatus('Waiting for 3Dmol.js to load... (' + waitAttempts * 200 + 'ms)');
  }
  if (typeof $3Dmol === 'undefined') {
    setStatus('ERROR: 3Dmol.js library failed to load from all CDNs. Check your internet connection or try reloading.');
    document.getElementById('fileBox').textContent += '\n\nTried:\n  unpkg.com/3dmol\n  cdnjs.cloudflare.com/3Dmol\n\nIf blocked, download 3Dmol-min.js locally and update the <script> tag.';
    console.error('$3Dmol is undefined after all fallbacks');
    return;
  }

  /* Create 3Dmol viewers */
  setStatus('Creating viewers...');
  var cfg = { backgroundColor: 'white' };
  try {
    state.viewers.unmod   = $3Dmol.createViewer('viewer-unmod', cfg);
    state.viewers.mod     = $3Dmol.createViewer('viewer-mod', cfg);
    state.viewers.overlay = $3Dmol.createViewer('viewer-overlay', cfg);
  } catch (err) {
    console.error('Failed to create 3Dmol viewers:', err);
    setStatus('ERROR: Could not create 3D viewers — ' + err.message);
    return;
  }

  /* Link cameras for synchronized rotation/zoom */
  var vkeys = ['unmod','mod','overlay'];
  for (var i = 0; i < vkeys.length; i++) {
    for (var j = 0; j < vkeys.length; j++) {
      if (i !== j) state.viewers[vkeys[i]].linkViewer(state.viewers[vkeys[j]]);
    }
  }

  /* Fetch structure files */
  setStatus('Loading structures...');
  try {
    var resp1 = await fetch(FILES.unmodified);
    if (!resp1.ok) throw new Error('Failed: ' + FILES.unmodified + ' (' + resp1.status + ')');
    state.cifData.unmod = await resp1.text();

    var candidateKeys = ['pf1','pf2','pf3'];
    for (var ck = 0; ck < candidateKeys.length; ck++) {
      var k = candidateKeys[ck];
      if (FILES[k]) {
        var resp = await fetch(FILES[k]);
        if (!resp.ok) throw new Error('Failed: ' + FILES[k] + ' (' + resp.status + ')');
        state.cifData[k] = await resp.text();
      }
    }
    state.cifData.mod = state.cifData[currentPoseKey()] || state.cifData.pf1 || '';
  } catch (err) {
    console.error(err);
    setStatus('Error loading structures: ' + err.message + '. Make sure all CIF/PDB files are in the same directory as this HTML.');
    return;
  }

  /* Add models to viewers — auto-detect format */
  setStatus('Building molecular models...');
  var fmt = FILES.unmodified.match(/\.(cif|mmcif)$/i) ? 'cif' : 'pdb';
  state.fmtUn = fmt;
  try {
    state.viewers.unmod.addModel(state.cifData.unmod, fmt);
    loadPoseModels();
  } catch (err) {
    console.error('Failed to parse structure files:', err);
    setStatus('Error parsing structures: ' + err.message + '. The file may not be valid CIF/PDB.');
    return;
  }

  /* Base cartoon styles */
  state.viewers.unmod.setStyle({}, { cartoon: { color: COLORS.unmodCartoon } });
  state.viewers.unmod.zoomTo();   state.viewers.unmod.render();

  setStatus('Ready');

  /* Show first site */
  try { refreshCurrentSite(); } catch(e) { console.error(e); setStatus(String(e)); }
}

main();
</script>
</body>
</html>
"""

def read_report_tsv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        rows = [dict(r) for r in reader]
    if not rows:
        raise SystemExit(f"No rows found in report TSV: {path}")
    return rows

def main() -> None:
    ap = argparse.ArgumentParser(
        description="Create a 3Dmol.js 3-panel PhosphoFill comparison page "
                    "showing PhosphoFill-identified contacts as lost/gained/maintained."
    )
    ap.add_argument("unmodified_structure")
    ap.add_argument("report_file", help="Report TSV or JSON produced by phosphofill_report_v5_richviz.py")
    ap.add_argument("--selection-json", required=True, help="Selection JSON from graft_phospho_openmm_v5_prodready.py")
    ap.add_argument("--output-prefix", default="phosphofill_vis")
    ap.add_argument("--prescan-frames", default=None,
                    help="Optional prescan_frames.json from the grafting script. "
                         "If not given, the HTML will try to auto-load it from the server directory.")
    args = ap.parse_args()

    unmod = Path(args.unmodified_structure)
    report = Path(args.report_file)
    selection = json.loads(Path(args.selection_json).read_text(encoding="utf-8"))

    def read_report(path: Path):
        if path.suffix.lower() == '.json':
            data = json.loads(path.read_text(encoding='utf-8'))
            if isinstance(data, dict) and 'sites' in data:
                return data.get('sites', [])
            if isinstance(data, list):
                return data
            raise SystemExit(f'Unsupported report JSON format: {path}')
        rows = read_report_tsv(path)
        json_candidate = path.with_suffix('.json')
        if json_candidate.exists():
            data = json.loads(json_candidate.read_text(encoding='utf-8'))
            if isinstance(data, dict) and 'sites' in data:
                return data.get('sites', [])
        return rows

    rows = read_report(report)
    payload = {"sites": rows}
    candidate_paths = {rec.get('output_rank'): Path(rec.get('path')).name for rec in selection.get('candidate_poses', []) or []}
    files = {
        "unmodified": unmod.name,
        "modified": Path(selection.get('selected_output_path') or '').name if selection.get('selected_output_path') else '',
        "pf1": candidate_paths.get(1, ''),
        "pf2": candidate_paths.get(2, ''),
        "pf3": candidate_paths.get(3, ''),
        "selection_json": Path(args.selection_json).name,
    }

    # Load prescan frames if provided and embed them directly.
    prescan_frames = {}
    frames_path = args.prescan_frames
    if frames_path is None:
        # Auto-detect sidecar file next to the report TSV.
        auto_path = report.with_suffix(report.suffix + ".prescan_frames.json")
        if auto_path.exists():
            frames_path = str(auto_path)
    if frames_path and Path(frames_path).exists():
        prescan_frames = json.loads(Path(frames_path).read_text(encoding="utf-8"))
        print(f"Loaded prescan frames for {len(prescan_frames)} sites from {frames_path}")

    out_json = Path(f"{args.output_prefix}.3dmol.json")
    out_html = Path(f"{args.output_prefix}.3dmol.html")
    out_json.write_text(json.dumps({"files": files, "sites": rows}, indent=2), encoding="utf-8")

    # If we have prescan frames, embed them so the HTML is self-contained.
    prescan_inject = ""
    if prescan_frames:
        prescan_inject = f"\n  state.prescanFrames = {json.dumps(prescan_frames, separators=(',', ':'))};\n  console.log('Embedded prescan frames for', Object.keys(state.prescanFrames).length, 'sites');\n"

    html = (HTML_TEMPLATE
            .replace("__REPORT_JSON__", json.dumps(payload))
            .replace("__FILES_JSON__", json.dumps(files))
            .replace("/* __PRESCAN_FRAMES_INJECT__ */", prescan_inject))
    out_html.write_text(html, encoding="utf-8")
    print(f"Wrote {out_json}")
    print(f"Wrote {out_html}")
    print("Serve the folder with: python -m http.server 8000")
    print(f"Then open: http://localhost:8000/{out_html.name}")

if __name__ == "__main__":
    main()
