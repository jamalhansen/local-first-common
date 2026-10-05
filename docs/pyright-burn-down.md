# pyright burn-down

Shared CI runs pyright 1.1.414 on every fleet repo since 2026-10-05, report-only:
errors are warning annotations and the run stays green. A repo passes
`typecheck: strict` in its `.github/workflows/ci.yml` once it reaches zero, and
from then on a new type error fails its CI. The goal is every repo strict.

## Baseline (2026-10-05, run inside each repo's venv)

527 errors across 41 Python repos; 263 of them are in `tests/`.

| Errors | Repos |
|---|---|
| 0 | brand-voice-validator, marketing-persona-counsel, model-compare, photo-metadata-scrubber, rot-finder, weekly-thread-triage |
| 1-3 | newsletter-prep-assistant, pipeline-compose, process-doctor, cross-vault-seed-sync, persona-counsel, photo-scaler, unsplash-uploader, draft-tools, finding-triage, photo-renamer, pipeline-analysis, stale-obsidian-note-detector, transcription-summarizer |
| 5-10 | blog-post-draft-reviewer, yt-transcription-summarizer, frontmatter-validator, social-post-reader, pebble, pedantic-troll, fleet-cli, tension-triage-dashboard, weekly-review-generator, obsidian-vault-auto-tagger |
| 12-28 | vault-query, adversary, llm-gateway-service, artist-agent, fleet-dashboard-service, obsidian-hugo-bridge, calibration, content-discovery-agent, model-comparison-harness, series-cross-link-suggester |
| 100+ | japanese-tutor (113), local-first-common (127) |

Re-measure: `uv run --frozen --with pyright==1.1.414 pyright .` in the repo.

## Order

1. **Shared roots in local-first-common first.** Three of its types cause errors in
   other repos, about 60 in all:
   - `BaseProvider` sets `item_count` and `source_location` dynamically. Declare
     them on the class (`item_count: int | None = None`, likewise
     `source_location`). Clears the "Cannot assign to attribute" errors in
     frontmatter-validator, yt-transcription-summarizer, model-comparison-harness
     and the other two-error repos.
   - `known_models` on each provider overrides an instance attribute on
     `BaseProvider`. Annotate it `ClassVar[...]` on the base (18 errors).
   - `tracked_call(tool: Tool)` is passed `Tool | None` from `register_tool`
     (7 in readwise.py). Decide which side is wrong, since register_tool returns
     None on failure and that is a real path.
   Re-measure the fleet afterwards: siblings use local-first-common by `../` path,
   so the effect is immediate.
2. **Flip the six zero-error repos to strict** in one sweep.
3. **The 1-10 error repos, one commit each:** fix, then flip strict in the same
   commit, so the fix can't regress.
4. **The 12-28 error repos**, same way, one at a time.
5. **japanese-tutor and local-first-common last.** japanese-tutor's 113 are mostly
   tests assigning `.return_value` onto real methods (switch to
   `patch.object`) and Optional access on an API model.

## How to fix (so the count drops honestly)

- **An Optional error in `src/` may be a real bug.** Before narrowing it, decide
  whether `None` can actually arrive there. If it can, handle it. List any real
  bugs found in the commit message.
- In tests, narrow with `assert x is not None`; that is a test assertion anyway.
- Mocks: `patch.object(obj, "method")` instead of assigning attributes onto a
  bound method; a typed fake that subclasses `BaseProvider` instead of a duck type.
- `# type: ignore` only as `# pyright: ignore[ruleName]` with a reason on the line,
  and only where the type system can't express the code. No blanket ignores, no
  per-repo rule downgrades in `[tool.pyright]`.

## Done when

Every caller passes `typecheck: strict`, and the shared workflow's default can flip
from `report` to `strict` (then drop the input).
