# Tools

这些脚本用于这次 UE 5.8 光照还原的取证、构建与验证。仓库不包含 UE 工程、RDC 截帧、游戏原始资产或派生数据，所以只有 `analysis/` 里的少数纯数学脚本和 `image/` 可以直接运行，其余是参考实现，需要本地环境或源数据。

## 状态

| 组 | 运行时 | 能否直接跑 | 用途 |
| --- | --- | --- | --- |
| `analysis/` | Node 24 | 部分可以 | AO / CSM 数学、拟合、逐像素对比 |
| `ue/` | UE 5.8 + UE_MCP_Bridge | 否 | 材质与关卡集成、视口截图 |
| `renderdoc/` | RenderDoc 1.45 Python | 否 | 导出事件、PS、常量、RT |
| `image/` | Node 24 | 是 | PNG 读写、缩放、并排、差分、裁剪 |

## 环境变量

```bash
cp config/tools.env.example config/tools.env
# 编辑 config/tools.env
source config/tools.env
```

| 变量 | 用途 |
| --- | --- |
| `MC_WORKSPACE` | 源数据工作区根目录（默认 `.`） |
| `UE_PROJECT` | 本地 UE 5.8 工程根目录 |
| `UE_MCP_WS` | `ws` 模块路径，或在仓库根 `npm i ws` 后留空 |
| `RENDERDOC_DIR` | RenderDoc 安装目录（含 `qrenderdoc`） |
| `MC_OUT` | 输出目录（默认 `./out`） |

`ue/ue.mjs` 从 `${UE_PROJECT}/Saved/UE_MCP_Bridge/port.json` 读取端口，编辑器需要先启动桥接插件。

## analysis/

| 脚本 | 作用 | 直接跑 | 依赖 |
| --- | --- | --- | --- |
| `ao_ref.mjs` | 屏幕空间 AO 的 CPU 参考实现（库） | 是 | 无 |
| `ao_test.mjs` | AO 合成场景测试（平地、墙角、悬空球、天空、远裁） | 是 | 无 |
| `csm_fit.mjs` | UE 级联分段拟合 | 是 | 无 |
| `ao_gpu_compare.mjs` | GPU 回读与 CPU 参考逐像素对比 | 否 | 本地 AO GPU 回读 JSON |
| `cluster_ref.mjs` | 按 UE 源码复刻 Light Grid 剔除 | 否 | 源帧视空间灯缓冲 |
| `cluster_cmp.mjs` | CPU 复刻与 UE Light Grid 调试输出逐像素对比 | 否 | UE 调试截图与深度 |
| `mc_lights.mjs` | 把源帧灯缓冲解成 35 盏灯的参数 | 否 | 源帧灯缓冲 |
| `veg_build_mesh.mjs` | 用源顶点、索引、UV 重建草网格 OBJ | 否 | 源网格缓冲 |
| `veg_inst_stats.mjs` | 统计源草实例的缩放、朝向和密度 | 否 | 源实例数据 |

需要源数据的脚本在文件头标了 `reference implementation; source data not included`。

## ue/

| 脚本 | 作用 |
| --- | --- |
| `ue.mjs` | 极简 UE_MCP_Bridge WebSocket 客户端 |
| `py.sh` | 把 Python 文件送进编辑器执行 `run(*args)` |
| `ue_shot.py` | SceneCapture2D 截图并读回 RT |
| `vpshot.sh` | 真实视口截图（挪相机、HighResShot、还原相机） |
| `ue_vp_cam.py` | 视口相机 get/set/restore，供 `vpshot.sh` 调用 |
| `ue_unminimize.ps1` | 截图前还原最小化的编辑器窗口，不抢焦点 |
| `ue_mpc_set.py` | 改 MPC 标量参数 |
| `ue_build_pp_generic.py` | 单 Custom 节点后处理材质生成器，可挂到 PPV |
| `ue_build_pp_ao.py` | 构建 `M_PP_CustomAO`（读 `hlsl/pp_custom_ao.hlsl`） |
| `ue_csm_mode.py` | 运行时切换 `vsm / csm_ue / csm_mc` |
| `ue_water_restore.py` | 水面系数注入与开关 |
| `ue_veg_restore.py` | 草网格导入、材质、撒布与恢复 |

这些脚本假定配套工程使用 `/Game/Reconstruction/Rendering/_Restore/...` 资产布局。仓库不含 `.uasset`，它们是参考集成，不是插件。UE 5.8 自动化里遇到的问题（MaterialFunction 不能用 `MaterialEditingLibrary`、函数 pin 名带类型后缀、PP 域必须用 `PostProcessInput0` 等）见 [docs/toolchain.md](../docs/toolchain.md)。

## renderdoc/

| 脚本 | 作用 |
| --- | --- |
| `rdrun.sh` | 串行调用 `qrenderdoc` 执行 Python 脚本 |
| `rd_events.py` | 导出事件表 |
| `rd_ps_dump.py` | 导出指定 PS 反汇编 |
| `rd_save_rt.py` | 保存 RenderTarget |
| `rd_probe.py` | 通用探查入口 |

需要本地 RenderDoc 1.45 和对应的 `.rdc`，仓库不分发 RDC。

## image/

| 脚本 | 作用 |
| --- | --- |
| `png.mjs` | PNG 读写，`resize` / `sbs` / `diff` / `crop` |
| `img_diff.mjs` | 两张图的逐像素差分热图 |
| `img_stats.mjs` | 分区亮度与饱和度统计 |
| `cmp_stats.mjs` | 两张图的分区统计对比 |

全部只用 Node 内置模块，直接 `node tools/image/png.mjs ...` 即可。

## 两个容易对不上的数字

1. CSM 级联：`csm_fit.mjs` 会打印“4 级近景 + 1 级远景”的结果（723/2361/6131/14800/32500）以及几个变体；关卡实际用的是 `ue_csm_mode.py` 里 5 级普通级联的设置（`e=2.24, R=32500`，得到 737/2366/6016/14190/32500）。文档用的是后者。
2. AO 半径：源帧的 `15` 在它自己的相机空间里，UE 侧默认的 `150 cm` 是起步值，两者不是换算关系。

## 不包含

- `.rdc`、`.uasset`、`.umap`、`.pak`、游戏贴图、网格和 shader 反汇编。
- 游戏派生数据样本（灯数据、草网格 OBJ 等）。
- UE 工程及其 `Content/`、`Binaries/`、`Intermediate/`、`Saved/`。
