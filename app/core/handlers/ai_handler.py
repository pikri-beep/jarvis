"""AI reasoning, Autonomous ReAct Agent Loop, Action Interpreter, and LLM streaming handler for JARVIS."""

import re
from typing import Any, Generator, Tuple

from app.ai.llm import OllamaClient
from app.core.logger import setup_logger
from app.core.router import RouteResult
from app.core.task_executor import AutonomousReActAgent, execute_registered_tool

logger = setup_logger("jarvis.handlers.ai")


def is_meta_reasoning(text: str) -> bool:
    """Detects internal chain-of-thought or third-person meta commentary about the user."""
    if not text:
        return False
    low = text.strip().lower()
    return bool(re.search(r"^(?:the\s+user\s+(?:is|wants|looking|tried|needs)|user\s+(?:is|wants|looking)|in\s+this\s+case,\s+the\s+user|i\s+need\s+to\s+determine)\b", low))


def _stream_conversational_response(
    orchestrator: Any,
    user_input: str,
    effective_lang: str,
    is_id: bool,
    state_ctx: Any = None,
) -> Generator[str, None, None]:
    """Streams full conversational response from Groq or Ollama adhering strictly to JARVIS persona."""
    from app.ai.prompts import get_system_prompt

    # Prepare system prompt with contextual grounding
    sys_prompt = get_system_prompt(language=effective_lang)
    if state_ctx and state_ctx.get("last_search_query"):
        q = state_ctx["last_search_query"]
        sources = state_ctx.get("last_search_sources", [])
        src_summary = ", ".join([f"{idx+1}. {getattr(s, 'title', s.get('title', '')) if isinstance(s, dict) else getattr(s, 'title', '')}" for idx, s in enumerate(sources[:3])]) if sources else "Tidak ada"
        sys_prompt += f"\n\nContextual Desktop Info:\n- Recent Search Query: '{q}'\n- Available Search Sources: {src_summary}"
    if state_ctx and state_ctx.get("stored_memories"):
        sys_prompt += f"\n- Stored User Facts: {state_ctx['stored_memories']}"

    messages = orchestrator.state.get_messages_for_llm()
    # Ensure system prompt is present at messages[0]
    if messages and messages[0].get("role") == "system":
        messages[0]["content"] = sys_prompt
    else:
        messages.insert(0, {"role": "system", "content": sys_prompt})

    # Ensure current user_input is the last user message
    if not messages or messages[-1].get("content") != user_input:
        messages.append({"role": "user", "content": user_input})

    full_resp = []

    # 1. Try Groq Cloud first if active (< 300ms latency)
    groq_client = getattr(getattr(orchestrator, "interpreter", None), "_groq_client", None)
    if groq_client is not None:
        try:
            groq_model = getattr(orchestrator.interpreter, "groq_model", "qwen/qwen3.8-27b")
            stream = groq_client.chat.completions.create(
                model=groq_model,
                messages=messages,
                stream=True,
                temperature=0.7,
                max_tokens=300,
                timeout=6.0,
            )
            for chunk in stream:
                token = chunk.choices[0].delta.content or ""
                if token:
                    full_resp.append(token)
                    yield token

            complete = "".join(full_resp).strip()
            if complete:
                orchestrator.state.add_turn(user_input, complete)
                return
        except Exception as e:
            logger.warning("Groq conversational streaming error (%s); falling back to local LLM", e)

    # 2. Fallback to local Ollama LLM
    try:
        if orchestrator.llm:
            for token in orchestrator.llm.chat_stream(messages):
                full_resp.append(token)
                yield token
            complete = "".join(full_resp).strip()
            orchestrator.state.add_turn(user_input, complete)
            return
    except Exception as e:
        logger.error("Local LLM conversational streaming error: %s", e)

    fallback = "Maaf sir, saya mengalami kendala teknis saat memproses tanggapan." if is_id else "I apologize sir, I encountered a technical issue while generating a response."
    orchestrator.state.add_turn(user_input, fallback)
    yield fallback


