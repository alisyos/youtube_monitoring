import os
import pandas as pd
from comment_collector import fetch_youtube_comments, fetch_video_stats
from comment_analyzer import (
    analyze_comments_with_llm,
    normalize_category_label,
    normalize_sentiment_label,
)
from config_loader import (
    get_collectable_reports,
    load_dashboard_config,
    resolve_prompt_file,
    data_file_for_report,
    stats_file_for_report,
)


def normalize(text):
    return "".join(text.split()) if isinstance(text, str) else ""


def build_initial_stats_frame(report, title):
    columns = ["timestamp", "view_count", "like_count", "comment_count", "title"]
    start_at = report.get("video_start_at")
    if not start_at:
        return pd.DataFrame(columns=columns)

    return pd.DataFrame(
        [
            {
                "timestamp": start_at,
                "view_count": 0,
                "like_count": 0,
                "comment_count": 0,
                "title": title,
            }
        ],
        columns=columns,
    )


def run_update_for_report(report, config):
    report_id = report.get("id", report.get("start_date"))
    video_url = report["video_url"]
    data_file = data_file_for_report(report)
    stats_file = stats_file_for_report(report)
    prompt_file = resolve_prompt_file(report, config)

    print(f"[{report_id}] 업데이트 시작")

    # 1. 영상 통계 업데이트
    stats = fetch_video_stats(video_url)
    if stats:
        if os.path.exists(stats_file):
            df_stats = pd.read_csv(stats_file)
        else:
            df_stats = build_initial_stats_frame(report, stats.get("title") or report.get("video_title", ""))

        new_row = pd.DataFrame([stats])
        df_stats = pd.concat([df_stats, new_row], ignore_index=True)
        df_stats.to_csv(stats_file, index=False)
        print(f"[{report_id}] 영상 통계 업데이트 완료.")
    else:
        print(f"[{report_id}] 영상 통계를 가져오지 못했습니다.")

    # 2. 신규 댓글 수집 및 LLM 분석
    raw_comments = fetch_youtube_comments(video_url)

    if os.path.exists(data_file):
        existing_df = pd.read_csv(data_file)
    else:
        existing_df = pd.DataFrame(columns=["text", "sentiment", "category", "keyword"])
        existing_df.to_csv(data_file, index=False)

    existing_normalized = set(normalize(text) for text in existing_df["text"].tolist()) if not existing_df.empty else set()

    # 중복되지 않은 신규 댓글만 선별 (공백 무시 기준)
    new_comments = []
    seen_in_batch = set()
    for comment in raw_comments:
        normalized_comment = normalize(comment)
        if normalized_comment not in existing_normalized and normalized_comment not in seen_in_batch:
            new_comments.append(comment)
            seen_in_batch.add(normalized_comment)

    if new_comments and os.path.exists(prompt_file):
        with open(prompt_file, "r", encoding="utf-8") as file:
            prompt_template = file.read()

        analyzed_list = analyze_comments_with_llm(new_comments, prompt_template)
        if analyzed_list:
            # LLM이 반환한 text가 변형되었을 수 있으므로, 원본 new_comments와 순서대로 매칭하여 저장
            # (analyze_comments_with_llm이 입력 리스트와 동일한 순서/개수를 반환한다고 가정)
            final_data = []
            for i, result in enumerate(analyzed_list):
                if i < len(new_comments):
                    # 결과 딕셔너리에서 text만 원본으로 교체
                    item = result.copy()
                    item["text"] = new_comments[i]
                    item["sentiment"] = normalize_sentiment_label(item.get("sentiment"))
                    item["category"] = normalize_category_label(item.get("category"))
                    final_data.append(item)

            new_df = pd.DataFrame(final_data)
            updated_df = pd.concat([existing_df, new_df], ignore_index=True)
            updated_df.to_csv(data_file, index=False)
            print(f"[{report_id}] 새 댓글 {len(new_comments)}개 분석 및 저장 완료.")
    elif new_comments:
        print(f"[{report_id}] 프롬프트 파일이 없어 새 댓글 분석을 건너뜁니다: {prompt_file}")
    else:
        print(f"[{report_id}] 분석할 새로운 댓글이 없습니다.")


if __name__ == "__main__":
    dashboard_config = load_dashboard_config()
    reports = get_collectable_reports(dashboard_config)
    if not reports:
        print("수집 대상 영상이 없습니다. dashboard_config.json의 reports 설정을 확인하세요.")
    for report_item in reports:
        run_update_for_report(report_item, dashboard_config)
