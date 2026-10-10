import sounddevice as sd

devices = sd.query_devices()
for idx, d in enumerate(devices):
    if d["max_input_channels"] > 0:
        for sr in [16000, 48000, 44100]:
            for ch in [1, 2]:
                try:
                    stream = sd.InputStream(device=idx, channels=ch, samplerate=sr)
                    stream.start()
                    stream.stop()
                    stream.close()
                    print(f"Working: dev={idx:2d}, name={d['name'][:35]:35s}, sr={sr}, ch={ch}")
                    break
                except Exception:
                    pass
            else:
                continue
            break
