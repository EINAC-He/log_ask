# LabMemory

把散落在文件夹里的实验日志、输出表格、手写笔记，变成**可检索、可追溯的知识卡片**，
并且支持用一句人话查回来：*"上次学习率调到 0.001 时 loss 最后降到多少？"*

这是一个 **Agent**（不是流水线脚本）：调什么工具、读多少行、要不要横向对比、什么时候建卡，
都由模型在循环里自己决定；三条护栏（轮数/工具配额/结果截断）保证它不会跑飞。
没有 API Key 时自动降级为规则策略，**断网也能完整演示**。

---

## 获取与协作

```bash
git clone https://github.com/EINAC-He/log_ask.git
cd log_ask
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python main.py demo              # 先确认环境能跑起来（不需要 Key）
```

几条约定，能省掉大部分来回：

- **`labmemory.toml` 不要提交**（里面有 api_key，已在 `.gitignore`）。新同学第一次执行
  `python main.py config --init` 从模板生成本地配置即可。
- 改代码前先 `python -m unittest discover -s tests`（53 个用例，约 8 秒），提交前再跑一次；
  动到 LLM 相关逻辑时，再跑 `python scripts/acceptance.py` 看五项检查。
- `main` 分支保持"随时能 `demo` 跑通"；个人改动开 `feat/xxx` 分支发 PR。
- 改了工具签名 / 卡片字段 / 配置键，请同步更新 `实现方案.md` 的对应小节——那份文档是设计契约，
  不同步的话下一个人会按旧文档改出 bug。

---

## 快速开始

```bash
pip install -r requirements.txt          # 只有 openai 一个必需依赖

python main.py demo                      # 一键三幕演示，不需要 Key，约 1 秒
```

---

## 配置：只需要改一个文件

**配置文件地址：`labmemory.toml`（就在本 README 同级目录）**

```bash
python main.py config --show     # 看当前生效的值 + 到底读的哪个文件
python main.py config --init     # 没有这个文件时，从 labmemory.toml.example 生成
```

要填的就两处，其余留默认：

```toml
[llm]
api_key = "sk-..."                        # 必填，DeepSeek / Kimi / GLM 任选
base_url = "https://api.deepseek.com/v1"  # 换服务商时一起改
model = "deepseek-chat"

[paths]
data_dir = "D:\\lab\\exp-dtu"             # 要摄录的实验目录
db = "labmemory.db"
```

完整字段（都有注释）见 [`labmemory.toml.example`](labmemory.toml.example)：
`temperature / timeout / offline`、`max_turns_* / max_calls / max_result_chars`、
`scan.hours`、`watch.settle / batch_window / interval / duration`、`capture.enabled`。

**优先级：命令行参数 > 环境变量（`LM_*`）> `labmemory.toml` > 内置默认值。**
所以临时改一次不用动文件：

```bash
python main.py scan --dir ./other-logs --hours 240
LM_MODEL=kimi-k3 python main.py ask "lr 0.001 那次 loss 到多少"
python main.py --config ./team.toml scan
```

> `labmemory.toml` 已写进 `.gitignore`（里面有 key），仓库里只提交 `labmemory.toml.example`。
> 别的机器上：`python main.py config --init` 重新生成一份即可。

配置好之后的日常命令：

```bash
python main.py scan                      # 摄入：文件 → 知识卡片（目录取自配置）
python main.py ask "lr 0.001 那次 loss 到多少"
python main.py weekly --days 7 --out weekly.md
python main.py cards                     # 列表
python main.py show c-17ca2b4c           # 单张卡片全文
```

`--offline` 强制走规则策略；配置里 `offline = true` 或不填 `api_key` 时也会自动降级。

### 当项目"没有日志"时（参数改在代码里、直接 F5 调试）

```bash
python main.py hook                        # 一次性：装解释器级采集钩子
export LABMEMORY_HOME=<本仓库目录>          # Windows: setx LABMEMORY_HOME "..."
cd D:\lab\exp-dtu && mkdir .labmemory      # 在要采集的项目里登记
python main.py watch --dir D:\lab\exp-dtu  # 常驻监听，改动写完就自动摄录
```

