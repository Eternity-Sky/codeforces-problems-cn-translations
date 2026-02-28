#!/usr/bin/env python3
"""
Codeforces 题目自动翻译脚本
使用免费翻译 API（LibreTranslate 社区实例 / MyMemory）无需 API Key
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

try:
    import cloudscraper
    SCRAPER = cloudscraper.create_scraper()
except ImportError:
    SCRAPER = requests.Session()

# 免费翻译 API 配置（无需 Key）
LIBRETRANSLATE_URL = "https://translate.cutie.dating"  # 社区实例，免 Key
MYMEMORY_URL = "https://api.mymemory.translated.net/get"

# Codeforces 标签中英对照
TAG_MAP = {
    "math": "数学",
    "implementation": "实现",
    "dp": "DP",
    "greedy": "贪心",
    "brute force": "暴力",
    "constructive algorithms": "构造",
    "sortings": "排序",
    "binary search": "二分",
    "graphs": "图论",
    "trees": "树",
    "strings": "字符串",
    "data structures": "数据结构",
    "geometry": "几何",
    "number theory": "数论",
    "combinatorics": "组合数学",
    "two pointers": "双指针",
    "bitmasks": "位运算",
    "dfs and similar": "DFS",
    "shortest paths": "最短路",
    "probabilities": "概率",
    "games": "博弈",
    "flows": "网络流",
    "dsu": "并查集",
    "divide and conquer": "分治",
    "hashing": "哈希",
    "interactive": "交互",
    "schedules": "调度",
    "matrices": "矩阵",
    "fft": "FFT",
    "ternary search": "三分",
    "expression parsing": "表达式解析",
    "meet-in-the-middle": "折半搜索",
    "2-sat": "2-SAT",
    "chinese remainder theorem": "中国剩余定理",
}


def translate_libretranslate(text: str, source: str = "en", target: str = "zh-Hans") -> str:
    """使用 LibreTranslate 社区实例翻译（免 Key）"""
    try:
        r = requests.post(
            f"{LIBRETRANSLATE_URL}/translate",
            json={"q": text, "source": source, "target": target, "format": "text"},
            headers={"User-Agent": "Codeforces-Translate-Bot/1.0"},
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        return data.get("translatedText", text)
    except Exception as e:
        print(f"  [LibreTranslate 失败] {e}", file=sys.stderr)
        return ""


def translate_mymemory(text: str, source: str = "en", target: str = "zh-CN") -> str:
    """使用 MyMemory 翻译（免 Key，每日约 5000 字符限制）"""
    try:
        r = requests.get(
            MYMEMORY_URL,
            params={"q": text, "langpair": f"{source}|{target}"},
            headers={"User-Agent": "Codeforces-Translate-Bot/1.0"},
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        if data.get("responseStatus") == 200:
            return data.get("responseData", {}).get("translatedText", text)
    except Exception as e:
        print(f"  [MyMemory 失败] {e}", file=sys.stderr)
    return ""


def translate(text: str, source: str = "en", target: str = "zh") -> str:
    """翻译文本，优先 LibreTranslate，失败则用 MyMemory"""
    if not text or not text.strip():
        return text
    # LibreTranslate 用 zh-Hans，MyMemory 用 zh-CN
    result = translate_libretranslate(text, source, "zh-Hans")
    if not result:
        result = translate_mymemory(text, source, "zh-CN")
    time.sleep(0.5)  # 避免请求过快
    return result if result else text


def fetch_problem(contest_id: int, problem_index: str) -> dict | None:
    """从 Codeforces 抓取题目内容"""
    url = f"https://codeforces.com/contest/{contest_id}/problem/{problem_index}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        r = SCRAPER.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        r.encoding = "utf-8"
        soup = BeautifulSoup(r.text, "html.parser")
        return parse_problem_html(soup)
    except Exception as e:
        print(f"抓取失败: {e}", file=sys.stderr)
        return None


def parse_problem_html(soup: BeautifulSoup) -> dict:
    """解析 Codeforces 题目 HTML"""
    ps = soup.find("div", class_="problem-statement")
    if not ps:
        return {}

    def get_text(el):
        if not el:
            return ""
        return el.get_text(separator=" ", strip=True)

    title_el = ps.find("div", class_="header").find("div", class_="title")
    full_title = get_text(title_el)  # e.g. "A. Theatre Square"
    name = re.sub(r"^[A-Z]\.\s*", "", full_title) if full_title else ""

    # 题目描述（header 后的第一个 div）
    header = ps.find("div", class_="header")
    desc_div = header.find_next_sibling("div")
    description = html_to_markdown(desc_div) if desc_div else ""

    # 输入格式
    inp_spec = ps.find("div", class_="input-specification")
    input_section = extract_section(inp_spec) if inp_spec else ""

    # 输出格式
    out_spec = ps.find("div", class_="output-specification")
    output_section = extract_section(out_spec) if out_spec else ""

    # 样例
    sample_tests = ps.find("div", class_="sample-tests")
    examples = parse_examples(sample_tests) if sample_tests else []

    # Note（如果有）
    note_div = ps.find("div", class_="note")
    note_section = extract_section(note_div) if note_div else ""

    return {
        "title": name,
        "full_title": full_title,
        "description": description,
        "input_section": input_section,
        "output_section": output_section,
        "examples": examples,
        "note": note_section,
    }


def extract_section(div) -> str:
    """提取 section 内容，去掉标题"""
    if not div:
        return ""
    title = div.find("div", class_="section-title")
    if title:
        title.decompose()
    return html_to_markdown(div)


def html_to_markdown(el) -> str:
    """简单 HTML 转 Markdown，保留 LaTeX"""
    if not el:
        return ""
    text = str(el)
    # 保留 $...$ LaTeX
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</p>", "\n\n", text, flags=re.I)
    text = re.sub(r"<p>", "", text, flags=re.I)
    text = re.sub(r"<pre[^>]*>", "\n```\n", text, flags=re.I)
    text = re.sub(r"</pre>", "\n```\n", text, flags=re.I)
    soup = BeautifulSoup(text, "html.parser")
    return soup.get_text(separator=" ", strip=True)


def parse_examples(sample_tests) -> list:
    """解析样例"""
    examples = []
    sample_test = sample_tests.find("div", class_="sample-test")
    if not sample_test:
        return examples
    inputs = sample_test.find_all("div", class_="input")
    outputs = sample_test.find_all("div", class_="output")
    for i, (inp, out) in enumerate(zip(inputs, outputs)):
        inp_pre = inp.find("pre")
        out_pre = out.find("pre")
        examples.append({
            "input": inp_pre.get_text() if inp_pre else "",
            "output": out_pre.get_text() if out_pre else "",
        })
    return examples


def get_problem_meta(contest_id: int, problem_index: str) -> dict:
    """从 Codeforces API 获取题目元信息（难度、标签）"""
    try:
        r = requests.get(
            "https://codeforces.com/api/contest.standings",
            params={"contestId": contest_id, "from": 1, "count": 1},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        if data.get("status") != "OK":
            return {}
        for p in data.get("result", {}).get("problems", []):
            if p.get("index") == problem_index:
                return {
                    "rating": p.get("rating", "?"),
                    "tags": p.get("tags", []),
                }
    except Exception:
        pass
    return {"rating": "?", "tags": []}


def tags_to_chinese(tags: list) -> str:
    """标签转中文，全角逗号分隔"""
    cn = [TAG_MAP.get(t.lower(), t) for t in tags]
    return "，".join(cn)


def translate_problem(problem: dict) -> dict:
    """翻译题目各部分"""
    translated = {}
    translated["title"] = translate(problem["title"])
    translated["description"] = translate(problem["description"])
    translated["input_section"] = translate(problem["input_section"])
    translated["output_section"] = translate(problem["output_section"])
    translated["note"] = translate(problem["note"]) if problem["note"] else ""
    translated["examples"] = problem["examples"]  # 样例不翻译
    return translated


def build_zh_md(problem: dict, translated: dict, contest_id: int, problem_index: str, author: str = "github-actions") -> str:
    """生成中文 md"""
    lines = [
        "---",
        f"author: {author}",
        "---",
        "",
        f"# {problem_index}. {translated['title']}",
        "",
        "## 题目描述",
        "",
        translated["description"],
        "",
    ]
    if translated["input_section"]:
        lines.extend(["## 输入格式", "", translated["input_section"], ""])
    if translated["output_section"]:
        lines.extend(["## 输出格式", "", translated["output_section"], ""])
    if translated["examples"]:
        lines.append("## 样例")
        for i, ex in enumerate(translated["examples"], 1):
            sub = f" {i}" if len(translated["examples"]) > 1 else ""
            lines.extend([
                "", f"### 输入{sub}",
                "", "```", ex["input"].strip(), "```", "",
                "### 输出",
                "", "```", ex["output"].strip(), "```", "",
            ])
    if translated["note"]:
        lines.extend(["## 注意", "", translated["note"], ""])
    return "\n".join(lines).strip() + "\n"


def build_en_md(problem: dict, contest_id: int, problem_index: str) -> str:
    """生成英文 md（原文）"""
    lines = [
        f"# {problem_index}. {problem['title']}",
        "",
        problem["description"],
        "",
    ]
    if problem["input_section"]:
        lines.extend(["## Input", "", problem["input_section"], ""])
    if problem["output_section"]:
        lines.extend(["## Output", "", problem["output_section"], ""])
    if problem["examples"]:
        lines.append("## Examples")
        for i, ex in enumerate(problem["examples"], 1):
            lines.extend([
                "", "### Input",
                "", "```", ex["input"].strip(), "```", "",
                "### Output",
                "", "```", ex["output"].strip(), "```", "",
            ])
    if problem["note"]:
        lines.extend(["## Note", "", problem["note"], ""])
    return "\n".join(lines).strip() + "\n"


def update_index(contest_id: int, problem_index: str, en_title: str, zh_title: str, rating: str, tags_en: list, tags_zh: str, repo_root: Path):
    """更新 index.md，若题目已存在则跳过"""
    zh_idx = repo_root / "docs" / "zh" / "problem" / "index.md"
    en_idx = repo_root / "docs" / "en" / "problem" / "index.md"
    if not zh_idx.exists():
        return
    content = zh_idx.read_text(encoding="utf-8")
    if f"/problem/{contest_id}/{problem_index}" in content:
        return
    contest_header = f"## {contest_id}"
    zh_entry = f"[{en_title} \\| {zh_title}](/problem/{contest_id}/{problem_index})（{tags_zh}）"
    en_entry = f"[{en_title}](/en/problem/{contest_id}/{problem_index}) ({', '.join(tags_en)})"
    new_block = f"\n{contest_header}\n\n|{problem_index} [{rating}]|\n|:-:|\n|{zh_entry}|\n\n"
    if contest_header not in content:
        content = content.rstrip() + new_block
    else:
        # 在已有 contest 块中添加新题目列
        pattern = rf"({re.escape(contest_header)}\n\n)([^\n]+\n)([^\n]+\n)([^\n]+)"
        m = re.search(pattern, content)
        if m:
            pre, hdr, sep, row = m.group(1), m.group(2), m.group(3), m.group(4)
            hdr = hdr.rstrip().rstrip("|") + f"|{problem_index} [{rating}]|\n"
            sep = sep.rstrip().rstrip("|") + "|:-:|\n"
            row = row.rstrip().rstrip("|") + f"|{zh_entry}|\n"
            content = content[: m.start()] + pre + hdr + sep + row + content[m.end() :]
    zh_idx.write_text(content, encoding="utf-8")
    if en_idx.exists() and f"/en/problem/{contest_id}/{problem_index}" not in en_idx.read_text(encoding="utf-8"):
        en_content = en_idx.read_text(encoding="utf-8")
        if contest_header not in en_content:
            en_content = en_content.rstrip() + f"\n{contest_header}\n\n|{problem_index} [{rating}]|\n|:-:|\n|{en_entry}|\n\n"
        else:
            m = re.search(rf"({re.escape(contest_header)}\n\n)([^\n]+\n)([^\n]+\n)([^\n]+)", en_content)
            if m:
                pre, hdr, sep, row = m.group(1), m.group(2), m.group(3), m.group(4)
                hdr = hdr.rstrip().rstrip("|") + f"|{problem_index} [{rating}]|\n"
                sep = sep.rstrip().rstrip("|") + "|:-:|\n"
                row = row.rstrip().rstrip("|") + f"|{en_entry}|\n"
                en_content = en_content[: m.start()] + pre + hdr + sep + row + en_content[m.end() :]
        en_idx.write_text(en_content, encoding="utf-8")


def run_translate(contest_id: int, problem_index: str, repo_root: Path, author: str = "Eternity-Sky", force: bool = False):
    """执行单题翻译并保存"""
    problem_index = problem_index.upper()
    zh_file = repo_root / "docs" / "zh" / "problem" / str(contest_id) / f"{problem_index}.md"
    if zh_file.exists() and not force:
        print(f"跳过 CF{contest_id}{problem_index}（已存在，使用 --force 强制覆盖）")
        return True
    print(f"正在处理 CF{contest_id}{problem_index}...")
    problem = fetch_problem(contest_id, problem_index)
    if not problem:
        print("  抓取失败，跳过")
        return False
    meta = get_problem_meta(contest_id, problem_index)
    time.sleep(1)  # Codeforces API 限制
    translated = translate_problem(problem)
    rating = meta.get("rating", "?")
    tags_en = meta.get("tags", [])
    tags_zh = tags_to_chinese(tags_en)
    zh_dir = repo_root / "docs" / "zh" / "problem" / str(contest_id)
    en_dir = repo_root / "docs" / "en" / "problem" / str(contest_id)
    zh_dir.mkdir(parents=True, exist_ok=True)
    en_dir.mkdir(parents=True, exist_ok=True)
    zh_md = build_zh_md(problem, translated, contest_id, problem_index, author)
    en_md = build_en_md(problem, contest_id, problem_index)
    (zh_dir / f"{problem_index}.md").write_text(zh_md, encoding="utf-8")
    (en_dir / f"{problem_index}.md").write_text(en_md, encoding="utf-8")
    update_index(contest_id, problem_index, problem["title"], translated["title"], str(rating), tags_en, tags_zh, repo_root)
    print(f"  已保存 docs/zh/problem/{contest_id}/{problem_index}.md")
    return True


def main():
    parser = argparse.ArgumentParser(description="Codeforces 题目自动翻译")
    parser.add_argument("contest_id", type=int, nargs="?", help="比赛 ID（使用 --config 时可选）")
    parser.add_argument("problem_index", type=str, nargs="?", help="题号，如 A（使用 --config 时可选）")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--author", default="Eternity-Sky")
    parser.add_argument("--config", type=Path, help="从 JSON 配置文件读取题目列表，格式: [{\"contest\":1,\"problem\":\"A\"},...]")
    parser.add_argument("--force", action="store_true", help="强制覆盖已存在的翻译")
    args = parser.parse_args()
    repo_root = args.repo_root
    if args.config and args.config.exists():
        config = json.loads(args.config.read_text(encoding="utf-8"))
        for item in config:
            cid = item.get("contest") or item.get("contestId")
            pid = item.get("problem") or item.get("problemIndex") or item.get("index")
            if cid and pid:
                run_translate(int(cid), str(pid), repo_root, args.author, args.force)
                time.sleep(2)
    elif args.contest_id is not None and args.problem_index:
        run_translate(args.contest_id, args.problem_index, repo_root, args.author, args.force)
    else:
        parser.error("请提供 contest_id 和 problem_index，或使用 --config 指定配置文件")


if __name__ == "__main__":
    main()
