export const tradeFields = ['tradeDate', 'side', 'instrument', 'quantity', 'price'];
export const validTrade = ['2026.09.03', '판매', 'KODEX 200(A069500)', '2', '7,830'];
const invalidTrade = ['2026.02.30', '교환', 'KODEX 200(A??????)', '불명', '1,,000'];

export function rowDamageMatrix() {
  const cases = [{ name: 'complete transaction', changes: {}, kind: 'transaction' }];
  for (let i = 0; i < tradeFields.length; i += 1) {
    for (const value of [null, invalidTrade[i]]) cases.push({
      name: 'single ' + tradeFields[i] + ' ' + value, changes: { [tradeFields[i]]: value }, kind: 'incomplete_transaction',
    });
    for (let j = i + 1; j < tradeFields.length; j += 1) {
      // These sparse shapes cannot distinguish holdings or a dated numeric footer from a trade.
      const ambiguous = i === 0 && j === 1 || i === 1 && j === 2;
      cases.push({ name: 'missing pair ' + tradeFields[i] + '/' + tradeFields[j],
        changes: { [tradeFields[i]]: null, [tradeFields[j]]: null }, kind: ambiguous ? 'non_transaction' : 'incomplete_transaction' });
      cases.push({ name: 'invalid pair ' + tradeFields[i] + '/' + tradeFields[j],
        changes: { [tradeFields[i]]: invalidTrade[i], [tradeFields[j]]: invalidTrade[j] },
        kind: i === 1 && j === 2 ? 'non_transaction' : 'incomplete_transaction' });
    }
  }
  const additional = [
    ['Major A', { tradeDate: null, price: null }],
    ['Major B', { instrument: invalidTrade[2], quantity: null }],
    ['mixed side/quantity', { side: invalidTrade[1], quantity: null }],
    ['mixed price/date', { price: invalidTrade[4], tradeDate: null }],
    ['mixed instrument/date', { instrument: invalidTrade[2], tradeDate: null }],
    ['mixed quantity/side', { quantity: invalidTrade[3], side: null }],
  ];
  for (const [name, changes] of additional) cases.push({ name, changes, kind: 'incomplete_transaction' });
  cases.push({ name: 'lone side', changes: { tradeDate: null, instrument: null, quantity: null, price: null }, kind: 'non_transaction' });
  cases.push({ name: 'no cells', changes: Object.fromEntries(tradeFields.map(key => [key, null])), kind: 'non_transaction' });
  return cases;
}

export function transactionIdentityMatrix() {
  return [
    ...['합계', '잔고', '임의항목'].map(side => ({
      name: 'occupied side slot without transaction identity: ' + side,
      changes: { tradeDate: '2026.09.02', side, instrument: null, price: '7830' }, kind: 'non_transaction',
    })),
    { name: 'dense occupied slots without transaction identity',
      changes: { side: '임의항목', instrument: invalidTrade[2] }, kind: 'non_transaction' },
    { name: 'malformed side retains valid instrument anchor', changes: { side: invalidTrade[1] }, kind: 'incomplete_transaction' },
    { name: 'malformed instrument retains valid side anchor', changes: { instrument: invalidTrade[2] }, kind: 'incomplete_transaction' },
  ].map(row => ({ ...row, samePage: true }));
}
