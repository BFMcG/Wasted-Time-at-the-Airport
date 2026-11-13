import sys
from pathlib import Path

WEBSITE_DIR = Path(__file__).parent
# importing from main/
sys.path.insert(0, str(WEBSITE_DIR.parent / "main"))

import pages

sample = {
    "data_date": "2026-11-10",
    "views": {
        "total_delay_month": [
            {"days_wasted": 3, "hours_wasted": 7, "minutes_wasted": 12, "secs_wasted": 45}
        ],
        "total_delay_yesterday": [
            {"days_wasted": 0, "hours_wasted": 9, "minutes_wasted": 41, "secs_wasted": 3}
        ]
    }
}

for page_key, html in pages.SITE.render_all(sample).items():
    output = WEBSITE_DIR / page_key
    output.write_text(html, encoding="utf-8")
    print(f"Wrote {output}")