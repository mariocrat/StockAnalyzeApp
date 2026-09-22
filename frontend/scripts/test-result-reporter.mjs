// A single structured result per explicit file. Never count nested cases twice.
import { entrypoint, finishGuard } from './test-entrypoint-guard.mjs';

export default async function* reporter(events) {
  const cases = [];
  const nested = [];
  const errors = [];
  let summary = false;
  for await (const { type, data } of events) {
    if (type === 'test:summary') summary = true;
    if (type !== 'test:pass' && type !== 'test:fail') continue;
    const record = { id: `${entrypoint.file}::${data.name}`, name: data.name,
      status: data.skip ? 'SKIP' : type === 'test:pass' ? 'PASS' : 'FAIL',
      reason: typeof data.skip === 'string' ? data.skip : null };
    if (data.todo) errors.push('unexpected todo');
    if (data.details?.type === 'suite') errors.push('unexpected suite');
    (data.nesting === 0 ? cases : nested).push(record);
  }
  let boundary;
  try {
    boundary = finishGuard();
  } catch {
    boundary = { restored: false, patches_restored: false, unexpected: null, violations: [] };
    errors.push('guard restoration failed');
  }
  const passed = summary && cases.length > 0 && errors.length === 0 &&
    cases.every(record => record.status !== 'FAIL') && boundary.unexpected === 0 &&
    boundary.restored && boundary.patches_restored;
  if (!passed) process.exitCode = 1;
  yield `NODE_TEST_RESULT ${JSON.stringify({ version: 1, ...entrypoint, cases, nested,
    errors, summary, ...boundary, passed })}\n`;
}
