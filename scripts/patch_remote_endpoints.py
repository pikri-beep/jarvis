"""Update D:\\Project\\remote\\main.py JARVIS endpoints with bulletproof error responses."""

path = r"D:\Project\remote\main.py"
with open(path, "r", encoding="utf-8") as f:
    code = f.read()

old_block = '''@app.post("/api/jarvis/message")
async def api_jarvis_message(req: JarvisMessageRequest):
    """Relay text command to JARVIS Gateway."""
    cmd_text = req.text.strip()
    if not cmd_text:
        raise HTTPException(status_code=400, detail="Text cannot be empty")
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{JARVIS_GATEWAY_URL}/api/process",
                json={"text": cmd_text, "audio_target": req.audio_target or "laptop"}
            )
            if resp.status_code == 200:
                return resp.json()
            else:
                return JSONResponse(status_code=resp.status_code, content=resp.json())
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="JARVIS is offline. Start JARVIS first.")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/jarvis/voice")
async def api_jarvis_voice(audio: UploadFile = File(...), audio_target: str = Form("laptop")):
    """Upload voice recording from phone, transcribe using JARVIS Whisper, and process command."""
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio recording")

    try:
        async with httpx.AsyncClient(timeout=35.0) as client:
            # 1. Transcribe via JARVIS Gateway
            transcribe_resp = await client.post(
                f"{JARVIS_GATEWAY_URL}/api/transcribe",
                content=audio_bytes,
                headers={"Content-Type": "audio/wav"}
            )
            if transcribe_resp.status_code != 200:
                detail = transcribe_resp.json().get("error", "Transcription failed")
                raise HTTPException(status_code=transcribe_resp.status_code, detail=detail)

            transcription = transcribe_resp.json().get("transcription", "").strip()
            if not transcription:
                return {
                    "success": False,
                    "transcription": "",
                    "reply": "Suara tidak terdengar jelas atau terlalu hening, sir.",
                    "audio_base64": ""
                }

            # 2. Process command
            process_resp = await client.post(
                f"{JARVIS_GATEWAY_URL}/api/process",
                json={"text": transcription, "audio_target": audio_target}
            )
            data = process_resp.json()
            data["transcription"] = transcription
            return data
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="JARVIS is offline. Start JARVIS first.")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))'''

new_block = '''@app.post("/api/jarvis/message")
async def api_jarvis_message(req: JarvisMessageRequest):
    """Relay text command to JARVIS Gateway."""
    cmd_text = req.text.strip()
    if not cmd_text:
        return {"success": False, "error": "Teks perintah tidak boleh kosong."}
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{JARVIS_GATEWAY_URL}/api/process",
                json={"text": cmd_text, "audio_target": req.audio_target or "laptop"}
            )
            if resp.status_code == 200:
                return resp.json()
            else:
                try:
                    err_data = resp.json()
                    err_msg = err_data.get("error") or err_data.get("detail") or "Gagal memproses di JARVIS."
                except Exception:
                    err_msg = f"HTTP {resp.status_code}"
                return {"success": False, "error": err_msg}
    except (httpx.ConnectError, httpx.TimeoutException):
        return {
            "success": False,
            "error": "JARVIS di laptop sedang offline atau belum siap. Silakan klik tombol 'Nyalakan JARVIS'.",
            "offline": True
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}


@app.post("/api/jarvis/voice")
async def api_jarvis_voice(audio: UploadFile = File(...), audio_target: str = Form("laptop")):
    """Upload voice recording from phone, transcribe using JARVIS Whisper, and process command."""
    audio_bytes = await audio.read()
    if not audio_bytes:
        return {"success": False, "error": "Rekaman suara kosong."}

    try:
        async with httpx.AsyncClient(timeout=35.0) as client:
            # 1. Transcribe via JARVIS Gateway
            transcribe_resp = await client.post(
                f"{JARVIS_GATEWAY_URL}/api/transcribe",
                content=audio_bytes,
                headers={"Content-Type": "audio/wav"}
            )
            if transcribe_resp.status_code != 200:
                try:
                    detail = transcribe_resp.json().get("error", "Transkripsi gagal.")
                except Exception:
                    detail = "Transkripsi gagal."
                return {"success": False, "error": detail}

            transcription = transcribe_resp.json().get("transcription", "").strip()
            if not transcription:
                return {
                    "success": False,
                    "transcription": "",
                    "reply": "Suara tidak terdengar jelas atau terlalu hening, sir.",
                    "audio_base64": ""
                }

            # 2. Process command
            process_resp = await client.post(
                f"{JARVIS_GATEWAY_URL}/api/process",
                json={"text": transcription, "audio_target": audio_target}
            )
            data = process_resp.json()
            data["transcription"] = transcription
            return data
    except (httpx.ConnectError, httpx.TimeoutException):
        return {
            "success": False,
            "error": "JARVIS di laptop sedang offline. Silakan klik 'Nyalakan JARVIS'.",
            "offline": True
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}'''

if old_block in code:
    code = code.replace(old_block, new_block)
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    print("Successfully updated D:\\Project\\remote\\main.py endpoints!")
else:
    print("old_block not found in main.py, please check manually.")