之后改完代码按 F5，运行记录会自动落到 `.labmemory/runs/`，里面带：
`params(new)`（这次 lr/batch 是多少）、`changes`（相对上次改了什么）、`stdout`（loss 曲线）、`exit/duration`。

也可以显式包装一次运行（能拿到真实退出码）：

```bash
python main.py run -- python train.py
```

细节见 [`实现方案.md`](实现方案.md) 第十六节。

---

## 测试与验收

```bash
# 1) 回归测试：53 个用例，约 8 秒，不需要网络和 API Key
python -m unittest discover -s tests -v

# 2) 验收器自检：只验证"检查逻辑本身没写错"，也不调模型
python scripts/acceptance.py --selftest

# 3) 真模型验收：接上 Key 之后跑这个，出红绿灯
python scripts/acceptance.py
python scripts/acceptance.py --data D:/lab/logs    # 或直接拿你自己的实验目录跑
python scripts/acceptance.py --keep                # 保留工作目录，方便翻卡片
```

验收器会真的调模型跑一次摄录 + 一次检索，然后检查五件事：

| # | 检查 | 不过意味着什么 |
|---|---|---|
| 0 | 配置与连通性 | key / base_url / model 有一个不对，或没装 `openai` |
| 1 | 覆盖：每个文件都进卡片 | 模型漏读了文件，或把一次 run 拆成了多张卡 |
| 2 | 数字：卡片指标与源文件一致 | **模型在编数字**，直接判不合格 |
| 3 | 证据：每条观测都有 evidence | 行号对不上，卡片不可追溯 |
| 4 | 检索：一句话查到正确答案 | 提示词里的"自然语言→结构化条件"没生效 |
| 5 | 降级：key 不可用时说清楚 | 静默降级会让人以为结果可信 |

`PASS / WARN / FAIL` 三档：WARN 是可接受但要留意（比如数字被四舍五入、卡片数略多于文件数）。
**退出码 = 失败项数**，方便挂到 CI：`python scripts/acceptance.py || exit 1`。

回归测试覆盖的关键路径（改代码前先跑，别靠肉眼）：
重复摄录幂等 / supersede 实验链（按证据新旧对账）/ 结构化检索命中 / 工具不抛异常与越界拒绝 /
配置的单反斜杠与 BOM / 运行采集的参数 diff / 监听稳定窗口与攒批 / 周报结构 /
三种日志格式解析 / 模型给出畸形卡片时的归一与兜底 / 目录深度剪枝与下钻 /
模型失败态分类（鉴权·限流·超时·连接·缺依赖）/ 卡片写入的事务回滚 /
同证据原地更新（防模型死循环）/ 重复调用护栏 / 验收器自身的判定逻辑。

---

## 常见问题

**1. IDE 里点运行就崩，报 `ImportError: DLL load failed while importing _sqlite3`**

这和项目无关：**IDE 配置的 Python 解释器和终端里的不是同一个，且前者环境是坏的**
（典型是 conda/venv 里 `_sqlite3.pyd` 缺失的残缺环境）。

```bash
# 先确认哪个解释器是好的
python -c "import sys, sqlite3; print(sys.executable, sqlite3.sqlite_version)"
```

三种修法：
- IDE 里换解释器：Settings → Project → Python Interpreter，选上面打印出来的那个；
- 修 conda：`conda install -c conda-forge sqlite`（或新建 Python 3.11+ 干净环境）；
- 直接用能跑的解释器：`<那个python> LabMemory/scripts/acceptance.py`。

`scripts/acceptance.py` 现在会在导入项目代码之前先做这个检查，并打印解释器路径，
所以以后遇到类似问题它会直接把话说明白，而不是抛一堆栈。

**2. 卡片里的指标是裸数字（`"loss": 0.641`）导致某处报错**

模型偶尔不按 schema 写 `metrics`。写入口 `save_card` 现在会把裸数字归一成
`{first,last,best,worst,trend:"flat",n:1}` 并在返回里带 `warnings` 提醒模型，
检索 / 周报 / 问答三个读路径也都加了兜底，不会再崩。

**3. `git status` 里出现 `tests/_tmp`**

测试的临时目录，已在 `.gitignore` 里。若因为权限残留删不掉，`icacls <dir> /reset /T`
后重试。

---

## 目录结构

