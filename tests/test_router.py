"""Unit tests for the command router."""

import pytest
from app.core.router import CommandRouter, RouteType


@pytest.fixture
def router():
    return CommandRouter()


def test_terminal_commands(router):
    res_help = router.route("/help")
    assert res_help.route_type == RouteType.TERMINAL_COMMAND
    assert res_help.action == "help"

    res_exit = router.route("exit")
    assert res_exit.route_type == RouteType.TERMINAL_COMMAND
    assert res_exit.action == "exit"

    res_status = router.route("/status")
    assert res_status.route_type == RouteType.TERMINAL_COMMAND
    assert res_status.action == "status"

    res_clear = router.route("clear")
    assert res_clear.route_type == RouteType.TERMINAL_COMMAND
    assert res_clear.action == "clear"

    res_voice = router.route("/voice")
    assert res_voice.route_type == RouteType.TERMINAL_COMMAND
    assert res_voice.action == "toggle_voice"

    res_ptt = router.route("/ptt")
    assert res_ptt.route_type == RouteType.TERMINAL_COMMAND
    assert res_ptt.action == "toggle_voice"

    res_mic = router.route("/mic")
    assert res_mic.route_type == RouteType.TERMINAL_COMMAND
    assert res_mic.action == "list_devices"

    res_dev = router.route("devices")
    assert res_dev.route_type == RouteType.TERMINAL_COMMAND
    assert res_dev.action == "list_devices"


def test_fast_commands(router):
    res_chrome = router.route("Open Chrome")
    assert res_chrome.route_type == RouteType.FAST_COMMAND
    assert res_chrome.action == "open_application"
    assert res_chrome.args.get("target") == "chrome"

    # Test conversational wake prefix stripping
    res_jarvis_chrome = router.route("Jarvis, open Chrome")
    assert res_jarvis_chrome.route_type == RouteType.FAST_COMMAND
    assert res_jarvis_chrome.action == "open_application"
    assert res_jarvis_chrome.args.get("target") == "chrome"

    # Test time and date queries
    res_time = router.route("What time is it?")
    assert res_time.route_type == RouteType.FAST_COMMAND
    assert res_time.action == "get_time"

    res_time2 = router.route("Jarvis, current time")
    assert res_time2.route_type == RouteType.FAST_COMMAND
    assert res_time2.action == "get_time"

    res_date = router.route("What is today's date?")
    assert res_date.route_type == RouteType.FAST_COMMAND
    assert res_date.action == "get_date"

    # Test system specs and battery
    res_sys = router.route("System specs")
    assert res_sys.route_type == RouteType.FAST_COMMAND
    assert res_sys.action == "system_info"

    res_bat = router.route("Battery status")
    assert res_bat.route_type == RouteType.FAST_COMMAND
    assert res_bat.action == "battery_status"

    res_screen = router.route("take a screenshot")
    assert res_screen.route_type == RouteType.FAST_COMMAND
    assert res_screen.action == "take_screenshot"

    res_lock = router.route("lock computer")
    assert res_lock.route_type == RouteType.FAST_COMMAND
    assert res_lock.action == "lock_screen"

    res_vol = router.route("increase the volume")
    assert res_vol.route_type == RouteType.FAST_COMMAND
    assert res_vol.action == "volume_up"


def test_web_dependent_queries(router):
    res_weather = router.route("What is the weather tomorrow in Paris?")
    assert res_weather.route_type == RouteType.WEB_DEPENDENT
    assert res_weather.action == "search_web"

    res_news = router.route("Show me the latest news")
    assert res_news.route_type == RouteType.WEB_DEPENDENT


def test_ai_requests(router):
    res_ai = router.route("Explain quantum entanglement in simple terms.")
    assert res_ai.route_type == RouteType.AI_REQUEST
    assert res_ai.action == "llm_chat"

    res_code = router.route("Write a Python function to compute Fibonacci numbers.")
    assert res_code.route_type == RouteType.AI_REQUEST

    # Indonesian AI requests
    res_id_ai = router.route("Saya ingin mengetahui perbedaan RAM dan SSD.")
    assert res_id_ai.route_type == RouteType.AI_REQUEST

    res_id_jadwal = router.route("JARVIS, tolong jelaskan jadwal saya hari ini.")
    assert res_id_jadwal.route_type == RouteType.AI_REQUEST


