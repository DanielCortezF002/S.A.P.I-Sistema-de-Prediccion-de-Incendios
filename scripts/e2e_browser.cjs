// Real browser against the web-v2 container; no local Streamlit imports.
const { chromium } = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
const [url, out, scenario] = process.argv.slice(2);
(async () => {
  const browser = await chromium.launch({channel: process.env.SAPI_E2E_BROWSER_CHANNEL || 'msedge'});
  try {
    const page = await browser.newPage({viewport: {width: 1440, height: 1100}});
    // Do not access external tile servers, CDNs, or credentials during the test.
    await page.route('**/*', route => {
      const target = new URL(route.request().url());
      return target.origin === new URL(url).origin ? route.continue() : route.abort();
    });
    const start = performance.now();
    let ready = false;
    for (let attempt = 0; attempt < 60; attempt++) {
      try { const r = await page.request.get(url); ready = r.ok(); } catch {}
      if (ready) break;
      await page.waitForTimeout(500);
    }
    if (!ready) throw Error('web-v2 did not become ready');
    await page.goto(url);
    await page.getByRole('button', {name: 'Actualizar ranking'}).waitFor({timeout: 90000});
    let cell_ids = [];
    if (scenario === 'down') {
      await page.getByText('No se pudo obtener el ranking del backend:', {exact: false}).waitFor({timeout: 90000});
      if (await page.getByRole('combobox', {name: 'Celda', exact: true}).count()) throw Error('Stale ranking visible');
      await page.getByText('No se ejecuta inferencia local', {exact: false}).waitFor();
    } else {
      await page.getByText('BACKEND REST', {exact: false}).first().waitFor({timeout: 90000});
      const select = page.getByRole('combobox', {name: 'Celda', exact: true});
      await select.click();
      const options = page.getByRole('option');
      await options.first().waitFor();
      const seen = new Set();
      for (let step = 0; step < 60 && seen.size < 50; step++) {
        for (const id of await options.allTextContents()) seen.add(id);
        await page.getByRole('listbox').evaluate(el => { el.scrollTop += 200; });
        await page.waitForTimeout(100);
      }
      cell_ids = [...seen];
      if (cell_ids.length !== 50) throw Error(`Expected 50 cells; got ${cell_ids.length}`);
      await page.keyboard.press('Escape');
      await page.getByText('Información técnica y fuentes', {exact: true}).click();
      await page.getByText('Inputs fingerprint:', {exact: false}).waitFor();
      await page.getByText('Ver ranking completo', {exact: true}).click();
      await page.getByTestId('stDataFrame').waitFor();
    }
    const seconds = (performance.now() - start) / 1000;
    const text = await page.locator('body').innerText();
    await page.screenshot({path: path.join(out, `browser-${scenario}.png`), fullPage:true});
    fs.writeFileSync(path.join(out, `browser-${scenario}.json`), JSON.stringify({seconds, cell_ids, text}, null, 2));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
