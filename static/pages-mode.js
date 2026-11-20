(function enableGitHubPagesSnapshot() {
  const nativeFetch = window.fetch.bind(window);
  let snapshotPromise;

  function snapshot() {
    if (!snapshotPromise) {
      snapshotPromise = nativeFetch('./snapshot.json', { cache: 'no-store' }).then(response => {
        if (!response.ok) throw new Error('线上数据快照加载失败');
        return response.json();
      });
    }
    return snapshotPromise;
  }

  function filterRows(rows, params) {
    const q = (params.get('q') || '').toLowerCase();
    return (rows || []).filter(row => {
      if (params.get('sector') && row.sector !== params.get('sector')) return false;
      if (params.get('evidence_type') && row.evidence_type !== params.get('evidence_type')) return false;
      if (params.get('source_type') && row.source_type !== params.get('source_type')) return false;
      if (params.get('asset_level') && row.asset_level !== params.get('asset_level')) return false;
      if (params.get('decision_status') && row.decision_status !== params.get('decision_status')) return false;
      if (q && !`${row.title || ''} ${row.summary || ''} ${row.region || ''}`.toLowerCase().includes(q)) return false;
      return true;
    });
  }

  function jsonResponse(value, status = 200) {
    return new Response(JSON.stringify(value), {
      status,
      headers: { 'Content-Type': 'application/json; charset=utf-8' },
    });
  }

  window.fetch = async function pagesFetch(input, options = {}) {
    const url = new URL(typeof input === 'string' ? input : input.url, window.location.href);
    if (!url.pathname.startsWith('/api/')) return nativeFetch(input, options);
    if ((options.method || 'GET').toUpperCase() !== 'GET') {
      return jsonResponse({ message: 'GitHub 在线版为只读快照，请在本机后台提交或更新资讯。' }, 405);
    }

    const data = await snapshot();
    const path = url.pathname;
    if (path === '/api/meta') return jsonResponse(data.meta);
    if (path === '/api/dashboard') return jsonResponse(data.radar_dashboard);
    if (path === '/api/intelligence-dashboard') return jsonResponse(data.dashboard);
    if (path === '/api/ingestion-status') return jsonResponse(data.ingestion_status);
    if (path === '/api/company-profile') return jsonResponse(data.company_profile);
    if (path === '/api/audit') return jsonResponse(data.audit);
    if (path === '/api/sources') return jsonResponse(data.sources);
    if (path === '/api/update-rules') return jsonResponse(data.update_rules);
    if (path === '/api/signals') return jsonResponse(filterRows(data.signals, url.searchParams));
    if (path === '/api/opportunities') return jsonResponse(filterRows(data.opportunities, url.searchParams));
    if (path.startsWith('/api/opportunities/')) {
      const id = Number(path.split('/').pop());
      return jsonResponse(data.opportunities.find(row => Number(row.id) === id) || { message: '未找到项目' }, 200);
    }
    return jsonResponse({ message: '该接口未包含在线快照中。' }, 404);
  };

  window.addEventListener('DOMContentLoaded', () => {
    const banner = document.createElement('div');
    banner.className = 'pages-readonly-banner';
    banner.innerHTML = '<b>GitHub 在线只读版</b><span>展示最近一次发布的数据快照；提交资讯、DeepSeek 和自动检测请使用后台服务。</span>';
    document.body.prepend(banner);
  });
})();