```
LabMemory/
├── main.py                  # CLI 入口（scan / ask / weekly / cards / show / demo / watch / run / hook）
├── app.py                   # 可选 Gradio 网页壳（pip install gradio 后 python app.py）
├── tests/test_labmemory.py  # 端到端用例（unittest，无外部依赖）
├── tests/test_acceptance_checks.py  # 验收器自身的判定逻辑
├── tests/test_limits.py     # 深度剪枝 / 失败态分类 / 事务回滚
├── scripts/acceptance.py    # 真模型验收：五项检查 + PASS/WARN/FAIL
├── demo/make_demo_data.py   # 生成 7 个样例实验文件（可复现，随机数有种子）
└── labmemory/
    ├── agent.py             # Agent 主循环 + 三道护栏 + 调用轨迹
    ├── tools.py             # 8 个工具：list_files / inspect_file / read_slice /
    │                        #   compare_files / search_cards / get_card / save_card / ask_user
    ├── store.py             # SQLite + FTS5：卡片表、参数表、检索、实验链、审计事件
    ├── parsing.py           # 文件分类、指标抽取、异常规则（带行号证据）
    ├── meta.py              # 从文件名/文件头推断实验名、run、超参
    ├── watch.py             # 文件监听（watchdog / 轮询双后端 + 稳定窗口 + 攒批）
    ├── capture.py           # 运行采集：参数快照比对、stdout tee、运行记录、解释器钩子
    ├── config.py            # 配置加载（TOML + 环境变量 + 命令行覆盖）
    ├── prompts.py           # 摄录 / 检索 / 周报 三套提示词
    ├── llm.py               # OpenAI 兼容适配器 + RulePolicy（离线降级策略）
    └── report.py            # 确定性 Markdown 周报（不依赖 LLM）
```

约 1900 行，除 `openai` 外只用标准库（`sqlite3` 自带 FTS5）。

---

## 核心设计

**规则发现信号，模型解释信号。** 指标数值、异常类型、行号证据全部由确定性代码产出，
模型只负责判断"这几条信号意味着什么、该建几张卡"。这样既避免模型编数字，也让每张卡片都能回指到 `文件名:行号`。

**中文检索不用向量库。** 用户问"学习率 0.001"本质是**结构化查询**，不是语义相似度。
所以检索是"SQL 精确过滤（超参/状态/时间/标签）→ FTS5 中文单字匹配 → bm25 排序"，
零额外依赖、可解释、毫秒级。向量库留给"找类似的故障"这类模糊需求（未实现）。

**同实验同 run 自动成链。** 重跑一次 run3，旧卡片标记 `superseded`，新卡片用 `links.supersedes` 指回去。
"run3 崩过、隔天重跑成功"这种历史不会被覆盖掉，但回答问题时优先用有效卡片。

**覆盖兜底。** 模型偶尔会"读了文件但忘了建卡"（真模型跑 7 个文件时漏过 1 个）。
摄录结束后有一道确定性自检：`列出过/读过 - 已进卡片的文件` 若非空，就用规则补建，
并标上 `#补漏` + `needs_review`，同时打印出来——产品承诺的"每个文件都有归属"不靠模型记性，
但补出来的卡一眼看得出不是模型写的（`--no-repair` 可关闭）。

**三道护栏。** `max_turns`（模型交互轮数）、工具级配额（`read_slice` 最多 12 次等）、
单次结果截断 5000 字符。没有这些，一个 prompt 偏差就能把额度烧光或把上下文撑爆。

---

## 已知限制

- 扫描表（一次扫多个 lr 的 CSV）只能识别出"这是扫描维度"，不会自动按维度分组比较，
  目前靠 `setup.sweep` 字段提示人和模型；
- 图片类文件只登记存在，不做 OCR/图表读数；
- 中文检索是单字匹配 + bm25，不做语义扩展，"loss 上不去"和"收敛困难"不会互相命中；
- 单进程单库，没有多用户隔离。

## 目录之外的产物

| 文件 | 说明 |
|---|---|
| `labmemory.db` | SQLite 库（卡片、参数、审计事件） |
| `ingested.json` | 已处理文件指纹，用于增量扫描幂等 |
| `runs/*.json` | 每次 Agent 运行的完整调用轨迹（答辩/复盘用） |
| `weekly.md` | 周报输出 |
