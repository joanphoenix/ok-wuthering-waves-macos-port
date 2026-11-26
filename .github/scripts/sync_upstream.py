"""Bring the macOS port up to a newer upstream ok-wuthering-waves release.

The port shares no git history with upstream, so a plain ``git merge`` is not
possible. Instead this applies the diff between two upstream release tags on
top of the working tree with a 3-way merge, file by file. When the release
also moves the ok-script pin, the diff between the two ok-script PyPI source
distributions is applied to the vendored ``ok-script/`` copy the same way.

Usage:
    python .github/scripts/sync_upstream.py --check     # report only
    python .github/scripts/sync_upstream.py             # sync to latest
    python .github/scripts/sync_upstream.py --to v3.9.0 # sync to a tag
    python .github/scripts/sync_upstream.py --patches   # check ok-script/MACOS_PATCHES.md

The baseline lives in ``.github/upstream.json``. A Markdown report is written
to ``--report`` (default ``upstream-sync-report.md``). Exit status: 0 when the
tree is already current or the sync applied cleanly, 2 when files were left
with conflict markers or need manual attention, 1 on errors.
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

UPSTREAM_URL = "https://github.com/ok-oldking/ok-wuthering-waves.git"
TAG_REF_PREFIX = "refs/upstream-tags/"
ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / ".github" / "upstream.json"
MAC_BUILD_SUFFIX = "+macos.1"
# Files that carry the vendored ok-script build version string. The workflows
# read it from .github/upstream.json instead, because the sync can't push
# workflow changes with Actions' default token.
VERSION_FILES = (
    "run_macos.sh",
    "ok-script/setup.py",
    # Also makes the in-app updater reinstall dependencies after an ok-script update.
    "requirements-macos.txt",
)
# sdist packaging metadata that is not part of the vendored source tree.
SDIST_EXCLUDES = ("PKG-INFO", "ok_script.egg-info")
# Upstream workflows are not synced. The fork runs its own CI, and GitHub
# refuses pushes from Actions' default token that touch workflow files.
UPSTREAM_EXCLUDES = (".github/workflows",)
STABLE_TAG = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")
OK_SCRIPT_PIN = re.compile(r'"ok-script\[[^\]]*\]==([^"]+)"')
PATCH_LIST = ROOT / "ok-script" / "MACOS_PATCHES.md"


def git(*args, cwd=ROOT, check=True, input=None):
    result = subprocess.run(["git", *args], cwd=cwd, input=input, capture_output=True,
                            text=isinstance(input, str) or input is None)
    if check and result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed:\n{result.stderr}")
    return result


def version_key(tag):
    return tuple(int(part) for part in STABLE_TAG.match(tag).groups())


def fetch_upstream_tags():
    git("fetch", "--quiet", "--no-tags", UPSTREAM_URL, f"+refs/tags/v*:{TAG_REF_PREFIX}v*")
    refs = git("for-each-ref", "--format=%(refname:strip=2)", TAG_REF_PREFIX).stdout.split()
    return sorted((tag for tag in refs if STABLE_TAG.match(tag)), key=version_key)


def tag_ref(tag):
    return f"{TAG_REF_PREFIX}{tag}"


def changed_files(old, new, cwd=ROOT, excludes=()):
    args = ["diff", "--name-status", "--no-renames", old, new, "--", "."]
    args += [f":!{path}" for path in excludes]
    rows = git(*args, cwd=cwd).stdout.splitlines()
    return [tuple(row.split("\t", 1)) for row in rows if row]


def apply_file_diff(old, new, path, directory=None, source_cwd=ROOT):
    """3-way apply one file's diff. Returns 'clean', 'conflict' or 'failed'."""
    patch = git("diff", "--binary", "--no-renames", old, new, "--", path, cwd=source_cwd).stdout
    args = ["apply", "--3way", "--index"]
    if directory:
        args.append(f"--directory={directory}")
    result = subprocess.run(["git", *args], cwd=ROOT, input=patch, capture_output=True, text=True)
    output = result.stdout + result.stderr
    if result.returncode == 0 and "with conflicts" not in output:
        return "clean"
    if "with conflicts" in output:
        return "conflict"
    return "failed"


def show_blob(rev, path, cwd=ROOT):
    return subprocess.run(["git", "show", f"{rev}:{path}"], cwd=cwd, capture_output=True,
                          check=True).stdout


