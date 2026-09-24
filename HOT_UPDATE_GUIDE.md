# 热更新功能说明

## 功能概述

应用内更新用于让用户在不手动重新下载完整压缩包的情况下升级到新版本。当前方案支持：

- 多镜像源下载与代理配置
- Mirror 酱 CDK 下载源与 `changes.json` 增量包兼容
- WebSocket 实时下载进度
- 更新包 SHA-256 校验（当 Release asset 提供 digest 时）
- 基于 manifest 的文件级更新
- 基于旧/新 dist 对比生成增量包，只下载变更文件
- 增量包基线不匹配或预安装校验失败时自动回退全量包
- 独立 Rust 更新器 `_internal/eer_updater.exe`
- 更新器随 manifest 复制并可被后续更新替换
- 失败时尽力回滚到旧版本文件

## 核心原则

热更新的第一目标不是“尽快覆盖文件”，而是“安全地把安装目录收敛到目标版本”。因此需要遵守以下原则：

1. **目标状态明确**：发布包中的 `_internal/manifest.json` 声明该版本应包含的文件和 protected 路径。
2. **用户数据不动**：`config.json`、`profiles.json`、`logs/`、`screenshots/`、`.env` 等白名单路径不会被删除或覆盖；`_updates/` 和系统临时目录中的更新解压目录会在更新完成后尽量清理。
3. **路径不可越界**：Python 解压阶段和 Rust 执行阶段都会拒绝路径穿越；Rust 侧还会拒绝经过符号链接/重解析点的更新路径。
4. **失败优先保旧版本可用**：删除或覆盖旧文件前先备份；复制失败、源文件缺失或路径非法时写入失败状态并尽力回滚。
5. **更新器放在内部目录**：`eer_updater.exe` 固定放在 `_internal/` 下，避免用户在安装根目录误启动。

## 模块结构

### 后端

- `src/endfield_essence_recognizer/updater/checker.py`：按启用顺序检查版本、解析下载地址、获取 GitHub asset digest，并兼容 Mirror 酱最新版本接口。
- `src/endfield_essence_recognizer/updater/downloader.py`：下载更新包并回调进度。
- `src/endfield_essence_recognizer/updater/installer.py`：解压更新包、读取 manifest 或增量元数据、生成 `_plan.json`、启动 updater。
- `src/endfield_essence_recognizer/updater/manager.py`：串联检查、下载、校验和安装流程。
- `src/endfield_essence_recognizer/updater/sources.py`：维护更新流程开关、默认流程和检查失败后的回退顺序。
- `src/endfield_essence_recognizer/updater/mirrors.py`：维护 GitHub 下载镜像模板和展示名称。
- `src/endfield_essence_recognizer/api/routes/update.py`：更新相关 HTTP API。
- `src/endfield_essence_recognizer/api/websockets/update_progress.py`：下载进度 WebSocket。

### 独立更新器

- `updater/`：Rust 编写的独立更新器工程。
- `updater/src/main.rs`：等待主程序退出、执行文件删除/复制/回滚、重启主程序。
- `updater/Cargo.toml` / `updater/Cargo.lock`：Rust 依赖和锁文件。

### 发布辅助

- `scripts/generate_manifest.py`：扫描 PyInstaller 产物并生成 `_internal/manifest.json`。
- `scripts/generate_incremental_package.py`：对比旧/新 PyInstaller 产物并生成文件级增量 zip。
- `scripts/generate_yituliu_json.py`：从最新 GitHub Release 自动生成一图流 `version.json`（含全量包和增量包信息、SHA-256）。
- `main.spec`：PyInstaller 打包脚本，会在本地存在 release updater 时复制 `_internal/eer_updater.exe` 到 dist 的 `_internal` 目录。

## Manifest 与 Plan

### `_internal/manifest.json`

manifest 是发布包的目标状态声明，由 CI 或本地发布流程生成：

```json
{
  "version": "0.9.0",
  "files": [
    "endfield-essence-recognizer.exe",
    "_internal/eer_updater.exe",
    "_internal/python3.dll",
    "_internal/manifest.json",
    "README.md"
  ],
  "file_hashes": {
    "endfield-essence-recognizer.exe": "0123...64位sha256",
    "_internal/eer_updater.exe": "abcd...64位sha256"
  },
  "protected": [
    "config.json",
    "profiles.json",
    "logs/",
    "screenshots/",
    ".env"
  ]
}
```

