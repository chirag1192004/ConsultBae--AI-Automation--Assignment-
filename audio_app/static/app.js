// Navigation
const navSubmit = document.getElementById('nav-submit');
const navDashboard = document.getElementById('nav-dashboard');
const navMatcher = document.getElementById('nav-matcher');

const viewSubmit = document.getElementById('view-submit');
const viewDashboard = document.getElementById('view-dashboard');
const viewMatcher = document.getElementById('view-matcher');

function hideAllViews() {
    [navSubmit, navDashboard, navMatcher].forEach(n => n.classList.remove('active'));
    [viewSubmit, viewDashboard, viewMatcher].forEach(v => {
        v.classList.remove('active-view');
        v.classList.add('hidden');
    });
}

navSubmit.addEventListener('click', () => {
    hideAllViews();
    navSubmit.classList.add('active');
    viewSubmit.classList.add('active-view');
    viewSubmit.classList.remove('hidden');
});

navDashboard.addEventListener('click', () => {
    hideAllViews();
    navDashboard.classList.add('active');
    viewDashboard.classList.add('active-view');
    viewDashboard.classList.remove('hidden');
    loadDashboard();
});

navMatcher.addEventListener('click', () => {
    hideAllViews();
    navMatcher.classList.add('active');
    viewMatcher.classList.add('active-view');
    viewMatcher.classList.remove('hidden');
});

// Audio Recording Logic
let mediaRecorder;
let audioChunks = [];
let audioBlob = null;
const recordBtn = document.getElementById('record-btn');
const statusIndicator = document.getElementById('recording-status');
const audioPreview = document.getElementById('audio-preview');
const fileUpload = document.getElementById('audio-upload');
const submitBtn = document.getElementById('submit-btn');

// Audio Analysis Helper
let clientMetrics = {
    duration: null,
    loudness: null,
    sampleRate: null
};

async function analyzeBlob(blob) {
    try {
        const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        const arrayBuffer = await blob.arrayBuffer();
        const audioBuffer = await audioCtx.decodeAudioData(arrayBuffer);
        
        const duration = audioBuffer.duration;
        const sampleRate = audioBuffer.sampleRate / 1000.0;
        
        // Calculate true RMS loudness from first channel
        const channelData = audioBuffer.getChannelData(0);
        let sumSq = 0;
        const step = Math.max(1, Math.floor(channelData.length / 50000));
        let count = 0;
        for (let i = 0; i < channelData.length; i += step) {
            sumSq += channelData[i] * channelData[i];
            count++;
        }
        const rms = Math.sqrt(sumSq / count);
        const loudness = rms > 0.00001 ? 20 * Math.log10(rms) : -60.0;
        
        clientMetrics = {
            duration: duration,
            sampleRate: sampleRate,
            loudness: loudness
        };
        console.log("Audio analyzed:", clientMetrics);
    } catch (e) {
        console.warn("Client audio analysis note:", e);
    }
}

recordBtn.addEventListener('click', async () => {
    if (mediaRecorder && mediaRecorder.state === 'recording') {
        // Stop recording
        mediaRecorder.stop();
        recordBtn.textContent = 'Start Recording';
        recordBtn.classList.remove('recording');
        statusIndicator.textContent = 'Analyzing audio...';
    } else {
        // Start recording
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaRecorder = new MediaRecorder(stream);
            audioChunks = [];
            
            mediaRecorder.ondataavailable = e => {
                if (e.data.size > 0) audioChunks.push(e.data);
            };
            
            mediaRecorder.onstop = async () => {
                audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                const audioUrl = URL.createObjectURL(audioBlob);
                audioPreview.src = audioUrl;
                audioPreview.style.display = 'block';
                await analyzeBlob(audioBlob);
                statusIndicator.textContent = clientMetrics.duration 
                    ? `Recorded: ${clientMetrics.duration.toFixed(1)}s (Loudness: ${clientMetrics.loudness.toFixed(1)} dB)` 
                    : 'Recorded successfully!';
                submitBtn.disabled = false;
                
                // Clear file upload if they recorded
                fileUpload.value = '';
            };
            
            mediaRecorder.start();
            recordBtn.textContent = 'Stop Recording';
            recordBtn.classList.add('recording');
            statusIndicator.textContent = 'Recording in progress... Speak clearly';
            
        } catch (err) {
            console.error(err);
            alert("Microphone access denied or unavailable.");
        }
    }
});