def find_moved_copy(old, path, local_prefix):
    """Find an unmodified copy of upstream's old file that the port moved elsewhere."""
    blob = git("rev-parse", f"{old}:{path}").stdout.strip()
    for row in git("ls-files", "--stage", "--", local_prefix or ".").stdout.splitlines():
        meta, tracked = row.split("\t", 1)
        if meta.split()[1] == blob:
            return tracked
    return None


def sync_tree(old, new, local_prefix="", source_cwd=ROOT, excludes=()):
    """Apply old..new onto ROOT/local_prefix. Returns report rows (status, path, note)."""
    rows = []
    for status, path in changed_files(old, new, cwd=source_cwd, excludes=excludes):
        local = f"{local_prefix}{path}"
        local_path = ROOT / local
        outcome = apply_file_diff(old, new, path, directory=local_prefix.rstrip("/") or None,
                                  source_cwd=source_cwd)
        if outcome != "failed":
            rows.append((outcome, local, ""))
            continue
        # The two cases git apply cannot merge: upstream deleted a file this
        # port modified, or upstream changed a file this port never had.
        if status == "D" and local_path.exists():
            git("rm", "--quiet", "--force", local)
            rows.append(("review", local, "upstream deleted it; the port had local changes"))
        elif status == "D":
            rows.append(("clean", local, "already absent locally"))
        elif status == "M" and (moved := find_moved_copy(old, path, local_prefix)):
            (ROOT / moved).write_bytes(show_blob(new, path, cwd=source_cwd))
            git("add", moved)
            rows.append(("clean", moved, f"the port keeps this file at `{moved}`"))
        elif status in ("M", "A") and not local_path.exists():
            local_path.parent.mkdir(parents=True, exist_ok=True)
            local_path.write_bytes(show_blob(new, path, cwd=source_cwd))
            git("add", local)
            rows.append(("review", local, "missing locally; copied upstream's new version whole"))
        else:
            rows.append(("failed", local, "patch did not apply; merge it by hand"))
    return rows


def ok_script_pin(rev):
    match = OK_SCRIPT_PIN.search(show_blob(rev, "pyproject.toml").decode())
    return match.group(1) if match else None


def sdist_repo(versions, workdir):
    """Build a throwaway repo with one commit per ok-script sdist; returns its path."""
    with urllib.request.urlopen("https://pypi.org/pypi/ok-script/json") as response:
        releases = json.load(response)["releases"]
    repo = workdir / "ok-script-sdists"
    git("init", "--quiet", str(repo))
    for version in versions:
        sdist = next(f for f in releases[version] if f["packagetype"] == "sdist")
        archive = workdir / sdist["filename"]
        urllib.request.urlretrieve(sdist["url"], archive)
        for child in repo.iterdir():
            if child.name != ".git":
                shutil.rmtree(child) if child.is_dir() else child.unlink()
        with tarfile.open(archive) as tar:
            tar.extractall(workdir / "x", filter="data")
        top = workdir / "x" / f"ok_script-{version}"
        shutil.copytree(top, repo, dirs_exist_ok=True)
        git("add", "-A", cwd=repo)
        git("-c", "user.name=sync", "-c", "user.email=sync@localhost", "commit", "--quiet",
            "--allow-empty", "-m", version, cwd=repo)
        git("tag", f"sdist-{version}", cwd=repo)
    return repo


def fetch_sdists(versions, workdir):
    repo = sdist_repo(versions, workdir)
    git("fetch", "--quiet", str(repo), "+refs/tags/sdist-*:refs/ok-script-sdists/*")


def unlisted_patches(version):
    """Return ok-script files that differ from the sdist but are missing from MACOS_PATCHES.md."""
    ref = f"refs/ok-script-sdists/{version}"
    if git("rev-parse", "--verify", "--quiet", ref, check=False).returncode != 0:
        with tempfile.TemporaryDirectory() as tmp:
            fetch_sdists((version,), Path(tmp))
    tree = git("write-tree").stdout.strip()
    output = git("diff", "--name-only", "--no-renames", "-z", ref, f"{tree}:ok-script").stdout
    changed = [name for name in output.split("\0")
               if name and not name.startswith(SDIST_EXCLUDES)]
    listed = set()
    for line in PATCH_LIST.read_text().splitlines():
        if line.lstrip().startswith("- "):
            listed.update(re.findall(r"`([^`\s]+)`", line))
    folders = tuple(entry for entry in listed if entry.endswith("/"))
    return [name for name in changed
            if name not in listed and name != PATCH_LIST.name and not name.startswith(folders)]


