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
import { useLanguage } from '../i18n/LanguageContext';

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
  const { t } = useLanguage();
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
      <div className="bg-gradient-to-r from-slate-100 via-gray-50 to-slate-50 border border-slate-200 rounded-2xl p-6 shadow-xs">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="inline-flex items-center space-x-2 text-xs font-bold uppercase tracking-wider text-slate-800 bg-slate-200 border border-slate-300 px-3 py-1 rounded-md mb-2">
              <Database className="w-3.5 h-3.5" />
              <span>{t('walMonitor.bannerTag')}</span>
            </div>
            <h2 className="text-2xl font-black text-slate-950 tracking-tight">
              {t('walMonitor.title')}
            </h2>
            <p className="text-sm text-slate-600 mt-1 max-w-3xl">
              {t('walMonitor.description')}
            </p>
          </div>

          <div className="flex items-center space-x-3">
            <button
              onClick={() => onRefreshWAL()}
              className="p-2.5 rounded-xl bg-white hover:bg-slate-100 text-slate-700 transition border border-slate-300 hover:text-slate-900 shadow-xs cursor-pointer"
              title={t('walMonitor.refreshButton')}
            >
              <RefreshCw className={`w-4 h-4 ${isSyncing ? 'animate-spin' : ''}`} />
            </button>

            <button
              onClick={() => onTriggerSync()}
              disabled={isSyncing || pendingCount === 0 || !effectiveOnline}
              className="bg-emerald-700 hover:bg-emerald-800 disabled:bg-slate-200 disabled:text-slate-400 text-white font-bold px-4 py-2.5 rounded-xl text-sm transition flex items-center space-x-2 shadow-md shadow-emerald-700/20 cursor-pointer"
            >
              {isSyncing ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin text-white" />
                  <span>{t('walMonitor.syncingBatch')}</span>
                </>
              ) : (
                <>
                  <Send className="w-4 h-4" />
                  <span>{t('walMonitor.syncBatch')} ({pendingCount})</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Metric Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white border border-slate-200 p-4 rounded-xl shadow-xs">
          <div className="text-slate-500 text-xs font-bold uppercase tracking-wider flex items-center justify-between">
            <span>{t('walMonitor.totalMutations')}</span>
            <HardDrive className="w-4 h-4 text-slate-400" />
          </div>
          <div className="text-2xl font-black text-slate-900 mt-1.5 font-mono">{walRecords.length}</div>
          <div className="text-[10px] text-slate-500 mt-1 font-semibold">{t('walMonitor.indexedDbWal')}</div>
        </div>

        <div className="bg-white border border-slate-200 p-4 rounded-xl shadow-xs">
          <div className="text-slate-500 text-xs font-bold uppercase tracking-wider flex items-center justify-between">
            <span>{t('walMonitor.pendingSync')}</span>
            <Clock className={`w-4 h-4 ${pendingCount > 0 ? 'text-amber-600' : 'text-slate-400'}`} />
          </div>
          <div className={`text-2xl font-black mt-1.5 font-mono ${pendingCount > 0 ? 'text-amber-700' : 'text-slate-500'}`}>
            {pendingCount}
          </div>
          <div className="text-[10px] text-slate-500 mt-1 font-semibold">{t('walMonitor.queuedReplication')}</div>
        </div>

        <div className="bg-white border border-slate-200 p-4 rounded-xl shadow-xs">
          <div className="text-slate-500 text-xs font-bold uppercase tracking-wider flex items-center justify-between">
            <span>{t('walMonitor.reconciled')}</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-700" />
          </div>
          <div className="text-2xl font-black text-emerald-800 mt-1.5 font-mono">{syncedCount}</div>
          <div className="text-[10px] text-slate-500 mt-1 font-semibold">{t('walMonitor.acknowledgedServer')}</div>
        </div>

        <div className="bg-white border border-slate-200 p-4 rounded-xl shadow-xs">
          <div className="text-slate-500 text-xs font-bold uppercase tracking-wider flex items-center justify-between">
            <span>{t('walMonitor.networkRail')}</span>
            <Zap className={`w-4 h-4 ${effectiveOnline ? 'text-emerald-700' : 'text-amber-600'}`} />
          </div>
          <div className={`text-sm font-black mt-2 truncate ${effectiveOnline ? 'text-emerald-800' : 'text-amber-700'}`}>
            {effectiveOnline ? t('walMonitor.liveCloudLink') : t('walMonitor.offlineAirGap')}
          </div>
          <div className="text-[10px] text-slate-500 mt-1 font-semibold">
            {effectiveOnline ? t('walMonitor.directRestGzip') : t('walMonitor.indexedDbLocalFallback')}
          </div>
        </div>
      </div>

      {/* Offline Test Mutation Generator Panel */}
      <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm">
        <div className="flex items-center justify-between mb-3 border-b border-slate-200 pb-2.5">
          <div className="flex items-center space-x-2">
            <Zap className="w-4 h-4 text-amber-600" />
            <h3 className="text-sm font-extrabold text-slate-900">{t('walMonitor.generateMutations')}</h3>
          </div>
          <span className="text-[11px] text-slate-500 font-medium">
            {t('walMonitor.generateMutationsSubtitle')}
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
            className="bg-slate-50 hover:bg-slate-100 text-slate-800 border border-slate-300 text-xs px-3 py-2 rounded-xl font-bold transition shadow-xs active:scale-95 cursor-pointer"
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
            className="bg-slate-50 hover:bg-slate-100 text-slate-800 border border-slate-300 text-xs px-3 py-2 rounded-xl font-bold transition shadow-xs active:scale-95 cursor-pointer"
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
            className="bg-slate-50 hover:bg-slate-100 text-slate-800 border border-slate-300 text-xs px-3 py-2 rounded-xl font-bold transition shadow-xs active:scale-95 cursor-pointer"
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
            className="bg-slate-50 hover:bg-slate-100 text-slate-800 border border-slate-300 text-xs px-3 py-2 rounded-xl font-bold transition shadow-xs active:scale-95 cursor-pointer"
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
            className="bg-slate-50 hover:bg-slate-100 text-slate-800 border border-slate-300 text-xs px-3 py-2 rounded-xl font-bold transition shadow-xs active:scale-95 cursor-pointer"
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
            className="bg-slate-50 hover:bg-slate-100 text-slate-800 border border-slate-300 text-xs px-3 py-2 rounded-xl font-bold transition shadow-xs active:scale-95 cursor-pointer"
          >
            + DBT Settlement
          </button>
        </div>
      </div>

      {/* Sync Result Notification */}
      {lastSyncResult && (
        <div
          className={`p-4 rounded-xl border text-sm flex items-center justify-between shadow-xs ${
            lastSyncResult.success
              ? 'bg-emerald-50 border-emerald-300 text-emerald-950'
              : 'bg-amber-50 border-amber-300 text-amber-950'
          }`}
        >
          <div className="flex items-center space-x-2">
            {lastSyncResult.success ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-700 flex-shrink-0" />
            ) : (
              <AlertTriangle className="w-4 h-4 text-amber-700 flex-shrink-0" />
            )}
            <div>
              <span className="font-bold">
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
        <div className="flex items-center space-x-2 bg-slate-100 p-1.5 rounded-xl border border-slate-200">
          <button
            onClick={() => {
              setViewMode('WAL_LEDGER');
              setSelectedTxn(null);
            }}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition flex items-center space-x-2 ${
              viewMode === 'WAL_LEDGER'
                ? 'bg-emerald-700 text-white shadow-xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <HardDrive className="w-3.5 h-3.5" />
            <span>{t('walMonitor.tabLedger')} ({walRecords.length})</span>
          </button>

          <button
            onClick={() => {
              setViewMode('MATERIALIZED_STATE');
              setSelectedRecord(null);
            }}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition flex items-center space-x-2 ${
              viewMode === 'MATERIALIZED_STATE'
                ? 'bg-emerald-700 text-white shadow-xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <Layers className="w-3.5 h-3.5" />
            <span>{t('walMonitor.tabMaterialized')} ({localTxns.length})</span>
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
              const statusLabel =
                status === 'ALL'
                  ? t('common.all')
                  : status === 'PENDING'
                  ? t('walMonitor.statusPending')
                  : status === 'SYNCED'
                  ? t('walMonitor.statusSynced')
                  : t('walMonitor.statusFailed');
              return (
                <button
                  key={status}
                  onClick={() => setFilterStatus(status)}
                  className={`px-3 py-1 rounded-lg font-bold transition ${
                    filterStatus === status
                      ? 'bg-emerald-700 text-white shadow-xs'
                      : 'bg-white text-slate-600 hover:text-slate-900 border border-slate-300'
                  }`}
                >
                  {statusLabel} ({count})
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* Main Table: WAL Ledger View */}
      {viewMode === 'WAL_LEDGER' && (
        <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm overflow-hidden">
          <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
            <h3 className="text-base font-extrabold text-slate-900 flex items-center space-x-2">
              <HardDrive className="w-4 h-4 text-emerald-700" />
              <span>{t('walMonitor.tabLedger')} ({filteredRecords.length})</span>
            </h3>
          </div>

          {filteredRecords.length === 0 ? (
            <div className="text-center py-12 text-slate-500 text-sm">
              {t('walMonitor.noRecordsFound')}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-slate-200 text-slate-500 uppercase text-[10px] tracking-wider font-bold">
                    <th className="py-2.5 px-3">#</th>
                    <th className="py-2.5 px-3">{t('walMonitor.colMutationId')}</th>
                    <th className="py-2.5 px-3">{t('walMonitor.colEntityId')}</th>
                    <th className="py-2.5 px-3">{t('sync.targetState')}</th>
                    <th className="py-2.5 px-3">{t('walMonitor.colStatus')}</th>
                    <th className="py-2.5 px-3">{t('walMonitor.colTimestamp')}</th>
                    <th className="py-2.5 px-3 text-right">{t('common.details')}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {filteredRecords.map((record) => (
                    <tr
                      key={record.id}
                      className="hover:bg-slate-50 transition cursor-pointer"
                      onClick={() => setSelectedRecord(selectedRecord?.id === record.id ? null : record)}
                    >
                      <td className="py-3 px-3 font-mono text-slate-500">#{record.id}</td>
                      <td className="py-3 px-3 font-mono text-slate-700">
                        {record.client_mutation_id.substring(0, 18)}...
                      </td>
                      <td className="py-3 px-3 font-bold text-slate-900 font-mono">{record.transaction_id}</td>
                      <td className="py-3 px-3">
                        <span className="px-2 py-0.5 rounded bg-slate-100 border border-slate-200 text-slate-800 font-mono text-[11px] font-semibold">
                          {record.current_state}
                        </span>
                      </td>
                      <td className="py-3 px-3">
                        <span
                          className={`px-2.5 py-0.5 rounded-full text-[10px] font-black uppercase tracking-wider ${
                            record.sync_status === 'SYNCED'
                              ? 'bg-emerald-100 text-emerald-800 border border-emerald-300'
                              : record.sync_status === 'FAILED'
                              ? 'bg-rose-100 text-rose-800 border border-rose-300'
                              : 'bg-amber-100 text-amber-800 border border-amber-300'
                          }`}
                        >
                          {record.sync_status}
                        </span>
                      </td>
                      <td className="py-3 px-3 text-slate-500 font-medium">
                        {new Date(record.client_timestamp).toLocaleTimeString()}
                      </td>
                      <td className="py-3 px-3 text-slate-600 font-mono">{record.retry_count}</td>
                      <td className="py-3 px-3 text-right">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedRecord(selectedRecord?.id === record.id ? null : record);
                          }}
                          className="p-1 rounded hover:bg-slate-100 text-slate-500 hover:text-slate-900 transition"
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
        <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm overflow-hidden">
          <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
            <h3 className="text-base font-extrabold text-slate-900 flex items-center space-x-2">
              <Layers className="w-4 h-4 text-emerald-700" />
              <span>IndexedDB localTransactions State Mirror ({localTxns.length})</span>
            </h3>
            <span className="text-xs text-slate-500 font-medium">
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
                  <tr className="border-b border-slate-200 text-slate-500 uppercase text-[10px] tracking-wider font-bold">
                    <th className="py-2.5 px-3">{t('walMonitor.transactionId')}</th>
                    <th className="py-2.5 px-3">{t('walMonitor.currentState')}</th>
                    <th className="py-2.5 px-3">{t('walMonitor.farmer')}</th>
                    <th className="py-2.5 px-3">{t('walMonitor.mandi')}</th>
                    <th className="py-2.5 px-3">{t('walMonitor.syncStatus')}</th>
                    <th className="py-2.5 px-3">{t('walMonitor.lastUpdated')}</th>
                    <th className="py-2.5 px-3 text-right">{t('walMonitor.details')}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {localTxns.map((txn) => (
                    <tr
                      key={txn.transaction_id}
                      className="hover:bg-slate-50 transition cursor-pointer"
                      onClick={() => setSelectedTxn(selectedTxn?.transaction_id === txn.transaction_id ? null : txn)}
                    >
                      <td className="py-3 px-3 font-bold text-slate-900 font-mono">{txn.transaction_id}</td>
                      <td className="py-3 px-3">
                        <span className="px-2 py-0.5 rounded bg-emerald-50 border border-emerald-200 text-emerald-900 font-mono text-[11px] font-bold">
                          {txn.current_state}
                        </span>
                      </td>
                      <td className="py-3 px-3 text-slate-600">#{txn.farmer_id}</td>
                      <td className="py-3 px-3 text-slate-600">Mandi {txn.mandi_id}</td>
                      <td className="py-3 px-3">
                        <span
                          className={`px-2.5 py-0.5 rounded-full text-[10px] font-black uppercase tracking-wider ${
                            txn.sync_status === 'SYNCED'
                              ? 'bg-emerald-100 text-emerald-800 border border-emerald-300'
                              : txn.sync_status === 'FAILED'
                              ? 'bg-rose-100 text-rose-800 border border-rose-300'
                              : 'bg-amber-100 text-amber-800 border border-amber-300'
                          }`}
                        >
                          {txn.sync_status}
                        </span>
                      </td>
                      <td className="py-3 px-3 text-slate-500 font-medium">
                        {new Date(txn.last_updated_ts).toLocaleTimeString()}
                      </td>
                      <td className="py-3 px-3 text-right">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedTxn(selectedTxn?.transaction_id === txn.transaction_id ? null : txn);
                          }}
                          className="p-1 rounded hover:bg-slate-100 text-slate-500 hover:text-slate-900 transition"
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
        <div className="bg-white border-2 border-emerald-600/40 rounded-2xl p-6 shadow-sm space-y-4">
          <div className="flex items-center justify-between border-b border-slate-200 pb-3">
            <div className="flex items-center space-x-3">
              <FileCode className="w-5 h-5 text-emerald-700" />
              <div>
                <h4 className="text-sm font-extrabold text-slate-900">
                  {t('walMonitor.payloadInspector')} — #{selectedRecord.id}
                </h4>
                <p className="text-xs text-slate-500 font-mono">
                  {t('walMonitor.mutationUuid')}: {selectedRecord.client_mutation_id}
                </p>
              </div>
            </div>
            <button
              onClick={() => setSelectedRecord(null)}
              className="text-xs text-slate-400 hover:text-slate-700 p-1 rounded font-bold"
            >
              ✕
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
            <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 space-y-2 font-mono">
              <div className="text-slate-500 text-[11px] uppercase font-bold">{t('walMonitor.metadataAttributes')}</div>
              <div><span className="text-slate-500">{t('walMonitor.transactionId')}:</span> <span className="text-slate-900 font-bold">{selectedRecord.transaction_id}</span></div>
              <div><span className="text-slate-500">{t('walMonitor.colFarmerId')}:</span> <span className="text-slate-900 font-bold">{selectedRecord.farmer_id}</span></div>
              <div><span className="text-slate-500">{t('walMonitor.colMandiId')}:</span> <span className="text-slate-900 font-bold">{selectedRecord.mandi_id}</span></div>
              <div><span className="text-slate-500">{t('walMonitor.targetState')}:</span> <span className="text-emerald-800 font-bold">{selectedRecord.current_state}</span></div>
              <div><span className="text-slate-500">{t('walMonitor.hmacIntegrity')}:</span> <span className="text-slate-700 text-[10px] break-all">{selectedRecord.hmac_signature}</span></div>
            </div>

            <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 space-y-2">
              <div className="text-slate-500 text-[11px] uppercase font-bold font-mono">{t('walMonitor.parsedPayload')}</div>
              <pre className="text-slate-900 font-mono text-[11px] overflow-x-auto bg-white p-3 rounded-lg border border-slate-200 max-h-40">
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
        <div className="bg-white border-2 border-emerald-600/40 rounded-2xl p-6 shadow-sm space-y-4">
          <div className="flex items-center justify-between border-b border-slate-200 pb-3">
            <div className="flex items-center space-x-3">
              <Layers className="w-5 h-5 text-emerald-700" />
              <div>
                <h4 className="text-sm font-extrabold text-slate-900">
                  {t('walMonitor.materializedTransaction')} — {selectedTxn.transaction_id}
                </h4>
                <p className="text-xs text-slate-500 font-mono">
                  {t('walMonitor.currentState')}: {selectedTxn.current_state} | {t('walMonitor.syncStatus')}: {selectedTxn.sync_status}
                </p>
              </div>
            </div>
            <button
              onClick={() => setSelectedTxn(null)}
              className="text-xs text-slate-400 hover:text-slate-700 p-1 rounded font-bold"
            >
              ✕
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
            <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 space-y-2 font-mono">
              <div className="text-slate-500 text-[11px] uppercase font-bold">{t('walMonitor.stateAttributes')}</div>
              <div><span className="text-slate-500">{t('walMonitor.transactionId')}:</span> <span className="text-slate-900 font-bold">{selectedTxn.transaction_id}</span></div>
              <div><span className="text-slate-500">{t('walMonitor.currentState')}:</span> <span className="text-emerald-800 font-bold">{selectedTxn.current_state}</span></div>
              <div><span className="text-slate-500">{t('walMonitor.colFarmerId')}:</span> <span className="text-slate-900 font-bold">{selectedTxn.farmer_id}</span></div>
              <div><span className="text-slate-500">{t('walMonitor.colMandiId')}:</span> <span className="text-slate-900 font-bold">{selectedTxn.mandi_id}</span></div>
              <div><span className="text-slate-500">{t('walMonitor.syncStatus')}:</span> <span className="text-slate-900 font-bold">{selectedTxn.sync_status}</span></div>
              <div><span className="text-slate-500">{t('walMonitor.lastMutationId')}:</span> <span className="text-slate-700 text-[11px]">{selectedTxn.last_mutation_id || 'N/A'}</span></div>
            </div>

            <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 space-y-2">
              <div className="text-slate-500 text-[11px] uppercase font-bold font-mono">{t('walMonitor.aggregatedPayload')}</div>
              <pre className="text-slate-900 font-mono text-[11px] overflow-x-auto bg-white p-3 rounded-lg border border-slate-200 max-h-40">
                {JSON.stringify(selectedTxn.payload, null, 2)}
              </pre>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