`_internal/eer_updater.exe` 必须在 `files` 中，但不能在 `protected` 中，否则后续无法替换更新器。
`file_hashes` 记录发布包内文件的 SHA-256；`_internal/manifest.json` 自身不记录哈希，避免清单内容自引用。

### 临时解压目录中的 `_plan.json`

安装开始前，Python 侧会把 manifest 转换为 updater 可执行的 plan：

```json
{
  "package_type": "manifest",
  "remove_list": ["_internal/old.dll"],
  "copy_list": ["endfield-essence-recognizer.exe", "_internal/eer_updater.exe"],
  "copy_hashes": {
    "endfield-essence-recognizer.exe": "0123...64位sha256",
    "_internal/eer_updater.exe": "abcd...64位sha256"
  },
  "protected_list": ["config.json", "profiles.json", "logs/", "screenshots/", ".env"]
}
```

协议要求：`_plan.json` 是 Python installer 与 Rust updater 之间的协议。新增字段应优先保持可选，避免破坏双方调用关系。`copy_hashes` 是可选字段；新版 Rust updater 在字段存在时会在复制前校验 SHA-256，旧包缺少 manifest 哈希时 Python 会回退为解压目录实际文件哈希。

### `_internal/incremental_update.json`

增量包额外包含该文件，用于声明包内有哪些可复制文件、需要删除哪些旧文件，以及该包只能从哪个版本升级：

```json
{
  "schema_version": 2,
  "format": 1,
  "package_type": "incremental",
  "from_version": "0.8.0",
  "to_version": "0.9.2",
  "base_manifest_sha256": "old-manifest-sha256",
  "target_manifest_sha256": "new-manifest-sha256",
  "target_manifest": "_internal/manifest.json",
  "files": [
    "endfield-essence-recognizer.exe",
    "_internal/manifest.json",
    "_internal/endfield_essence_recognizer/webui_dist/assets/index-BDeaBJ68.js"
  ],
  "remove": [
    "_internal/endfield_essence_recognizer/webui_dist/assets/index-D32FmWFi.js"
  ],
  "protected": ["config.json", "profiles.json", "logs/", "screenshots/", ".env"]
}
```

增量包仍然必须包含目标版本的 `_internal/manifest.json`，这样安装完成后本地 manifest 会收敛到新版本完整状态。安装前还会重新计算本地已安装 manifest 和包内目标 manifest 的 sha256，分别匹配 `base_manifest_sha256` 与 `target_manifest_sha256` 后才允许应用增量包。

### Mirror 酱 `changes.json`

Mirror 酱生成的增量包根目录可包含 `changes.json`。安装器会把它转换为与 updater 兼容的 plan：

```json
{
  "added": ["_internal/new.dll"],
  "modified": ["endfield-essence-recognizer.exe"],
  "deleted": ["_internal/old.dll"],
  "added_dir": ["_internal/new_assets/"],
  "deleted_dir": ["_internal/old_assets/"]
}
```

转换规则：

- `added`、`modified` 和 `added_dir` 会进入复制清单；如果 `added/modified` 缺失，则兜底扫描包内全部文件。
- `deleted` 和 `deleted_dir` 会进入删除清单。
- 不复制 `changes.json`、`_plan.json`、`_internal/incremental_update.json` 等安装协议文件。
- 删除和复制仍会经过 protected 路径过滤，以及 Python/Rust 双层路径穿越校验。
- 如果包内包含 `_internal/incremental_update.json`，优先按本项目自定义增量格式处理，而不是按 Mirror 酱 `changes.json` 处理。

protected 来源优先级：

1. 包内 `_internal/manifest.json` 的 `protected`。
2. 本地已安装 `_internal/manifest.json` 的 `protected`。
3. 内置白名单：`config.json`、`profiles.json`、`logs/`、`screenshots/`、`.env`。

建议 Mirror 酱增量包仍包含目标版本 `_internal/manifest.json`，否则更新后本地 manifest 可能停留在旧版本，影响下一次增量基线判断。

## 更新流程

