import test, { describe, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { loginUser, getStoredToken, seedCachedSessionForTesting } from '../src/services/authService.ts';

// Polyfill localStorage for Node test runner
const storage = new Map<string, string>();
globalThis.localStorage = {
  getItem: (key: string) => storage.get(key) ?? null,
  setItem: (key: string, val: string) => { storage.set(key, String(val)); },
  removeItem: (key: string) => { storage.delete(key); },
  clear: () => { storage.clear(); },
  key: (i: number) => Array.from(storage.keys())[i] ?? null,
  get length() { return storage.size; }
} as unknown as Storage;

describe('Authentication Fallback Hardening - authService', () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    storage.clear();
    globalThis.fetch = originalFetch;
  });

  test('1. correct credentials + server available -> JWT login', async () => {
    const mockJwt = 'mock.jwt.token.123';
    globalThis.fetch = async () => {
      return new Response(JSON.stringify({
        access_token: mockJwt,
        token_type: 'bearer',
        role: 'FARMER',
        user_id: 5,
        username: 'farmer'
      }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' }
      });
    };

    const res = await loginUser('farmer', 'Farmer@MandiQ2026');
    assert.equal(res.access_token, mockJwt);
    assert.equal(res.role, 'FARMER');
    assert.equal(getStoredToken(), mockJwt);
  });

  test('2. wrong password + server 401 -> login fails (no offline session created)', async () => {
    globalThis.fetch = async () => {
      return new Response(JSON.stringify({
        detail: 'Invalid username or password.'
      }), {
        status: 401,
        headers: { 'Content-Type': 'application/json' }
      });
    };

    await assert.rejects(
      async () => {
        await loginUser('farmer', 'WrongPassword123');
      },
      (err: Error) => {
        assert.match(err.message, /Invalid username or password/);
        return true;
      }
    );

    // Stored token must NOT be manufactured
    assert.equal(getStoredToken(), null);
  });

  test('3. disabled account + server 401 -> login fails (no offline session created)', async () => {
    // Even if credentials match OFFLINE_USERS, server 401 must fail closed
    globalThis.fetch = async () => {
      return new Response(JSON.stringify({
        detail: 'User account is disabled.'
      }), {
        status: 401,
        headers: { 'Content-Type': 'application/json' }
      });
    };

    await assert.rejects(
      async () => {
        await loginUser('farmer', 'Farmer@MandiQ2026');
      },
      (err: Error) => {
        assert.match(err.message, /User account is disabled/);
        return true;
      }
    );

    // Stored token must NOT be manufactured
    assert.equal(getStoredToken(), null);
  });

  test('4. server 403 -> login fails (no offline session created)', async () => {
    globalThis.fetch = async () => {
      return new Response(JSON.stringify({
        detail: 'Access forbidden: account locked.'
      }), {
        status: 403,
        headers: { 'Content-Type': 'application/json' }
      });
    };

    await assert.rejects(
      async () => {
        await loginUser('farmer', 'Farmer@MandiQ2026');
      },
      (err: Error) => {
        assert.match(err.message, /Access forbidden/);
        return true;
      }
    );

    assert.equal(getStoredToken(), null);
  });

  test('4b. server 400 or 422 -> login fails (no offline session created)', async () => {
    globalThis.fetch = async () => {
      return new Response(JSON.stringify({
        detail: 'Invalid request payload.'
      }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' }
      });
    };

    await assert.rejects(
      async () => {
        await loginUser('farmer', 'Farmer@MandiQ2026');
      },
      (err: Error) => {
        assert.match(err.message, /Invalid request payload/);
        return true;
      }
    );

    assert.equal(getStoredToken(), null);
  });

  test('5. backend unreachable -> previously authenticated cached credentials may continue in offline mode', async () => {
    // Seed cached session from prior authentication
    seedCachedSessionForTesting('farmer', 'Farmer@MandiQ2026', {
      user_id: 5,
      username: 'farmer',
      full_name: 'Ramesh Kumar (Registered Farmer)',
      role: 'FARMER',
      mandi_id: 1,
      farmer_id: 1,
      is_active: true,
    });

    // Fetch throws network error (e.g. TypeError: Failed to fetch)
    globalThis.fetch = async () => {
      throw new TypeError('Failed to fetch');
    };

    const res = await loginUser('farmer', 'Farmer@MandiQ2026');
    assert.match(res.access_token, /^offline_pwa_token_farmer_\d+$/);
    assert.equal(res.role, 'FARMER');
    assert.equal(res.user_id, 5);
    assert.equal(getStoredToken(), res.access_token);
  });

  test('5b. backend unreachable + wrong credentials -> login fails with network error', async () => {
    seedCachedSessionForTesting('farmer', 'Farmer@MandiQ2026', {
      user_id: 5,
      username: 'farmer',
      full_name: 'Ramesh Kumar (Registered Farmer)',
      role: 'FARMER',
      mandi_id: 1,
      farmer_id: 1,
      is_active: true,
    });

    globalThis.fetch = async () => {
      throw new TypeError('Failed to fetch');
    };

    await assert.rejects(
      async () => {
        await loginUser('farmer', 'WrongPassword');
      },
      (err: Error) => {
        assert.match(err.message, /Invalid password for cached offline session/);
        return true;
      }
    );

    assert.equal(getStoredToken(), null);
  });

  test('5c. backend unreachable + un-cached user (e.g. farmer_balvinder without prior login) -> login fails and rejects offline fabrication', async () => {
    // Ensure no cached session exists
    globalThis.fetch = async () => {
      throw new TypeError('Failed to fetch');
    };

    await assert.rejects(
      async () => {
        await loginUser('farmer_balvinder', 'Farmer@MandiQ2026');
      },
      (err: Error) => {
        assert.match(err.message, /No previously authenticated offline session found/);
        return true;
      }
    );

    assert.equal(getStoredToken(), null);
  });
});
