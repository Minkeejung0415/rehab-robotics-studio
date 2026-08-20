import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { renderToStaticMarkup } from 'react-dom/server';
import { useMappingStore } from '../../state/mappingStore';
import {
  MappingWorkspace,
  mappingFrameOptionValue,
  parseMappingFrameOptionValue,
} from './MappingWorkspace';

describe('Mapping Workspace apply contract', () => {
  it('round-trips distinct body segment and model frame identities', () => {
    const value = mappingFrameOptionValue('tibia_r', 'tibia_r_imu');
    assert.deepEqual(parseMappingFrameOptionValue(value), {
      segment: 'tibia_r',
      frame: 'tibia_r_imu',
    });
    assert.equal(parseMappingFrameOptionValue('tibia_r'), null);
  });

  it('keeps the Save then Apply workflow visible even before a model arrives', () => {
    useMappingStore.setState({
      rows: {},
      catalogModelHash: null,
      catalogModelPath: null,
      catalogFrameList: [],
      mappingRevision: 0,
      appliedRevision: 0,
      applyStatus: 'idle',
      applyError: null,
      calibrationInterlocked: false,
    });
    const markup = renderToStaticMarkup(<MappingWorkspace />);
    assert.match(markup, /Save each sensor assignment, then Apply Mapping/);
    assert.match(markup, /aria-label="Apply mapping to runtime"/);
    assert.match(markup, /Apply Mapping<\/button>/);
    assert.match(markup, /disabled=""/);
  });

  it('uses the full mapping viewport and a sticky apply footer', () => {
    const sourceRoot = join(dirname(fileURLToPath(import.meta.url)), '../..');
    const css = readFileSync(join(sourceRoot, 'styles/app.css'), 'utf8');
    const component = readFileSync(join(sourceRoot, 'components/mapping/MappingWorkspace.tsx'), 'utf8');
    assert.match(css, /\.workspace--mapping\s*{[^}]*grid-template-columns:\s*minmax\(0, 1fr\)/s);
    assert.match(component, /\.mapping-workspace\s*{[^}]*width:\s*100%[^}]*max-width:\s*none/s);
    assert.match(component, /\.mapping-workspace-footer\s*{[^}]*position:\s*sticky[^}]*bottom:\s*0/s);
  });
});
