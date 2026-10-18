"""生成一套可复现的样例实验数据（不含真实实验内容，用于演示与自测）。

场景覆盖知识管理最典型的四类情况：
  1. 一次正常收敛的 run；
  2. 一次学得太慢、后期停滞的 run（换了个更大的 lr）；
  3. 一次跑到一半 OOM 崩掉的 run；
  4. 同一条命令隔天重跑成功的 run —— 与 3 同名同 run，会形成"实验链"；
  5. 一个超参扫描表 + 一份手写组会笔记 + 一次评测的 jsonl。
"""

from __future__ import annotations

import json
import random
from pathlib import Path


def _train_log(path: Path, steps: int, l0: float, l1: float, a0: float, a1: float,
               crash_at: int | None = None, plateau_from: int | None = None,
               header_note: str = "") -> None:
    rnd = random.Random(hash(path.name) & 0xFFFF)
    lines = [
        f"[2026-10-13 09:12:03] config: model=qwen3-7b lr=0.001 batch_size=32 seed=42 "
        f"dataset=sft-v3 max_steps={steps}" + (f' note="{header_note}"' if header_note else ""),
        "[2026-10-13 09:12:04] start training",
    ]
    for s in range(10, steps + 1, 10):
        t = s / steps
        loss = l0 + (l1 - l0) * (t ** 0.55) + rnd.uniform(-0.012, 0.012)
        acc = a0 + (a1 - a0) * (t ** 0.7) + rnd.uniform(-0.004, 0.004)
        if plateau_from and s >= plateau_from:
            loss = l1 + 0.004 * ((s // 10) % 2)      # 停滞：在末值附近抖动
            acc = a1 - 0.002 * ((s // 10) % 2)
        lines.append(f"step {s} loss={loss:.4f} acc={acc:.4f} lr=0.001 grad_norm={rnd.uniform(0.4, 2.1):.3f} "
                     f"tokens_per_s={rnd.randint(1800, 2400)}")
        if crash_at and s >= crash_at:
            lines += [
                "Traceback (most recent call last):",
                '  File "train.py", line 212, in <module>',
                "    trainer.fit(model, datamodule)",
                '  File "train.py", line 178, in fit',
                "    loss = model(batch)",
                "torch.OutOfMemoryError: CUDA out of memory. Tried to allocate 2.00 GiB "
                "(GPU 0; 23.65 GiB total capacity; 21.98 GiB already allocated)",
            ]
            break
    if not crash_at:
        lines.append(f"[2026-10-13 11:02:44] training finished, eval_loss={l1:.4f}, "
                     f"eval_acc={a1:.4f}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def generate(root: Path) -> int:
    root = Path(root)
    (root / "logs").mkdir(parents=True, exist_ok=True)
    (root / "notes").mkdir(parents=True, exist_ok=True)
    made = 0

    # 1. 正常收敛
    p = root / "logs" / "2026-10-11" / "lora-sft_lr0001_bs32_run2.log"
    p.parent.mkdir(parents=True, exist_ok=True)
    _train_log(p, 1200, 1.821, 0.641, 0.312, 0.712)
    made += 1

    # 2. lr 放大 5 倍：下降更慢、后期停滞
    p = root / "logs" / "2026-10-12" / "lora-sft_lr0005_bs32_run1.log"
    p.parent.mkdir(parents=True, exist_ok=True)
    _train_log(p, 1200, 1.804, 0.724, 0.298, 0.661, plateau_from=900)
    made += 1

    # 3. 崩在 1180 步
    p = root / "logs" / "2026-10-13" / "lora-sft_lr0001_bs32_run3.log"
    p.parent.mkdir(parents=True, exist_ok=True)
    _train_log(p, 2000, 1.792, 0.312, 0.305, 0.845, crash_at=1180)
    made += 1

    # 4. 隔天改 seq_len 重跑成功（同名同 run -> 与 3 形成实验链）
    p = root / "logs" / "2026-10-14" / "lora-sft_lr0001_bs32_run3.log"
    p.parent.mkdir(parents=True, exist_ok=True)
    _train_log(p, 1600, 1.744, 0.287, 0.310, 0.861,
               header_note="retry of run3 after CUDA OOM; seq_len 2048 -> 1024")
    made += 1

    # 5. 超参扫描表
    p = root / "logs" / "2026-10-12" / "sweep_lr.csv"
    rows = ["epoch,lr,loss,f1,acc,steps_per_s"]
    for lr, base in ((0.0005, 0.98), (0.001, 0.66), (0.005, 0.93)):
        for e in range(1, 5):
            rows.append(f"{e},{lr},{base - 0.08 * e:.4f},{0.42 + 0.03 * e:.4f},"
                        f"{0.61 + 0.04 * e:.4f},{18 + e}")
    p.write_text("\n".join(rows) + "\n", encoding="utf-8")
    made += 1

    # 6. 评测结果（jsonl）
    p = root / "logs" / "2026-10-13" / "eval_20261013.jsonl"
    recs = []
    for i, step in enumerate((200, 600, 1000, 1400)):
        recs.append({"step": step, "eval_loss": round(0.72 - 0.09 * i, 4),
                     "map": round(0.38 + 0.05 * i, 4), "acc": round(0.63 + 0.06 * i, 4)})
    p.write_text("\n".join(json.dumps(r) for r in recs) + "\n", encoding="utf-8")
    made += 1

    # 7. 手写组会笔记
    p = root / "notes" / "2026-10-13_组会笔记.md"
    p.write_text(
        "# 组会笔记 2026-10-13\n\n"
        "- 这周主要调 lr。lr=0.001 收敛最快，1200 步就能到 0.64；放大到 0.005 反而停滞在 0.72。\n"
        "- run3 跑到 1180 步 OOM 崩了，怀疑是 seq_len=2048 太长，显存吃满。\n"
        "- 下一步：把 seq_len 降到 1024 重跑 run3，看能不能到 0.3 以下；顺便把 batch 降到 16 试试。\n"
        "- 老张建议加上 grad accumulation，别直接放大 batch。\n",
        encoding="utf-8")
    made += 1

    return made


if __name__ == "__main__":
    import sys
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "./demo_data")
    n = generate(target)
    print(f"已生成 {n} 个文件 → {target.resolve()}")
