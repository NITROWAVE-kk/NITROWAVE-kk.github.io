#!/usr/bin/env python3
"""Obsidian Vault の集計（読み取り専用）。

使い方:
    python3 vault_stats.py                 # ホーム配下から Vault を自動検出
    python3 vault_stats.py /path/to/Vault  # 場所を指定
    python3 vault_stats.py /path/to/Vault -o stats.json

Vault のファイルは一切書き換えない。出力は JSON（既定は標準出力）。
動画に出す数字はすべてこの JSON から取る。
"""
import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

RULE_FILE = Path("00_Rules") / "code-chat-role-division.md"
SKIP_DIRS = {".obsidian", ".git", ".trash", "node_modules", ".smart-env"}
SEARCH_SKIP = {"node_modules", ".git", ".cache", "Library", "AppData", ".Trash", ".npm", ".local"}

FRONTMATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.S)
CODE_BLOCK = re.compile(r"```.*?```|~~~.*?~~~", re.S)
INLINE_CODE = re.compile(r"`[^`\n]*`")
WIKILINK = re.compile(r"(!?)\[\[([^\[\]\n]+?)\]\]")
TAG = re.compile(r"(?<![\w/#])#([^\s#.,;:!?()\[\]{}'\"`<>]+)")
FM_DATE = re.compile(r"^(created|date|updated|modified)\s*:\s*['\"]?(\d{4}-\d{2}-\d{2})", re.M | re.I)
NAME_DATE = re.compile(r"(20\d{2})-?(\d{2})-?(\d{2})")


def find_vaults(root: Path):
    """root 配下で .obsidian を持つディレクトリを列挙する。"""
    found = []
    for dirpath, dirnames, _ in os.walk(root):
        if ".obsidian" in dirnames:
            found.append(Path(dirpath))
            dirnames[:] = []  # Vault の中は潜らない
            continue
        dirnames[:] = [d for d in dirnames if d not in SEARCH_SKIP and not d.startswith(".")]
    return found


def fm_tags(fm: str):
    """frontmatter の tags（インライン配列／リスト両対応）を取り出す。"""
    tags = []
    m = re.search(r"^tags\s*:\s*(.*)$", fm, re.M)
    if not m:
        return tags
    rest = m.group(1).strip()
    if rest:
        tags += [t.strip(" '\"#") for t in rest.strip("[]").split(",")]
    else:
        for line in fm[m.end():].splitlines():
            lm = re.match(r"\s+-\s+(.+)", line)
            if lm:
                tags.append(lm.group(1).strip(" '\"#"))
            elif line.strip():
                break
    return [t for t in tags if t]


