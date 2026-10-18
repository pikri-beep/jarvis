"""Fast Command, Screen Reading, and Deterministic Web Search handler for JARVIS."""

import re
import time
from typing import Any, Generator, Tuple

from app.core.logger import setup_logger
from app.core.router import RouteResult

logger = setup_logger("jarvis.handlers.fast_command")


def handle_fast_command(
    orchestrator: Any,
    route: RouteResult,
    user_input: str,
    effective_lang: str,
    is_id: bool,
) -> Tuple[RouteResult, Generator[str, None, None]]:
    """Handles fast deterministic commands bypassing the LLM."""
    def _fast_command_gen():
        target = route.args.get("target", "")
        reply_chunks = []

        # Contextual pronoun resolution (e.g. "tutup aplikasinya", "close it", "tutup yang tadi")
        if target.lower() in ("it", "aplikasinya", "yang tadi", "programnya", "the app", "aplikasi tadi"):
            last_target = orchestrator.state.get_last_action_target()
            if last_target:
                target = last_target

        tool_start = time.time()

        if route.action == "app_not_found":
            target_display = route.args.get("raw_target") or route.args.get("target") or target
            out = (
                f"Saya tidak dapat menemukan aplikasi atau situs '{target_display}' di sistem, sir. Silakan periksa kembali nama programnya."
                if is_id
                else f"I couldn't find the application or website '{target_display}' on your system, sir. Please check the program name."
            )
            reply_chunks.append(out)
            orchestrator.state.add_turn(user_input, out)
            yield out
            return

        if route.action == "open_application":
            from app.tools.apps import launch_application
            # Sensitive applications check: WhatsApp accesses private communications
            if target.lower() in ("whatsapp",):
                from app.core.state import PendingAction
                orchestrator.state.pending_action = PendingAction(
                    action="open_application",
                    target=target,
                    display_name="WhatsApp",
                )
                logger.info('[TOOL] name="open_application" target="whatsapp" status="CONFIRMATION_REQUIRED"')
                out = (
                    "Membuka WhatsApp dapat mengakses data pesan pribadi Anda, sir. Apakah Anda yakin ingin melanjutkannya?"
                    if is_id
                    else "Opening WhatsApp will access your personal messages, sir. Are you sure you want to proceed?"
                )
                reply_chunks.append(out)
                orchestrator.state.add_turn(user_input, out)
                yield out
                return

            try:
                success, display_name, msg = launch_application(target)
                elapsed_ms = (time.time() - tool_start) * 1000.0
                orchestrator.state.set_last_action("open_application", target, display_name, success)
                if success:
                    logger.info(
                        '[TOOL] name="open_application" target="%s" status="SUCCESS" latency=%.1fms',
                        target,
                        elapsed_ms,
                    )
                    out = f"Membuka {display_name}, sir." if is_id else f"Opening {display_name}, sir."
                else:
                    logger.warning(
                        '[TOOL] name="open_application" target="%s" status="FAILURE" error="%s" latency=%.1fms',
                        target,
                        msg,
                        elapsed_ms,
                    )
                    retry_txt = " Silakan periksa atau coba ulangi perintah, sir." if is_id else " Please check if it is installed or try again, sir."
                    out = (
                        f"Maaf sir, saya tidak dapat membuka {display_name}. {msg}.{retry_txt}"
                        if is_id
                        else f"I couldn't open {display_name}, sir. {msg}.{retry_txt}"
                    )
            except Exception as exc:
                elapsed_ms = (time.time() - tool_start) * 1000.0
                logger.exception('[TOOL] name="open_application" target="%s" status="FAILURE" exception="%s"', target, exc)
                out = (
                    f"Terjadi kesalahan saat membuka {target}, sir: {exc}. Silakan coba lagi."
                    if is_id
                    else f"An error occurred while opening {target}, sir: {exc}. Please try again."
                )
            reply_chunks.append(out)
            yield out

        elif route.action == "open_website":
            from app.tools.browser import launch_website
            try:
                success, display_name, url, msg = launch_website(target)
                elapsed_ms = (time.time() - tool_start) * 1000.0
                orchestrator.state.set_last_action("open_website", "chrome", display_name, success)
                if success:
                    logger.info(
                        '[TOOL] name="open_website" target="%s" status="SUCCESS" latency=%.1fms',
                        target,
                        elapsed_ms,
                    )
                    out = f"Membuka {display_name}, sir." if is_id else f"Opening {display_name}, sir."
                else:
                    logger.warning(
                        '[TOOL] name="open_website" target="%s" status="FAILURE" error="%s" latency=%.1fms',
                        target,
                        msg,
                        elapsed_ms,
                    )
                    retry_txt = " Anda dapat mencoba mengulang perintah ini, sir." if is_id else " You can try asking again, sir."
                    out = (
                        f"Maaf sir, saya tidak dapat membuka {display_name}. {msg}.{retry_txt}"
                        if is_id
                        else f"I couldn't open {display_name}, sir. {msg}.{retry_txt}"
                    )
            except Exception as exc:
                elapsed_ms = (time.time() - tool_start) * 1000.0
                logger.exception('[TOOL] name="open_website" target="%s" status="FAILURE" exception="%s"', target, exc)
                out = (
                    f"Terjadi kesalahan saat membuka situs {target}, sir: {exc}. Silakan coba lagi."
                    if is_id
                    else f"An error occurred while opening website {target}, sir: {exc}. Please try again."
                )
            reply_chunks.append(out)
            yield out

        elif route.action == "close_application":
            from app.tools.apps import close_application
            if not target or target.lower() in ("it", "aplikasinya", "yang tadi"):
                out = "Tidak ada aplikasi yang terlacak dalam sesi ini, sir." if is_id else "No active application was tracked in this session, sir."
                reply_chunks.append(out)
                yield out
            else:
                try:
                    success, display_name, msg = close_application(target)
                    elapsed_ms = (time.time() - tool_start) * 1000.0
                    orchestrator.state.set_last_action("close_application", target, display_name, success)
                    if success:
                        logger.info(
                            '[TOOL] name="close_application" target="%s" status="SUCCESS" latency=%.1fms',
                            target,
                            elapsed_ms,
                        )
                        out = f"Menutup {display_name}, sir." if is_id else f"Closing {display_name}, sir."
                    else:
                        logger.info(
                            '[TOOL] name="close_application" target="%s" status="FAILURE" error="%s" latency=%.1fms',
                            target,
                            msg,
                            elapsed_ms,
                        )
                        out = f"Maaf sir, {display_name} tidak sedang berjalan." if is_id else f"Application {display_name} is not currently running, sir."
                except Exception as exc:
                    elapsed_ms = (time.time() - tool_start) * 1000.0
                    logger.exception('[TOOL] name="close_application" target="%s" status="FAILURE" exception="%s"', target, exc)
                    out = (
                        f"Terjadi kesalahan saat menutup {target}, sir: {exc}"
                        if is_id
                        else f"An error occurred while closing {target}, sir: {exc}"
                    )
                reply_chunks.append(out)
                yield out

        elif route.action == "greeting":
            out = "Halo sir! Ada yang bisa saya bantu?" if is_id else "Hello sir! How can I assist you today?"
            logger.info('[TOOL] name="greeting" status="SUCCESS"')
            reply_chunks.append(out)
            yield out

        elif route.action == "greeting_status":
            out = (
                "Saya aktif dan semua sistem siap membantu Anda, sir."
                if is_id
                else "All systems are operational and ready to assist you, sir."
            )
            logger.info('[TOOL] name="greeting_status" status="SUCCESS"')
            reply_chunks.append(out)
            yield out

        elif route.action == "get_time":
            from app.tools.datetime_tool import get_current_time
            out = get_current_time(lang=effective_lang)
            orchestrator.state.set_last_action("get_time", "time", "Time", True)
            logger.info('[TOOL] name="get_time" status="SUCCESS"')
            reply_chunks.append(out)
            yield out

        elif route.action == "get_date":
            from app.tools.datetime_tool import get_current_date
            out = get_current_date(lang=effective_lang)
            orchestrator.state.set_last_action("get_date", "date", "Date", True)
            logger.info('[TOOL] name="get_date" status="SUCCESS"')
            reply_chunks.append(out)
            yield out

        elif route.action == "system_info":
            from app.tools.windows import get_hardware_specs
            specs = get_hardware_specs()
            if is_id:
                out = (
                    f"Sistem berjalan pada {specs['os']} {specs['os_release']}, "
                    f"prosesor {specs['processor']}, {specs['cpu_count_logical']} threads, "
                    f"penggunaan RAM {specs['ram_percent']}% ({specs['ram_used_gb']} dari {specs['ram_total_gb']} GB), sir."
                )
            else:
                out = (
                    f"System running on {specs['os']} {specs['os_release']}, "
                    f"processor {specs['processor']}, {specs['cpu_count_logical']} threads, "
                    f"RAM usage at {specs['ram_percent']}% ({specs['ram_used_gb']} of {specs['ram_total_gb']} GB), sir."
                )
            orchestrator.state.set_last_action("system_info", "system", "System", True)
            logger.info('[TOOL] name="system_info" status="SUCCESS"')
            reply_chunks.append(out)
            yield out

        elif route.action == "battery_status":
            from app.tools.windows import get_battery_status
            batt = get_battery_status()
            if batt["has_battery"]:
                mode = (
                    ("sedang mengisi daya AC" if batt["power_plugged"] else "menggunakan baterai")
                    if is_id
                    else ("charging on AC power" if batt["power_plugged"] else "running on battery")
                )
                out = (
                    f"Baterai berada pada level {batt['percent']}%, {mode}, sir."
                    if is_id
                    else f"Battery is at {batt['percent']}%, currently {mode}, sir."
                )
            else:
                out = (
                    "Perangkat terhubung langsung ke daya listrik AC tanpa baterai internal, sir."
                    if is_id
                    else "Device is connected directly to AC power with no internal battery, sir."
                )
            orchestrator.state.set_last_action("battery_status", "battery", "Battery", True)
            logger.info('[TOOL] name="battery_status" status="SUCCESS"')
            reply_chunks.append(out)
            yield out

        elif route.action == "take_screenshot":
            from app.tools.windows import take_screenshot
            success, path, msg = take_screenshot()
            orchestrator.state.set_last_action("take_screenshot", "screen", "Screenshot", success)
            if success:
                out = f"Tangkapan layar berhasil disimpan di {path}, sir." if is_id else f"Screenshot saved successfully to {path}, sir."
            else:
                out = f"Gagal mengambil tangkapan layar, sir: {msg}" if is_id else f"Failed to take screenshot, sir: {msg}"
            logger.info('[TOOL] name="take_screenshot" status="%s"', "SUCCESS" if success else "FAILURE")
            reply_chunks.append(out)
            yield out

        elif route.action == "lock_screen":
            from app.tools.windows import lock_windows
            success, msg = lock_windows()
            orchestrator.state.set_last_action("lock_screen", "windows", "Lock", success)
            if success:
                out = "Mengunci workstation Windows, sir." if is_id else "Locking Windows workstation, sir."
            else:
                out = f"Gagal mengunci komputer, sir: {msg}" if is_id else f"Failed to lock computer, sir: {msg}"
            logger.info('[TOOL] name="lock_screen" status="%s"', "SUCCESS" if success else "FAILURE")
            reply_chunks.append(out)
            yield out

        elif route.action == "volume_up":
            from app.tools.music import change_volume
            steps = int(route.args.get("steps", 2))
            pct = int(route.args.get("percentage", steps * 2))
            change_volume("up", steps=steps)
            out = f"Menaikkan volume sebesar {pct} persen, sir." if is_id else f"Increasing volume by {pct} percent, sir."
            logger.info('[TOOL] name="volume_up" steps=%d status="SUCCESS"', steps)
            reply_chunks.append(out)
            yield out

        elif route.action == "volume_down":
            from app.tools.music import change_volume
            steps = int(route.args.get("steps", 2))
            pct = int(route.args.get("percentage", steps * 2))
            change_volume("down", steps=steps)
            out = f"Menurunkan volume sebesar {pct} persen, sir." if is_id else f"Decreasing volume by {pct} percent, sir."
            logger.info('[TOOL] name="volume_down" steps=%d status="SUCCESS"', steps)
            reply_chunks.append(out)
            yield out

        elif route.action in ("toggle_mute", "mute", "unmute"):
            from app.tools.music import change_volume
            change_volume("mute")
            out = "Mengalihkan status senyap (Mute/Unmute), sir." if is_id else "Toggled mute status, sir."
            logger.info('[TOOL] name="toggle_mute" status="SUCCESS"')
            reply_chunks.append(out)
            yield out

        elif route.action in ("media_play_pause", "media_next", "media_previous", "media_stop"):
            from app.tools.music import media_next, media_play_pause, media_previous, media_stop
            if route.action == "media_play_pause":
                media_play_pause()
                out = "Memutar atau menjeda media, sir." if is_id else "Toggled media playback, sir."
            elif route.action == "media_next":
                media_next()
                out = "Memutar lagu berikutnya, sir." if is_id else "Playing next track, sir."
            elif route.action == "media_previous":
                media_previous()
                out = "Memutar lagu sebelumnya, sir." if is_id else "Playing previous track, sir."
            elif route.action == "media_stop":
                media_stop()
                out = "Menghentikan pemutaran media, sir." if is_id else "Stopped media playback, sir."
            logger.info('[TOOL] name="%s" status="SUCCESS"', route.action)
            reply_chunks.append(out)
            yield out

        elif route.action == "stop_speech":
            if orchestrator.settings.tts_enabled:
                orchestrator.get_tts().stop()
            out = "Siap, sir." if is_id else "Understood, sir."
            logger.info('[TOOL] name="stop_speech" status="SUCCESS"')
            reply_chunks.append(out)
            yield out

        elif route.action == "pause_music":
            from app.tools.music import pause_music
            ok, msg = pause_music(target="active_media", language=effective_lang)
            orchestrator.state.set_last_action("pause_music", "active_media", "Media Session", ok)
            logger.info('[TOOL] name="pause_music" status="%s"', "SUCCESS" if ok else "FAILURE")
            reply_chunks.append(msg)
            yield msg

        elif route.action == "resume_music":
            from app.tools.music import resume_music
            ok, msg = resume_music(target="active_media", language=effective_lang)
            orchestrator.state.set_last_action("resume_music", "active_media", "Media Session", ok)
            logger.info('[TOOL] name="resume_music" status="%s"', "SUCCESS" if ok else "FAILURE")
            reply_chunks.append(msg)
            yield msg

        elif route.action in ("play_music", "play_contextual_music"):
            from app.tools.youtube_controller import execute_youtube_command
            query = route.args.get("query", "").strip()

            # Contextual pronoun resolution ("yes play it", "play it for me", "putar", "iya putarkan")
            if not query or query.lower() in ("it", "music", "musik", "lagu", "the song", "song", "lagunya", "lagu tadi"):
                resolved_song = ""
                # 1. Check last action context
                last_t = orchestrator.state.last_action_context.get("target") or orchestrator.state.last_action_context.get("display_name")
                if last_t and last_t.lower() not in ("it", "music", "musik", "lagu"):
                    resolved_song = last_t
                # 2. Check recent history messages for quoted song or mentioned song
                if not resolved_song and orchestrator.state.history:
                    for msg in reversed(orchestrator.state.history[-6:]):
                        if msg.role == "assistant":
                            m_quotes = re.findall(r"(?<![a-zA-Z])['\"]([A-Za-z0-9\s\-]+?)['\"](?![a-zA-Z])", msg.content)
                            if m_quotes:
                                resolved_song = m_quotes[-1].strip()
                                break
                            m_s = re.search(r"(?:play|putar|musik|lagu)\s+([A-Za-z0-9\s\-]+?)(?:\s+(?:music|lagu|right|now|for|sir|\.|\?|$))", msg.content, re.I)
                            if m_s:
                                resolved_song = m_s.group(1).strip()
                                break
                        elif msg.role == "user":
                            m_u = re.search(r"(?:play|kripp|creep|radiohead|lagu)\s*(.+)?", msg.content, re.I)
                            if m_u and m_u.group(1):
                                resolved_song = m_u.group(1).strip()
                                break
                query = resolved_song or "Radiohead - Creep"
                cmd_q = query
            else:
                cmd_q = user_input

            # Call YouTube controller for intelligent search and ranking
            success, spoken_yt, meta = execute_youtube_command(cmd_q, language=effective_lang)
            if success:
                orchestrator.state.set_last_action("play_music", query or user_input, "YouTube", True)
                out = spoken_yt
            else:
                from app.tools.music import play_music
                success, p_used, msg = play_music(query=query, provider=route.args.get("provider", "auto"))
                orchestrator.state.set_last_action("play_music", query, p_used, success)
                out = msg if not success else (f"Memutar '{query}' melalui {p_used}, sir." if is_id else f"Playing '{query}' via {p_used}, sir.")
            logger.info('[TOOL] name="play_music" query="%s" status="%s"', query, "SUCCESS" if success else "FAILURE")
            reply_chunks.append(out)
            yield out

        elif route.action == "open_folder":
            from app.tools.filesystem import open_folder
            folder_target = route.args.get("target", "") or target
            success, disp_name, f_path, msg = open_folder(folder_target)
            orchestrator.state.set_last_action("open_folder", folder_target, disp_name, success)
            if success:
                out = f"Membuka folder {disp_name}, sir." if is_id else f"Opening {disp_name} folder, sir."
            else:
                out = f"Maaf sir, tidak dapat membuka folder {disp_name}: {msg}" if is_id else f"Could not open {disp_name} folder, sir: {msg}"
            logger.info('[TOOL] name="open_folder" target="%s" status="%s"', folder_target, "SUCCESS" if success else "FAILURE")
            reply_chunks.append(out)
            yield out

        elif route.action == "search_web":
            from app.tools.browser_agent import answer_search_query, open_search_in_browser
            query = route.args.get("query", "") or target
            # Always open Google in browser directly for web search queries
            if query:
                open_search_in_browser(query)

            ans = answer_search_query(query, language=effective_lang)
            confirm_line = (
                f"Membuka pencarian Google untuk '{query}' di browser, sir."
                if is_id
                else f"Opening Google search for '{query}' in your browser, sir."
            )

            # Build display answer: 1-line confirmation + clickable silent sources list
            display_lines = [confirm_line]
            if ans.sources:
                display_lines.append("")
                display_lines.append("Sumber Terkait:")
                for idx, src in enumerate(ans.sources[:3], 1):
                    domain_tag = f" ({src.domain})" if getattr(src, "domain", None) else ""
                    title = getattr(src, "title", "Sumber")
                    url = getattr(src, "url", "#") if not isinstance(src, dict) else src.get("url", "#")
                    if not str(url).startswith(("http://", "https://")) and str(getattr(src, "snippet", "")).startswith(("http://", "https://")):
                        url = getattr(src, "snippet", "#")
                    display_lines.append(f"{idx}. [{title}]({url}){domain_tag}")

            out = "\n".join(display_lines)

            orchestrator.state.set_last_search(
                query=ans.query or query,
                spoken_answer=confirm_line,
                display_answer=out,
                sources=ans.sources,
            )
            orchestrator.state.set_last_action("search_web", query, "Web Search", True)
            logger.info('[TOOL] name="search_web" query="%s" status="SUCCESS"', query)
            reply_chunks.append(out)
            yield out

        elif route.action == "read_search_result":
            last_search = orchestrator.state.get_last_search()
            spoken = last_search.get("spoken_answer")
            if spoken:
                out = spoken
            else:
                out = "Belum ada hasil pencarian sebelumnya untuk dibacakan, sir." if is_id else "There is no previous search result to read, sir."
            orchestrator.state.set_last_action("read_search_result", "search", "Search", bool(spoken))
            logger.info('[TOOL] name="read_search_result" status="%s"', "SUCCESS" if spoken else "FAILURE")
            reply_chunks.append(out)
            yield out

        elif route.action == "list_search_sources":
            last_search = orchestrator.state.get_last_search()
            sources = last_search.get("sources", [])
            if sources:
                def _get_val(obj, key, dflt=""):
                    return str(obj.get(key, dflt) if isinstance(obj, dict) else getattr(obj, key, dflt) or dflt)

                domains = [_get_val(s, "domain") for s in sources if _get_val(s, "domain")]
                dom_str = ", ".join(domains[:3])
                spoken_lead = f"Sumber pencarian berasal dari {dom_str}, sir." if is_id else f"Search sources are from {dom_str}, sir."
                lines = [spoken_lead, "", "Sumber:" if is_id else "Sources:"]
                for i, s in enumerate(sources[:5], 1):
                    lines.append(f"{i}. {_get_val(s, 'title', 'Result')} - {_get_val(s, 'url')}")
                out = "\n".join(lines)
            else:
                out = "Belum ada sumber pencarian sebelumnya yang tersimpan, sir." if is_id else "No search sources are stored in the current session, sir."
            orchestrator.state.set_last_action("list_search_sources", "search", "Search", bool(sources))
            logger.info('[TOOL] name="list_search_sources" status="%s"', "SUCCESS" if sources else "FAILURE")
            reply_chunks.append(out)
            yield out

        elif route.action == "open_search_source":
            from app.tools.browser import launch_website
            last_search = orchestrator.state.get_last_search()
            sources = last_search.get("sources", [])
            idx = route.args.get("index", 1) - 1
            if 0 <= idx < len(sources):
                def _get_val(obj, key, dflt=""):
                    return str(obj.get(key, dflt) if isinstance(obj, dict) else getattr(obj, key, dflt) or dflt)
                target_url = _get_val(sources[idx], "url")
                target_title = _get_val(sources[idx], "title", f"Sumber #{idx+1}")
                if target_url:
                    ok, disp, final_url, msg = launch_website(target_url)
                    if ok:
                        out = f"Membuka sumber ke-{idx+1} ({target_title}) di browser, sir." if is_id else f"Opening source #{idx+1} ({target_title}) in your browser, sir."
                    else:
                        out = f"Gagal membuka tautan {target_url}, sir: {msg}" if is_id else f"Failed to open link {target_url}, sir: {msg}"
                else:
                    out = f"Tautan untuk sumber ke-{idx+1} tidak valid, sir." if is_id else f"Link for source #{idx+1} is invalid, sir."
            else:
                out = f"Sumber ke-{idx+1} tidak ditemukan dalam riwayat pencarian terakhir, sir." if is_id else f"Source #{idx+1} not found in last search results, sir."
            orchestrator.state.set_last_action("open_search_source", str(idx+1), "Search Source", 0 <= idx < len(sources))
            logger.info('[TOOL] name="open_search_source" index=%d status="%s"', idx+1, "SUCCESS" if (0 <= idx < len(sources)) else "FAILURE")
            reply_chunks.append(out)
            yield out

        elif route.action == "read_search_source_snippet":
            last_search = orchestrator.state.get_last_search()
            sources = last_search.get("sources", [])
            idx = route.args.get("index", 1) - 1
            if 0 <= idx < len(sources):
                def _get_val(obj, key, dflt=""):
                    return str(obj.get(key, dflt) if isinstance(obj, dict) else getattr(obj, key, dflt) or dflt)
                target_src = sources[idx]
                snippet = _get_val(target_src, "snippet") or _get_val(target_src, "title")
                domain = _get_val(target_src, "domain")
                domain_tag = f" ({domain})" if domain else ""
                out = f"Sumber ke-{idx+1}{domain_tag}: {snippet}" if is_id else f"Source #{idx+1}{domain_tag}: {snippet}"
            else:
                out = f"Sumber ke-{idx+1} tidak ditemukan dalam riwayat pencarian terakhir, sir." if is_id else f"Source #{idx+1} not found in last search results, sir."
            orchestrator.state.set_last_action("read_search_source_snippet", str(idx+1), "Search Source", 0 <= idx < len(sources))
            logger.info('[TOOL] name="read_search_source_snippet" index=%d status="%s"', idx+1, "SUCCESS" if (0 <= idx < len(sources)) else "FAILURE")
            reply_chunks.append(out)
            yield out

        elif route.action == "learn_memory":
            from app.memory.memory import memory_manager
            text_arg = route.args.get("text", "") or user_input
            res = memory_manager.learn_from_text(text_arg, auto_confirm=False, language=effective_lang)
            if res.has_conflicts:
                conf = res.conflicts[0]
                from app.core.router import RouteResult, RouteType
                orchestrator.state.pending_action = RouteResult(
                    route_type=RouteType.CLARIFY,
                    action="confirm_memory_conflict",
                    args={"conflict": conf.to_dict(), "language": effective_lang},
                    raw_input=user_input,
                    description=f"Confirm memory conflict for {conf.item.key}",
                )
            orchestrator.state.set_last_action("learn_memory", text_arg, "Memory", True)
            logger.info('[TOOL] name="learn_memory" learned=%d conflicts=%d', len(res.learned), len(res.conflicts))
            reply_chunks.append(res.summary_message)
            yield res.summary_message

        elif route.action == "show_profile":
            from app.memory.memory import memory_manager
            msg = memory_manager.format_profile_card(language=effective_lang)
            orchestrator.state.set_last_action("show_profile", "user_profile", "Memory", True)
            logger.info('[TOOL] name="show_profile" status="SUCCESS"')
            reply_chunks.append(msg)
            yield msg

        elif route.action == "interactive_learn_session":
            from app.memory.memory import memory_manager
            hon = memory_manager.get_honorific()
            msg = (
                f"Sesi belajar memori aktif, {hon}! Silakan ceritakan tentang diri Anda, kebiasaan, peramban/editor favorit, "
                f"atau aturan kerja yang ingin Anda tanamkan pada saya. (Ketik 'selesai' jika sudah cukup)."
                if is_id else
                f"Memory learning session active, {hon}! Please tell me anything about your identity, habits, preferred apps, "
                f"or custom workflow rules you would like me to remember. (Type 'done' when finished)."
            )
            orchestrator.state.set_last_action("interactive_learn_session", "session_start", "Memory", True)
            reply_chunks.append(msg)
            yield msg

        elif route.action == "learn_memory":
            from app.memory.memory import memory_manager
            text_to_learn = route.args.get("text", "") or user_input
            res = memory_manager.learn_from_text(text_to_learn, auto_confirm=True, language=effective_lang)
            msg = res.summary_message or (
                "Informasi berhasil dipelajari dan disimpan ke memori, sir."
                if is_id else
                "Information learned and saved to memory, sir."
            )
            orchestrator.state.set_last_action("learn_memory", "memory", "Memory", True)
            logger.info('[TOOL] name="learn_memory" status="SUCCESS"')
            reply_chunks.append(msg)
            yield msg

        elif route.action == "store_memory":
            from app.memory.memory import save_user_memory, memory_manager
            key = route.args.get("key", "").strip()
            val = route.args.get("value", "").strip()
            raw = route.args.get("raw", user_input)

            if (not key or key in ("catatan", "fakta", "")) and raw:
                res = memory_manager.learn_from_text(raw, auto_confirm=True, language=effective_lang)
                if res.learned:
                    success = True
                    msg = res.summary_message
                else:
                    success, msg = save_user_memory(key=key or "catatan", value=val or raw, user_input=user_input, language=effective_lang)
            else:
                success, msg = save_user_memory(key=key, value=val, user_input=user_input, language=effective_lang)

            orchestrator.state.set_last_action("store_memory", key or "memory", "Memory", success)
            logger.info('[TOOL] name="store_memory" key="%s" status="%s"', key, "SUCCESS" if success else "FAILURE")
            reply_chunks.append(msg)
            yield msg

        elif route.action == "recall_memories":
            from app.memory.memory import recall_user_memories
            query = route.args.get("query", "")
            msg = recall_user_memories(query=query, language=effective_lang)
            orchestrator.state.set_last_action("recall_memories", query, "Memory", True)
            logger.info('[TOOL] name="recall_memories" query="%s" status="SUCCESS"', query)
            reply_chunks.append(msg)
            yield msg

        elif route.action == "forget_memory":
            from app.memory.memory import forget_user_memory
            key = route.args.get("key", "")
            success, msg = forget_user_memory(key=key, language=effective_lang)
            orchestrator.state.set_last_action("forget_memory", key, "Memory", success)
            logger.info('[TOOL] name="forget_memory" key="%s" status="%s"', key, "SUCCESS" if success else "FAILURE")
            reply_chunks.append(msg)
            yield msg

        elif route.action == "enable_vision":
            from app.vision import get_vision_manager
            vm = getattr(orchestrator, "vision", None) or get_vision_manager()
            ok = vm.start()
            msg = "Pemantau kamera dan gestur pintar telah diaktifkan, sir." if is_id else "Smart camera presence and gesture control enabled, sir."
            orchestrator.state.set_last_action("enable_vision", "camera", "Vision", ok)
            logger.info('[TOOL] name="enable_vision" status="%s"', "SUCCESS" if ok else "FAILURE")
            reply_chunks.append(msg)
            yield msg

        elif route.action == "disable_vision":
            from app.vision import get_vision_manager
            vm = getattr(orchestrator, "vision", None) or get_vision_manager()
            vm.stop()
            msg = "Pemantau kamera telah dinonaktifkan dan perangkat kamera dilepas, sir." if is_id else "Camera monitoring disabled and hardware released, sir."
            orchestrator.state.set_last_action("disable_vision", "camera", "Vision", True)
            logger.info('[TOOL] name="disable_vision" status="SUCCESS"')
            reply_chunks.append(msg)
            yield msg

        elif route.action == "vision_status":
            from app.vision import get_vision_manager
            vm = getattr(orchestrator, "vision", None) or get_vision_manager()
            active = vm.is_running()
            if is_id:
                state_s = "aktif memantau kehadiran dan gestur" if active else "nonaktif (kamera mati)"
                msg = f"Status kamera pemantau saat ini {state_s}, sir."
            else:
                state_s = "active" if active else "disabled"
                msg = f"Vision camera is currently {state_s}, sir."
            orchestrator.state.set_last_action("vision_status", "camera", "Vision", True)
            reply_chunks.append(msg)
            yield msg


        elif route.action == "focus_app":
            from app.tools.desktop import focus_application
            app_t = route.args.get("target", "") or target
            ok, msg = focus_application(app_t, language=effective_lang)
            orchestrator.state.set_last_action("focus_app", app_t, app_t, ok)
            logger.info('[TOOL] name="focus_app" target="%s" status="%s"', app_t, "SUCCESS" if ok else "FAILURE")
            reply_chunks.append(msg)
            yield msg

        elif route.action == "open_new_tab":
            from app.tools.browser import open_new_tab
            ok, msg = open_new_tab(language=effective_lang)
            orchestrator.state.set_last_action("open_new_tab", "tab", "Browser Tab", ok)
            logger.info('[TOOL] name="open_new_tab" status="%s"', "SUCCESS" if ok else "FAILURE")
            reply_chunks.append(msg)
            yield msg

        elif route.action == "close_tab":
            from app.tools.browser import close_tab
            ok, msg = close_tab(language=effective_lang)
            orchestrator.state.set_last_action("close_tab", "tab", "Browser Tab", ok)
            logger.info('[TOOL] name="close_tab" status="%s"', "SUCCESS" if ok else "FAILURE")
            reply_chunks.append(msg)
            yield msg

        elif route.action == "refresh_page":
            from app.tools.browser import refresh_page
            ok, msg = refresh_page(language=effective_lang)
            orchestrator.state.set_last_action("refresh_page", "page", "Browser Page", ok)
            logger.info('[TOOL] name="refresh_page" status="%s"', "SUCCESS" if ok else "FAILURE")
            reply_chunks.append(msg)
            yield msg

        elif route.action == "navigate_back":
            from app.tools.browser import navigate_back
            ok, msg = navigate_back(language=effective_lang)
            orchestrator.state.set_last_action("navigate_back", "history", "Browser History", ok)
            logger.info('[TOOL] name="navigate_back" status="%s"', "SUCCESS" if ok else "FAILURE")
            reply_chunks.append(msg)
            yield msg

        elif route.action == "navigate_forward":
            from app.tools.browser import navigate_forward
            ok, msg = navigate_forward(language=effective_lang)
            orchestrator.state.set_last_action("navigate_forward", "history", "Browser History", ok)
            logger.info('[TOOL] name="navigate_forward" status="%s"', "SUCCESS" if ok else "FAILURE")
            reply_chunks.append(msg)
            yield msg

        elif route.action == "focus_address_bar":
            from app.tools.browser import focus_address_bar
            ok, msg = focus_address_bar(language=effective_lang)
            orchestrator.state.set_last_action("focus_address_bar", "address_bar", "Address Bar", ok)
            logger.info('[TOOL] name="focus_address_bar" status="%s"', "SUCCESS" if ok else "FAILURE")
            reply_chunks.append(msg)
            yield msg

        elif route.action == "click_search_field":
            from app.tools.desktop import click_search_field
            ok, msg = click_search_field(language=effective_lang)
            orchestrator.state.set_last_action("click_search_field", "search_field", "Search Field", ok)
            logger.info('[TOOL] name="click_search_field" status="%s"', "SUCCESS" if ok else "FAILURE")
            reply_chunks.append(msg)
            yield msg

        elif route.action == "move_cursor_center":
            from app.tools.desktop import move_cursor_to_center
            ok, msg = move_cursor_to_center(language=effective_lang)
            orchestrator.state.set_last_action("move_cursor_center", "center", "Mouse", ok)
            logger.info('[TOOL] name="move_cursor_center" status="%s"', "SUCCESS" if ok else "FAILURE")
            reply_chunks.append(msg)
            yield msg

        elif route.action == "mouse_click_left":
            from app.tools.desktop import mouse_click
            ok, msg = mouse_click(button="left", double=False, language=effective_lang)
            orchestrator.state.set_last_action("mouse_click", "left", "Mouse Click", ok)
            logger.info('[TOOL] name="mouse_click_left" status="%s"', "SUCCESS" if ok else "FAILURE")
            reply_chunks.append(msg)
            yield msg

        elif route.action == "mouse_click_right":
            from app.tools.desktop import mouse_click
            ok, msg = mouse_click(button="right", double=False, language=effective_lang)
            orchestrator.state.set_last_action("mouse_click", "right", "Mouse Click", ok)
            logger.info('[TOOL] name="mouse_click_right" status="%s"', "SUCCESS" if ok else "FAILURE")
            reply_chunks.append(msg)
            yield msg

        elif route.action == "mouse_click_double":
            from app.tools.desktop import mouse_click
            ok, msg = mouse_click(button="left", double=True, language=effective_lang)
            orchestrator.state.set_last_action("mouse_click", "double", "Mouse Click", ok)
            logger.info('[TOOL] name="mouse_click_double" status="%s"', "SUCCESS" if ok else "FAILURE")
            reply_chunks.append(msg)
            yield msg

        elif route.action == "mouse_scroll_down":
            from app.tools.desktop import mouse_scroll
            ok, msg = mouse_scroll(direction="down", amount=5, language=effective_lang)
            orchestrator.state.set_last_action("mouse_scroll", "down", "Mouse Scroll", ok)
            logger.info('[TOOL] name="mouse_scroll_down" status="%s"', "SUCCESS" if ok else "FAILURE")
            reply_chunks.append(msg)
            yield msg

        elif route.action == "mouse_scroll_up":
            from app.tools.desktop import mouse_scroll
            ok, msg = mouse_scroll(direction="up", amount=5, language=effective_lang)
            orchestrator.state.set_last_action("mouse_scroll", "up", "Mouse Scroll", ok)
            logger.info('[TOOL] name="mouse_scroll_up" status="%s"', "SUCCESS" if ok else "FAILURE")
            reply_chunks.append(msg)
            yield msg

        elif route.action == "mouse_scroll_right":
            from app.tools.desktop import mouse_scroll
            ok, msg = mouse_scroll(direction="right", amount=5, language=effective_lang)
            orchestrator.state.set_last_action("mouse_scroll", "right", "Mouse Scroll", ok)
            logger.info('[TOOL] name="mouse_scroll_right" status="%s"', "SUCCESS" if ok else "FAILURE")
            reply_chunks.append(msg)
            yield msg

        elif route.action == "mouse_scroll_left":
            from app.tools.desktop import mouse_scroll
            ok, msg = mouse_scroll(direction="left", amount=5, language=effective_lang)
            orchestrator.state.set_last_action("mouse_scroll", "left", "Mouse Scroll", ok)
            logger.info('[TOOL] name="mouse_scroll_left" status="%s"', "SUCCESS" if ok else "FAILURE")
            reply_chunks.append(msg)
            yield msg

        elif route.action == "previous_tab":
            from app.tools.desktop import send_shortcut
            ok, _ = send_shortcut("ctrl+shift+tab", language=effective_lang)
            msg = "Beralih ke tab sebelumnya, sir." if is_id else "Switched to previous tab, sir."
            orchestrator.state.set_last_action("previous_tab", "tab", "Browser Tab", ok)
            logger.info('[TOOL] name="previous_tab" status="%s"', "SUCCESS" if ok else "FAILURE")
            reply_chunks.append(msg)
            yield msg

        elif route.action == "next_tab":
            from app.tools.desktop import send_shortcut
            ok, _ = send_shortcut("ctrl+tab", language=effective_lang)
            msg = "Beralih ke tab berikutnya, sir." if is_id else "Switched to next tab, sir."
            orchestrator.state.set_last_action("next_tab", "tab", "Browser Tab", ok)
            logger.info('[TOOL] name="next_tab" status="%s"', "SUCCESS" if ok else "FAILURE")
            reply_chunks.append(msg)
            yield msg

        elif route.action == "click_contextual_element":
            focused_el = orchestrator.state.get_last_focused_element()
            if focused_el and focused_el.center_x > 0 and focused_el.center_y > 0:
                from app.tools.desktop import move_cursor, mouse_click
                move_cursor(focused_el.center_x, focused_el.center_y, language=effective_lang)
                ok_click, _ = mouse_click("left", language=effective_lang)
                out = f"Mengeklik tombol '{focused_el.name}', sir." if is_id else f"Clicked '{focused_el.name}' button, sir."
                orchestrator.state.set_last_action("click_contextual_element", focused_el.name, "Mouse Click", ok_click)
            else:
                out = (
                    "Tombol yang mana yang ingin Anda klik, sir? Mohon sebutkan nama atau posisinya lebih spesifik."
                    if is_id
                    else "Which button would you like me to click, sir? Please specify its label or position."
                )
            reply_chunks.append(out)
            yield out

        elif route.action == "click_named_button":
            btn_name = route.args.get("button_name", "")
            from app.tools.screen_reader import read_screen_content, find_element_by_reference
            res = read_screen_content(prompt=btn_name, language=effective_lang)
            matched_el = None
            if res.observation:
                matched_el = find_element_by_reference(btn_name, res.observation)
            if matched_el and matched_el.center_x > 0 and matched_el.center_y > 0:
                from app.tools.desktop import move_cursor, mouse_click
                move_cursor(matched_el.center_x, matched_el.center_y, language=effective_lang)
                ok_click, _ = mouse_click("left", language=effective_lang)
                out = f"Mengeklik tombol '{matched_el.name}', sir." if is_id else f"Clicked '{matched_el.name}' button, sir."
                orchestrator.state.set_last_action("click_named_button", matched_el.name, "Mouse Click", ok_click)
                orchestrator.state.set_last_focused_element(matched_el)
            else:
                out = (
                    f"Tombol '{btn_name}' tidak ditemukan di antarmuka aktif, sir."
                    if is_id
                    else f"Button '{btn_name}' was not detected on the active screen, sir."
                )
            reply_chunks.append(out)
            yield out

        elif route.action == "vision_task":
            from app.core.vision_agent import VisionAgent
            goal_arg = route.args.get("goal", "") or user_input
            agent = VisionAgent(settings=orchestrator.settings, max_steps=8)
            res = agent.start_task(goal_arg, language=effective_lang)
            if res.is_paused:
                orchestrator.state.set_pending_vision_task(res.state)
            else:
                orchestrator.state.clear_pending_vision_task()

            if res.state and res.state.last_observation:
                orchestrator.state.set_last_observation(res.state.last_observation)

            orchestrator.state.set_last_action("vision_task", goal_arg, "Vision Agent", res.status in ("COMPLETED", "PAUSED_FOR_USER_INPUT"))
            out = res.display_output if res.display_output else res.spoken_output
            reply_chunks.append(out)
            yield out

        elif route.action == "execute_task":
            from app.core.task_executor import TaskExecutor
            ctx_el = orchestrator.state.get_last_focused_element()
            executor = TaskExecutor(max_steps=5, contextual_element=ctx_el)
            task_res = executor.run(user_input, language=effective_lang)
            if task_res.last_observation:
                orchestrator.state.set_last_observation(task_res.last_observation)
            orchestrator.state.set_last_action("execute_task", user_input, "Task Execution", task_res.success)
            out = f"{task_res.spoken_summary}\n\n{task_res.display_summary}"
            reply_chunks.append(out)
            yield out

        elif route.action == "continue_task":
            out = "Melanjutkan langkah berikutnya, sir." if is_id else "Continuing to next step, sir."
            reply_chunks.append(out)
            yield out

        elif route.action == "retry_last_action":
            last_target = orchestrator.state.get_last_action_target()
            out = f"Mencoba mengulangi tindakan untuk {last_target or 'langkah sebelumnya'}, sir." if is_id else "Retrying previous action, sir."
            reply_chunks.append(out)
            yield out

        elif route.action == "type_text":
            from app.tools.desktop import type_text
            txt = route.args.get("text", "")
            ok, msg = type_text(txt, language=effective_lang)
            orchestrator.state.set_last_action("type_text", txt, "Desktop Typing", ok)
            logger.info('[TOOL] name="type_text" len=%d status="%s"', len(txt), "SUCCESS" if ok else "FAILURE")
            reply_chunks.append(msg)
            yield msg

        elif route.action == "press_key":
            from app.tools.desktop import press_single_key
            k = route.args.get("key", "enter")
            ok, msg = press_single_key(k, language=effective_lang)
            orchestrator.state.set_last_action("press_key", k, "Key Press", ok)
            logger.info('[TOOL] name="press_key" key="%s" status="%s"', k, "SUCCESS" if ok else "FAILURE")
            reply_chunks.append(msg)
            yield msg

        elif route.action == "send_hotkey":
            from app.tools.desktop import send_shortcut
            combo = route.args.get("combo", "")
            ok, msg = send_shortcut(combo, language=effective_lang)
            orchestrator.state.set_last_action("send_hotkey", combo, "Shortcut", ok)
            logger.info('[TOOL] name="send_hotkey" combo="%s" status="%s"', combo, "SUCCESS" if ok else "FAILURE")
            reply_chunks.append(msg)
            yield msg

        elif route.action == "request_confirmation":
            act_name = route.args.get("intended_action", "Tindakan")
            out = (
                f"Tindakan '{act_name}' memerlukan konfirmasi karena berisiko menghapus data atau mengubah konfigurasi sistem. Apakah Anda ingin melanjutkan, sir?"
                if is_id
                else f"Action '{act_name}' requires confirmation as it can delete data or modify system settings. Do you want to proceed, sir?"
            )
            orchestrator.state.set_last_action("request_confirmation", act_name, "Confirmation", False)
            logger.info('[TOOL] name="request_confirmation" action="%s"', act_name)
            reply_chunks.append(out)
            yield out

        elif route.action == "cancel_action":
            out = "Baik sir, tindakan dibatalkan." if is_id else "Understood sir, action cancelled."
            orchestrator.state.set_last_action("cancel_action", "cancel", "Cancel", True)
            logger.info('[TOOL] name="cancel_action"')
            reply_chunks.append(out)
            yield out

        elif route.action == "capability_inquiry":
            out = (
                "Saya dapat membuka aplikasi, membuka website, mengontrol tab dan browser, menggerakkan kursor, mengetik teks, dan membaca layar Windows, sir."
                if is_id
                else "I can open applications, websites, control browser tabs, move mouse, type text, and inspect your Windows screen, sir."
            )
            reply_chunks.append(out)
            yield out

        elif route.action == "start_remote_server":
            from app.tools.remote_server import start_remote_server
            try:
                ok, url, msg = start_remote_server()
                elapsed_ms = (time.time() - tool_start) * 1000.0
                logger.info('[TOOL] name="start_remote_server" ok=%s url="%s" latency=%.1fms', ok, url, elapsed_ms)
                out = msg
            except Exception as exc:
                logger.exception('[TOOL] name="start_remote_server" status="FAILURE" exception="%s"', exc)
                out = f"Maaf sir, gagal menyalakan server remote: {exc}" if is_id else f"Sorry sir, could not start remote server: {exc}"
            reply_chunks.append(out)
            yield out

        elif route.action == "stop_remote_server":
            from app.tools.remote_server import stop_remote_server
            try:
                ok, msg = stop_remote_server()
                elapsed_ms = (time.time() - tool_start) * 1000.0
                logger.info('[TOOL] name="stop_remote_server" ok=%s latency=%.1fms', ok, elapsed_ms)
                out = msg
            except Exception as exc:
                logger.exception('[TOOL] name="stop_remote_server" status="FAILURE" exception="%s"', exc)
                out = f"Maaf sir, gagal mematikan server remote: {exc}" if is_id else f"Sorry sir, could not stop remote server: {exc}"
            reply_chunks.append(out)
            yield out

        elif route.action == "get_remote_server_status":
            from app.tools.remote_server import get_remote_server_status
            try:
                st = get_remote_server_status()
                if st["running"]:
                    out = (
                        f"Server PocketDesk Remote sedang aktif di {st['url']}, sir. Anda dapat memberikan instruksi suara atau ketikan langsung dari smartphone."
                        if is_id
                        else f"PocketDesk Remote server is active at {st['url']}, sir. You can control JARVIS directly from your smartphone."
                    )
                else:
                    out = (
                        "Server PocketDesk Remote sedang tidak aktif, sir. Katakan 'aktifkan remote' untuk menyalakannya."
                        if is_id
                        else "PocketDesk Remote server is currently offline, sir. Say 'start remote' to launch it."
                    )
            except Exception as exc:
                out = f"Gagal memeriksa status remote: {exc}"
            reply_chunks.append(out)
            yield out

        elif route.action == "clean_workspace":
            from app.tools.janitor import clean_workspace
            target = route.args.get("target", "downloads")
            try:
                res = clean_workspace(target, dry_run=False)
                elapsed_ms = (time.time() - tool_start) * 1000.0
                moved = res.get("moved_count", 0)
                logger.info('[TOOL] name="clean_workspace" target="%s" moved=%d latency=%.1fms', target, moved, elapsed_ms)
                out = (
                    f"Saya telah merapikan folder {target.capitalize()}, sir. Sebanyak {moved} file berhasil dikelompokkan ke subfolder yang sesuai."
                    if is_id
                    else f"I have organized your {target.capitalize()} folder, sir. {moved} file(s) moved into clean subfolders."
                )
            except Exception as exc:
                logger.exception('[TOOL] name="clean_workspace" target="%s" status="FAILURE" exception="%s"', target, exc)
                out = f"Maaf sir, terjadi kendala saat merapikan folder {target}: {exc}" if is_id else f"Sorry sir, an error occurred while organizing {target}: {exc}"
            reply_chunks.append(out)
            yield out

        elif route.action == "list_todos":
            from app.core.todo_manager import TodoManager
            try:
                mgr = TodoManager(database=orchestrator.memory.db if hasattr(orchestrator, "memory") and hasattr(orchestrator.memory, "db") else None)
                todos = mgr.list_tasks(include_completed=False)
                elapsed_ms = (time.time() - tool_start) * 1000.0
                logger.info('[TOOL] name="list_todos" count=%d latency=%.1fms', len(todos), elapsed_ms)
                if not todos:
                    out = (
                        "Belum ada tugas aktif di daftar todo Anda, sir."
                        if is_id
                        else "You have no active tasks in your todo list, sir."
                    )
                else:
                    lines = ["📋 **Daftar Tugas Aktif:**" if is_id else "📋 **Active Todo List:**"]
                    for idx, t in enumerate(todos, start=1):
                        title = t.get("title", "")
                        due = t.get("due_date", "")
                        due_str = f" *(Waktu: {due})*" if due else ""
                        lines.append(f"{idx}. [ ] {title}{due_str}")
                    lines.append("\n*Tip: Buka tab 📝 TODO & NOTES untuk melihat atau mencentang tugas.*" if is_id else "\n*Tip: Open the 📝 TODO & NOTES tab to view or check off tasks.*")
                    out = "\n".join(lines)
            except Exception as exc:
                logger.exception('[TOOL] name="list_todos" status="FAILURE" exception="%s"', exc)
                out = f"Maaf sir, gagal mengambil daftar tugas: {exc}" if is_id else f"Sorry sir, could not retrieve tasks: {exc}"
            reply_chunks.append(out)
            yield out

        elif route.action == "complete_todo":
            from app.core.todo_manager import TodoManager
            task_num = route.args.get("task_number")
            try:
                mgr = TodoManager(database=orchestrator.memory.db if hasattr(orchestrator, "memory") and hasattr(orchestrator.memory, "db") else None)
                todos = mgr.list_tasks(include_completed=False)
                if task_num and 1 <= task_num <= len(todos):
                    target_todo = todos[task_num - 1]
                    mgr.toggle_task(target_todo["id"])
                    out = (
                        f"Tugas #{task_num} ('{target_todo['title']}') telah ditandai selesai, sir."
                        if is_id
                        else f"Task #{task_num} ('{target_todo['title']}') has been marked completed, sir."
                    )
                else:
                    out = (
                        f"Tugas nomor {task_num} tidak ditemukan di daftar aktif, sir."
                        if is_id
                        else f"Task number {task_num} not found in active list, sir."
                    )
            except Exception as exc:
                logger.exception('[TOOL] name="complete_todo" status="FAILURE" exception="%s"', exc)
                out = f"Maaf sir, gagal menyelesaikan tugas: {exc}" if is_id else f"Sorry sir, could not complete task: {exc}"
            reply_chunks.append(out)
            yield out

        elif route.action == "clear_completed_todos":
            from app.core.todo_manager import TodoManager
            try:
                mgr = TodoManager(database=orchestrator.memory.db if hasattr(orchestrator, "memory") and hasattr(orchestrator.memory, "db") else None)
                cleared_count = mgr.clear_completed()
                out = (
                    f"Sebanyak {cleared_count} tugas selesai telah dibersihkan dari daftar, sir."
                    if is_id
                    else f"{cleared_count} completed task(s) cleared from todo list, sir."
                )
            except Exception as exc:
                logger.exception('[TOOL] name="clear_completed_todos" status="FAILURE" exception="%s"', exc)
                out = f"Maaf sir, gagal membersihkan tugas: {exc}" if is_id else f"Sorry sir, could not clear tasks: {exc}"
            reply_chunks.append(out)
            yield out

        elif route.action == "clear_all_todos":
            from app.core.todo_manager import TodoManager
            try:
                mgr = TodoManager(database=orchestrator.memory.db if hasattr(orchestrator, "memory") and hasattr(orchestrator.memory, "db") else None)
                cleared_count = mgr.clear_all()
                out = (
                    f"Semua {cleared_count} tugas dalam daftar todo Anda telah berhasil dihapus, sir."
                    if is_id
                    else f"All {cleared_count} tasks in your todo list have been cleared, sir."
                )
            except Exception as exc:
                logger.exception('[TOOL] name="clear_all_todos" status="FAILURE" exception="%s"', exc)
                out = f"Maaf sir, gagal menghapus semua tugas: {exc}" if is_id else f"Sorry sir, could not clear all tasks: {exc}"
            reply_chunks.append(out)
            yield out

        elif route.action == "add_todo":
            from app.core.todo_manager import TodoManager
            task_text = route.args.get("task", "")
            try:
                mgr = TodoManager(database=orchestrator.memory.db if hasattr(orchestrator, "memory") and hasattr(orchestrator.memory, "db") else None)
                ok, msg, todo_id = mgr.add_task(task_text)
                elapsed_ms = (time.time() - tool_start) * 1000.0
                logger.info('[TOOL] name="add_todo" task="%s" id=%d latency=%.1fms', task_text, todo_id, elapsed_ms)
                out = (
                    f"Siap sir, {msg.lower()}."
                    if is_id
                    else f"Noted, sir. {msg}."
                )
            except Exception as exc:
                logger.exception('[TOOL] name="add_todo" status="FAILURE" exception="%s"', exc)
                out = f"Maaf sir, gagal mencatat tugas: {exc}" if is_id else f"Sorry sir, could not save task: {exc}"
            reply_chunks.append(out)
            yield out

        elif route.action == "unsupported_command":
            out = (
                "Perintah tidak dikenali, sir. Sebutkan tindakan seperti buka aplikasi, kontrol browser, ketik teks, atau baca layar."
                if is_id
                else "Command not recognized, sir. Please state an action such as opening an application, browser control, or reading the screen."
            )
            logger.info('[TOOL] name="unsupported_command"')
            reply_chunks.append(out)
            yield out

        else:
            out = f"Menjalankan perintah {route.action}, sir." if is_id else f"Executing {route.action}, sir."
            logger.info('[TOOL] name="%s" status="SUCCESS"', route.action)
            reply_chunks.append(out)
            yield out

        # Record the completed fast command turn in session state history
        full_reply = "".join(reply_chunks)
        orchestrator.state.add_turn(user_input, full_reply)

    return route, _fast_command_gen()