// File Upload Logic
fileUpload.addEventListener('change', async (e) => {
    if (e.target.files.length > 0) {
        audioBlob = e.target.files[0];
        const audioUrl = URL.createObjectURL(audioBlob);
        audioPreview.src = audioUrl;
        audioPreview.style.display = 'block';
        statusIndicator.textContent = 'Analyzing file...';
        await analyzeBlob(audioBlob);
        statusIndicator.textContent = clientMetrics.duration 
            ? `Uploaded: ${clientMetrics.duration.toFixed(1)}s (Loudness: ${clientMetrics.loudness.toFixed(1)} dB)` 
            : 'File ready for submission';
        submitBtn.disabled = false;
        
        if (mediaRecorder && mediaRecorder.state === 'recording') {
            mediaRecorder.stop();
            recordBtn.textContent = 'Start Recording';
            recordBtn.classList.remove('recording');
        }
    }
});

// Form Submission
const form = document.getElementById('submission-form');
const loader = document.getElementById('loader');
const successMsg = document.getElementById('success-msg');

form.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!audioBlob) return alert("Please record or upload audio first.");
    
    const name = document.getElementById('worker_name').value;
    const phone = document.getElementById('worker_phone').value;
    
    const formData = new FormData();
    formData.append('name', name);
    formData.append('phone', phone);
    
    // Determine extension for file
    let filename = "recording.webm";
    if (audioBlob.name) {
        filename = audioBlob.name; // Use uploaded file name
    }
    formData.append('audio', audioBlob, filename);
    
    if (clientMetrics.duration !== null) formData.append('client_duration', clientMetrics.duration);
    if (clientMetrics.loudness !== null) formData.append('client_loudness', clientMetrics.loudness);
    if (clientMetrics.sampleRate !== null) formData.append('client_sample_rate', clientMetrics.sampleRate);
    
    submitBtn.disabled = true;
    loader.classList.remove('hidden');
    successMsg.classList.add('hidden');
    
    try {
        const res = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });
        
        const data = await res.json();
        if (data.status === 'success') {
            const tier = data.metrics ? data.metrics.quality_tier : 'Processed';
            successMsg.textContent = `Submission Successful! Quality Tier: ${tier}`;
            successMsg.classList.remove('hidden');
            form.reset();
            audioBlob = null;
            clientMetrics = { duration: null, loudness: null, sampleRate: null };
            audioPreview.style.display = 'none';
            statusIndicator.textContent = '';
        } else {
            alert("Error: " + data.message);
            submitBtn.disabled = false;
        }
    } catch (err) {
        alert("Failed to submit.");
        submitBtn.disabled = false;
    } finally {
        loader.classList.add('hidden');
    }
});

