# cdp

终端里的「最近 Claude Code 项目」选择器。

## 它做什么

列出你用 [Claude Code](https://claude.com/claude-code) 开过的项目，让你用 [fzf](https://github.com/junegunn/fzf) 模糊过滤选中一个，然后在**当前终端**里 `cd` 进项目目录并启动 `claude` —— 不需要开 IDE、不需要多窗口。

项目列表自动从 `~/.claude/projects/`（Claude Code 的 session 记录目录）读取，按最近一次使用时间排序。

## 环境要求

- macOS + zsh
- Python ≥ 3.10
- [fzf](https://github.com/junegunn/fzf)（`brew install fzf`）
- [claude](https://claude.com/claude-code) CLI

## 安装

```bash
git clone <this-repo-url> ~/Documents/cdp
cd ~/Documents/cdp
./install.sh
source ~/.zshrc
```

安装脚本会：

1. 检查 Python / fzf / claude 是否就位（缺 fzf 或 claude 只警告，不阻断）
2. 在仓库根建 `.venv/`，`pip install -e .` 装好自身
3. 往 `~/.zshrc` 追加一个带标记注释的 block：

   ```
   # >>> cdp >>>
   export CDP_HOME="..."
   export CDP_PYTHON="..."
   source "$CDP_HOME/shell/cdp.zsh"
   # <<< cdp <<<
   ```

   幂等 —— 重复跑不会重复注入。

安装完 `source ~/.zshrc` 或开新终端，`cdp` 就能用了。

## 使用

```bash
cdp                       # 打开 fzf 选择器
cdp /some/path            # 直接 cd + claude（路径支持 ~ 和相对路径）
cdp pin                   # 把当前目录钉到列表顶部
cdp pin /path             # 钉指定路径
cdp unpin [path]          # 取消钉住（默认当前目录）
cdp hide [path]           # 从列表里隐藏某个项目
cdp unhide [path]         # 取消隐藏
cdp alias 别名            # 给当前目录起别名（fzf 列表里显示这个别名）
cdp alias /path 别名      # 显式指定路径
cdp unalias [path]        # 移除别名
cdp list                  # 以 "路径<TAB>显示名" 格式打印（可管道）
cdp --help
```

### fzf 里的热键

| 键 | 动作 |
|---|---|
| ↑ ↓ / Ctrl-j Ctrl-k | 上下移动 |
| 任意字符 | 模糊过滤 |
| Enter | 选中，`cd` + 启动 claude |
| Esc / Ctrl-c | 取消，不做任何事 |
| Ctrl-p | 钉住 / 取消钉住当前高亮项 |
| Ctrl-h | 隐藏当前高亮项 |
| Ctrl-o | 在 Finder 打开当前高亮项 |

## 显示格式

```
 📌 高考              /Users/you/WorkProject/gaokao
 📌 dotfiles          /Users/you/dotfiles-workspace
    银河              /Users/you/WorkProject/galaxy-client
    wxzs-website      /Users/you/WorkProject/wxzs-website
```

- `📌` 前缀 = 已钉住
- 第二列：优先显示别名，没设别名就显示路径 basename
- 第三列：完整路径（不折叠成 `~`，方便 fzf 按目录关键词过滤）

## 配置文件

`~/.config/cdp/config.toml`（遵循 XDG 规范）：

```toml
# 顺序决定 pin 区的置顶顺序，可以直接手动编辑本文件

[[project]]
path = "/Users/you/WorkProject/gaokao"
alias = "高考"
pinned = true

[[project]]
path = "/Users/you/dotfiles-workspace"
pinned = true

[[project]]
path = "/Users/you/old-project"
hidden = true
```

- 每个 `[[project]]` 至少要有 `path`；`alias` / `pinned` / `hidden` 都是可选
- 手动加的 `# 注释` 在 cdp 写回（`cdp pin` / `cdp alias` 等）时会被保留
- `pinned` / `hidden` 必须是真正的布尔值（`true` / `false`，不带引号）。写成 `"false"` 会被拒绝，**不会**被悄悄当作 `true`
- 写入是**原子**的：先写 `.tmp`，再 `os.replace` 过去，中途 kill 不会损坏原文件

## 改名

不喜欢 `cdp` 这个名字？

```bash
./install.sh --name myp     # 改成 myp
source ~/.zshrc
myp --help
```

脚本会：

1. 改 `src/cdp/constants.py` 里的 `COMMAND_NAME`
2. 改 `shell/cdp.zsh` 里的函数名
3. 清掉 `~/.zshrc` 里旧名字的 block，注入新名字的 block

**可以反复改名**。每次都会把上一次的 block 干掉（名字记在仓库根的 `.installed_name` 里）。改回默认：`./install.sh`（不带 `--name`）。

## 卸载

1. 删掉 `~/.zshrc` 里 `# >>> <你的命令名> >>>` 和 `# <<< <同名> <<<` 之间的那几行
2. 删掉仓库目录
3. （可选）删掉 `~/.config/cdp/`（如果想保留 pin/alias/hide 配置以便重装，可留着）

## 工作原理

- 扫描 `~/.claude/projects/` 下每个目录（Claude Code 的 session 记录，目录名是编码后的项目路径）
- 按每个项目目录下所有 `.jsonl` 文件的最大 mtime 倒序排序
- 合并 `~/.config/cdp/config.toml` 里的 pin / alias / hide 信息
- 调用 `fzf` 做交互选择
- 选中后，把目标路径写到 stdout
- zsh wrapper 函数从 stdout 拿到路径，在**当前 shell** 里执行 `cd` + `claude`
  —— 子进程无法修改父 shell 的 pwd，所以必须是 shell function，这和 `z` / `zoxide` / `fasd` 是一个套路

## 运行测试

```bash
.venv/bin/pytest
```

## 已知限制

- **跨 shell 支持**：目前只支持 zsh。bash / fish 需要自己改 wrapper。
- **路径解码的连字符歧义**：Claude Code 把路径里的 `/` 编码成 `-`，如果原路径本身含 `-`（比如 `galaxy-client`），解码是模糊的。cdp 的做法是：从根目录开始贪心回溯，在每一层尝试不同的分段方式找一个真实存在的目录，解码失败就跳过不展示。
- **目录已删但 Claude 记录还在**：静默跳过（不在选择器里显示，也不动 `~/.claude/projects/` 下的 session 历史，这样重新 clone 回原路径后对话记录还能续上）。
