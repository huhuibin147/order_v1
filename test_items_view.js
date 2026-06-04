// 提取 admin.html 中 renderItems 的聚合逻辑做单测
// 用法：node test_items_view.js
const assert = require('node:assert/strict');

// 模拟菜单（带 base_options 的双拼碗）
const MENU = {
  dishes: [
    { id: 'd_noodle_beef', name: '红烧牛肉面' },
    { id: 'd_fried_chicken', name: '炸鸡' },
    { id: 'd_noodle_pork', name: '肉末拌面' },
    { id: 'd_cola', name: '可乐' },
    { id: 'd_chicken_beef', name: '鸡胸肉牛肉双拼碗', base_options: ['杂粮饭', '意面', '荞麦面'] },
  ],
  sauces: [
    { id: 's_beef_chili', name: '牛肉辣酱' },
    { id: 's_black_pepper', name: '黑胡椒汁' },
  ],
  addons: [
    { id: 'a_egg', name: '加蛋' },
    { id: 'a_vege', name: '加蔬菜' },
  ],
};

function dishName(id) { return (MENU.dishes.find(d => d.id === id) || {}).name || '未知菜品'; }
// 与 admin.html displayName 一致：菜名（主食底）
function displayName(o) {
  const d = MENU.dishes.find(x => x.id === o.dish_id) || {};
  return d.name + (o.base ? `（${o.base}）` : '');
}
function sauceName(id) { return (MENU.sauces.find(s => s.id === id) || {}).name; }
function addonName(id) { return (MENU.addons.find(a => a.id === id) || {}).name; }

// 与 admin.html renderItems 一致的聚合函数
function aggregate(orders) {
  const map = {};
  function bump(key, name, tag, userNo) {
    if (!map[key]) map[key] = { name, tag, count: 0, userNos: new Set() };
    map[key].count += 1;
    map[key].userNos.add(userNo);
  }
  orders.forEach(o => {
    // 关键：同菜不同底在聚合中拆成两条独立行
    bump('dish:' + o.dish_id + ':' + (o.base || ''), displayName(o), '菜品', o.user_no);
    (o.sauce_ids || []).forEach(sid => {
      bump('sauce:' + sid, sauceName(sid), '酱料', o.user_no);
    });
    (o.addon_ids || []).forEach(aid => {
      bump('addon:' + aid, addonName(aid), '附加品', o.user_no);
    });
  });
  const rows = Object.values(map).map(r => ({
    name: r.name, tag: r.tag, count: r.count,
    userNos: [...r.userNos].sort((a, b) => a - b),
  }));
  rows.sort((a, b) => b.count - a.count || a.name.localeCompare(b.name, 'zh-Hans-CN'));
  const totalItems = rows.reduce((s, r) => s + r.count, 0);
  return { rows, totalItems };
}

// ---- 主测试用例 ----
const orders = [
  { dish_id: 'd_noodle_beef', addon_ids: ['a_egg'], user_no: 1, user_name: '小王' },
  { dish_id: 'd_fried_chicken', addon_ids: [], user_no: 2, user_name: '小李' },
  { dish_id: 'd_cola', addon_ids: [], user_no: 1, user_name: '小王' },
  { dish_id: 'd_noodle_pork', addon_ids: ['a_vege'], user_no: 3, user_name: '小张' },
  { dish_id: 'd_fried_chicken', addon_ids: [], user_no: 2, user_name: '小李' },
];

// 删除可乐后
const filtered = orders.filter(o => o.dish_id !== 'd_cola');
const { rows, totalItems } = aggregate(filtered);

console.log('rows =', rows);
console.log('totalItems =', totalItems);

assert.equal(rows.length, 5, 'should have 5 distinct items');
assert.equal(totalItems, 6, 'total items = 4 dishes + 2 addons');

// 炸鸡应该排第一，count=2
const fried = rows[0];
assert.equal(fried.name, '炸鸡', 'top item is fried chicken');
assert.equal(fried.count, 2, 'fried chicken count = 2');
assert.deepEqual(fried.userNos, [2], 'only user 2');

// 验证所有行（按 count desc，再按拼音 asc；红<加<肉）
const expected = [
  { name: '炸鸡', count: 2, userNos: [2] },
  { name: '红烧牛肉面', count: 1, userNos: [1] },
  { name: '加蛋', count: 1, userNos: [1] },
  { name: '加蔬菜', count: 1, userNos: [3] },
  { name: '肉末拌面', count: 1, userNos: [3] },
];
rows.forEach((r, i) => {
  assert.equal(r.name, expected[i].name, `row[${i}].name`);
  assert.equal(r.count, expected[i].count, `row[${i}].count`);
  assert.deepEqual(r.userNos, expected[i].userNos, `row[${i}].userNos`);
});