1. 用户点击“一键更新”。
2. 后端按用户选择的更新流程检查版本；该流程失败时，按 `UPDATE_FLOW_ENABLED` 中启用的顺序继续尝试后续流程，直到某个流程返回“有更新”或“已是最新”。
3. `download_update()` 下载 zip 到 `_updates/`，前端通过 WebSocket 显示进度；Mirror 酱返回的是带时效的下载 URL，下载阶段不再携带 CDK。
4. 如果可获得 SHA-256，`UpdateManager` 校验下载包完整性；Mirror 酱 API 当前没有 sha256 字段，因此会跳过外部哈希校验。
5. `install_update()` 解压 zip 到系统临时目录中的独立更新目录，并校验 zip 条目不能路径穿越。
6. Python 读取 `_internal/manifest.json`；如果同时存在 `_internal/incremental_update.json`，先校验本地 manifest 版本必须等于 `from_version`，并校验本地/目标 manifest sha256 必须匹配元数据。
7. 全量包根据目标 manifest 计算完整 `remove_list` / `copy_list`；本项目增量包只复制 metadata 中声明的变更文件，并只删除 metadata 中声明的旧文件。
8. 如果包内没有 `_internal/incremental_update.json`，但根目录存在 Mirror 酱 `changes.json`，则按 `added` / `modified` / `deleted` / `deleted_dir` 生成 plan。
9. Python 写入临时解压目录中的 `_plan.json`。
10. Python 优先启动临时解压目录中的 `_internal/eer_updater.exe`；如果更新包没有 updater，才回退到安装目录中的 `_internal/eer_updater.exe`。
11. 当前主程序延迟退出，Rust updater 等待父进程退出。
12. Rust updater 拒绝安装在盘符根目录的场景，并校验 plan 中所有路径不能越界。
13. 需要删除或覆盖的旧文件先移动到安装目录同盘的 `_update_backup_{pid}/`，避免 Windows 跨盘 `rename` 失败。
14. Rust updater 按 `copy_list` 从临时解压目录复制新文件到安装目录。
15. 如果复制失败、源文件缺失或路径非法，Rust updater 删除本次新增文件并从 `_update_backup_{pid}/` 恢复旧文件。
16. 更新成功后写入 `logs/{旧版本}_{新版本}_updater_success.txt`，删除同版本失败状态文件、更新包，并重启主程序。
17. 如果 updater 正从临时解压目录运行，会在退出后延迟删除该目录；`_updates/` 在更新包删除后也会尝试删除空目录。
18. `_update_backup_{pid}/` 会在更新成功或失败回滚后删除；如果 Windows 暂时拒绝访问，会安排延迟重试，并在下次更新开始前再次清理遗留目录。
19. 每次更新使用 `update-{时间戳}-{进程ID}-{随机后缀}` 形式的唯一临时目录，并在开始前清理超过 24 小时的旧更新临时目录；清理时会跳过符号链接/越界目录。
20. Rust updater 在安全检查失败、plan 文件读取/解析失败、回滚完成后，也会清理解压目录、更新包和 plan 文件；如果立即删除失败，会安排延迟重试。
21. Python installer 在启动 updater 之前的任何阶段失败（如解压、校验、plan 生成），会通过 `finally` 块清理本次临时文件（plan 文件、解压目录、更新包）；如果立即删除失败，同样会安排延迟重试。

## 更新器位置与运行方式

`eer_updater.exe` 不是给用户直接打开的程序，因此打包产物中固定放在 `_internal/` 下：

- 发布包路径：`_internal/eer_updater.exe`。
- 解压后的运行路径：系统临时目录中的 `_internal/eer_updater.exe`。
- 安装目录回退路径：`_internal/eer_updater.exe`。
- 该文件必须写入 manifest 的 `files`，并且不能加入 `protected`。
- 如果下载到的测试包不包含 updater，installer 会保留当前安装目录里的 `_internal/eer_updater.exe`，避免移动正在运行的更新器。
- 临时解压目录使用唯一名称，避免上一次清理失败影响下一次更新。

## 安全特性

### 文件保护

默认 protected 路径定义在 `scripts/generate_manifest.py` 的 `PROTECTED_PATHS` 中：

- `config.json`：用户配置
- `profiles.json`：多账号配置
- `logs/`：运行日志
- `screenshots/`：用户截图
- `_updates/`：下载缓存；更新成功后会删除本次下载包，并尝试删除空目录
- 系统临时目录中的更新解压目录：使用唯一目录名，更新成功后会尽量删除；下次更新会清理超过 24 小时的旧目录
- `_update_backup_{pid}/`：安装目录同盘的临时回滚备份；更新结束后会尽量删除，失败时会延迟重试并在下次更新前清理
- `.env`：环境变量配置

