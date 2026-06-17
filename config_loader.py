import json


CONFIG_FILE = "dashboard_config.json"


def load_dashboard_config(path: str = CONFIG_FILE) -> dict:
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def get_reports(config: dict, include_disabled: bool = False) -> list[dict]:
    reports = config.get("reports", [])
    if include_disabled:
        return reports
    return [report for report in reports if report.get("enabled", True)]


def get_report_by_id(config: dict, report_id: str | None) -> dict | None:
    if not report_id:
        return None
    for report in config.get("reports", []):
        if report.get("id") == report_id:
            return report
    return None


def get_default_report(config: dict) -> dict | None:
    default_report = get_report_by_id(config, config.get("default_report_id"))
    if default_report and default_report.get("enabled", True):
        return default_report

    reports = get_reports(config)
    return reports[0] if reports else None


def get_collectable_reports(config: dict) -> list[dict]:
    collectable = []
    for report in get_reports(config):
        if not report.get("collect_enabled", True):
            continue
        if not report.get("video_url"):
            continue
        collectable.append(report)
    return collectable


def resolve_prompt_file(report: dict, config: dict) -> str:
    return report.get("prompt_file") or config.get("default_prompt_file") or "prompt_base.txt"


def data_file_for_report(report: dict) -> str:
    return f"analyzed_comments_{report['start_date']}.csv"


def stats_file_for_report(report: dict) -> str:
    return f"video_stats_{report['start_date']}.csv"
