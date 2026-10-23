# Known Limitations

PaperPilot's PDF parsing uses simple, explainable rules. These are the cases they do not
handle. The full list is completed in task T046.

## Headings

- **Headings that wrap onto a third line are cut off.** When a numbered heading is long
  enough to wrap, the PDF holds the number, the first title line and the second title line
  as three separate lines (e.g. "3" / "How Well Can Language Models" / "Retrieve From Input
  Contexts?" in *Lost in the Middle*). Only the number and the first title line are joined,
  so the section is labelled "How Well Can Language Models". The second line becomes the
  first text of the section. Passages still get the right section; only the label is short.

## Tables and figures

- **Mixed blocks stay in text passages.** Table-like blocks (mostly numbers or symbols) become
  separate table passages, but a PDF block that mixes prose with table rows or figure labels
  (axis ticks, legend entries) is not table-like, so it stays in a text passage. Table header
  rows, which are mostly words, may also stay with the surrounding prose. On the Checkpoint 2
  samples about 12 of 15 text passages read cleanly; the rest contain such fragments. The
  goal (SC-003) remains 9 of 10.
