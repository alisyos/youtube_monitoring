# 국민연금 이사장 유튜브 여론 모니터링 대시보드

**🔗 [실시간 대시보드 바로가기](https://roy8in.github.io/youtube-comment-monitoring/)**

여러 개의 유튜브 영상을 한 번에 추적하고, 새 댓글만 AI로 분석해 대표 페이지와 영상별 탭 대시보드로 보여주는 정적 모니터링 시스템입니다.

## 주요 구성

- 대표 페이지: 전체 영상의 감성 분포, 분류별 여론, 기본 통계 비교
- 영상별 탭: 조회수 추이, 감성 분포, 분류별 여론, 전체 댓글 분석 결과
- 멀티 영상 수집: GitHub Actions 한 번 실행으로 여러 영상의 통계와 댓글을 순회 수집
- 증분 분석: 이미 저장된 댓글은 건너뛰고 새 댓글만 OpenRouter로 분석

## 설정 파일 구조

모든 영상 메타데이터는 [dashboard_config.json](/Users/binmoojin/work/youtube-comment-monitoring/dashboard_config.json)에서 관리합니다.

```json
{
  "dashboard_title": "국민연금 이사장 유튜브 여론 모니터링",
  "default_report_id": "sampro_ceo_ep1_20260423",
  "default_prompt_file": "prompt_base.txt",
  "reports": [
    {
      "id": "sampro_ceo_ep1_20260423",
      "tab_label": "삼프로TV",
      "video_title": "영상 제목",
      "video_url": "https://youtu.be/...",
      "start_date": "20260423",
      "video_start_at": "2026-04-23 19:00:00",
      "prompt_file": "prompt_20260423.txt",
      "enabled": true,
      "collect_enabled": true
    }
  ]
}
```

## 필드 설명

- `id`: 내부 식별자
- `tab_label`: 탭에 표시할 이름
- `video_title`: 화면에 표시할 제목
- `video_url`: 실제 유튜브 URL
- `start_date`: 파일명 기준 키
- `video_start_at`: 영상 시작 시각. `video_stats_<start_date>.csv`의 기준 시작점으로 사용
- `prompt_file`: 영상 전용 프롬프트 파일. 없으면 `default_prompt_file` 사용
- `enabled`: 대시보드에 표시할지 여부
- `collect_enabled`: GitHub Actions 수집 대상 포함 여부

## 새 영상 추가 방법

1. [dashboard_config.json](/Users/binmoojin/work/youtube-comment-monitoring/dashboard_config.json)에 `reports` 항목을 추가합니다.
2. 아래 값을 채웁니다.
   - `video_url`
   - `tab_label`
   - `video_title`
   - `start_date`
   - `video_start_at`
3. 프롬프트가 기존 영상들과 크게 다르지 않으면 `prompt_file`을 생략하고 `prompt_base.txt`를 그대로 사용합니다.
4. 영상별 분류 기준이 필요하면 `prompt_<start_date>.txt`를 새로 만들고 `prompt_file`에 연결합니다.
5. `collect_enabled: true`로 두면 GitHub Actions가 다음 실행부터 자동 수집합니다.

## 파일 규칙

- 댓글 분석 결과: `analyzed_comments_<start_date>.csv`
- 영상 통계: `video_stats_<start_date>.csv`
- 영상 전용 프롬프트: `prompt_<start_date>.txt`
- 공통 프롬프트: `prompt_base.txt`

## GitHub Actions 동작 방식

[.github/workflows/update_data.yml](/Users/binmoojin/work/youtube-comment-monitoring/.github/workflows/update_data.yml)은 정해진 주기마다 [update_job.py](/Users/binmoojin/work/youtube-comment-monitoring/update_job.py)를 실행합니다.

실행 흐름은 아래와 같습니다.

1. `dashboard_config.json`의 `reports` 목록을 읽습니다.
2. `collect_enabled: true`인 영상을 순서대로 처리합니다.
3. 각 영상마다
   - 최신 조회수, 좋아요, 댓글 수를 수집합니다.
   - `video_stats_<start_date>.csv`에 새 행을 추가합니다.
   - 댓글을 수집합니다.
   - 기존 CSV와 비교해 새 댓글만 추립니다.
   - 새 댓글만 OpenRouter로 감성/주제 분석합니다.
   - 결과를 `analyzed_comments_<start_date>.csv` 뒤에 추가합니다.

즉, GitHub Actions 한 번 실행 시 여러 영상이 모두 갱신되고, OpenRouter는 새 댓글에 대해서만 호출됩니다.

## 수동 실행

```bash
python update_job.py
```

특정 영상 CSV를 다시 분석하려면:

```bash
python reanalyze_existing_comments.py --report-id sampro_ceo_ep1_20260423
```

## 필요한 시크릿

GitHub Actions와 로컬 실행 모두 아래 값이 필요합니다.

- `YOUTUBE_API_KEY`
- `OPENROUTER_API_KEY`

선택 환경 변수:

- `OPENROUTER_MODEL`
- `OPENROUTER_BATCH_SIZE`
- `OPENROUTER_TIMEOUT`

## 참고

- `video_start_at`은 실제 게시 시각에 맞게 수동 보정할수록 조회수 추이 해석이 더 정확해집니다.
- 댓글 수가 아주 적은 영상은 대표 페이지에서 표본이 적다는 표시가 함께 보입니다.
- 기존 댓글 분류 체계가 영상별로 달라도 대시보드는 그대로 집계해 보여줍니다.
