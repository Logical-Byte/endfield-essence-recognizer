# 贡献指南 (Contributing Guide)

感谢你对本项目的关注！无论你是开发者还是普通用户，你的参与对项目都至关重要。

## 多样化的贡献方式

参与一个开源项目不仅限于提交代码。如果你发现了一个 Bug，或者有一个很棒的新功能想法，即使你不打算亲自编写代码，我们也**强烈鼓励**你通过 Issue 与我们分享：

*   **报告问题 (Bug Report)**：如果你在使用过程中遇到异常，请详细描述问题现象、你的预期行为，并尽可能提供截图或日志。这能极大节省我们的排查时间。
*   **提出建议 (Feature Request)**：如果你觉得项目可以更好，欢迎分享你的想法。请简要描述新功能及其应用场景和必要性。
*   **贡献代码 (Code Contribution)**：如果你有兴趣参与开发，请提出 RFC 与我们讨论，并参考下文的贡献流程和代码规范。

你可以在提交 Issue 时选择相应的模板（Bug 报告或功能建议），以帮助我们更好地理解你的反馈。

## 沟通与反馈流程

除 **紧急修复 (Hotfix)** 外，所有代码提交建议遵循以下流程：

1. **先开 Issue 讨论 (Issue/RFC)**：重大功能或架构调整必须先通过 Issue 进行讨论。在维护者确认方向符合项目规划后再开始编写代码，以避免无效的开发。
2. **使用草稿模式 (Draft PR)**：如果你希望在代码未完全完成时提前获取反馈，请将 Pull Request 设置为 **Draft** 状态。
3. **PR 处理策略**：对于未经沟通、且不符合项目方向的非紧急 PR，维护者可能会为了维护项目结构而直接关闭。

---

## 代码质量与风格规范

本规范主要针对 `src/` 目录下的 Python 代码，其核心原则（如命名与逻辑清晰度）同样适用于 `frontend/` 目录。

### 1. 命名规范

* **避免过短的变量名**：避免使用如 `x`, `y`, `i` 等无明确语义的单字母变量名。变量名应能准确描述其承载的数据含义。
* **例外情况**：仅允许在极短的循环索引（如 `for i in range(...)`）或通用的数学背景下使用简写。

### 2. Python 后端规范 (`src/`)

* **文档字符串 (Docstrings)**：公有函数、和类必须包含完整的 Docstring。如果修改了函数或类的行为，其文档字符串也必须同步更新。
* **类型标注 (Type Hints)**：强烈建议为函数参数和返回值添加类型注解，以增强代码的健壮性。
* **代码一致性**：新代码应在风格、布局和设计模式上与项目现有代码保持高度一致。

### 3. 前端规范 (`frontend/`)

* **模式一致性**：新开发的组件或状态管理应参考项目现有的设计模式，确保风格统一。
* **变量命名**：同样需遵守语义化命名的原则，避免混淆。

### 4. 注释与可读性

* **逻辑清晰**：复杂逻辑块必须配有必要的行内注释，解释其目的和实现思路。
* **可读性优先**：我们推崇编写自解释的代码。在代码简洁性与可读性发生冲突时，请优先选择可读性。
* **拒绝臃肿**：避免过长的函数和过深的嵌套分支。必要时应拆分为更小的函数。

---

## 审核与接受标准

维护者在进行代码审查 (Review) 时将重点关注以下几点：

1. **代码一致性**：新代码是否自然地融入了现有代码体系？
2. **长期维护成本**：逻辑是否清晰？是否缺乏必要的注释或文档？
3. **架构合理性**：是否遵循了已达成的 Issue 讨论共识？

对于严重违反命名规范、缺乏必要注释、或未经讨论便进行大规模架构变动的 PR，维护者保留直接关闭的权利。

---

## 如何开始？

1. **Fork** 本仓库并创建你的功能分支。
2. 确保本地环境配置了 `pre-commit` （运行 `uv run pre-commit install`），并在提交前通过所有静态检查。
3. 提交 PR 时，请在描述中关联对应的 Issue 编号。


### 环境准备

本项目目前只支持 Windows 平台的开发环境。

#### 1. 安装依赖管理器

本项目使用 [uv](https://docs.astral.sh/uv/) 管理 Python 依赖：

```bash
# 安装 uv（Windows PowerShell）
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

#### 2. 安装 Node.js

前端开发需要 [Node.js](https://nodejs.org/) 环境（推荐 LTS 版本）。

#### 3. 准备游戏数据

游戏数据体积较大，未包含在代码仓库中。请从任一[发行版](https://github.com/Logical-Byte/endfield-essence-recognizer/releases)中下载并解压游戏数据到 `src/endfield_essence_recognizer/data` 目录。

目录结构应类似：
```
src/endfield_essence_recognizer/data/
├── endfielddata/
│   └── TableCfg/
│       ├── GemTable.json
│       ├── ItemTable.json
│       └── ...
```

#### 4. 配置环境变量

复制环境变量模板文件并根据需要修改：

```bash
cp .env.example .env
```

环境变量说明：
- `EER_DEV_MODE`: 开发模式开关（`true`/`false`）
- `EER_DEV_URL`: 开发模式下前端服务地址（默认 `http://localhost:3000`）
- `EER_DIST_DIR`: 生产模式下前端构建文件夹路径
- `EER_API_HOST`: API 服务器主机地址
- `EER_API_PORT`: API 服务器端口

### 开发流程

#### Backend 开发

后端位于 `src/endfield_essence_recognizer` 目录，使用 Python 3.12+ 开发。

1. **安装依赖**

```bash
# 安装所有依赖
uv sync --all-groups
```

2. **运行后端服务**

```bash
# 运行后端服务
uv run eer
```

3. **代码检查**

项目使用 Ruff 进行代码检查和格式化：

```bash
# 运行 pre-commit 检查
uv run pre-commit run --all-files
```

4. **运行测试**

```bash
# 运行所有测试
uv run pytest
```

#### Frontend 开发

前端位于 `frontend` 目录，使用 Vue 3 + Vite + Vuetify + TypeScript 开发。

1. **安装依赖**

```bash
cd frontend
npm install
```

2. **运行开发服务器**

```bash
npm run dev
```

前端开发服务器默认运行在 `http://localhost:3000`。

3. **构建生产版本**

```bash
npm run build
```

构建产物将输出到 `frontend/dist` 目录。

4. **类型检查**

```bash
npm run type-check
```

5. **代码检查和格式化**

```bash
# 检查代码
npm run lint

# 自动修复
npm run lint:fix
```

### 完整开发流程

**开发模式：**

1. 确保 `.env` 中设置 `EER_DEV_MODE=true`
2. 启动前端开发服务器：
   ```bash
   cd frontend
   npm run dev
   ```
3. 新开一个终端，启动后端服务：
   ```bash
   uv run eer
   ```
4. 访问 `http://localhost:3000` 即可看到应用界面

**生产模式：**

1. 构建前端：
   ```bash
   cd frontend
   npm run build
   ```
2. 设置 `.env` 中 `EER_DEV_MODE=false`
3. 启动后端服务：
   ```bash
   uv run eer
   ```
4. 访问 `http://localhost:325`

### 打包发布

使用 PyInstaller 打包成可执行文件：

```bash
# 安装构建依赖
uv sync --group build --no-dev

# 构建前端（必需）
cd frontend
npm run build
cd ..

# 打包
uv run pyinstaller main.spec -y
```

打包产物位于 `dist/endfield-essence-recognizer` 目录。
