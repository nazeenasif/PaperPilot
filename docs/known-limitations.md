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
