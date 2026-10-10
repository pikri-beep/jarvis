import sounddevice as sd
import numpy as np
import time

for dev in [18, 19, 20, 21]:
    d = sd.query_devices(dev)
    sr = int(d['default_samplerate'])
    frames = []
    def _cb(indata, f, t, s):
        frames.append(indata.copy())
    try:
        s = sd.InputStream(device=dev, samplerate=sr, channels=1, callback=_cb)
        s.start()
        time.sleep(0.3)
        s.stop()
        s.close()
        if frames:
            arr = np.concatenate(frames)
            peak = float(np.max(np.abs(arr)))
            rms = float(np.sqrt(np.mean(arr**2)))
            print(f"Dev {dev:2d} ({d['name']:25s}): chunks={len(frames)}, sr={sr}, peak={peak:.6f}, rms={rms:.6f}")
        else:
            print(f"Dev {dev:2d} ({d['name']:25s}): 0 frames")
    except Exception as e:
        print(f"Dev {dev:2d} ({d['name']:25s}) error: {e}")
