# 林榕桌宠

面向 Windows 10/11 64 位的透明置顶桌面宠物。角色会在主屏幕底部自然行走，支持点击语音互动、鼠标拖拽、系统托盘、三档尺寸、静音和可选开机启动。

## 当前特性

- `idle`、左右行走、挥手、跳跃、坐下、等待、专注和观察动画。
- 坐下后保持正面坐姿，再次点击才反向播放起身动画。
- 行走八帧逐帧播放，不通过跳帧追赶计时误差。
- 16ms 精确移动定时器、浮点位移累计和动画帧预取。
- 无边框、逐像素透明、始终置顶，不显示在任务栏。
- 离线 `zh-CN-XiaoxiaoNeural` 少女音语音资源。
- 设置保存在 `%APPDATA%\LinRongPet\settings.json`。

## 开发运行

要求 Python 3.12、Windows 10/11 和可用的系统托盘。

```powershell
uv venv --python 3.12 .venv
uv pip install --python .venv\Scripts\python.exe -e ".[build,test]"
.venv\Scripts\python.exe -m linrong_pet
```

## 角色资产

- `src/linrong_pet/assets/spritesheet.webp`：`3072x3744` 透明高清图集，每帧 `384x416`。
- `src/linrong_pet/assets/frames/*.webp`：按状态导出的逐帧运行资源。
- `src/linrong_pet/assets/animation.json`：状态、帧数、逐帧时长和循环策略。
- `src/linrong_pet/assets/audio/*.wav`：24kHz 离线神经语音。

重新组装角色图集：

```powershell
.venv\Scripts\python.exe scripts\refine_character_assets.py `
  --manifest artifacts\repair-v1.4\asset-manifest.json `
  --output src\linrong_pet\assets\spritesheet.webp
.venv\Scripts\python.exe scripts\export_runtime_frames.py `
  --animation src\linrong_pet\assets\animation.json `
  --spritesheet src\linrong_pet\assets\spritesheet.webp `
  --output-dir src\linrong_pet\assets\frames
```

`repair-v1.4` 以 `role.png` 和统一标准人物图为身份基准。各动作源图保持高于目标帧的分辨率，组图流程只执行确定性的分帧、整行统一缩放、源像素密度校正、基线对齐和一次下采样，不进行逐帧贴脸或超分重构。清单可为独立帧声明密度系数、头部目标宽度、基线偏移和镜像规则；所有最终有效缩放仍必须小于 1。

## 验证

```powershell
.venv\Scripts\python.exe scripts\validate_voice.py `
  --audio-dir src\linrong_pet\assets\audio
.venv\Scripts\python.exe scripts\validate_assets.py `
  --animation src\linrong_pet\assets\animation.json `
  --spritesheet src\linrong_pet\assets\spritesheet.webp `
  --json-out artifacts\repair-v1.4\validation.json
.venv\Scripts\python.exe scripts\render_animation_qa.py `
  --animation src\linrong_pet\assets\animation.json `
  --spritesheet src\linrong_pet\assets\spritesheet.webp `
  --output-dir build\qa\previews-v1.4
.venv\Scripts\python.exe scripts\render_face_qa.py `
  --animation src\linrong_pet\assets\animation.json `
  --spritesheet src\linrong_pet\assets\spritesheet.webp `
  --reference role.png `
  --output build\qa\face-qa-v1.4.png
.venv\Scripts\python.exe scripts\render_size_qa.py `
  --animation src\linrong_pet\assets\animation.json `
  --spritesheet src\linrong_pet\assets\spritesheet.webp `
  --output-dir build\qa\sizes-v1.4
.venv\Scripts\python.exe -m pytest
```

资产校验会检查行走关键帧唯一性、坐姿首帧与站姿尺度衔接、坐姿统一基线、坐姿及跳跃的脸部尺度波动和透明边缘。组图脚本拒绝任何最终放大低分辨率动作源图；运行帧使用临时文件原子替换，避免导出中断留下半套资源。

## 打包

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build.ps1
```

输出：

- `dist\LinRongPet\LinRongPet.exe`
- `output\LinRongPet-Setup-1.4.2.exe`

安装程序按当前用户安装，无需管理员权限。开机启动默认关闭，卸载时保留用户设置。

桌宠空闲时约每 6 秒自然眨眼一次；自动漫游约每 30–50 秒触发，
且只进行短距离移动。除走动外，角色还会约每 18–32 秒自动随机执行
挥手、跳跃、等待、专注或观察动作，自动动作不会播放点击语音或气泡。
