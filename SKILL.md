---
name: qingyun-code-video
description: >-
  Make videos with code by using Canvas, HTML-CSS-SVG, WebGL shaders, Three.js, Remotion, HyperFrames, Manim, and along with code-synthesis sound technology,rendered frame by frame with Playwright + FFmpeg. Asks what the user wants to make (an idea, source content such as an article,script, product page or codebase, or a reference video), proposes three distinct video plans with shot-by-shot visual summaries,renders a key-frame still or a few-second preview for each, and after the user confirms one, writes the full brief and builds
  the finished MP4. Use whenever someone wants Claude to make, animate or render a video, motion graphic, animated explainer,
  product promo, kinetic-typography piece, pixel-art or retro animation, UI motion demo, or wants to recreate the look of a
  reference video in code — including Chinese requests like「做个视频」「用代码做视频」「做个动效」「做个宣传片」「帮我复刻这个视频」
  「Opus 做视频」. Also use when the user has AI-generated character clips (green screen) and wants code-built scenes around them.
  Not for generating footage with video models, editing in Premiere/CapCut/AE, or subtitling an existing video.
---

# qingyun-code-video：用代码做视频

创建animated网页或 Manim 场景，通过网页暴露 `render(t)`的方式，由脚本一帧一帧截图，并用 FFmpeg 合成 MP4。声音也用代码合成或调用语音模型API。

先把规划摆到用户面前，确认了再动手：三个方案 → 每个方案一张关键帧图片或几秒预览视频 → 用户确认 → 写成 `brief.md` → 按 brief 逐镜头制作并逐镜头自检 → 交付。

## 工作目录

在当前目录下建 `code-videos/<slug>/`，所有东西放在里面：

```
code-videos/<slug>/
  source/        // 用户给的素材、参考视频抽帧、分析笔记
  previews/      // 三个方案的预览（plan-a.png / plan-b.mp4 ...）
  brief.md       // 用户确认后的完整方案，也是可以复用的提示词
  index.html     // 成片的画面代码（或 Remotion / HyperFrames / Manim 工程）
  audio/         // 合成的配乐、音效、配音
  qa/            // 自检用的静帧和抽帧图
  out/final.mp4  // 成片
```

## 第 0 步：检查环境

运行一次 `python3 scripts/check_env.py`（路径相对本 skill 目录）。它会检查 python3、ffmpeg、Playwright 以及可用的浏览器。缺少依赖时，告知用户并请求用户同意安装。

## 第 1 步：分析用户输入

分析用户的输入内容，包括想法、要求、指令和原始素材等：

- **想法**：进行创意发散，提炼出核心信息和表现形式。
- **文章、口播稿、产品网址、产品代码库、数据表等**：提炼出核心信息、受众和必须出现的事实。不要编造事实（数字、年份等）。
- **参考视频**：如果是网络链接，先下载该视频。然后，运行 `python3 scripts/analyze_video.py <视频> --out source/ref` 得到输出时长、分辨率、帧率、镜头切换时间点和一张抽帧拼图。接着，基于这些信息和这张拼图分析参考视频的镜头结构、节奏、配色、字体，并对照 [references/code-stack.md](references/code-stack.md)推断出参考视频所采用的技术组合。仅学习参考视频的结构和手法，不要照搬其内容、素材和文案等。
- **音乐文件**：先运行 `python3 scripts/audio_tools.py beats <音乐文件> > source/beats.json` 测出节拍、重拍和鼓点。然后，按照这些节拍信息规划视频制作方案和编排分镜。

## 第 2 步：澄清用户需求

根据用户需求分析结果和素材分析结果，为待制作视频确定一套最佳默认参数值，包括：时长、画幅：16:9 / 9:16 / 3:4 / 4:5 / 1:1；配乐：代码合成(默认) / 音频文件；配音：是否需要(默认需要) / 语速 / 响度；颜色系统：颜色组合 / 颜色组合；字幕信息：是否显示(默认显示) / 颜色 / 字体名称 / 字号；内容字体：字体名称。默认帧率为30fps。

然后向用户发起问卷，问卷分两步：
- 第一步：询问用户使用默认制作方案还是自定义方案。
- 第二步：
  - 若用户选择默认制作方案，则采用前面确定的那套默认参数值，并直接进入第 3 步。
  - 若用户选择自定义方案，则使用那套默认参数值逐一构建问卷（以默认参数值作为每项的推荐选项 + 其他选项）。注意：若用户已经在前面的输入中提供了某些参数值，则不要构建这一项的问卷。

## 第 3 步：给出三个方案

读 [references/code-stack.md](references/code-stack.md) 选技术组合，按 [references/plan-format.md](references/plan-format.md) 的格式编写三个方案。

三个方案要有明显差别，差别要体现在风格、叙事结构或技术组合上，不能敷衍了事（例如，仅仅换一套配色这种做法）。常见的差异组合：一个稳妥（最贴近原材料和参考），一个风格化（换一种画面语言），一个结构上更大胆（换一种讲法，比如用一个贯穿全片的主角或者一个不切镜头的长镜头）。

每个方案都要写画面概括（每个镜头一两句话）、技术组合、声音、预计渲染耗时和风险。

## 第 4 步：给每个方案做预览

