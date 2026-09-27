const assert=require('node:assert/strict');
const {validDate,matchesMedia,collectionItems,sortByDate}=require('../docs/filtering.js');
const media={
  a:{id:'a',title:'Current art',source:'a',createdDate:'2026-09-24',demoStatus:'in-demo'},
  b:{id:'b',title:'Old art',source:'b',createdDate:'2026-09-26',demoStatus:'not-in-demo'},
  c:{id:'c',title:'Undated art',source:'c',createdDate:null,demoStatus:'unknown'},
};
const collection={title:'Queen',category:'Units',source:'queen',items:['a','b','c']};
assert.deepEqual(collectionItems(collection,media,{from:'2026-09-26',demo:'in-demo'}),[], 'Date and demo must match the SAME artwork');
assert.deepEqual(collectionItems(collection,media,{from:'2026-09-24',to:'2026-09-24',demo:'in-demo'}).map(x=>x.id),['a'],'Date endpoints are inclusive');
assert.equal(matchesMedia(media.c,{}),true);
assert.equal(matchesMedia(media.c,{from:'2026-01-01'}),false);
assert.equal(matchesMedia(media.a,{from:'2026-09-26',to:'2026-09-24'}),false);
assert.deepEqual(collectionItems(collection,media,{query:'Queen',demo:'in-demo'}).map(x=>x.id),['a'],'Collection-name search persists inside the collection');
assert.deepEqual(collectionItems(collection,media,{query:'old art'}).map(x=>x.id),['b'],'Artwork search works at collection level');
assert.deepEqual(sortByDate(Object.values(media),'newest').map(x=>x.id),['b','a','c']);
assert.deepEqual(sortByDate(Object.values(media),'oldest').map(x=>x.id),['a','b','c'],'Unknown dates stay last');
assert.equal(validDate('2026-02-30'),false);
assert.equal(validDate('2026-09-24'),true);
assert.equal(validDate(null),false);
console.log('Gallery date, status, search and ordering checks passed.');