def handle_ai_request(
    orchestrator: Any,
    route: RouteResult,
    user_input: str,
    effective_lang: str,
    is_id: bool,
) -> Tuple[RouteResult, Generator[str, None, None]]:
    """Handles AI reasoning and multi-step agentic tasks using the Autonomous ReAct Loop or Action Interpreter."""
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

    # 2. Check for explicit standalone user cancellation
    is_negated = bool(re.match(r"^(?:batal(?:kan)?|cancel|stop|tidak\s+jadi|tidak\s+usah|jangan(?:\s+lakukan|\s+jadi|\s+dulu)?|don'?t(?:\s+do\s+that)?)[!.]*$", user_input.strip(), re.I))
    if is_negated:
        def _negated_gen():
            logger.info('[EXEC] Action cancelled due to explicit user negation: "%s"', user_input)
            out = "Perintah dibatalkan, sir." if is_id else "Command cancelled, sir."
            orchestrator.state.add_turn(user_input, out)
            yield out

        return route, _negated_gen()

    # 3. If explicit mock LLM is provided without agentic task action, support streaming directly
    if is_mock_llm and route.action != "agentic_task":
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

    # 4. Multi-Step Autonomous ReAct Agent Loop & Action Interpreter
    def _agentic_gen():
        # Provide recent dialog history for pronoun & context resolution
        recent_dlg = ""
        if orchestrator.state.history:
            recent_msgs = [f"{m.role}: '{m.content[:100]}'" for m in orchestrator.state.history[-2:]]
            recent_dlg = " | ".join(recent_msgs)

        # Provide memory context to ActionInterpreter
        stored_mems_summary = ""
        try:
            if hasattr(orchestrator, "memory") and orchestrator.memory:
                all_m = orchestrator.memory.recall_all()
                if all_m:
                    stored_mems_summary = ", ".join([f"{k}: {v}" for k, v in list(all_m.items())[:12]])
        except Exception:
            pass

        state_ctx = {
            "recent_dialog": recent_dlg,
            "active_media": orchestrator.state.get_last_action_target() if ("music" in (orchestrator.state.get_last_action_target() or "") or "youtube" in (orchestrator.state.get_last_action_target() or "").lower()) else "",
            "last_action": orchestrator.state.last_action_context.get("action", ""),
            "last_target": orchestrator.state.last_action_context.get("target", ""),
            "last_focused_element": getattr(orchestrator.state.get_last_focused_element(), "name", ""),
            "last_search_query": orchestrator.state.get_last_search().get("query", ""),
            "last_search_sources": orchestrator.state.get_last_search().get("sources", []),
            "stored_memories": stored_mems_summary,
            "active_window": orchestrator.state.get_last_screen().get("window_title", ""),
        }

        # Check if the route is an explicit agentic task or multi-step/implicit goal
        is_explicit_agentic = (
            route.action == "agentic_task"
            or any(w in user_input.lower() for w in ["lanjut ngerjain", "lanjut kerja", "ngerjain tugas", "lanjutkan tugas", "error gini", "layarku kok", "layar error", "kok error", "lalu", "kemudian", "terus"])
        )

        # For non-explicit agentic goals, check if fast Action Interpreter recognizes a single turn
        plan = None
        if not is_explicit_agentic and hasattr(orchestrator, "interpreter"):
            try:
                plan = orchestrator.interpreter.interpret(user_input, state_context=state_ctx, language=effective_lang)
            except Exception as e:
                logger.debug("Action Interpreter check error: %s", e)

        # Handle explicit clarification from interpreter
        if plan and plan.type == "clarify":
            clarify_msg = plan.response or (
                "Mohon sebutkan target yang Anda maksud lebih spesifik, sir."
                if is_id
                else "Please specify which target you mean, sir."
            )
            orchestrator.state.add_turn(user_input, clarify_msg)
            yield clarify_msg
            return

        # Handle simple single-turn action from interpreter
        if plan and plan.is_action:
            logger.info('[EXEC] Executing interpreted plan: intent=%s, action=%s, target=%s', plan.intent, plan.action, plan.target)
            out = ""

            # Media Control
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

            # Web Search
            elif plan.intent == "web_search":
                from app.tools.web_agent import web_agent
                from app.tools.browser_agent import answer_search_query, open_search_in_browser
                raw_q_search = plan.parameters.get("query") or plan.target or user_input
                q_search = re.sub(r"\s+(?:open\s+(?:in|on)\s+google|search\s+(?:in|on)\s+google|cari\s+di\s+google|di\s+google)$", "", raw_q_search, flags=re.I).strip()
                if plan.action == "open_search_results":
                    open_search_in_browser(q_search)
                    out = f"Membuka pencarian Google untuk '{q_search}' di browser, sir." if is_id else f"Opening search for '{q_search}' in browser, sir."
                elif plan.action in ("open_source", "open_search_source"):
                    from app.tools.browser_agent import open_search_source
                    idx_val = 1
                    try:
                        raw_idx = plan.parameters.get("index") or plan.target
                        word_map = {"pertama": 1, "kedua": 2, "ketiga": 3, "first": 1, "second": 2, "third": 3}
                        if str(raw_idx).lower() in word_map:
                            idx_val = word_map[str(raw_idx).lower()]
                        else:
                            m_d = re.search(r"\d+", str(raw_idx))
                            idx_val = int(m_d.group(0)) if m_d else 1
                    except Exception:
                        idx_val = 1
                    _, out = open_search_source(idx_val)
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
                else:
                    ans = answer_search_query(q_search, language=effective_lang)
                    orchestrator.state.set_last_search(query=ans.query, spoken_answer=ans.spoken_answer, display_answer=ans.display_answer, sources=ans.sources)
                    out = ans.display_answer

            # Todo Management
            elif plan.intent == "todo":
                from app.core.todo_manager import TodoManager
                db = orchestrator.memory.db if hasattr(orchestrator, "memory") and hasattr(orchestrator.memory, "db") else None
                mgr = TodoManager(database=db)
                if plan.action in ("clear_all", "delete_all"):
                    cleared = mgr.clear_all()
                    out = f"Semua {cleared} tugas dalam daftar todo Anda telah berhasil dihapus, sir." if is_id else f"All {cleared} tasks in your todo list have been cleared, sir."
                elif plan.action in ("clear_completed", "clear"):
                    cleared = mgr.clear_completed()
                    out = f"Sebanyak {cleared} tugas selesai telah dibersihkan, sir." if is_id else f"{cleared} completed tasks cleared, sir."
                elif plan.action == "list":
                    todos = mgr.list_tasks(include_completed=False)
                    if not todos:
                        out = "Belum ada tugas aktif di daftar todo Anda, sir." if is_id else "No active tasks in your todo list, sir."
                    else:
                        lines = ["📋 **Daftar Tugas Aktif:**" if is_id else "📋 **Active Todo List:**"]
                        for idx, t in enumerate(todos, start=1):
                            due = f" *(Waktu: {t['due_date']})*" if t.get("due_date") else ""
                            lines.append(f"{idx}. [ ] {t['title']}{due}")
                        out = "\n".join(lines)
                elif plan.action in ("add", "add_task"):
                    t_text = plan.parameters.get("task") or plan.target or user_input
                    ok, msg, _ = mgr.add_task(t_text)
                    out = f"Siap sir, {msg.lower()}." if is_id else f"Noted sir, {msg}."
                elif plan.action in ("delete", "remove"):
                    t_id = plan.parameters.get("id") or plan.parameters.get("task_id")
                    if t_id:
                        mgr.delete_task(int(t_id))
                        out = f"Tugas #{t_id} telah dihapus, sir." if is_id else f"Task #{t_id} deleted, sir."
                    else:
                        out = "Tugas berhasil dihapus, sir." if is_id else "Task deleted, sir."
                else:
                    out = "Operasi todo telah dijalankan, sir." if is_id else "Todo operation executed, sir."

            # Screen Reading
            elif plan.intent == "screen_read":
                from app.tools.screen_reader import read_screen_content
                res = read_screen_content(prompt=user_input, language=effective_lang)
                out = f"{res.spoken_summary}\n\n{res.display_text}"

            # Persistent Memory Management
            elif plan.intent == "memory":
                from app.memory.memory import memory_manager, recall_user_memories, forget_user_memory
                if plan.action in ("store", "save", "add", "store_memory"):
                    k = plan.parameters.get("key") or plan.target
                    v = plan.parameters.get("value")
                    if k and v:
                        _, out = memory_manager.store_fact(key=str(k), value=str(v))
                    else:
                        res = memory_manager.learn_from_text(user_input, auto_confirm=True, language=effective_lang)
                        out = res.summary_message
                elif plan.action in ("recall", "get", "recall_memory"):
                    q_rec = plan.parameters.get("key") or plan.target or ""
                    out = recall_user_memories(query=q_rec, language=effective_lang)
                elif plan.action in ("list", "all", "recall_all", "recall_all_memories", "show_profile", "profile"):
                    out = memory_manager.format_profile_card(language=effective_lang)
                elif plan.action in ("forget", "delete", "remove", "forget_memory"):
                    k_del = plan.parameters.get("key") or plan.target or ""
                    _, out = forget_user_memory(key=k_del, language=effective_lang)
                elif plan.action in ("learn", "learn_memory"):
                    res = memory_manager.learn_from_text(user_input, auto_confirm=True, language=effective_lang)
                    out = res.summary_message
                else:
                    out = "Operasi memori telah diproses, sir." if is_id else "Memory operation processed, sir."

            # Fallback registered tool execution
            else:
                ok, msg = execute_registered_tool(
                    action=plan.action,
                    target=plan.target,
                    args=plan.parameters,
                    language=effective_lang,
                    contextual_element=orchestrator.state.get_last_focused_element(),
                )
                out = msg

            if not out:
                out = "Tindakan telah dijalankan, sir." if is_id else "Action executed, sir."

            orchestrator.state.add_turn(user_input, out)
            yield out
            return

        # Anti-Hallucination Guard:
        # Detect if user input is an imperative command to perform an action or alter state
        is_imperative_action = bool(
            re.search(
                r"^(?:(?:tolong|coba|silakan|mohon)\s+)?(?:hapus|kosongkan|delete|clear|remove|buat|create|bikin|ubah|ganti|setel|atur|arsipkan|pindahkan|move|salin|copy|jalankan|run|eksekusi|hitung|calculate|instal|install)\b",
                user_input.strip(),
                re.IGNORECASE,
            )
        )

        # Handle conversational or out-of-context requests with full streaming JARVIS persona,
        # UNLESS the user gave an imperative action command that hasn't been executed by a tool!
        if not is_explicit_agentic and not is_imperative_action:
            if plan and plan.response and not is_meta_reasoning(plan.response):
                orchestrator.state.add_turn(user_input, plan.response)
                yield plan.response
                return
            yield from _stream_conversational_response(
                orchestrator,
                user_input,
                effective_lang,
                is_id,
                state_ctx=state_ctx,
            )
            return

        # Autonomous ReAct Agent Loop Execution (for multi-step desktop tasks or imperative actions)
        logger.info("[AGENT] Launching Autonomous ReAct loop for user goal: '%s'", user_input)
        agent = AutonomousReActAgent(
            llm=orchestrator.llm,
            max_iterations=5,
            contextual_element=orchestrator.state.get_last_focused_element(),
        )

        agent_res = agent.run(
            goal=user_input,
            language=effective_lang,
            state_context=state_ctx,
        )

        final_resp = agent_res.final_answer or (
            "Tugas telah selesai diproses, sir." if is_id else "Task processing completed, sir."
        )

        # Update session state turns
        orchestrator.state.add_turn(user_input, final_resp)

        # Record last actions and observations in state if tools were executed
        if agent_res.steps:
            for st in agent_res.steps:
                if st.action:
                    orchestrator.state.set_last_action(st.action, str(st.action_input), "ReActAgent", True)

        yield final_resp

    return route, _agentic_gen()
