# cdp

`cdp` 是一个面向 Claude Code 工作流的终端项目切换工具。

它的目标很简单：在当前 shell 中快速找到最近开发过的项目，完成项目切换，然后直接启动 `claude`，减少“必须先打开 IDE 才能开始”的摩擦。

## 当前状态

本仓库目前处于**公开仓库初始化 + 最小代码骨架落地**阶段，核心功能仍待实现。

- 已完成设计文档：`docs/superpowers/specs/2026-04-17-cdp-terminal-tool-design.md`
- 已完成实施计划：`docs/superpowers/plans/2026-04-17-cdp-terminal-tool.md`
- 已完成最小骨架：`pyproject.toml`、`src/cdp/`、`tests/`
- 当前定位：公开仓库、早期阶段、欢迎围绕设计与实现方案提出 issue / PR

如果你现在进入仓库，看到的会是“规格、计划与最小代码骨架”，而不是已经可安装可运行的成品，这是当前阶段的真实状态。

## 项目要解决的问题

当前终端开发流里，常见的两个摩擦点是：

1. 想开始一次 Claude Code 会话时，往往先得打开某个 IDE 窗口。
2. 同时处理多个项目时，经常要来回切不同窗口或手动 `cd`。

`cdp` 计划把这件事收敛成一个更顺手的终端动作：

```bash
cdp
```

然后通过 `fzf` 选择项目，在当前 shell 中执行项目切换，并启动 `claude`。

## 计划能力

根据当前设计，后续实现会围绕这些能力展开：

- 自动读取 `~/.claude/projects/` 中的最近项目记录
- 使用 `fzf` 做筛选和选择
- 在当前 shell 内执行 `cd <path> && claude`
- 支持 `pin`、`hide`、`alias` 三种项目管理能力
- 提供可脚本化的子命令接口
- 使用 `~/.config/cdp/config.toml` 保存用户配置

## 计划技术栈

- 平台：macOS
- Shell：zsh
- 语言：Python 3.10+
- 外部依赖：`fzf`、`claude`
- 配置格式：TOML

## 仓库结构

当前仓库目前主要包含以下内容：

```text
cdp/
├── pyproject.toml
├── README.md
├── LICENSE
├── .editorconfig
├── .gitattributes
├── .gitignore
├── src/
│   └── cdp/
│       ├── __init__.py
│       ├── __main__.py
│       └── constants.py
├── tests/
│   ├── __init__.py
│   └── conftest.py
└── docs/
    └── superpowers/
        ├── plans/
        │   └── 2026-04-17-cdp-terminal-tool.md
        └── specs/
            └── 2026-04-17-cdp-terminal-tool-design.md
```

下一阶段预计继续补齐：

- `src/cdp/cli.py`
- `src/cdp/projects.py`
- `src/cdp/config.py`
- `src/cdp/picker.py`
- `shell/cdp.zsh`
- `install.sh`

## 协作约定

- 公开仓库默认欢迎 issue 和 PR，但请先阅读 `README`、设计文档和实施计划，避免重复讨论。
- 当前阶段优先关注：范围是否合理、命令体验是否顺手、数据模型是否清晰、实现路径是否足够简单。
- 请不要提交任何 token、私钥、账号配置、会话记录或其他敏感信息。

## 后续里程碑

1. 初始化 Python 包与 CLI 骨架
2. 实现项目发现、排序与配置合并
3. 实现 `fzf` 选择器、shell wrapper 与安装脚本
4. 补齐最小测试与使用文档

## License

本项目采用 `MIT` 许可证，详见 `LICENSE`。
