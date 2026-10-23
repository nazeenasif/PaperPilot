"""Tests for ingest.detect_heading() (FR-008, FR-009, research R7)."""

import pytest

from paperpilot.ingest import detect_heading, heading_candidate


@pytest.mark.parametrize(
    ("line", "name"),
    [
        ("Abstract", "Abstract"),
        ("ABSTRACT", "Abstract"),
        ("Abstract.", "Abstract"),
        ("1 Introduction", "Introduction"),
        ("2. Related Work", "Related Work"),
        ("Background", "Background"),
        ("III. METHODOLOGY", "Methods"),
        ("3 Method", "Methods"),
        ("Methods", "Methods"),
        ("Approach", "Methods"),
        ("4 Experiments", "Experiments"),
        ("Results", "Results"),
        ("5 Discussion", "Discussion"),
        ("Limitations", "Limitations"),
        ("Conclusion", "Conclusion"),
        ("6 Conclusions", "Conclusion"),
    ],
)
def test_canonical_headings(line, name):
    heading = detect_heading(line, None)
    assert heading is not None
    assert heading.kind == "canonical"
    assert heading.name == name


def test_canonical_heading_records_its_number():
    assert detect_heading("1 Introduction", None).number == 1
    assert detect_heading("Abstract", None).number is None


def test_canonical_word_with_extra_text_is_not_a_heading():
    assert detect_heading("Introduction to transformers", None) is None


def test_numbered_heading_uses_its_own_text():
    heading = detect_heading("3 Model Architecture", 2)
    assert heading is not None
    assert heading.kind == "numbered"
    assert heading.name == "Model Architecture"
    assert heading.number == 3


def test_numbered_heading_with_dot():
    heading = detect_heading("5. Training", 4)
    assert heading is not None
    assert heading.name == "Training"
    assert heading.number == 5


def test_first_numbered_heading_may_be_1_or_2():
    assert detect_heading("1 Overview", None).name == "Overview"
    assert detect_heading("2 Overview", None).name == "Overview"
    assert detect_heading("3 Overview", None) is None


def test_missing_heading_is_tolerated():
    # Heading 4 was missed: 5 is still accepted after 3, then 6 after 5.
    training = detect_heading("5 Training", 3)
    assert training is not None
    assert training.name == "Training"
    results = detect_heading("6 Results", training.number)
    assert results is not None
    assert results.name == "Results"


def test_numbered_canonical_heading_updates_previous_number():
    # Canonical headings return their number, so the caller can keep the sequence going.
    last_number = 2
    detected = []
    for line in ["3 Model Architecture", "4 Experiments", "5 Results", "6 Analysis"]:
        heading = detect_heading(line, last_number)
        assert heading is not None, line
        detected.append((heading.name, heading.kind, heading.number))
        last_number = heading.number
    assert detected == [
        ("Model Architecture", "numbered", 3),
        ("Experiments", "canonical", 4),
        ("Results", "canonical", 5),
        ("Analysis", "numbered", 6),
    ]


@pytest.mark.parametrize(
    ("line", "last_number"),
    [
        ("3.1 Encoder", 3),  # sub-heading
        ("2 0.5 1.3", 1),  # table row
        ("3 We train the model on eight GPUs.", 2),  # sentence ending with a period
        ("3 This section describes the details of our training setup here", 2),  # > 8 words
        ("7 Results Table", 2),  # more than 2 higher
        ("2 Model Details", 3),  # not greater than the previous number
        ("", None),
        ("The model uses attention.", None),
    ],
)
def test_rejected_lines(line, last_number):
    assert detect_heading(line, last_number) is None


@pytest.mark.parametrize("line", ["References", "REFERENCES", "Bibliography", "6 References"])
def test_stop_headings(line):
    heading = detect_heading(line, 5)
    assert heading is not None
    assert heading.kind == "stop"


@pytest.mark.parametrize(
    ("text", "line", "rest"),
    [
        ("1\nIntroduction\nBody text.", "1 Introduction", "Body text."),
        ("3.\nTraining\n", "3. Training", ""),
        ("III.\nMETHODOLOGY", "III. METHODOLOGY", ""),
        ("3.1\nEncoder and Decoder Stacks", "3.1 Encoder and Decoder Stacks", ""),
        ("Abstract\nWe propose a model.", "Abstract", "We propose a model."),
        ("12", "12", ""),  # a lone number with nothing after it stays as it is
        ("The model has\n6 layers", "The model has", "6 layers"),
    ],
)
def test_heading_candidate_joins_a_number_only_first_line(text, line, rest):
    assert heading_candidate(text) == (line, rest)


def test_number_on_its_own_line_is_detected_as_numbered_heading():
    line, _ = heading_candidate("3\nModel Architecture\n")
    heading = detect_heading(line, 2)
    assert heading is not None
    assert heading.kind == "numbered"
    assert heading.name == "Model Architecture"


def test_sub_heading_on_two_lines_is_still_rejected():
    line, _ = heading_candidate("3.1\nEncoder and Decoder Stacks")
    assert detect_heading(line, 3) is None


@pytest.mark.parametrize(
    ("line", "last_number", "name"),
    [
        ("2 PROBLEM STATEMENT", 1, "Problem Statement"),
        ("3 AREN’T EXISTING SOLUTIONS GOOD ENOUGH?", 2, "Aren’t Existing Solutions Good Enough?"),
        ("5 UNDERSTANDING THE LOW-RANK UPDATES", 4, "Understanding the Low-Rank Updates"),
        ("7 CONCLUSION AND FUTURE WORK", 6, "Conclusion and Future Work"),
        ("3 BERT", 2, "BERT"),  # single-word label: likely an acronym, kept as is
        ("3 Model Architecture", 2, "Model Architecture"),  # mixed case unchanged
    ],
)
def test_all_caps_numbered_labels_become_title_case(line, last_number, name):
    heading = detect_heading(line, last_number)
    assert heading is not None
    assert heading.name == name
