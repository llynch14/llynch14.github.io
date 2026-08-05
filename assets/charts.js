/* Reading & watching stats: renders lists and single-series SVG column charts
   from the JSON files committed by the daily fetch workflow. No dependencies. */
(function () {
  'use strict';

  const esc = s => String(s ?? '').replace(/[&<>"]/g,
    c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

  function stars(rating) {
    if (rating == null || rating === 0) return '';
    const full = Math.floor(rating);
    const half = rating - full >= 0.5;
    return '★'.repeat(full) + (half ? '½' : '');
  }

  const fmt = n => Number(n).toLocaleString('en-GB');

  /* --- tooltip (one shared, follows the hovered mark) --- */
  const tip = document.createElement('div');
  tip.className = 'chart-tip';
  tip.setAttribute('role', 'status');
  document.body.appendChild(tip);

  function showTip(evt, html) {
    tip.innerHTML = html;
    tip.style.display = 'block';
    const pad = 12;
    let x = evt.clientX + pad, y = evt.clientY + pad;
    const r = tip.getBoundingClientRect();
    if (x + r.width > window.innerWidth - 8) x = evt.clientX - r.width - pad;
    if (y + r.height > window.innerHeight - 8) y = evt.clientY - r.height - pad;
    tip.style.left = x + 'px';
    tip.style.top = y + window.scrollY + 'px';
  }
  const hideTip = () => { tip.style.display = 'none'; };

  /* --- single-series column chart (pixel style) --- */
  function columnChart(el, points, opts) {
    // points: [{label, count, tip}] — wide square bars with chunky outlines,
    // value labeled on each cap, solid baseline, hover tooltip.
    const W = 560, H = 180, padX = 8, padBottom = 24, padTop = 18;
    const n = points.length;
    if (!n) { el.remove(); return; }
    const max = Math.max(...points.map(p => p.count));
    const band = (W - padX * 2) / n;
    const barW = Math.min(56, band * 0.75);
    const plotH = H - padTop - padBottom;
    const yFor = c => padTop + plotH * (1 - c / max);

    let svg = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(opts.label)}">`;
    svg += `<line x1="${padX}" y1="${H - padBottom}" x2="${W - padX}" y2="${H - padBottom}" class="axis"/>`;
    points.forEach((p, i) => {
      const x = padX + band * i + (band - barW) / 2;
      const y = yFor(p.count);
      const h = H - padBottom - y;
      if (h > 0) {
        svg += `<rect class="bar" data-i="${i}" x="${x}" y="${y}" width="${barW}" height="${h}"/>`;
        svg += `<text class="cap" x="${x + barW / 2}" y="${y - 6}" text-anchor="middle">${fmt(p.count)}</text>`;
      }
      svg += `<text class="tick" x="${x + barW / 2}" y="${H - 6}" text-anchor="middle">${esc(p.label)}</text>`;
    });
    svg += '</svg>';
    el.querySelector('.chart-body').innerHTML = svg;

    el.querySelectorAll('.bar').forEach(bar => {
      const p = points[+bar.dataset.i];
      bar.addEventListener('mousemove', e => showTip(e, p.tip));
      bar.addEventListener('mouseleave', hideTip);
    });
  }

  /* --- the bookshelf: recent reads as spines, hover for details --- */
  const SPINE_COLS = ['#b8e0d2', '#7fb5d9', '#c7dcb9', '#f4a259', '#8fa8c8', '#8fd0c6'];
  function bookshelf(el, books) {
    el.innerHTML = '';
    const shelf = [...books].reverse(); // oldest left, newest leaning at the right
    shelf.forEach((b, i) => {
      const a = document.createElement('a');
      a.className = 'spine' + (i === shelf.length - 1 ? ' lean' : '');
      a.href = b.url;
      const hash = [...b.title].reduce((h, c) => (h * 31 + c.charCodeAt(0)) >>> 0, 7);
      a.style.background = SPINE_COLS[hash % SPINE_COLS.length];
      const pages = b.pages || 350;
      const h = Math.round(Math.max(100, Math.min(152, 100 + (pages - 120) * 0.055)));
      a.style.height = h + 'px';
      a.style.width = (24 + (hash % 2) * 5) + 'px';
      // truncate in JS — Safari clips vertical text with CSS ellipsis
      const maxChars = Math.floor((h - 16) / 8);
      a.textContent = b.title.length > maxChars ? b.title.slice(0, maxChars - 1) + '…' : b.title;
      a.setAttribute('aria-label', `${b.title} by ${b.author}`);
      const tip = `<strong>${esc(b.title)}</strong><br>${esc(b.author)}<br>` +
                  `<span class="tipstars">${stars(b.rating) || 'unrated'}</span>`;
      a.addEventListener('mousemove', e => showTip(e, tip));
      a.addEventListener('mouseleave', hideTip);
      el.appendChild(a);
    });
  }

  function filmList(el, films) {
    el.innerHTML = films.map(f => `
      <li>
        <a href="${esc(f.url)}">${esc(f.title)}</a>
        <span class="media-meta">${f.year ? esc(f.year) : ''}</span>
        <span class="media-stars">${stars(f.rating)}</span>
      </li>`).join('');
  }

  /* --- data plumbing --- */
  const getJSON = url => fetch(url).then(r => { if (!r.ok) throw new Error(url); return r.json(); });

  /* --- domains.exe current champion --- */
  const hiscoreEl = document.getElementById('game-hiscore');
  if (hiscoreEl) {
    getJSON('https://domains-exe-lb.lindseylynch.workers.dev')
      .then(top => {
        hiscoreEl.textContent = top.length
          ? `Current champion: ${top[0].name} — ${fmt(top[0].score)} points, level ${top[0].level}.`
          : 'No scores yet — the leaderboard is yours for the taking.';
      })
      .catch(() => { hiscoreEl.remove(); });
  }

  const READING_GOAL = 30; // books per year

  Promise.all([getJSON('/data/books.json'), getJSON('/data/reading_stats.json')])
    .then(([books, stats]) => {
      bookshelf(document.getElementById('book-list'), books);

      // currently-reading lies flat at the end of the shelf
      getJSON('/data/currently_reading.json').then(current => {
        const shelfEl = document.getElementById('book-list');
        current.slice(0, 2).forEach(b => {
          const a = document.createElement('a');
          a.className = 'spine flat';
          a.href = b.url;
          const hash = [...b.title].reduce((h, c) => (h * 31 + c.charCodeAt(0)) >>> 0, 7);
          a.style.background = SPINE_COLS[hash % SPINE_COLS.length];
          a.style.width = Math.round(Math.max(90, Math.min(140, 90 + ((b.pages || 300) - 150) * 0.08))) + 'px';
          a.style.height = '27px';
          a.textContent = b.title.length > 15 ? b.title.slice(0, 14) + '…' : b.title;
          a.setAttribute('aria-label', `Currently reading: ${b.title} by ${b.author}`);
          const tip = `<strong>currently reading</strong><br>${esc(b.title)}<br>${esc(b.author)}`;
          a.addEventListener('mousemove', e => showTip(e, tip));
          a.addEventListener('mouseleave', hideTip);
          shelfEl.appendChild(a);
        });
      }).catch(() => {});

      // yearly goal meter
      const year = new Date().getFullYear();
      const thisYear = (stats.per_year.find(d => d.year === year) || {}).count || 0;
      const meter = document.getElementById('goal-meter');
      const pct = Math.min(100, 100 * thisYear / READING_GOAL);
      meter.innerHTML =
        `<div class="glabel"><span>${year} reading goal</span>` +
        `<span>${fmt(thisYear)} / ${READING_GOAL}${thisYear >= READING_GOAL ? ' ✦ done!' : ''}</span></div>` +
        `<div class="track"><div class="fill${pct >= 100 ? ' done' : ''}" style="width:${pct}%"></div></div>`;
      const f = stats.fun;
      document.getElementById('book-fun').textContent =
        `${fmt(f.total_books)} books and ${fmt(f.total_pages)} pages so far — ` +
        `averaging ${fmt(f.avg_pages)} pages a book. Longest: ${f.longest.title} (${fmt(f.longest.pages)} pages).`;
      columnChart(document.getElementById('books-year'),
        stats.per_year.map(d => ({
          label: d.year, count: d.count,
          tip: `<strong>${d.year}</strong> · ${fmt(d.count)} book${d.count === 1 ? '' : 's'}`
        })), { label: 'Books read per year' });
    })
    .catch(() => document.getElementById('reading').classList.add('stats-unavailable'));

  Promise.all([getJSON('/data/films.json'), getJSON('/data/watching_stats.json')])
    .then(([films, stats]) => {
      filmList(document.getElementById('film-list'), films);
      const f = stats.fun;
      document.getElementById('film-fun').textContent =
        `${fmt(f.total_films)} films logged, rated ${f.avg_rating} ★ on average.`;
      // Rating distribution: fixed half-star bins 0.5–5
      const bins = new Map();
      for (let r = 0.5; r <= 5; r += 0.5) bins.set(r, 0);
      stats.timeline.forEach(t => bins.set(t.rating, (bins.get(t.rating) || 0) + 1));
      columnChart(document.getElementById('film-ratings'),
        [...bins].map(([r, c]) => ({
          label: Number.isInteger(r) ? r : '', count: c,
          tip: `<strong>${stars(r) || r}</strong> · ${fmt(c)} film${c === 1 ? '' : 's'}`
        })), { label: 'Film rating distribution' });
    })
    .catch(() => document.getElementById('watching').classList.add('stats-unavailable'));

  getJSON('/data/nyt_stats.json')
    .then(nyt => {
      const w = nyt.wordle;
      document.getElementById('wordle-fun').textContent =
        `Wordle: ${fmt(w.games_played)} played, ${w.win_pct}% won — ` +
        `current streak ${fmt(w.current_streak)}, best ${fmt(w.max_streak)}.`;
      columnChart(document.getElementById('wordle-guesses'),
        ['1','2','3','4','5','6'].map(k => ({
          label: k, count: w.guesses[k] || 0,
          tip: `<strong>${k} guess${k === '1' ? '' : 'es'}</strong> · ${fmt(w.guesses[k] || 0)} games`
        })), { label: 'Wordle guess distribution' });
    })
    .catch(() => document.getElementById('puzzles').classList.add('stats-unavailable'));

  getJSON('/data/psn_stats.json')
    .then(psn => {
      document.getElementById('trophy-line').textContent = `Trophy level ${fmt(psn.level)}.`;
      const TCOL = { platinum: '#cfe4f0', gold: '#f4c95d', silver: '#c9ced6', bronze: '#c89b6d' };
      document.getElementById('trophy-row').innerHTML =
        Object.entries(psn.trophies).map(([kind, n]) =>
          `<span class="tchip"><i style="background:${TCOL[kind]}"></i>${fmt(n)} ${kind}</span>`).join('');
      document.getElementById('psn-list').innerHTML = psn.recent.map(g => `
        <li>
          <img src="${esc(g.icon)}" alt="" loading="lazy">
          <span class="gname">${esc(g.name)}</span>
          <span class="gmeta">${fmt(g.earned)}/${fmt(g.total)} 🏆</span>
        </li>`).join('');
    })
    .catch(() => document.getElementById('playing').classList.add('stats-unavailable'));
})();
