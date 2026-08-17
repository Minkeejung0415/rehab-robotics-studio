import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { describe, it } from 'node:test';
import { fileURLToPath } from 'node:url';

import { parseCanonicalSignalSample } from './signalContract.js';

type FixtureCase = {
  readonly id: string;
  readonly traces: readonly string[];
  readonly topic_token: string;
  readonly overrides: Readonly<Record<string, unknown>>;
  readonly remove?: readonly string[];
  readonly expect?: Readonly<Record<string, unknown>>;
  readonly reason?: string;
};

type Fixture = {
  readonly trace_decisions: Readonly<Record<string, string>>;
  readonly base_input: Readonly<Record<string, unknown>>;
  readonly accepted: readonly FixtureCase[];
  readonly rejected: readonly FixtureCase[];
  readonly measurement_cases: readonly { readonly traces: readonly string[] }[];
};

const fixturePath = join(
  dirname(fileURLToPath(import.meta.url)),
  '../../../backend/test/fixtures/signal_contract_cases.json',
);
const fixture = JSON.parse(readFileSync(fixturePath, 'utf8')) as Fixture;

function clone<T>(value: T): T {
  return structuredClone(value);
}

function applyCase(testCase: FixtureCase): Record<string, unknown> {
  const sample = clone(fixture.base_input) as Record<string, unknown>;
  Object.assign(sample, clone(testCase.overrides));
  for (const key of testCase.remove ?? []) delete sample[key];
  return sample;
}

function assertSubset(actual: unknown, expected: unknown, path = 'sample'): void {
  if (expected !== null && typeof expected === 'object' && !Array.isArray(expected)) {
    assert.ok(actual !== null && typeof actual === 'object', `${path} must be an object`);
    for (const [key, value] of Object.entries(expected as Record<string, unknown>)) {
      assertSubset((actual as Record<string, unknown>)[key], value, `${path}.${key}`);
    }
    return;
  }
  assert.deepEqual(actual, expected, path);
}

describe('canonical signal contract shared-fixture parity', () => {
  it('covers every locked D-01 through D-16 decision', () => {
    const covered = new Set(
      [...fixture.accepted, ...fixture.rejected, ...fixture.measurement_cases]
        .flatMap((testCase) => testCase.traces),
    );
    assert.deepEqual([...covered].sort(), Object.keys(fixture.trace_decisions).sort());
  });

  for (const testCase of fixture.accepted) {
    it(`accepts ${testCase.id} with the expected canonical shape`, () => {
      const result = parseCanonicalSignalSample(applyCase(testCase), testCase.topic_token);
      assert.equal(result.ok, true, result.ok ? 'expected accepted sample' : result.reason);
      if (result.ok) assertSubset(result.value, testCase.expect);
    });
  }

  for (const testCase of fixture.rejected) {
    it(`rejects ${testCase.id} with the Python reason code`, () => {
      const result = parseCanonicalSignalSample(applyCase(testCase), testCase.topic_token);
      assert.deepEqual(result, { ok: false, reason: testCase.reason });
    });
  }

  it('owns nested accepted values rather than retaining mutable input references', () => {
    const testCase = fixture.accepted[0];
    const input = applyCase(testCase);
    const result = parseCanonicalSignalSample(input, testCase.topic_token);
    assert.equal(result.ok, true, result.ok ? 'expected accepted sample' : result.reason);
    if (!result.ok) return;

    const raw = input.raw as Record<string, number>;
    const mapping = input.applied_mapping as Record<string, unknown>;
    raw.ax = 0;
    mapping.segment = 'draft_injection';
    assert.notEqual(result.value.raw.ax, raw.ax);
    assert.notEqual(result.value.applied_mapping.segment, mapping.segment);
  });
});
