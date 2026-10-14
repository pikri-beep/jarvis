"""Confirmation, Clarification, and Paused Task handlers for JARVIS."""

import logging
import re
import time
from typing import Any, Generator, Optional, Tuple

from app.core.logger import setup_logger
from app.core.router import RouteResult, RouteType

logger = setup_logger("jarvis.handlers.confirmation")

_AFFIRMATIVES = {
    "ya", "yes", "y", "buka", "lanjut", "lanjutkan", "oke", "ok",
    "sure", "proceed", "confirm", "silakan", "buka saja", "boleh"
}
_NEGATIVES = {
    "tidak", "batal", "batalkan", "jangan", "no", "cancel",
    "stop", "nevermind", "enggak", "gak", "nanti saja"
}


def handle_pending_confirmation(
    orchestrator: Any,
    user_input: str,
    effective_lang: str,
    is_id: bool,
) -> Optional[Tuple[RouteResult, Generator[str, None, None]]]:
    """Handles an active pending action requiring user confirmation (e.g. WhatsApp, fuzzy targets)."""
    if not orchestrator.state.pending_action:
        return None

    pending = orchestrator.state.pending_action
    cleaned_lower = user_input.strip().lower()

    words_set = set(re.findall(r"\b[a-z]+\b", cleaned_lower))
    is_confirmed = bool(words_set & _AFFIRMATIVES) or cleaned_lower in _AFFIRMATIVES
    is_cancelled = bool(words_set & _NEGATIVES) or cleaned_lower in _NEGATIVES

    # Check clarification follow-up actions (clarify_open, clarify_close, clarify_type)
    if pending.action in ("clarify_open", "clarify_close", "clarify_type"):
        if is_cancelled:
            orchestrator.state.pending_action = None
            logger.info('[CLARIFY] User cancelled pending clarification for %s', pending.action)

            def _cancel_gen():
                out = "Baik sir, perintah dibatalkan." if is_id else "Understood, command cancelled sir."
                orchestrator.state.add_turn(user_input, out)
                yield out

            route = RouteResult(
                route_type=RouteType.FAST_COMMAND,
                action=f"cancel_{pending.action}",
                args={"language": effective_lang},
                raw_input=user_input,
                description=f"Cancelled {pending.action}",
            )
            return route, _cancel_gen()

        # Otherwise, user provided the follow-up parameter/target (e.g. "Chrome", "YouTube")
        orchestrator.state.pending_action = None
        clean_arg = user_input.strip()

        # If user issued a fresh independent command (e.g. "ketik", "tutup", or a fast command), route directly
        r_direct = orchestrator.router.route(clean_arg)
        if r_direct.route_type in (RouteType.FAST_COMMAND, RouteType.CLARIFY, RouteType.WEB_SEARCH):
            if r_direct.action != "app_not_found":
                return orchestrator.process_input_stream(clean_arg)

        if pending.action == "clarify_open":
            if not re.match(r"^(?:buka|open|launch|start|run|jalankan)\s+", clean_arg, re.I):
                clean_arg = f"buka {clean_arg}"
        elif pending.action == "clarify_close":
            if not re.match(r"^(?:tutup|close|quit|exit|matikan|hentikan)\s+", clean_arg, re.I):
                clean_arg = f"tutup {clean_arg}"
        elif pending.action == "clarify_type":
            if not re.match(r"^(?:ketik|type)\s+", clean_arg, re.I):
                clean_arg = f"ketik {clean_arg}"

        logger.info('[CLARIFY] Synthesizing follow-up command: "%s"', clean_arg)
        return orchestrator.process_input_stream(clean_arg)

    if is_confirmed:
        if pending.action == "confirm_memory_conflict":
            orchestrator.state.pending_action = None
            conf_data = pending.args.get("conflict", {})
            from app.memory.schemas import MemoryConflict, MemoryItem
            from app.memory.memory import memory_manager

            c_item = MemoryItem(
                key=conf_data.get("key", ""),
                value=conf_data.get("new_value", ""),
                category=conf_data.get("category", "general"),
                description=conf_data.get("existing_description", ""),
            )
            conflict_obj = MemoryConflict(
                item=c_item,
                existing_value=conf_data.get("existing_value", ""),
                existing_description=conf_data.get("existing_description", ""),
            )
            success, out = memory_manager.apply_conflict_resolution(conflict_obj, approved=True, language=effective_lang)
            orchestrator.state.add_turn(user_input, out)

            def _mem_confirm_gen():
                yield out

            route = RouteResult(
                route_type=RouteType.FAST_COMMAND,
                action="confirm_memory_conflict",
                args={"key": c_item.key, "value": c_item.value},
                raw_input=user_input,
                description=f"Confirmed memory conflict update for {c_item.key}",
            )
            return route, _mem_confirm_gen()

        if pending.action == "clarify_ml_intent":
            orchestrator.state.pending_action = None
            p_intent = pending.args.get("intent", "")
            p_action = pending.args.get("action", "")
            p_target = pending.args.get("target", "")
            p_args = pending.args.get("args", {})
            raw_input = pending.args.get("raw_input", "")

            # Active Learning: Append confirmed utterance to dataset & retrain model!
            try:
                from app.ai.ml_classifier import get_ml_classifier
                ml_clf = get_ml_classifier()
                ml_clf.add_example_and_retrain(raw_input, p_intent, p_target)
                logger.info('[ACTIVE_LEARNING] Learned new utterance "%s" -> intent=%s', raw_input, p_intent)
            except Exception as ml_err:
                logger.warning("Active learning update failed: %s", ml_err)

            # Dispatch confirmed action
            from app.core.handlers.fast_command_handler import handle_fast_command, handle_web_search
            r_type = RouteType.WEB_SEARCH if p_intent == "search_web" else RouteType.FAST_COMMAND
            synth_route = RouteResult(
                route_type=r_type,
                action=p_action,
                args=dict(p_args),
                raw_input=raw_input,
                description=f"ML intent confirmed: {p_intent}",
            )
            if r_type == RouteType.WEB_SEARCH:
                return handle_web_search(orchestrator, synth_route, user_input, effective_lang, is_id)
            return handle_fast_command(orchestrator, synth_route, user_input, effective_lang, is_id)

        orchestrator.state.pending_action = None

        def _confirm_gen():
            if pending.action == "open_application":
                from app.tools.apps import launch_application
                t_tool_start = time.time()
                try:
                    success, display_name, msg = launch_application(pending.target)
                    elapsed_ms = (time.time() - t_tool_start) * 1000.0
                    orchestrator.state.set_last_action("open_application", pending.target, display_name, success)
                    if success:
                        logger.info('[TOOL] name="open_application" target="%s" status="SUCCESS" latency=%.1fms', pending.target, elapsed_ms)
                        out = f"Membuka {display_name}, sir." if is_id else f"Opening {display_name}, sir."
                    else:
                        logger.warning('[TOOL] name="open_application" target="%s" status="FAILURE" error="%s" latency=%.1fms', pending.target, msg, elapsed_ms)
                        retry_txt = " Silakan periksa kembali atau coba ulangi perintah, sir." if is_id else " Please check if it is installed or try again, sir."
                        out = f"Maaf sir, saya tidak dapat membuka {display_name}. {msg}.{retry_txt}" if is_id else f"I couldn't open {display_name}, sir. {msg}.{retry_txt}"
                except Exception as exc:
                    logger.exception('[TOOL] name="open_application" target="%s" status="FAILURE" exception="%s"', pending.target, exc)
                    out = f"Terjadi kesalahan saat membuka {pending.display_name}, sir: {exc}" if is_id else f"An error occurred while opening {pending.display_name}, sir: {exc}"
                orchestrator.state.add_turn(user_input, out)
                yield out

            elif pending.action == "open_fuzzy_confirmed":
                t_tool_start = time.time()
                target_type = pending.args.get("target_type", "app")
                raw_alias = pending.args.get("raw_alias", "")
                display_name = pending.display_name

                try:
                    if target_type == "website":
                        from app.tools.browser import launch_website
                        success, _, display_name, msg = launch_website(pending.target)
                    else:
                        from app.tools.apps import launch_application
                        success, display_name, msg = launch_application(pending.target)

                    elapsed_ms = (time.time() - t_tool_start) * 1000.0
                    orchestrator.state.set_last_action("open_application", pending.target, display_name, success)

                    # Adaptive Learning: Auto-learn alias into SQLite and runtime registries
                    if success and raw_alias and raw_alias.lower() != pending.target.lower():
                        from app.memory.memory import store_learned_alias
                        store_learned_alias(raw_alias, pending.target, target_type=target_type)
                        logger.info('[LEARNING] Auto-learned alias "%s" -> "%s" (%s)', raw_alias, pending.target, target_type)

                    if success:
                        logger.info('[TOOL] name="open_fuzzy_confirmed" target="%s" status="SUCCESS" latency=%.1fms', pending.target, elapsed_ms)
                        out = f"Membuka {display_name}, sir." if is_id else f"Opening {display_name}, sir."
                    else:
                        logger.warning('[TOOL] name="open_fuzzy_confirmed" target="%s" status="FAILURE" error="%s" latency=%.1fms', pending.target, msg, elapsed_ms)
                        out = f"Maaf sir, saya tidak dapat membuka {display_name}. {msg}." if is_id else f"I couldn't open {display_name}, sir. {msg}."
                except Exception as exc:
                    logger.exception('[TOOL] name="open_fuzzy_confirmed" target="%s" status="FAILURE" exception="%s"', pending.target, exc)
                    out = f"Terjadi kesalahan saat membuka {pending.display_name}, sir: {exc}" if is_id else f"An error occurred while opening {pending.display_name}, sir: {exc}"
                orchestrator.state.add_turn(user_input, out)
                yield out

            elif pending.action == "close_fuzzy_confirmed":
                t_tool_start = time.time()
                raw_alias = pending.args.get("raw_alias", "")
                try:
                    from app.tools.apps import close_application
                    success, display_name, msg = close_application(pending.target)
                    elapsed_ms = (time.time() - t_tool_start) * 1000.0
                    orchestrator.state.set_last_action("close_application", pending.target, display_name, success)

                    if success and raw_alias and raw_alias.lower() != pending.target.lower():
                        from app.memory.memory import store_learned_alias
                        store_learned_alias(raw_alias, pending.target, target_type="app")
                        logger.info('[LEARNING] Auto-learned alias "%s" -> "%s" (app)', raw_alias, pending.target)

                    if success:
                        out = f"Berhasil menutup {display_name}, sir." if is_id else f"Successfully closed {display_name}, sir."
                    else:
                        out = msg
                except Exception as exc:
                    out = f"Terjadi kesalahan saat menutup {pending.display_name}, sir: {exc}" if is_id else f"Error closing {pending.display_name}, sir: {exc}"
                orchestrator.state.add_turn(user_input, out)
                yield out

        route = RouteResult(
            route_type=RouteType.FAST_COMMAND,
            action=f"confirm_{pending.action}",
            args={"target": pending.target, "language": effective_lang},
            raw_input=user_input,
            description=f"Confirmed {pending.action} for {pending.target}",
        )
        return route, _confirm_gen()

    elif is_cancelled:
        orchestrator.state.pending_action = None
        logger.info('[TOOL] name="%s" target="%s" status="CANCELLED"', pending.action, pending.target)

        if pending.action == "confirm_memory_conflict":
            conf_data = pending.args.get("conflict", {})
            from app.memory.schemas import MemoryConflict, MemoryItem
            from app.memory.memory import memory_manager

            c_item = MemoryItem(
                key=conf_data.get("key", ""),
                value=conf_data.get("new_value", ""),
                category=conf_data.get("category", "general"),
                description=conf_data.get("existing_description", ""),
            )
            conflict_obj = MemoryConflict(
                item=c_item,
                existing_value=conf_data.get("existing_value", ""),
                existing_description=conf_data.get("existing_description", ""),
            )
            _, out = memory_manager.apply_conflict_resolution(conflict_obj, approved=False, language=effective_lang)
            orchestrator.state.add_turn(user_input, out)

            def _mem_cancel_gen():
                yield out

            route = RouteResult(
                route_type=RouteType.FAST_COMMAND,
                action="cancel_memory_conflict",
                args={"key": c_item.key},
                raw_input=user_input,
                description=f"Cancelled memory conflict update for {c_item.key}",
            )
            return route, _mem_cancel_gen()

        def _cancel_gen():
            if pending.action == "clarify_ml_intent":
                out = "Baik sir, perintah dibatalkan." if is_id else "Understood, command cancelled sir."
            else:
                out = (
                    f"Baik sir, pembukaan {pending.display_name} dibatalkan."
                    if is_id
                    else f"Understood, sir. {pending.display_name} launch cancelled."
                )
            orchestrator.state.add_turn(user_input, out)
            yield out

        route = RouteResult(
            route_type=RouteType.FAST_COMMAND,
            action=f"cancel_{pending.action}",
            args={"target": pending.target, "language": effective_lang},
            raw_input=user_input,
            description=f"Cancelled {pending.action} for {pending.target}",
        )
        return route, _cancel_gen()
    else:
        # If neither clear confirmation nor cancellation, cancel pending action and proceed
        orchestrator.state.pending_action = None
        return None


