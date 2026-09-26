# Laptop Optimizer (Universal)

One tool to check and speed up any laptop running **Windows, macOS or Linux**.

- **Health scan**: CPU, RAM, swap, disks, battery, temperatures, uptime and the heaviest processes, rolled into a 0–100 score with specific fixes.
- **Junk cleaner**: clears temp files, OS caches, browser caches, thumbnail caches, crash dumps and developer caches (pip, npm, Xcode DerivedData). Can also empty the trash.
- **Startup audit**: lists every program that launches at login.
- **Power profiles**: switch between saver, balanced and performance with one command.
- **Big file finder**: shows what is eating your disk.
- **HTML report**: a report you can open in any browser, with dark mode.

## Quick start

| OS | Run |
|---|---|
| Windows | Double-click `optimize.bat` |
| macOS / Linux | `./optimize.sh` |
| Anywhere | `pip install -r requirements.txt && python -m optimizer` |

Requires Python 3.9+. The launchers install the one dependency (`psutil`) automatically.

## Commands

```sh
optimizer scan                        # health score + recommendations
optimizer scan --report r.html --open # save and open an HTML report
optimizer scan --json                 # machine-readable output
optimizer clean                       # show what can be freed (deletes nothing)
optimizer clean --apply               # delete it (asks to confirm)
optimizer clean --apply --trash -y    # also empty the trash, no prompt
optimizer boost                       # clean + scan in one go
optimizer startup -v                  # list login programs
optimizer power                       # show current power profile
optimizer power performance           # or: saver / balanced
optimizer bigfiles ~ --min-mb 1000    # files over 1 GB in your home folder
```

(`optimizer` = `./optimize.sh`, `optimize.bat`, or `python -m optimizer`.)

## Safety

The cleaner is designed so it cannot hurt your data:

- **Dry run by default.** Nothing is deleted without `--apply`, and `--apply` asks for confirmation unless you pass `-y`.
- It only touches known cache and temp folders. It never deletes documents, settings or app data.
- It skips files changed in the last 24 hours (change this with `--min-age`), so it won't touch files that are in use.
- It never follows symlinks, so it can't wander outside those folders.
- If a file is locked or needs admin rights, the cleaner skips it and never forces the delete.
- `startup` and `bigfiles` only read. They never change anything.

## Development

```sh
pip install psutil pytest
python -m pytest
```
