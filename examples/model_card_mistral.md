---
license: apache-2.0
base_model: mistralai/Mistral-7B-v0.3
pipeline_tag: text-generation
tags:
  - finetuned
datasets:
  - internal/cv-parsing-corpus
model-index:
  - name: cv-parser-ft
    results:
      - task:
          type: text-generation
        dataset:
          name: internal/cv-eval-set
          type: internal
        metrics:
          - type: field-extraction-f1
            value: 0.91
          - type: exact-match
            value: 0.78
---

# cv-parser-ft

Fine-tune of Mistral-7B-v0.3 for structured CV field extraction.
(Fictional model card used as an `aigov ingest` demo fixture.)
