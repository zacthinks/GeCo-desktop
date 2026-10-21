"""Create real TeAL artifacts and a linked GeCo workspace; no Desktop imports."""
from __future__ import annotations
import argparse
import json
from importlib.metadata import version
from pathlib import Path
from text_analysis_lab import Project
from text_analysis_lab import translators as tr

def build(root: Path, csv: Path):
    root.mkdir(parents=True, exist_ok=True)
    if (root / ".teal").exists():
        raise FileExistsError("Refusing to overwrite TeAL state")
    with Project.create(root, name="Ontology smoke", delete_existing=False) as project:
        docs = project.read_csv(
            csv, text_fields="text",
            metadata_fields=["source_id", "entity", "category"], alias="documents")
        counts = project.translate(
            tr.CountVectorizer(text_field="text", max_features=300),
            docs, alias="counts")["output"]
        tfidf = project.translate(
            tr.TfidfTransformer(norm="l2"), counts, alias="tfidf")["output"]
        svd = project.translate(
            tr.SVD(n_components=2, random_state=42),
            tfidf, alias={"output": "projection", "components": "svd_components"})["output"]
        project.geco.create(
            "desktop", documents=docs, text_field="text", geometry=tfidf,
            projections={"svd2": svd},
            metadata_fields=["source_id", "entity", "category"])
        return {"rows": int(docs.n_rows),
                "workspaces": [row["name"] for row in project.geco.list()],
                "teal_version": version("text-analysis-lab"),
                "geco_version": version("geometric-coder")}

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--root", required=True, type=Path)
    p.add_argument("--csv", required=True, type=Path)
    args = p.parse_args()
    print(json.dumps(build(args.root.resolve(), args.csv.resolve())))
