"""可选：Gradio 网页外壳（评审"点开就能用"的 Demo 链接）。

    pip install gradio
    python app.py        # 默认 http://127.0.0.1:7860

只是薄壳：所有逻辑仍在 labmemory 里，网页层不承担任何判断。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from labmemory import config, prompts, report              # noqa: E402
from labmemory.agent import Agent                          # noqa: E402
from labmemory.llm import OpenAICompat, RulePolicy         # noqa: E402
from labmemory.store import Store                          # noqa: E402
from labmemory.tools import Ctx                            # noqa: E402

CFG = config.load()                                        # 读 labmemory.toml
DB = Path(CFG.paths.db)
DATA = Path(CFG.paths.data_dir).expanduser().resolve()


def _llm(mode: str):
    if CFG.llm.offline or not CFG.llm.api_key:
        return RulePolicy(mode=mode, since_hours=CFG.scan.hours), "rule(offline)"
    return OpenAICompat(model=CFG.llm.model, base_url=CFG.llm.base_url,
                        api_key=CFG.llm.api_key, temperature=CFG.llm.temperature,
                        timeout=CFG.llm.timeout), f"llm({CFG.llm.model})"


def _ctx() -> Ctx:
    return Ctx(root=DATA, store=Store(DB),
               state_file=DB.resolve().parent / ".labmemory" / "ingested.json",
               interactive=False)


def ask(question: str, trace: bool = True) -> str:
    ctx = _ctx()
    llm, tag = _llm("query")
    res = Agent(llm, ctx, prompts.QUERY_SYSTEM,
                max_turns=CFG.agent.max_turns_query, verbose=False).run(question)
    body = res.get("final") or res.get("error", "无输出")
    return body + (f"\n\n---\n`{tag}` · {res.get('turns')} 轮 · {res.get('elapsed')}s" if trace else "")


def scan() -> str:
    ctx = _ctx()
    llm, tag = _llm("ingest")
    system = prompts.INGEST_SYSTEM.replace("{tags}", "、".join(prompts.TAG_VOCAB))
    res = Agent(llm, ctx, system, max_turns=CFG.agent.max_turns_ingest,
                max_calls=CFG.agent.max_calls, verbose=False).run(
        f"数据目录：{DATA}\n请处理其中最近 {CFG.scan.hours:g} 小时内新增或改动过的实验记录。")
    return (res.get("final") or res.get("error", "")) + f"\n\n---\n`{tag}`"


def weekly() -> str:
    return report.build_weekly(Store(DB).recent(days=7), days=7)


def main() -> int:
    try:
        import gradio as gr
    except ImportError:
        print("需要先安装：pip install gradio")
        return 1

    with gr.Blocks(title="LabMemory · 实验记录知识卡片") as demo:
        gr.Markdown("## LabMemory\n散落的实验日志 → 可检索的知识卡片。"
                    "先点「扫描实验记录」，再用自然语言问。")
        with gr.Tab("自然语言检索"):
            q = gr.Textbox(label="问一句", placeholder="上次学习率 0.001 那次的 loss 最后降到多少？")
            gr.Examples([["上次学习率 0.001 那次的 loss 最后降到多少？"],
                         ["最近有没有出现异常或者崩溃的实验？"],
                         ["lr 放大到 0.005 效果怎么样？"]], inputs=q)
            a = gr.Markdown()
            gr.Button("检索").click(ask, inputs=q, outputs=a)
        with gr.Tab("扫描实验记录"):
            s = gr.Markdown()
            gr.Button("扫描数据目录").click(scan, outputs=s)
        with gr.Tab("周报"):
            w = gr.Markdown()
            gr.Button("生成本周周报").click(weekly, outputs=w)
    demo.launch(server_name="127.0.0.1", server_port=7860)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
