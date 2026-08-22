from pathlib import Path
import re
import pandas as pd
import spacy

# Load spaCy
nlp = spacy.load("en_core_web_sm")


def segment_day(input_folder: str | Path, output_csv: str | Path):
    input_folder = Path(input_folder)
    output_csv = Path(output_csv)

    rows = []

    article_counter = 1

    # Read every markdown file in order
    for md_file in sorted(input_folder.glob("*.md")):

        with open(md_file, "r", encoding="utf-8") as f:
            markdown = f.read()

        # Split into articles using H1
        articles = re.split(r'(?=^# )', markdown, flags=re.MULTILINE)

        for article in articles:

            if not article.strip():
                continue

            headline = ""
            subheadline = ""
            author = ""

            body = []

            lines = article.splitlines()

            for line in lines:

                line = line.strip()

                if not line:
                    continue

                if line.startswith("# "):
                    headline = line[2:].strip()

                elif line.startswith("## "):
                    subheadline = line[3:].strip()

                elif line.startswith("{") and line.endswith("}"):
                    author = line[1:-1].strip()

                else:
                    body.append(line)

            body_text = "\n".join(body)

            if not body_text.strip():
                continue

            doc = nlp(body_text)

            sentence_order = 1

            article_id = f"{input_folder.name}_A{article_counter:03d}"

            for sent in doc.sents:

                sentence = sent.text.strip()

                if not sentence:
                    continue

                sentence_id = f"{article_id}_S{sentence_order:04d}"

                rows.append({
                    "sentence_id": sentence_id,
                    "article_id": article_id,
                    "date": input_folder.name,
                    "headline": headline,
                    "subheadline": subheadline,
                    "author": author,
                    "sentence_order": sentence_order,
                    "sentence": sentence
                })

                sentence_order += 1

            article_counter += 1

    df = pd.DataFrame(rows)

    output_csv.parent.mkdir(parents=True, exist_ok=True)

    df.to_csv(output_csv, index=False, encoding="utf-8")

    print(f"Saved {len(df)} sentences to {output_csv}")

def main():

    input_root = Path("Parsed_Markdown")
    output_root = Path("Segmentation")

    output_root.mkdir(exist_ok=True)

    # Process every day automatically
    for day_folder in sorted(input_root.iterdir()):

        if not day_folder.is_dir():
            continue

        output_csv = output_root / f"{day_folder.name}.csv"

        segment_day(day_folder, output_csv)


if __name__ == "__main__":
    main()