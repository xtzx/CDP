# cdp · 终端项目切换工具 设计文档

- **日期**：2026-04-17
- **状态**：Design approved，等待 writing-plans
- **仓库**：`/Users/bjhl/Documents/手写系列/cdp/`
- **默认命令名**：`cdp`（安装时可覆盖，后续也可改名）

---

## 1. 问题陈述

用户当前的终端开发流程有两个痛点：

1. 依赖 IDE 打开终端才能方便开始一次 Claude Code 会话。终端快捷键与 IDE 存在差异，体验割裂。
2. 同时编辑多个项目时必须打开多个 IDE 窗口。

用户想要一个独立的终端工具，执行后：

- 列出"最近开发过的项目"
- 通过键盘选中某一项（或过滤后回车）
- 自动 `cd` 到项目目录并启动 `claude`

## 2. 目标 / 非目标

### 目标

- 零冷启动：第一次安装就能从 `~/.claude/projects/` 读到历史项目，无需用户手动登记
- 切换一次项目的操作路径 ≤ 3 个键（`cdp`、几个字符过滤、Enter）
- 支持 pin（置顶常用项目）、hide（隐藏不想看到的项目）、alias（起别名）三种个性化管理
- 可脚本化（子命令形式的稳定 CLI，所有写操作都有对应的子命令）
- 独立 git repo、可迭代（Python 实现，便于后续扩展功能）
- 支持简单的卸载流程（删掉 `~/.zshrc` 里的注入段 + repo 目录）

### 非目标

- 跨 shell 支持（当前只支持 zsh；bash/fish 有需要再加）
- 跨操作系统（仅 macOS；Linux 理论上应能工作但不保证，Windows 不支持）
- GUI 或 web 界面
- 与 IDE 集成（打开 VSCode/IDEA 等）
- 为"未曾用 claude 打开过的新项目"做目录扫描/推荐（问题过于发散，体验不如让用户自己 `cd` 一次）

## 3. 核心数据流

```
用户在终端输入 `cdp`
  │
  ▼
[zsh wrapper 函数 cdp]           ← ~/.zshrc 里 source
  │
  │  1. 调用 python 主程序（python3 -m cdp ...），从 stdout 接收"选中的目标路径"
  │     - python 负责：扫 ~/.claude/projects/ → 解码路径 → 合并 ~/.config/cdp/config.toml
  │       里的 pin/hide/alias 信息 → 排序 → 启动 fzf 让用户选 → 打印选中路径到 stdout
  │     - 所有日志/提示走 stderr，避免污染 stdout
  │
  │  2. wrapper 接到路径后在当前 shell 执行 cd <path> && claude
  │     - 必须由 shell function 执行 cd，子进程无法修改父 shell 的 pwd（此设计为 z/zoxide/fasd 的标准做法）
  │
  ▼
用户进入项目目录，claude 已在跑
```

## 4. 仓库结构

```
cdp/
├── README.md                    # 安装、使用、改名、卸载
├── pyproject.toml               # Python 包定义（PEP 621），单依赖 tomlkit
├── install.sh                   # 检测依赖、建 venv、pip install -e、注入 ~/.zshrc
├── src/
│   └── cdp/
│       ├── __init__.py
│       ├── __main__.py          # 入口：python -m cdp
│       ├── cli.py               # argparse 子命令分派
│       ├── projects.py          # 扫描 ~/.claude/projects/、路径解码、mtime 排序
│       ├── config.py            # 读/写 ~/.config/cdp/config.toml（tomlkit，保留注释）
│       ├── picker.py            # 调用 fzf、解析结果、fzf 热键回调
│       └── constants.py         # 命令名、配置路径、默认值（改名时集中修改）
├── shell/
│   └── cdp.zsh                  # zsh wrapper function 定义
├── tests/
│   ├── test_projects.py
│   ├── test_config.py
│   └── test_cli.py
└── docs/
    └── superpowers/specs/
        └── 2026-04-17-cdp-terminal-tool-design.md   # 本文件
```

### 改名路径

需要改命令名时：

1. 改 `src/cdp/constants.py` 里的 `COMMAND_NAME` 常量
2. 改 `shell/cdp.zsh` 里的函数名（文件名本身可不改，但保持一致更清晰）
3. 重跑 `./install.sh`（幂等，会覆盖 `~/.zshrc` 里的注入段）

