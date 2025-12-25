# CALB ESS Sizing Tool

This repository contains a Streamlit application for sizing energy storage systems across Stage 1–4 and lightweight unit tests for the Stage 4 interface helpers.

## Setup

1. Create and activate a virtual environment (recommended).
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Run the app

Launch the Streamlit application from the repository root:

```bash
streamlit run app.py
```

Ensure the Excel data files (for example, `ess_sizing_data_dictionary_v13_dc_autofit.xlsx`) are present in the same directory before running.

## Report V2.1 (Beta) usage

1. Run DC sizing and AC sizing as usual.
2. In the AC Sizing downloads area, select `Report Template: V2.1 (Beta)`.
3. Download the Combined report. V1 remains the default and unchanged.

## SLD Generator usage (PowSyBl, single MV node chain)

1. Install dependencies: `pip install pypowsybl`.
2. Run DC sizing and AC sizing.
3. Open the `SLD Generator (PowSyBl)` page (beta).
4. Click **Generate SLD Snapshot + SVG**, then download `snapshot.json`, `sld.svg`, `sld_metadata.json`, and `sld_final.svg`.

## SLD Generator Pro usage (engineering style)

1. Install dependencies: `pip install pypowsybl`.
2. Run DC sizing and AC sizing.
3. Open the `SLD Generator Pro` page.
4. Fill Electrical SLD Inputs (RMU/TR/Busbar/Cables), then click **Generate SLD Pro**.
5. Download `sld_pro.svg` alongside the raw SVG, metadata, and snapshot.

## Run tests

Execute the test suite with:

```bash
pytest -q
```
感谢您使用和关注本项目！
本项目基于开源生态构建，参考并使用了社区中多种优秀技术与工具。我们尊重开源许可证并在此明确致谢：

This project is built upon and inspired by the open source community. We acknowledge and appreciate the many frameworks, libraries, tools, and resources that make this work possible. Users are encouraged to review and comply with the respective licenses of third‑party components used herein.

如您在使用本项目过程中引用或修改了本仓库的代码，请保留本说明及相关开源许可证信息，并在发布成果时注明来源。
If you redistribute or build upon this project, please retain this notice, and clearly credit the original source.

📬 联系方式 / Contact

如需技术沟通、反馈建议，请通过以下方式联系我：
For technical questions, feedback, or business inquiries, feel free to reach out via:

微信 WeChat: +14015927928 


WhatsApp: +14015927928 


https://www.linkedin.com/in/alex-zhaoyutao
