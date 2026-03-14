const express = require('express');
const cors = require('cors');
const fetch = require('node-fetch');

const app = express();
const PORT = process.env.PORT || 3000;

app.use(cors());
app.use(express.json());

// ═══════════════════════════════════════════════════════════════════
//  Health Check
// ═══════════════════════════════════════════════════════════════════
app.get('/api/health', (req, res) => {
  res.json({ status: 'ok', service: 'osint-tools', version: '1.0.0' });
});

// ═══════════════════════════════════════════════════════════════════
//  1. URLScan.io — Scan & analyze a website
// ═══════════════════════════════════════════════════════════════════
app.get('/api/urlscan', async (req, res) => {
  const { url } = req.query;
  if (!url) return res.status(400).json({ error: 'Missing required parameter: url' });

  try {
    // Search for existing scans first (no API key needed)
    const searchResp = await fetch(
      `https://urlscan.io/api/v1/search/?q=domain:${encodeURIComponent(url.replace(/^https?:\/\//, '').replace(/\/.*$/, ''))}&size=5`,
      { headers: { 'Accept': 'application/json' }, timeout: 15000 }
    );

    if (!searchResp.ok) {
      return res.status(searchResp.status).json({ error: `URLScan API error: ${searchResp.status}` });
    }

    const data = await searchResp.json();
    const results = (data.results || []).map(r => ({
      url: r.page?.url,
      domain: r.page?.domain,
      ip: r.page?.ip,
      server: r.page?.server,
      country: r.page?.country,
      asn: r.page?.asn,
      asnname: r.page?.asnname,
      status: r.page?.status,
      mimeType: r.page?.mimeType,
      screenshot: r.screenshot,
      reportUrl: r.result,
      time: r.task?.time,
      visibility: r.task?.visibility,
      tags: r.task?.tags || [],
      verdicts: r.verdicts || {},
    }));

    res.json({
      total: data.total || results.length,
      results,
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ═══════════════════════════════════════════════════════════════════
//  2. Subdomain Enumeration via crt.sh (Certificate Transparency)
// ═══════════════════════════════════════════════════════════════════
app.get('/api/subdomains', async (req, res) => {
  const { domain } = req.query;
  if (!domain) return res.status(400).json({ error: 'Missing required parameter: domain' });

  const cleanDomain = domain.replace(/^https?:\/\//, '').replace(/\/.*$/, '');

  try {
    const resp = await fetch(
      `https://crt.sh/?q=%25.${encodeURIComponent(cleanDomain)}&output=json`,
      { timeout: 20000 }
    );

    if (!resp.ok) {
      return res.status(resp.status).json({ error: `crt.sh error: ${resp.status}` });
    }

    const text = await resp.text();
    if (!text || text.trim() === '') {
      return res.json({ domain: cleanDomain, total: 0, subdomains: [], certificates: 0 });
    }

    let data;
    try {
      data = JSON.parse(text);
    } catch (e) {
      return res.json({ domain: cleanDomain, total: 0, subdomains: [], certificates: 0, note: 'No certificate transparency data found' });
    }

    // Extract unique subdomains
    const subdomainSet = new Set();
    data.forEach(entry => {
      const names = (entry.name_value || '').split('\n');
      names.forEach(n => {
        const clean = n.trim().toLowerCase();
        if (clean && clean.endsWith(cleanDomain.toLowerCase())) {
          subdomainSet.add(clean);
        }
      });
    });

    const subdomains = [...subdomainSet].sort();

    res.json({
      domain: cleanDomain,
      total: subdomains.length,
      subdomains,
      certificates: data.length,
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ═══════════════════════════════════════════════════════════════════
//  3. AbuseIPDB — Check if an IP is reported for abuse
// ═══════════════════════════════════════════════════════════════════
app.get('/api/abuseipdb', async (req, res) => {
  const { ip } = req.query;
  if (!ip) return res.status(400).json({ error: 'Missing required parameter: ip' });

  const apiKey = process.env.ABUSEIPDB_API_KEY;
  if (!apiKey) {
    return res.status(500).json({ error: 'AbuseIPDB API key not configured' });
  }

  try {
    const resp = await fetch(
      `https://api.abuseipdb.com/api/v2/check?ipAddress=${encodeURIComponent(ip)}&maxAgeInDays=90&verbose=true`,
      {
        headers: {
          'Key': apiKey,
          'Accept': 'application/json',
        },
        timeout: 15000,
      }
    );

    if (!resp.ok) {
      const errBody = await resp.text();
      return res.status(resp.status).json({ error: `AbuseIPDB error: ${resp.status}`, details: errBody });
    }

    const data = await resp.json();
    const d = data.data || {};

    res.json({
      ip: d.ipAddress,
      isPublic: d.isPublic,
      abuseConfidenceScore: d.abuseConfidenceScore,
      countryCode: d.countryCode,
      usageType: d.usageType,
      isp: d.isp,
      domain: d.domain,
      isTor: d.isTor,
      totalReports: d.totalReports,
      numDistinctUsers: d.numDistinctUsers,
      lastReportedAt: d.lastReportedAt,
      isWhitelisted: d.isWhitelisted,
      reports: (d.reports || []).slice(0, 10).map(r => ({
        reportedAt: r.reportedAt,
        comment: r.comment,
        categories: r.categories,
        reporterCountryCode: r.reporterCountryCode,
      })),
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ═══════════════════════════════════════════════════════════════════
//  4. Wayback Machine — Website history snapshots
// ═══════════════════════════════════════════════════════════════════
app.get('/api/wayback', async (req, res) => {
  const { url } = req.query;
  if (!url) return res.status(400).json({ error: 'Missing required parameter: url' });

  const cleanUrl = url.replace(/^https?:\/\//, '').replace(/\/+$/, '');

  try {
    // Get available snapshots via CDX API
    const cdxResp = await fetch(
      `https://web.archive.org/cdx/search/cdx?url=${encodeURIComponent(cleanUrl)}&output=json&limit=50&fl=timestamp,original,statuscode,mimetype,length&collapse=timestamp:6`,
      { timeout: 20000 }
    );

    if (!cdxResp.ok) {
      return res.status(cdxResp.status).json({ error: `Wayback CDX error: ${cdxResp.status}` });
    }

    const data = await cdxResp.json();

    // First row is headers, rest is data
    const headers = data[0] || [];
    const snapshots = data.slice(1).map(row => {
      const obj = {};
      headers.forEach((h, i) => { obj[h] = row[i]; });
      // Format timestamp to readable date
      if (obj.timestamp) {
        const ts = obj.timestamp;
        obj.date = `${ts.slice(0,4)}-${ts.slice(4,6)}-${ts.slice(6,8)}`;
        obj.archiveUrl = `https://web.archive.org/web/${ts}/${obj.original || cleanUrl}`;
      }
      return obj;
    });

    // Get first and last capture info
    const firstCapture = snapshots.length > 0 ? snapshots[snapshots.length - 1] : null;
    const lastCapture = snapshots.length > 0 ? snapshots[0] : null;

    // Also get availability
    const availResp = await fetch(
      `https://archive.org/wayback/available?url=${encodeURIComponent(cleanUrl)}`,
      { timeout: 10000 }
    );
    const availData = availResp.ok ? await availResp.json() : {};

    res.json({
      url: cleanUrl,
      totalSnapshots: snapshots.length,
      firstCapture: firstCapture ? firstCapture.date : null,
      lastCapture: lastCapture ? lastCapture.date : null,
      available: !!(availData.archived_snapshots && availData.archived_snapshots.closest),
      closestSnapshot: availData.archived_snapshots?.closest || null,
      snapshots: snapshots.reverse(),
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ═══════════════════════════════════════════════════════════════════
//  5. Username Search — Check username across platforms
// ═══════════════════════════════════════════════════════════════════

// Platform definitions for username checking
const PLATFORMS = [
  { name: 'GitHub', url: 'https://github.com/{username}', errorType: 'status_code' },
  { name: 'Twitter/X', url: 'https://x.com/{username}', errorType: 'status_code' },
  { name: 'Instagram', url: 'https://www.instagram.com/{username}/', errorType: 'status_code' },
  { name: 'Reddit', url: 'https://www.reddit.com/user/{username}', errorType: 'status_code' },
  { name: 'YouTube', url: 'https://www.youtube.com/@{username}', errorType: 'status_code' },
  { name: 'TikTok', url: 'https://www.tiktok.com/@{username}', errorType: 'status_code' },
  { name: 'Pinterest', url: 'https://www.pinterest.com/{username}/', errorType: 'status_code' },
  { name: 'GitLab', url: 'https://gitlab.com/{username}', errorType: 'status_code' },
  { name: 'Medium', url: 'https://medium.com/@{username}', errorType: 'status_code' },
  { name: 'Dev.to', url: 'https://dev.to/{username}', errorType: 'status_code' },
  { name: 'Twitch', url: 'https://www.twitch.tv/{username}', errorType: 'status_code' },
  { name: 'Steam', url: 'https://steamcommunity.com/id/{username}', errorType: 'status_code' },
  { name: 'Keybase', url: 'https://keybase.io/{username}', errorType: 'status_code' },
  { name: 'HackerNews', url: 'https://news.ycombinator.com/user?id={username}', errorType: 'status_code' },
  { name: 'Replit', url: 'https://replit.com/@{username}', errorType: 'status_code' },
  { name: 'NPM', url: 'https://www.npmjs.com/~{username}', errorType: 'status_code' },
  { name: 'PyPI', url: 'https://pypi.org/user/{username}/', errorType: 'status_code' },
  { name: 'Docker Hub', url: 'https://hub.docker.com/u/{username}', errorType: 'status_code' },
  { name: 'Gravatar', url: 'https://en.gravatar.com/{username}', errorType: 'status_code' },
  { name: 'About.me', url: 'https://about.me/{username}', errorType: 'status_code' },
];

async function checkPlatform(platform, username) {
  const url = platform.url.replace('{username}', username);
  try {
    const resp = await fetch(url, {
      method: 'HEAD',
      redirect: 'follow',
      timeout: 8000,
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
      },
    });
    return {
      platform: platform.name,
      url,
      found: resp.status >= 200 && resp.status < 400,
      status: resp.status,
    };
  } catch (err) {
    return {
      platform: platform.name,
      url,
      found: false,
      status: 0,
      error: 'timeout/unreachable',
    };
  }
}

app.get('/api/username', async (req, res) => {
  const { username } = req.query;
  if (!username) return res.status(400).json({ error: 'Missing required parameter: username' });

  // Sanitize
  const clean = username.trim().replace(/[^a-zA-Z0-9_\-\.]/g, '');
  if (!clean) return res.status(400).json({ error: 'Invalid username' });

  try {
    const results = await Promise.allSettled(
      PLATFORMS.map(p => checkPlatform(p, clean))
    );

    const platforms = results
      .filter(r => r.status === 'fulfilled')
      .map(r => r.value);

    const found = platforms.filter(p => p.found);
    const notFound = platforms.filter(p => !p.found);

    res.json({
      username: clean,
      platformsChecked: platforms.length,
      found: found.length,
      notFound: notFound.length,
      results: platforms,
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ═══════════════════════════════════════════════════════════════════
//  Start Server
// ═══════════════════════════════════════════════════════════════════
app.listen(PORT, '0.0.0.0', () => {
  console.log(`OSINT Tools API running on port ${PORT}`);
});