运行时只信任 installer 侧硬编码白名单内的 protected 路径；manifest 中额外声明的程序文件（例如 `_internal/eer_updater.exe`）不会被加入 `protected_list`。修改 protected 白名单时，请同步更新单元测试。

### 路径穿越防护

- Python 解压 zip 前使用 `Path.resolve()` 与 `relative_to()` 拒绝 `../`、绝对路径等可疑条目。
- Rust updater 执行 plan 时再次拒绝绝对路径、盘符路径、根路径、`..`、空路径，以及路径中已存在的符号链接/Windows 重解析点。

### 回滚策略

- 新文件会先复制到目标目录旁的临时文件，再移动旧文件到 `_update_backup_{pid}/`，最后用 rename 完成替换，避免直接写目标文件导致半写损坏。
- 删除和覆盖前先移动到 `_update_backup_{pid}/`。
- 若 copy 阶段失败，先删除本次新增文件，再把 `_update_backup_{pid}/` 中的旧文件恢复到原位置。
- `_update_backup_{pid}/` 删除前会清理只读属性；若被杀毒软件或系统短暂占用导致删除失败，会安排后台延迟重试。
- 回滚是“尽力而为”：权限错误、磁盘错误或杀进程仍可能导致手动修复需求。

## API 接口

### `GET /api/update/check`

检查是否有新版本。

### `POST /api/update/install`

下载并安装更新。

```json
{
  "success": true
}
```

### `POST /api/update/cancel`

取消当前下载任务。

### `GET /api/update/flows`

获取后端已启用的更新流程列表。该列表由 `UPDATE_FLOW_ENABLED` 控制，前端只能展示并保存启用的流程。

```json
{
  "flows": [
    { "title": "一图流 API (CN 镜像)", "value": "cn_yituliu" },
    { "title": "Mirror 酱", "value": "cn_mirrorchyan" },
    { "title": "GitHub Release", "value": "github" }
  ]
}
```

### `GET /api/update/mirrors`

获取 GitHub 流程可用的下载镜像列表。该列表只在本次检查成功的流程为 `github` 时用于下载 URL 改写；一图流和 Mirror 酱流程不会使用这些镜像。

### `WebSocket /ws/update/progress`

实时推送下载进度。

```json
{
  "progress": 45.5,
  "downloaded": 5242880,
  "total": 11534336,
  "speed": 1048576
}
```

## 更新流程开关

更新流程和 GitHub 下载镜像是两层概念：

- 更新流程决定从哪里检查版本、拿到哪个下载 URL。
- GitHub 下载镜像只在 `github` 流程内生效，用于把 GitHub 官方下载地址改写为代理镜像地址。

`src/endfield_essence_recognizer/updater/sources.py` 中的核心配置：

```python
UPDATE_FLOW_ENABLED = {
    "cn_yituliu": True,
    "cn_mirrorchyan": True,
    "github": True,
}

DEFAULT_UPDATE_FLOW = "cn_yituliu"
```

规则：

- `UPDATE_FLOW_ENABLED` 的字典顺序就是检查失败后的回退顺序，当前为一图流 → Mirror 酱 → GitHub。
- `DEFAULT_UPDATE_FLOW` 只表示启动自动检查和无效配置时的首选流程；该流程失败时仍会继续尝试其他已启用流程。
- 用户可以在前端选择已启用的流程；后端不会返回被禁用的流程。
- 某个流程一旦成功返回“有更新”或“已是最新”，本轮检查立即停止，不再访问后续流程。
- 某个流程返回网络错误、接口错误、配置缺失或解析失败时，才会继续尝试后续流程。
- 下载阶段锁定本次检查成功的 `source`，不跨流程改写下载地址；只有 GitHub 流程允许在 GitHub 官方与 GitHub 代理镜像之间切换。

配置字段：

```json
{
  "update_flow": "cn_yituliu",
  "update_github_mirror": "github",
  "update_mirror": "github",
  "update_mirrorchyan_res_id": "",
  "update_mirrorchyan_cdk": "",
  "update_mirrorchyan_user_agent": "EER_APP"
}
```

