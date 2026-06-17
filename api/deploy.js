// 대시보드 "수동 업데이트" 버튼이 호출하는 엔드포인트.
// GitHub repository_dispatch를 서버 측 토큰으로 트리거해 데이터 수집 워크플로를 실행시킨다.
// 토큰(GH_DISPATCH_TOKEN)은 Vercel 환경변수로만 보관하며 클라이언트에 노출하지 않는다.

const GH_REPO = process.env.GH_REPO || 'alisyos/youtube_monitoring';
const EVENT_TYPE = 'manual-deploy';

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    res.setHeader('Allow', 'POST');
    return res.status(405).json({ ok: false, error: 'Method Not Allowed' });
  }

  const token = process.env.GH_DISPATCH_TOKEN;
  if (!token) {
    return res.status(500).json({ ok: false, error: 'GH_DISPATCH_TOKEN is not configured' });
  }

  try {
    const ghRes = await fetch(`https://api.github.com/repos/${GH_REPO}/dispatches`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
        'Content-Type': 'application/json',
        'User-Agent': 'youtube-comment-monitoring-dashboard',
      },
      body: JSON.stringify({ event_type: EVENT_TYPE }),
    });

    // GitHub은 성공 시 204 No Content를 반환한다.
    if (ghRes.status === 204) {
      return res.status(200).json({ ok: true });
    }

    const detail = await ghRes.text();
    return res.status(502).json({ ok: false, status: ghRes.status, error: detail });
  } catch (err) {
    return res.status(500).json({ ok: false, error: String(err) });
  }
}
