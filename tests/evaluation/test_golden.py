"""The golden set and its check (spec US1, FR-001-FR-005; research R1, R2). A fixture PDF in a
temporary library with the fake embedder; no model and no network."""

import json

import pytest

from evaluation import golden
from paperpilot import library

ARXIV = "2401.00001"
METHOD = (
    "We propose a retrieval method for scientific papers. arXiv:2401.00001 The pre-training stage "
    "uses a large corpus of abstracts, and the fine-tuning stage adapts the encoder to questions "
    "written by readers of each paper."
)
RESULTS_TEXT = (
    "Our method reaches the best accuracy on every benchmark we tried, and it is faster to train "
    "than the baselines, which we describe in the text that follows this short paragraph."
)
TABLE = "Model Acc F1 Base 81.6 79.2 Large 86.6 84.3 Ours 91.7 90.1 Prior 73.7 70.4"


@pytest.fixture
def paper(tmp_path, make_pdf, library_env, fake_embedder):
    path = make_pdf(tmp_path / "golden-paper.pdf", references=False, title="A Study of Golden Questions",
                    sections=[("1 Method", METHOD), ("2 Results", RESULTS_TEXT), ("3 Tables", TABLE)])
    return library.add_paper(path)


def item(**overrides):
    base = {
        "id": "q-1", "kind": "single", "question": "What corpus is used for pre-training?", "scope": "library",
        "papers": [ARXIV], "expected": "A large corpus of abstracts.", "table": False,
        "evidence": [{"paper": ARXIV, "page": 1, "phrase": "large corpus of abstracts"}], "confirmed": True,
    }
    return {**base, **overrides}


def write(tmp_path, questions, version=1, papers=(ARXIV,), comments=""):
    path = tmp_path / "golden.json"
    body = json.dumps({"version": version, "papers": list(papers), "questions": questions}, indent=2)
    path.write_text(comments + body, encoding="utf-8")
    return path


def full_set():
    """A set meeting the targets for one paper (the fixture library holds one)."""
    questions = [item(id=f"s{n}") for n in range(19)]
    questions.append(item(id="t1", table=True, question="What accuracy does Ours reach?", expected="91.7.",
                          evidence=[{"paper": ARXIV, "page": 1, "phrase": "Ours 91.7"}]))
    questions += [item(id=f"c{n}", kind="cross") for n in range(5)]
    questions += [item(id=f"n{n}", kind="near_miss", expected="not_found", evidence=[]) for n in range(4)]
    questions += [item(id=f"o{n}", kind="off_topic", papers=[], expected="not_found", evidence=[]) for n in range(3)]
    questions += [item(id=f"f{n}", kind="follow_up", standalone="What corpus is used for pre-training?",
                       turns=[{"role": "user", "text": "Tell me about the method."},
                              {"role": "assistant", "text": "It is a retrieval method [1]."}]) for n in range(4)]
    return questions


def check(tmp_path, questions, drafts=False, **kwargs):
    return golden.check(golden.load_golden(write(tmp_path, questions, **kwargs)), drafts=drafts, cross_min_papers=1)


# --- normalisation ---


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("ﬁne-tuning", "finetuning"),
        ("pre-\ntraining", "pretraining"),
        ("Pre-training", "pretraining"),
        ("  Two   spaces\nand lines ", "two spaces and lines"),
        ("91.7% ± 0.2 × 10", "91.7% ± 0.2 × 10"),
        ("GPT-3 (175B)!", "gpt3 175b"),
    ],
)
def test_normalise(raw, expected):
    assert golden.normalise(raw) == expected


def test_a_hyphen_lost_at_a_line_break_still_matches():
    assert golden.normalise("pre-training") in golden.normalise("the pretraining stage")


# --- loading ---


def test_full_line_comments_are_ignored(tmp_path):
    loaded = golden.load_golden(write(tmp_path, [item()], comments="// a comment\n  // another\n"))
    assert loaded.version == 1 and loaded.questions[0]["id"] == "q-1"