预览是为了让用户在花大量时间渲染之前，先看到画面长什么样。使用`render(t)` 预览页面。动手前先读 [references/craft-rules.md](references/craft-rules.md) 的页面骨架和字体两节内容，后面正式制作时可以直接在确定方案的代码的基础上接着进行。

每个方案的预览页只搭一个镜头，时间用这个镜头自己的时间（从 0 开始），不用搭整条时间轴。

- 每个方案做 **一张关键帧**：只搭建这个方案最有代表性的那一个镜头：`python3 scripts/render.py previews/plan-a.html previews/plan-a.png --still 2.0 --size 1920x1080`。
- 若方案的卖点在画面运动（界面变形、节拍卡点、转场）时，制作 **2–4 秒的小样**：`python3 scripts/render.py previews/plan-b.html previews/plan-b.mp4 --size <方案画幅> --fps 30 --duration 3`。
- 预览做出来后，先检查一遍，然后修正明显的问题（字溢出、元素挤在一起、画面太空），再呈现给用户。
- 方案里的「预计渲染耗时」用预览来估：渲染脚本会打印用时，单帧耗时 × 总帧数 × 子帧数，再乘 1.3 左右留余量。

把三个方案和预览路径一起给用户，请他选一个，或者说要怎么混合、修改。用户要改就回到第 2 或第 3 步，直到确认。

## 第 5 步：写 brief.md

用户确认后，按 [references/brief-template.md](references/brief-template.md) 写 `brief.md`。它就是这支视频完整的结构化提示词，分 `<role>` `<inputs>` `<direction>` `<structure>` `<build>` `<gotchas>` `<start>` 七块，已经确认的内容全部填实。

这份文件有两个用处：接下来的制作严格按它来；用户以后想复用、换主题、或者拿到别的工具里跑，直接用这份。写完告诉用户文件位置。

## 第 6 步：制作

制作规则在 [references/craft-rules.md](references/craft-rules.md)，动手前把整份读完。最要紧的几条：

1. **画面只由时间决定**。`window.render(t)` 画出第 t 秒；不用 `requestAnimationFrame`、`setTimeout`、CSS transition，随机数带固定种子，帧和帧之间不保存状态。这样任何一帧都能单独重渲，改一个镜头不会影响别的镜头。
2. **一个镜头一个镜头做**。每做完一个镜头，用 `render.py --still` 渲 3 张静帧，自己看：文字有没有溢出、元素有没有重叠、主体够不够大、字停留够不够久。修好再做下一个。30 秒以上的片子，所有镜头搭完后先渲一版 960×540、不加运动模糊的低清小样，节奏和转场对了再精修，精修前别花时间在细节上。
3. **声音和画面用同一张时间表**。先定节拍网格或旁白时间轴，镜头切换和关键动作落在上面；音效放在画面动作发生的那一帧。配音整段合成，不要一句一句拼。
4. **镜头要动**。推、拉、跟随，让主体在画面里足够大；brief 没写镜头的时候，Opus 默认会固定机位，画面容易显得空。

用户点名框架时按框架来（Remotion / HyperFrames / Manim），没点名默认单个 HTML 文件，具体选择见 code-stack.md。

## 第 7 步：渲染和验收

- 渲染：`python3 scripts/render.py index.html out/video.mp4 --size 1920x1080 --fps 30 --duration 30 --audio audio/mix.wav`，要运动模糊加 `--subframes 4`（渲染时间也会变成 4 倍，先告诉用户）。
- 声音：音效用 `python3 scripts/audio_tools.py sfx timeline.json audio/sfx.wav` 按时间点合成，混好后 `audio_tools.py normalize` 到 -14 LUFS，再用 `audio_tools.py check audio/mix.wav --out qa/audio` 看响度和波形图。
- 验收：`python3 scripts/analyze_video.py out/final.mp4 --out qa/final` 出抽帧图，再加一张手机尺寸的（`--cell-width 360`）。按 craft-rules.md 的「自检打分」给自己打分，列出最严重的 3 个问题和时间点，改完只重渲那几秒，重复到每项 8 分以上，再对照验收清单核对。把每一轮的分数和问题记在 `qa/review_log.md` 里，交付时一起给用户。
- 有问题就回到对应镜头修，只重渲那一段也可以（`--start` / `--duration`），最后再整片合成。

## 交付

告诉用户：成片路径、`brief.md` 路径、工程目录，以及一段简短说明，包括这次的关键创作决定、已知的不足（比如某个镜头可以更好）、渲染用时。事实类内容里有不确定的地方，单独列出来让用户核对。

## 遇到这些情况

- **用户想要真人或写实角色**：代码画不出来。可以建议用户先用视频模型生成**纯绿幕背景**的人物片段，交给本 skill 抠像，再用代码搭场景、大字和动效，做法见 code-stack.md 的「视频模型角色 + 代码场景」。
- **渲染太慢**：先降分辨率或帧率出小样，确认后再出正式版；运动模糊和 WebGL 后期是最耗时的两项。
- **浏览器里 WebGL 不可用**：`check_env.py` 会提示；先渲一帧确认着色器真的生效了，再渲整片。
- **用户只想要提示词**：跳过第 5、6 步，把 `brief.md` 交给用户即可。