def test_indonesian_fast_commands(router):
    # Utterance 2: "Baik, sekarang buka Chrome."
    res_buka = router.route("Baik, sekarang buka Chrome.")
    assert res_buka.route_type == RouteType.FAST_COMMAND
    assert res_buka.action == "open_application"
    assert res_buka.args.get("target") == "chrome"

    # Variations of Indonesian commands
    res_tutup = router.route("Tolong tutup notepad")
    assert res_tutup.route_type == RouteType.FAST_COMMAND
    assert res_tutup.action == "close_application"
    assert res_tutup.args.get("target") == "notepad"

    res_jam = router.route("Jam berapa sekarang?")
    assert res_jam.route_type == RouteType.FAST_COMMAND
    assert res_jam.action == "get_time"

    res_tgl = router.route("Tanggal berapa hari ini?")
    assert res_tgl.route_type == RouteType.FAST_COMMAND
    assert res_tgl.action == "get_date"

    res_ss = router.route("Ambil tangkapan layar")
    assert res_ss.route_type == RouteType.FAST_COMMAND
    assert res_ss.action == "take_screenshot"

    # App alias normalization in command context
    res_kromya = router.route("Tolong buka kromya")
    assert res_kromya.route_type == RouteType.FAST_COMMAND
    assert res_kromya.action == "open_application"
    assert res_kromya.args.get("target") == "chrome"

    res_google_chrome = router.route("Sekarang buka Google Chrome.")
    assert res_google_chrome.route_type == RouteType.FAST_COMMAND
    assert res_google_chrome.action == "open_application"
    assert res_google_chrome.args.get("target") == "chrome"

    # Terminal /lang commands
    res_lang_id = router.route("/lang id")
    assert res_lang_id.route_type == RouteType.TERMINAL_COMMAND
    assert res_lang_id.action == "set_language"
    assert res_lang_id.args.get("language") == "id"

    res_lang_en = router.route("/lang en")
    assert res_lang_en.action == "set_language"
    assert res_lang_en.args.get("language") == "en"

    res_kunci = router.route("Kunci komputer")
    assert res_kunci.route_type == RouteType.FAST_COMMAND
    assert res_kunci.action == "lock_screen"

    # Additional application controls
    res_wa = router.route("Tolong buka WhatsApp")
    assert res_wa.route_type == RouteType.FAST_COMMAND
    assert res_wa.action == "open_application"
    assert res_wa.args.get("target") == "whatsapp"

    res_buka_wa = router.route("Buka wa")
    assert res_buka_wa.route_type == RouteType.FAST_COMMAND
    assert res_buka_wa.args.get("target") == "whatsapp"

    res_settings = router.route("Buka pengaturan")
    assert res_settings.route_type == RouteType.FAST_COMMAND
    assert res_settings.args.get("target") == "settings"

    res_calc = router.route("Buka kalkulator")
    assert res_calc.route_type == RouteType.FAST_COMMAND
    assert res_calc.args.get("target") == "calculator"

    res_explorer = router.route("Buka file explorer")
    assert res_explorer.route_type == RouteType.FAST_COMMAND
    assert res_explorer.args.get("target") == "explorer"

    res_app_chrome = router.route("Buka aplikasi Chrome")
    assert res_app_chrome.route_type == RouteType.FAST_COMMAND
    assert res_app_chrome.args.get("target") == "chrome"

    res_edge = router.route("Open Edge")
    assert res_edge.route_type == RouteType.FAST_COMMAND
    assert res_edge.args.get("target") == "edge"


