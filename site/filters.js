/* Shared filter bar (League / Split / Stage / Year) + client-side aggregation of dist/data/*.json.
   Default = the page's embedded Worlds data. Picking anything else loads the league files and calls the page's handler(s). */
(function () {
  var ROLES = ['Top', 'Jungle', 'Mid', 'Bot', 'Support'];
  var NAMES = { WLDs: 'Worlds', MSI: 'MSI', LCK: 'LCK', LPL: 'LPL', LEC: 'LEC', LCS: 'LCS', LCP: 'LCP', CBLOL: 'CBLOL', LCKC: 'LCK Challengers', LAS: 'LAS', LES: 'LES', LJL: 'LJL', LLA: 'LLA', PCS: 'PCS', VCS: 'VCS', TCL: 'TCL', LFL: 'LFL', NLC: 'NLC', PRM: 'Prime League', LIT: 'LIT', EM: 'EMEA Masters', EWC: 'Esports World Cup', FST: 'First Stand', CD: 'Circuit Demacia', NACL: 'NACL', AL: 'LPL Academy', LRN: 'LRN', LRS: 'LRS', WLRQ: 'Worlds Qualifiers', WSCI: 'Worlds Play-Ins', CCWS: 'CCWS', AC: 'Asia Cup', AM: 'Americas Cup', DCGI: 'DCGI', DCup: 'DCup', HC: 'Hitpoint Challengers', HLL: 'Hellenic Legends', HM: 'Hitpoint Masters', HW: 'HW', NL: 'NL', RL: 'Rift Legends', ROL: 'Roll', LPLOL: 'LPLOL', EBL: 'Esports Balkan League', KeSPA: 'KeSPA' };
  var MAJOR = ['WLDs', 'MSI', 'EWC', 'FST', 'LCK', 'LPL', 'LEC', 'LCS', 'LCP', 'CBLOL'];
  var S = { league: 'WLDs', split: 'All', stage: 'All', year: 'All' };
  try { var sv = JSON.parse(sessionStorage.getItem('lvf') || 'null'); if (sv) S = sv; } catch (e) {}
  var meta = null, cache = {}, handlers = [], bar = null, busy = 0, cur = null;
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var lname = function (id) { return id === 'ALL' ? 'All leagues' : (NAMES[id] || id) + (id === 'WLDs' ? ' 2026' : ''); };

  /* ---------- data ---------- */
  function jget(u) { return fetch(u).then(function (r) { if (!r.ok) throw new Error(u); return r.json(); }); }
  function loadMeta() { return meta ? Promise.resolve(meta) : jget('data/meta.json').then(function (m) { meta = m; uniqueCodes(); return m; }); }
  function uniqueCodes() {
    var seen = {}; meta.teams.forEach(function (t) { var c = t[1], n = 2; while (seen[c] && seen[c] !== t[0]) c = t[1] + n++; seen[c] = t[0]; t[1] = c; });
    meta.code = {}; meta.tname = {}; meta.teams.forEach(function (t, i) { meta.code[t[0]] = t[1]; meta.tname[t[1]] = t[0]; });
  }
  function loadLeague(id) { return cache[id] ? Promise.resolve(cache[id]) : jget('data/lg-' + id.replace(/[^A-Za-z0-9_-]/g, '_') + '.json').then(function (d) { return (cache[id] = d); }); }
  function isDefault() { return S.league === 'WLDs' && S.split === 'All' && S.stage === 'All' && S.year === 'All'; }

  /* a filtered dataset: arrays of games / player rows / team rows restricted to the scope, with game ids remapped */
  function slice(d, lg) {
    var G = d.games, keep = [], map = {};
    for (var i = 0; i < G.id.length; i++) {
      if (S.year !== 'All' && G.y[i] !== +S.year) continue;
      if (S.split !== 'All' && d.splitNames[G.sp[i]] !== S.split) continue;
      if (S.stage === 'Regular' && G.po[i]) continue; if (S.stage === 'Playoffs' && !G.po[i]) continue;
      map[i] = keep.length; keep.push(i);
    }
    var pick = function (blk, ids) { var o = {}, idx = []; for (var j = 0; j < blk.g.length; j++) if (map[blk.g[j]] !== undefined) idx.push(j);
      Object.keys(blk).forEach(function (k) { o[k] = idx.map(function (j) { return blk[k][j]; }); }); o.g = o.g.map(function (g) { return map[g]; }); o.n = idx.length; return o; };
    return { lg: lg, keep: keep, games: keep.map(function (i) { var r = {}; Object.keys(G).forEach(function (k) { r[k] = G[k][i]; }); r.sp = d.splitNames[G.sp[i]]; r.lg = lg; return r; }), rows: pick(d.rows), teams: pick(d.teams) };
  }
  function dataset() {
    var ids = S.league === 'ALL' ? Object.keys(meta.leagues) : [S.league];
    return Promise.all(ids.map(loadLeague)).then(function (ds) {
      var out = { games: [], rows: null, teams: null };
      ds.forEach(function (d, i) {
        d.splitNames = d.splitNames || meta.leagues[ids[i]].splits;
        var s = slice(d, ids[i]), base = out.games.length;
        out.games = out.games.concat(s.games);
        ['rows', 'teams'].forEach(function (b) {
          var x = s[b]; x.g = x.g.map(function (g) { return g + base; });
          if (!out[b]) out[b] = x; else Object.keys(x).forEach(function (k) { if (k === 'n') out[b].n += x.n; else out[b][k] = out[b][k].concat(x[k]); });
        });
      });
      return out;
    });
  }

  /* ---------- aggregation into the shapes the pages draw ---------- */
  var mean = function (a) { var s = 0, n = 0; a.forEach(function (v) { if (v != null) { s += v; n++; } }); return n ? s / n : 0; };
  function players(ds) {
    var R = ds.rows, by = {}, tkg = {};
    for (var i = 0; i < R.n; i++) { var key = R.p[i] + '|' + R.t[i] + '|' + R.pos[i]; (by[key] = by[key] || []).push(i); }
    var out = [];
    Object.keys(by).forEach(function (key) {
      var ix = by[key], n = ix.length, f = function (c) { return ix.map(function (i) { return R[c][i]; }); };
      var K = f('k'), D = f('d'), A = f('a'), sum = function (a) { return a.reduce(function (x, y) { return x + (y || 0); }, 0); };
      var z = f('z').filter(function (v) { return v != null; }), zr = z.length ? 50 + z.length / (z.length + 5) * (12 * mean(z)) : 50;
      out.push({ p: meta.players[R.p[ix[0]]], t: meta.teams[R.t[ix[0]]][1], r: ROLES[R.pos[ix[0]]], g: n, wp: 100 * sum(f('w')) / n, kda: (sum(K) + sum(A)) / Math.max(1, sum(D)),
        k: sum(K) / n, d: sum(D) / n, a: sum(A) / n, dpm: mean(f('dpm')), cs: mean(f('cspm')), gd: mean(f('gd')), csd: mean(f('csd')), xpd: mean(f('xpd')), ds: mean(f('ds')) * 100, gpm: mean(f('gpm')),
        kp: +((sum(K) + sum(A)) / Math.max(1, sum(f('tk'))) * 100).toFixed(1), rt: Math.min(99.9, Math.max(1, 68 + 4 * (zr - 50))) });
    });
    return out;
  }
  function champs(ds, pl) {
    var R = ds.rows, G = ds.games.length, by = {}, bans = {};
    for (var i = 0; i < R.n; i++) if (R.c[i] >= 0) (by[R.c[i]] = by[R.c[i]] || []).push(i);
    var T = ds.teams; for (i = 0; i < T.n; i++) T.bans[i].forEach(function (b) { if (b >= 0) bans[b] = (bans[b] || 0) + 1; });
    var row = function (c, ix) {
      var n = ix.length, b = bans[c] || 0, f = function (k) { return ix.map(function (j) { return R[k][j]; }); }, sum = function (a) { return a.reduce(function (x, y) { return x + (y || 0); }, 0); };
      var w = sum(f('w')), o = { c: meta.champs[c], pk: n, bn: b, pr: Math.round((n + b) / Math.max(1, G) * 100), w: n ? w : 0, l: n ? n - w : 0 };
      if (n) { o.wr = Math.round(w / n * 100); o.kda = +((sum(f('k')) + sum(f('a'))) / Math.max(1, sum(f('d')))).toFixed(1); o.cs = +mean(f('cspm')).toFixed(1); o.dpm = Math.round(mean(f('dpm'))); o.gd = Math.round(mean(f('gd'))); o.csd = Math.round(mean(f('csd'))); }
      else { o.wr = o.kda = o.cs = o.dpm = o.gd = o.csd = null; }
      return o;
    };
    var ids = {}; Object.keys(by).forEach(function (c) { ids[c] = 1; }); Object.keys(bans).forEach(function (c) { ids[c] = 1; });
    var all = Object.keys(ids).map(function (c) { return row(+c, by[c] || []); });
    all.sort(function (a, b) { return b.pr - a.pr || b.pk - a.pk || b.w - a.w || (a.c < b.c ? -1 : 1); });
    var cbr = {};
    ROLES.forEach(function (role, ri) {
      var m = {}; for (var i = 0; i < R.n; i++) if (R.pos[i] === ri && R.c[i] >= 0) (m[R.c[i]] = m[R.c[i]] || []).push(i);
      cbr[role] = Object.keys(m).map(function (c) { return row(+c, m[c]); }).sort(function (a, b) { return b.pk - a.pk || b.w - a.w || b.bn - a.bn || (a.c < b.c ? -1 : 1); });
    });
    return { games: G, players: pl, top: [], champs: all.slice(0, 10), cbr: cbr, champsAll: all };
  }
  function wd(ds) { return champs(ds, players(ds)); }


  /* ---------- profile data (player.html / champion.html / team.html shapes) ---------- */
  var ROLEPOS = ROLES;
  var D2 = function (n) { return n == null ? null : n; };
  function base(ds) {
    var R = ds.rows, G = ds.games, rows = [], idx = {};
    for (var i = 0; i < R.n; i++) {
      var gm = G[R.g[i]], mine = R.s[i] === 0 ? gm.bt : gm.rt, opp = R.s[i] === 0 ? gm.rt : gm.bt;
      var o = { player: meta.players[R.p[i]], team: meta.teams[R.t[i]][1], opp: opp >= 0 ? meta.teams[opp][1] : '?', role: ROLES[R.pos[i]], champ: R.c[i] >= 0 ? meta.champs[R.c[i]] : '?', win: R.w[i], k: R.k[i], d: R.d[i], a: R.a[i],
        cs: R.cs[i], gl: gm.len / 60, dmg: R.dmg[i], gold: R.gold[i], tk: R.tk[i], ds: R.ds[i], gs: R.gs[i], csd: R.csd[i], gd: R.gd[i], xpd: R.xpd[i], vs: R.vs[i] || 0, wpm: R.wpm[i] || 0, wcpm: R.wcpm[i] || 0, dtm: R.dtm[i] || 0,
        cspm: R.cspm[i], date: gm.d.slice(0, 10), gid: gm.id, side: R.s[i] === 0 ? 'Blue' : 'Red', pt: gm.pt >= 0 ? meta.patches[gm.pt] : null, lg: gm.lg, sp: gm.sp, ev: gm.lg, len: gm.len };
      o.ic = o.champ; rows.push(o); idx[o.gid + '|' + o.role + '|' + o.team] = o;
    }
    rows.forEach(function (o) { var q = idx[o.gid + '|' + o.role + '|' + o.opp]; o.oc = q ? q.champ : '?'; o.op = q ? q.player : o.opp; });
    return rows;
  }
  function iconsFor(names, ic) { var o = {}; names.forEach(function (n) { if (ic[n]) o[n] = ic[n]; }); return o; }
  function newest(a) { return a.slice().sort(function (x, y) { return x.date < y.date ? 1 : x.date > y.date ? -1 : 0; }); }
  function mode(a) { var c = {}, b = null; a.forEach(function (x) { c[x] = (c[x] || 0) + 1; if (!b || c[x] > c[b]) b = x; }); return b; }
  function profPlayers(ds, ic) {
    var rows = base(ds), by = {}; rows.forEach(function (o) { (by[o.player] = by[o.player] || []).push(o); });
    var P = {}, used = {}, champs = {};
    Object.keys(by).forEach(function (n) {
      var g = newest(by[n]); P[n] = { name: n, team: g[0].team, role: mode(g.map(function (x) { return x.role; })), region: null, face: null, bd: null, contract: null, games: g };
      g.forEach(function (x) { champs[x.champ] = 1; });
    });
    return { players: P, icons: iconsFor(Object.keys(champs), ic), logos: {} };
  }
  function profChamps(ds, ic) {
    var rows = base(ds), T = ds.teams, ch = {}, avgs = {}, tkk = {};
    rows.forEach(function (o) {
      var r = { role: o.role, player: o.player, team: o.team, opp: o.opp, win: o.win, k: o.k, d: o.d, a: o.a, cspm: o.cspm, dmg: o.ds, gold: o.gs, gd: o.gd, csd: o.csd, xpd: o.xpd, kp: o.tk ? +((o.k + o.a) / o.tk).toFixed(4) : null,
        oc: o.oc, oi: o.oc, op: o.op, game: o.gid, side: o.side, len: o.len, date: o.date, pt: o.pt, lg: o.lg };
      (ch[o.champ] = ch[o.champ] || { rows: [], bans: [] }).rows.push(r); (avgs[o.role] = avgs[o.role] || []).push(o);
    });
    var G = ds.games;
    for (var i = 0; i < T.n; i++) { var gm = G[T.g[i]], me = meta.teams[T.t[i]][1], opp = T.s[i] === 0 ? gm.rt : gm.bt;
      T.bans[i].forEach(function (b, n) { if (b >= 0) (ch[meta.champs[b]] = ch[meta.champs[b]] || { rows: [], bans: [] }).bans.push({ by: me, vs: opp >= 0 ? meta.teams[opp][1] : '?', ph: n < 3 ? 1 : 2, game: gm.id, win: T.w[i] }); }); }
    var avg = {}; Object.keys(avgs).forEach(function (r) {
      var x = avgs[r], s = function (f) { return x.reduce(function (a, o) { return a + (o[f] || 0); }, 0); }, m = function (f) { var v = x.filter(function (o) { return o[f] != null; }); return v.length ? v.reduce(function (a, o) { return a + o[f]; }, 0) / v.length : 0; };
      avg[r] = { kda: (s('k') + s('a')) / Math.max(1, s('d')), cspm: m('cspm'), dmg: m('ds'), gold: m('gs'), kp: x.reduce(function (a, o) { return a + (o.tk ? (o.k + o.a) / o.tk : 0); }, 0) / x.length, gd: m('gd'), csd: m('csd'), xpd: m('xpd') };
    });
    var out = {}; Object.keys(ch).forEach(function (n) { out[n] = { ic: ic[n] ? n : null, rows: ch[n].rows, bans: ch[n].bans }; });
    return { champs: out, avg: avg, icons: iconsFor(Object.keys(out), ic), games: G.length, logos: {} };
  }
  function profTeams(ds) {
    var T = ds.teams, R = ds.rows, G = ds.games, teams = {}, byGame = {};
    for (var i = 0; i < R.n; i++) { var k = R.g[i] + '|' + R.s[i]; (byGame[k] = byGame[k] || []).push(i); }
    var pl = base(ds), plBy = {}; pl.forEach(function (o) { (plBy[o.player] = plBy[o.player] || []).push(o); });
    var players = {};
    Object.keys(plBy).forEach(function (n) { var g = newest(plBy[n]); players[n] = { name: n, team: g[0].team, role: mode(g.map(function (x) { return x.role; })), face: null, games: g }; });
    for (i = 0; i < T.n; i++) {
      var gm = G[T.g[i]], t = meta.teams[T.t[i]], opp = T.s[i] === 0 ? gm.rt : gm.bt, ix = byGame[T.g[i] + '|' + T.s[i]] || [];
      var sum = function (c) { return ix.reduce(function (a, j) { return a + (R[c][j] || 0); }, 0); };
      var row = { gid: gm.id, opp: opp >= 0 ? meta.teams[opp][1] : '?', win: T.w[i], gl: gm.len, date: gm.d.slice(0, 10), k: sum('k'), d: sum('d'), a: sum('a'), fb: T.fb[i] || 0, ft: T.ft[i] || 0, dr: T.dr[i] || 0, ba: T.ba[i] || 0,
        tw: T.tw[i] || 0, gr: T.gr[i] || 0, he: T.he[i] || 0, gold: T.gold[i] || 0, dmg: sum('dmg'), vs: sum('vs'), cs: sum('cs'), gd: sum('gd'), csd: sum('csd'), xpd: sum('xpd'), lg: gm.lg };
      (teams[t[1]] = teams[t[1]] || { code: t[1], name: t[0], region: null, games: [], players: [] }).games.push(row);
    }
    Object.keys(players).forEach(function (n) { var p = players[n], seen = {}; p.games.forEach(function (g) { var t = teams[g.team]; if (t && !seen[g.team]) { seen[g.team] = 1; if (t.players.indexOf(n) < 0) t.players.push(n); } }); });
    Object.keys(teams).forEach(function (c) { teams[c].region = mode(teams[c].games.map(function (g) { return g.lg; })); teams[c].games.sort(function (a, b) { return a.date < b.date ? -1 : 1; }); });
    return { teams: teams, players: players, logos: {} };
  }
  function profile(kind, ds) { return Promise.all([LVF_icons(), LVF_logos()]).then(function (v) { var d = kind === 'player' ? profPlayers(ds, v[0]) : kind === 'champion' ? profChamps(ds, v[0]) : profTeams(ds); d.logos = v[1]; return d; }); }
  var _lg = null; function LVF_logos() { return (_lg = _lg || jget('data/logos.json').catch(function () { return {}; })); }
  var _ic = null; function LVF_icons() { return (_ic = _ic || jget('data/champs.json').catch(function () { return {}; })); }


  /* series list for results.html: [winner, "2:1", loser, time, date, first game id, ms, league] newest first; games of the same pair < 12h apart form one series */
  function results(ds) {
    var G = ds.games.map(function (g, i) { return { g: g, i: i, t: Date.parse(g.d.replace(' ', 'T') + ':00Z') }; }).filter(function (x) { return x.g.bt >= 0 && x.g.rt >= 0 && x.g.cp !== 0; }).sort(function (a, b) { return a.t - b.t; });
    var ser = [], last = {};
    G.forEach(function (x) {
      var a = x.g.bt, b = x.g.rt, key = Math.min(a, b) + '|' + Math.max(a, b), s = last[key];
      if (s && x.t - s.last < 12 * 3600e3) { s.games.push(x); s.last = x.t; } else { s = { key: key, games: [x], last: x.t }; last[key] = s; ser.push(s); }
    });
    var out = ser.map(function (s) {
      var w = {}; s.games.forEach(function (x) { var win = x.g.bw === 1 ? x.g.bt : x.g.rt; w[win] = (w[win] || 0) + 1; });
      var ids = Object.keys(w).map(Number).sort(function (p, q) { return w[q] - w[p]; }), win = ids[0], lose = +s.key.split('|').filter(function (v) { return +v !== win; })[0];
      var lastG = s.games[s.games.length - 1], t = new Date(lastG.t), fmt = function (o) { return new Intl.DateTimeFormat('en-GB', Object.assign({ timeZone: 'Europe/London' }, o)).format(t); };
      return [meta.teams[win][1], w[win] + ':' + (w[lose] || 0), meta.teams[lose][1], fmt({ hour: '2-digit', minute: '2-digit' }), fmt({ month: 'short', day: 'numeric' }), s.games[0].g.id, lastG.t, lastG.g.lg];
    });
    return out.sort(function (a, b) { return b[6] - a[6]; });
  }

  /* ---------- UI ---------- */
  function css() {
    var s = document.createElement('style');
    s.textContent = '#lvf{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-top:24px !important;margin-bottom:-28px;position:relative;z-index:60}' +
      '#lvf .fd{position:relative}#lvf .fb{display:flex;align-items:center;gap:8px;height:32px;padding:0 12px;background:var(--surface);border:1px solid var(--line);border-radius:8px;color:var(--fg);font:inherit;font-size:12.5px;cursor:pointer}' +
      '#lvf .fb small{color:var(--muted);font-size:10.5px;letter-spacing:.06em;text-transform:uppercase}#lvf .fb svg{color:var(--muted)}#lvf .fb.sel{border-color:var(--fg)}' +
      '#lvf .fm{display:none;position:absolute;left:0;top:calc(100% + 6px);min-width:100%;width:max-content;max-width:300px;max-height:340px;overflow:auto;background:var(--surface);border:1px solid var(--line);border-radius:8px;padding:4px;box-shadow:0 12px 32px rgba(0,0,0,.35)}' +
      '#lvf .fd.open .fm{display:block}#lvf .fm button{display:block;width:100%;text-align:left;background:none;border:0;color:var(--fg);font:inherit;font-size:12.5px;padding:7px 10px;border-radius:5px;cursor:pointer;white-space:nowrap}' +
      '#lvf .fm button:hover,#lvf .fm button.on{background:var(--surface-2)}#lvf .fm .gh{font-size:10.5px;letter-spacing:.08em;text-transform:uppercase;color:var(--dim);padding:8px 10px 4px}' +
      '#lvf .st{color:var(--muted);font-size:12px;margin-left:4px}#lvf .rs{background:none;border:0;color:var(--muted);font:inherit;font-size:12px;cursor:pointer;text-decoration:underline;padding:0}';
    document.head.appendChild(s);
  }
  var chev = '<svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" stroke-width="1.5"><path d="m2 4 3 3 3-3"/></svg>';
  function options() {
    var lgs = Object.keys(meta.leagues), maj = MAJOR.filter(function (x) { return meta.leagues[x]; }), rest = lgs.filter(function (x) { return MAJOR.indexOf(x) < 0; }).sort(function (a, b) { return lname(a).localeCompare(lname(b)); });
    var splits = {}; (S.league === 'ALL' ? lgs : [S.league]).forEach(function (l) { (meta.leagues[l] ? meta.leagues[l].splits : []).forEach(function (s) { if (s) splits[s] = 1; }); });
    var years = {}; (S.league === 'ALL' ? lgs : [S.league]).forEach(function (l) { meta.leagues[l] && meta.leagues[l].years.forEach(function (y) { years[y] = 1; }); });
    return {
      league: [['h', 'Featured']].concat(maj.map(function (x) { return [x, lname(x)]; }), [['ALL', 'All leagues'], ['h', 'Other leagues']], rest.map(function (x) { return [x, lname(x)]; })),
      split: [['All', 'All splits']].concat(Object.keys(splits).sort().map(function (x) { return [x, x]; })),
      stage: [['All', 'All stages'], ['Regular', 'Regular season'], ['Playoffs', 'Playoffs']],
      year: [['All', 'All years']].concat(Object.keys(years).sort().reverse().map(function (x) { return [x, x]; }))
    };
  }
  var LBL = { league: 'League', split: 'Split', stage: 'Stage', year: 'Year' };
  function render(status) {
    if (!bar) return;
    var o = options(), open = (bar.querySelector('.fd.open') || {}).id;
    bar.innerHTML = ['league', 'split', 'stage', 'year'].map(function (k) {
      var cur = o[k].filter(function (x) { return x[0] === S[k]; })[0], label = cur ? cur[1] : S[k];
      return '<div class="fd' + (open === 'fd-' + k ? ' open' : '') + '" id="fd-' + k + '"><button type="button" class="fb' + (k !== 'league' && S[k] !== 'All' ? ' sel' : '') + '"><small>' + LBL[k] + '</small>' + label + chev + '</button><div class="fm">' +
        o[k].map(function (x) { return x[0] === 'h' ? '<div class="gh">' + x[1] + '</div>' : '<button type="button" data-k="' + k + '" data-v="' + x[0] + '"' + (x[0] === S[k] ? ' class="on"' : '') + '>' + x[1] + '</button>'; }).join('') + '</div></div>';
    }).join('') + '<span class="st">' + (status || '') + '</span>' + (isDefault() ? '' : '<button type="button" class="rs" data-reset="1">Back to Worlds</button>');
  }
  function apply() {
    try { sessionStorage.setItem('lvf', JSON.stringify(S)); } catch (e) {}
    var my = ++busy;
    if (isDefault()) { cur = null; render('Worlds 2026 · Main Stage'); handlers.forEach(function (h) { h(null, S); }); return Promise.resolve(); }
    render('Loading…');
    return dataset().then(function (ds) {
      if (my !== busy) return; cur = ds; cur.scope = S;
      var n = ds.games.length; render(n.toLocaleString('en-US') + ' game' + (n === 1 ? '' : 's') + (n ? '' : ' - nothing matches these filters'));
      handlers.forEach(function (h) { h(ds, S); });
    }).catch(function (e) { render('Could not load data'); console.error(e); });
  }
  function init() {
    var top = $('.page > .topbar'); if (!top) return;
    css(); bar = document.createElement('div'); bar.id = 'lvf'; top.parentNode.insertBefore(bar, top.nextSibling);
    loadMeta().then(function () {
      if (!meta.leagues[S.league] && S.league !== 'ALL') S.league = 'WLDs';
      bar.addEventListener('click', function (e) {
        if (e.target.closest('[data-reset]')) { S = { league: 'WLDs', split: 'All', stage: 'All', year: 'All' }; apply(); return; }
        var m = e.target.closest('.fm button[data-k]');
        if (m) { S[m.dataset.k] = m.dataset.v; if (m.dataset.k === 'league') { S.split = 'All'; S.year = 'All'; } apply(); return; }
        var b = e.target.closest('.fb'); var d = b && b.parentNode, was = d && d.classList.contains('open');
        Array.prototype.forEach.call(bar.querySelectorAll('.fd'), function (x) { x.classList.remove('open'); }); if (d && !was) d.classList.add('open');
      });
      document.addEventListener('click', function (e) { if (!e.target.closest('#lvf')) Array.prototype.forEach.call(bar.querySelectorAll('.fd'), function (x) { x.classList.remove('open'); }); });
      apply();
    }).catch(function () { bar.style.display = 'none'; });
  }
  window.LVF = { onChange: function (fn) { handlers.push(fn); if (bar && meta) fn(cur, S); }, state: function () { return S; }, meta: function () { return meta; }, wd: wd, players: players, isDefault: isDefault, lname: lname,
    loadMeta: loadMeta, profile: profile, results: results, leagueName: lname, icons: function () { return jget('data/champs.json'); } };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
