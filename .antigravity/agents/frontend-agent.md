# Frontend Agent Specification

## Scope & Responsibility
The Frontend Agent owns all client-side touchpoints across the MandiQ prototype: the Vite + React 18 PWA for terminal PCs and farmer mobile devices, IndexedDB Write-Ahead Logging (Dexie.js), the software weighbridge telemetry simulator UI, and the web-based USSD (`*247#`) emulator.

## Approved Prototype Technology Stack
- **Web PWA**: Vite, React 18, TypeScript, Tailwind CSS
- **Edge Storage**: Dexie.js (IndexedDB `transactionsWAL`)
- **Offline Compression**: `pako` or browser-native `CompressionStream` (Gzip sync batches)
- **Telemetry UI**: WebSocket/REST software scale emulator
- **USSD Emulator**: Interactive web terminal emulating GSM MAP text menu trees

## Production / Future Stack (P2 — DO NOT INSTALL IN PROTOTYPE)
- `react-native` / `react-native-ble-plx` $\rightarrow$ *PRODUCTION / FUTURE*.
- `tflite-runtime` on mobile hardware $\rightarrow$ *PRODUCTION / FUTURE*.
- Physical GSM MAP telecom hardware connections $\rightarrow$ *PRODUCTION / FUTURE*.
- Physical Web Serial (RS232) / Web Bluetooth hardware connections $\rightarrow$ *PRODUCTION / FUTURE*.

## Code Generation Mandate
Ensure all web components gracefully handle `navigator.onLine === false` states by routing writes directly to Dexie.js IndexedDB storage without unhandled promise rejections. Never output placeholders.
