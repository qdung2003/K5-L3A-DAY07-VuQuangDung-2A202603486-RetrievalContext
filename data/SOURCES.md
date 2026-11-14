# Corpus Day 7

This submission uses the actual Day 6 corpus and persistent vector-store snapshot,
not the synthetic Vietnamese policy demonstration retained in `data/legacy/`.

- Upstream: CPython documentation, tag `v3.13.0`, eight Python Tutorial chapters.
- Day 6 submission: https://github.com/qdung2003/K5-L3A-DAY06-VuQuangDung-2A202603486-DataIngestion
- Local sources: `data/python_tutorial/raw/*.rst`; normalized chapters: `*.txt`.
- License: PSF License Version 2; examples additionally covered by 0BSD as described
  in `python_tutorial/documentation-license.rst`. Copyright and license files retained.
- Provenance: `day6_manifest.json` includes original source URLs, retrieval times,
  hashes, and text-unit offsets. No physical PDF pages are claimed. The Day 6 corpus
  has 93 non-overlapping source units, at least 1,500 normalized characters each,
  over 186,787 characters. Day 7 reuses the existing corpus as required by GUIDE.
- Chunking: Day 6 strategy B, 256 chunks; IDs, text, page/unit IDs and offsets retained.
- Embedding: real `sentence-transformers/all-MiniLM-L6-v2`, revision
  `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`, 384 dimensions, normalized, maximum
  sequence length 256 tokens. Query and indexed documents use the same encoder.
- Store: original Chroma `day06_b`, cosine HNSW. `src/day6_index.json` exports its
  actual vectors for rebuilding without the sibling project. Rebuilding the HNSW
  graph can change approximate-search tie ordering; original traces remain available.

`questions.json` has 17 dev and 7 test cases. Fifteen answerable dev questions are
reused from Day 6; two dev abstention questions are new. All seven test questions
are new for Day 7 and cover different answers from the previously observed Day 6
test. Inputs and the selection rule were hashed in `benchmark_freeze.json` before
running neural Day 7 experiments. Gold and expected answers are evaluator-only;
the agent receives just the question and any user-specified chapter filter.

The test shares source documents with dev, so this is a small query holdout rather
than a document-disjoint benchmark. No test-driven tuning is permitted. If test
results are subsequently used for tuning, create another test set.