def bump_versions(old_upstream, new_upstream, old_ok, new_ok):
    for name in VERSION_FILES:
        path = ROOT / name
        if path.exists() and old_ok != new_ok:
            text = path.read_text()
            path.write_text(text.replace(f"{old_ok}{MAC_BUILD_SUFFIX}", f"{new_ok}{MAC_BUILD_SUFFIX}"))
    readme = ROOT / "README.md"
    text = readme.read_text()
    text = text.replace(f"[{old_upstream}](https://github.com/ok-oldking/ok-wuthering-waves/releases/tag/{old_upstream})",
                        f"[{new_upstream}](https://github.com/ok-oldking/ok-wuthering-waves/releases/tag/{new_upstream})")
    text = text.replace(f"**ok-script {old_ok}**", f"**ok-script {new_ok}**")
    readme.write_text(text)
    BASELINE.write_text(json.dumps({"ok_wuthering_waves": new_upstream, "ok_script": new_ok}, indent=2) + "\n")
    git("add", *VERSION_FILES, "README.md", str(BASELINE.relative_to(ROOT)))


def write_report(path, old, new, old_ok, new_ok, rows, releases, skipped=()):
    attention = [row for row in rows if row[0] != "clean"]
    lines = [f"Upstream sync from **{old}** to **{new}**.", ""]
    lines.append("Releases included: " + ", ".join(
        f"[{tag}](https://github.com/ok-oldking/ok-wuthering-waves/releases/tag/{tag})" for tag in releases))
    if old_ok != new_ok:
        lines.append(f"\nVendored ok-script: {old_ok} to {new_ok}.")
    lines.append(f"\n{len(rows)} files changed, {len(rows) - len(attention)} applied cleanly.")
    if attention:
        lines += ["", "### Needs attention", "", "| Status | File | Note |", "| --- | --- | --- |"]
        lines += [f"| {status} | `{file}` | {note} |" for status, file, note in attention]
        lines += ["", "Files marked `conflict` contain `<<<<<<< ours` / `>>>>>>> theirs` markers. "
                      "Keep the macOS code paths when resolving them."]
    if skipped:
        lines += ["", "### Not synced", "",
                  "Upstream changed these workflows. The fork keeps its own, so they were left alone:", ""]
        lines += [f"- `{file}`" for file in skipped]
    Path(path).write_text("\n".join(lines) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="only report whether upstream is ahead")
    parser.add_argument("--to", help="upstream tag to sync to (default: newest stable tag)")
    parser.add_argument("--patches", action="store_true",
                        help="list changed ok-script files missing from MACOS_PATCHES.md")
    parser.add_argument("--report", default="upstream-sync-report.md")
    args = parser.parse_args()

    baseline = json.loads(BASELINE.read_text())
    current, current_ok = baseline["ok_wuthering_waves"], baseline["ok_script"]
    if args.patches:
        missing = unlisted_patches(current_ok)
        for name in missing:
            print(f"ok-script/{name} differs from ok-script {current_ok} but is not in {PATCH_LIST.name}")
        if not missing:
            print(f"every change to ok-script {current_ok} is listed in {PATCH_LIST.name}")
        return 2 if missing else 0
    tags = fetch_upstream_tags()
    target = args.to or tags[-1]
    if target not in tags:
        sys.exit(f"unknown upstream tag {target}")
    releases = [tag for tag in tags if version_key(current) < version_key(tag) <= version_key(target)]
    print(json.dumps({"current": current, "latest": tags[-1], "target": target, "releases": releases}))
    if args.check or not releases:
        return 0

    if git("status", "--porcelain", "--untracked-files=no").stdout.strip():
        sys.exit("working tree has uncommitted changes; commit or stash them first")

    rows = sync_tree(tag_ref(current), tag_ref(target), excludes=UPSTREAM_EXCLUDES)
    skipped = [path for _, path in changed_files(tag_ref(current), tag_ref(target))
               if path.startswith(UPSTREAM_EXCLUDES)]
    target_ok = ok_script_pin(tag_ref(target)) or current_ok
    if target_ok != current_ok:
        with tempfile.TemporaryDirectory() as tmp:
            fetch_sdists((current_ok, target_ok), Path(tmp))
            rows += sync_tree(f"refs/ok-script-sdists/{current_ok}", f"refs/ok-script-sdists/{target_ok}",
                              local_prefix="ok-script/", excludes=SDIST_EXCLUDES)
    bump_versions(current, target, current_ok, target_ok)
    write_report(args.report, current, target, current_ok, target_ok, rows, releases, skipped)
    print(Path(args.report).read_text())
    return 2 if any(status != "clean" for status, _, _ in rows) else 0


if __name__ == "__main__":
    sys.exit(main())
