# 架构：从截帧证据到 UE 光照

> 目标：给定《鸣潮》(Wuthering Waves) 一个场景帧的 RenderDoc 截帧，在 Unreal Engine 5.8 中重建该帧的主要光照结构和关键参数，并以可开关的方式逐模块验证。
> 本文说明项目的范围、证据链、模块划分与落地方式。各模块细节见同目录下的专题文档。

## 1. 项目目标与边界

**目标**：还原「水岸高塔」场景的日间光照，本仓库整理其中五个模块：屏幕空间 AO、级联阴影（CSM, Cascaded Shadow Maps）、聚簇光照（clustered lighting）、水面和地表植被。每个模块都能与原生 UE 实现并排对照。判定标准是结构与参数一致，不是像素级一致。

**载体边界**：全部实现落在 Material + Custom Node 上，不写 C++、不写 Global Shader。这直接决定了哪些环节能自研：全屏 raymarch AO 可以写成后处理材质；聚簇剔除是 compute shader，shadow map 的采样 UE 也不暴露给材质，这两块只能做参数对照与可视化。

**资产边界**：所有还原改动只落在复制出来的还原关卡与其独立目录内，原场景关卡与工程其余部分不动；引擎源码只读查证，不修改。

## 2. 源帧与采样

截帧集为同一街景的 8 个机位，每帧 RDC 约 1.6–2.1 GB，3840×2160，D3D11。[事实]

| 项 | 内容 |
| --- | --- |
| 主分析帧 | Frame 61250（面向高塔，水岸） |
| 交叉验证帧 | Frame 36153（补拍草坪） |
| 单帧规模 | 2302 Draw / 53 Dispatch / 939 张纹理 / 172 个自动切分 Pass |
| 切分方式 | 发布版无 marker，按「输出 RT 组合变化」自动切 Pass，编号是本项目的标签 |

主帧只重画了 2 级 CSM（其余槽位是上一帧残留），局部灯 35 盏。

## 3. 渲染链到 UE 的映射

逆向阶段把这一帧分成 13 个阶段。与本仓库五个模块相关的如下：

| 鸣潮阶段 | 内容 | UE 对应 | 本项目动作 |
| --- | --- | --- | --- |
| E–F 几何/GBuffer | 7-MRT 写入，含地表草 | Deferred GBuffer | 植被网格重建 |
| H 阴影 | CSM + 局部光阴影 | CSM | 参数对齐 |
| I 屏幕空间 | 贴花 + AO 链 | Decal + GTAO | 自研 AO 接入 |
| K 光照合成 | 聚簇延迟光照 | Light Grid | 灯光落地 + 剔除对照 |
| 水面 | 单层水体着色 | Single Layer Water | 系数对齐 |

其余阶段（准备、预深度、遮挡查询、体积、后处理、终合成）由 UE 自身覆盖，或不在本仓库范围内。

![模块与插入位置](./images/diagrams/module-map.svg)

## 4. 证据链

每个模块尽量走同一条链，避免用「看着像」代替可核验的结论：

1. **截帧**：RenderDoc 打开 RDC，定位到具体 event / pixel shader。
2. **数值**：导出该 event 的常量缓冲、结构化缓冲、RT，取得实值（颜色、方向、系数、尺寸）。
3. **源码对照**：在 UE 5.8 源码中找同名算法与常数，判断这是 UE 原生行为还是鸣潮自改。
4. **CPU 参考**：用独立脚本按 shader 逐行复刻核心数学，可离线单测。
5. **UE 材质**：Custom Node 承载同一段数学，输入来自 GBuffer 与 MPC。
6. **验证**：GPU 渲染到 RT 后回读，与 CPU 参考逐像素比对；视觉部分再用真实视口截图确认。

![证据链：截帧 → 常量 → 源码对照 → 参考实现 → 材质 → 验证](./images/diagrams/evidence-chain.svg)

第 3 步是整条链的关键。它把「猜鸣潮用了什么」变成了「确认鸣潮用的是 UE 的哪一段」，也决定了每个模块是自研还是参数对齐。水面和植被以参数和资产为主，第 4–6 步换成同机位截图和区域统计。

## 5. 鸣潮是 UE4 系渲染器

下面几项都能在 UE 源码（`Engine/Shaders` 与 `Engine/Source`）里找到同名实现。这个判断改变了整个还原策略：CSM、聚簇、水面不需要近似替代。[事实]

| 维度 | 鸣潮侧观察 | UE 源码侧 | 结论 |
| --- | --- | --- | --- |
| 聚簇切片 | 深度切片 `log2(z·B+O)·S`，S=4.05，反解 near=10 cm | `GetLightGridZParams`，`DepthDistributionScale = 4.05f` | 同公式同常数 |
| 聚簇布局 | 60×34×32 簇、64 px 瓦片、每簇 32 灯槽 | `LightGridPixelSize` 等默认值 | 全部是 UE 默认值 |
| 灯数据打包 | 10:10:10 打包颜色、点光哨兵值 | `PackLightColor`、`PackedPreProcAngleAndFlags` | 同一数据结构 |
| CSM 滤波 | 5×5 PCF，每槽 2048−2×4 | `Manual5x5PCF`、`SHADOW_BORDER=4` | 逐行对应 |
| 水面 | shading model ID=10，Schlick 相位 | `SHADINGMODELID_SINGLELAYERWATER`、`SchlickPhase` | 就是 UE 的单层水体 |

