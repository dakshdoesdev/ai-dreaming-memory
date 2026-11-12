"""Rebuild documentation visuals from the published pilot (optional: matplotlib)."""

import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"


def svg(name, width, height, content, title, description):
    document = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">
<title id="title">{title}</title><desc id="desc">{description}</desc>
<style>text{{font-family:DejaVu Sans,Arial,sans-serif}}.small{{font-size:16px}}.label{{font-size:14px;letter-spacing:2px}}.body{{font-size:19px}}</style>
{content}</svg>'''
    ET.fromstring(document)
    (ASSETS / name).write_text(document + "\n")


def main():
    ASSETS.mkdir(exist_ok=True)
    svg("hero.svg", 1440, 490, '''
<defs><pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse"><path d="M40 0H0V40" fill="none" stroke="#fff" stroke-opacity=".035"/></pattern></defs>
<rect width="1440" height="490" rx="24" fill="#101e2b"/>
<rect width="1440" height="490" rx="24" fill="url(#grid)"/>
<path d="M70 76h36" stroke="#68dbc4" stroke-width="4"/>
<text x="122" y="82" fill="#93aab9" class="label">AN EVIDENCE-FIRST RESEARCH EXPERIMENT</text>
<text x="68" y="174" fill="#f5f7f5" font-size="59" font-weight="700">Dreaming Memory</text>
<text x="68" y="242" fill="#f5f7f5" font-size="59" font-weight="700">Research Lab</text>
<text x="70" y="300" fill="#bfccd3" font-size="22">Can consolidation help an agent remember?</text>
<text x="70" y="339" fill="#93aab9" class="body">Collect papers. Preserve evidence. Test the memory.</text>
<rect x="70" y="386" width="460" height="42" rx="21" fill="#1a303c"/>
<text x="91" y="412" fill="#a7e4d7" class="small">arXiv  /  DeepSeek  /  SQLite  /  RAG</text>
<circle cx="1118" cy="246" r="172" fill="none" stroke="#38505d" stroke-width="1"/>
<circle cx="1118" cy="246" r="131" fill="none" stroke="#38505d" stroke-width="1" stroke-dasharray="4 8"/>
<path d="M966 159L1236 220L1048 352Z" fill="#68dbc4" fill-opacity=".035" stroke="#68dbc4" stroke-opacity=".55"/>
<circle cx="966" cy="159" r="15" fill="#68dbc4"/>
<circle cx="1236" cy="220" r="15" fill="#f1bf77"/>
<circle cx="1048" cy="352" r="15" fill="#91adf5"/>
<text x="910" y="119" fill="#e0f4ee" class="body">Evidence</text>
<text x="1222" y="269" fill="#f4dfc2" class="body">Memory</text>
<text x="1009" y="400" fill="#d5dff8" class="body">Replay</text>
<text x="1121" y="247" text-anchor="middle" fill="#f5f7f5" font-size="31" font-weight="700">Recall</text>
<text x="1121" y="275" text-anchor="middle" fill="#93aab9" class="small">measured, not assumed</text>
''', "Dreaming Memory Research Lab", "An arXiv research-memory experiment connecting evidence, compact memories, and synthetic replay. Decorative concept illustration, not an application screenshot.")

    svg("architecture.svg", 1440, 640, '''