def handle_screen_read(
    orchestrator: Any,
    route: RouteResult,
    user_input: str,
    effective_lang: str,
    is_id: bool,
) -> Tuple[RouteResult, Generator[str, None, None]]:
    """Handles on-demand screen reading and OCR."""
    def _screen_read_gen():
        from app.tools.screen_reader import read_screen_content
        pref_vis = route.args.get("prefer_vision", False)
        prompt = route.args.get("prompt", user_input)
        res = read_screen_content(
            prompt=prompt,
            language=effective_lang,
            vision_enabled=pref_vis,
            ollama_url=orchestrator.settings.ollama_url,
        )
        orchestrator.state.set_last_screen(
            window_title=res.window_title,
            text=res.text,
            method=res.method,
            spoken_summary=res.spoken_summary,
            display_text=res.display_text,
        )
        orchestrator.state.set_last_action("read_screen", res.window_title, "Screen Reader", res.success)
        if res.observation:
            orchestrator.state.set_last_observation(res.observation)
            from app.tools.screen_reader import find_element_by_reference
            matched_el = find_element_by_reference(prompt, res.observation)
            if matched_el:
                orchestrator.state.set_last_focused_element(matched_el)
        logger.info(
            '[TOOL] name="read_screen" method="%s" window="%s" latency=%.1fms status="%s"',
            res.method,
            res.window_title,
            res.latency_ms,
            "SUCCESS" if res.success else "FAILURE",
        )
        out = f"{res.spoken_summary}\n\n{res.display_text}"
        orchestrator.state.add_turn(user_input, out)
        yield out

    return route, _screen_read_gen()


