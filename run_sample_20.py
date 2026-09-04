"""Run local batch archiver for 20 sample items and generate detailed inspection manifest."""
from batch_archive_fulltext_and_screenshots import run_full_archive_and_screenshots

if __name__ == "__main__":
    run_full_archive_and_screenshots(max_items=20)
