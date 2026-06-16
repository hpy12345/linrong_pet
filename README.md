# 林榕桌宠

面向 Windows 10/11 64 位的透明置顶桌面宠物。角色会在主屏幕底部自然行走，支持点击语音互动、鼠标拖拽、系统托盘、三档尺寸、静音和可选开机启动。

## 当前特性

- `idle`、左右行走、挥手、坐下、等待、专注、观察、比爱心和求抱抱动画。
- 点击可随机触发语音互动；比爱心播放“爱你哦”，求抱抱播放“主人，来陪我玩嘛”。
- 用户长时间未互动时，桌宠会主动走到主屏水平中央，播放求抱抱动作和语音；默认 5 分钟触发，仍无响应时按同一间隔重复提醒。
- 坐下后保持正面坐姿，再次点击才反向播放起身动画。
- 离线 `zh-CN-XiaoxiaoNeural` 温柔少女语音资源。
- 设置保存到 `%APPDATA%\LinRongPet\settings.json`，其中 `attention_delay_minutes` 和 `attention_repeat_minutes` 使用分钟单位，默认和最小值均为 5。
- 托盘菜单可直接自定义“无互动求关注时间”，输入单位为分钟。

## 开发运行

要求 Python 3.12、Windows 10/11 和可用的系统托盘。

```powershell
uv venv --python 3.12 .venv
uv pip install --python .venv\Scripts\python.exe -e ".[build,test]"
.venv\Scripts\python.exe -m linrong_pet
```

## 角色资源

- `src/linrong_pet/assets/spritesheet.webp`：`3072x4160` 透明高清图集，每帧 `384x416`。
- `src/linrong_pet/assets/frames/*.webp`：按状态导出的 68 张逐帧运行资源。
- `src/linrong_pet/assets/animation.json`：状态、帧数、逐帧时长和循环策略。
- `src/linrong_pet/assets/audio/*.wav`：7 条 24kHz 离线神经语音。

重新导出运行帧：

```powershell
.venv\Scripts\python.exe scripts\export_runtime_frames.py `
  --animation src\linrong_pet\assets\animation.json `
  --spritesheet src\linrong_pet\assets\spritesheet.webp `
  --output-dir src\linrong_pet\assets\frames
```

`repair-v1.6.0` 以 `role.png` 和当前生产图集为身份基准，新增 `hug` 第 10 行。求抱抱峰值帧复用同一人物身份的正面动作源，统一基线和轻微前倾缩放，不进行逐帧贴脸或超分重构。

## 验证

```powershell
.venv\Scripts\python.exe scripts\validate_voice.py `
  --audio-dir src\linrong_pet\assets\audio
.venv\Scripts\python.exe scripts\validate_assets.py `
  --animation src\linrong_pet\assets\animation.json `
  --spritesheet src\linrong_pet\assets\spritesheet.webp `
  --json-out artifacts\repair-v1.6.0\validation.json
.venv\Scripts\python.exe scripts\render_animation_qa.py `
  --animation src\linrong_pet\assets\animation.json `
  --spritesheet src\linrong_pet\assets\spritesheet.webp `
  --output-dir build\qa\previews-v1.6.0
.venv\Scripts\python.exe scripts\render_face_qa.py `
  --animation src\linrong_pet\assets\animation.json `
  --spritesheet src\linrong_pet\assets\spritesheet.webp `
  --reference role.png `
  --output build\qa\face-qa-v1.6.0.png
.venv\Scripts\python.exe scripts\render_size_qa.py `
  --animation src\linrong_pet\assets\animation.json `
  --spritesheet src\linrong_pet\assets\spritesheet.webp `
  --output-dir build\qa\sizes-v1.6.0
.venv\Scripts\python.exe -m pytest
```

资产校验会检查图集尺寸、状态集合、运行帧唯一性、透明边缘、比爱心特效数量，以及坐姿/求抱抱与站姿的尺度和基线一致性。语音校验会检查文件集合、格式、响度、削波、时长及首尾静音。

## 打包

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build.ps1
```

输出：

- `dist\LinRongPet\LinRongPet.exe`
- `output\LinRongPet-Setup-1.6.1.exe`

安装程序按当前用户安装，无需管理员权限。开机启动默认关闭，卸载时保留用户设置。
