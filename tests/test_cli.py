from __future__ import annotations

import pytest

from zafather import __version__
from zafather.cli import create_project, main


def test_version(capsys) -> None:
    assert main(["version"]) == 0
    assert capsys.readouterr().out.strip() == f"Zafather {__version__}"


def test_new_bot_project(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["new", "mybot"]) == 0
    project = tmp_path / "mybot"
    source = (project / "bot.py").read_text(encoding="utf-8")
    compile(source, "bot.py", "exec")
    assert "BOT_TOKEN" in (project / ".env").read_text()
    assert (project / "requirements.txt").read_text().startswith("zafather>=")
    assert ".env" in (project / ".gitignore").read_text()
    assert main(["new", "mybot"]) == 1
    assert "already exists" in capsys.readouterr().err


def test_new_userbot_project(tmp_path) -> None:
    project = create_project("myuser", userbot=True, root=tmp_path)
    source = (project / "userbot.py").read_text(encoding="utf-8")
    compile(source, "userbot.py", "exec")
    assert "API_HASH" in (project / ".env").read_text()
    assert "zafather[userbot]" in (project / "requirements.txt").read_text()


def test_help(capsys) -> None:
    assert main([]) == 0
    assert "zafather" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        main(["--unknown"])
