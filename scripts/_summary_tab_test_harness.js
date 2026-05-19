// Test harness — runs Phase 2 logic against real data, no DOM dependency
// Validates: deriveMasterRatings populates correctly; waterfall counts make sense

const fs = require('fs');
const path = require('path');

// Stub the globals the module expects
global.D = {
  prices: JSON.parse(fs.readFileSync('data/prices.json')).stocks,
  filters: JSON.parse(fs.readFileSync('data/filter-results.json')).stocks,
  ssem: JSON.parse(fs.readFileSync('data/factset-ssem.json')),
  valuation: JSON.parse(fs.readFileSync('data/factset-valuation.json')),
  ticker_mapping: {}
};

// Build ticker_mapping from stock_mapping_final.json (the canonical taxonomy)
const smRaw = JSON.parse(fs.readFileSync('../stock_mapping_final.json'));
for (const tk in smRaw) {
  const td = smRaw[tk];
  if (td && td.new_industry) {
    global.D.ticker_mapping[tk] = {industry: td.new_industry, sector: td.new_sector};
  }
}

// Build filterMap globally (mimics build_dashboard.py L712)
global.filterMap = {};
for (let i = 0; i < global.D.filters.length; i++) {
  global.filterMap[global.D.filters[i].ticker] = global.D.filters[i];
}

// Stub ssemRatingMap (assume not yet computed; will be all "-" for the test)
global.ssemRatingMap = {};
// To do a more realistic test, populate with reasonable proxy: random A-F
// But for now leave empty so we see how the module behaves with no SSEM.

// Stub window for handler attachment
global.window = {};

// getTaxonomy helper used by the module
global.getTaxonomy = function(tkr) {
  const tm = global.D.ticker_mapping[tkr];
  return {industry: tm ? tm.industry : "", sector: tm ? tm.sector : ""};
};

// Now load the module
const moduleCode = fs.readFileSync('scripts/_summary_tab_module.js', 'utf8');
eval(moduleCode);

// Test 1: deriveMasterRatings populates the map
deriveMasterRatings();
const total = Object.keys(masterRatingsMap).length;
console.log(`TEST 1: masterRatingsMap populated with ${total} entries (expect 946)`);
console.assert(total === 946, "Expected 946 entries");

// Test 2: rating distributions
const dist = {tm:{},val:{}};
for (const tk in masterRatingsMap) {
  const mr = masterRatingsMap[tk];
  dist.tm[mr.tm] = (dist.tm[mr.tm] || 0) + 1;
  dist.val[mr.val] = (dist.val[mr.val] || 0) + 1;
}
console.log(`TEST 2: TM rating distribution:`);
for (const r of ['A','B','C','D','F','-']) {
  console.log(`  ${r}: ${dist.tm[r] || 0}`);
}
console.log(`TEST 2b: Valuation rating distribution:`);
for (const r of ['A','B','C','D','F','-']) {
  console.log(`  ${r}: ${dist.val[r] || 0}`);
}

// Test 3: spot-check 5 known stocks
console.log("\nTEST 3: Spot-check known tickers");
for (const tk of ['HTRO-SE', 'ABB-SE', 'AZA-SE', 'FEVR-GB', 'CARL.B-DK']) {
  const mr = masterRatingsMap[tk];
  console.log(`  ${tk}: ${JSON.stringify(mr)}`);
}

// Test 4: SUM_buildGroupAggregates - smoke test for industries
const indGroups = SUM_buildGroupAggregates("industry");
console.log(`\nTEST 4: Industries aggregated: ${indGroups.length} groups`);
console.log(`  Top 3 by TM A-or-B%:`);
for (let i = 0; i < Math.min(3, indGroups.length); i++) {
  const g = indGroups[i];
  console.log(`    ${g.groupName}: total=${g.total}, TM A-or-B=${(g.perRating.tm.pct_AB * 100).toFixed(1)}%`);
}

const secGroups = SUM_buildGroupAggregates("sector");
console.log(`\nTEST 4b: Sectors aggregated: ${secGroups.length} groups`);
console.log(`  Top 5 by TM A-or-B%:`);
for (let i = 0; i < Math.min(5, secGroups.length); i++) {
  const g = secGroups[i];
  console.log(`    ${g.groupName}: total=${g.total}, TM A-or-B=${(g.perRating.tm.pct_AB * 100).toFixed(1)}%`);
}

// Test 5: Waterfall simulation — call the helper functions used inside renderSummary
// Just verify the row counts make sense
console.log(`\nTEST 5: Waterfall simulation`);
const tickers = global.D.prices.map(p => p.ticker);
const Y = tickers.length;
const thresholds = [
  {key: "A", passSet: {A:1}},
  {key: "AB", passSet: {A:1,B:1}},
  {key: "ABC", passSet: {A:1,B:1,C:1}}
];
for (const thr of thresholds) {
  let survivors = tickers.slice();
  const cells = [];
  for (const rid of SUM_RATINGS) {
    let folded = 0;
    const next = [];
    for (const tk of survivors) {
      const mr = masterRatingsMap[tk];
      const rg = mr ? mr[rid] : "-";
      if (rg === "-") { next.push(tk); folded++; }
      else if (thr.passSet[rg]) next.push(tk);
    }
    cells.push({rating: rid, count: next.length, folded: folded});
    survivors = next;
  }
  console.log(`  ${thr.key}: ${cells.map(c => `${c.rating}=${c.count}(fold ${c.folded})`).join(' ')}`);
}

// Test 6: Filter cascade — apply all-A-filter, count survivors
console.log(`\nTEST 6: Filter cascade - count stocks rated A on TM:`);
let aTm = 0;
for (const tk in masterRatingsMap) if (masterRatingsMap[tk].tm === "A") aTm++;
console.log(`  Stocks with TM=A: ${aTm}`);
console.log(`  Stocks with TM=A AND SSEM=A: 0 (SSEM not computed in test harness)`);

console.log("\nAll tests complete.");
