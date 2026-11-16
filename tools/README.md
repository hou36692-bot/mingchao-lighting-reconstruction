# Tools

这些脚本用于**取证、构建与验证**这次 UE 5.8 光照还原。仓库**不包含** UE 工程、RDC 捕获、游戏原始资产或派生数据；因此只有 `analysis/` 里的少数纯数学脚本可以直接运行，其余脚本是参考实现，需要本地环境或源数据。

## 状态矩阵

| 组 | 运行时 | 能否直接跑 | 证明什么 |
| --- | --- | --- | --- |
| `analysis/` | Node 24 | **部分可以** | AO/LUT/CSM 数学、拟合、逐像素对比 |
| `ue/` | UE 5.8 + UE_MCP_Bridge | 否 | 材质/关卡集成、视口截图 |
| `renderdoc/` | RenderDoc 1.45 Python | 否 | 事件/PS/常量/RT 导出 |
| `image/` | Node 24 | **是** | PNG 读写、缩放、并排、差分、裁剪 |

## 环境变量

```bash
cp config/tools.env.example config/tools.env
# 编辑 config/tools.env
source config/tools.env
```

| 变量 | 用途 |
| --- | --- |
| `MC_WORKSPACE` | 本仓库根目录（默认 `.`） |
| `UE_PROJECT` | 本地 UE 5.8 工程根目录 |
| `UE_MCP_WS` | `ws` 模块路径，或在仓库根 `npm i ws` 后留空 |
| `RENDERDOC_DIR` | RenderDoc 安装目录（含 `qrenderdoc`） |
| `MC_OUT` | 输出目录（默认 `./out`） |

`ue/ue.mjs` 从 `${UE_PROJECT}/Saved/UE_MCP_Bridge/port.json` 读取端口；编辑器必须先启动桥接。

## analysis/

| 脚本 | 作用 | 直接跑？ | 依赖 |
| --- | --- | --- | --- |
| `ao_ref.mjs` | 屏幕空间 AO 的 CPU 参考实现（库） | 是 | 无 |
| `ao_test.mjs` | AO 合成场景单测（平地/内凹角/悬空球/天空/远裁） | **是** | 无 |
| `csm_fit.mjs` | UE 级联分割拟合 | **是** | 无 |
| `lut_bake.mjs` | 32³ LUT 烘焙为 1024×32 PNG 条带 | **是** | 无 |
| `ao_gpu_compare.mjs` | GPU 回读 vs CPU 参考逐像素对比 | 否 | 本地 AO GPU 回读 JSON |
| `lut_verify.mjs` | 导入 UE 后的 LUT 查表 vs CPU 参考 | 否 | 本地 RT 导出 |
| `cluster_ref.mjs` | CPU 复刻 UE Light Grid 剔除 | 否 | 源帧视空间灯缓冲（仓库不提供） |
| `cluster_cmp.mjs` | CPU 复刻 vs UE Light Grid debug 逐像素比 | 否 | UE debug 图 + 深度 |
| `mc_lights.mjs` | 解码源帧灯缓冲为 35 盏灯参数 | 否 | 源帧灯缓冲 |
| `tod_ratio.mjs` | 从 HDR 截图测太阳/天光比 | 否 | 本地 HDR 截图 |
| `veg_build_mesh.mjs` | 从源 VB/IB/UV 重建草 OBJ | 否 | 源网格缓冲 |
| `veg_inst_stats.mjs` | 源草实例缩放/偏航/密度统计 | 否 | 源实例数据 |

> `cluster_ref.mjs` / `mc_lights.mjs` / `veg_*` / `tod_ratio.mjs` / `lut_verify.mjs` / `ao_gpu_compare.mjs` 的文件头标了 `reference implementation; source data not included`。仓库不分发这些源数据。

## ue/

