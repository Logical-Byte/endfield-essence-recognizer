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

* **文档字符串 (Docstrings)**：公有函数和类必须包含完整的 Docstring。如果修改了函数或类的行为，其文档字符串也必须同步更新。
* **类型标注 (Type Hints)**：强烈建议为函数参数和返回值添加类型注解，以增强代码的健壮性。
* **代码一致性**：新代码应在风格、布局和设计模式上与项目现有代码保持高度一致。

### 3. 前端规范 (`frontend/`)

* **模式一致性**：新开发的组件或状态管理应参考项目现有的设计模式，确保风格统一。
* **变量命名**：同样需遵守语义化命名的原则，避免混淆。

### 4. Rust 更新器规范 (`updater/`)

`_internal/eer_updater.exe` 是应用内热更新的最后执行者，修改时请优先保证安全边界和可回滚性：

* **协议保持稳定**：Python 侧生成的 `_plan.json` 与 updater 命令行参数是内部协议。新增能力应优先添加可选字段，避免破坏 installer 与 updater 的调用关系。
* **路径必须收敛在根目录内**：所有来自 manifest 或 plan 的路径都必须拒绝绝对路径、盘符路径、`..`、根路径和空路径。
* **拒绝链接绕路**：更新执行路径不得穿过符号链接或 Windows 重解析点；目录清理也不能递归进入链接目标。
* **失败优先保旧版本可用**：覆盖前必须先把新文件写入同目录临时文件，再备份旧文件并 rename 替换；复制失败、缺少源文件或路径非法时，应写入失败状态并尽量回滚。
* **复制前校验完整性**：新版 `_plan.json` 会携带 `copy_hashes`，Rust updater 在复制前校验 SHA-256；修改 manifest 或增量包生成逻辑时必须保持该字段向后兼容。
* **更新器位置固定**：`eer_updater.exe` 必须放在 `_internal/` 下，并参与 manifest 复制；不要把 `_internal/eer_updater.exe` 加入 manifest protected 列表。
* **protected 必须白名单化**：运行时只信任 installer 内硬编码的用户数据白名单，不能直接信任 manifest 中新增的 protected 程序路径。
* **测试要求**：涉及路径解析、复制、删除、回滚、protected 规则、临时目录或 plan schema 的变更，必须补充 Rust 单元测试或 Python 侧计划生成测试。

常用检查命令：

```bash
cargo fmt --manifest-path updater/Cargo.toml --check
cargo clippy --manifest-path updater/Cargo.toml -- -D warnings
cargo test --manifest-path updater/Cargo.toml
```

### 5. 修改配置 Schema

如果需要修改 `UserSetting` 配置结构（位于 `src/endfield_essence_recognizer/schemas/user_setting.py`），**必须**遵循以下步骤：

1. **更新版本号**：递增 `UserSetting._VERSION`
2. **添加迁移函数**：创建 `_migrate_vN_to_vN+1` 静态方法
3. **注册迁移函数**：在 `_MIGRATIONS` 字典中添加映射
4. **添加迁移测试**：在 `tests/test_user_setting_manager.py` 中添加测试验证迁移逻辑正确
5. **更新 Schema 测试**：更新 `test_user_setting_schema_stability()` 中的 `expected_fields` 集合

**示例（v4 → v5）：**
```python
# 1. 更新后端版本号
_VERSION: ClassVar[int] = 5
# 从 4 改为 5

# 2. 更新前端版本号
将 frontend/src/pages/settings.vue 中的 version 改为 5
# 从 4 改为 5

# 3. 添加迁移函数
@staticmethod
def _migrate_v4_to_v5(data: dict) -> None:
    """v4 → v5: 添加新字段"""
    data.setdefault("new_field", "default_value")

# 4. 注册到迁移映射表
_MIGRATIONS: ClassVar[dict[int, Any]] = {
    3: _migrate_v3_to_v4,
    4: _migrate_v4_to_v5,  # 新增
}
```

**为什么这样做？**
- 保证用户升级时配置不丢失
- 链式迁移支持跨版本升级（v2 → v5 会自动执行 v2→v3→v4→v5）
- 自动化测试会在你忘记更新时提醒你
- 避免用户手动重新配置

### 6. 注释与可读性

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

#### 2.5 安装 Rust 工具链（可选，仅打包时需要）