- `update_flow`：用户选择的更新流程，支持 `cn_yituliu`、`cn_mirrorchyan`、`github`。
- `update_github_mirror`：GitHub 流程使用的下载镜像，支持 `github`、`ghproxy`、`ghfast` 等。
- `update_mirror`：兼容旧字段，当前仍写入 GitHub 下载镜像；旧值 `cn` 会在 v5 内自动归一为 `update_flow = "cn_yituliu"`。
- `update_mirrorchyan_res_id`：Mirror 酱分配的资源 ID，为空时该流程检查失败。
- `update_mirrorchyan_cdk`：Mirror 酱 CDK；日志和前端提示不得输出明文。
- `update_mirrorchyan_user_agent`：Mirror 酱来源统计标识，默认 `EER_APP`。

配置版本从 v4 升级到 v5 时，前端会自动迁移：

- 旧字段 `update_mirror = "cn"` 归一为 `update_flow = "cn_yituliu"`、`update_github_mirror = "github"`。
- 其他 `update_mirror` 值（如 `ghproxy`）同时写入 `update_flow`（默认 `cn_yituliu`）和 `update_github_mirror`（保留原值）。
- `update_mirrorchyan_*` 字段不存在时回退为空字符串或 `EER_APP`。

## 一图流版本源 JSON

`cn_yituliu` 流程只访问一图流版本源，并会优先选择与当前版本精确匹配的增量包：

```json
{
  "latestVersion": "0.9.2",
  "downloadUrl": "https://github.com/owner/repo/releases/download/v0.9.2/endfield-essence-recognizer-v0.9.2-windows.zip",
  "sha256": "full-package-sha256",
  "size": 16777216,
  "mirrors": {
    "cn_yituliu": {
      "downloadUrl": "https://cdn.example.com/endfield-essence-recognizer-v0.9.2-windows.zip"
    }
  },
  "incrementalPackages": [
    {
      "fromVersion": "0.8.0",
      "toVersion": "0.9.2",
      "downloadUrl": "https://cdn.example.com/endfield-essence-recognizer-0.8.0-to-0.9.2-windows-delta.zip",
      "sha256": "delta-package-sha256",
      "size": 1441792,
      "mirrors": {
        "cn_yituliu": {
          "downloadUrl": "https://cdn.example.com/endfield-essence-recognizer-0.8.0-to-0.9.2-windows-delta.zip"
        }
      }
    }
  ]
}
```

兼容别名：一图流镜像 key 仍兼容旧的 `cn`；增量列表也可使用 `incremental_packages`、`deltaPackages` 或 `patches`；包内字段也兼容 `from_version` / `to_version` / `download_url` / `url`。

一图流流程不会使用顶层 GitHub 下载地址作为实际下载地址；如果版本源缺少 `mirrors.cn_yituliu.downloadUrl`（或兼容旧 key `mirrors.cn.downloadUrl`），该流程会视为检查失败，并按启用顺序尝试后续流程。

## GitHub Release 流程

`github` 流程只访问 GitHub Releases API：

```text
GET https://api.github.com/repos/Logical-Byte/endfield-essence-recognizer/releases/latest
```

选择策略：

- 使用 `tag_name` 与当前版本比较。
- 优先匹配文件名中同时包含当前版本、目标版本和 `delta` / `incremental` / `patch` 标记的 Windows zip 增量包。
- 找不到匹配增量包时，使用 Windows zip 全量包。
- 如果 GitHub asset 带有 `digest: sha256:...`，下载后会进行 SHA-256 校验。
- 安装阶段可以使用用户选择的 GitHub 下载镜像改写下载 URL，但仍属于 GitHub 流程，不会切换到一图流或 Mirror 酱。

## Mirror 酱更新源兼容

Mirror 酱用于支持 CDK 下载和托管增量包。`cn_mirrorchyan` 流程只访问 Mirror 酱接口；如果该流程检查失败，外层流程调度器才会按 `UPDATE_FLOW_ENABLED` 顺序尝试后续启用流程。

### 检查更新接口

Mirror 酱最新版本接口：

```text
GET https://mirrorchyan.com/api/resources/{res_id}/latest
```

常用请求参数：