// 同一人同一菜下多个附加品
const dup = aggregate([
  { dish_id: 'd_noodle_beef', addon_ids: ['a_egg', 'a_egg'], user_no: 1, user_name: '小王' },
]);
assert.equal(dup.rows.find(r => r.name === '加蛋').count, 2, 'duplicate addons counted twice');
assert.deepEqual(dup.rows.find(r => r.name === '加蛋').userNos, [1], 'unique user nos even with duplicates');

// ---- 重点：主食底聚合 ----
// 3 个双拼碗，不同底，独立成 3 行
const baseOrders = [
  { dish_id: 'd_chicken_beef', base: '杂粮饭', addon_ids: [], user_no: 1, user_name: '小王' },
  { dish_id: 'd_chicken_beef', base: '意面',   addon_ids: [], user_no: 1, user_name: '小王' },
  { dish_id: 'd_chicken_beef', base: '意面',   addon_ids: [], user_no: 2, user_name: '小李' },
  { dish_id: 'd_chicken_beef', base: '荞麦面', addon_ids: [], user_no: 3, user_name: '小张' },
];
const baseAgg = aggregate(baseOrders);
console.log('base rows =', baseAgg.rows);
assert.equal(baseAgg.rows.length, 3, '3 different bases = 3 rows');
const 意面 = baseAgg.rows.find(r => r.name === '鸡胸肉牛肉双拼碗（意面）');
assert.ok(意面, 'display name should be 鸡胸肉牛肉双拼碗（意面）');
assert.equal(意面.count, 2, '意面 count = 2');
assert.deepEqual(意面.userNos, [1, 2], '意面 from user 1 and 2');
const 杂粮饭 = baseAgg.rows.find(r => r.name === '鸡胸肉牛肉双拼碗（杂粮饭）');
assert.equal(杂粮饭.count, 1, '杂粮饭 count = 1');
const 荞麦面 = baseAgg.rows.find(r => r.name === '鸡胸肉牛肉双拼碗（荞麦面）');
assert.equal(荞麦面.count, 1, '荞麦面 count = 1');

// 不带 base 的菜保持原状
const noBase = aggregate([
  { dish_id: 'd_noodle_beef', base: '', addon_ids: [], user_no: 1, user_name: '小王' },
]);
assert.equal(noBase.rows[0].name, '红烧牛肉面', 'no base_options -> plain name');
assert.equal(noBase.rows[0].name.includes('（）'), false, 'no empty parenthesis');

// ---- 重点：酱料聚合 ----
const sauceOrders = [
  { dish_id: 'd_noodle_beef', sauce_ids: ['s_beef_chili'],     addon_ids: [], user_no: 1, user_name: '小王' },
  { dish_id: 'd_noodle_pork', sauce_ids: ['s_beef_chili'],     addon_ids: [], user_no: 1, user_name: '小王' },
  { dish_id: 'd_fried_chicken', sauce_ids: ['s_black_pepper'], addon_ids: [], user_no: 2, user_name: '小李' },
  { dish_id: 'd_chicken_beef', base: '意面', sauce_ids: ['s_black_pepper'], addon_ids: [], user_no: 3, user_name: '小张' },
];
const sauceAgg = aggregate(sauceOrders);
console.log('sauce rows =', sauceAgg.rows);
// 4 个菜品 + 2 种酱料 = 6 行
assert.equal(sauceAgg.rows.length, 6, '4 dishes + 2 sauces = 6 rows');
const 牛肉辣酱 = sauceAgg.rows.find(r => r.name === '牛肉辣酱');
assert.ok(牛肉辣酱, 'sauce 牛肉辣酱 should exist');
assert.equal(牛肉辣酱.tag, '酱料', 'tag = 酱料');
assert.equal(牛肉辣酱.count, 2, '牛肉辣酱 count = 2');
assert.deepEqual(牛肉辣酱.userNos, [1], '牛肉辣酱 only from user 1');
const 黑胡椒汁 = sauceAgg.rows.find(r => r.name === '黑胡椒汁');
assert.equal(黑胡椒汁.count, 2, '黑胡椒汁 count = 2');
assert.deepEqual(黑胡椒汁.userNos, [2, 3], '黑胡椒汁 from user 2 and 3');

// 多人点同一道菜用同一种酱料：sauce 行的 userNos 是去重的 user_no 集合
const dupSauce = aggregate([
  { dish_id: 'd_noodle_beef', sauce_ids: ['s_beef_chili'], addon_ids: [], user_no: 1, user_name: '小王' },
  { dish_id: 'd_noodle_pork', sauce_ids: ['s_beef_chili'], addon_ids: [], user_no: 1, user_name: '小王' },
]);
assert.equal(dupSauce.rows.find(r => r.name === '牛肉辣酱').count, 2, 'same sauce from same user across dishes counted');
assert.deepEqual(dupSauce.rows.find(r => r.name === '牛肉辣酱').userNos, [1], 'userNos deduped to [1]');

console.log('\nALL PASS');