更新器 `_internal/eer_updater.exe` 使用 Rust 编写。如果需要本地构建完整包，需安装 [Rust 工具链](https://rustup.rs/)：

```bash
# 安装 rustup（Windows）
winget install Rustlang.Rustup
```

仅开发后端/前端功能可跳过此步骤。

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

Python 代码使用 Ruff 进行检查和格式化，Rust 更新器代码使用 clippy 和 rustfmt：

```bash
# 一键检查 Python + 前端 + Rust（推荐，pre-commit 已包含全部钩子）
uv run pre-commit run --all-files

# 仅 Python 侧 manifest / installer 测试
uv run pytest tests/unit/updater/test_manifest.py

# 仅 Python 侧 lint
uv run ruff check scripts/generate_manifest.py scripts/generate_incremental_package.py src/endfield_essence_recognizer/updater/installer.py tests/unit/updater/test_manifest.py

# 仅 Rust: 检查更新器代码（需要 Rust 工具链，pre-commit 会自动触发）
cargo fmt --manifest-path updater/Cargo.toml --check
cargo clippy --manifest-path updater/Cargo.toml -- -D warnings
cargo test --manifest-path updater/Cargo.toml
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

# 检查代码格式
npm run format:check
```

6. **运行测试**

```bash
npm run test
```

前端单元测试使用 [Vitest](https://vitest.dev/)，测试文件位于 `frontend/src/**/__tests__/` 目录（目前覆盖 `useProfiles` 等组合式函数）。新增或修改前端状态逻辑时请同步补充对应测试。

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

使用 PyInstaller 打包成可执行文件，需要以下步骤：

#### 前置条件

- Python 3.12+（通过 uv 管理）
- Node.js LTS（前端构建）
- Rust 工具链（更新器构建，安装：https://rustup.rs/）

#### 构建步骤

```bash
# 1. 安装构建依赖
uv sync --group build --no-dev

# 2. 构建前端
cd frontend
npm run build
cd ..

# 3. 构建更新器 (eer_updater.exe)
cargo build --release --manifest-path updater/Cargo.toml

# 4. PyInstaller 打包（main.spec 会自动复制 release updater）
uv run pyinstaller main.spec -y

# 5. 生成更新清单（manifest.json）
uv run python scripts/generate_manifest.py --dist-dir dist/endfield-essence-recognizer
```

打包产物位于 `dist/endfield-essence-recognizer` 目录。

> **注意**：第 3 步需要 Rust 工具链。如果不需要本地构建更新器，可以跳过第 3 步，
> 但打包产物中将不包含 `_internal/eer_updater.exe`，应用内更新功能将无法使用。

---

## 发版流程 (Release Process)

以下为完整的发版步骤，供维护者参考。

### 1. 更新游戏数据

如有需要，按以下顺序更新游戏数据文件：

1. **更新模板匹配模板** — 如有新版本游戏界面变更，需要更新模板匹配所用的截图模板。

2. **更新武器 / 基质数据** — 使用数据转换脚本更新游戏数据：
   ```bash
   uv run .\scripts\transform_weapon_data.py ...\TableCfg
   ```
   该脚本会读取原始游戏数据，生成 JSON 文件。

3. **更新武器图片**

### 2. 更新版本号并提交

1. 修改 `pyproject.toml` 中的版本号：

   ```toml
   version = "X.Y.Z"  # 改为新版本号
   ```

2. 同步 `uv.lock`：

   ```bash
   uv sync
   ```

3. 提交并推送：

   ```bash
   git add pyproject.toml uv.lock
   git commit -m "chore: release X.Y.Z"
   git push
   ```

4. 创建并推送标签（GitHub Actions 检测到标签后会自动构建并创建 Release）：

   ```bash
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```

### 3. 下载构建产物

发布后 GitHub Actions 会自动构建，生成以下两个文件：

- `endfield-essence-recognizer-B-windows.zip` — 完整包
- `incremental-A-to-B-windows.zip` — 增量更新包

下载后上传至一图流 CDN（对应资源目录）。

### 4. 生成一图流 Version JSON

构建完成后，在本地执行以下命令生成 `version.json`：

```bash
uv run python scripts/generate_yituliu_json.py --output version.json --use-api
```

执行后根目录会生成 `version.json`，将其上传至一图流 CDN 即可。