`install.sh` 也支持 `./install.sh --name xxx` 在安装期直接覆盖，免去手动改代码。

## 5. CLI 命令

### 5.1 子命令列表

| 命令 | 行为 |
|---|---|
| `cdp` | 打开 fzf 选择器。Enter 进入项目 + 启动 claude。Esc/ctrl-c 什么都不做。 |
| `cdp <path>` | 直接 `cd <path> && claude`。路径支持 `~` 展开和相对路径。非目录则错误退出。不自动 pin；首次用完 claude 之后该路径自然出现在 `~/.claude/projects/` 里，下次在列表中显示。 |
| `cdp pin [path]` | 把路径写入 `config.toml` 并标记 `pinned=true`。`path` 缺省 = `$PWD`。 |
| `cdp unpin [path]` | 从配置中移除 pin 标记（如果条目只剩 pin 一个属性则删掉整条）。 |
| `cdp hide [path]` | 给路径标记 `hidden=true`。 |
| `cdp unhide [path]` | 移除 hide 标记。 |
| `cdp alias [path] <name>` | 给路径设置别名 `<name>`，fzf 列表的"名字"列展示别名。 |
| `cdp unalias [path]` | 移除别名。 |
| `cdp list` | 按最终排序纯文本打印项目，格式 `<path>\t<display_name>`。用于脚本调用 / 调试。 |
| `cdp --help` | argparse 自动生成。 |

### 5.2 shell wrapper 关键片段

`shell/cdp.zsh`：

```zsh
cdp() {
  case "$1" in
    # 写配置 / 只读子命令：python 输出直接透传到 tty，wrapper 不捕获
    pin|unpin|hide|unhide|alias|unalias|list|-h|--help)
      command "$CDP_PYTHON" -m cdp "$@"
      return $?
      ;;
    # 其余（无参 = 进选择器；或第一个参数是路径）：捕获 stdout 作为目标路径
    *)
      local selected
      selected="$(command "$CDP_PYTHON" -m cdp "$@")" || return $?
      [[ -z "$selected" ]] && return 0
      cd "$selected" && claude
      ;;
  esac
}
```

关键点：

- **wrapper 按子命令名分派**，而不是靠 stdout/stderr 区分。这样 `cdp list | grep gaokao` 等管道使用仍可工作（python 正常写 stdout）
- 只有"进选择器"和"直接路径模式"两种调用会捕获 stdout
  - picker 模式：python 把选中的绝对路径写到 stdout
  - 路径模式：python 把**绝对化 + `~` 展开后**的路径回写到 stdout，便于 wrapper 直接 `cd`
- 两种捕获模式下，python 的提示 / 警告 / 错误仍走 **stderr**，避免污染路径输出
- 用户取消 fzf（Esc / ctrl-c）时 python 以非 0 退出码退出，`|| return $?` 让 wrapper 提前返回，不做 cd
- `--help` 被路由到"透传"分支，不会被当作选中路径误 cd

## 6. fzf 选择器 UX

### 6.1 展示格式

```
 📌 高考              /Users/bjhl/Documents/WorkProject/gaokao
 📌 dotfiles         /Users/bjhl/dotfiles-workspace
    银河              /Users/bjhl/Documents/WorkProject/1-xxx/galaxy-client
    wxzs-website     /Users/bjhl/Documents/WorkProject/1-xxx/wxzs-website
    web-capability… /Users/bjhl/Documents/手写系列/web-capability-compiler
```

- pin 的项目前缀 `📌`，普通项目两个空格对齐
- 名字列（第二列）固定宽度 **18 字符**，超出用 `…` 截断
- 名字 = 如果 config.toml 里设了 `alias`，则显示别名；否则显示路径 basename
- 路径列完整展示，不替换 `~`（fzf 输入 `/Documents/Work` 能直接过滤，不需要纠结家目录展开）
- 长路径不主动截断，fzf 自动处理（会在视图横向滚动）

### 6.2 排序规则

1. **pin 区**（`pinned=true`）：按 config.toml 里 `[[project]]` 条目的出现顺序
2. **普通区**：按 `~/.claude/projects/<encoded>/*.jsonl` 所有文件的最大 mtime 倒序
3. **`hidden=true` 的**：完全不展示
4. 目录已删除（`os.path.isdir` 为假）的：也不展示（静默跳过）

### 6.3 热键

