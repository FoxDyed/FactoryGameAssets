'use strict';
// The same predicates serve collection cards and individual artwork results.
(function(root) {
  const validDate = value => /^\d{4}-\d{2}-\d{2}$/.test(value || '') &&
    !Number.isNaN(Date.parse(value)) && new Date(value).toISOString().slice(0,10) === value;
  function matchesMedia(item, filters) {
    if (filters.from && filters.to && filters.from > filters.to) return false;
    if ((filters.from || filters.to) && !item.createdDate) return false;
    if (filters.from && item.createdDate < filters.from) return false;
    if (filters.to && item.createdDate > filters.to) return false;
    return !filters.demo || item.demoStatus === filters.demo;
  }
  function collectionItems(collection, media, filters) {
    const query = (filters.query || '').trim().toLowerCase();
    const collectionMatches = `${collection.title} ${collection.category} ${collection.source}`.toLowerCase().includes(query);
    return collection.items.map(id => media[id]).filter(item => matchesMedia(item, filters) &&
      (collectionMatches || `${item.title} ${item.source}`.toLowerCase().includes(query)));
  }
  function sortByDate(entries, order, getDate = entry => entry.createdDate) {
    if (!['newest','oldest'].includes(order)) return entries;
    return [...entries].sort((a,b) => {
      const ad = getDate(a), bd = getDate(b);
      if (!ad || !bd) return ad ? -1 : bd ? 1 : 0;
      return order === 'newest' ? bd.localeCompare(ad) : ad.localeCompare(bd);
    });
  }
  const api = {validDate, matchesMedia, collectionItems, sortByDate};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.GalleryFilters = api;
})(globalThis);
