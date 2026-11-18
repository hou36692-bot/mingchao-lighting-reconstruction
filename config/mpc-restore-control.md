# MPC_RestoreControl 参数表与开关约定

本文说明还原工程中用于「原方案 / 还原方案」并排对照的材质参数集合（Material Parameter Collection，MPC），以及后处理材质的挂载顺序。

> 这是参考文档，不是可直接导入的资产。MPC 本身是二进制 `.uasset`，不在本仓库内；下表只记录参数名、默认值和用途，便于阅读代码与复现材质逻辑。

## 1. 资产与用途

| 项 | 内容 |
| --- | --- |
| MPC 资产 | `/Game/Reconstruction/Rendering/_Restore/Common/MPC_RestoreControl` |
| 作用 | 为自研模块提供统一的开关、强度、调试模式与常量 |
| 读取方式 | 材质中用 `CollectionParameter` 节点读取 |
| 写入方式 | 编辑器内修改，或用 UE 自动化脚本批量写入 |

每个自研模块都能单独开关，随时与 UE 原生结果并排比较。开关为 0 时，材质输出应退化为原始 UE 结果。

## 2. 参数表

### 2.1 模块开关（Scalar，0/1）

| 参数 | 默认 | 作用 |
| --- | --- | --- |
| `Enable_Custom_AO` | 0 | 屏幕空间自研 AO 开关；0 = 直通，1 = 应用 AO |
| `Enable_Water_Absorb` | 0 | 水体吸收开关的镜像；0 = 原 UE 近似参数，1 = 鸣潮 SLW 吸收/散射参数 |

### 2.2 AO 参数

| 参数 | 类型 | 默认 | 作用 |
| --- | --- | --- | --- |
| `AO_Radius` | Scalar | 150 | 世界空间 AO 半径（cm）；起步值，未与鸣潮的 15 做单位换算 |
| `AO_Intensity` | Scalar | 1 | AO 强度 |
| `AO_Debug_View` | Scalar | 0 | 0 = 正常着色，1 = 输出 AO 灰度 |

### 2.3 调试与 CSM 镜像参数

| 参数 | 类型 | 默认 | 作用 |
| --- | --- | --- | --- |
| `Debug_Viz_Mode` | Scalar | 0 | 0 = 关闭；1 = 鸣潮级联色带；2 = 当前 UE 级联色带；3 = 64px 瓦片 + 32 片指数深度着色 |
| `CSM_UE_Exponent` | Scalar | 3.0 | 当前太阳的级联分布指数，供调试材质绘制 UE 级联色带 |
| `CSM_UE_Distance` | Scalar | 34000 | 当前 CSM 有效阴影距离（cm）= 阴影距离 × `r.Shadow.DistanceScale` |
| `CSM_UE_Count` | Scalar | 4 | 当前实际级联数 = min(太阳级联数, `r.Shadow.CSM.MaxCascades`) |

`Debug_Viz_Mode` 与 `CSM_UE_*` 主要服务调试材质 `M_PP_RestoreDebugViz`。其中 `CSM_UE_*` 由 CSM 模式切换脚本在运行时写入，数值跟随太阳组件属性与 cvar 变化。

### 2.4 水面参数（不在 MPC 中）

水体吸收的散射/吸收/相位参数位于材质实例 `MI_Water_Restore_SLW` 的参数组 `WW Restore (Water)`：

| 参数 | 默认（原 UE） | 鸣潮值 | 作用 |
| --- | --- | --- | --- |
| `MC_Scattering_1PerCm` | 0（引脚未接） | (3.0e-5, 8.3e-5, 1.0e-4) | SLW 散射系数 |
| `MC_Absorption_1PerCm` | (0.005, 0.0025, 0.0015) | 0.0167（灰） | SLW 吸收系数 |
| `MC_PhaseG` | 0（引脚未接） | 0.5 | 相位函数各向异性 |
| `Enable_Water_Absorb` | 0 | 1 | 开关；同时镜像到 MPC |

UE 中一个材质最多引用 2 个 MPC，水面材质已使用 `MPC_WaterAnimationClock` 与 `MPC_WaterConditions`，所以开关只能做成材质实例参数，再镜像到 MPC 供脚本读取。

## 3. 开关约定

1. 所有模块开关取 0 或 1，不做连续混合。
2. 材质内统一写成 `Lerp(原始值, 还原值, Enable)`，或等价的 `原结果 + 还原增量 × Enable`。
3. `Enable = 0` 时输出必须与改造前的 UE 结果一致，对比图才可信。
4. AO 开关只影响后处理材质，不影响场景资产；水面开关影响材质实例，不改变关卡几何。
5. 一个开关只驱动一个模块，便于归因。
6. 调试探针放在独立的 `M_Dbg_*` 资产上，不写进共享的 `M_PP_*`，以免影响正常视口。

## 4. 后处理材质顺序（PPV）

宿主：关卡中的 `APPROX_Daylight_Exposure`（PostProcessVolume，Unbound，Priority 100）。

| 序 | 材质 | Blendable Location | 说明 |
| --- | --- | --- | --- |
| 1 | `M_PP_CustomAO` | Before Bloom | SceneColor 仍为线性 HDR，AO 在 Bloom 前作用 |
| 2 | `M_PP_RestoreDebugViz` | After Tonemapping | 调试可视化，正常出图时 `Debug_Viz_Mode = 0` |

后处理材质只在编辑器视口中随 PPV 生效；`SceneCapture2D` 未开启逐帧捕获时会跳过 PP blendable，所以开关效果以真实视口截图为准。

## 5. 典型状态

| 场景 | `Enable_Custom_AO` | `Enable_Water_Absorb` | `Debug_Viz_Mode` |
| --- | --- | --- | --- |
| 纯 UE 基线 | 0 | 0 | 0 |
| 还原出图 | 按需 | 1 | 0 |
| CSM 色带检查 | 0 | 0 | 1 或 2 |
| 聚簇瓦片调试 | 0 | 0 | 3 |
