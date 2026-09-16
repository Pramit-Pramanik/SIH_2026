/**
 * MandiQ Offline Cryptographic & Structural Gate Verification Service.
 *
 * Implements client-side structural validation, invariant checks, and provisional
 * entry authorization during network blackouts without exposing server HMAC secret keys.
 */

export interface GatePassToken {
  transaction_id: string;
  farmer_id: number;
  mandi_id: number;
  slot_id: number;
  scheduled_date: string;
  start_time?: string;
  end_time?: string;
  requested_qty_qt?: number;
  token_signature: string;
}

export interface OfflineVerificationResult {
  isVerified: boolean;
  verificationMode: 'OFFLINE_LOCAL_PROVISIONAL';
  error?: string;
  warning?: string;
  timestamp: number;
}

const HEX_64_REGEX = /^[0-9a-fA-F]{64}$/;
const UUID_REGEX = /^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$/;
const DATE_REGEX = /^\d{4}-\d{2}-\d{2}$/;

/**
 * Validates cryptographic signature formatting and field invariants of a Gate Pass Token.
 */
export function validateGatePassTokenStructure(token: GatePassToken): { valid: boolean; error?: string } {
  if (!token.transaction_id || typeof token.transaction_id !== 'string') {
    return { valid: false, error: 'Missing or invalid transaction_id' };
  }

  if (!UUID_REGEX.test(token.transaction_id) && token.transaction_id.length < 10) {
    return { valid: false, error: 'Malformed transaction_id format' };
  }

  if (!token.farmer_id || typeof token.farmer_id !== 'number' || token.farmer_id <= 0) {
    return { valid: false, error: 'Invalid farmer_id in token' };
  }

  if (!token.mandi_id || typeof token.mandi_id !== 'number' || token.mandi_id <= 0) {
    return { valid: false, error: 'Invalid mandi_id in token' };
  }

  if (!token.slot_id || typeof token.slot_id !== 'number' || token.slot_id <= 0) {
    return { valid: false, error: 'Invalid slot_id in token' };
  }

  if (!token.scheduled_date || !DATE_REGEX.test(token.scheduled_date)) {
    return { valid: false, error: 'Invalid or missing scheduled_date (expected YYYY-MM-DD)' };
  }

  if (token.requested_qty_qt !== undefined && (typeof token.requested_qty_qt !== 'number' || token.requested_qty_qt <= 0)) {
    return { valid: false, error: 'Invalid requested quantity: must be positive numeric quintals' };
  }

  if (!token.token_signature || typeof token.token_signature !== 'string') {
    return { valid: false, error: 'Missing cryptographic token signature' };
  }

  if (!HEX_64_REGEX.test(token.token_signature)) {
    return {
      valid: false,
      error: `Invalid HMAC signature format: expected 64-character hexadecimal digest, received ${token.token_signature.length} chars`
    };
  }

  return { valid: true };
}

/**
 * Verifies a Gate Pass during offline conditions.
 * Enforces local domain invariants (mandi match, date validity, ceiling checks)
 * and issues a provisional offline verification verdict.
 */
export function verifyOfflineGateEntry(
  token: GatePassToken,
  options?: {
    terminalMandiId?: number;
    farmerCeilingQt?: number;
    cumulativeDeliveredQt?: number;
  }
): OfflineVerificationResult {
  const timestamp = Date.now();

  // 1. Structural and cryptographic format verification
  const structuralCheck = validateGatePassTokenStructure(token);
  if (!structuralCheck.valid) {
    return {
      isVerified: false,
      verificationMode: 'OFFLINE_LOCAL_PROVISIONAL',
      error: `Structural Cryptographic Failure: ${structuralCheck.error}`,
      timestamp
    };
  }

  // 2. Mandi check
  if (options?.terminalMandiId && token.mandi_id !== options.terminalMandiId) {
    return {
      isVerified: false,
      verificationMode: 'OFFLINE_LOCAL_PROVISIONAL',
      error: `Mandi Mismatch: Gate pass is registered for Mandi ID ${token.mandi_id}, but this terminal is Mandi ID ${options.terminalMandiId}`,
      timestamp
    };
  }

  // 3. Local yield ceiling check (if known locally)
  if (options?.farmerCeilingQt !== undefined && token.requested_qty_qt !== undefined) {
    const delivered = options.cumulativeDeliveredQt || 0;
    const projectedTotal = delivered + token.requested_qty_qt;
    if (projectedTotal > options.farmerCeilingQt) {
      return {
        isVerified: false,
        verificationMode: 'OFFLINE_LOCAL_PROVISIONAL',
        error: `Yield Ceiling Exceeded: ${projectedTotal} qt would exceed farmer ceiling of ${options.farmerCeilingQt} qt`,
        timestamp
      };
    }
  }

  return {
    isVerified: true,
    verificationMode: 'OFFLINE_LOCAL_PROVISIONAL',
    timestamp
  };
}
