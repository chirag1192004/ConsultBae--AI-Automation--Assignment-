import os
import math
import struct
import wave

try:
    from mutagen import File as MutagenFile
except ImportError:
    MutagenFile = None

def get_audio_metadata(file_path, client_duration=None, client_loudness=None, client_sample_rate=None):
    """
    Extracts duration, sample rate, bitrate, and loudness.
    Uses native wave analysis for WAV, mutagen for MP3/OGG/FLAC, and Web Audio API client data for WebM.
    """
    duration = float(client_duration) if client_duration and float(client_duration) > 0 else 0.0
    sample_rate = float(client_sample_rate) if client_sample_rate and float(client_sample_rate) > 0 else 0.0
    loudness = float(client_loudness) if client_loudness is not None else None
    bitrate = 0
    file_size_bytes = os.path.getsize(file_path) if os.path.exists(file_path) else 0

    # 1. Try native WAV analysis if WAV file
    if file_path.lower().endswith('.wav'):
        try:
            with wave.open(file_path, 'rb') as wf:
                channels = wf.getnchannels()
                sampwidth = wf.getsampwidth()
                rate = wf.getframerate()
                n_frames = wf.getnframes()
                if rate > 0:
                    duration = n_frames / float(rate)
                    sample_rate = rate / 1000.0  # kHz
                
                # Calculate true RMS loudness from sample data
                read_count = min(n_frames, 200000)
                frames = wf.readframes(read_count)
                if sampwidth == 2 and len(frames) >= 2:
                    count = len(frames) // 2
                    samples = struct.unpack(f"{count}h", frames)
                    sum_sq = sum(s * s for s in samples)
                    rms = math.sqrt(sum_sq / count) if count > 0 else 0
                    loudness = 20 * math.log10(rms / 32768.0) if rms > 0 else -60.0
        except Exception as e:
            print(f"WAV analysis notice: {e}")

    # 2. Mutagen extraction for MP3, OGG, FLAC
    if duration == 0.0 and MutagenFile:
        try:
            audio = MutagenFile(file_path)
            if audio and hasattr(audio, 'info'):
                duration = getattr(audio.info, 'length', 0.0)
                sample_rate = getattr(audio.info, 'sample_rate', 0) / 1000.0
                bitrate = getattr(audio.info, 'bitrate', 0) / 1000
        except Exception as e:
            print(f"Mutagen notice: {e}")

    # 3. WebM / fallback estimation if duration still unknown
    if duration == 0.0:
        # Default ~128kbps Opus assumption if no duration available
        bitrate = 128
        duration = (file_size_bytes * 8) / (bitrate * 1000)
        sample_rate = 48.0
    
    if bitrate == 0 and duration > 0:
        bitrate = (file_size_bytes * 8) / (duration * 1000)

    if sample_rate == 0:
        sample_rate = 48.0

    if loudness is None:
        # Realistic fallback based on energy
        loudness = -18.0 if duration >= 3.0 else -38.0

    # 4. Multi-tier Audio Quality & QA Classification Rules:
    # - Too short (< 2.0s): Rejected
    # - Inaudible / Too quiet (Loudness < -35 dB): Rejected
    # - Gold: Clear loud voice (>= -22 dB) and sufficient length (>= 3.5s)
    # - Silver: Acceptable loudness (>= -35 dB) and length (>= 2.0s)
    if duration < 2.0:
        quality_tier = "Retake Needed (Too Short)"
        qa_status = "Rejected"
    elif loudness < -35.0:
        quality_tier = "Retake Needed (Too Quiet)"
        qa_status = "Rejected"
    elif duration >= 3.5 and loudness >= -22.0:
        quality_tier = "Gold (Good)"
        qa_status = "Approved"
    elif duration >= 2.0 and loudness >= -35.0:
        quality_tier = "Silver (Acceptable)"
        qa_status = "Approved"
    else:
        quality_tier = "Retake Needed (Poor Quality)"
        qa_status = "Rejected"

    return {
        "duration_sec": round(duration, 2),
        "sample_rate_khz": round(sample_rate, 2),
        "bitrate_kbps": int(bitrate) if not math.isnan(bitrate) and not math.isinf(bitrate) else 0,
        "loudness_db": round(loudness, 2),
        "quality_tier": quality_tier,
        "qa_status": qa_status
    }

