import { useState } from 'react';
import { useLanguage } from '../i18n/LanguageContext';

interface USSDPhoneModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function USSDPhoneModal({ isOpen, onClose }: USSDPhoneModalProps) {
  const { t } = useLanguage();
  const [phoneNumber, setPhoneNumber] = useState('9876543210');
  const [currentText, setCurrentText] = useState('*247#');
  const [history, setHistory] = useState<string>('');
  const [screenMessage, setScreenMessage] = useState<string>(() => t('ussd.dialPrompt'));
  const [sessionActive, setSessionActive] = useState<boolean>(false);
  const [sessionId, setSessionId] = useState<string>(() => `ussd-sess-${Date.now()}`);
  const [loading, setLoading] = useState<boolean>(false);

  if (!isOpen) return null;

  const handleSend = async (overrideText?: string) => {
    const textToSend = overrideText !== undefined ? overrideText : currentText;
    if (!textToSend) return;

    setLoading(true);
    try {
      let cumulativeInput = '';
      if (!sessionActive && textToSend === '*247#') {
        // New session
        const newSessId = `ussd-sess-${Date.now()}`;
        setSessionId(newSessId);
        setSessionActive(true);
        setHistory('');
        cumulativeInput = '';
      } else {
        // Appending to session
        cumulativeInput = history ? `${history}*${textToSend}` : textToSend;
      }

      const response = await fetch('/api/v1/ussd/session', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        body: JSON.stringify({
          session_id: sessionId,
          phone_number: phoneNumber,
          service_code: '*247#',
          text: cumulativeInput
        })
      });

      if (!response.ok) {
        setScreenMessage(`Error HTTP ${response.status}:\n${t('ussd.networkTimeout')}`);
        setSessionActive(false);
        return;
      }

      const data = await response.json();
      setScreenMessage(data.message.replace(/^CON\s+/, '').replace(/^END\s+/, ''));
      setSessionActive(data.continue_session);

      if (data.continue_session) {
        setHistory(cumulativeInput);
      } else {
        setHistory('');
      }
      setCurrentText('');
    } catch {
      setScreenMessage(t('ussd.networkTimeout'));
      setSessionActive(false);
    } finally {
      setLoading(false);
    }
  };

  const handleKeypadPress = (val: string) => {
    setCurrentText(prev => prev + val);
  };

  const handleClear = () => {
    setCurrentText('');
  };

  const handleEndSession = () => {
    setSessionActive(false);
    setHistory('');
    setCurrentText('*247#');
    setScreenMessage(t('ussd.sessionEnded'));
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4">
      <div className="relative w-full max-w-sm bg-white border-2 border-slate-200 rounded-3xl p-6 shadow-2xl flex flex-col items-center">
        {/* Close Button */}
        <button
          onClick={onClose}
          aria-label={t('common.close')}
          className="absolute top-4 right-4 text-slate-400 hover:text-slate-700 text-lg font-bold p-1 rounded cursor-pointer"
        >
          &times;
        </button>

        {/* Feature Phone Title */}
        <div className="text-center mb-4">
          <div className="text-xs font-extrabold text-emerald-800 uppercase tracking-wider">
            {t('ussd.simulatorTitle')}
          </div>
          <div className="text-sm font-black text-slate-900">
            {t('ussd.simulatorSubtitle')}
          </div>
        </div>

        {/* Phone Body */}
        <div className="w-full bg-slate-50 border-2 border-slate-200 rounded-2xl p-4 shadow-inner">
          {/* LCD Screen (Retro High Contrast Agrarian Green) */}
          <div className="bg-[#0b1a10] border-2 border-[#16361f] rounded-xl p-3 font-mono text-emerald-400 text-xs min-h-[160px] max-h-[220px] overflow-y-auto flex flex-col justify-between shadow-inner">
            <div className="flex justify-between border-b border-emerald-900/60 pb-1 text-[10px] text-emerald-500 font-bold">
              <span>GSM-4G [||||]</span>
              <span>{sessionActive ? t('ussd.activeCallState') : t('ussd.standbyState')}</span>
            </div>

            <pre className="whitespace-pre-wrap leading-relaxed my-2 font-mono text-[11px] text-emerald-300 font-semibold">
              {loading ? t('ussd.transmittingPacket') : screenMessage}
            </pre>

            <div className="border-t border-emerald-900/60 pt-1 flex items-center justify-between text-[10px]">
              <span className="text-emerald-500 font-bold">{t('ussd.inputLabel')}</span>
              <span className="font-bold text-emerald-200">{currentText || '_'}</span>
            </div>
          </div>

          {/* Action Row */}
          <div className="grid grid-cols-2 gap-2 my-3">
            <button
              onClick={() => handleSend()}
              disabled={loading}
              className="bg-emerald-700 hover:bg-emerald-800 text-white font-extrabold py-2 rounded-xl text-xs transition shadow-xs cursor-pointer"
            >
              {t('ussd.sendDial')}
            </button>
            <button
              onClick={handleEndSession}
              className="bg-rose-700 hover:bg-rose-800 text-white font-extrabold py-2 rounded-xl text-xs transition shadow-xs cursor-pointer"
            >
              {t('ussd.endCall')}
            </button>
          </div>

          {/* Keypad */}
          <div className="grid grid-cols-3 gap-2">
            {['1', '2', '3', '4', '5', '6', '7', '8', '9', '*', '0', '#'].map(key => (
              <button
                key={key}
                onClick={() => handleKeypadPress(key)}
                className="bg-white hover:bg-slate-100 text-slate-900 font-mono font-black py-2.5 rounded-xl text-sm transition active:scale-95 shadow-xs border border-slate-300 cursor-pointer"
              >
                {key}
              </button>
            ))}
          </div>

          <div className="mt-2 text-center">
            <button
              onClick={handleClear}
              className="text-[10px] text-slate-500 hover:text-slate-800 font-bold uppercase tracking-wider cursor-pointer"
            >
              {t('ussd.clearInput')}
            </button>
          </div>
        </div>

        {/* Info footer */}
        <div className="text-[11px] text-slate-600 text-center mt-3 flex items-center justify-center space-x-1.5 font-medium">
          <span>{t('ussd.callerLabel')}</span>
          <input
            type="text"
            value={phoneNumber}
            onChange={(e) => setPhoneNumber(e.target.value)}
            className="bg-slate-100 border border-slate-300 px-2.5 py-0.5 rounded-lg font-mono text-slate-900 text-[11px] w-28 text-center font-bold focus:outline-none focus:border-emerald-600"
          />
        </div>
      </div>
    </div>
  );
}