def handle_pending_vision_task(
    orchestrator: Any,
    user_input: str,
    effective_lang: str,
    is_id: bool,
) -> Optional[Tuple[RouteResult, Generator[str, None, None]]]:
    """Resumes a paused vision task waiting for user parameter."""
    if not orchestrator.state.pending_vision_task:
        return None

    paused_task = orchestrator.state.pending_vision_task
    from app.core.vision_agent import VisionAgent
    agent = VisionAgent(settings=orchestrator.settings, max_steps=8)
    res = agent.resume_task(paused_task, user_response=user_input)
    if res.is_paused:
        orchestrator.state.set_pending_vision_task(res.state)
    else:
        orchestrator.state.clear_pending_vision_task()

    orchestrator.state.set_last_action("vision_task", paused_task.goal, "Vision Agent", res.status == "COMPLETED")

    def _resume_gen():
        out_msg = res.display_output if res.display_output else res.spoken_output
        orchestrator.state.add_turn(user_input, res.spoken_output)
        yield out_msg

    route = RouteResult(
        route_type=RouteType.FAST_COMMAND,
        action="resume_vision_task",
        args={"goal": paused_task.goal, "user_response": user_input},
        raw_input=user_input,
        description=f"Resumed vision task: {paused_task.goal}",
    )
    return route, _resume_gen()


