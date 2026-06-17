import os
import re
import json
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv(dotenv_path=".env")

def extract_video_id(url: str) -> str:
    """유튜브 URL에서 video_id를 추출합니다."""
    patterns = [
        r"(?:v=|\/)([0-9A-Za-z_-]{11}).*",
        r"youtu\.be\/([0-9A-Za-z_-]{11})"
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return url  # 이미 ID 형태인 경우

def fetch_youtube_comments(video_url: str, max_results: int = None) -> list:
    """유튜브 영상의 댓글을 수집합니다. max_results가 없으면 모든 댓글을 수집합니다."""
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        raise ValueError("YOUTUBE_API_KEY가 .env 파일에 설정되어 있지 않습니다.")

    video_id = extract_video_id(video_url)
    
    comments = []
    next_page_token = None

    def get_json(endpoint: str, params: dict) -> dict:
        query = urllib.parse.urlencode(params)
        full_url = f"https://www.googleapis.com/youtube/v3/{endpoint}?{query}"
        with urllib.request.urlopen(full_url) as response:
            return json.load(response)
    
    while True:
        params = {
            "part": "snippet",
            "videoId": video_id,
            "maxResults": 100,  # 한 페이지당 최대 100개씩 호출
            "textFormat": "plainText",
            "key": api_key,
        }
        if next_page_token:
            params["pageToken"] = next_page_token

        response = get_json("commentThreads", params)
        
        for item in response['items']:
            comment = item['snippet']['topLevelComment']['snippet']['textDisplay']
            comments.append(comment)
            
        next_page_token = response.get('nextPageToken')
        
        # 다음 페이지가 없으면(댓글을 끝까지 다 가져왔으면) 루프 종료
        if not next_page_token:
            break
            
        # 만약 최대 개수 제한이 설정되어 있고, 그 수를 넘었다면 종료
        if max_results and len(comments) >= max_results:
            comments = comments[:max_results]
            break
            
    return comments

def fetch_video_stats(video_url: str) -> dict:
    """영상의 현재 조회수, 좋아요 수 등 통계를 가져옵니다."""
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        return None
        
    video_id = extract_video_id(video_url)

    def get_json(endpoint: str, params: dict) -> dict:
        query = urllib.parse.urlencode(params)
        full_url = f"https://www.googleapis.com/youtube/v3/{endpoint}?{query}"
        with urllib.request.urlopen(full_url) as response:
            return json.load(response)
    
    response = get_json("videos", {"part": "statistics,snippet", "id": video_id, "key": api_key})
    
    if not response['items']:
        return None
        
    item = response['items'][0]
    stats = item['statistics']

    kst_now = datetime.utcnow() + timedelta(hours=9)
    
    return {
        "title": item['snippet']['title'],
        "view_count": int(stats.get('viewCount', 0)),
        "like_count": int(stats.get('likeCount', 0)),
        "comment_count": int(stats.get('commentCount', 0)),
        "timestamp": kst_now.strftime('%Y-%m-%d %H:%M:%S')
    }