def analyze(vault: Path):
    notes = []
    other_files = Counter()
    for dirpath, dirnames, filenames in os.walk(vault):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for fn in sorted(filenames):
            p = Path(dirpath) / fn
            if fn.lower().endswith(".md"):
                notes.append(p)
            else:
                other_files[p.suffix.lower() or "(なし)"] += 1

    by_stem = defaultdict(list)
    for p in notes:
        by_stem[p.stem.lower()].append(p)

    folder_notes, folder_chars = Counter(), Counter()
    tags, inlinks = Counter(), Counter()
    edges = set()
    month_modified, month_created = Counter(), Counter()
    day_modified = Counter()
    total_chars = total_chars_nospace = total_links = embeds = unresolved = 0
    per_note = []

    for p in notes:
        rel = p.relative_to(vault)
        top = rel.parts[0] if len(rel.parts) > 1 else "(ルート直下)"
        raw = p.read_text(encoding="utf-8", errors="replace")
        st = p.stat()

        fm = ""
        m = FRONTMATTER.match(raw)
        body = raw
        if m:
            fm, body = m.group(1), raw[m.end():]
        prose = INLINE_CODE.sub("", CODE_BLOCK.sub("", body))

        chars = len(body)
        chars_ns = len(re.sub(r"\s", "", body))
        total_chars += chars
        total_chars_nospace += chars_ns
        folder_notes[top] += 1
        folder_chars[top] += chars_ns

        out = 0
        for bang, target in WIKILINK.findall(prose):
            name = target.split("|")[0].split("#")[0].strip()
            if not name:
                continue  # 同一ノート内の見出しリンク
            if bang and not name.lower().endswith(".md") and Path(name).suffix:
                embeds += 1  # 画像など添付の埋め込み
                continue
            total_links += 1
            out += 1
            key = Path(name).stem.lower() if name.lower().endswith(".md") else name.split("/")[-1].lower()
            if key in by_stem:
                dst = str(by_stem[key][0].relative_to(vault))
                inlinks[dst] += 1
                if dst != str(rel):
                    edges.add((str(rel), dst))
            else:
                unresolved += 1

        note_tags = set(fm_tags(fm)) | {t for t in TAG.findall(prose) if not t.isdigit()}
        tags.update(note_tags)

        # 作成日: frontmatter > ファイル名の日付 > ファイルの作成時刻（無ければ更新時刻）
        mtime = datetime.fromtimestamp(st.st_mtime)
        created, created_src = None, None
        for key, val in FM_DATE.findall(fm):
            if key.lower() in ("created", "date"):
                created, created_src = val, "frontmatter"
                break
        if not created:
            nm = NAME_DATE.search(p.stem)
            if nm and 1 <= int(nm.group(2)) <= 12 and 1 <= int(nm.group(3)) <= 31:
                created, created_src = "-".join(nm.groups()), "filename"
        if not created:
            bt = getattr(st, "st_birthtime", None)
            if bt:
                created, created_src = datetime.fromtimestamp(bt).strftime("%Y-%m-%d"), "birthtime"
            else:
                created, created_src = mtime.strftime("%Y-%m-%d"), "mtime"

        month_modified[mtime.strftime("%Y-%m")] += 1
        day_modified[mtime.strftime("%Y-%m-%d")] += 1
        month_created[created[:7]] += 1
        per_note.append({
            "path": str(rel), "folder": top, "chars": chars_ns, "links_out": out,
            "tags": sorted(note_tags), "modified": mtime.strftime("%Y-%m-%d %H:%M"),
            "created": created, "created_source": created_src,
        })

    for n in per_note:
        n["links_in"] = inlinks.get(n["path"], 0)

    # リンク構造（名前を含まない番号だけのグラフ。動画のノード配置に使う）
    degree = Counter()
    for a, b in edges:
        degree[a] += 1
        degree[b] += 1
    top_nodes = [p for p, _ in sorted(degree.items(), key=lambda kv: (-kv[1], kv[0]))[:90]]
    node_idx = {p: i for i, p in enumerate(top_nodes)}
    folder_order = [f for f, _ in folder_notes.most_common()]
    folder_of = {n["path"]: n["folder"] for n in per_note}
    graph = {
        "nodes": [{"degree": degree[p], "folder": folder_order.index(folder_of[p])} for p in top_nodes],
        "edges": sorted([node_idx[a], node_idx[b]] for a, b in edges if a in node_idx and b in node_idx),
        "linked_notes": len(degree), "unique_edges": len(edges),
    }

    now = datetime.now()
    mods = sorted(n["modified"] for n in per_note)
    recent = lambda days: sum(
        1 for n in per_note
        if (now - datetime.strptime(n["modified"], "%Y-%m-%d %H:%M")).days < days)

    return {
        "vault": str(vault),
        "generated_at": now.strftime("%Y-%m-%d %H:%M"),
        "method": {
            "notes": ".md ファイル数（.obsidian/.git/.trash 等を除く）",
            "chars": "frontmatter を除いた本文の文字数。chars_nospace は空白・改行を除く",
            "links": "コードブロック外の [[...]] の出現数（添付の埋め込み ![[x.png]] は embeds に分離）",
            "tags": "frontmatter の tags と本文の #タグ。ノート単位で重複排除",
            "activity": "更新=ファイルの更新時刻。作成=frontmatter(created/date)>ファイル名の日付>作成時刻>更新時刻",
        },
        "totals": {
            "notes": len(notes), "chars": total_chars, "chars_nospace": total_chars_nospace,
            "wikilinks": total_links, "unresolved_links": unresolved, "embeds": embeds,
            "unique_tags": len(tags), "top_level_folders": len(folder_notes),
            "attachments": sum(other_files.values()),
        },
        "folders": [{"folder": f, "notes": c, "chars_nospace": folder_chars[f]}
                    for f, c in folder_notes.most_common()],
        "hubs": [{"path": p, "links_in": c} for p, c in inlinks.most_common(20)],
        "tags_top": [{"tag": t, "notes": c} for t, c in tags.most_common(30)],
        "activity": {
            "modified_by_month": dict(sorted(month_modified.items())),
            "created_by_month": dict(sorted(month_created.items())),
            "created_sources": dict(Counter(n["created_source"] for n in per_note)),
            "oldest_created": min((n["created"] for n in per_note), default=None),
            "oldest_modified": mods[0] if mods else None,
            "newest_modified": mods[-1] if mods else None,
            "modified_last_7d": recent(7), "modified_last_30d": recent(30),
            "active_days_last_30d": sum(
                1 for d in day_modified
                if (now - datetime.strptime(d, "%Y-%m-%d")).days < 30),
        },
        "graph": graph,
        "other_file_types": dict(other_files.most_common()),
        "notes": sorted(per_note, key=lambda n: n["path"]),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("vault", nargs="?", help="Vault のパス（省略時はホーム配下を検索）")
    ap.add_argument("-o", "--out", help="JSON の出力先（省略時は標準出力）")
    args = ap.parse_args()

    if args.vault:
        vault = Path(args.vault).expanduser().resolve()
        if not (vault / ".obsidian").is_dir():
            sys.exit(f".obsidian が見つかりません: {vault}")
    else:
        found = find_vaults(Path.home())
        matched = [v for v in found if (v / RULE_FILE).is_file()]
        if len(matched) != 1:
            print("Vault を1つに特定できません。パスを引数で指定してください。", file=sys.stderr)
            for v in found:
                mark = "*" if v in matched else " "
                print(f" {mark} {v}", file=sys.stderr)
            sys.exit(2)
        vault = matched[0]

    text = json.dumps(analyze(vault), ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"{vault} -> {args.out}", file=sys.stderr)
    else:
        print(text)


if __name__ == "__main__":
    main()
