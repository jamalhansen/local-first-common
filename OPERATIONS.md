# Local-First Fleet: Operations Standards

`STANDARDS.md` covers how a tool is written (CLI flags, layout, run tracking). This file covers how the fleet runs: scheduling, deploying, shared state, security, CI. Every rule here was learned the hard way; the date says when.

## Scheduled jobs

- **One host.** The Mac mini runs every `com.localfirst.*` job. No other machine runs them (2026-10-04: conflict files showed the MacBook Air also running `discovery-loop` at 07:00 against the same synced database).
- **Plists live in `personal-infra/launchagents/`**, and `install.sh` copies them into `~/Library/LaunchAgents`. Never edit only the live copy.
- **Reload after editing a plist:** `launchctl bootout` then `bootstrap`. `kickstart` does not re-read a changed plist.
- **No secrets in plists.** Keys live in the Keychain.
- **Long jobs heartbeat.** Set `LOCALFIRST_JOB_LABEL` in the plist and call `local_first_common.heartbeat.heartbeat()` per unit of work. Give the job `stuck_after` / `max_runtime` in `personal-infra/config/process-doctor.toml`. A job that mostly waits (LLM calls, fetches) looks hung to a CPU check (2026-09-30 to 10-03: process-doctor killed the discovery run every morning).
- **Test under the launcher.** A scheduled job is verified when it has run under launchd (`launchctl kickstart`), not from a terminal. Draw Things, the heartbeat fix and the snapshot job all behaved differently under launchd.

## Deploying

- **A commit is not live until deployed.** `uv tool install` is a snapshot, and a KeepAlive service keeps running the old process. Run `make deploy REPO=<repo>`: it reinstalls the tool, restarts the service if it is one, and smoke-tests the entry points. (2026-10-03/04: two fixes sat committed but undeployed.)
- `repo-health` flags an installed tool whose code no longer matches the repo.

## Shared state

- **Databases are never live-synced.** SQLite and DuckDB files in `~/sync` are excluded by `.stignore` (`personal-infra/config/syncthing/stignore`, installed on every device). Syncthing copies whole files; two writers lose data.
- **DuckDB allows one writing process.** Write `processing_log.duckdb` through `local_first_common.tracking`, which retries the lock; anything that opens it directly must retry too.

## Code

- **Every network call and subprocess has a timeout.**
- **Every dependency pin carries its reason and the condition for lifting it.** The `click<8.3.2` pin had a reason but no exit condition, and quietly held a vulnerable version in 13 repos.
- **Tests never depend on `~/.config`, synced files, API keys in the environment, or installed-but-undeclared packages.** CI has none of them. Patch config-derived module globals in `conftest.py` (2026-10-04: 18 content-discovery tests only passed because the real feed list existed) and set fake keys with `monkeypatch.setenv` (a DeepSeek test only passed because a real `DEEPSEEK_API_KEY` was exported). Check locally with an empty home, no keys, and an exact install:
  `uv sync --frozen && env -u ANTHROPIC_API_KEY -u DEEPSEEK_API_KEY -u GEMINI_API_KEY -u GROQ_API_KEY -u OPENAI_API_KEY -u LLM_GATEWAY_URL HOME=$(mktemp -d) uv run --frozen pytest -q`
- **CI failures are readable without logging in:** each failing test, and the tail of pytest's output, become annotations on the run (job logs need a login even on public repos).

## Dependencies

- **Upgrade sweep:** `uv lock --upgrade`, commit through the hook (tests gate it), `make deploy`, then re-audit. A major version bump can drop an optional piece: pydantic-ai 2.x stopped bundling the Groq client, which a plain `uv run` hid because it never removes stray packages. CI's exact install catches this.
- **Audits run without commits:** weekly in `repo-health` and in CI's weekly schedule.

## Security

- **gitleaks** blocks commits that stage a credential (pre-commit), and CI scans the full history. All repos are public: a leaked key is a published key.
- **pip-audit** runs in CI and weekly in `repo-health`.
- **Dependabot security alerts** are on for every fleet repo (alerts only, no automatic PRs; enabled 2026-10-04). Check with `gh api repos/jamalhansen/<repo>/dependabot/alerts?state=open`.
- Services bound to `0.0.0.0` (japanese-tutor, fleet-dashboard) are read-only and hold no secrets.

## CI

- Every Python repo runs `local-first-common/.github/workflows/python-ci.yml` through a short `.github/workflows/ci.yml`: lint (ruff 0.16.7 + SIM115, same as the hook), tests with the 50% coverage floor, pip-audit, gitleaks. Triggered on push, PR, weekly, and on demand.
- Repos with `../` path dependencies pass `siblings:` so CI clones them next to the repo.
- Keep `RUFF_PIN` in the workflow in step with `install_hooks.py`.
- No CD: deploy targets are this Mac's launchd jobs and uv tools, which a cloud runner can't and shouldn't reach. Deploying is `make deploy`.
- `http-retriever-service` (Node) is not yet covered; its checks are `npm test`, `npm run lint`, `npm audit`.
