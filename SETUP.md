# 终末地基质妙妙小工具 - 开发环境配置说明

## 已完成的配置

### 1. Python 环境
- Python 版本：3.13.11
- 包管理器：uv

### 2. 依赖安装
- Python 后端依赖已安装：`uv sync`
- 前端依赖已安装：`npm install`
- 前端已构建：`npm run build`

### 3. 配置文件
- `.env` 文件已创建（从 `.env.example` 复制）
- 开发模式已设置为 `false`（生产模式）

### 4. 数据文件占位符
- 已创建 `src/endfield_essence_recognizer/data/endfielddata/TableCfg/` 目录
- 已创建所有必要的 JSON 占位符文件（空文件）
- 已添加数据文件获取说明：`src/endfield_essence_recognizer/data/endfielddata/TableCfg/README.md`

## 如何运行项目

### 开发模式（前端热重载）

1. 修改 `.env` 文件：
```bash
EER_DEV_MODE=true
```

2. 启动前端开发服务器：
```bash
cd frontend
npm run dev
```

3. 启动后端服务器：
```bash
uv run eer
```

### 生产模式（使用构建的前端）

1. 确保前端已构建：
```bash
cd frontend
npm run build
```

2. 确保 `.env` 中的 `EER_DEV_MODE=false`

3. 启动后端服务器：
```bash
uv run eer
```

## 重要提醒

### 数据文件问题

当前项目缺少游戏表数据文件，需要从官方发布的程序中获取：

1. **下载 Release 包**：访问 https://github.com/Mr-P-hainan/endfield-essence-recognizer/releases
2. **提取数据文件**：从解压后的 `endfield-essence-recognizer/_internal/endfield_essence_recognizer/data/` 复制 `endfielddata` 文件夹
3. **放置到项目中**：粘贴到 `src/endfield_essence_recognizer/data/` 目录

详细说明请参考：`src/endfield_essence_recognizer/data/endfielddata/TableCfg/README.md`

### 使用前注意事项

- **需要管理员权限**：程序需要全局热键捕获，必须以管理员身份运行
- **游戏分辨率设置**：终末地窗口必须设置为 **1920×1080 窗口**模式
- **操作说明**：
  - 按 `[` 键：识别当前选中的基质（仅识别不操作）
  - 按 `]` 键：扫描所有基质，自动锁定宝藏，解锁垃圾
  - 按 `Alt+Delete`：退出程序

## 项目结构

```
endfield-essence-recognizer/
├── src/endfield_essence_recognizer/    # Python 后端源码
│   ├── data/endfielddata/              # 游戏表数据（需手动添加）
│   ├── game_data/                      # 游戏数据处理
│   ├── templates/                      # 图像识别模板
│   └── ...
├── frontend/                           # Vue 3 + Vuetify 前端
│   ├── src/                           # 源码
│   └── dist/                          # 构建产物
├── .venv/                             # 虚拟环境
├── .env                               # 环境变量配置
└── pyproject.toml                      # Python 项目配置
```

## 常用命令

```bash
# 安装/更新 Python 依赖
uv sync

# 安装/更新前端依赖
cd frontend && npm install

# 构建前端
cd frontend && npm run build

# 运行程序
uv run eer

# 构建可执行文件
uv run pyinstaller main.spec
```

## 故障排查

### 问题：找不到 JSON 数据文件
**解决方案**：参考上述"数据文件问题"部分，从 Release 包中获取数据文件。

### 问题：无法捕获全局热键
**解决方案**：确保以管理员身份运行程序。

### 问题：前端无法访问
**解决方案**：
- 开发模式：确保 `npm run dev` 正在运行
- 生产模式：确保 `npm run build` 已执行且 `EER_DEV_MODE=false`
