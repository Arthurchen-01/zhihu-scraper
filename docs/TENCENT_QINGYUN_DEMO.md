# Tencent Qingyun Demo Script

This script is for a short external review of the project. The goal is to show a clean local-first archive product, not to prove live scraping coverage under unpredictable network and anti-bot conditions.

## Positioning

Zhihu-Scraper is a local-first archive tool:

- Input: Zhihu links or local URL lists.
- Processing: protocol-first fetch, optional browser fallback, typed payload handling.
- Output: Markdown, images, and SQLite owned by the user.
- Interfaces: CLI for humans and automation.

## Five-Minute Flow

1. Show the repository entry points.

```bash
zhihu --help
zhihu check
zhihu config
```

2. Show the command surface.

```bash
zhihu fetch --help
zhihu query --help
```

3. Show local archive value without depending on live network.

```bash
zhihu query "深度学习"
```

If the local demo database is not present, show a freshly generated local export under `data/entries/` or `examples/outputs/` and explain that the durable deliverable is plain Markdown plus local assets.

4. Show maintainability.

```bash
python -m unittest -q tests.test_docs_sync tests.test_command_surface tests.test_install_contract
```

Then point to:

- `CONSTITUTION.md`
- `AGENTS.md`
- `docs/PROJECT_CONVERGENCE_REPORT.md`
- `docs/agent-skills/`

## What To Emphasize

- The project is intentionally not a cloud scraping service.
- The value is local ownership and readable archives.
- The current version is in maintenance freeze after `v3.0.1-final`.
- Clean command contracts matter more than expanding crawler scope.
- Performance is not the priority for this phase.

## What Not To Promise

- Do not promise continuous compatibility with all future Zhihu page/API changes.
- Do not describe it as an enterprise batch crawling platform.
- Do not imply remote data hosting, SaaS operation, or managed scraping.
- Do not demo large live crawling as the core story.

## Preferred Closing

The repository is now converged around one `main` branch, one local-first product story, and one guarded CLI command surface. The next high-value polish is local config separation and a no-network demo fixture.
