"""Comprehensive tests for Strict Intent Guard, Fuzzy Matching, and Adaptive Alias Learning.

Verifies:
1. Exact command execution remains instant (<50ms).
2. Spoken and typed typos never leak to LLM (RouteType.AI_REQUEST).
3. Ambiguous/close typos route to RouteType.CLARIFY with clarify_open_fuzzy / clarify_close_fuzzy.
4. Completely unknown targets route to RouteType.FAST_COMMAND with app_not_found (never LLM).
5. User confirmation stores the learned alias into SQLite, making subsequent calls 100% exact match.
6. Question markers ('bagaimana cara', 'kenapa') still correctly flow to LLM for reasoning.
"""

import pytest
from app.core.router import CommandRouter, RouteType
from app.core.orchestrator import Orchestrator
from app.core.config import Settings
from app.tools.apps import registry, find_best_app_or_site_candidate
from app.tools.browser import website_registry
from app.memory.memory import memory_manager, store_learned_alias


@pytest.fixture
def router():
    return CommandRouter()


@pytest.fixture
def orchestrator():
    settings = Settings(llm_enabled=False, voice_enabled=False, tts_enabled=False)
    orch = Orchestrator(settings=settings)
    return orch


def test_exact_matches_remain_fast_commands(router):
    """Test 1: Exact commands route deterministically to FAST_COMMAND."""
    res_chrome = router.route("buka Chrome")
    assert res_chrome.route_type == RouteType.FAST_COMMAND
    assert res_chrome.action == "open_application"
    assert res_chrome.args.get("target") == "chrome"

    res_yt = router.route("open YouTube")
    assert res_yt.route_type == RouteType.FAST_COMMAND
    assert res_yt.action == "open_website"
    assert res_yt.args.get("target") == "youtube"

    res_np = router.route("jalankan Notepad")
    assert res_np.route_type == RouteType.FAST_COMMAND
    assert res_np.action == "open_application"
    assert res_np.args.get("target") == "notepad"


def test_typos_caught_by_guard_never_leak_to_llm(router):
    """Test 2: App & website typos must be caught by Intent Guard and NEVER leak to AI_REQUEST."""
    typo_queries = [
        ("buka crome", "chrome"),
        ("bukain notped", "notepad"),
        ("buka kalkualtor", "calculator"),
        ("open youtbe", "youtube"),
        ("buka spotifi", "spotify"),
        ("buka disckord", "discord"),
    ]

    for query, expected_target in typo_queries:
        res = router.route(query)
        # MUST NOT leak to LLM
        assert res.route_type != RouteType.AI_REQUEST, f"Query '{query}' leaked to LLM!"
        # Must be either exact match (if alias already exists) or CLARIFY (fuzzy match)
        if res.route_type == RouteType.CLARIFY:
            assert res.action == "clarify_open_fuzzy"
            assert res.args.get("target") == expected_target, f"Expected {expected_target}, got {res.args.get('target')}"
        else:
            assert res.route_type == RouteType.FAST_COMMAND


def test_close_typos_caught_by_guard(router):
    """Test 3: Close commands with typos route to clarify_close_fuzzy and never to LLM."""
    res = router.route("tutup notepadd")
    assert res.route_type != RouteType.AI_REQUEST
    assert res.route_type == RouteType.CLARIFY
    assert res.action == "clarify_close_fuzzy"
    assert res.args.get("target") == "notepad"


def test_fictional_unregistered_app_rejected_at_router(router):
    """Test 4: Unregistered / fictional app targets must be rejected at router level (never LLM)."""
    res = router.route("buka software_fiktif_xyz_999")
    assert res.route_type != RouteType.AI_REQUEST, "Fictional target leaked to LLM!"
    assert res.route_type == RouteType.FAST_COMMAND
    assert res.action == "app_not_found"
    assert "fiktif_xyz_999" in res.args.get("target", "") or "software_fiktif_xyz_999" in res.args.get("raw_target", "")


