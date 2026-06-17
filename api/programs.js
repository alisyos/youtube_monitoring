// 대시보드 "프로그램 관리"(추가/삭제)가 호출하는 엔드포인트.
// 비밀번호(ADMIN_PASSWORD)로 보호하며, GitHub Contents API로 dashboard_config.json을
// 읽고 다시 커밋한다. 토큰(GH_DISPATCH_TOKEN)·비밀번호는 서버 환경변수로만 보관한다.

const GH_REPO = process.env.GH_REPO || 'alisyos/youtube_monitoring';
const CONFIG_PATH = 'dashboard_config.json';
const EVENT_TYPE = 'manual-deploy';

const GH_HEADERS = (token) => ({
  Authorization: `Bearer ${token}`,
  Accept: 'application/vnd.github+json',
  'X-GitHub-Api-Version': '2022-11-28',
  'Content-Type': 'application/json',
  'User-Agent': 'youtube-comment-monitoring-dashboard',
});

// 입력 비밀번호와 환경변수 비밀번호를 길이 의존성을 낮춰 비교한다.
function passwordOk(input) {
  const expected = process.env.ADMIN_PASSWORD || '';
  if (!expected) return false;
  const a = String(input || '');
  if (a.length !== expected.length) return false;
  let diff = 0;
  for (let i = 0; i < expected.length; i++) diff |= a.charCodeAt(i) ^ expected.charCodeAt(i);
  return diff === 0;
}

function extractVideoId(url) {
  if (!url) return null;
  const m = String(url).match(/(?:youtu\.be\/|v=|\/shorts\/|\/embed\/)([A-Za-z0-9_-]{11})/);
  return m ? m[1] : null;
}

// KST(UTC+9) 기준 현재 시각
function kstNow() {
  const now = new Date(Date.now() + 9 * 60 * 60 * 1000);
  const p = (n) => String(n).padStart(2, '0');
  const ymd = `${now.getUTCFullYear()}${p(now.getUTCMonth() + 1)}${p(now.getUTCDate())}`;
  const full = `${now.getUTCFullYear()}-${p(now.getUTCMonth() + 1)}-${p(now.getUTCDate())} ${p(now.getUTCHours())}:${p(now.getUTCMinutes())}:${p(now.getUTCSeconds())}`;
  return { ymd, full };
}

async function fetchOEmbedTitle(videoUrl) {
  try {
    const res = await fetch(`https://www.youtube.com/oembed?url=${encodeURIComponent(videoUrl)}&format=json`);
    if (!res.ok) return null;
    const data = await res.json();
    return data && data.title ? data.title : null;
  } catch {
    return null;
  }
}

async function getConfig(token) {
  const res = await fetch(`https://api.github.com/repos/${GH_REPO}/contents/${CONFIG_PATH}`, {
    headers: GH_HEADERS(token),
  });
  if (!res.ok) throw new Error(`config 읽기 실패 (HTTP ${res.status})`);
  const data = await res.json();
  const json = JSON.parse(Buffer.from(data.content, 'base64').toString('utf-8'));
  return { config: json, sha: data.sha };
}

async function putConfig(token, config, sha, message) {
  const content = Buffer.from(JSON.stringify(config, null, 2) + '\n', 'utf-8').toString('base64');
  const res = await fetch(`https://api.github.com/repos/${GH_REPO}/contents/${CONFIG_PATH}`, {
    method: 'PUT',
    headers: GH_HEADERS(token),
    body: JSON.stringify({ message, content, sha }),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`config 커밋 실패 (HTTP ${res.status}): ${detail}`);
  }
}

async function triggerCollection(token) {
  try {
    await fetch(`https://api.github.com/repos/${GH_REPO}/dispatches`, {
      method: 'POST',
      headers: GH_HEADERS(token),
      body: JSON.stringify({ event_type: EVENT_TYPE }),
    });
  } catch {
    // 수집 트리거 실패는 치명적이지 않음(다음 정시 cron이 처리).
  }
}

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    res.setHeader('Allow', 'POST');
    return res.status(405).json({ ok: false, error: 'Method Not Allowed' });
  }

  const body = typeof req.body === 'string' ? JSON.parse(req.body || '{}') : (req.body || {});
  const { action, password } = body;

  if (!passwordOk(password)) {
    return res.status(401).json({ ok: false, error: '비밀번호가 올바르지 않습니다.' });
  }

  const token = process.env.GH_DISPATCH_TOKEN;
  if (!token) {
    return res.status(500).json({ ok: false, error: 'GH_DISPATCH_TOKEN is not configured' });
  }

  try {
    if (action === 'add') {
      const videoUrl = (body.video_url || '').trim();
      const tabLabel = (body.tab_label || '').trim();
      if (!videoUrl || !tabLabel) {
        return res.status(400).json({ ok: false, error: 'video_url과 tab_label이 필요합니다.' });
      }
      const videoId = extractVideoId(videoUrl);
      if (!videoId) {
        return res.status(400).json({ ok: false, error: '유효한 YouTube URL이 아닙니다.' });
      }

      const { config, sha } = await getConfig(token);
      const reports = config.reports || (config.reports = []);

      // start_date 고유화 (동일 날짜 충돌 방지)
      const { ymd, full } = kstNow();
      const used = new Set(reports.map((r) => r.start_date));
      let startDate = ymd;
      let n = 2;
      while (used.has(startDate)) startDate = `${ymd}-${n++}`;

      // id 고유화
      const usedIds = new Set(reports.map((r) => r.id));
      let id = `${videoId}_${startDate}`;
      let k = 2;
      while (usedIds.has(id)) id = `${videoId}_${startDate}-${k++}`;

      const title = (await fetchOEmbedTitle(videoUrl)) || tabLabel;

      const report = {
        id,
        tab_label: tabLabel,
        video_title: title,
        video_url: videoUrl,
        start_date: startDate,
        video_start_at: full,
        enabled: true,
        collect_enabled: true,
      };
      reports.push(report);

      await putConfig(token, config, sha, `Add program: ${tabLabel}`);
      await triggerCollection(token);
      return res.status(200).json({ ok: true, report });
    }

    if (action === 'delete') {
      const id = (body.id || '').trim();
      if (!id) return res.status(400).json({ ok: false, error: 'id가 필요합니다.' });

      const { config, sha } = await getConfig(token);
      const reports = config.reports || [];
      const next = reports.filter((r) => r.id !== id);
      if (next.length === reports.length) {
        return res.status(404).json({ ok: false, error: '해당 프로그램을 찾을 수 없습니다.' });
      }
      config.reports = next;

      // 삭제 대상이 기본 리포트였다면 다른 리포트로 교체
      if (config.default_report_id === id) {
        config.default_report_id = next.length ? next[next.length - 1].id : '';
      }

      await putConfig(token, config, sha, `Delete program: ${id}`);
      return res.status(200).json({ ok: true });
    }

    return res.status(400).json({ ok: false, error: "action은 'add' 또는 'delete'여야 합니다." });
  } catch (err) {
    return res.status(502).json({ ok: false, error: String(err.message || err) });
  }
}
