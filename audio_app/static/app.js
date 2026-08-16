// Navigation
const navSubmit = document.getElementById('nav-submit');
const navDashboard = document.getElementById('nav-dashboard');
const viewSubmit = document.getElementById('view-submit');
const viewDashboard = document.getElementById('view-dashboard');

navSubmit.addEventListener('click', () => {
    navSubmit.classList.add('active');
    navDashboard.classList.remove('active');
    viewSubmit.classList.add('active-view');
    viewSubmit.classList.remove('hidden');
    viewDashboard.classList.remove('active-view');
    viewDashboard.classList.add('hidden');
});

navDashboard.addEventListener('click', () => {
    navDashboard.classList.add('active');
    navSubmit.classList.remove('active');
    viewDashboard.classList.add('active-view');
    viewDashboard.classList.remove('hidden');
    viewSubmit.classList.remove('active-view');
    viewSubmit.classList.add('hidden');
    loadDashboard();
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

recordBtn.addEventListener('click', async () => {
    if (mediaRecorder && mediaRecorder.state === 'recording') {
        // Stop recording
        mediaRecorder.stop();
        recordBtn.textContent = 'Start Recording';
        recordBtn.classList.remove('recording');
        statusIndicator.textContent = 'Processing...';
    } else {
        // Start recording
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaRecorder = new MediaRecorder(stream);
            audioChunks = [];
            
            mediaRecorder.ondataavailable = e => {
                if (e.data.size > 0) audioChunks.push(e.data);
            };
            
            mediaRecorder.onstop = () => {
                audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                const audioUrl = URL.createObjectURL(audioBlob);
                audioPreview.src = audioUrl;
                audioPreview.style.display = 'block';
                statusIndicator.textContent = 'Recorded successfully!';
                submitBtn.disabled = false;
                
                // Clear file upload if they recorded
                fileUpload.value = '';
            };
            
            mediaRecorder.start();
            recordBtn.textContent = 'Stop Recording';
            recordBtn.classList.add('recording');
            statusIndicator.textContent = 'Recording...';
            
        } catch (err) {
            console.error(err);
            alert("Microphone access denied or unavailable.");
        }
    }
});

// File Upload Logic
fileUpload.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
        audioBlob = e.target.files[0];
        const audioUrl = URL.createObjectURL(audioBlob);
        audioPreview.src = audioUrl;
        audioPreview.style.display = 'block';
        submitBtn.disabled = false;
        
        // Clear recording status if they upload
        statusIndicator.textContent = '';
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
            successMsg.classList.remove('hidden');
            form.reset();
            audioBlob = null;
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
                if (row.quality_tier && row.quality_tier.includes('Gold')) badgeClass = 'tier-gold';
                else if (row.quality_tier && row.quality_tier.includes('Silver')) badgeClass = 'tier-silver';
                
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td><strong>${row.worker_name}</strong><br><small style="color:var(--text-muted)">${row.City}</small></td>
                    <td>${row.phone}</td>
                    <td><audio controls src="${row.file_url}"></audio></td>
                    <td>${row.duration_sec}s</td>
                    <td><span class="tier-badge ${badgeClass}">${row.quality_tier}</span></td>
                    <td>${row.loudness_db} dB</td>
                    <td>${row.bitrate_kbps} kbps</td>
                    <td>${row.sample_rate_khz} kHz</td>
                    <td>${row.qa_status}</td>
                `;
                tbody.appendChild(tr);
            });
        }
    } catch (err) {
        tbody.innerHTML = '<tr><td colspan="9" style="text-align:center; color:red;">Error loading data.</td></tr>';
    }
}