| 键 | 动作 |
|---|---|
| `↑`/`↓` 或 `ctrl-j`/`ctrl-k` | 上下移动 |
| 任意可打印字符 | fzf 模糊过滤 |
| `Enter` | 确认选中，wrapper 执行 `cd <path> && claude` |
| `Esc` / `ctrl-c` | 退出不做任何事 |
| `ctrl-p` | 钉住 / 取消钉住当前高亮项（fzf reload 刷新列表） |
| `ctrl-h` | 隐藏当前高亮项 |
| `ctrl-o` | `open <path>`（在 Finder 打开），不退出选择器 |

实现要点：`ctrl-p` / `ctrl-h` 通过 `fzf --bind "ctrl-p:reload(...)"` 调用一条不对外暴露的内部命令（如 `python3 -m cdp _toggle_pin {}`），内部命令修改 config.toml 后重新生成列表内容，fzf 的 `reload` 动作重绘视图。

## 7. 数据与配置

### 7.1 项目数据源

- 权威来源：`~/.claude/projects/<encoded>/*.jsonl`
- 路径解码：目录名形如 `-Users-bjhl-Documents-WorkProject-gaokao`，把 `-` 替换为 `/` 即可（首字符 `-` 对应开头 `/`）
  - 注意：若实际路径中本就包含 `-`，解码会错乱。当前解码策略只做「`-` → `/`」简单替换，依赖 Claude Code 官方编码方案。**已知限制**：包含连字符的目录名（如 `galaxy-client`）在解码后会变成 `galaxy/client`，实际会被 `os.path.isdir` 过滤掉而"消失"。
  - 处理方式：在实现中将"解码后路径不存在 → 尝试把连字符回退"列为一条补救规则（遍历 basename 里的 `-`，尝试替换回去并判断 isdir），仅作为回退启发式。细节在实施计划里具体打磨。
- mtime：取目录下所有 `.jsonl` 文件的最大 `os.path.getmtime`（最近一次 session 时间）

### 7.2 配置文件

`~/.config/cdp/config.toml`（遵循 XDG Base Directory）：

```toml
# 顺序决定 pin 区的置顶顺序。可以手动编辑本文件。

[[project]]
path = "/Users/bjhl/Documents/WorkProject/gaokao"
alias = "高考"
pinned = true

[[project]]
path = "/Users/bjhl/dotfiles-workspace"
pinned = true

[[project]]
path = "/Users/bjhl/Documents/trash-proj"
hidden = true

[[project]]
path = "/Users/bjhl/Documents/galaxy-client"
alias = "银河"
# 只设了 alias，没 pin 没 hide，也合法
```

规则：

- 每条 `[[project]]` 必须含 `path`
- `alias` / `pinned` / `hidden` 均为可选
- `~/.claude/projects/` 里有但本文件里没有的项目，仍然作为"普通项目"展示
- `~/.claude/projects/` 里没有但本文件里有（并标记了 pin / alias）的项目，也会出现在列表中 —— 允许用户"预登记"一个还没用 claude 打开过的项目
- 空行和 `#` 开头的注释行允许，写操作保留它们（靠 `tomlkit`）

### 7.3 依赖

- Python ≥ 3.10
- Python 包依赖：`tomlkit`（唯一第三方依赖；用 `tomllib` 不够，因其只读）
- 外部 CLI：`fzf`、`claude`

## 8. 安装脚本

`install.sh` 行为（顺序执行）：

1. 检测 `python3 --version` ≥ 3.10，否则报错退出
2. 检测 `fzf`、`claude` 是否在 PATH，不在则 **警告** 但不阻断（用户可能晚点装）
3. 在 repo 根创建 venv：`python3 -m venv .venv`
4. `.venv/bin/pip install -e .`（editable，改代码立即生效）
5. 往 `~/.zshrc` 追加（幂等，用标记注释检测是否已注入）：

   ```
   # >>> cdp >>>
   export CDP_HOME="/path/to/repo"
   export CDP_PYTHON="$CDP_HOME/.venv/bin/python3"
   source "$CDP_HOME/shell/cdp.zsh"
   # <<< cdp <<<
   ```

   `shell/cdp.zsh` 里调用 Python 时用 `$CDP_PYTHON`（拿到 venv 里的解释器）。

6. 支持 `./install.sh --name <newname>` 覆盖命令名：改 `constants.py`、改 `shell/cdp.zsh` 里的函数名、注入 `~/.zshrc` 的 source 语句不变（文件名不随命令名走，避免复杂化）
7. 提示用户 `source ~/.zshrc` 或开新终端生效

