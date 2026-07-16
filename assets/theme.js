/* Wires the nav theme toggle. A tiny inline script in <head> applies the saved
   theme before first paint; this handles the button and icon. */
(function () {
  'use strict';

  const btn = document.querySelector('.theme-toggle');
  if (!btn) return;

  function current() {
    return document.documentElement.dataset.theme ||
      (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  }

  function setIcon() {
    const dark = current() === 'dark';
    btn.textContent = dark ? '☀' : '☾';
    btn.setAttribute('aria-label', dark ? 'Switch to light mode' : 'Switch to dark mode');
  }

  btn.addEventListener('click', () => {
    const next = current() === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.theme = next;
    localStorage.setItem('theme', next);
    setIcon();
  });

  setIcon();
})();
