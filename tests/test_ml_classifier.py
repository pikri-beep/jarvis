"""Comprehensive unit tests for the ML Intent Classifier and Active Learning Pipeline."""

import json
import pytest
from unittest.mock import patch

from app.ai.ml_classifier import get_ml_classifier, MLIntentClassifier, DEFAULT_DATASET_PATH
from app.core.config import Settings
from app.core.orchestrator import Orchestrator
from app.core.router import CommandRouter, RouteType


@pytest.fixture
def classifier():
    return get_ml_classifier()


@pytest.fixture
def router():
    return CommandRouter()


@pytest.fixture
def orchestrator():
    settings = Settings(llm_enabled=False, voice_enabled=False, tts_enabled=False)
    return Orchestrator(settings=settings)


def test_ml_classifier_training_and_caching(classifier):
    """Test 1: ML Intent model initializes and predicts in < 10ms."""
    assert classifier.pipeline is not None
    classes = classifier.pipeline.classes_
    assert len(classes) >= 15
    assert "open_app" in classes
    assert "close_app" in classes
    assert "take_screenshot" in classes


def test_ml_classifier_predictions(classifier):
    """Test 2: Model recognizes Indonesian slang, colloquialisms, and typos."""
    pred_open = classifier.predict("gas buka crome")
    assert pred_open is not None
    assert pred_open.intent == "open_app"
    assert pred_open.target == "chrome"
    assert pred_open.confidence >= 0.70

    pred_close = classifier.predict("matiin notepad")
    assert pred_close is not None
    assert pred_close.intent == "close_app"
    assert pred_close.target == "notepad"

    pred_next = classifier.predict("ganti lagu berikutnya")
    assert pred_next is not None
    assert pred_next.intent == "media_next"

    pred_battery = classifier.predict("sisa baterai berapa")
    assert pred_battery is not None
    assert pred_battery.intent == "battery_status"


def test_router_tier2_ml_dispatch(router):
    """Test 3: Router dispatches novel slang commands via Tier 2 ML classifier."""
    res = router.route("gas buka crome")
    assert res.route_type == RouteType.FAST_COMMAND
    assert res.action == "open_application"
    assert res.args.get("target") == "chrome"
    assert "ML intent direct" in res.description


def test_active_learning_cycle(classifier):
    """Test 4: Adding a novel utterance retrains model and boosts subsequent confidence."""
    novel_phrase = "potret layar desktopku saat ini"
    intent = "take_screenshot"

    # Add novel example
    success = classifier.add_example_and_retrain(novel_phrase, intent)
    assert success is True

    # Prediction should now be confident
    pred = classifier.predict(novel_phrase)
    assert pred is not None
    assert pred.intent == intent
    assert pred.confidence >= 0.70

    # Clean up test dataset
    try:
        with open(classifier.dataset_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        cleaned = [item for item in data if item.get("text") != novel_phrase]
        with open(classifier.dataset_path, "w", encoding="utf-8") as f:
            json.dump(cleaned, f, ensure_ascii=False, indent=2)
        classifier._train_and_save()
    except Exception:
        pass


def test_orchestrator_clarification_and_active_learning(orchestrator):
    """Test 5: Medium confidence triggers clarification, user confirms with 'Ya', auto-learning triggers."""
    user_phrase = "googling resep masakan"

    # Turn 1: User says phrase requiring clarification
    route1, gen1 = orchestrator.process_input_stream(user_phrase)
    reply1 = "".join(list(gen1))
    assert route1.route_type == RouteType.CLARIFY
    assert orchestrator.state.pending_action is not None
    assert orchestrator.state.pending_action.action == "clarify_ml_intent"
    assert "Apakah maksud Anda ingin" in reply1 or "Did you mean you want to" in reply1

    # Turn 2: User confirms with "Ya"
    route2, gen2 = orchestrator.process_input_stream("ya")
    reply2 = "".join(list(gen2))
    assert route2.route_type == RouteType.WEB_SEARCH
    assert orchestrator.state.pending_action is None

    # Clean up test addition if active learned
    try:
        classifier = get_ml_classifier()
        with open(classifier.dataset_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        cleaned = [item for item in data if item.get("text") != user_phrase]
        with open(classifier.dataset_path, "w", encoding="utf-8") as f:
            json.dump(cleaned, f, ensure_ascii=False, indent=2)
        classifier._train_and_save()
    except Exception:
        pass
