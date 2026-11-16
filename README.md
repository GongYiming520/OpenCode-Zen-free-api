# OpenCode Zen Free API

[English](./README.en.md) | **简体中文**

> 把 **OpenCode Zen 的免费模型**变成标准的 **OpenAI 兼容接口**：
> 客户端填 `http://127.0.0.1:8790/v1`，就能像用 OpenAI 一样使用 Zen 的免费模型。

**三步开始：** 下载项目 → 双击 `start.bat` → 在任意 OpenAI 客户端里填 Base URL。

---

## 目录

- [先说清楚：能做什么、不能做什么](#先说清楚能做什么不能做什么)
- [它是怎么工作的](#它是怎么工作的)
- [准备工作](#准备工作)
- [Windows：最快上手](#windows最快上手)
- [macOS / Linux / Termux](#macos--linux--termux)
- [客户端怎么填](#客户端怎么填)
- [模型怎么选](#模型怎么选)
- [调用示例](#调用示例)
- [后台运行与停止](#后台运行与停止)
- [命令行参数](#命令行参数)
- [兼容性说明](#兼容性说明)
- [常见问题](#常见问题)
- [安全、隐私与合规](#安全隐私与合规)
- [文件说明](#文件说明)
- [开发与手动启动](#开发与手动启动)

---

## 先说清楚：能做什么、不能做什么

| 能力 | 支持情况 |
|---|---|
| 文本对话、多轮对话 | ✅ 支持 |
| 自定义系统提示（`system` / `developer`） | ✅ 原样传给上游 |
| `GET /v1/models` 模型列表 | ✅ 支持 |
| `POST /v1/chat/completions` | ✅ 支持 |
| `stream: true` 流式格式 | ✅ 返回标准 SSE；⚠️ 但不是逐 token 实时输出，见下 |
| 函数调用 / `tools` / tool calls | ❌ 不支持，会被忽略 |
| 图片、音频等多模态输入 | ❌ 只提取其中的文本部分 |
| `temperature`、`top_p`、`max_tokens` 等采样参数 | ⚠️ 会被忽略（不会报错） |
| `n > 1`（一次返回多个候选） | ❌ 只返回一个 |
| `usage` token 统计 | ⚠️ 固定返回 0 |
| `/v1/completions`（旧版补全接口） | ❌ 只实现了 `/v1/chat/completions` |
| API Key 校验 | ❌ 不校验，填任意非空字符串即可 |

**关于“流式”**：桥会先等上游把整段回答生成完，再按 SSE 格式分片发给客户端。
所以客户端能正常解析流式响应，但不会像真正的流式模型那样一个字一个字实时出现。
如果你只是要兼容客户端，这没问题；如果追求实时打字机效果，这个项目目前做不到。

**关于免费额度**：Zen 的免费模型清单、限流和地区限制由上游决定，随时可能变化。
这个项目只是把官方客户端的请求转发出去，不能保证某个模型永久可用。

---

## 它是怎么工作的

OpenCode Zen 的免费额度会检查请求是不是由 **OpenCode 客户端本身**发出的。
第三方程序直接请求会得到：

```text
403 FreeTierError: OpenCode's free tier can only be used from within OpenCode
```

本项目的做法不是伪造请求头，而是**真的启动一个官方 `opencode` 进程**，
让这个真实客户端去发请求，再把它的结果翻译成 OpenAI 格式：

```text
你的客户端（Cherry Studio / Chatbox / RikkaHub / OpenAI SDK / ...）
        │  POST /v1/chat/completions
        ▼
oc_bridge.py  (:8790)                 ← 本项目，只依赖 Python 标准库
        │  POST /session
        │  POST /session/{id}/message
        ▼
opencode serve (:4097)                ← 官方 opencode 二进制
        │  POST /inference/v1/chat/completions
        ▼
OpenCode Zen 网关  ✅
```

更完整的实测记录见 [`FINDINGS-2026-10-15.md`](./FINDINGS-2026-10-15.md)。

---

## 准备工作

### 必需

| 依赖 | 版本 | 用途 |
|---|---|---|
| Python | 3.8 或更高 | 运行 `oc_bridge.py`（无第三方 Python 依赖） |
| Node.js + npm | 18 或更高 | 首次启动时用 `npm i -g opencode-ai` 安装 opencode |
| 网络 | 能访问 `opencode.ai` 和 npm | 下载 opencode、调用 Zen |

### Windows

1. 安装 Python：<https://www.python.org/downloads/>
   **安装时勾选 “Add Python to PATH”**。
2. 安装 Node.js：<https://nodejs.org/>（选 LTS 版本即可）。
3. 打开新的 PowerShell / CMD，确认：

```bat
python --version
npm --version
```

能显示版本号即可。

### macOS / Linux

```bash
python3 --version    # 需要 3.8+
node --version       # 需要 18+
npm --version
```

没有的话：

- Ubuntu/Debian：`sudo apt install python3 nodejs npm`
- macOS：`brew install python node`
- Termux：`pkg install python nodejs`

---

## Windows：最快上手

### 第 1 步：下载

在 GitHub 页面点 **Code → Download ZIP**，解压到一个普通目录，例如：

```text
D:\OpenCode-Zen-free-api
```

> 路径里有空格或中文一般没问题，但**不要放在需要管理员权限的目录**
>（如 `C:\Program Files`），也不建议放在 OneDrive 同步目录里。

也可以用 Git：

```bat
git clone https://github.com/Fly143/OpenCode-Zen-free-api.git
cd OpenCode-Zen-free-api
```

### 第 2 步：双击 `start.bat`

首次启动会自动做这些事：

1. 检查 Python 版本；
2. 查找 `opencode`，找不到就执行 `npm i -g opencode-ai`；
3. 在项目目录下创建隔离数据目录 `.opencode-home`；
4. 启动 `oc_bridge.py`，它会再拉起 `opencode serve`；
5. 出现下面这样的提示后，就可以使用了：

```text
[bridge] opencode serve is ready (...)
[bridge] OpenAI-compatible endpoint: http://127.0.0.1:8790/v1 ...
================================================================
  Base URL : http://127.0.0.1:8790/v1
  API Key  : any non-empty string (not checked)
  Model    : deepseek-v4.1-flash-free
  Health   : http://127.0.0.1:8790/health
  Stop     : Ctrl+C
================================================================
```

**第一次启动会比较慢**：npm 下载 opencode、opencode 初始化数据目录、
第一次请求冷启动，可能需要 1～3 分钟。之后启动和请求都会快很多。

**这个窗口要一直开着。** 关闭窗口或按 `Ctrl+C` 就会停止服务。
想让它后台运行，见[后台运行与停止](#后台运行与停止)。

### 第 3 步：在客户端里填配置

| 配置项 | 填写内容 |
|---|---|
| Base URL / API 地址 | `http://127.0.0.1:8790/v1` |
| API Key / 密钥 | 任意非空字符串，例如 `sk-anything` |
| 模型 ID | `deepseek-v4.1-flash-free`（或见[模型怎么选](#模型怎么选)） |

> 注意：Base URL 末尾要有 `/v1`。有些客户端会自动补 `/v1`，
> 如果它补了，就只填 `http://127.0.0.1:8790`。

---

## macOS / Linux / Termux

```bash
git clone https://github.com/Fly143/OpenCode-Zen-free-api.git
cd OpenCode-Zen-free-api
chmod +x start.sh stop.sh
./start.sh
```

首次启动同样会自动查找/安装 opencode，并创建 `.opencode-home`。

后台运行：

```bash
./start.sh --bg        # 日志写入 bridge.log，PID 写入 .bridge.pid
./stop.sh              # 停止
```

> `--bg` 必须放在第一个参数。
> 例如：`./start.sh --bg --port 9000`。

Termux 补充：

```bash
pkg install python nodejs
./start.sh
```

---

## 客户端怎么填

### 通用规则

只要是支持 **OpenAI API 兼容**的客户端，基本都可以：

- 提供商类型：`OpenAI` / `OpenAI Compatible` / `自定义 OpenAI`
- Base URL：`http://127.0.0.1:8790/v1`
- API Key：任意非空字符串
- 模型：从 `/v1/models` 里选，或直接填 `deepseek-v4.1-flash-free`

### Cherry Studio

设置 → 模型服务 → 添加提供商 → 类型选 OpenAI →
API 地址填 `http://127.0.0.1:8790/v1`，密钥随便填 →
在模型列表里添加 `deepseek-v4.1-flash-free`。

### Chatbox

设置 → 模型 → 添加自定义 OpenAI 兼容提供商 →
API Host 填 `http://127.0.0.1:8790`（或 `.../v1`，看它是否自动补）→
模型名填 `deepseek-v4.1-flash-free`。

### RikkaHub

提供商 → OpenAI → 自定义 Base URL `http://127.0.0.1:8790/v1` →
API Key 随便填 → 模型 ID `deepseek-v4.1-flash-free`。

### Open WebUI / Docker 中的客户端

如果客户端跑在 Docker 容器里，`127.0.0.1` 指向的是容器自己，不是宿主机。
Windows / macOS 的 Docker Desktop 可以用：

```text
http://host.docker.internal:8790/v1
```

Linux 需要把桥监听到容器可访问的地址，或做端口转发。
注意本项目默认只监听 `127.0.0.1`，**不要为了图方便直接暴露到公网**。

---

## 模型怎么选

### 查看当前可用模型

浏览器打开：

```text
http://127.0.0.1:8790/v1/models
```

或者在 PowerShell 里：

```powershell
(Invoke-RestMethod http://127.0.0.1:8790/v1/models).data.id
```

也可以运行：

```bat
test_api.bat
```

### 2026-11-16 实测的免费模型

> 下表只是参考，不是白名单。上游会增删模型、改名或按地区限制；
> 以 `/v1/models` 实际返回和你自己的测试结果为准。

| 模型 | 状态 | 参考耗时 | 备注 |
|---|---|---|---|
| `deepseek-v4.1-flash-free` | ✅ | 3.1s | **推荐** |
| `glm-5.3-flash-free` | ✅ | 2.5s | **推荐** |
| `minimax-m3.1-flash-free` | ✅ | 2.4s | **推荐**，流式实测通过 |
| `big-pickle` | ✅ | 2.8s | 没有 `-free` 后缀，但属于免费档 |
| `longcat-2.5-free` | ✅ | 3.4s | |
| `iceman-free` | ✅ | 4.8s | |
| `inkling-2-small-free` | ✅ | 2.1s | |
| `flint-40b-free` | ✅ | 2.2s | |
| `nemotron-3.5-super-vl-free` | ✅ | 2.0s | |
| `nemotron-3.5-lightning-free` | ✅ | 2.6s | |
| `hy4-flash-free` | ✅ | 3.1s | |
| `mimo-v2.6-flash-free` | ✅ | 14.2s | 偏慢 |
| `beam-free` | ⚠️ | 0.9s | HTTP 200 但通常返回空文本，不建议用 |

### 模型名报错怎么办

- `404 model not found`：模型名写错或已下架，重新看 `/v1/models`。
- `500` / `502`：上游抖动或该模型坏了，换一个模型，或稍后重试。
- `403 RegionError`：该模型在你所在地区不可用，换模型。
- 返回空文本：模型半残（例如 `beam-free`），换模型。

---

## 调用示例

### Python（官方 `openai` SDK）

```bash
pip install openai
```

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:8790/v1",
    api_key="sk-anything",
)

resp = client.chat.completions.create(
    model="deepseek-v4.1-flash-free",
    messages=[{"role": "user", "content": "用三句话介绍你自己"}],
)
print(resp.choices[0].message.content)
```

流式：

```python
stream = client.chat.completions.create(
    model="deepseek-v4.1-flash-free",
    messages=[{"role": "user", "content": "从 1 数到 5"}],
    stream=True,
)
for chunk in stream:
    print(chunk.choices[0].delta.content or "", end="")
```

### Node.js（官方 `openai` SDK）

```bash
npm i openai
```

```js
import OpenAI from "openai";

const client = new OpenAI({
  baseURL: "http://127.0.0.1:8790/v1",
  apiKey: "sk-anything",
});

const resp = await client.chat.completions.create({
  model: "deepseek-v4.1-flash-free",
  messages: [{ role: "user", content: "Hello!" }],
});
console.log(resp.choices[0].message.content);
```

### curl

Linux / macOS：

```bash
curl http://127.0.0.1:8790/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-anything" \
  -d '{
    "model": "deepseek-v4.1-flash-free",
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

Windows PowerShell 里请用 `curl.exe`（`curl` 在 PowerShell 中是
`Invoke-WebRequest` 的别名，参数不兼容）：

```powershell
$body = @{
  model = "deepseek-v4.1-flash-free"
  messages = @(@{ role = "user"; content = "Hello" })
} | ConvertTo-Json -Depth 5

Invoke-RestMethod -Uri "http://127.0.0.1:8790/v1/chat/completions" `
  -Method Post -ContentType "application/json" `
  -Headers @{ Authorization = "Bearer sk-anything" } -Body $body
```

### 健康检查

```text
http://127.0.0.1:8790/health
```

返回 `{"ok": true}` 说明桥在运行。

---

## 后台运行与停止

### Windows

| 操作 | 方式 |
|---|---|
| 前台运行（推荐新手） | 双击 `start.bat`，保持窗口打开 |
| 后台运行 | 双击 `start-zen.bat` |
| 停止后台服务 | 双击 `stop-zen.bat` |
| 查看日志 | 用 VS Code / 记事本打开 `bridge.log`、`bridge-err.log` |

`start-zen.bat` 是幂等的：服务已经在运行时再双击，只会提示“已在运行”，
不会重复启动。

### macOS / Linux

| 操作 | 命令 |
|---|---|
| 前台运行 | `./start.sh` |
| 后台运行 | `./start.sh --bg` |
| 停止后台服务 | `./stop.sh` |
| 查看日志 | `tail -f bridge.log` |

### 彻底重置

停止服务后，删除 `.opencode-home` 目录，再重新启动即可。
下次启动会重新初始化 opencode 的数据目录。

---

## 命令行参数

直接运行 `oc_bridge.py` 时可用：

```bash
python oc_bridge.py --port 8790 --oc-port 4097
```

| 参数 | 默认值 | 说明 |
|---|---|---|
| `--port` | `8790` | OpenAI 兼容端点端口 |
| `--oc-port` | `4097` | 内部 `opencode serve` 端口 |
| `--opencode-bin` | 自动查找 | opencode 可执行文件路径 |
| `--home` | 当前用户的 opencode 目录 | opencode 的 HOME / 数据目录；启动脚本默认传 `.opencode-home` |
| `--mode` | `stateless` | `stateless`：每个请求新会话；`stateful`：按 `X-Conversation-Id` / `X-Session-Id` 复用会话 |
| `--free-models` | 不过滤 | 逗号分隔的白名单；传了之后 `/v1/models` 只返回这些，其它模型返回 404 |
| `--agent` | `bridge` | 使用的 opencode agent；默认注入精简系统提示 |
| `--prompt` | `You are a helpful assistant.` | `bridge` agent 的系统提示文本 |
| `--full-prompt` | 关闭 | 使用 opencode 默认的完整系统提示（约 9.5KB） |
| `--version` | — | 显示版本号 |

### 系统提示

opencode 默认会附带一大段自己的 agent 系统提示。本项目默认通过
`OPENCODE_CONFIG_CONTENT` 注入一个精简的 `bridge` agent，把系统提示从约 9.5KB
降到约 1KB，并且**不会修改你自己的 `opencode.json`**。

| 想要的效果 | 启动方式 |
|---|---|
| 默认精简提示 | `start.bat` / `./start.sh` |
| 自定义提示 | 加 `--prompt "You are a terse assistant."` |
| 恢复完整提示 | 加 `--full-prompt` |

下游客户端自己的 `system` 消息会通过 opencode 的 `system` 字段原样透传，
不会被塞进 user 文本里。

---

## 兼容性说明

### 已实现

- `GET /`：返回服务信息和用法
- `GET /health`：健康检查
- `GET /v1/models`：模型列表（默认原样返回上游，可加 `--free-models` 过滤）
- `GET /v1/models/{id}`：单个模型信息
- `POST /v1/chat/completions`：非流式与 SSE 流式
- CORS：允许浏览器客户端直接调用

### 未实现 / 有限制

| 项目 | 说明 |
|---|---|
| `tools` / function calling | 请求里的工具定义会被忽略，模型不会返回 tool calls |
| 图片 / 音频输入 | `content` 数组里只提取 `text` / `input_text` 部分 |
| 采样参数 | `temperature`、`top_p`、`max_tokens`、`stop` 等不会传给上游 |
| `usage` | 固定为 0，不能用于精确计费 |
| 真流式 | 先完整生成，再分片发送；首字延迟等于整段生成时间 |
| 会话记忆 | 默认 `stateless`，客户端每次都要发送完整历史；`stateful` 模式下按请求头复用 opencode session |
| 并发 | 桥本身用线程处理请求，但上游免费额度可能限流 |

---

## 常见问题

### 1. 双击后提示 `Python 3 was not found`

没装 Python，或安装时没勾选 “Add Python to PATH”。
重新安装 Python 3.8+，然后**新开一个** CMD / PowerShell 再试。

### 2. 提示 `Node.js / npm was not found`

没装 Node.js。去 <https://nodejs.org/> 下载 LTS 版本，安装后新开终端。

### 3. `npm i -g opencode-ai` 很慢或失败

- 检查网络 / 代理，确保能访问 npm registry；
- 手动在终端执行 `npm i -g opencode-ai`，看完整报错；
- 如果已经用其它方式装了 opencode，可以指定路径：

```bat
start.bat --opencode-bin "C:\path\to\opencode.exe"
```

### 4. 端口 8790 被占用

换一个端口：

```bat
start.bat --port 8791
```

然后客户端 Base URL 改成 `http://127.0.0.1:8791/v1`。

查看谁占用了端口：

```bat
netstat -ano | findstr :8790
```

### 5. 第一次请求特别慢

正常。`opencode serve` 冷启动通常要 10～20 秒，之后 2～5 秒。
如果一直很慢，检查网络，或换一个更快的免费模型。

### 6. 返回 `403 FreeTierError`

说明上游的免费额度策略变了，或者请求没有走真实 opencode 进程。
确认你是用 `start.bat` / `start-zen.bat` 启动的，而不是只运行了
`python oc_bridge.py` 又复用了别的 `opencode serve`。

如果所有模型都 403，可能上游收紧了免费策略，本项目无法保证长期可用。

### 7. 返回 `403 RegionError`

该模型在你的出口地区不可用。换模型，或更换网络出口。

### 8. 返回 500、502 或空文本

通常是上游模型抖动或该模型半残。换一个模型重试。
`beam-free` 就是典型的“200 但空文本”。

### 9. 报 `Database is not empty and has no session table`

你复用了旧版 opencode 的数据库。启动脚本默认使用项目内的
`.opencode-home`，通常不会遇到；如果你是手动运行，请加：

```bash
python oc_bridge.py --home .opencode-home
```

### 10. 日志里的中文是乱码

日志是 UTF-8。用 VS Code、Notepad++ 或 `Get-Content -Encoding utf8` 打开。
PowerShell 5 的 `Get-Content` 默认按 ANSI 读取，可能显示乱码。

### 11. 客户端提示“模型不存在”

先访问 `http://127.0.0.1:8790/v1/models` 看实际模型名。
免费模型经常改名、下架或新增，不要照抄旧文章里的名字。

### 12. 需要登录 opencode 吗？

免费模型实测**不需要登录**。如果你想用付费模型，需要先在同一个
`--home` 下执行 `opencode auth login`，否则上游会返回未授权错误。

### 13. 可以放到服务器上给多人用吗？

技术上可以改监听地址，但**强烈不建议**：

- 默认没有鉴权，API Key 不校验；
- 任何人都能消耗你的免费额度；
- 暴露公网可能违反上游条款。

如果确实要多人使用，请自己在前面加带鉴权的反向代理，并自行承担风险。

### 14. 如何更新

```bash
git pull
```

然后重启服务。Python 部分没有第三方依赖，不需要 `pip install`。
如果你用的是 ZIP 下载，重新下载解压覆盖即可（保留 `.opencode-home` 可以少初始化一次）。

---

## 安全、隐私与合规

- **只监听本机**：默认绑定 `127.0.0.1`，局域网其它设备访问不到。
- **没有鉴权**：API Key 不校验，任何能访问本机端口的人都能调用。
- **请求会发往上游**：你的提示词会经 `opencode serve` 发送到 OpenCode Zen，
  请勿发送敏感信息。
- **非官方项目**：与 OpenCode / OpenCode Zen 官方无关。
- **灰色用法**：本质是借真实官方客户端进程通过免费额度校验，
  请求量大时可能被服务端针对或封禁。重要场景请使用官方付费 Key。
- **许可证**：本项目使用 MIT License；opencode 和 OpenCode Zen 的使用受其各自条款约束。

---

## 文件说明

| 文件 | 用途 |
|---|---|
| `oc_bridge.py` | 核心桥接：OpenAI 兼容端点，仅用 Python 标准库 |
| `start.bat` | Windows 一键前台启动 |
| `start-zen.bat` / `start-zen.ps1` | Windows 后台启动（写 PID、健康检查、日志） |
| `stop-zen.bat` / `stop-zen.ps1` | Windows 停止后台服务（按 PID 杀进程树） |
| `start.sh` / `stop.sh` | macOS / Linux / Termux 启动与停止 |
| `test_api.py` / `test_api.bat` | 快速自测：健康、模型列表、非流式、流式 |
| `test_free_models.py` / `test_free_models.bat` | 逐个测试免费模型可用性 |
| `opencode.json.example` | 可选：手动管理 `bridge` agent 的配置示例 |
| `FINDINGS-2026-10-15.md` | 原理与实测记录 |
| `CHANGELOG.md` | 改动记录 |
| `.opencode-home/` | 首次启动自动创建，opencode 的隔离数据目录（已 gitignore） |
| `bridge.log` / `bridge-err.log` | 运行日志（已 gitignore） |

---

## 开发与手动启动

本项目**没有第三方 Python 依赖**，直接运行即可：

```bash
python oc_bridge.py --port 8790 --oc-port 4097 --home .opencode-home
```

开发时建议：

1. 先停掉后台服务；
2. 用前台模式启动，方便看日志；
3. 用 `python test_api.py` 做快速回归；
4. 修改后至少跑一次非流式和流式测试。

### 自测

```bash
python test_api.py
python test_free_models.py --quick
```

Windows 也可以双击 `test_api.bat`、`test_free_models.bat`。

---

## 相关

- 仓库：<https://github.com/Fly143/OpenCode-Zen-free-api>
- 早期“伪造请求头”方案（已失效）保留在分支 `legacy-header-spoof`：

```bash
git checkout legacy-header-spoof
```

- OpenCode：<https://opencode.ai>

如果这个项目帮到了你，欢迎 Star。遇到问题请附上：
操作系统、启动方式、`bridge.log` 末尾 30 行、以及你请求的模型名。
