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

  /* --- single-series column chart --- */
  function columnChart(el, points, opts) {
    // points: [{label, count, tip}] — bars ≤24px wide, 4px rounded caps,
    // value labeled on each cap, hairline baseline, hover tooltip.
    const W = 560, H = 180, padX = 8, padBottom = 22, padTop = 18;
    const n = points.length;
    if (!n) { el.remove(); return; }
    const max = Math.max(...points.map(p => p.count));
    const band = (W - padX * 2) / n;
    const barW = Math.min(24, band * 0.6);
    const plotH = H - padTop - padBottom;
    const yFor = c => padTop + plotH * (1 - c / max);

    let svg = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(opts.label)}">`;
    svg += `<line x1="${padX}" y1="${H - padBottom}" x2="${W - padX}" y2="${H - padBottom}" class="axis"/>`;
    points.forEach((p, i) => {
      const x = padX + band * i + (band - barW) / 2;
      const y = yFor(p.count);
      const h = H - padBottom - y;
      const rr = Math.min(4, h);
      if (h > 0) {
        svg += `<path class="bar" data-i="${i}" d="M${x},${H - padBottom}
          v${-(h - rr)} q0,${-rr} ${rr},${-rr} h${barW - 2 * rr} q${rr},0 ${rr},${rr}
          v${h - rr} z"/>`;
        svg += `<text class="cap" x="${x + barW / 2}" y="${y - 5}" text-anchor="middle">${fmt(p.count)}</text>`;
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

  /* --- lists --- */
  function bookList(el, books) {
    el.innerHTML = books.map(b => `
      <li>
        <a href="${esc(b.url)}">${esc(b.title)}</a>
        <span class="media-meta">${esc(b.author)}</span>
        <span class="media-stars">${stars(b.rating)}</span>
      </li>`).join('');
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

  Promise.all([getJSON('/data/books.json'), getJSON('/data/reading_stats.json')])
    .then(([books, stats]) => {
      bookList(document.getElementById('book-list'), books);
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
        `${fmt(f.total_films)} films logged, rated ${f.avg_rating} ★ on average.` +
        (f.highest_rated ? ` Five stars went to ${f.highest_rated.title}.` : '');
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
})();
