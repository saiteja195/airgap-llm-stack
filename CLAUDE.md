# CLAUDE.md

Project: air-gapped LLM agent stack (agent API + Qdrant + Ollama, Helm chart, offline bundle, preflight). See `README.md` and `docs/`.

## Git rules (owner's standing instructions)

- **Author identity:** commit only as `Sai Teja J <saiteja.javvaji@gmail.com>`. Never commit as "Claude" or a noreply address. Check `git config user.name` / `user.email` before the first commit in a session and set them repo-locally if wrong. A `Co-Authored-By` trailer is fine.
- **One branch per feature.** Never commit directly to `main`. Name branches `<type>/<short-kebab-description>` with type one of `feat`, `fix`, `docs`, `chore`, `test`, `refactor` (e.g. `feat/jev-gate`, `fix/netpol-dns`).
- **Merge to `main` only when the branch is tested and has no known issues.** Run `make test lint` first; anything that touches the chart or scripts must also pass `make chart-lint`. If it can only be verified on a real cluster and hasn't been, say so and do not merge.
- Never rewrite `main`. Force-push only your own unmerged feature branches, with `--force-with-lease`.
- Don't open a PR unless asked.

## Working conventions

- Python lives in `agent/` (ruff, pytest; `cd agent && pytest -q`). Shell scripts source `scripts/lib.sh` and must pass `bash -n` and shellcheck.
- Nothing may require internet at runtime: no CDN assets in the UI, no model/image pulls inside the cluster. Anything fetched must be added to `scripts/bundle.sh`.
- Keep README "Status" and the metrics table honest: mark things unverified until run on a real cluster.
- Model name is defined in `scripts/lib.sh`, `charts/airgap-agent/values.yaml` and `agent/app/config.py`; change all three together.
- Don't write scratch files into the repo tree; `bundle/` and `bench/results.json` are gitignored.