- `current_version`：当前本地版本，建议传入 `v{当前版本}`，例如 `v0.9.2`。
- `cdk`：用户 CDK，可选；有 CDK 且有效时才会返回带时效的下载 URL。
- `user_agent`：来源统计标识，不是 HTTP User-Agent，而是 Mirror 酱统计面板里的来源字段，默认使用 `EER_APP`。

成功响应 `code == 0` 时，主要读取 `data.version_name`、`data.url` 和 `data.release_note`。失败响应 `code != 0` 时，应把 `code/msg` 作为该流程失败原因记录；如果还有后续启用流程，则继续尝试后续流程，否则展示给用户。

### 选择策略

`cn_mirrorchyan` 的检查流程：

1. 不读取一图流版本源，也不访问 GitHub Releases API。
2. 当用户选择 `cn_mirrorchyan` 且配置了 `update_mirrorchyan_res_id` 时，调用 Mirror 酱最新版本接口。
3. 如果 `version_name` 大于当前版本且返回 `url`，使用该 URL 下载，并把 `source` 标记为 `cn_mirrorchyan`。
4. 如果 Mirror 酱没有返回 `url`，通常表示没有 CDK 或 CDK 不满足下载条件，该流程检查失败，由外层调度器决定是否尝试后续流程。
5. 如果 Mirror 酱返回业务错误，该流程检查失败；只有所有启用流程都失败时，才把错误信息展示给用户。

### 配置字段

用户配置中新增：

```json
{
  "update_flow": "cn_mirrorchyan",
  "update_mirrorchyan_res_id": "由 Mirror 酱分配的资源 ID",
  "update_mirrorchyan_cdk": "用户 CDK",
  "update_mirrorchyan_user_agent": "EER_APP"
}
```

注意事项：

- `update_mirrorchyan_res_id` 为空时，Mirror 酱流程会检查失败；如果后续流程启用，则继续尝试后续流程。
- CDK 会保存在本地配置中；日志、错误信息和前端提示不得输出 CDK 明文。
- 前端选择 Mirror 酱更新流程时，应显示资源 ID、CDK、来源标识输入框。

### 安全边界

Mirror 酱 API 当前没有 sha256 字段，因此无法复用本项目原有“下载后外部 sha256 校验”。Mirror 酱链路的安全性主要来自：

- HTTPS 下载和 Mirror 酱 CDK 权限控制。
- 安装器路径穿越检查和 protected 路径保护。
- Rust updater 的备份、失败回滚和越界路径拒绝。
- Mirror 酱下载阶段不会跨流程回退到一图流或 GitHub 全量包；如需切换流程，需要重新检查更新。
- 如果包内包含本项目 `_internal/incremental_update.json`，仍可获得 manifest sha256 强校验。

推荐顺序：

1. Mirror 酱托管本项目自定义增量包：安全性最好。
2. Mirror 酱 `changes.json` 增量包，并包含新版本 `_internal/manifest.json`：可兼容，下一次更新仍较稳定。
3. Mirror 酱 `changes.json` 增量包但无 manifest：仅作为兼容兜底，不建议长期使用。

## 本地开发与验证

`pre-commit` 已包含 Rust 更新器的 `fmt`、`clippy` 和 `test` 钩子，触发条件为 `updater/` 目录下文件变更。执行全量检查：

```bash
# 一键检查 Python + 前端 + Rust（推荐）
uv run pre-commit run --all-files

# 仅 Python 侧 manifest / installer 测试
uv run pytest tests/unit/updater/test_manifest.py

# 仅 Python 侧 lint
uv run ruff check scripts/generate_manifest.py scripts/generate_incremental_package.py src/endfield_essence_recognizer/updater/installer.py tests/unit/updater/test_manifest.py

# 仅 Rust updater（需要 Rust 工具链）
cargo fmt --manifest-path updater/Cargo.toml --check
cargo clippy --manifest-path updater/Cargo.toml -- -D warnings
cargo test --manifest-path updater/Cargo.toml
```

## 发布新版本

### CI 自动化（推荐）

推送以 `v` 开头的 tag 后，`build-and-release.yml` 会自动完成以下步骤：

