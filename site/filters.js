/* Shared filter bar (League / Split / Stage / Year) + client-side aggregation of dist/data/*.json.
   Default = the page's embedded Worlds data. Picking anything else loads the league files and calls the page's handler(s). */
(function () {
  var ROLES = ['Top', 'Jungle', 'Mid', 'Bot', 'Support'];
  var NAMES = { WLDs: 'Worlds', MSI: 'MSI', LCK: 'LCK', LPL: 'LPL', LEC: 'LEC', LCS: 'LCS', LCP: 'LCP', CBLOL: 'CBLOL', LCKC: 'LCK Challengers', LAS: 'LAS', LES: 'LES', LJL: 'LJL', LLA: 'LLA', PCS: 'PCS', VCS: 'VCS', TCL: 'TCL', LFL: 'LFL', NLC: 'NLC', PRM: 'Prime League', LIT: 'LIT', EM: 'EMEA Masters', EWC: 'EWC', FST: 'FST', CD: 'Circuit Demacia', NACL: 'NACL', AL: 'LPL Academy', LRN: 'LRN', LRS: 'LRS', WLRQ: 'Worlds Qualifiers', WSCI: 'Worlds Play-Ins', CCWS: 'CCWS', AC: 'Asia Cup', AM: 'Americas Cup', DCGI: 'DCGI', DCup: 'DCup', HC: 'Hitpoint Challengers', HLL: 'Hellenic Legends', HM: 'Hitpoint Masters', HW: 'HW', NL: 'NL', RL: 'Rift Legends', ROL: 'Roll', LPLOL: 'LPLOL', EBL: 'Esports Balkan League', KeSPA: 'KeSPA' };
  var MAJOR = ['WLDs', 'MSI', 'EWC', 'FST', 'DCGI', 'AC', 'LCK', 'LPL', 'LEC', 'LCS', 'LCP', 'CBLOL'];
  var S = { league: 'WLDs', split: 'All', stage: 'All', year: 'All' };
  var meta = null, cache = {}, handlers = [], bar = null, busy = 0, cur = null;
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var EI = /*EI*/{}/*EI*/;
  var evIcon = function (id, size, fb) {
    var e = EI[id]; if (!e) return fb || ''; var t = lname(id).replace(' 2026', ''), w = size, h = size;
    if (e.ar > 1.3) { w = Math.round(size * 1.6); h = Math.round(w / e.ar * 10) / 10; }
    var at = ' width="' + w + '" height="' + h + '" alt="' + t + '">';
    return e.d ? '<img class="wi-l" src="' + e.l + '"' + at + '<img class="wi-d" src="' + e.d + '"' + at : '<img src="' + e.l + '"' + at;
  };
  var TROPHY = '<svg width="16" height="14" viewBox="0 0 16 14" fill="none" aria-hidden="true"><path d="M12.91 1H15C15.2652 1 15.5196 1.10536 15.7071 1.29289C15.8946 1.48043 16 1.73478 16 2V4C16 4.79565 15.6839 5.55871 15.1213 6.12132C14.5587 6.68393 13.7956 7 13 7H12.364L12.362 7.017C12.2786 7.93293 11.9089 8.79935 11.3055 9.49344C10.702 10.1875 9.89543 10.674 9 10.884V12H11L12 13V14H4V13L5 12H7V10.884C6.10457 10.674 5.29795 10.1875 4.69451 9.49344C4.09107 8.79935 3.72143 7.93293 3.638 7.017L3.636 7H3L2.846 6.996C2.07803 6.95653 1.35455 6.62366 0.824929 6.06613C0.295313 5.5086 1.15153e-05 4.76898 5.08215e-08 4L5.08215e-08 2C-7.87927e-05 1.75256 0.0915822 1.51388 0.257263 1.3301C0.422944 1.14632 0.650877 1.03049 0.897 1.005L1 1H3.09L3 0H13L12.91 1ZM2 4C2 4.26522 2.10536 4.51957 2.29289 4.70711C2.48043 4.89464 2.73478 5 3 5H3.454L3.272 3H2V4ZM12.546 5H13C13.2652 5 13.5196 4.89464 13.7071 4.70711C13.8946 4.51957 14 4.26522 14 4V3H12.727L12.546 5Z" fill="currentColor"/></svg>';
  var lname = function (id) { return id === 'ALL' ? 'All leagues' : (NAMES[id] || id); };

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
  function slice(d, lg, S) {
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
  function dataset(sc) {
    var S0 = sc || S, ids = S0.league === 'ALL' ? Object.keys(meta.leagues) : [S0.league];
    return Promise.all(ids.map(loadLeague)).then(function (ds) {
      var out = { games: [], rows: null, teams: null };
      ds.forEach(function (d, i) {
        d.splitNames = d.splitNames || meta.leagues[ids[i]].splits;
        var s = slice(d, ids[i], S0), base = out.games.length;
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
        k: sum(K) / n, d: sum(D) / n, a: sum(A) / n, dpm: mean(f('dpm')), cs: mean(f('cspm')), gd: mean(f('gd')), csd: mean(f('csd')), xpd: mean(f('xpd')), ds: mean(f('ds')) * 100, gpm: mean(f('gpm')), vs: mean(f('vs')),
        kp: +((sum(K) + sum(A)) / Math.max(1, sum(f('tk'))) * 100).toFixed(1), rt: Math.min(99.9, Math.max(1, 68 + 3.3 * (zr - 50))) });
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
        cspm: R.cspm[i], date: gm.d.slice(0, 10), gid: gm.id, side: R.s[i] === 0 ? 'Blue' : 'Red', pt: gm.pt >= 0 ? meta.patches[gm.pt] : null, lg: gm.lg, sp: gm.sp, ev: gm.lg, len: gm.len, gn: gm.g, dt: gm.d, fbk: R.fb ? R.fb[i] : null };
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
        tw: T.tw[i] || 0, gr: T.gr[i] || 0, he: T.he[i] || 0, gold: T.gold[i] || 0, dmg: sum('dmg'), vs: sum('vs'), cs: sum('cs'), gd: sum('gd'), csd: sum('csd'), xpd: sum('xpd'), lg: gm.lg, pt: gm.pt >= 0 ? meta.patches[gm.pt] : null };
      (teams[t[1]] = teams[t[1]] || { code: t[1], name: t[0], home: t[2] || null, region: null, games: [], players: [] }).games.push(row);
    }
    Object.keys(players).forEach(function (n) { var p = players[n], seen = {}; p.games.forEach(function (g) { var t = teams[g.team]; if (t && !seen[g.team]) { seen[g.team] = 1; if (t.players.indexOf(n) < 0) t.players.push(n); } }); });
    Object.keys(teams).forEach(function (c) { teams[c].region = teams[c].home || mode(teams[c].games.map(function (g) { return g.lg; })); teams[c].games.sort(function (a, b) { return a.date < b.date ? -1 : 1; }); });
    return { teams: teams, players: players, logos: {} };
  }
  /* items, runes and 1-minute gold from the Riot feed for the games of the other leagues (dist/data/items-<LEAGUE>.json, written by build.py) */
  var _it = {}, _ia = null;
  function LVF_items(lg) { return (_it[lg] = _it[lg] || jget('data/items-' + lg.replace(/[^A-Za-z0-9_-]/g, '_') + '.json').catch(function () { return {}; })); }
  function LVF_itemAssets() { return (_ia = _ia || jget('data/item-assets.json').catch(function () { return null; })); }
  function withItems(d, rows) {
    var lgs = {}; rows.forEach(function (r) { if (r.lg && r.lg !== 'WLDs') lgs[r.lg] = 1; });
    var ks = Object.keys(lgs); if (!ks.length) return d;
    return Promise.all(ks.map(LVF_items).concat([LVF_itemAssets()])).then(function (v) {
      var AS = v[ks.length], X = {}; ks.forEach(function (k, i) { X[k] = v[i]; });
      if (!AS) return d;
      var any = false;
      rows.forEach(function (r) {
        var gid = r.gid || r.game, e = r.lg && X[r.lg] && X[r.lg][gid]; if (!e) return;
        var x = e.p[(r.side === 'Blue' ? 0 : 1) + ':' + ROLES.indexOf(r.role)]; if (!x) return;
        r.it = x[0]; r.rn = x[1]; any = true;
      });
      if (any) { d.items = AS.items; d.runes = AS.runes; }
      return d;
    });
  }
  function profile(kind, ds) {
    return Promise.all([LVF_icons(), LVF_logos()]).then(function (v) {
      var d = kind === 'player' ? profPlayers(ds, v[0]) : kind === 'champion' ? profChamps(ds, v[0]) : profTeams(ds); d.logos = v[1];
      var rows = kind === 'player' ? [].concat.apply([], Object.keys(d.players).map(function (n) { return d.players[n].games; })) : kind === 'champion' ? [].concat.apply([], Object.keys(d.champs).map(function (c) { return d.champs[c].rows; })) : [];
      return withItems(d, rows);
    });
  }
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
  var ENT = null;   // {kind, name}: on a player / team page only what that player or team took part in is offered
  var PLACE = { 'player.html': ['prepend', '.body > section'], 'team.html': ['prepend', '.tbody > .main'], 'champion.html': ['after', '.gh'], 'players.html': ['after', '.tp .tp-head'], 'index.html': ['after', '.tp .tp-head'], '': ['after', '.tp .tp-head'],
    'champions.html': ['after', '#champions > h2, #champions > :first-child'], 'results.html': ['after', 'h2.sec'] };
  function css() {
    var s = document.createElement('style');
    s.textContent = '#lvf{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin:16px 0;position:relative;z-index:50}' +
      '#lvf .fd{position:relative}#lvf .fb{display:flex;align-items:center;gap:8px;height:32px;padding:0 12px;background:var(--surface);border:1px solid var(--line);border-radius:8px;color:var(--fg);font:inherit;font-size:12.5px;cursor:pointer}' +
      '#lvf .fb small{color:var(--muted);font-size:10.5px;letter-spacing:.06em;text-transform:uppercase}#lvf .fb svg{color:var(--muted)}#lvf .fb.sel{border-color:var(--fg)}#lvf .fb.one{cursor:default}#lvf .fb.one svg{display:none}' +
      '#lvf .fm{display:none;position:absolute;left:0;top:calc(100% + 6px);min-width:100%;width:max-content;max-width:300px;max-height:340px;overflow:auto;background:var(--surface);border:1px solid var(--line);border-radius:8px;padding:4px;box-shadow:0 12px 32px rgba(0,0,0,.35)}' +
      '#lvf .fd.open .fm{display:block}#lvf .fm button{display:block;width:100%;text-align:left;background:none;border:0;color:var(--fg);font:inherit;font-size:12.5px;padding:7px 10px;border-radius:5px;cursor:pointer;white-space:nowrap}' +
      '#lvf .fi{display:inline-grid;place-items:center;width:28px;height:18px;flex:none}#lvf .fi img{width:auto;height:auto;max-width:28px;max-height:18px}#lvf .fm button:has(.fi){display:flex;align-items:center;gap:8px}#lvf .fb .fi{margin-right:-2px}#lvf .fm button.sub{padding-left:46px;color:var(--muted)}#lvf .fm button.sub.on{color:var(--fg)}' +
      '#lvf .fm button:hover,#lvf .fm button.on{background:var(--surface-2)}#lvf .fm .gh{font-size:10.5px;letter-spacing:.08em;text-transform:uppercase;color:var(--dim);padding:8px 10px 4px}' +
      '#lvf .lst{color:var(--muted);font-size:12px;margin-left:4px}#lvf .rs{background:none;border:0;color:var(--muted);font:inherit;font-size:12px;cursor:pointer;text-decoration:underline;padding:0}';
    document.head.appendChild(s);
  }
  var chev = '<svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" stroke-width="1.5"><path d="m2 4 3 3 3-3"/></svg>';
  /* every [league, year, split, stageMask] that exists for the current page (whole site, or the player / team being viewed) */
  function tuples() {
    if (ENT) { var k = ENT.kind === 'player' ? meta.pix[ENT.name] : meta.tix[meta.tname[ENT.name] || ENT.name]; if (k) return k; }
    var o = []; Object.keys(meta.leagues).forEach(function (l) { meta.leagues[l].tuples.forEach(function (t) { o.push([l, t[0], t[1], t[2]]); }); }); return o;
  }
  function options() {
    var T = tuples(), ys = {}; T.forEach(function (t) { ys[t[1]] = 1; });
    var years = Object.keys(ys).sort().reverse().map(Number);
    var Ty = T.filter(function (t) { return S.year === 'All' || t[1] === +S.year; });
    var lgs = {}, spl = {}; Ty.forEach(function (t) { lgs[t[0]] = 1; if (t[2]) (spl[t[0]] = spl[t[0]] || {})[t[2]] = 1; });
    var ids = Object.keys(lgs), maj = MAJOR.filter(function (x) { return lgs[x]; }), rest = ids.filter(function (x) { return MAJOR.indexOf(x) < 0; }).sort(function (a, b) { return lname(a).localeCompare(lname(b)); });
    var tour = [];
    if (ids.length > 1) tour.push(['ALL|All', 'All']);
    var add = function (l) { var sp = Object.keys(spl[l] || {}).sort(); tour.push([l + '|All', lname(l) + (sp.length > 1 ? ' (All)' : '')]); if (sp.length > 1) sp.forEach(function (x) { tour.push([l + '|' + x, lname(l) + ' · ' + x, 1]); }); };
    maj.concat(rest).forEach(add);
    var Tt = Ty.filter(function (t) { return (S.league === 'ALL' || t[0] === S.league) && (S.split === 'All' || t[2] === S.split); }), mask = 0; Tt.forEach(function (t) { mask |= t[3]; });
    var stage = mask === 3 ? [['All', 'All stages'], ['Regular', 'Regular season'], ['Playoffs', 'Playoffs']] : null;
    return { years: years, tour: tour, stage: stage, ids: ids };
  }
  /* keep the selection inside what is offered; returns true when something had to change */
  function normalize(o) {
    var c = false, set = function (k, v) { if (S[k] !== v) { S[k] = v; c = true; } };
    if (S.year !== 'All' && o.years.indexOf(+S.year) < 0) set('year', 'All');
    var cur = S.league + '|' + S.split;
    if (!o.tour.some(function (t) { return t[0] === cur; })) {
      var first = o.tour.filter(function (t) { return !t[2]; })[0]; if (first) { var p = first[0].split('|'); set('league', p[0]); set('split', p[1]); }
    }
    if (S.stage !== 'All' && !(o.stage && o.stage.some(function (x) { return x[0] === S.stage; }))) set('stage', 'All');
    return c;
  }
  function ico(k, x) {
    if (k !== 'tour') return '';
    var id = x[0].split('|')[0];
    if (x[2]) return '';
    return '<span class="fi">' + (id === 'ALL' ? TROPHY : evIcon(id, 18)) + '</span>';
  }
  function dd(k, label, items, curv, one) {
    var cu = items.filter(function (x) { return x[0] === curv; })[0];
    return '<div class="fd" id="fd-' + k + '"><button type="button" class="fb' + (one ? ' one' : '') + '">' + (cu ? ico(k, cu) : '') + label + chev + '</button>' + (one ? '' : '<div class="fm">' +
      items.map(function (x) { return '<button type="button" data-k="' + k + '" data-v="' + x[0] + '"' + ((x[0] === curv ? ' class="on' + (x[2] ? ' sub' : '') + '"' : (x[2] ? ' class="sub"' : ''))) + '>' + ico(k, x) + x[1] + '</button>'; }).join('') + '</div>') + '</div>';
  }
  var LBL = { year: 'Year', tour: 'Tournament', stage: 'Stage' };
  function render(status) {
    if (!bar) return;
    var o = options(), open = (bar.querySelector('.fd.open') || {}).id;
    var yl = S.year === 'All' ? (o.years.length === 1 ? String(o.years[0]) : 'All years') : S.year;
    var cur = S.league + '|' + S.split, tl = (o.tour.filter(function (t) { return t[0] === cur; })[0] || [0, ''])[1];
    var h = dd('year', yl, [['All', 'All years']].concat(o.years.map(function (y) { return [String(y), String(y)]; })), S.year, o.years.length <= 1) + dd('tour', tl, o.tour, cur, o.tour.length <= 1);
    if (o.stage) h += dd('stage', (o.stage.filter(function (x) { return x[0] === S.stage; })[0] || o.stage[0])[1], o.stage, S.stage, false);
    bar.innerHTML = h + '<span class="lst">' + (status || '') + '</span>' + (isDefault() ? '' : '<button type="button" class="rs" data-reset="1">' + 'Reset' + '</button>');
    if (open) { var d = bar.querySelector('#' + open); if (d) d.classList.add('open'); }
  }
  function apply() {
    normalize(options());
    var my = ++busy;
    if (isDefault()) { cur = null; render(''); handlers.forEach(function (h) { h(null, S); }); return Promise.resolve(); }
    render('Loading…');
    return dataset().then(function (ds) {
      if (my !== busy) return; cur = ds; cur.scope = S;
      var n = ds.games.length; render(ENT || window.LVF_NOCOUNT ? (n ? '' : 'Nothing matches these filters') : n.toLocaleString('en-US') + ' game' + (n === 1 ? '' : 's') + (n ? '' : ' - nothing matches these filters'));
      handlers.forEach(function (h) { h(ds, S); });
    }).catch(function (e) { render('Could not load data'); console.error(e); });
  }
  function place() {
    var pg = location.pathname.split('/').pop(), r = PLACE[pg] || PLACE['index.html'], el = $(r[1]);
    if (!el) { el = $('.page > .topbar'); r = ['after', '']; }
    if (!el) return false;
    if (r[0] === 'prepend') el.insertBefore(bar, el.firstChild); else el.parentNode.insertBefore(bar, el.nextSibling);
    return true;
  }
  function init() {
    if (!$('.page > .topbar') || /(tournament|rankings)\.html$/.test(location.pathname)) return;
    css(); bar = document.createElement('div'); bar.id = 'lvf';
    loadMeta().then(function () {
      if (!place()) return;
      if (ENT) Object.assign(S, entityDefault());
      bar.addEventListener('click', function (e) {
        if (e.target.closest('[data-reset]')) { S = ENT ? entityDefault() : baseDefault(); apply(); return; }
        var m = e.target.closest('.fm button[data-k]');
        if (m) {
          if (m.dataset.k === 'tour') { var p = m.dataset.v.split('|'); S.league = p[0]; S.split = p[1]; S.stage = 'All'; } else S[m.dataset.k] = m.dataset.v;
          apply(); return;
        }
        var b = e.target.closest('.fb'); if (!b || b.classList.contains('one')) return; var d = b.parentNode, was = d.classList.contains('open');
        Array.prototype.forEach.call(bar.querySelectorAll('.fd'), function (x) { x.classList.remove('open'); }); if (!was) d.classList.add('open');
      });
      document.addEventListener('click', function (e) { if (!e.target.closest('#lvf')) Array.prototype.forEach.call(bar.querySelectorAll('.fd'), function (x) { x.classList.remove('open'); }); });
      apply();
    }).catch(function () { bar.style.display = 'none'; });
  }
  /* default scope: the current event; for a player / team that is not in it, their most recent event */
  function baseDefault() { return { league: 'WLDs', split: 'All', stage: 'All', year: 'All' }; }
  function entityDefault() {
    var T = ENT ? tuples() : [];
    if (!ENT || !T.length || T.some(function (t) { return t[0] === meta.current; })) return baseDefault();
    var p = T.slice().sort(function (a, b) { return a[4] < b[4] ? 1 : a[4] > b[4] ? -1 : 0; })[0];
    return { league: p[0], split: p[2] || 'All', stage: 'All', year: String(p[1]) };
  }
  function focus(kind, name) {
    var same = ENT && ENT.kind === kind && ENT.name === name; ENT = { kind: kind, name: name };
    if (same || !bar || !meta) return; Object.assign(S, entityDefault()); return apply();
  }
  function entity(kind, name) { if (ENT && ENT.kind === kind && ENT.name === name) { render((bar && bar.querySelector('.lst') || {}).textContent); return; } return focus(kind, name); }
  function tours() { return meta ? Object.keys(meta.leagues).map(function (l) { return [l, lname(l)]; }) : []; }
  function load(league, split) { return loadMeta().then(function () { return dataset({ league: league, split: split || 'All', stage: 'All', year: 'All' }); }); }
  window.LVF = { trophy: TROPHY, tours: tours, load: load, players: function (ds) { return players(ds); }, champs: function (ds) { return wd(ds).champsAll; }, entity: entity, focus: focus, set: function (o) { if (Object.keys(o).every(function (k) { return S[k] === o[k]; })) return; Object.assign(S, o); if (bar && meta) return apply(); }, has: function (kind, n) { return loadMeta().then(function (m) { return kind === 'player' ? m.players.indexOf(n) >= 0 : kind === 'team' ? !!m.tname[n] : m.champs.indexOf(n) >= 0; }); }, onChange: function (fn) { handlers.push(fn); if (bar && meta) fn(cur, S); }, state: function () { return S; }, meta: function () { return meta; }, wd: wd, players: players, isDefault: isDefault, lname: lname,
    loadMeta: loadMeta, profile: profile, results: results, leagueName: lname, evIcon: evIcon, icons: function () { return jget('data/champs.json'); } };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