| 脚本 | 作用 |
| --- | --- |
| `ue.mjs` | 极简 UE_MCP_Bridge WebSocket 客户端 |
| `py.sh` | 把 Python 文件送进编辑器执行 `run(*args)` |
| `ue_shot.py` | SceneCapture2D 截图 + RT 读回 |
| `vpshot.sh` | **真实视口截图**（挪相机 → HighResShot → 还原） |
| `ue_vp_cam.py` | 视口相机 get/set/restore（`vpshot.sh` 的辅助脚本） |
| `ue_unminimize.ps1` | 截图前还原最小化的编辑器窗口（不抢焦点） |
| `ue_mpc_set.py` | 改 MPC 标量参数 |
| `ue_build_pp_generic.py` | 单 Custom 节点后处理材质生成器 + 挂 PPV |
| `ue_build_pp_sh.py` | 构建 `M_PP_SH_Ambient` |
| `ue_build_pp_ao.py` | 构建 `M_PP_CustomAO`（读 `hlsl/pp_custom_ao.hlsl`） |
| `ue_build_pp_lut.py` | 构建 `M_PP_LUT`（读 `hlsl/pp_lut.hlsl`） |
| `ue_sh_apply.py` | 天空 6 面捕获 → SH 投影 → 写 MPC |
| `ue_csm_mode.py` | 运行时切 `vsm / csm_ue / csm_mc` |
| `ue_tod_apply.py` | 太阳/天光/雾/曝光映射 |
| `ue_water_restore.py` | SLW 水面系数注入与开关 |
| `ue_veg_restore.py` | 草网格导入/材质/撒布/恢复 |

这些脚本假定配套工程使用 `/Game/Reconstruction/Rendering/_Restore/...` 资产布局；仓库不含 `.uasset`，所以它们是**参考集成**，不是一键插件。UE 5.8 的自动化坑（MaterialFunction 不能用 `MaterialEditingLibrary`、函数 pin 名带类型后缀、PP 域必须用 `PostProcessInput0` 等）见 [docs/toolchain.md](../docs/toolchain.md)。

## renderdoc/

| 脚本 | 作用 |
| --- | --- |
| `rdrun.sh` | 串行调用 `qrenderdoc` Python |
| `rd_events.py` | 导出事件表 |
| `rd_ps_dump.py` | 导出指定 PS 反汇编 |
| `rd_save_rt.py` | 保存 RenderTarget |
| `rd_probe.py` | 通用探查入口 |

需要本地 RenderDoc 1.45 与对应 `.rdc`；仓库不分发 RDC。把 `RENDERDOC_DIR` 指到安装目录。

## image/

| 脚本 | 作用 |
| --- | --- |
| `png.mjs` | 纯 Node PNG 读写、`resize` / `sbs` / `diff` / `crop` |
| `img_diff.mjs` | 两张图逐像素差分热图 |
| `img_stats.mjs` | 分带亮度/饱和度统计 |
| `cmp_stats.mjs` | 两张图的分带统计对比 |

全部无外部依赖，直接 `node tools/image/png.mjs ...`。

## 两个容易对不上的数字

1. **CSM 级联**：`csm_fit.mjs` 会打印 4 个 dynamic cascades + 1 个 far 的 5 级结果（723/2361/6131/14800/32500），以及 3+2、2+3 的变体；关卡实际使用的是 `ue_csm_mode.py` 里的 5 个 dynamic cascades（`e=2.24, R=32500` → **737/2366/6016/14190/32500**）。README 与模块文档用后者。
2. **AO 半径**：源帧的 `15` 是它自己的相机/缩放空间；UE 侧默认 `150 cm` 是起步值，不是等值换算。两者不能直接对等。

## 不包含

- 任何 `.rdc`、`.uasset`、`.umap`、`.pak`、游戏贴图/网格/Shader 反汇编。
- 任何游戏派生数据样本（灯 JSON、TOD 曲线、LUT 条带、草 OBJ）。
- UE 工程、`Content/`、`Binaries/`、`Intermediate/`、`Saved/`。
