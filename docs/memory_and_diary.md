# Long-Term Memory And Observation Diary

Both v0.83 features are disabled by default and store runtime records only on the local machine.

## Long-Term Memory

- Enable it in `Settings Center -> Memory And Diary`.
- Only conversations completed after enabling are stored.
- Retrieval uses local sparse text vectors and cosine similarity.
- The text Provider receives only the configured top relevant records, not the full memory file.
- API Key, token, password, and secret-like input is rejected before storage.
- Records are visible in Settings Center and can be cleared without deleting chat history.

Runtime file:

```text
data/daniya_relation/long_term_memory.jsonl
```

In a packaged build, this resolves under `%APPDATA%\DaniyaSummerPet\`.

## Observation Diary

- Enable permission in `Settings Center -> Memory And Diary`.
- Diary generation is manual. No background timer generates or sends diaries.
- Clicking Generate shows a second confirmation before recent event summaries are sent to the active text Provider.
- The user chooses a 1-30 day event window.
- A local fallback or failed Provider response is not saved as a successful diary.
- Saved diary text remains visible and clearable in Settings Center.

Runtime file:

```text
data/observation_diary.jsonl
```

## Privacy Boundary

The repository and Windows release archive must not contain either runtime file. Clearing memory is permanent; export or backup is the user's responsibility.
