import { cli, Strategy } from '@jackwener/opencli/registry';
import { ArgumentError, EmptyResultError } from '@jackwener/opencli/errors';

cli({
  site: 'smzdm',
  name: 'haojia',
  access: 'read',
  description: '什么值得买好价搜索',
  domain: 'search.smzdm.com',
  strategy: Strategy.PUBLIC,
  browser: true,
  args: [
    { name: 'keyword', required: true, positional: true, help: '搜索关键词' },
    { name: 'limit', type: 'int', default: 20, help: '返回数量' },
  ],
  columns: ['index', 'title', 'price', 'mall', 'time', 'url'],
  func: async (page, args) => {
    const keyword = String(args.keyword ?? '').trim();
    if (!keyword) throw new ArgumentError('keyword is required');
    const limit = Number(args.limit ?? 20);
    if (!Number.isInteger(limit) || limit <= 0) throw new ArgumentError('limit must be a positive integer');
    if (limit > 100) throw new ArgumentError('limit must be <= 100');

    const q = encodeURIComponent(keyword);
    await page.goto(`https://search.smzdm.com/?c=faxian&s=${q}&order=time&v=b`);

    const data = await page.evaluate((maxItems) => {
      const items = document.querySelectorAll('li.feed-row-wide');
      const results = [];
      items.forEach((li) => {
        if (results.length >= maxItems) return;
        const titleEl = li.querySelector('h5.feed-block-title > a')
                     || li.querySelector('h5 > a');
        if (!titleEl) return;
        const title = (titleEl.getAttribute('title') || titleEl.textContent || '').trim();
        const url = titleEl.getAttribute('href') || titleEl.href || '';

        const priceEl = li.querySelector('.z-highlight');
        let price = priceEl ? priceEl.textContent.trim() : '';
        const priceMatch = price.match(/(\d+(?:\.\d+)?)/);
        price = priceMatch ? priceMatch[1] : null;

        let mall = '';
        const mallEl = li.querySelector('.z-feed-foot-r .feed-block-extras span')
                    || li.querySelector('.z-feed-foot-r span');
        if (mallEl) mall = mallEl.textContent.trim();
        if (!mall) {
          const mallMatch = li.textContent.match(/(京东|天猫|淘宝|拼多多|唯品会|苏宁|国美|亚马逊|当当)/);
          mall = mallMatch ? mallMatch[1] : '';
        }

        let time = '';
        const timeMatch = li.textContent.match(/(\d{2})-(\d{2})\s+(\d{2}):(\d{2})/);
        time = timeMatch ? timeMatch[0] : '';

        results.push({ index: results.length + 1, title, price, mall, time, url });
      });
      return results;
    }, limit);

    if (!Array.isArray(data) || data.length === 0) {
      throw new EmptyResultError('smzdm haojia', `no results for "${keyword}"`);
    }

    return data;
  },
});
