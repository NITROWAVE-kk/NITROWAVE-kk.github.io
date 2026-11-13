#!/usr/bin/env python3
"""stats.json（vault_stats.py の出力）から、動画に出す内容 content.json を作る。

    python3 build_content.py stats.json -o content.json

ここで作られる content.json が「動画に出る数字と文言のすべて」。
レンダリング前に中身を確認し、必要なら手で編集する（lines / final など）。

既定ではフォルダ名を「フォルダA」のように伏せる。出してよい場合だけ --show-folders を付ける。
タグ名も既定では出さない（--show-tags で出す）。
"""
import argparse
import json
from pathlib import Path


def month_range(first, last):
    y, m = map(int, first.split("-"))
    out = []
    while f"{y:04d}-{m:02d}" <= last:
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stats")
    ap.add_argument("-o", "--out", default="content.json")
    ap.add_argument("--activity", choices=["modified", "created"], default="modified",
                    help="月別グラフに使う日付（更新 or 作成）")
    ap.add_argument("--months", type=int, default=12, help="月別グラフに出す月数（最新から）")
    ap.add_argument("--show-folders", action="store_true", help="フォルダ名をそのまま出す")
    ap.add_argument("--show-tags", action="store_true", help="タグ名をそのまま出す")
    args = ap.parse_args()

    s = json.loads(Path(args.stats).read_text(encoding="utf-8"))
    t, act = s["totals"], s["activity"]

    # フォルダ: 上位5 + その他（6個以下ならそのまま）
    fl = s["folders"]
    if len(fl) > 6:
        rest = fl[5:]
        fl = fl[:5] + [{"folder": f"その他（{len(rest)}フォルダ）", "notes": sum(f["notes"] for f in rest), "_other": True}]
    folders = []
    for i, f in enumerate(fl):
        name = f["folder"]
        if not args.show_folders and not f.get("_other") and name != "(ルート直下)":
            name = f"フォルダ{chr(ord('A') + i)}"
        folders.append({"name": name, "notes": f["notes"]})

    by_month = act[f"{args.activity}_by_month"]
    months = []
    if by_month:
        keys = month_range(min(by_month), max(by_month))[-args.months:]
        months = [{"ym": k, "count": by_month.get(k, 0)} for k in keys]

    kind = "更新" if args.activity == "modified" else "作成"
    if args.show_tags and s["tags_top"]:
        lines_title = "タグ上位（付いているノート数）"
        lines = [f"#{x['tag']}　{x['notes']}" for x in s["tags_top"][:6]]
    else:
        lines_title = "Vaultの中身（集計値）"
        lines = [
            f"リンクでつながるノート　{s['graph']['linked_notes']:,}",
            f"タグの種類　{t['unique_tags']:,}",
            f"直近30日で{kind}したノート　{act['modified_last_30d']:,}" if args.activity == "modified"
            else f"直近30日で更新したノート　{act['modified_last_30d']:,}",
            f"直近30日のうち更新があった日　{act['active_days_last_30d']}日",
        ]
        if s["hubs"]:
            lines.append(f"最多の被リンク　1ノートに{s['hubs'][0]['links_in']:,}本")

    content = {
        "sample": False,
        "generated_at": s["generated_at"],
        "title": ["Vaultから見える", "今の実力"],
        "subtitle": "数字はすべてVaultの実データから集計",
        "totals": {
            "notes": t["notes"], "links": t["wikilinks"], "chars": t["chars_nospace"],
            "tags": t["unique_tags"], "folders": t["top_level_folders"],
        },
        "folders_title": "フォルダ別ノート数",
        "folders": folders,
        "months_title": f"月別の{kind}ノート数",
        "months": months,
        "activity": {
            "last30_label": "直近30日で更新したノート",
            "last30": act["modified_last_30d"],
            "range": f"{(act['oldest_created'] or '')[:7]} → {(act['newest_modified'] or '')[:7]}",
        },
        "lines_title": lines_title,
        "lines": lines,
        "final": ["全部、実データ。"],
        "final_sub": f"{t['notes']:,}ノート・{t['wikilinks']:,}リンク・{t['chars_nospace']:,}文字",
        "graph": s["graph"],
    }
    Path(args.out).write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"-> {args.out}")
    print("動画に出る文言:")
    for k in ("title", "subtitle", "folders_title", "months_title", "lines_title", "lines", "final", "final_sub"):
        print(f"  {k}: {content[k]}")
    print("  folders:", [(f["name"], f["notes"]) for f in folders])
    print("  months:", [(m["ym"], m["count"]) for m in months])
    print("  totals:", content["totals"], "activity:", content["activity"])


if __name__ == "__main__":
    main()
