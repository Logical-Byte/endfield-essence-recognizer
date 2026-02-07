# 终末地基质妙妙小工具

[![Python](https://img.shields.io/badge/python-3.12+-blue.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Vue.js](https://img.shields.io/badge/Vue.js-3.x-green.svg?logo=vue.js)](https://vuejs.org/)
[![Vuetify](https://img.shields.io/badge/Vuetify-3.x-lightblue.svg?logo=vuetify)](https://vuetifyjs.com/)
[![①群](https://img.shields.io/badge/①群-486622964-orange.svg?logo=qq)](https://qm.qq.com/cgi-bin/qm/qr?k=1xqRp7JwQHwGswa-8_SMFuAsRYYRnF8J)
[![②群](https://img.shields.io/badge/②群-1082880855-orange.svg?logo=qq)](https://qm.qq.com/cgi-bin/qm/qr?k=qAmvmHCc3HuESiJhZVe6Ytgj7foOxXx9)
[![官网](https://img.shields.io/badge/官网-终末地一图流-yellow.svg)](https://ef.yituliu.cn/resources/essence-recognizer)

不知道哪些基质该留哪些该扔？想要当狗粮又担心万一这个基质有用？快来逝逝终末地基质妙妙小工具罢！

官网（下载最新版）：[https://ef.yituliu.cn/resources/essence-recognizer](https://ef.yituliu.cn/resources/essence-recognizer)

反馈交流群
- ①群：[486622964](https://qm.qq.com/cgi-bin/qm/qr?k=1xqRp7JwQHwGswa-8_SMFuAsRYYRnF8J)
- ②群：[1082880855](https://qm.qq.com/cgi-bin/qm/qr?k=qAmvmHCc3HuESiJhZVe6Ytgj7foOxXx9)

![终末地基质小助手展示](https://cos.yituliu.cn/endfield/endfield-essence-recognizer/assets/终末地基质小助手展示_0.webp)
![终末地基质小助手展示](https://cos.yituliu.cn/endfield/endfield-essence-recognizer/assets/终末地基质小助手展示_1.webp)

## 使用前准备

- 请使用**管理员权限**（是 Windows 管理员，不是终末地管理员）运行本工具，否则无法捕获全局热键
- 请在 Windows 屏幕设置中**关闭 HDR**
- 请将终末地的界面语言更改为**简体中文**
- 请将终末地的分辨率更改为 **1920×1080 窗口**
  - 若您的显示器分辨率为 1920×1080，请将终末地的分辨率更改为 1920×1080 全屏后按下 **`Alt+Enter` 切换为窗口模式**
- 请确保终末地的整个窗口都位于屏幕范围内且未被性能监控工具等任何其他内容遮挡
- 请按 `N` 键打开终末地**贵重品库**并切换到**武器基质**页面
- 在运行过程中，请确保终末地窗口**置于前台**

## 功能介绍

- 按 `[` 键识别当前选中的基质是宝藏还是养成材料
- 按 `]` 键扫描所有基质，并根据设置，自动锁定或者解锁基质<br>
  基质扫描过程中再次按 `]` 键中断扫描
- 按 `Alt+Delete` 退出程序

**宝藏基质和养成材料：** 可以在设置界面自定义。默认情况下，如果这个基质和任何一把武器能对上（基质的所有属性与至少 1 件已实装武器的属性完全相同），则是宝藏，否则是养成材料。

## 常见问题

### 1. 双击运行时遇到“Unhandled exception in script”弹窗报错

![遇到报错解决方法](https://cos.yituliu.cn/endfield/endfield-essence-recognizer/assets/遇到报错解决方法.webp)

这大概率是由于 Windows 自带的解压导致的。

有两种解决办法：

1. 改用 [7zip](https://www.7-zip.org/) 或者 [WinRAR](https://www.win-rar.com/) 解压即可解决（其他解压软件也可以试试）。
2. 如果电脑上没安装其他解压软件，则请右键点击 zip 压缩包，点击"属性"，然后把"解除锁定"勾上，点击"确定"，再解压即可。

### 2. 界面窗口能打开，但是白屏

白屏问题比较复杂，请参考以下临时解决方法。

**方法一：** 请参考 [https://github.com/Logical-Byte/endfield-essence-recognizer/issues/24#issuecomment-3830421851](https://github.com/Logical-Byte/endfield-essence-recognizer/issues/24#issuecomment-3830421851)

**方法二：** 请保持工具打开状态，用浏览器访问 [http://127.0.0.1:325/](http://127.0.0.1:325/)

**方法三：** 如果以上方法仍然解决不了，那就先凑合用。界面看不见没关系的，只要终末地在前台，按 `]` 键是可以正常使用的。

### 3. 明明是 1920×1080 窗口，依然提示分辨率错误

请尝试：将所有显示器的缩放都更改为 100%，然后重启电脑，把本工具和终末地窗口都放在主显示器上，再试一次。

### 4. 出现大面积识别错误

- 请在 Windows 屏幕设置中**关闭 HDR**
- 请将终末地的界面语言更改为**简体中文**
- 请确保终末地的整个窗口都位于屏幕范围内且未被性能监控工具等任何其他内容遮挡
- 如果问题仍未解决，可以使用**监控**工具进行排查

### 5. 识别到的基质始终是同一个

请确保终末地的分辨率为 **1920×1080 窗口**。若您的显示器分辨率为 1920×1080，请将终末地的分辨率更改为 1920×1080 全屏后按下 **Alt+Enter 切换为窗口模式**。

## 联系我们

如果在使用过程中遇到任何问题，或是想提出建议，欢迎 **[在 GitHub 上提 Issue](https://github.com/Logical-Byte/endfield-essence-recognizer)**，或者加入反馈交流群：
- ①群：[486622964](https://qm.qq.com/cgi-bin/qm/qr?k=1xqRp7JwQHwGswa-8_SMFuAsRYYRnF8J)
- ②群：[1082880855](https://qm.qq.com/cgi-bin/qm/qr?k=qAmvmHCc3HuESiJhZVe6Ytgj7foOxXx9)

## 说明

- 机器识别，可能存在错误。若发现错误，欢迎反馈。
- 工具仅检索基质是否匹配已实装的武器，而没有能力预测是否能匹配未实装的武器。至于一个基质未来有没有用，你可以给海猫打个电话（
- 本工具按“原样”提供，作者不对可用性、准确性或使用效果作出任何保证。
- 使用者必须确保使用本工具符合相关法律法规与服务条款，禁止用于任何违法或侵权行为。
- 使用者需承担因使用本工具产生的任何风险、损失或责任。
- 使用本工具即意味着您同意以上全部内容。

## 开发

### 环境准备

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

### 贡献指南

欢迎提交 Issue 和 Pull Request！

PR 前请确保包含相关测试，并通过所有代码检查。不建议在 PR 中包含大段 AI 生成的文档。