def handle_web_search(
    orchestrator: Any,
    route: RouteResult,
    user_input: str,
    effective_lang: str,
    is_id: bool,
) -> Tuple[RouteResult, Generator[str, None, None]]:
    """Handles dedicated search-first requests without LLM."""
    def _search_first_gen():
        from app.tools.browser_agent import answer_search_query, open_search_in_browser
        query = route.args.get("query", "") or user_input
        open_b = route.args.get("open_browser", False) or route.action == "open_search_results"

        if open_b:
            open_search_in_browser(query)
            out = (
                f"Membuka hasil pencarian '{query}' di browser, sir."
                if is_id
                else f"Opening search results for '{query}' in your browser, sir."
            )
            orchestrator.state.set_last_action("open_search_results", query, "Web Browser", True)
            orchestrator.state.add_turn(user_input, out)
            yield out
            return

        # Open Google in browser directly for explicit search queries
        if query:
            open_search_in_browser(query)

        # Zero-LLM extractive factual search pipeline for sources
        ans = answer_search_query(query, language=effective_lang)
        confirm_line = (
            f"Membuka pencarian Google untuk '{query}' di browser, sir."
            if is_id
            else f"Opening Google search for '{query}' in your browser, sir."
        )

        display_lines = [confirm_line]
        if ans.sources:
            display_lines.append("")
            display_lines.append("Sumber Terkait:")
            for idx, src in enumerate(ans.sources[:3], 1):
                domain_tag = f" ({src.domain})" if getattr(src, "domain", None) else ""
                title = getattr(src, "title", "Sumber")
                url = getattr(src, "url", "#") if not isinstance(src, dict) else src.get("url", "#")
                if not str(url).startswith(("http://", "https://")) and str(getattr(src, "snippet", "")).startswith(("http://", "https://")):
                    url = getattr(src, "snippet", "#")
                display_lines.append(f"{idx}. [{title}]({url}){domain_tag}")

        out = "\n".join(display_lines)

        orchestrator.state.set_last_search(
            query=ans.query or query,
            spoken_answer=confirm_line,
            display_answer=out,
            sources=ans.sources,
        )
        orchestrator.state.set_last_action("search_web", query, "Search-First", bool(ans.sources))
        logger.info(
            '[TOOL] name="search_web" query="%s" sources=%d latency=%.1fms status="%s"',
            query,
            len(ans.sources),
            ans.latency_ms,
            "SUCCESS" if ans.sources else "FAILURE",
        )
        orchestrator.state.add_turn(user_input, out)
        yield out

    return route, _search_first_gen()


def handle_web_dependent(
    orchestrator: Any,
    route: RouteResult,
    user_input: str,
    effective_lang: str,
    is_id: bool,
) -> Tuple[RouteResult, Generator[str, None, None]]:
    """Handles web-dependent requests (weather, breaking news, etc.)."""
    def _web_query_gen():
        from app.tools.browser_agent import answer_search_query
        query = route.args.get("query", "") or user_input
        ans = answer_search_query(query, language=effective_lang)
        orchestrator.state.set_last_search(
            query=ans.query,
            spoken_answer=ans.spoken_answer,
            display_answer=ans.display_answer,
            sources=ans.sources,
        )
        orchestrator.state.set_last_action("search_web", query, "Web Dependent", bool(ans.sources))
        logger.info(
            '[TOOL] name="web_dependent" query="%s" sources=%d latency=%.1fms',
            query,
            len(ans.sources),
            ans.latency_ms,
        )
        out = ans.display_answer
        orchestrator.state.add_turn(user_input, out)
        yield out

    return route, _web_query_gen()
