"""Microphone and Audio Subsystem Diagnostic Script for JARVIS."""

import sys
import time
from pathlib import Path
import numpy as np
import sounddevice as sd
import wave

# Ensure UTF-8 on Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def print_audio_devices():
    print("=" * 70)
    print("               AUDIO DEVICE INVENTORY & HOST APIS")
    print("=" * 70)
    print(f"Global default device in sounddevice: {sd.default.device}")
    
    print("\n[Host APIs]")
    for i, api in enumerate(sd.query_hostapis()):
        print(f"  HostAPI {i}: {api['name']:25s} | default_in: {api['default_input_device']} | default_out: {api['default_output_device']}")

    print("\n[Input Devices Available]")
    for i, d in enumerate(sd.query_devices()):
        if d['max_input_channels'] > 0:
            api_name = sd.query_hostapis(d['hostapi'])['name']
            is_default = (i == sd.default.device[0])
            def_marker = " <-- [SYSTEM DEFAULT INPUT]" if is_default else ""
            print(f"  [{i:2d}] {d['name'][:42]:42s} | API: {api_name:18s} | in_ch: {d['max_input_channels']} | sr: {d['default_samplerate']:.0f}{def_marker}")


def test_recording_methods():
    print("\n" + "=" * 70)
    print("           TESTING RECORDING METHODS ON EACH CANDIDATE")
    print("=" * 70)
    
    devices = sd.query_devices()
    test_results = []

    for i, d in enumerate(devices):
        if d['max_input_channels'] <= 0:
            continue
            
        api_name = sd.query_hostapis(d['hostapi'])['name']
        sr_list = [int(d['default_samplerate']), 16000, 48000, 44100]
        
        # Test 1: sd.rec (blocking buffer record)
        rec_ok = False
        rec_details = ""
        for sr in sr_list:
            for ch in [1, min(2, d['max_input_channels'])]:
                try:
                    data = sd.rec(int(0.3 * sr), samplerate=sr, channels=ch, dtype="float32", device=i)
                    sd.wait()
                    peak = float(np.max(np.abs(data)))
                    rms = float(np.sqrt(np.mean(data**2)))
                    rec_ok = True
                    rec_details = f"sr={sr}, ch={ch}, peak={peak:.4f}, rms={rms:.4f}"
                    break
                except Exception as e:
                    rec_details = f"FAILED: {e}"
            if rec_ok:
                break

        # Test 2: sd.InputStream with callback (what PushToTalkRecorder used!)
        stream_ok = False
        stream_details = ""
        callback_called_count = 0
        chunks_collected = []
        
        def _cb(indata, frames, time_info, status):
            nonlocal callback_called_count
            callback_called_count += 1
            chunks_collected.append(indata.copy())

        for sr in sr_list:
            for ch in [1, min(2, d['max_input_channels'])]:
                callback_called_count = 0
                chunks_collected.clear()
                try:
                    stream = sd.InputStream(
                        samplerate=sr,
                        channels=ch,
                        dtype="float32",
                        device=i,
                        callback=_cb,
                        blocksize=1024,
                    )
                    stream.start()
                    time.sleep(0.3)
                    stream.stop()
                    stream.close()
                    
                    if callback_called_count > 0 and chunks_collected:
                        arr = np.concatenate(chunks_collected, axis=0)
                        peak = float(np.max(np.abs(arr)))
                        rms = float(np.sqrt(np.mean(arr**2)))
                        stream_ok = True
                        stream_details = f"calls={callback_called_count}, sr={sr}, ch={ch}, peak={peak:.4f}, rms={rms:.4f}"
                    else:
                        stream_details = f"Zero callbacks fired! calls={callback_called_count}"
                    break
                except Exception as e:
                    stream_details = f"FAILED: {e}"
            if stream_ok:
                break

        status_str = f"Device [{i:2d}] {d['name'][:30]:30s} ({api_name}):"
        print(f"{status_str}")
        print(f"    sd.rec():         {'[OK]' if rec_ok else '[FAIL]'} {rec_details}")
        print(f"    sd.InputStream(): {'[OK]' if stream_ok else '[FAIL]'} {stream_details}")
        
        test_results.append({
            "index": i,
            "name": d['name'],
            "api": api_name,
            "rec_ok": rec_ok,
            "stream_ok": stream_ok,
            "rec_details": rec_details,
            "stream_details": stream_details,
        })

    return test_results


def record_sample_wav(device_idx=None, duration=3.0, filename="test_mic_sample.wav"):
    """Records a short audio sample and saves it as WAV for playback verification."""
    print("\n" + "=" * 70)
    print(f"      RECORDING {duration:.1f}s SAMPLE WAV (Device: {device_idx})")
    print("=" * 70)
    output_path = PROJECT_ROOT / "data" / filename
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Query device info
    dev_info = sd.query_devices(device_idx) if device_idx is not None else sd.query_devices(sd.default.device[0])
    sr = int(dev_info.get("default_samplerate", 16000))
    channels = min(2, dev_info.get("max_input_channels", 1))
    
    print(f"Device:       {dev_info['name']}")
    print(f"Sample Rate:  {sr} Hz")
    print(f"Channels:     {channels}")
    print(f"Saving to:    {output_path}")
    print("\n>>> Please say a few words into your microphone now...")
    time.sleep(0.5)
    
    t0 = time.time()
    try:
        data = sd.rec(int(duration * sr), samplerate=sr, channels=channels, dtype="float32", device=device_idx)
        sd.wait()
    except Exception as e:
        print(f"[ERROR] Failed to record with sd.rec: {e}")
        return None

    elapsed = time.time() - t0
    peak = float(np.max(np.abs(data)))
    rms = float(np.sqrt(np.mean(data**2)))
    shape = data.shape
    
    print(f"\n[Recording Completed in {elapsed:.2f}s]")
    print(f"  Shape:           {shape}")
    print(f"  Peak Amplitude:  {peak:.6f}  (Silence if < 0.005)")
    print(f"  RMS Energy:      {rms:.6f}")
    
    # Convert float32 [-1.0, 1.0] to int16 for WAV file
    int16_data = np.clip(data * 32767, -32768, 32767).astype(np.int16)
    with wave.open(str(output_path), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(int16_data.tobytes())

    print(f"  File created:    {output_path} ({output_path.stat().st_size} bytes)")
    
    # Now test what Whisper sees if resampled to 16kHz mono
    if channels > 1:
        mono = np.mean(data, axis=1)
    else:
        mono = np.squeeze(data)
        
    if sr != 16000:
        target_len = int(len(mono) * 16000 / sr)
        mono_16k = np.interp(np.linspace(0, len(mono) - 1, target_len), np.arange(len(mono)), mono).astype(np.float32)
    else:
        mono_16k = mono.astype(np.float32)

    print(f"  16kHz Mono Shape: {mono_16k.shape}")
    print(f"  16kHz Peak Amp:   {float(np.max(np.abs(mono_16k))):.6f}")

    return output_path, data, mono_16k


if __name__ == "__main__":
    print_audio_devices()
    test_recording_methods()