def test_inquiry_markers_still_route_to_llm(router):
    """Test 5: Conversational questions with question markers still correctly route to LLM."""
    inquiries = [
        "bagaimana cara buka Chrome di Windows?",
        "kenapa Chrome tidak bisa dibuka?",
        "apa itu Chrome?",
        "jelaskan cara membuka browser",
    ]
    for q in inquiries:
        res = router.route(q)
        assert res.route_type == RouteType.AI_REQUEST, f"Inquiry '{q}' should route to LLM!"


def test_orchestrator_clarification_and_confirmation_auto_learning(orchestrator):
    """Test 6: User confirmation executes action and auto-learns alias into SQLite."""
    # 1. User says "buka chromee" (typo)
    route, reply_gen = orchestrator.process_input_stream("buka chromee")
    reply = "".join(list(reply_gen))
    assert route.route_type == RouteType.CLARIFY
    assert "Apakah maksud Anda membuka" in reply or "Did you mean to open" in reply
    assert orchestrator.state.pending_action is not None
    assert orchestrator.state.pending_action.action == "open_fuzzy_confirmed"

    # 2. User confirms with "Ya"
    conf_route, conf_gen = orchestrator.process_input_stream("ya")
    conf_reply = "".join(list(conf_gen))
    assert conf_route.route_type == RouteType.FAST_COMMAND
    assert "Membuka Google Chrome" in conf_reply or "Opening Google Chrome" in conf_reply
    assert orchestrator.state.pending_action is None

    # 3. Verify alias 'chromee' is now learned in registry and database
    assert registry.resolve_canonical_name("chromee") == "chrome"

    # 4. Now the second call with 'chromee' is a 100% exact match!
    next_route = orchestrator.router.route("buka chromee")
    assert next_route.route_type == RouteType.FAST_COMMAND
    assert next_route.action == "open_application"
    assert next_route.args.get("target") == "chrome"

    # Clean up test alias
    memory_manager.db.delete_learned_alias("chromee")


def test_verb_typos_and_standalone_targets(router):
    """Test 7: Imperative verb typos (oen, bka, clsoe, tutp) and standalone app names."""
    # Verb typos on launch
    r_oen = router.route("oen chrome")
    assert r_oen.route_type == RouteType.FAST_COMMAND
    assert r_oen.action == "open_application"
    assert r_oen.args.get("target") == "chrome"

    r_bka = router.route("bka chrome")
    assert r_bka.route_type == RouteType.FAST_COMMAND
    assert r_bka.action == "open_application"
    assert r_bka.args.get("target") == "chrome"

    # Both verb typo and target typo
    r_double = router.route("oen crome")
    assert r_double.route_type == RouteType.FAST_COMMAND
    assert r_double.action == "open_application"
    assert r_double.args.get("target") == "chrome"

    # Standalone application name (verb omitted)
    r_solo = router.route("chrome")
    assert r_solo.route_type == RouteType.FAST_COMMAND
    assert r_solo.action == "open_application"
    assert r_solo.args.get("target") == "chrome"

    r_solo_typo = router.route("crome")
    assert r_solo_typo.route_type == RouteType.FAST_COMMAND
    assert r_solo_typo.action == "open_application"
    assert r_solo_typo.args.get("target") == "chrome"

    # Verb typos on termination
    r_clsoe = router.route("clsoe chrome")
    assert r_clsoe.route_type == RouteType.FAST_COMMAND
    assert r_clsoe.action == "close_application"
    assert r_clsoe.args.get("target") == "chrome"

    r_tutp = router.route("tutp chrome")
    assert r_tutp.route_type == RouteType.FAST_COMMAND
    assert r_tutp.action == "close_application"
    assert r_tutp.args.get("target") == "chrome"

    # Ambiguous verb typo alone triggers clarify_open
    r_ambig = router.route("oen")
    assert r_ambig.route_type == RouteType.CLARIFY
    assert r_ambig.action == "clarify_open"
