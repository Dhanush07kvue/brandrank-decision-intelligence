from app.ingestion.pipeline import run_ingestion
from app.services.db import Database
from app.settings import settings


def main() -> None:
    db = Database(settings.db_path)
    summary = run_ingestion(settings.input_root, db, settings.output_dir)
    print(summary)


if __name__ == '__main__':
    main()
