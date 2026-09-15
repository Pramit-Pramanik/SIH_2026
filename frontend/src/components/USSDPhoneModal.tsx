import { useState } from 'react';

interface USSDPhoneModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function USSDPhoneModal({ isOpen, onClose }: USSDPhoneModalProps) {
  const [phoneNumber, setPhoneNumber] = useState('9876543210');
  const [currentText, setCurrentText] = useState('*247#');
  const [history, setHistory] = useState<string>('');
  const [screenMessage, setScreenMessage] = useState<string>(
    'MandiQ Feature Phone Simulator\nDial *247# to begin zero-data session.'
  );
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
        setScreenMessage(`Error HTTP ${response.status}:\nSession timed out.`);
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
      setScreenMessage('Network / MAP signaling timeout.\nCheck connectivity.');
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
    setScreenMessage('Session ended.\nDial *247# to begin.');
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-sm p-4">
      <div className="relative w-full max-w-sm bg-slate-900 border border-slate-700 rounded-3xl p-6 shadow-2xl flex flex-col items-center">
        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-slate-400 hover:text-white text-lg font-bold"
        >
          &times;
        </button>

        {/* Feature Phone Title */}
        <div className="text-center mb-4">
          <div className="text-xs font-bold text-emerald-400 uppercase tracking-wider">
            Zero-Data Cellular Simulator
          </div>
          <div className="text-sm font-semibold text-white">
            GSM MAP Layer (*247#)
          </div>
        </div>

        {/* Phone Body */}
        <div className="w-full bg-slate-800 border-2 border-slate-700 rounded-2xl p-4 shadow-inner">
          {/* LCD Screen */}
          <div className="bg-[#0b1a10] border-2 border-[#16361f] rounded-lg p-3 font-mono text-emerald-400 text-xs min-h-[160px] max-h-[220px] overflow-y-auto flex flex-col justify-between shadow-inner">
            <div className="flex justify-between border-b border-emerald-900/60 pb-1 text-[10px] text-emerald-500">
              <span>GSM-4G [||||]</span>
              <span>{sessionActive ? 'MAP ACTIVE' : 'STANDBY'}</span>
            </div>

            <pre className="whitespace-pre-wrap leading-relaxed my-2 font-mono text-[11px] text-emerald-300">
              {loading ? 'Transmitting signaling packet...' : screenMessage}
            </pre>

            <div className="border-t border-emerald-900/60 pt-1 flex items-center justify-between text-[10px]">
              <span className="text-emerald-500">Input:</span>
              <span className="font-bold text-emerald-200">{currentText || '_'}</span>
            </div>
          </div>

          {/* Action Row */}
          <div className="grid grid-cols-2 gap-2 my-3">
            <button
              onClick={() => handleSend()}
              disabled={loading}
              className="bg-emerald-600 hover:bg-emerald-500 text-slate-950 font-bold py-2 rounded-lg text-xs transition shadow"
            >
              SEND / DIAL
            </button>
            <button
              onClick={handleEndSession}
              className="bg-rose-800 hover:bg-rose-700 text-white font-bold py-2 rounded-lg text-xs transition shadow"
            >
              END / EXIT
            </button>
          </div>

          {/* Keypad */}
          <div className="grid grid-cols-3 gap-2">
            {['1', '2', '3', '4', '5', '6', '7', '8', '9', '*', '0', '#'].map(key => (
              <button
                key={key}
                onClick={() => handleKeypadPress(key)}
                className="bg-slate-700/80 hover:bg-slate-600 text-white font-mono font-bold py-2.5 rounded-lg text-sm transition active:scale-95 shadow border border-slate-600/50"
              >
                {key}
              </button>
            ))}
          </div>

          <div className="mt-2 text-center">
            <button
              onClick={handleClear}
              className="text-[10px] text-slate-400 hover:text-slate-200 uppercase tracking-wider"
            >
              Clear Input
            </button>
          </div>
        </div>

        {/* Info footer */}
        <div className="text-[11px] text-slate-400 text-center mt-3 flex items-center justify-center space-x-1.5">
          <span>Caller:</span>
          <input
            type="text"
            value={phoneNumber}
            onChange={(e) => setPhoneNumber(e.target.value)}
            className="bg-slate-800 border border-slate-700 px-2 py-0.5 rounded font-mono text-slate-200 text-[11px] w-28 text-center"
          />
        </div>
      </div>
    </div>
  );
}