// Dashboard Logic
async function loadDashboard() {
    const tbody = document.getElementById('table-body');
    tbody.innerHTML = '<tr><td colspan="9" style="text-align:center;">Loading...</td></tr>';
    
    try {
        const res = await fetch('/api/submissions');
        const data = await res.json();
        
        if (data.status === 'success') {
            tbody.innerHTML = '';
            if (data.data.length === 0) {
                tbody.innerHTML = '<tr><td colspan="9" style="text-align:center;">No submissions found.</td></tr>';
                return;
            }
            
            data.data.forEach(row => {
                let badgeClass = 'tier-retake';
                let tierText = row.quality_tier || 'Pending';
                
                if (row.qa_status === 'Rejected') {
                    tierText = 'Rejected';
                    badgeClass = 'tier-retake';
                } else if (tierText.includes('Gold')) {
                    badgeClass = 'tier-gold';
                } else if (tierText.includes('Silver')) {
                    badgeClass = 'tier-silver';
                }
                
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td><strong>${row.worker_name || 'Anonymous'}</strong><br><small style="color:var(--text-muted)">${row.City || 'N/A'}</small></td>
                    <td>${row.phone || '-'}</td>
                    <td>${row.file_url ? `<audio controls src="${row.file_url}" style="height:35px;"></audio>` : 'N/A'}</td>
                    <td>${row.duration_sec !== null && row.duration_sec !== undefined ? row.duration_sec + 's' : '-'}</td>
                    <td><span class="tier-badge ${badgeClass}">${tierText}</span></td>
                    <td>${row.loudness_db !== null && row.loudness_db !== undefined ? row.loudness_db + ' dB' : '-'}</td>
                    <td>${row.bitrate_kbps !== null && row.bitrate_kbps !== undefined ? row.bitrate_kbps + ' kbps' : '-'}</td>
                    <td>${row.sample_rate_khz !== null && row.sample_rate_khz !== undefined ? row.sample_rate_khz + ' kHz' : '-'}</td>
                    <td>${row.qa_status || 'Pending'}</td>
                `;
                tbody.appendChild(tr);
            });
        } else {
            tbody.innerHTML = `<tr><td colspan="9" style="text-align:center; color:red;">${data.message || 'Failed to load submissions.'}</td></tr>`;
        }
    } catch (err) {
        tbody.innerHTML = '<tr><td colspan="9" style="text-align:center; color:red;">Error loading data: ' + err.message + '</td></tr>';
    }
}

// AI Voice Matcher Logic
const voiceBtn = document.getElementById('voice-search-btn');
const transcriptBox = document.getElementById('transcript-box');
const matcherResults = document.getElementById('matcher-results');
const matcherIntentTitle = document.getElementById('matcher-intent-title');
const matcherTableBody = document.getElementById('matcher-table-body');

let recognition;
if ('webkitSpeechRecognition' in window) {
    recognition = new webkitSpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = true;
    
    recognition.onstart = function() {
        voiceBtn.classList.add('recording');
        voiceBtn.innerHTML = "🔴 Listening... (Release to search)";
        transcriptBox.innerHTML = "<p><em>Listening...</em></p>";
    };
    
    recognition.onresult = function(event) {
        let interimTranscript = '';
        for (let i = event.resultIndex; i < event.results.length; ++i) {
            if (event.results[i].isFinal) {
                // Final result
                const finalTranscript = event.results[i][0].transcript;
                transcriptBox.innerHTML = `<p>${finalTranscript}</p>`;
                searchMatcher(finalTranscript);
            } else {
                interimTranscript += event.results[i][0].transcript;
                transcriptBox.innerHTML = `<p><em>${interimTranscript}</em></p>`;
            }
        }
    };
    
    recognition.onerror = function(event) {
        console.error("Speech recognition error", event.error);
        voiceBtn.classList.remove('recording');
        voiceBtn.innerHTML = "🎤 Hold to Speak";
    };
    
    recognition.onend = function() {
        voiceBtn.classList.remove('recording');
        voiceBtn.innerHTML = "🎤 Hold to Speak";
    };
    
    voiceBtn.addEventListener('mousedown', () => recognition.start());
    voiceBtn.addEventListener('mouseup', () => recognition.stop());
    // Fallback for touch devices
    voiceBtn.addEventListener('touchstart', (e) => { e.preventDefault(); recognition.start(); });
    voiceBtn.addEventListener('touchend', (e) => { e.preventDefault(); recognition.stop(); });
} else {
    voiceBtn.innerHTML = "Speech API Not Supported";
    voiceBtn.disabled = true;
}

async function searchMatcher(transcript) {
    matcherResults.classList.remove('hidden');
    matcherTableBody.innerHTML = '<tr><td colspan="5" style="text-align:center;">Analyzing intent and finding matches...</td></tr>';
    
    try {
        const res = await fetch('/api/match', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ transcript: transcript })
        });
        
        const data = await res.json();
        if (data.status === 'success') {
            matcherIntentTitle.textContent = `Intent Detected: ${data.intent.toUpperCase()} (${data.data.length} matches)`;
            
            if (data.data.length === 0) {
                matcherTableBody.innerHTML = '<tr><td colspan="5" style="text-align:center;">No candidates found for this category.</td></tr>';
                return;
            }
            
            matcherTableBody.innerHTML = '';
            data.data.forEach(cand => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td><strong>${cand.name}</strong></td>
                    <td>${cand.phone}</td>
                    <td>${cand.city || '-'}</td>
                    <td><small>${cand.skills.substring(0, 100)}${cand.skills.length > 100 ? '...' : ''}</small></td>
                    <td><span class="tier-badge" style="background:var(--primary); color:white;">${cand.skill_category}</span></td>
                `;
                matcherTableBody.appendChild(tr);
            });
        } else {
            matcherTableBody.innerHTML = `<tr><td colspan="5" style="text-align:center; color:red;">Error: ${data.message}</td></tr>`;
        }
    } catch (err) {
        matcherTableBody.innerHTML = `<tr><td colspan="5" style="text-align:center; color:red;">Network Error</td></tr>`;
    }
}
