import type { CanonicalSignalParseResult } from '../types/signals.js';

/** Parse one untrusted rosbridge canonical sample for its subscribed full-MAC topic. */
export function parseCanonicalSignalSample(
  _raw: unknown,
  _expectedTopicToken: string,
): CanonicalSignalParseResult {
  return { ok: false, reason: 'canonical_parser_unimplemented' };
}
