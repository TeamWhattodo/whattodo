from pathlib import Path
from tinydb import TinyDB, Query

DB_DIR = Path(__file__).parent / "data"
DB_DIR.mkdir(parents=True, exist_ok=True)

work_items_db = TinyDB(DB_DIR / "work_items.json")
expense_reports_db = TinyDB(DB_DIR / "expense_reports.json")
ItemQuery = Query()