def test_the_file_hash_is_recorded(tmp_path):
    first = golden.load_golden(write(tmp_path, [item()]))
    second = golden.load_golden(write(tmp_path, [item(question="Changed?")]))
    assert len(first.sha256) == 64 and first.sha256 != second.sha256


# --- the check ---


def test_a_full_valid_set_passes(tmp_path, paper):
    report = check(tmp_path, full_set())
    assert report.ok, report.errors
    assert report.counts == {"single": 20, "cross": 5, "near_miss": 4, "off_topic": 3, "follow_up": 4}


def test_an_empty_set_reports_every_target_at_zero_and_fails(tmp_path, paper):
    report = check(tmp_path, [])
    assert not report.ok
    assert report.counts == dict.fromkeys(golden.TARGETS, 0)
    assert any("single" in e and "20" in e for e in report.errors)


@pytest.mark.parametrize(
    ("change", "fragment"),
    [
        ({"evidence": [{"paper": ARXIV, "page": 1, "phrase": "never written anywhere"}]}, "matches no stored passage"),
        ({"evidence": [{"paper": ARXIV, "page": 2, "phrase": "large corpus of abstracts"}]}, "not on page 2"),
        ({"papers": ["9999.99999"], "evidence": [{"paper": "9999.99999", "page": 1, "phrase": "x"}]}, "9999.99999"),
        ({"note": "see a8ca46b17146-34"}, "passage ID"),
        ({"evidence": []}, "no evidence"),
        ({"table": True}, "table"),
        ({"confirmed": False}, "not confirmed"),
        ({"kind": "poem"}, "kind"),
        ({"scope": "everywhere"}, "scope"),
    ],
    ids=["unmatched phrase", "wrong page", "unknown paper", "passage id", "no evidence", "table not in a table",
         "unconfirmed", "unknown kind", "unknown scope"],
)
def test_a_bad_item_fails_and_is_named(tmp_path, paper, change, fragment):
    questions = full_set()
    questions[0] = {**questions[0], **change}
    report = check(tmp_path, questions)
    assert not report.ok
    assert any(questions[0]["id"] in e and fragment in e for e in report.errors), report.errors


def test_a_paper_without_a_table_question_fails(tmp_path, paper):
    questions = [q for q in full_set() if not q.get("table")] + [item(id="s-extra")]
    report = check(tmp_path, questions)
    assert any(ARXIV in e and "table" in e for e in report.errors)


def test_a_follow_up_needs_turns_and_a_standalone_wording(tmp_path, paper):
    questions = full_set()
    questions[-1] = {**questions[-1], "turns": [], "standalone": ""}
    report = check(tmp_path, questions)
    assert any(questions[-1]["id"] in e and "turns" in e for e in report.errors)


def test_drafts_allow_unconfirmed_items_and_missing_evidence(tmp_path, paper):
    questions = full_set()
    questions[0] = {**questions[0], "confirmed": False}
    questions[1] = {**questions[1], "evidence": []}
    report = check(tmp_path, questions, drafts=True)
    assert report.ok, report.errors
    assert any(questions[0]["id"] in n for n in report.notes) and any(questions[1]["id"] in n for n in report.notes)


def test_the_set_stays_valid_after_rechunking(tmp_path, paper, monkeypatch):
    path = write(tmp_path, full_set())
    assert golden.check(golden.load_golden(path), cross_min_papers=1).ok
    monkeypatch.setenv("CHUNK_WORDS", "40")
    monkeypatch.setenv("CHUNK_OVERLAP", "10")
    monkeypatch.setenv("MIN_CHUNK_WORDS", "5")
    library.reprocess_paper(paper.paper_id)
    assert golden.check(golden.load_golden(path), cross_min_papers=1).ok


# --- the command ---


def test_check_command_exit_codes(tmp_path, paper, capsys):
    from evaluation.__main__ import main

    good = write(tmp_path, full_set())
    assert main(["check", "--golden", str(good), "--cross-min-papers", "1"]) == 0
    empty = write(tmp_path, [])
    assert main(["check", "--golden", str(empty), "--cross-min-papers", "1"]) == 1
    out = capsys.readouterr().out
    assert "single: 0 of 20" in out and "Model requests: 0" in out
