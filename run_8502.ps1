$ErrorActionPreference = "Stop"
if (!(Test-Path ".venv")) {
  py -m venv .venv
}
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py --server.port 8502