def handle_clarification(
    orchestrator: Any,
    route: RouteResult,
    user_input: str,
    effective_lang: str,
    is_id: bool,
) -> Tuple[RouteResult, Generator[str, None, None]]:
    """Handles clarification requests for ambiguous user commands."""
    def _clarify_gen():
        from app.core.state import PendingAction

        if route.action == "clarify_open":
            orchestrator.state.pending_action = PendingAction(
                action="clarify_open",
                target="",
                display_name="aplikasi",
                args={"raw_input": user_input},
            )
            out = (
                "Aplikasi atau situs apa yang ingin Anda buka, sir?"
                if is_id
                else "Which application or website would you like me to open, sir?"
            )
        elif route.action == "clarify_close":
            orchestrator.state.pending_action = PendingAction(
                action="clarify_close",
                target="",
                display_name="aplikasi",
                args={"raw_input": user_input},
            )
            out = (
                "Aplikasi apa yang ingin Anda tutup, sir?"
                if is_id
                else "Which application would you like me to close, sir?"
            )
        elif route.action == "clarify_type":
            orchestrator.state.pending_action = PendingAction(
                action="clarify_type",
                target="",
                display_name="teks",
                args={"raw_input": user_input},
            )
            out = (
                "Teks apa yang ingin Anda ketik, sir?"
                if is_id
                else "What text would you like me to type, sir?"
            )
        elif route.action == "clarify_vision":
            out = (
                "Tugas apa yang ingin Anda jalankan di layar, sir? (Contoh: '/vision setel timer 5 menit' atau 'lihat layar dan buka YouTube')."
                if is_id
                else "What task would you like me to perform on screen, sir? (e.g. '/vision set timer for 5 minutes')."
            )
        elif route.action == "clarify_open_fuzzy":
            from app.core.state import PendingAction
            t_name = route.args.get("display_name", route.args.get("target", ""))
            t_type = route.args.get("target_type", "app")
            type_str = "situs" if t_type == "website" else "aplikasi"
            type_en = "website" if t_type == "website" else "application"
            orchestrator.state.pending_action = PendingAction(
                action="open_fuzzy_confirmed",
                target=route.args.get("target", ""),
                display_name=t_name,
                args={"target_type": t_type, "raw_alias": route.args.get("raw_target", "")},
            )
            out = (
                f"Apakah maksud Anda membuka {type_str} {t_name}, sir?"
                if is_id
                else f"Did you mean to open the {type_en} {t_name}, sir?"
            )
        elif route.action == "clarify_close_fuzzy":
            from app.core.state import PendingAction
            t_name = route.args.get("display_name", route.args.get("target", ""))
            orchestrator.state.pending_action = PendingAction(
                action="close_fuzzy_confirmed",
                target=route.args.get("target", ""),
                display_name=t_name,
                args={"raw_alias": route.args.get("raw_target", "")},
            )
            out = (
                f"Apakah maksud Anda menutup aplikasi {t_name}, sir?"
                if is_id
                else f"Did you mean to close {t_name}, sir?"
            )
        elif route.action == "clarify_ml_intent":
            from app.core.state import PendingAction
            p_intent = route.args.get("intent", "")
            p_target = route.args.get("target", "")

            action_desc_id = {
                "open_app": f"membuka aplikasi {p_target}",
                "close_app": f"menutup aplikasi {p_target}",
                "open_website": f"membuka situs {p_target}",
                "media_play_pause": "memutar atau menjeda musik",
                "media_next": "memutar lagu berikutnya",
                "volume_up": "menaikkan volume",
                "volume_down": "menurunkan volume",
                "toggle_mute": "menonaktifkan atau menyalakan suara",
                "take_screenshot": "mengambil tangkapan layar",
                "lock_screen": "mengunci komputer",
                "get_time": "mengetahui waktu saat ini",
                "get_date": "mengetahui tanggal hari ini",
                "system_info": "memeriksa spesifikasi sistem",
                "battery_status": "memeriksa status baterai",
                "open_new_tab": "membuka tab browser baru",
                "close_tab": "menutup tab browser",
                "search_web": f"mencari '{p_target}' di web",
            }.get(p_intent, f"menjalankan perintah {p_intent}")

            action_desc_en = {
                "open_app": f"open the {p_target} application",
                "close_app": f"close the {p_target} application",
                "open_website": f"open the {p_target} website",
                "media_play_pause": "play or pause music",
                "media_next": "play the next track",
                "volume_up": "turn up the volume",
                "volume_down": "turn down the volume",
                "toggle_mute": "toggle mute audio",
                "take_screenshot": "take a screenshot",
                "lock_screen": "lock the computer",
                "get_time": "check current time",
                "get_date": "check today's date",
                "system_info": "check system specs",
                "battery_status": "check battery status",
                "open_new_tab": "open a new browser tab",
                "close_tab": "close the browser tab",
                "search_web": f"search web for '{p_target}'",
            }.get(p_intent, f"execute {p_intent}")

            orchestrator.state.pending_action = PendingAction(
                action="clarify_ml_intent",
                target=p_target,
                display_name=p_target or p_intent,
                args=dict(route.args),
            )
            out = (
                f"Apakah maksud Anda ingin {action_desc_id}, sir?"
                if is_id
                else f"Did you mean you want to {action_desc_en}, sir?"
            )
        else:
            out = (
                "Mohon jelaskan perintah Anda lebih spesifik, sir."
                if is_id
                else "Please specify your request further, sir."
            )
        orchestrator.state.add_turn(user_input, out)
        yield out

    return route, _clarify_gen()
