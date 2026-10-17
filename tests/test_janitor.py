"""Unit tests for Workspace Janitor tool."""

from pathlib import Path
from app.tools.janitor import clean_workspace, count_clutter, scan_workspace


def test_janitor_scan_and_clean(tmp_path: Path):
    """Verifies scanning and sorting files into categorized subfolders."""
    # Create mock downloads folder with assorted test files
    mock_downloads = tmp_path / "mock_downloads"
    mock_downloads.mkdir()

    (mock_downloads / "report.pdf").write_text("dummy doc")
    (mock_downloads / "invoice.docx").write_text("dummy doc")
    (mock_downloads / "photo.png").write_text("dummy image")
    (mock_downloads / "installer.exe").write_text("dummy exe")
    (mock_downloads / "backup.zip").write_text("dummy zip")
    (mock_downloads / "script.py").write_text("dummy code")
    (mock_downloads / "song.mp3").write_text("dummy audio")

    # Clutter count
    assert count_clutter(str(mock_downloads)) == 7

    # Scan
    scan_res = scan_workspace(str(mock_downloads))
    assert scan_res["success"] is True
    assert scan_res["total_files"] == 7
    categories = scan_res["categories"]
    assert "Documents" in categories and len(categories["Documents"]) == 2
    assert "Images" in categories and len(categories["Images"]) == 1
    assert "Installers" in categories and len(categories["Installers"]) == 1
    assert "Archives" in categories and len(categories["Archives"]) == 1
    assert "Code" in categories and len(categories["Code"]) == 1
    assert "Media" in categories and len(categories["Media"]) == 1

    # Clean (execute move)
    clean_res = clean_workspace(str(mock_downloads), dry_run=False)
    assert clean_res["success"] is True
    assert clean_res["moved_count"] == 7

    # Verify subfolders were created and loose files removed
    assert (mock_downloads / "Documents" / "report.pdf").exists()
    assert (mock_downloads / "Documents" / "invoice.docx").exists()
    assert (mock_downloads / "Images" / "photo.png").exists()
    assert (mock_downloads / "Installers" / "installer.exe").exists()
    assert (mock_downloads / "Archives" / "backup.zip").exists()
    assert (mock_downloads / "Code" / "script.py").exists()
    assert (mock_downloads / "Media" / "song.mp3").exists()

    # Remaining clutter in root should now be 0
    assert count_clutter(str(mock_downloads)) == 0


def test_orchestrator_janitor_routing():
    """Verifies that Orchestrator routes 'rapikan folder downloads' correctly."""
    from app.core.orchestrator import Orchestrator
    orch = Orchestrator()
    route = orch.router.route("rapikan folder downloads")
    assert route.action == "clean_workspace"
    assert route.args.get("target") == "downloads"

    route_desk = orch.router.route("rapikan desktop")
    assert route_desk.action == "clean_workspace"
    assert route_desk.args.get("target") == "desktop"

