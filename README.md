☁️ Cloud Readers (云读者)
Resurrecting Bio-mechanics from Static Art. 从静止的艺术中，复活生物力学。

<p align="center"> <img src="https://img.shields.io/badge/Architecture-PA--Native%20v7.2-000000?style=flat-square" /> <img src="https://img.shields.io/badge/Protocol-RCP%202025-blue?style=flat-square" /> <img src="https://img.shields.io/badge/Status-Experimental-orange?style=flat-square" /> </p>

Cloud Readers 是一个逆向工程时间的数据兵工厂。 它利用神经科学中的 2/3 幂定律 (Two-Thirds Power Law)，从静止的油画、书法或摄影作品中，解压出丢失的时间维度，重建出具有完美生物力学特征（速度、加速度、压力、抖动）的触控轨迹与传感器数据。

我们不生产数据，我们只是大自然和艺术史的搬运工。

🧠 核心哲学 (Philosophy)
艺术即数据 (Art is Data): 梵高的笔触不仅是颜料，更是高熵值的神经系统运动记录。

形状即速度 (Geometry is Velocity): 生物运动的曲率与速度存在强耦合，无需原始时间戳即可逆向还原。

仿真即真实 (Simulation is Reality): 通过物理引擎补全 IMU 数据，让虚拟轨迹拥有物理质量。

🏗️ 处理流水线 (The Pipeline)
Cloud Readers 采用 S01-S05 的标准化流水线，将静态图像转化为符合 rcp_2025 标准的二进制流。

代码段

graph TD
    subgraph S01_Ingestion [摄入层]
        IMG[原始图像<br>Van Gogh / Calligraphy] --> META[元数据注入<br>Style / DPI / Device]
    end

    subgraph S02_Extraction [CV 处理层]
        META --> BIN[二值化 & 骨架提取]
        BIN --> HOUGH[霍夫变换<br>去除纯直线/非生物特征]
    end

    subgraph S03_Kinematics [动力学重构]
        HOUGH --> POWER[2/3 幂定律<br>生成速度分布 v(t)]
        POWER --> PRESS[笔触宽度分析<br>生成压力分布 p(t)]
        PRESS --> TEXTURE[残差提取<br>生成微观肌理]
    end

    subgraph S04_Simulation [仿真增强]
        TEXTURE --> VALID{质量熔断<br>Check Entropy/SNR}
        VALID -- Pass --> SIM[Isaac Sim / 物理引擎]
        SIM --> IMU[逆向生成传感器数据<br>ACC / GYRO]
    end

    subgraph S05_Storage [序列化]
        IMU --> PROTO[RCP Protocol Encoding]
        PROTO --> DISK[rcp_2025 Storage]
    end
💾 数据协议 (The Protocol)
输出数据严格遵循 RCP_2025 (Reality Capture Protocol) 标准，采用列式存储设计，兼顾高频读取性能与压缩率。

目录结构
Plaintext

rcp_2025-11-26T12-00Z_{uuid}/
├─ manifest.json              # 元数据真理 (DPI, Device Profile, Source Art)
├─ index.json                 # 快速检索索引 (Count, Duration, Integrity)
├─ channels/                  # 列式存储分片 (Zstd Compressed)
│  ├─ touch.pbz               # 核心轨迹 [t, x, y, p, size]
│  ├─ acc.pbz                 # 仿真加速度 [t, x, y, z]
│  ├─ gyro.pbz                # 仿真陀螺仪 [t, x, y, z]
│  └─ ... (battery, light)    # 环境上下文
└─ checksums.txt              # 数据完整性校验
🛠️ 功能特性 (Features)
1. 调酒师 (The Blender)
支持多风格混合。将“狂草”的连贯性与“印象派”的抖动进行频域融合，生成独一无二的 UUID 级轨迹，防止指纹撞车。

2. 品鉴师 (The Sommelier)
自动分析提取出的轨迹特征，输出行为画像标签：

Tag: Aggressive (激进型) -> 适合抢购/秒杀。

Tag: Chill (佛系型) -> 适合阅读/挂机。

3. 显微镜 (The Microscope)
提取画布底层的物理颗粒（Canvas Grain），映射为光电鼠标在粗糙表面滑动时产生的高频底噪。

🚀 快速开始 (Quick Start)
0. 安装依赖
Bash

# 使用 uv 安装项目依赖
uv sync

1. 准备原材料
找一张公版名画（推荐《星月夜》或《自叙帖》），分辨率越高越好。

2. 运行提取
Bash

# 提取轨迹，指定输出设备为 Pixel 4
uv run cr extract --source "starry_night.jpg" --device "pixel_4" --style "aggressive" --out "./artifacts/extraction"
3. 运行仿真增强
Bash

# 补全 IMU 数据
uv run cr simulate --input-dir "./artifacts/extraction" --physics-engine "internal" --out "./artifacts/simulation"
4. 导出
Bash

# 生成最终 RCP 包
uv run cr export --extraction-dir "./artifacts/extraction" --simulation-dir "./artifacts/simulation" --format rcp_2025 --out "./dataset/"
⚠️ 免责声明 (Disclaimer)
本工具是一个“引擎”，不包含任何“燃料”。 用户需自行寻找合法的图像源进行生成。

本工具产生的轨迹仅供研究与测试（如测试风控系统的鲁棒性）。 请勿用于非法用途。

Art is dead, long live the Data.

License
MIT © 2025 Natural Control Architect
