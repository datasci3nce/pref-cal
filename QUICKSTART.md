# Quick start: upload PREF-CAL to GitHub

1. Unzip the release. The folder you want is `PREF-CAL/`.
2. Create a new empty GitHub repository. Do **not** initialize it with another README or `.gitignore`.
3. In a terminal opened inside the `PREF-CAL/` folder, run:

```bash
git init
git add .
git commit -m "Release PREF-CAL v1.4"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git
git push -u origin main
```

4. On GitHub, wait for the `Verify release` Action to turn green.
5. Put the report link in the hackathon submission:

```text
reports/PREF_CAL_Digital_Minds_Submission.pdf
```

Before pushing, verify the archive without any model calls:

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
python -m pip install -e ".[dev]"
python scripts/verify_release.py
```

Never commit `NVIDIA_API_KEY` or another provider credential. The checked-in configs contain only environment-variable names.

