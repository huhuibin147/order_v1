// 提取 admin.html 中 renderItems 的聚合逻辑做单测
// 用法：node test_items_view.js
const assert = require('node:assert/strict');

// 模拟菜单
const MENU = {
  dishes: [
    { id: 'd_noodle_beef', name: '红烧牛肉面' },
    { id: 'd_fried_chicken', name: '炸鸡' },
    { id: 'd_noodle_pork', name: '肉末拌面' },
    { id: 'd_cola', name: '可乐' },
  ],
  addons: [
    { id: 'a_egg', name: '加蛋' },
    { id: 'a_vege', name: '加蔬菜' },
  ],
};

function dishName(id) { return (MENU.dishes.find(d => d.id === id) || {}).name || '未知菜品'; }
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
    bump('dish:' + o.dish_id, dishName(o.dish_id), '菜品', o.user_no);
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

// ---- 测试用例 ----
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

console.log('\nALL PASS');
