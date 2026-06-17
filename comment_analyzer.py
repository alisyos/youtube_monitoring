import json
import os

from dotenv import load_dotenv

load_dotenv()


CATEGORY_ALIAS_MAP = {
    "국민연금 조직": "국민연금 조직",
    "운용성과": "운용성과",
    "기금수익": "운용성과",
    "투자전략": "투자전략",
    "국내주식": "투자전략",
    "해외투자": "투자전략",
    "주택투자": "투자전략",
    "연금제도": "연금제도",
    "퇴직연금": "퇴직연금",
    "세대형평": "세대형평",
    "정부개입": "정부개입·거버넌스",
    "주주권행사": "정부개입·거버넌스",
    "정부개입·거버넌스": "정부개입·거버넌스",
    "지역발전": "지역발전",
    "전북금융생태계": "지역발전",
    "기타": "기타",
}


def normalize_sentiment_label(sentiment: str | None) -> str:
    value = (sentiment or "").strip()
    if value == "광고":
        return "광고"
    if value == "긍정":
        return "긍정"
    if value == "부정":
        return "부정"
    if value == "중립":
        return "중립"
    if value == "기타":
        return "중립"
    return "중립"


def normalize_category_label(category: str | None) -> str:
    value = (category or "").strip()
    return CATEGORY_ALIAS_MAP.get(value, "기타")


def _build_prompt(prompt_template: str, comments: list) -> str:
    strict_rules = """

[중요 제약]
- 입력 배열의 각 원소는 댓글 1개입니다.
- 출력 data 배열의 길이는 입력 댓글 수와 반드시 정확히 같아야 합니다.
- 입력 댓글 1개를 여러 행으로 쪼개지 마세요.
- 여러 댓글을 합치지 마세요.
- 출력 순서는 입력 순서와 반드시 같아야 합니다.
- text 값은 입력 댓글 원문과 동일한 댓글 1개를 그대로 유지하세요.
"""
    return f"{prompt_template}{strict_rules}\n\n댓글 목록: {json.dumps(comments, ensure_ascii=False)}"


def analyze_comments_with_llm(comments: list, prompt_template: str) -> list:
    """OpenRouter를 사용하여 댓글의 감성과 주요 키워드를 분석합니다."""
    if not comments:
        return []

    try:
        from openai import OpenAI
    except ModuleNotFoundError:
        print("CRITICAL ERROR: openai 패키지가 설치되어 있지 않습니다.")
        return [
            {"text": t, "sentiment": "오류", "category": "기타", "keyword": "SDK누락"}
            for t in comments
        ]

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("CRITICAL ERROR: OPENROUTER_API_KEY가 .env 파일에 없습니다.")
        return [
            {"text": t, "sentiment": "오류", "keyword": "API키누락"}
            for t in comments
        ]

    # 1. OpenRouter가 권장하는 필수 헤더 추가
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
        default_headers={
            "HTTP-Referer": "http://localhost:8501", 
            "X-Title": "NPS_PR_Dashboard"
        }
    )

    model = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
    batch_size = int(os.getenv("OPENROUTER_BATCH_SIZE", "10"))
    request_timeout = float(os.getenv("OPENROUTER_TIMEOUT", "60"))
    analyzed_data = []

    for i in range(0, len(comments), batch_size):
        batch = comments[i:i + batch_size]
        print(f"배치 {i // batch_size + 1}/{(len(comments) + batch_size - 1) // batch_size} 분석 중...")
        
        prompt = _build_prompt(prompt_template, batch)

        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                response_format={"type": "json_object"},  # JSON 구조 완벽 강제
                timeout=request_timeout,
            )
            
            content = response.choices[0].message.content.strip()
            result_dict = json.loads(content)  # 정규식 없이 깔끔하게 파싱!
            
            # 딕셔너리 안의 리스트를 추출
            if "data" in result_dict:
                if len(result_dict["data"]) != len(batch):
                    raise ValueError(
                        f"반환 개수 불일치: expected={len(batch)}, actual={len(result_dict['data'])}"
                    )
                normalized_batch = []
                for item in result_dict["data"]:
                    normalized_item = item.copy()
                    normalized_item["sentiment"] = normalize_sentiment_label(item.get("sentiment"))
                    normalized_item["category"] = normalize_category_label(item.get("category"))
                    normalized_batch.append(normalized_item)
                analyzed_data.extend(normalized_batch)
            else:
                raise ValueError("JSON에 'data' 키가 없습니다.")
                

        except Exception as e:
            # 2. 대시보드에서 직접 에러 종류를 확인 가능하도록 추적 로직 강화
            error_type = type(e).__name__
            print(f"배치 {i//batch_size} 분석 중 오류 발생: {e}")
            if 'content' in locals():
                print(f"Raw response: {content[:200]}")

            # 배치 응답이 어긋나면 댓글 단위로 재시도해 순서를 강제합니다.
            for text in batch:
                single_prompt = _build_prompt(prompt_template, [text])
                try:
                    response = client.chat.completions.create(
                        model=model,
                        messages=[{"role": "user", "content": single_prompt}],
                        temperature=0.1,
                        response_format={"type": "json_object"},
                        timeout=request_timeout,
                    )
                    content = response.choices[0].message.content.strip()
                    result_dict = json.loads(content)
                    if "data" not in result_dict or len(result_dict["data"]) != 1:
                        raise ValueError("단건 재시도 결과 형식 오류")
                    normalized_batch = []
                    for item in result_dict["data"]:
                        normalized_item = item.copy()
                        normalized_item["sentiment"] = normalize_sentiment_label(item.get("sentiment"))
                        normalized_item["category"] = normalize_category_label(item.get("category"))
                        normalized_batch.append(normalized_item)
                    analyzed_data.extend(normalized_batch)
                except Exception as single_error:
                    single_error_type = type(single_error).__name__
                    analyzed_data.append({
                        "text": text,
                        "sentiment": "오류",
                        "category": "기타",
                        "keyword": f"에러: {single_error_type}"
                    })

    return analyzed_data