### 卸载

写在 README，不做脚本：

- 删 `~/.zshrc` 里 `# >>> cdp >>>` 至 `# <<< cdp <<<` 之间内容
- 删仓库目录
- 删 `~/.config/cdp/`（可选，保留 pin/hide/alias 配置供重装用也行）

## 9. 错误处理与边界情况

| 场景 | 行为 |
|---|---|
| `~/.claude/projects/` 不存在（全新机器） | 选择器展示空列表 + 顶部提示 `No recent projects. Use \`cdp <path>\` to open one.` |
| 有记录但全部被 hide 或目录已删 | 同上 |
| config.toml 的某条 pin 指向已删目录 | 静默跳过（不显示），配置文件不动 |
| `cdp pin /x/y/z` 路径不存在 | 打印 `warning: /x/y/z does not exist, pinning anyway` 到 stderr，成功写入配置 |
| `cdp <path>` 传入非目录 | 错误退出：`error: <path> is not a directory` |
| `fzf` 未安装 | 启动 picker 时检测，打印 `fzf not found. Install via: brew install fzf`，退出码 1 |
| `claude` 未安装 | wrapper 在 `cd` 之后执行 `claude` 时由 shell 报错（`command not found`），不在 python 侧做检测 |
| 用户 Esc 退出 fzf | fzf 退出码 130。python 侦测到后自身也用非 0 退出，wrapper 收到非 0 → 不 cd，当前目录不变 |
| session 文件 mtime 读不到（IO/权限） | 视为 mtime=0 排到末尾，不抛异常 |
| 路径解码包含 `-` 的 basename | 见 7.1 的回退启发式 |
| 两个项目 basename 同名（或 alias 同名） | 不做特殊处理，靠路径列区分 |
| config.toml 手动写坏（tomlkit 解析失败） | 打印 `error: ~/.config/cdp/config.toml is invalid: <detail>` 并退出码 1，不尝试自动修复 |

## 10. 测试策略（精简版）

只写必要的最小用例，遵循用户要求"简单测试即可"。

- `tests/test_projects.py`
  - 伪造 `tmp_path` 下的 fake `~/.claude/projects/` 树，验证路径解码 + mtime 排序
  - 目录不存在被过滤（静默跳过）

- `tests/test_config.py`
  - 读一个典型 toml → 得到正确内部结构
  - 写 pin/alias 后再读 → 内容一致，且原注释保留
  - toml 格式错误时抛明确异常

- `tests/test_cli.py`
  - 用 `subprocess.run` 跑 `python -m cdp list`，断言输出格式
  - `cdp alias foo` 后 `cdp list` 显示用 alias

**不测**：

- shell wrapper 的行为（手动测试清单写在 README）
- fzf 交互（标准做法是不测 TUI）
- install.sh（属于一次性脚本）

## 11. 后续扩展（不在本次实现范围）

记下来便于将来考虑，**不做**：

- fzf 预览窗口显示项目最近一次 session 的头几行
- 统计每个项目打开次数、最后 N 次使用时间
- `cdp --no-claude`（仅 cd 不开 claude）
- 支持 bash / fish 的 wrapper
- `cdp rename` 内建改名命令（当前靠 `install.sh --name`）

## 12. 设计决策小结（why's）

- **为何是 Python + shell wrapper 而非纯 zsh？** 用户明确希望将来易扩展，Python 在处理结构化配置和复杂逻辑上优势明显。
- **为何 TOML 而非 JSON？** TOML 注释友好、手写更舒服、数组表 `[[project]]` 表达"一条项目的多属性集合"天然契合。
- **为何用 tomlkit 而非 stdlib tomllib？** 需要写回配置，`tomllib` 只读；`tomlkit` 保留注释和格式，适合用户手动编辑 + 程序写入共存的场景。
- **为何 pin/hide/alias 统一在一个 `[[project]]` 表？** 同一个项目的所有属性放一起直观，避免"同一路径在三段里分别出现"的冗余。
- **为何 fzf 而非编号列表？** 项目多时模糊过滤差别巨大；fzf 几乎是 macOS 开发者标配。
- **为何主命令走 shell function 而非把 Python 做成独立二进制？** 子进程不能改父 shell 的 pwd，这是 shell 切目录工具（z / zoxide / fasd）的标准做法。