1. 构建 Rust updater（`cargo build --release`）。
2. PyInstaller 打包并复制 updater 到 `_internal/`。
3. 生成 `_internal/manifest.json`。
4. 打包全量 zip。
5. 下载上一个稳定 Release 的全量 zip，与当前 dist 对比，自动生成增量包。
6. 增量包命名规则：`incremental-v{旧版本}-to-{新tag}-{os}.zip`（例如 `incremental-v0.9.2-to-v0.9.3-windows.zip`），其中旧版本从上一个 Release 包内的 `_internal/manifest.json` 中读取，而非 tag。
7. 全量包和增量包一并上传到 GitHub Release。

手动触发增量包前，需确保上一个 Release 的全量 zip 已存在，否则 CI 会跳过增量包步骤。

### 本地手动发布

1. 更新 `pyproject.toml` 中的版本号。
2. 构建前端产物。
3. 构建发布版 updater：`cargo build --release --manifest-path updater/Cargo.toml`。
4. 使用 PyInstaller 构建应用，`main.spec` 会复制发布版 updater 到 dist 的 `_internal` 目录。
5. 执行 `scripts/generate_manifest.py` 写入 `_internal/manifest.json`。
6. 打包全量 zip 并创建 GitHub Release。
7. 如需增量包，保留上一版本解压后的 dist 目录，并执行 `scripts/generate_incremental_package.py` 生成增量 zip。
8. 在版本源 JSON 中增加 `incrementalPackages`，用户端检查到匹配当前版本的增量包后会优先下载；不匹配则仍走全量包。
9. 如需发布到 Mirror 酱，优先上传本项目脚本生成的增量包；如果只能使用 Mirror 酱自动生成的 `changes.json` 增量包，也应确保包内包含新版本 `_internal/manifest.json`，并避免把用户数据文件加入 `added` / `modified` / `deleted`。
10. 执行 `scripts/generate_yituliu_json.py` 自动生成一图流 `version.json`（含全量包和增量包 URL、SHA-256、size），并上传到一图流 CDN。

本地生成 manifest：

```bash
uv run python scripts/generate_manifest.py --dist-dir dist/endfield-essence-recognizer
```

本地生成 `0.8.0 -> 0.9.2` 增量包：

```bash
uv run python scripts/generate_incremental_package.py \
  --old-dist-dir dist/endfield-essence-recognizer-0.8.0 \
  --new-dist-dir dist/endfield-essence-recognizer \
  --from-version 0.8.0 \
  --to-version 0.9.2 \
  --output dist/endfield-essence-recognizer-0.8.0-to-0.9.2-windows-delta.zip
```

本地生成一图流 `version.json`：

```bash
# 从 GitHub Release 自动获取信息并计算 SHA-256（需下载文件）
uv run python scripts/generate_yituliu_json.py --output version.json

# 跳过 SHA-256 计算（快速生成，不含 sha256 字段）
uv run python scripts/generate_yituliu_json.py --output version.json --skip-sha256

# 直接从 GitHub API 的 asset digest 字段读取 SHA-256（不下载文件，需 asset 有 digest）
uv run python scripts/generate_yituliu_json.py --output version.json --use-api
```

## 常见问题

### 更新器缺失

如果安装目录中没有 `_internal/eer_updater.exe`，应用内更新会失败。请确认发布包中包含该文件，并且构建流程已先执行 Rust release build。

### 更新失败后如何排查

- 查看 `logs/updater.log`。
- 查看 `logs/{旧版本}_{新版本}_updater_failure.txt`。
- 检查更新包是否缺少 manifest 声明的文件。
- 检查是否被杀毒软件、权限策略或磁盘空间问题阻止写入。

### 为什么临时解压目录有时不会立刻删除

当 updater 从临时解压目录运行时，Windows 会锁定正在运行的 exe。为避免删除正在运行的文件，updater 会启动延迟清理命令，在自身退出后删除该目录。安装目录下历史遗留的 `_update_temp/` 会在安装开始前尝试清理。

### 为什么 `_update_backup_{pid}` 有时不会立刻删除

`_update_backup_{pid}/` 是更新过程中的临时回滚备份，必须放在安装目录同盘，否则 Windows 无法使用 `rename` 快速移动旧文件。更新结束后 updater 会清理该目录；如果 Windows Defender、杀毒软件或系统文件句柄短暂占用旧 DLL/PYD，可能先返回“拒绝访问”。这种情况下 updater 会安排延迟清理，并且下次更新开始前会再次清理遗留的 `_update_backup_*` 目录。
