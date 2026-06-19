# ChronoArchiver — AGENTS.md

## Repo layout

```
src/core/     # Application logic
src/ui/       # PySide6 UI modules
tools/        # Build scripts (setup_launcher.py, chronoarchiver_setup.spec, bump_version.py)
tests/        # pytest suite
```

## Versioning

One SemVer string, synced across **all** of these files:
- `src/version.py` — `__version__ = "X.Y.Z"`
- `pyproject.toml` — `version = "X.Y.Z"`
- `PKGBUILD` — `pkgver=X.Y.Z`
- `README.md` — version badge + "Release X.Y.Z" text
- `tools/chronoarchiver_setup.spec` — default `_version` in `os.environ.get`
- `tools/setup_launcher.py` — default in `_read_version()`
- `src/core/changelog_notes.py` — `EMBEDDED_RELEASE_NOTES` key

Use `tools/bump_version.py` to sync all locations in one command.

## Building installers locally

```bash
pip install -r requirements.txt pyinstaller
pyinstaller tools/chronoarchiver_setup.spec --noconfirm --clean
```

Output: `dist/ChronoArchiver-Setup-{version}.exe` (Windows). The spec embeds the version from `CHRONOARCHIVER_VERSION` env var (default `6.6.4`).

## Releasing

1. Bump version: `python tools/bump_version.py X.Y.Z`
2. Update `CHANGELOG.md` — add the new version block at the top.
3. Update `src/core/changelog_notes.py` — add `EMBEDDED_RELEASE_NOTES["X.Y.Z"]`.
4. Commit and push.
5. Tag: `git tag vX.Y.Z && git push origin vX.Y.Z`

The `Build Releases` workflow (`.github/workflows/release.yml`) triggers on tag push. It builds installers for **Windows**, **macOS**, and **Linux**, then publishes a single GitHub Release with all three artifacts.

## CI

No per-PR CI runs. The only workflow is the release builder — it runs on tags and on `workflow_dispatch` (manual trigger with optional version input).

## Code style

- **Formatter:** Ruff (`ruff format`)
- **Linter:** Ruff (`ruff check`)
- **Type hints:** mypy on `src/core` (advisory, does not block)
- **Tests:** pytest (`python -m pytest tests/`)
- Line length: 120

## Conventions

- No `as any`, `@ts-ignore`, or similar type-suppression
- Empty `except:` blocks are forbidden
- No commit without explicit request
- Never suppress a failing test to make it pass
- Keep files under 250 LOC; refactor into modules when approaching the limit
- Prefer parsing over validation (explicit types, don't rely on runtime inference)

## Loop Prevention

To prevent infinite loops when using opencode-cli with local models:

1. **Built-In Guards**
   - `max_steps`: Set a hard limit on agentic iterations (e.g., 10–20). The agent auto-yields when exhausted.
   - No unmoderated execution — every tool call sequence requires human review. Treat agent loops as **state failures**, not model failures.

2. **Local MCP Servers & Prompts**
   - **Explicit system instructions**: Require the model to summarize findings in plain text before a second call. Force language generation over repeated JSON action calls.
   - **State-awareness**: Read a system file at loop start to "fingerprint" current state. ESCALATE to human if attempting the same command consecutively.

3. **Exception Handling**
   - **Detect tool duplication**: Identical tool call + parameters returned multiple times → terminal response: *"Same tool call failed multiple times. You must change parameters"*.
   - **Manual interruptions**: Use `Ctrl + C` in CLI. Use `/stop-continuation` to abort a looping agentic task.

4. **Callback Guards for External Tools (MCP, web fetch, etc.)**
   - Always prepend the model's response with an explicit acknowledgment: *"The tool returned successfully. Do not call this tool again for this specific request. This result is enough to begin processing."* This gives the model feedback that the call succeeded, preventing it from retrying the same tool.
   - If the tool is called repeatedly despite the acknowledgment, the model should treat it as a state failure and stop.
