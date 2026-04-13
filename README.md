# auto_video_pipeline

自动把素材筛选、按命名排序、配乐并导出成片的一站式流水线。

## Elevator Pitch

面向短视频与长视频创作者，这个仓库要把“素材筛选 → 规则排序 → 配乐 → 导出”的链路做成可重复、可配置、可观测的流水线。目标是在本地/云端都能运行，允许你在几十分钟内得到可用的样片草稿，再针对细节手调。

## MVP Scope（2026 Q2）

**本阶段只关注一件事：跑通 1 条可执行链路并交付 3 条样片。**

In scope：

- 规范素材命名与输入目录结构。
- 依据命名规则和元数据对镜头排序、筛掉不合格片段。
- 自动挑选配乐、设置音量包络，并导出 MP4。
- 产出可复现的配置与日志，方便快速调整。

Out of scope：

- 自动发布、分发、多账号矩阵。
- 平台 API 接入或风控策略。
- 复杂的多模态剪辑策略（保留 hook 位以便之后扩展）。

## Pipeline at a Glance

| Stage | Description | Notes |
| --- | --- | --- |
| 1. Asset Intake | 校验目录、解析素材命名、读取基础元数据。 | 失败即停止并输出诊断。 |
| 2. Shot Ranking & Ordering | 用规则/模型给镜头打分并生成时间线。 | 先用规则，后续插入模型。 |
| 3. Music & FX | 从音乐池中挑选、裁剪、做包络，补必要的转场音效。 | 允许外部 YAML 配置。 |
| 4. Render & Export | 调用 ffmpeg/moviepy 合成，输出 MP4 + 元数据。 | 导出日志与最终配置快照。 |

更细的流程与约束见 `docs/architecture.md` 与 `docs/pipeline-spec.md`。

## Repository Layout

- `docs/`：设计、流程与愈发细的实施文档。
- `src/`：（即将创建）核心流水线代码、模块化组件。
- `assets/`：示例素材、音乐清单（后续添加）。
- `LICENSE`：MIT，保持开放使用范围。

## Getting Started（面向开发者）

1. Clone：`git clone git@github.com:<org>/auto_video_pipeline.git`。
2. Python 3.11+：`py -3.11 -m venv .venv && .\\.venv\\Scripts\\activate`。
3. 安装依赖：后续会提供 `requirements.txt`/`pyproject.toml`，暂以 `pip install moviepy librosa numpy pydantic` 预热环境。
4. 约定目录：
   - `inputs/raw/<project>/<shot>.mp4`
   - `inputs/music/<bpm>_<mood>.wav`
   - `outputs/<project>/draft_<timestamp>.mp4`
5. 阅读 `docs/pipeline-spec.md`，确认配置文件字段，再开始实现 `src/` 中的模块。

### Configuration Entry Points

- **配置文件**：推荐做法。传入 `--config configs/sample_job.yaml`，文件里描述 job、输入路径、打分权重、导出参数，便于版本化。
- **命令行覆盖**：重要参数都应提供 CLI flags，例如 `--inputs.footage_glob`, `--timeline.target_duration_s`, `--export.resolution`。CLI 传参覆盖配置文件中的同名值，方便快速试验。
- **组合策略**：保持“文件为主、CLI 为增量覆盖”的原则，`docs/pipeline-spec.md` 中的所有键都要在 CLI 中有对应 flag，默认读取配置文件，未传入时沿用文件值。

## Roadmap（Rolling）

1. **MVP 0.1**：CLI 骨架、配置加载、日志模块 → 2026-04-20。
2. **MVP 0.2**：素材命名解析 + 排序规则 → 2026-04-27。
3. **MVP 0.3**：音乐自动匹配、导出 3 条样片 → 2026-05-05。
4. **Post-MVP**：接入模型 scoring、模版化项目、云端 worker。

## Documentation Map

- `docs/architecture.md`：整体目标、约束、模块分层、观测方案。
- `docs/pipeline-spec.md`：输入输出约定、打分规则、CLI/配置字段。

## Contributing & Collaboration

欢迎通过 issue/PR 讨论：明确问题背景 → 给出最小复现/素材示例 → 描述期望输出。暂不接受大规模的功能 PR，优先围绕 MVP 里程碑推进。

## License

MIT © 2026 Brant-B
