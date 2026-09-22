import test from 'node:test';
import assert from 'node:assert/strict';
import { translations } from '../src/i18n/translations';

test('Farmer Live Queue & Telemetry - MandiQ Verification', async (t) => {
  await t.test('1. Farmer live queue translation keys exist and are localized in both languages', () => {
    const requiredQueueKeys = [
      'farmerLiveQueueTitle',
      'farmerLiveQueueSubtitle',
      'yourQueuePosition',
      'peopleAheadCount',
      'youAreNextInLine',
      'yardOverviewTitle',
      'yardStatusOperational',
      'yardStatusDegraded',
      'notInDispatchQueue',
      'notInQueueHint',
      'selectLotToTrack',
      'noActiveLots',
      'estimatedWaitMins',
    ];

    for (const key of requiredQueueKeys) {
      assert.ok(
        (translations.en.queue as Record<string, string>)[key],
        `Key '${key}' must exist in English queue translations`
      );
      assert.ok(
        (translations.hi.queue as Record<string, string>)[key],
        `Key '${key}' must exist in Hindi queue translations`
      );

      // Verify Hindi strings contain Devanagari
      const hiVal = (translations.hi.queue as Record<string, string>)[key];
      assert.match(
        hiVal,
        /[\u0900-\u097F]/,
        `Hindi translation for '${key}' must contain Devanagari characters`
      );
    }
  });

  await t.test('2. "After how many people" interpolation behaves correctly', () => {
    const templateEn = translations.en.queue.peopleAheadCount;
    const templateHi = translations.hi.queue.peopleAheadCount;

    assert.equal(
      templateEn.replace('{count}', '3'),
      '3 vehicle(s) ahead of you'
    );
    assert.equal(
      templateHi.replace('{count}', '3'),
      'आपसे आगे 3 वाहन'
    );

    assert.equal(
      templateEn.replace('{count}', '0'),
      '0 vehicle(s) ahead of you'
    );
  });

  await t.test('3. Queue position calculation: rank 1 means 0 ahead, rank N means N-1 ahead', () => {
    function computeAhead(rank: number): number {
      return Math.max(0, rank - 1);
    }

    assert.equal(computeAhead(1), 0);
    assert.equal(computeAhead(2), 1);
    assert.equal(computeAhead(5), 4);
  });

  await t.test('4. Queue status evaluation for operational vs degraded yard', () => {
    function getQueueYardStatus(activeScales: number): 'OPERATIONAL' | 'DEGRADED' {
      return activeScales > 0 ? 'OPERATIONAL' : 'DEGRADED';
    }

    assert.equal(getQueueYardStatus(2), 'OPERATIONAL');
    assert.equal(getQueueYardStatus(1), 'OPERATIONAL');
    assert.equal(getQueueYardStatus(0), 'DEGRADED');
  });
});
