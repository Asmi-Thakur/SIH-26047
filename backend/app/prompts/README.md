# LLM prompts (version-controlled)

Prompt files land here as their phases are implemented (see
`docs/PROTOTYPE_BUILD_SPEC.md` §23). They are kept as plain-text files — never
inline strings scattered through service code.

Planned files:

```text
extract_answer_v1.txt     # transcript -> structured fields (Phase 4)
next_question_v1.txt      # choose next approved question (Phase 4)
document_extract_v1.txt   # OCR text -> clinical entities (Phase 5)
summary_v1.txt            # case data -> physician draft (Phase 6)
translation_v1.txt        # patient-language paraphrasing (later)
```

Phase 1 intentionally ships no prompts — nothing calls the LLM yet.