所以 CSM、聚簇、水面是对同一算法的参数对齐。AO 在两边实现方式不同，UE 也不暴露中间结果，是本仓库里唯一需要从头写的着色模块；植被则是用源帧网格数据重建资产。

## 6. 模块一览

| 模块 | 证据 | UE 载体 | 做法 | 验证 | 状态 |
| --- | --- | --- | --- | --- | --- |
| AO | 8 方向 × 4 步，三级 + 时域 [事实] | `M_PP_CustomAO` + CPU 参考 | 单 Pass 近似 | 合成场景单测；GPU 与 CPU 逐像素比对 | 数学已验证，视口观感待验收 |
| CSM | 5 级、5×5 PCF [事实] | 引擎 CSM（三模式切换） | 参数对齐 | 三模式并排 + 级联色带 | 完成 |
| 聚簇 | 35 灯、60×34×32 [事实] | UE Light Grid + 35 盏源灯 | 参数对齐 + CPU 复刻剔除 | 照亮对象一致；每像素灯数逐像素比对 | 完成 |
| 水面 | SLW 系数、相位 g [事实] | `MI_Water_Restore_SLW` | 填系数 + 少量美术项 | 开关响应、同机位观感 | 完成 |
| 植被 | 两种源网格、UV 段、实例分布 [事实] | `SM_WWGrass_TriCard_A/B` + `MI_WWGrass` | 源网格 + 程序化分布 | 有草/无草差分统计 | 已实现，待最终视口验收 |

各项残余差距集中写在 [boundaries.md](./boundaries.md)。

## 7. 控制面：MPC 与 PPV

**开关**：材质参数集合（Material Parameter Collection, MPC）`MPC_RestoreControl` 承载 AO 的开关与参数（`Enable_Custom_AO`、`AO_Radius`、`AO_Intensity`、`AO_Debug_View`），以及级联调试用的标量。水面因「一个材质最多引用 2 个 MPC」的限制，开关放在材质实例参数上，再镜像到 MPC 的 `Enable_Water_Absorb` 供脚本查询。约定：开关为 0 时材质直接返回输入颜色，保证「关」等于原生画面。

**后处理体积（Post Process Volume, PPV）**：

| 材质 | 插入点 | 作用 |
| --- | --- | --- |
| `M_PP_CustomAO` | Before Bloom | 屏幕空间 AO，乘在不透明表面 |
| `M_PP_RestoreDebugViz` | After Tonemapping | 级联色带 / 聚簇瓦片调试 |

AO 放在 Bloom 之前，SceneColor 仍是线性 HDR，后续的 Bloom 和曝光能看到 AO 的结果。调试材质独立成一件，不往生产材质里塞探针。参数表见 [config/mpc-restore-control.md](../config/mpc-restore-control.md)。

## 8. 关卡与资产布局

还原在一个复制出来的关卡上进行，新增内容集中在独立的还原目录。

| 目录 | 内容 |
| --- | --- |
| `_Restore/Common` | `MPC_RestoreControl`、`M_PP_RestoreDebugViz` |
| `_Restore/AO` | `M_PP_CustomAO`、测试材质 |
| `_Restore/Water` | 水面材质实例（基于工程既有的单层水体材质） |
| `_Restore/Veg` | 两种草网格与材质实例 |

关卡里另有 PPV 宿主、35 盏源灯（独立 Outliner 文件夹），以及水面和植被的组件级覆盖。仓库不收录 `.uasset/.umap`，也不收录灯数据、草地实例等任何游戏派生数据，只保留统计数字与截图。

## 9. 设计决定

| 决定 | 选择 | 理由 |
| --- | --- | --- |
| 全局光照 | 保留 Lumen | 自研模块用独立开关叠加，可随时与原生画面并排 |
| 阴影 | 保留 VSM 做基线，CSM 做对照 | 运行时切换阴影模式，三种状态同机位对比 |
| 实现载体 | Material + Custom Node | 不写 C++、不写 Global Shader；代价是聚簇与 shadow map 无法自研 |
| Substrate | 关闭 | 全工程材质均未使用 Substrate 节点 |
| 引擎源码 | 只读，不修改 | 对照基于公开发布的 5.8 源码，结论可复现 |
| 原场景 | 不修改 | 还原内容全部在关卡副本与独立目录内 |

这些决定界定了能做到什么程度：能自研的 AO 做到数值可验证，阴影、聚簇、水面做到参数层面可核验的对齐，植被按源数据重建网格，位置和颜色写明近似从哪里开始。
