# Git and GitHub Guide (Week 1)

```bash
git init -b main                 # start a repository (-b main names the default branch)
git status                       # shows untracked/changed files
cat .gitignore                   # confirm venv, logs, generated data, bin/ are ignored
git add -A && git status         # stage and double-check nothing unwanted is listed
git commit -m "Initial Week 1 project: config, utils, docs"
git switch -c week1              # optional: work on a Week 1 branch
git log --oneline                # review history
```

Meaningful, separate commits (examples):

```
Add shared config validation and SocketCAN frame helpers
Add normal traffic simulator with seeded payload generation
Add Python CAN monitor and observed-dataset CSV output
Add C SocketCAN capture program
Add setup scripts, Makefile and demo script
Add unit tests and Week 1 documentation
```
Only commit when something real changed; do not create empty or filler commits.

## Connect to GitHub
1. On github.com create an **empty** repository (no README), for example `CAN-Sentinel`.
2. Then:
```bash
git remote add origin https://github.com/<your-username>/CAN-Sentinel.git
git remote -v                    # verify
git push -u origin main          # first push; if you used the week1 branch: git push -u origin week1
```
GitHub no longer accepts account passwords for pushes. Use a Personal Access Token, the GitHub CLI (`gh auth login`), or SSH keys.

## Safe habits
* Run `git status` and `git diff --staged` before each commit.
* Never commit secrets, personal config (`config/config.json` is ignored) or large generated data (`data/generated/` is ignored).
* If a push is rejected: `git pull --rebase origin main`, resolve conflicts, then push. Avoid `git push --force`.