<defs><marker id="arrow" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto"><path d="M0 0L10 4L0 8" fill="none" stroke="#69818d" stroke-width="1.4"/></marker></defs>
<rect width="1440" height="640" rx="20" fill="#f5f7f6"/>
<text x="56" y="65" fill="#172f3d" font-size="30" font-weight="700">One corpus. Three memory conditions. Held-out questions.</text>
<text x="56" y="103" fill="#536a76" class="body">Original evidence stays local; model-generated records retain source provenance.</text>
<g stroke="#69818d" stroke-width="2" fill="none" marker-end="url(#arrow)">
<path d="M254 250H320"/><path d="M640 250H708"/><path d="M1014 225H1088"/>
<path d="M494 314V414H708"/><path d="M580 174V137H1210V164"/>
</g>
<rect x="56" y="184" width="198" height="130" rx="12" fill="#e7ecee" stroke="#cbd5d9"/>
<text x="78" y="224" fill="#172f3d" font-size="23" font-weight="700">arXiv papers</text>
<text x="78" y="257" fill="#536a76" class="small">Pinned IDs + metadata</text>
<text x="78" y="284" fill="#536a76" class="small">HTML / PDF text</text>
<rect x="320" y="174" width="320" height="140" rx="12" fill="#172f3d"/>
<text x="345" y="215" fill="#fff" font-size="23" font-weight="700">Persistent SQLite store</text>
<text x="345" y="251" fill="#bdcdd4" class="small">Full text · chunks · hashes</text>
<text x="345" y="279" fill="#bdcdd4" class="small">Original conversations stay intact</text>
<rect x="708" y="164" width="306" height="150" rx="12" fill="#e3f1eb" stroke="#b3d5c4"/>
<text x="731" y="204" fill="#155c4a" font-size="22" font-weight="700">DeepSeek consolidation</text>
<text x="731" y="241" fill="#426d5f" class="small">Compact facts + replay pairs</text>
<text x="731" y="272" fill="#426d5f" class="small">Schema + source-span validation</text>
<rect x="708" y="386" width="306" height="130" rx="12" fill="#eeeaf4" stroke="#d2c9e0"/>
<text x="731" y="425" fill="#57466d" font-size="22" font-weight="700">Paper claim extraction</text>
<text x="731" y="459" fill="#71617f" class="small">Methods · findings · gap candidates</text>
<text x="731" y="489" fill="#71617f" class="small">Separate records; review required</text>
<rect x="1088" y="164" width="296" height="150" rx="12" fill="#fff" stroke="#bdcbd0"/>
<text x="1111" y="204" fill="#172f3d" font-size="22" font-weight="700">BM25 + answering</text>
<text x="1111" y="239" fill="#536a76" class="small">raw / +memory / +replay</text>
<text x="1111" y="271" fill="#536a76" class="small">Same model + character budget</text>
<path d="M1240 314V387" stroke="#69818d" stroke-width="2" marker-end="url(#arrow)"/>
<rect x="1088" y="386" width="296" height="130" rx="12" fill="#faefd9" stroke="#e5d0a9"/>
<text x="1111" y="425" fill="#7b5a24" font-size="22" font-weight="700">Held-out evaluation</text>
<text x="1111" y="459" fill="#8a7148" class="small">Answers · scores · token usage</text>
<text x="1111" y="489" fill="#8a7148" class="small">Isolated frozen corpus per trial</text>
<rect x="56" y="557" width="1328" height="46" rx="8" fill="#e8edeb"/>
<text x="78" y="586" fill="#526a62" class="small">Extraction claims do not enter factual retrieval. Test questions and rubric answers never enter memory construction.</text>
''', "Research agent data flow", "arXiv text enters SQLite. Separate DeepSeek steps extract candidate claims and create compact memories and replay. Raw and derived records feed three BM25 retrieval conditions, then held-out evaluation. Extraction candidates stay outside factual retrieval.")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    report = json.loads((ROOT / "artifacts/deepseek-pilot.json").read_text())
    assert not report["smoke_only"] and len(report["records"]) == 36
    assert len(report["papers"]) == 4 and report["max_chunks_per_paper"] == 6
    arms = ("rag", "summary", "replay")
    totals = [sum(row["arm"] == arm for row in report["records"]) for arm in arms]
    passed = [sum(row["passed"] for row in report["records"] if row["arm"] == arm) for arm in arms]
    assert all(p / n == report["metrics"][a]["answer_accuracy"] for a, p, n in zip(arms, passed, totals))
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 12, "axes.spines.top": False,
                         "axes.spines.right": False, "axes.spines.left": False})
    fig, axes = plt.subplots(1, 2, figsize=(14.4, 6.4), facecolor="#f5f7f6")
    colors = ["#70848f", "#21866d", "#d4a14e"]
    names = ["Raw RAG", "+ Memory", "+ Memory\n+ Replay"]
    for ax in axes:
        ax.set_facecolor("#f5f7f6")
        ax.set_axisbelow(True)
        ax.grid(axis="y", color="#dce3e2", linewidth=.8)
        ax.tick_params(axis="both", length=0, labelcolor="#536a76", pad=10)
        ax.spines["bottom"].set_color("#ccd6d8")
    axes[0].bar(names, passed, color=colors, width=.55, zorder=3)
    axes[0].set_ylim(0, 13)
    axes[0].set_yticks([0, 3, 6, 9, 12])
    axes[0].set_title("Automatic rubric checks passed", loc="left", color="#172f3d", fontsize=16, pad=22)
    for i, (p, n) in enumerate(zip(passed, totals)):
        axes[0].text(i, p + .32, f"{p}/{n}", ha="center", color="#172f3d", fontsize=17, weight="bold")
    input_tokens = [report["metrics"][arm]["usage"]["prompt_tokens"] for arm in arms]
    output_tokens = [report["metrics"][arm]["usage"]["completion_tokens"] for arm in arms]
    axes[1].bar(names, input_tokens, color=colors, width=.55, zorder=3)
    axes[1].bar(names, output_tokens, bottom=input_tokens, color="#172f3d", width=.55, zorder=3)
    axes[1].set_ylim(0, 8800)
    axes[1].set_yticks([0, 2000, 4000, 6000, 8000], ["0", "2k", "4k", "6k", "8k"])
    axes[1].set_title("Answering tokens · input + output", loc="left", color="#172f3d", fontsize=16, pad=22)
    for i, (a, b) in enumerate(zip(input_tokens, output_tokens)):
        axes[1].text(i, a + b + 220, f"{a+b:,}", ha="center", color="#172f3d", fontsize=15, weight="bold")
    fig.suptitle("Consolidation helped this pilot. Replay added no gain.", x=.065, y=.97,
                 ha="left", color="#172f3d", fontsize=23, weight="bold")
    fig.text(.065, .89, "4 papers · first 6 chunks each · 12 questions · fixed character budget · one live run",
             color="#536a76", fontsize=12)
    prep = report["preprocessing_usage"]
    prep_tokens = prep["prompt_tokens"] + prep["completion_tokens"]
    fig.text(.065, .075, f"Memory construction adds {prep_tokens:,} shared tokens. Equal characters did not mean equal token usage.",
             color="#536a76", fontsize=12)
    fig.text(.065, .035, "Literal scoring has known false negatives. These results do not establish general superiority.",
             color="#536a76", fontsize=12)
    fig.subplots_adjust(left=.065, right=.97, bottom=.23, top=.76, wspace=.3)
    fig.savefig(ASSETS / "pilot-results.png", dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)
    print("Rendered hero.svg, architecture.svg, pilot-results.png from the published pilot.")


if __name__ == "__main__":
    main()