def test_user_reported_edge_cases(router):
    """Verifies edge cases reported by user: gemini, unmute, volume percentage, phutar typo."""
    # 1. Buka Gemini and web apps
    r_gem = router.route("buka gemini")
    assert r_gem.route_type == RouteType.FAST_COMMAND
    assert r_gem.action == "open_website"
    assert r_gem.args.get("target") == "gemini"

    r_gem_chrome = router.route("buka gemini di google chrome")
    assert r_gem_chrome.route_type == RouteType.FAST_COMMAND
    assert r_gem_chrome.action == "open_website"
    assert r_gem_chrome.args.get("target") == "gemini"

    # 2. Unmute
    r_unmute = router.route("unmute")
    assert r_unmute.route_type == RouteType.FAST_COMMAND
    assert r_unmute.action == "toggle_mute"

    # 3. Volume with percentage
    r_vol = router.route("kecilkan suara 20%")
    assert r_vol.route_type == RouteType.FAST_COMMAND
    assert r_vol.action == "volume_down"
    assert r_vol.args.get("percentage") == 20
    assert r_vol.args.get("steps") == 10

    r_vol_up = router.route("naikkan volume 10%")
    assert r_vol_up.route_type == RouteType.FAST_COMMAND
    assert r_vol_up.action == "volume_up"
    assert r_vol_up.args.get("percentage") == 10
    assert r_vol_up.args.get("steps") == 5

    # 4. Typo phutar
    r_phutar = router.route("phutar lagu sambulah by denada")
    assert r_phutar.route_type == RouteType.FAST_COMMAND
    assert r_phutar.action == "play_music"
    assert "sambulah by denada" in r_phutar.args.get("query")

    # 5. Discord, task manager typo, screenshot, battery, and lock screen
    r_disc = router.route("Open discord")
    assert r_disc.route_type == RouteType.FAST_COMMAND
    assert r_disc.action == "open_application"
    assert r_disc.args.get("target") == "discord"

    r_tm = router.route("opem task manager")
    assert r_tm.route_type == RouteType.FAST_COMMAND
    assert r_tm.action == "open_application"
    assert r_tm.args.get("target") == "taskmgr"

    r_ss = router.route("screenshot layar ku")
    assert r_ss.route_type == RouteType.FAST_COMMAND
    assert r_ss.action == "take_screenshot"

    r_bat = router.route("Berapa Batrai saya sekarang?")
    assert r_bat.route_type == RouteType.FAST_COMMAND
    assert r_bat.action == "battery_status"

    r_lock = router.route("lock my screen")
    assert r_lock.route_type == RouteType.FAST_COMMAND
    assert r_lock.action == "lock_screen"

    # 6. Lock screen with 'saya'
    r_lock_saya = router.route("Kunci layar saya")
    assert r_lock_saya.route_type == RouteType.FAST_COMMAND
    assert r_lock_saya.action == "lock_screen"

    r_lock_komp = router.route("kunci komputer saya")
    assert r_lock_komp.route_type == RouteType.FAST_COMMAND
    assert r_lock_komp.action == "lock_screen"

    # 7. STT commas in voice commands
    r_play_comma = router.route("Play, creep by radio hat.")
    assert r_play_comma.route_type == RouteType.FAST_COMMAND
    assert r_play_comma.action == "play_music"
    assert "creep by radio hat" in r_play_comma.args.get("query")

    r_play_comma2 = router.route("Play, clip, buy radio hat.")
    assert r_play_comma2.route_type == RouteType.FAST_COMMAND
    assert r_play_comma2.action == "play_music"

    # 8. Bare /vision requires clarification and does not execute unprompted timer
    r_vis_bare = router.route("/vision")
    assert r_vis_bare.route_type == RouteType.CLARIFY
    assert r_vis_bare.action == "clarify_vision"

    r_vis_goal = router.route("/vision setel timer 5 menit")
    assert r_vis_goal.route_type == RouteType.FAST_COMMAND
    assert r_vis_goal.action == "vision_task"
    assert r_vis_goal.args.get("goal") == "setel timer 5 menit"


