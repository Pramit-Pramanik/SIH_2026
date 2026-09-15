import { useState, useEffect } from 'react';
import {
  Database,
  RefreshCw,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Send,
  Zap,
  HardDrive,
  FileCode,
  ChevronDown,
  ChevronRight,
  Layers
} from 'lucide-react';
import { LocalTransactionWAL, LocalTransaction, getAllLocalTransactions } from '../db/dexie';
import { SyncResult } from '../services/syncWorker';

interface WALSyncMonitorProps {
  effectiveOnline: boolean;
  walRecords: LocalTransactionWAL[];
  isSyncing: boolean;
  lastSyncResult: SyncResult | null;
  onTriggerSync: () => Promise<void>;
  onRefreshWAL: () => Promise<void>;
  onCreateMutation: (
    mutationType: string,
    state: string,
    payload: Record<string, unknown>
  ) => Promise<void>;
}

export function WALSyncMonitor({
  effectiveOnline,
  walRecords,
  isSyncing,
  lastSyncResult,
  onTriggerSync,
  onRefreshWAL,
  onCreateMutation,
}: WALSyncMonitorProps) {
  const [selectedRecord, setSelectedRecord] = useState<LocalTransactionWAL | null>(null);
  const [selectedTxn, setSelectedTxn] = useState<LocalTransaction | null>(null);
  const [filterStatus, setFilterStatus] = useState<'ALL' | 'PENDING' | 'SYNCED' | 'FAILED'>('ALL');
  const [viewMode, setViewMode] = useState<'WAL_LEDGER' | 'MATERIALIZED_STATE'>('WAL_LEDGER');
  const [localTxns, setLocalTxns] = useState<LocalTransaction[]>([]);

  useEffect(() => {
    getAllLocalTransactions().then(setLocalTxns);
  }, [walRecords]);

  const pendingCount = walRecords.filter((r) => r.sync_status === 'PENDING').length;
  const syncedCount = walRecords.filter((r) => r.sync_status === 'SYNCED').length;
  const failedCount = walRecords.filter((r) => r.sync_status === 'FAILED').length;

  const filteredRecords = walRecords.filter((r) => {
    if (filterStatus === 'ALL') return true;
    return r.sync_status === filterStatus;
  });

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="bg-slate-800/60 border border-slate-700/80 rounded-2xl p-6 backdrop-blur shadow-xl">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="inline-flex items-center space-x-2 text-xs font-semibold uppercase tracking-wider text-emerald-400 bg-emerald-950/60 border border-emerald-800/50 px-3 py-1 rounded-md mb-2">
              <Database className="w-3.5 h-3.5" />
              <span>Phase 6 — Offline Write-Ahead Log (WAL) & Gzip Batch Sync</span>
            </div>
            <h2 className="text-2xl font-bold text-white tracking-tight">
              Client Mutation Ledger & Sync Engine
            </h2>
            <p className="text-sm text-slate-400 mt-1 max-w-3xl">
              Local-first IndexedDB ledger preserves ACID mutation safety on edge devices during rural APMC power & network outages.
              Upon reconnect, mutations are Gzip-compressed, uploaded to <code className="text-emerald-400">/api/v1/sync/wal</code>, and reconciled via authoritative server monotonic sequence.
            </p>
          </div>

          <div className="flex items-center space-x-3">
            <button
              onClick={() => onRefreshWAL()}
              className="p-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 transition border border-slate-700 hover:text-white"
              title="Refresh local WAL records"
            >
              <RefreshCw className={`w-4 h-4 ${isSyncing ? 'animate-spin' : ''}`} />
            </button>

            <button
              onClick={() => onTriggerSync()}
              disabled={isSyncing || pendingCount === 0 || !effectiveOnline}
              className="bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-800 disabled:text-slate-600 text-slate-950 font-bold px-4 py-2.5 rounded-xl text-sm transition flex items-center space-x-2 shadow-lg shadow-emerald-600/20"
            >
              {isSyncing ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin text-slate-950" />
                  <span>Syncing Batch...</span>
                </>
              ) : (
                <>
                  <Send className="w-4 h-4" />
                  <span>Sync Pending WAL ({pendingCount})</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Metric Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-slate-800/40 border border-slate-700/70 p-4 rounded-xl">
          <div className="text-slate-400 text-xs font-semibold uppercase tracking-wider flex items-center justify-between">
            <span>Total Mutations</span>
            <HardDrive className="w-4 h-4 text-slate-500" />
          </div>
          <div className="text-2xl font-bold text-white mt-1.5 font-mono">{walRecords.length}</div>
          <div className="text-[10px] text-slate-500 mt-1">IndexedDB transactionsWAL</div>
        </div>

        <div className="bg-slate-800/40 border border-slate-700/70 p-4 rounded-xl">
          <div className="text-slate-400 text-xs font-semibold uppercase tracking-wider flex items-center justify-between">
            <span>Pending Sync</span>
            <Clock className={`w-4 h-4 ${pendingCount > 0 ? 'text-amber-400' : 'text-slate-500'}`} />
          </div>
          <div className={`text-2xl font-bold mt-1.5 font-mono ${pendingCount > 0 ? 'text-amber-400' : 'text-slate-400'}`}>
            {pendingCount}
          </div>
          <div className="text-[10px] text-slate-500 mt-1">Queued for server replication</div>
        </div>

        <div className="bg-slate-800/40 border border-slate-700/70 p-4 rounded-xl">
          <div className="text-slate-400 text-xs font-semibold uppercase tracking-wider flex items-center justify-between">
            <span>Reconciled</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold text-emerald-400 mt-1.5 font-mono">{syncedCount}</div>
          <div className="text-[10px] text-slate-500 mt-1">Acknowledged by server</div>
        </div>

        <div className="bg-slate-800/40 border border-slate-700/70 p-4 rounded-xl">
          <div className="text-slate-400 text-xs font-semibold uppercase tracking-wider flex items-center justify-between">
            <span>Network Rail</span>
            <Zap className={`w-4 h-4 ${effectiveOnline ? 'text-emerald-400' : 'text-amber-400'}`} />
          </div>
          <div className={`text-sm font-bold mt-2 truncate ${effectiveOnline ? 'text-emerald-300' : 'text-amber-400'}`}>
            {effectiveOnline ? 'LIVE CLOUD LINK' : 'OFFLINE AIR-GAP'}
          </div>
          <div className="text-[10px] text-slate-500 mt-1">
            {effectiveOnline ? 'Direct REST & Gzip WAL' : 'IndexedDB Local Fallback'}
          </div>
        </div>
      </div>

      {/* Offline Test Mutation Generator Panel */}
      <div className="bg-slate-800/40 border border-slate-700/70 rounded-2xl p-5 shadow-lg">
        <div className="flex items-center justify-between mb-3 border-b border-slate-700/60 pb-2.5">
          <div className="flex items-center space-x-2">
            <Zap className="w-4 h-4 text-amber-400" />
            <h3 className="text-sm font-bold text-white">Generate Local Offline WAL Mutations</h3>
          </div>
          <span className="text-[11px] text-slate-400">
            Click to inject test entries into IndexedDB without cloud connection
          </span>
        </div>

        <div className="flex flex-wrap gap-2.5">
          <button
            onClick={() =>
              onCreateMutation('GATE_CHECK_IN', 'GATE_ENTRY_VERIFIED', {
                gate_id: 1,
                lane: 'SOUTH_01',
                scanner: 'HANDHELD_QR_04',
              })
            }
            className="bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs px-3 py-2 rounded-xl font-medium transition active:scale-95"
          >
            + Gate Ingress
          </button>

          <button
            onClick={() =>
              onCreateMutation('QUALITY_ASSAY', 'QUALITY_APPROVED', {
                moisture_pct: 13.2,
                foreign_matter_pct: 0.8,
                grade: 'GRADE_A',
              })
            }
            className="bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs px-3 py-2 rounded-xl font-medium transition active:scale-95"
          >
            + Quality Assay (13.2%)
          </button>

          <button
            onClick={() =>
              onCreateMutation('GROSS_WEIGHMENT', 'WEIGHED_GROSS', {
                gross_weight_qt: 94.5,
                scale_id: 'WB-LOADCELL-01',
              })
            }
            className="bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs px-3 py-2 rounded-xl font-medium transition active:scale-95"
          >
            + Gross Scale (94.50 qt)
          </button>

          <button
            onClick={() =>
              onCreateMutation('TARE_WEIGHMENT', 'WEIGHED_TARE', {
                tare_weight_qt: 32.0,
                net_weight_qt: 62.5,
                scale_id: 'WB-LOADCELL-01',
              })
            }
            className="bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs px-3 py-2 rounded-xl font-medium transition active:scale-95"
          >
            + Tare Scale (32.00 qt / Net: 62.50 qt)
          </button>

          <button
            onClick={() =>
              onCreateMutation('BILL_GENERATION', 'BILL_GENERATED', {
                net_weight_qt: 62.5,
                rate_per_qt: 2275.0,
                invoice_amount_inr: 142187.5,
              })
            }
            className="bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs px-3 py-2 rounded-xl font-medium transition active:scale-95"
          >
            + J-Form Bill (₹142,187.50)
          </button>

          <button
            onClick={() =>
              onCreateMutation('PAYOUT_STAGING', 'PAYMENT_SETTLED', {
                amount_inr: 142187.5,
                dual_sig: true,
              })
            }
            className="bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs px-3 py-2 rounded-xl font-medium transition active:scale-95"
          >
            + DBT Settlement
          </button>
        </div>
      </div>

      {/* Sync Result Notification */}
      {lastSyncResult && (
        <div
          className={`p-4 rounded-xl border text-sm flex items-center justify-between ${
            lastSyncResult.success
              ? 'bg-emerald-950/40 border-emerald-800/50 text-emerald-300'
              : 'bg-amber-950/40 border-amber-800/50 text-amber-300'
          }`}
        >
          <div className="flex items-center space-x-2">
            {lastSyncResult.success ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
            ) : (
              <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0" />
            )}
            <div>
              <span className="font-semibold">
                {lastSyncResult.success ? 'Sync Completed: ' : 'Sync Incomplete: '}
              </span>
              Reconciled {lastSyncResult.syncedCount} of {lastSyncResult.totalPending} pending records.
              {lastSyncResult.error && (
                <span className="ml-2 text-xs opacity-80">({lastSyncResult.error})</span>
              )}
            </div>
          </div>
        </div>
      )}

      {/* View Mode Toggle: WAL Ledger vs Materialized Transactions */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center space-x-2 bg-slate-800/80 p-1.5 rounded-xl border border-slate-700">
          <button
            onClick={() => {
              setViewMode('WAL_LEDGER');
              setSelectedTxn(null);
            }}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition flex items-center space-x-2 ${
              viewMode === 'WAL_LEDGER'
                ? 'bg-emerald-600 text-slate-950 shadow-md shadow-emerald-600/30'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <HardDrive className="w-3.5 h-3.5" />
            <span>WAL Mutation Ledger ({walRecords.length})</span>
          </button>

          <button
            onClick={() => {
              setViewMode('MATERIALIZED_STATE');
              setSelectedRecord(null);
            }}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition flex items-center space-x-2 ${
              viewMode === 'MATERIALIZED_STATE'
                ? 'bg-cyan-500 text-slate-950 shadow-md shadow-cyan-500/30'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <Layers className="w-3.5 h-3.5" />
            <span>Materialized State Mirror ({localTxns.length})</span>
          </button>
        </div>

        {viewMode === 'WAL_LEDGER' && (
          <div className="flex items-center space-x-2 text-xs">
            {(['ALL', 'PENDING', 'SYNCED', 'FAILED'] as const).map((status) => {
              const count =
                status === 'ALL'
                  ? walRecords.length
                  : status === 'PENDING'
                  ? pendingCount
                  : status === 'SYNCED'
                  ? syncedCount
                  : failedCount;
              return (
                <button
                  key={status}
                  onClick={() => setFilterStatus(status)}
                  className={`px-3 py-1 rounded-lg font-semibold transition ${
                    filterStatus === status
                      ? 'bg-emerald-600 text-slate-950 shadow'
                      : 'bg-slate-800 text-slate-400 hover:text-white border border-slate-700'
                  }`}
                >
                  {status} ({count})
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* Main Table: WAL Ledger View */}
      {viewMode === 'WAL_LEDGER' && (
        <div className="bg-slate-800/50 border border-slate-700/80 rounded-2xl p-6 shadow-xl overflow-hidden">
          <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
            <h3 className="text-base font-bold text-white flex items-center space-x-2">
              <HardDrive className="w-4 h-4 text-emerald-400" />
              <span>IndexedDB transactionsWAL Mutation Stream ({filteredRecords.length})</span>
            </h3>
          </div>

          {filteredRecords.length === 0 ? (
            <div className="text-center py-12 text-slate-500 text-sm">
              No WAL mutation records match the selected filter. Use the mutation buttons above to create mutations.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-slate-700 text-slate-400 uppercase text-[10px] tracking-wider">
                    <th className="py-2.5 px-3">Local ID</th>
                    <th className="py-2.5 px-3">Client Mutation ID</th>
                    <th className="py-2.5 px-3">Transaction</th>
                    <th className="py-2.5 px-3">Target State</th>
                    <th className="py-2.5 px-3">Status</th>
                    <th className="py-2.5 px-3">Created</th>
                    <th className="py-2.5 px-3">Retries</th>
                    <th className="py-2.5 px-3 text-right">Details</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/80">
                  {filteredRecords.map((record) => (
                    <tr
                      key={record.id}
                      className="hover:bg-slate-800/40 transition cursor-pointer"
                      onClick={() => setSelectedRecord(selectedRecord?.id === record.id ? null : record)}
                    >
                      <td className="py-3 px-3 font-mono text-slate-400">#{record.id}</td>
                      <td className="py-3 px-3 font-mono text-slate-300">
                        {record.client_mutation_id.substring(0, 18)}...
                      </td>
                      <td className="py-3 px-3 font-medium text-white font-mono">{record.transaction_id}</td>
                      <td className="py-3 px-3">
                        <span className="px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-slate-300 font-mono text-[11px]">
                          {record.current_state}
                        </span>
                      </td>
                      <td className="py-3 px-3">
                        <span
                          className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${
                            record.sync_status === 'SYNCED'
                              ? 'bg-emerald-950 text-emerald-400 border border-emerald-800/40'
                              : record.sync_status === 'FAILED'
                              ? 'bg-rose-950 text-rose-400 border border-rose-800/40'
                              : 'bg-amber-950 text-amber-400 border border-amber-800/40'
                          }`}
                        >
                          {record.sync_status}
                        </span>
                      </td>
                      <td className="py-3 px-3 text-slate-400">
                        {new Date(record.client_timestamp).toLocaleTimeString()}
                      </td>
                      <td className="py-3 px-3 text-slate-400 font-mono">{record.retry_count}</td>
                      <td className="py-3 px-3 text-right">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedRecord(selectedRecord?.id === record.id ? null : record);
                          }}
                          className="p-1 rounded hover:bg-slate-700 text-slate-400 hover:text-white transition"
                        >
                          {selectedRecord?.id === record.id ? (
                            <ChevronDown className="w-4 h-4" />
                          ) : (
                            <ChevronRight className="w-4 h-4" />
                          )}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Main Table: Materialized Local Transactions View */}
      {viewMode === 'MATERIALIZED_STATE' && (
        <div className="bg-slate-800/50 border border-slate-700/80 rounded-2xl p-6 shadow-xl overflow-hidden">
          <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
            <h3 className="text-base font-bold text-white flex items-center space-x-2">
              <Layers className="w-4 h-4 text-cyan-400" />
              <span>IndexedDB localTransactions State Mirror ({localTxns.length})</span>
            </h3>
            <span className="text-xs text-slate-400">
              Materialized state table queried directly by stations during offline operation
            </span>
          </div>

          {localTxns.length === 0 ? (
            <div className="text-center py-12 text-slate-500 text-sm">
              No materialized transactions found in IndexedDB. Mutations will populate this state boundary.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-slate-700 text-slate-400 uppercase text-[10px] tracking-wider">
                    <th className="py-2.5 px-3">Transaction ID</th>
                    <th className="py-2.5 px-3">Current State</th>
                    <th className="py-2.5 px-3">Farmer</th>
                    <th className="py-2.5 px-3">Mandi</th>
                    <th className="py-2.5 px-3">Sync Status</th>
                    <th className="py-2.5 px-3">Last Updated</th>
                    <th className="py-2.5 px-3 text-right">Details</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/80">
                  {localTxns.map((txn) => (
                    <tr
                      key={txn.transaction_id}
                      className="hover:bg-slate-800/40 transition cursor-pointer"
                      onClick={() => setSelectedTxn(selectedTxn?.transaction_id === txn.transaction_id ? null : txn)}
                    >
                      <td className="py-3 px-3 font-medium text-white font-mono">{txn.transaction_id}</td>
                      <td className="py-3 px-3">
                        <span className="px-2 py-0.5 rounded bg-slate-900 border border-cyan-800/50 text-cyan-300 font-mono text-[11px]">
                          {txn.current_state}
                        </span>
                      </td>
                      <td className="py-3 px-3 text-slate-300">#{txn.farmer_id}</td>
                      <td className="py-3 px-3 text-slate-300">Mandi {txn.mandi_id}</td>
                      <td className="py-3 px-3">
                        <span
                          className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${
                            txn.sync_status === 'SYNCED'
                              ? 'bg-emerald-950 text-emerald-400 border border-emerald-800/40'
                              : txn.sync_status === 'FAILED'
                              ? 'bg-rose-950 text-rose-400 border border-rose-800/40'
                              : 'bg-amber-950 text-amber-400 border border-amber-800/40'
                          }`}
                        >
                          {txn.sync_status}
                        </span>
                      </td>
                      <td className="py-3 px-3 text-slate-400">
                        {new Date(txn.last_updated_ts).toLocaleTimeString()}
                      </td>
                      <td className="py-3 px-3 text-right">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedTxn(selectedTxn?.transaction_id === txn.transaction_id ? null : txn);
                          }}
                          className="p-1 rounded hover:bg-slate-700 text-slate-400 hover:text-white transition"
                        >
                          {selectedTxn?.transaction_id === txn.transaction_id ? (
                            <ChevronDown className="w-4 h-4" />
                          ) : (
                            <ChevronRight className="w-4 h-4" />
                          )}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Record Payload Inspector Drawer (WAL) */}
      {selectedRecord && viewMode === 'WAL_LEDGER' && (
        <div className="bg-slate-800/60 border-2 border-indigo-500/40 rounded-2xl p-6 shadow-2xl space-y-4">
          <div className="flex items-center justify-between border-b border-slate-700 pb-3">
            <div className="flex items-center space-x-3">
              <FileCode className="w-5 h-5 text-indigo-400" />
              <div>
                <h4 className="text-sm font-bold text-white">
                  WAL Payload Inspector — Record #{selectedRecord.id}
                </h4>
                <p className="text-xs text-slate-400 font-mono">
                  Mutation UUID: {selectedRecord.client_mutation_id}
                </p>
              </div>
            </div>
            <button
              onClick={() => setSelectedRecord(null)}
              className="text-xs text-slate-400 hover:text-white p-1 rounded"
            >
              ✕
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
            <div className="bg-slate-900/80 p-4 rounded-xl border border-slate-800 space-y-2 font-mono">
              <div className="text-slate-400 text-[11px] uppercase font-semibold">Metadata Attributes</div>
              <div><span className="text-slate-500">Transaction ID:</span> <span className="text-white">{selectedRecord.transaction_id}</span></div>
              <div><span className="text-slate-500">Farmer ID:</span> <span className="text-white">{selectedRecord.farmer_id}</span></div>
              <div><span className="text-slate-500">Mandi ID:</span> <span className="text-white">{selectedRecord.mandi_id}</span></div>
              <div><span className="text-slate-500">Target State:</span> <span className="text-emerald-400">{selectedRecord.current_state}</span></div>
              <div><span className="text-slate-500">HMAC Integrity:</span> <span className="text-indigo-300 text-[10px] break-all">{selectedRecord.hmac_signature}</span></div>
            </div>

            <div className="bg-slate-900/80 p-4 rounded-xl border border-slate-800 space-y-2">
              <div className="text-slate-400 text-[11px] uppercase font-semibold font-mono">Parsed Payload JSON</div>
              <pre className="text-emerald-300 font-mono text-[11px] overflow-x-auto bg-slate-950 p-3 rounded-lg border border-slate-800/80 max-h-40">
                {JSON.stringify(
                  selectedRecord.payload || JSON.parse(selectedRecord.payload_json || '{}'),
                  null,
                  2
                )}
              </pre>
            </div>
          </div>
        </div>
      )}

      {/* Materialized Transaction Inspector Drawer */}
      {selectedTxn && viewMode === 'MATERIALIZED_STATE' && (
        <div className="bg-slate-800/60 border-2 border-cyan-500/40 rounded-2xl p-6 shadow-2xl space-y-4">
          <div className="flex items-center justify-between border-b border-slate-700 pb-3">
            <div className="flex items-center space-x-3">
              <Layers className="w-5 h-5 text-cyan-400" />
              <div>
                <h4 className="text-sm font-bold text-white">
                  Materialized Transaction — {selectedTxn.transaction_id}
                </h4>
                <p className="text-xs text-slate-400 font-mono">
                  State: {selectedTxn.current_state} | Sync: {selectedTxn.sync_status}
                </p>
              </div>
            </div>
            <button
              onClick={() => setSelectedTxn(null)}
              className="text-xs text-slate-400 hover:text-white p-1 rounded"
            >
              ✕
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
            <div className="bg-slate-900/80 p-4 rounded-xl border border-slate-800 space-y-2 font-mono">
              <div className="text-slate-400 text-[11px] uppercase font-semibold">State Attributes</div>
              <div><span className="text-slate-500">Transaction ID:</span> <span className="text-white">{selectedTxn.transaction_id}</span></div>
              <div><span className="text-slate-500">Current State:</span> <span className="text-cyan-300 font-bold">{selectedTxn.current_state}</span></div>
              <div><span className="text-slate-500">Farmer ID:</span> <span className="text-white">{selectedTxn.farmer_id}</span></div>
              <div><span className="text-slate-500">Mandi ID:</span> <span className="text-white">{selectedTxn.mandi_id}</span></div>
              <div><span className="text-slate-500">Sync Status:</span> <span className="text-white">{selectedTxn.sync_status}</span></div>
              <div><span className="text-slate-500">Last Mutation ID:</span> <span className="text-slate-300 text-[11px]">{selectedTxn.last_mutation_id || 'N/A'}</span></div>
            </div>

            <div className="bg-slate-900/80 p-4 rounded-xl border border-slate-800 space-y-2">
              <div className="text-slate-400 text-[11px] uppercase font-semibold font-mono">Aggregated Payload JSON</div>
              <pre className="text-cyan-300 font-mono text-[11px] overflow-x-auto bg-slate-950 p-3 rounded-lg border border-slate-800/80 max-h-40">
                {JSON.stringify(selectedTxn.payload, null, 2)}
              </pre>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
