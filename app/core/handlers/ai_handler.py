"""AI reasoning, Action Interpreter (Layer B/C), and LLM streaming handler for JARVIS."""

import re
from typing import Any, Generator, Tuple

from app.ai.llm import OllamaClient
from app.core.logger import setup_logger
from app.core.router import RouteResult

logger = setup_logger("jarvis.handlers.ai")


def handle_ai_request(
    orchestrator: Any,
    route: RouteResult,
    user_input: str,
    effective_lang: str,
    is_id: bool,
) -> Tuple[RouteResult, Generator[str, None, None]]:
    """Handles AI reasoning requests routed to the Action Interpreter or local LLM."""
    is_mock_llm = orchestrator.llm is not None and not isinstance(orchestrator.llm, OllamaClient)

    is_groq_active = (
        getattr(orchestrator.settings, "interpreter_provider", "groq") == "groq"
        and bool(getattr(orchestrator.settings, "groq_api_key", None))
    )

    # 1. Offline / LLM-disabled desktop assistant mode (only when both local LLM and Groq Interpreter are inactive)
    if not orchestrator.settings.llm_enabled and not orchestrator._explicit_llm and not is_mock_llm and not is_groq_active:
        def _no_llm_gen():
            if any(w in user_input.lower() for w in ["jangan", "don't", "do not", "tidak usah", "batal"]):
                msg = "Baik sir, tindakan dibatalkan." if is_id else "Understood sir, action cancelled."
            else:
                msg = (
                    "Mode asisten desktop aktif. Eksekusi LLM dinonaktifkan untuk menghemat daya dan menjaga latensi tetap instan, sir."
                    if is_id
                    else "Desktop assistant mode is active. LLM execution is offline to conserve resources and keep latency instant, sir."
                )
            orchestrator.state.add_turn(user_input, msg)
            yield msg

        return route, _no_llm_gen()

    # 2. If explicit mock LLM is provided (e.g. in test suites), stream directly from mock
    if is_mock_llm:
        orchestrator.state.add_message("user", user_input)
        messages = orchestrator.state.get_messages_for_llm()

        def _mock_llm_gen():
            full_resp = []
            for token in orchestrator.llm.chat_stream(messages):
                full_resp.append(token)
                yield token
            complete = "".join(full_resp)
            orchestrator.state.add_message("assistant", complete)

        return route, _mock_llm_gen()

    # 3. Action Interpreter (Layer B & C) and Local Ollama generation
    def _interpreted_gen():
        # Provide recent dialog history for pronoun & context resolution
        recent_dlg = ""
        if orchestrator.state.history:
            recent_msgs = [f"{m.role}: '{m.content[:100]}'" for m in orchestrator.state.history[-2:]]
            recent_dlg = " | ".join(recent_msgs)

        state_ctx = {
            "recent_dialog": recent_dlg,
            "active_media": orchestrator.state.get_last_action_target() if ("music" in (orchestrator.state.get_last_action_target() or "") or "youtube" in (orchestrator.state.get_last_action_target() or "").lower()) else "",
            "last_action": orchestrator.state.last_action_context.get("action", ""),
            "last_target": orchestrator.state.last_action_context.get("target", ""),
            "last_focused_element": getattr(orchestrator.state.get_last_focused_element(), "name", ""),
            "last_search_query": orchestrator.state.get_last_search().get("query", ""),
            "last_search_sources": orchestrator.state.get_last_search().get("sources", []),
            "active_window": orchestrator.state.get_last_screen().get("window_title", ""),
        }
        plan = orchestrator.interpreter.interpret(user_input, state_context=state_ctx, language=effective_lang)

        if plan.is_action:
            is_negated = bool(re.search(r"\b(?:jangan|don'?t|do\s+not|tidak\s+usah|batal(?:kan)?)\b", user_input, re.I))
            if is_negated:
                logger.info('[EXEC] Action cancelled due to explicit user negation: "%s"', user_input)
                out = "Perintah dibatalkan, sir." if is_id else "Command cancelled, sir."
                orchestrator.state.add_turn(user_input, out)
                yield out
                return

            logger.info('[EXEC] Executing interpreted plan: intent=%s, action=%s, target=%s', plan.intent, plan.action, plan.target)
            out = ""

            # A. Media Control
            if plan.intent == "media_control":
                if plan.action == "pause":
                    from app.tools.music import pause_music
                    _, out = pause_music(target=plan.target, language=effective_lang)
                    orchestrator.state.set_last_action("pause_music", "active_media", "Media Session", True)
                elif plan.action == "resume":
                    from app.tools.music import resume_music
                    _, out = resume_music(target=plan.target, language=effective_lang)
                    orchestrator.state.set_last_action("resume_music", "active_media", "Media Session", True)
                elif plan.action == "stop":
                    from app.tools.music import media_stop
                    media_stop()
                    out = "Menghentikan pemutaran musik, sir." if is_id else "Stopped music playback, sir."
                    orchestrator.state.set_last_action("stop_music", "active_media", "Media Session", True)
                elif plan.action == "play":
                    from app.tools.youtube_controller import execute_youtube_command
                    q_play = plan.target or plan.parameters.get("query", user_input)
                    _, out, _ = execute_youtube_command(q_play, language=effective_lang)
                    orchestrator.state.set_last_action("play_music", q_play, "YouTube", True)
                elif plan.action in ("volume_up", "volume_down", "mute", "unmute", "toggle_mute"):
                    from app.tools.music import change_volume
                    if plan.action in ("mute", "unmute", "toggle_mute"):
                        _, out = change_volume("mute")
                    else:
                        pct = plan.parameters.get("volume_percentage") or plan.parameters.get("percentage")
                        steps = max(1, round(int(pct) / 2)) if pct else int(plan.parameters.get("steps", 2))
                        dir_v = "up" if plan.action == "volume_up" else "down"
                        _, out = change_volume(dir_v, steps=steps)
                elif plan.action in ("next", "previous"):
                    from app.tools.music import media_next, media_previous
                    if plan.action == "next":
                        media_next()
                    else:
                        media_previous()
                    out = "Beralih lagu, sir." if is_id else "Skipped track, sir."

            # B. Web Search
            elif plan.intent == "web_search":
                from app.tools.web_agent import web_agent
                from app.tools.browser_agent import answer_search_query, open_search_in_browser
                raw_q_search = plan.parameters.get("query") or plan.target or user_input
                # Clean trailing prompt noise
                q_search = re.sub(r"\s+(?:open\s+(?:in|on)\s+google|search\s+(?:in|on)\s+google|cari\s+di\s+google|di\s+google)$", "", raw_q_search, flags=re.I).strip()
                if plan.action == "open_search_results":
                    open_search_in_browser(q_search)
                    out = f"Membuka pencarian Google untuk '{q_search}' di browser, sir." if is_id else f"Opening search for '{q_search}' in browser, sir."
                elif plan.action in ("search_google", "search", "search_web"):
                    res = web_agent.search_google(q_search, language=effective_lang, open_browser=True, open_top_source=False)
                    out = res.message
                    if res.data.get("sources"):
                        orchestrator.state.set_last_search(
                            query=q_search,
                            spoken_answer=res.data.get("spoken_answer", ""),
                            display_answer=res.data.get("display_answer", ""),
                            sources=res.data.get("sources", []),
                        )
                elif plan.action == "open_source":
                    sources = orchestrator.state.get_last_search().get("sources", [])
                    idx = int(plan.parameters.get("index", 1)) - 1
                    if 0 <= idx < len(sources):
                        s_url = sources[idx].get("url")
                        res = web_agent.open_url(s_url, language=effective_lang)
                        out = res.message
                    else:
                        out = "Sumber tidak ditemukan pada pencarian terakhir, sir." if is_id else "Source not found in recent search, sir."
                else:
                    ans = answer_search_query(q_search, language=effective_lang)
                    orchestrator.state.set_last_search(query=ans.query, spoken_answer=ans.spoken_answer, display_answer=ans.display_answer, sources=ans.sources)
                    out = ans.display_answer

            # C. Universal Web Browser Agent
            elif plan.intent in ("browser", "web_browser"):
                from app.tools.web_agent import web_agent
                if plan.action in ("search_google", "search"):
                    q_s = plan.parameters.get("query") or plan.target or user_input
                    res = web_agent.search_google(q_s, language=effective_lang, open_browser=True, open_top_source=False)
                    out = res.message
                    if res.data.get("sources"):
                        orchestrator.state.set_last_search(
                            query=q_s,
                            spoken_answer=res.data.get("spoken_answer", ""),
                            display_answer=res.data.get("display_answer", ""),
                            sources=res.data.get("sources", []),
                        )
                elif plan.action in ("open_url", "open"):
                    tgt = plan.parameters.get("url") or plan.target
                    res = web_agent.open_url(tgt, language=effective_lang)
                    out = res.message
                elif plan.action in ("click_element", "click"):
                    lbl = plan.parameters.get("label") or plan.target
                    res = web_agent.find_and_click(lbl, language=effective_lang)
                    out = res.message
                elif plan.action in ("fill_input", "type"):
                    fld = plan.parameters.get("field") or plan.target
                    txt = plan.parameters.get("text") or plan.parameters.get("value") or ""
                    press_ent = bool(plan.parameters.get("press_enter", True))
                    res = web_agent.fill_input(fld, txt, press_enter=press_ent, language=effective_lang)
                    out = res.message
                elif plan.action in ("scroll_page", "scroll"):
                    direction = plan.parameters.get("direction", "down")
                    res = web_agent.scroll_page(direction=direction, language=effective_lang)
                    out = res.message
                elif plan.action in ("read_page", "summarize"):
                    res = web_agent.read_page(language=effective_lang)
                    out = res.message
                elif plan.action in ("open_new_tab", "close_tab", "go_back", "navigate_back", "refresh_page"):
                    res = web_agent.manage_tab(plan.action, language=effective_lang)
                    out = res.message
                elif plan.action == "open_source":
                    sources = orchestrator.state.get_last_search().get("sources", [])
                    idx = int(plan.parameters.get("index", 1)) - 1
                    if 0 <= idx < len(sources):
                        src_url = sources[idx].get("url")
                        res = web_agent.open_url(src_url, language=effective_lang)
                        out = res.message
                    else:
                        out = "Sumber tidak ditemukan pada pencarian terakhir, sir." if is_id else "Source not found in recent search, sir."

            # D. Page Reader
            elif plan.intent == "page_reader":
                from app.tools.web_agent import web_agent
                from app.tools.browser_agent import fetch_page_content
                if not plan.parameters.get("index") and not plan.target:
                    res = web_agent.read_page(language=effective_lang)
                    out = res.message
                else:
                    sources = orchestrator.state.get_last_search().get("sources", [])
                    idx = int(plan.parameters.get("index", 1)) - 1
                    if 0 <= idx < len(sources):
                        target_url = sources[idx].get("url")
                        ok_fetch, p_title, p_content = fetch_page_content(target_url, max_chars=1200)
                        if ok_fetch:
                            out = f"Ringkasan artikel '{p_title}':\n\n{p_content[:400]}..." if is_id else f"Article summary '{p_title}':\n\n{p_content[:400]}..."
                        else:
                            out = f"Gagal membaca isi artikel: {p_content}" if is_id else f"Could not read article: {p_content}"
                    else:
                        res = web_agent.read_page(language=effective_lang)
                        out = res.message

            # E. Desktop Control
            elif plan.intent == "desktop_control":
                from app.tools.web_agent import web_agent
                if plan.action in ("click", "click_element"):
                    lbl = plan.parameters.get("target") or plan.target
                    res = web_agent.find_and_click(lbl, language=effective_lang)
                    out = res.message
                elif plan.action == "scroll":
                    direction = plan.parameters.get("direction", "down")
                    res = web_agent.scroll_page(direction=direction, language=effective_lang)
                    out = res.message
                elif plan.action in ("type", "fill"):
                    lbl = plan.parameters.get("target") or plan.target
                    txt = plan.parameters.get("text") or ""
                    res = web_agent.fill_input(lbl, txt, language=effective_lang)
                    out = res.message

            # F. Application & Website Launch
            elif plan.intent in ("open_application", "open_website"):
                from app.tools.apps import launch_application, close_application
                from app.tools.browser import is_known_website, launch_website
                tgt = plan.parameters.get("application") or plan.target
                if plan.action in ("close", "tutup"):
                    res_launch = close_application(tgt)
                    out = res_launch[2] if isinstance(res_launch, tuple) and len(res_launch) >= 3 else str(res_launch)
                else:
                    if is_known_website(tgt) or plan.intent == "open_website":
                        _, _, disp, out = launch_website(tgt)
                    else:
                        res_launch = launch_application(tgt)
                        out = res_launch[2] if isinstance(res_launch, tuple) and len(res_launch) >= 3 else str(res_launch)

            # G. Screen Reader
            elif plan.intent == "screen_read":
                from app.tools.screen_reader import read_screen_content
                res = read_screen_content(prompt=user_input, language=effective_lang)
                out = f"{res.spoken_summary}\n\n{res.display_text}"

            if not out:
                out = "Tindakan telah dijalankan, sir." if is_id else "Action executed, sir."

            orchestrator.state.add_turn(user_input, out)
            yield out
            return

        elif plan.type == "clarify":
            clarify_msg = plan.response or (
                "Mohon sebutkan target yang Anda maksud lebih spesifik, sir."
                if is_id
                else "Please specify which target you mean, sir."
            )
            orchestrator.state.add_turn(user_input, clarify_msg)
            yield clarify_msg
            return

        # Conversational Response
        if plan.response:
            orchestrator.state.add_turn(user_input, plan.response)
            yield plan.response
        else:
            orchestrator.state.add_message("user", user_input)
            messages = orchestrator.state.get_messages_for_llm()
            full_resp = []
            try:
                for token in orchestrator.llm.chat_stream(messages):
                    full_resp.append(token)
                    yield token
                orchestrator.state.add_message("assistant", "".join(full_resp))
            except Exception as exc:
                logger.error("LLM streaming error: %s", exc)
                fallback_err = "Maaf sir, terjadi kesalahan saat menghubungi asisten." if is_id else "Error connecting to assistant."
                yield fallback_err

    return route, _interpreted_gen()
