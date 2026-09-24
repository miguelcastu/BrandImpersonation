from contextlib import closing

from brandwatch.cli import main
from brandwatch.storage import connect, list_candidates, save_candidates


def test_storage_is_idempotent_and_tracks_sources(tmp_path):
    with closing(connect(tmp_path / "results.db")) as database:
        save_candidates(database, {"microsoft-help.example"}, "file")
        save_candidates(database, {"microsoft-help.example"}, "file")
        save_candidates(database, {"microsoft-help.example"}, "ct")
        assert database.execute("SELECT count(*) FROM candidates").fetchone()[0] == 1
        assert database.execute("SELECT count(*) FROM sightings").fetchone()[0] == 2
        assert list_candidates(database)[0][0] == "microsoft-help.example"


def test_cli_offline_example(tmp_path, capsys):
    config = tmp_path / "brand.toml"
    config.write_text(
        'name = "Microsoft"\nkeywords = ["microsoft"]\n'
        'legitimate_domains = ["microsoft.com"]\n',
        encoding="utf-8",
    )
    seeds = tmp_path / "seeds.txt"
    seeds.write_text(
        "login.microsoft.com\nmicrosoft-help.example\nunrelated.example\n", encoding="utf-8"
    )
    database = tmp_path / "results.db"
    assert main(
        [
            "--db", str(database), "discover", "--source", "file",
            "--config", str(config), "--input", str(seeds),
        ]
    ) == 0
    assert "Stored 1 candidate(s)" in capsys.readouterr().out
    assert main(["--db", str(database), "list"]) == 0
    assert capsys.readouterr().out == "microsoft-help.example\tfile\n"


def test_cli_variant_seed_tracks_match_provenance(tmp_path, capsys):
    from brandwatch.storage import list_discovery_matches

    config = tmp_path / "brand.toml"
    config.write_text(
        'name = "Microsoft"\nkeywords = ["microsoft"]\n'
        'legitimate_domains = ["microsoft.com"]\n',
        encoding="utf-8",
    )
    seeds = tmp_path / "seeds.txt"
    seeds.write_text("micr0soft-login.example\n", encoding="utf-8")
    database = tmp_path / "results.db"

    assert main(
        [
            "--db",
            str(database),
            "discover",
            "--source",
            "file",
            "--config",
            str(config),
            "--input",
            str(seeds),
        ]
    ) == 0
    assert "Stored 1 candidate(s)" in capsys.readouterr().out
    with closing(connect(database)) as db:
        assert list_discovery_matches(db) == [
            ("micr0soft-login.example", "file", "seed-file", "micr0soft", "variant")
        ]


def test_variants_cli_is_offline_and_bounded(tmp_path, capsys):
    config = tmp_path / "brand.toml"
    config.write_text(
        'name = "Microsoft"\nkeywords = ["microsoft"]\n'
        'legitimate_domains = ["microsoft.com"]\n',
        encoding="utf-8",
    )
    assert main(["variants", "--config", str(config), "--limit", "4"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 4
    assert any(line.startswith("micr0soft\t") for line in lines)
