"""
Script to apply AUD-008 translation keys to frontend/src/i18n/translations.ts
Ensures 100% key parity between interface Translations, en, and hi.
"""

import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

TRANSLATIONS_FILE = Path("frontend/src/i18n/translations.ts")

NEW_KEYS = {
    "common": {
        "txnPlaceholder": (
            "e.g. TXN-...",
            "उदा. TXN-..."
        ),
        "load": (
            "Load",
            "लोड करें"
        ),
        "txnNotFound": (
            'Authoritative transaction "{txnId}" not found.',
            'प्राधिकृत लेनदेन "{txnId}" नहीं मिला।'
        ),
        "txnNotFoundServer": (
            'Authoritative transaction "{txnId}" not found on server.',
            'सर्वर पर प्राधिकृत लेनदेन "{txnId}" नहीं मिला।'
        ),
        "txnNotFoundLocally": (
            'Transaction "{txnId}" not found locally or remotely.',
            'लेनदेन "{txnId}" स्थानीय या रिमोट में नहीं मिला।'
        ),
        "txnFarmerMismatch": (
            "Transaction belongs to Farmer #{txnFarmerId}, but active session is Farmer #{sessionFarmerId}",
            "लेनदेन किसान #{txnFarmerId} का है, लेकिन सक्रिय सत्र किसान #{sessionFarmerId} का है"
        ),
        "txnMandiMismatch": (
            "Transaction belongs to Mandi #{txnMandiId}, but selected Mandi is #{selectedMandiId}",
            "लेनदेन मंडी #{txnMandiId} का है, लेकिन चयनित मंडी #{selectedMandiId} है"
        ),
        "txnInvalidState": (
            "Transaction is in state '{currentState}', but required state is one of: [{allowedStates}]",
            "लेनदेन '{currentState}' स्थिति में है, लेकिन आवश्यक स्थिति इनमें से एक होनी चाहिए: [{allowedStates}]"
        ),
        "networkError": (
            "Network connection error. Please verify your connection.",
            "नेटवर्क कनेक्शन त्रुटि। कृपया अपने कनेक्शन की पुष्टि करें।"
        ),
        "adminDataUnavailable": (
            "Admin data unavailable: {errors}",
            "प्रशासन डेटा अनुपलब्ध: {errors}"
        ),
        "demoFarmersError": (
            "Network error fetching demo farmers",
            "डेमो किसानों को प्राप्त करने में नेटवर्क त्रुटि"
        ),
    },
    "farmer": {
        "appointmentCancelledSuccess": (
            "Appointment #{txnId} successfully cancelled. Capacity restored to APMC yard.",
            "अपॉइंटमेंट #{txnId} सफलतापूर्वक रद्द कर दिया गया। एपीएमसी यार्ड की क्षमता पुनर्स्थापित की गई।"
        ),
        "invalidQuantityError": (
            "Invalid quantity: Requested: {requested} qt | Available: > 0.00 qt | Rule: Requested delivery quantity must be strictly greater than 0.",
            "अमान्य मात्रा: अनुरोधित: {requested} क्विंटल | उपलब्ध: > 0.00 क्विंटल | नियम: अनुरोधित वितरण मात्रा शून्य से अधिक होनी चाहिए।"
        ),
        "ceilingExceededError": (
            "Farmer production ceiling exceeded: Requested: {requested} qt | Available: {available} qt | Rule: Farmer cumulative production ceiling is {ceiling} qt (already booked {booked} qt).",
            "किसान उत्पादन सीमा पार हो गई: अनुरोधित: {requested} क्विंटल | उपलब्ध: {available} क्विंटल | नियम: किसान संचयी उत्पादन सीमा {ceiling} क्विंटल है (पहले से बुक: {booked} क्विंटल)।"
        ),
        "slotCapacityExhaustedError": (
            "Slot capacity exhausted: Requested: {requested} qt | Available: {available} qt | Rule: Hourly slot allocated capacity is {allocated} qt (already booked {booked} qt).",
            "स्लॉट क्षमता समाप्त: अनुरोधित: {requested} क्विंटल | उपलब्ध: {available} क्विंटल | नियम: प्रति घंटा स्लॉट आवंटित क्षमता {allocated} क्विंटल है (पहले से बुक: {booked} क्विंटल)।"
        ),
    },
    "gate": {
        "entryVerifiedDetails": (
            "Gate Entry Verified for {farmerName} ({crop}). State: {state}. Authorized for mandi yard staging entry.",
            "{farmerName} ({crop}) के लिए गेट प्रवेश सत्यापित। स्थिति: {state}। मंडी यार्ड स्टेजिंग प्रवेश के लिए अधिकृत।"
        ),
        "passValidationFailed": (
            "Gate pass failed cryptographic signature or structural validation.",
            "गेट पास क्रिप्टोग्राफिक हस्ताक्षर या संरचनात्मक सत्यापन में विफल रहा।"
        ),
        "checkinRejected": (
            "Gate check-in rejected.",
            "गेट चेक-इन अस्वीकृत।"
        ),
        "passVerifiedOnline": (
            "Gate Pass Verified! Authoritative cloud check-in synchronized and vehicle admitted.",
            "गेट पास सत्यापित! प्राधिकृत क्लाउड चेक-इन सिंक हुआ और वाहन को प्रवेश दिया गया।"
        ),
        "passVerifiedOffline": (
            "[OFFLINE PROVISIONAL] Gate entry structurally verified and committed to IndexedDB WAL. Vehicle admitted under offline protocol.",
            "[ऑफलाइन अनंतिम] गेट प्रवेश संरचनात्मक रूप से सत्यापित और IndexedDB WAL में सहेजा गया। वाहन को ऑफलाइन प्रोटोकॉल के तहत प्रवेश दिया गया।"
        ),
        "verificationFailed": (
            "Gate verification failed",
            "गेट सत्यापन विफल"
        ),
        "noTxnPrompt": (
            "No active transaction selected. Please select an active transaction from the queue or recent workflow, or enter a Transaction ID below:",
            "कोई सक्रिय लेनदेन चयनित नहीं है। कृपया कतार या हालिया कार्यप्रवाह से एक सक्रिय लेनदेन चुनें, या नीचे लेनदेन आईडी दर्ज करें:"
        ),
        "hmacFormatInvalid": (
            "Invalid HMAC signature format: expected 64-character hexadecimal digest, received {length} chars",
            "अमान्य HMAC हस्ताक्षर प्रारूप: 64-वर्ण हेक्साडेसिमल डाइजेस्ट अपेक्षित, {length} वर्ण प्राप्त हुए"
        ),
        "hmacMissing": (
            "Missing cryptographic token signature",
            "क्रिप्टोग्राफिक टोकन हस्ताक्षर गायब है"
        ),
        "mandiMismatchError": (
            "Mandi Mismatch: Gate pass is registered for Mandi ID {passMandi}, but this terminal is Mandi ID {terminalMandi}",
            "मंडी बेमेल: गेट पास मंडी आईडी {passMandi} के लिए पंजीकृत है, लेकिन यह टर्मिनल मंडी आईडी {terminalMandi} है"
        ),
        "yieldCeilingExceeded": (
            "Yield Ceiling Exceeded: {projected} qt would exceed farmer ceiling of {ceiling} qt",
            "उत्पादन सीमा पार: {projected} क्विंटल किसान सीमा {ceiling} क्विंटल से अधिक होगा"
        ),
    },
    "quality": {
        "cannotAssessState": (
            "Cannot assess quality: Transaction is in state '{state}'. Expected 'GATE_ENTRY_VERIFIED'.",
            "गुणवत्ता का आकलन नहीं किया जा सकता: लेनदेन '{state}' स्थिति में है। 'GATE_ENTRY_VERIFIED' अपेक्षित है।"
        ),
        "assessmentRejected": (
            "Quality assessment rejected by server",
            "सर्वर द्वारा गुणवत्ता मूल्यांकन अस्वीकृत"
        ),
        "assessmentFailed": (
            "Quality assessment failed",
            "गुणवत्ता मूल्यांकन विफल"
        ),
        "offlineRejected": (
            "[OFFLINE WAL] Lot rejected: Moisture exceeds 17.0% limit. Stored locally.",
            "[ऑफलाइन WAL] लॉट अस्वीकृत: नमी 17.0% सीमा से अधिक है। स्थानीय रूप से सहेजा गया।"
        ),
        "offlineApproved": (
            "[OFFLINE WAL] Quality approved and stored to IndexedDB transactionsWAL. Will sync to Redis queue when online.",
            "[ऑफलाइन WAL] गुणवत्ता स्वीकृत और IndexedDB transactionsWAL में संग्रहीत। ऑनलाइन होने पर Redis कतार में सिंक होगी।"
        ),
        "overrideFailed": (
            "Supervisor override failed",
            "पर्यवेक्षक अधिरोहण विफल"
        ),
        "supervisorOverrideAuthorized": (
            "Supervisor Override Authorized: {message}",
            "पर्यवेक्षक अधिरोहण अधिकृत: {message}"
        ),
        "preflightNotice": (
            "Please book a slot and complete Gate Entry verification before quality assaying.",
            "कृपया गुणवत्ता परीक्षण से पहले स्लॉट बुक करें और गेट प्रवेश सत्यापन पूर्ण करें।"
        ),
    },
    "queue": {
        "offlineNotice": (
            "Queue offline: displaying locally cached queue if available.",
            "कतार ऑफलाइन है: यदि उपलब्ध हो तो स्थानीय रूप से कैश्ड कतार प्रदर्शित हो रही है।"
        ),
        "fetchError": (
            "Network error fetching queue",
            "कतार प्राप्त करने में नेटवर्क त्रुटि"
        ),
        "simulationInjected": (
            "Showcase traffic injected. Live DCDQ re-ordered queue.",
            "शोकेस ट्रैफ़िक प्रविष्ट किया गया। लाइव DCDQ ने कतार को पुन: व्यवस्थित किया।"
        ),
        "simulationError": (
            "Simulation error",
            "सिमुलेशन त्रुटि"
        ),
        "resetSuccess": (
            "Showcase queue reset to clean baseline.",
            "शोकेस कतार स्वच्छ बेसलाइन पर रीसेट की गई।"
        ),
        "resetError": (
            "Reset error",
            "रीसेट त्रुटि"
        ),
        "dispatchFailed": (
            "Dispatch failed",
            "प्रेषण विफल"
        ),
        "offlineDispatched": (
            "[OFFLINE LOCAL] Vehicle {txnId} popped from local queue and routed to weighbridge.",
            "[ऑफलाइन स्थानीय] वाहन {txnId} स्थानीय कतार से निकाला गया और धर्मकांटे पर भेजा गया।"
        ),
        "dispatchError": (
            "Dispatch error",
            "प्रेषण त्रुटि"
        ),
    },
    "weighbridge": {
        "vehicleMustBeRouted": (
            "Transaction is in state '{state}'. Vehicle must be routed to weighbridge before gross capture.",
            "लेनदेन '{state}' स्थिति में है। सकल वजन दर्ज करने से पहले वाहन को धर्मकांटे पर भेजा जाना चाहिए।"
        ),
        "grossRejected": (
            "Gross weighment rejected by server",
            "सर्वर द्वारा सकल वजन अस्वीकृत"
        ),
        "grossRecordedProceedTare": (
            "Gross weight recorded: {gross} qt. State: {state}. Now proceed to unload grain and capture tare weight.",
            "सकल वजन दर्ज: {gross} क्विंटल। स्थिति: {state}। अब अनाज खाली करने और खाली वजन लेने के लिए आगे बढ़ें।"
        ),
        "offlineGrossSaved": (
            "[OFFLINE WAL] Gross weight ({gross} qt) saved to IndexedDB transactionsWAL.",
            "[ऑफलाइन WAL] सकल वजन ({gross} क्विंटल) IndexedDB transactionsWAL में सहेजा गया।"
        ),
        "errorGross": (
            "Error capturing gross weight",
            "सकल वजन दर्ज करने में त्रुटि"
        ),
        "grossMustBeCapturedBeforeTare": (
            "Transaction is in state '{state}'. Gross weight must be captured before tare weight.",
            "लेनदेन '{state}' स्थिति में है। खाली वजन से पहले सकल वजन दर्ज किया जाना चाहिए।"
        ),
        "tareRejected": (
            "Tare weighment rejected by server",
            "सर्वर द्वारा खाली वजन अस्वीकृत"
        ),
        "tareRecordedNetSettlement": (
            "Tare weight recorded: {tare} qt. Net Settlement: {net} qt. State: {state}. Ready for J-Form billing.",
            "खाली वजन दर्ज: {tare} क्विंटल। शुद्ध निपटान: {net} क्विंटल। स्थिति: {state}। जे-फॉर्म बिलिंग के लिए तैयार।"
        ),
        "offlineTareSaved": (
            "[OFFLINE WAL] Tare weight ({tare} qt) saved to IndexedDB transactionsWAL. Net weight: {net} qt.",
            "[ऑफलाइन WAL] खाली वजन ({tare} क्विंटल) IndexedDB transactionsWAL में सहेजा गया। शुद्ध वजन: {net} क्विंटल।"
        ),
        "errorTare": (
            "Error capturing tare weight",
            "खाली वजन दर्ज करने में त्रुटि"
        ),
        "unifiedRejected": (
            "Unified weighment rejected by server",
            "सर्वर द्वारा एकीकृत वजन अस्वीकृत"
        ),
        "unifiedCaptured": (
            "Unified Weighment Captured: Gross={gross} qt, Tare={tare} qt, Net={net} qt. State: {state}.",
            "एकीकृत वजन दर्ज: सकल={gross} क्विंटल, खाली={tare} क्विंटल, शुद्ध={net} क्विंटल। स्थिति: {state}।"
        ),
        "offlineUnifiedSaved": (
            "[OFFLINE WAL] Unified weighment saved to IndexedDB transactionsWAL. Net weight: {net} qt.",
            "[ऑफलाइन WAL] एकीकृत वजन IndexedDB transactionsWAL में सहेजा गया। शुद्ध वजन: {net} क्विंटल।"
        ),
        "errorWeighment": (
            "Error capturing weighment",
            "वजन दर्ज करने में त्रुटि"
        ),
        "preflightNotice": (
            "Please dispatch a vehicle from the Live Priority Queue to perform weighbridge scale capture.",
            "धर्मकांटा माप दर्ज करने के लिए कृपया लाइव प्राथमिकता कतार से एक वाहन प्रेषित करें।"
        ),
    },
    "billing": {
        "noCropSpecified": (
            "No crop commodity specified for active transaction.",
            "सक्रिय लेनदेन के लिए कोई फसल वस्तु निर्दिष्ट नहीं है।"
        ),
        "mspNotFoundInMaster": (
            "Authoritative MSP not found in Crop Master for '{crop}'.",
            "'{crop}' के लिए फसल मास्टर में प्राधिकृत एमएसपी नहीं मिला।"
        ),
        "failedFetchCropMaster": (
            "Failed to fetch Crop Master directory.",
            "फसल मास्टर निर्देशिका प्राप्त करने में विफल।"
        ),
        "vehicleMustBeWeighedTare": (
            "Transaction is in state '{state}'. Vehicle must be in 'WEIGHED_TARE' before generating J-Form.",
            "लेनदेन '{state}' स्थिति में है। जे-फॉर्म उत्पन्न करने से पहले वाहन 'WEIGHED_TARE' स्थिति में होना चाहिए।"
        ),
        "mspUnresolvedWait": (
            "Authoritative crop MSP is unresolved. Please wait for Crop Master resolution.",
            "प्राधिकृत फसल एमएसपी अनसुलझा है। कृपया फसल मास्टर समाधान की प्रतीक्षा करें।"
        ),
        "jformRejectedServer": (
            "J-Form billing rejected by server",
            "सर्वर द्वारा जे-फॉर्म बिलिंग अस्वीकृत"
        ),
        "invoiceGeneratedDualSig": (
            "Official J-Form invoice generated: ₹{amount}. State: {state}. Ready for dual-signature payout staging.",
            "आधिकारिक जे-फॉर्म चालान उत्पन्न: ₹{amount}। स्थिति: {state}। दोहरे हस्ताक्षर भुगतान स्टेजिंग के लिए तैयार।"
        ),
        "offlineInvoiceSaved": (
            "[OFFLINE WAL] J-Form invoice (₹{amount}) saved to IndexedDB transactionsWAL.",
            "[ऑफलाइन WAL] जे-फॉर्म चालान (₹{amount}) IndexedDB transactionsWAL में सहेजा गया।"
        ),
        "unknownBillingError": (
            "Unknown billing error",
            "अज्ञात बिलिंग त्रुटि"
        ),
        "failedGenerateDemoSigs": (
            "Failed to generate demo signatures.",
            "डेमो हस्ताक्षर उत्पन्न करने में विफल।"
        ),
        "couldNotObtainDemoSigs": (
            "Could not obtain demo signatures.",
            "डेमो हस्ताक्षर प्राप्त नहीं किए जा सके।"
        ),
        "payoutStagingFailed": (
            "Payout staging failed",
            "भुगतान स्टेजिंग विफल"
        ),
        "payoutStagedSettled": (
            "DBT Payout Staged & Settled! Block Hash: {hash}...",
            "डीबीटी भुगतान स्टेज और निपटारा पूर्ण! ब्लॉक हैश: {hash}..."
        ),
        "generateJformFirstDbt": (
            "Cannot trigger DBT disbursement: Please generate a J-Form invoice first.",
            "डीबीटी संवितरण शुरू नहीं किया जा सकता: कृपया पहले जे-फॉर्म चालान उत्पन्न करें।"
        ),
        "pfmsSimRejected": (
            "PFMS Aadhaar Payment Rail simulation rejected.",
            "पीएफएमएस आधार भुगतान रेल सिमुलेशन अस्वीकृत।"
        ),
        "dbtFailed": (
            "DBT disbursement failed",
            "डीबीटी संवितरण विफल"
        ),
        "preflightNotice": (
            "Please complete weighbridge net settlement before generating J-Form billing.",
            "जे-फॉर्म बिलिंग उत्पन्न करने से पहले कृपया धर्मकांटा शुद्ध निपटान पूर्ण करें।"
        ),
        "mspRatePlaceholder": (
            "Authoritative MSP rate",
            "प्राधिकृत एमएसपी दर"
        ),
        "resolvingMsp": (
            "Resolving MSP...",
            "एमएसपी समाधान हो रहा है..."
        ),
        "unresolved": (
            "Unresolved",
            "अनसुलझा"
        ),
        "resolvingAuthoritativeMsp": (
            "Resolving Authoritative MSP...",
            "प्राधिकृत एमएसपी समाधान हो रहा है..."
        ),
    },
    "admin": {
        "dataUnavailable": (
            "Admin data unavailable: {errors}",
            "प्रशासन डेटा अनुपलब्ध: {errors}"
        ),
        "showcaseInjected": (
            "Live showcase traffic successfully injected into database and priority queue!",
            "लाइव शोकेस ट्रैफ़िक सफलतापूर्वक डेटाबेस और प्राथमिकता कतार में प्रविष्ट किया गया!"
        ),
        "errorSimulating": (
            "Error simulating showcase traffic",
            "शोकेस ट्रैफ़िक सिमुलेशन में त्रुटि"
        ),
        "showcaseResetClean": (
            "Showcase database and priority queue cleanly reset!",
            "शोकेस डेटाबेस और प्राथमिकता कतार स्वच्छ रूप से रीसेट किए गए!"
        ),
        "errorResetting": (
            "Error resetting showcase database",
            "शोकेस डेटाबेस रीसेट करने में त्रुटि"
        ),
        "failedCreateMandi": (
            "Failed to create mandi",
            "मंडी बनाने में विफल"
        ),
        "mandiRegisteredSuccess": (
            'APMC Mandi "{name}" registered successfully!',
            'एपीएमसी मंडी "{name}" सफलतापूर्वक पंजीकृत की गई!'
        ),
        "errorCreatingMandi": (
            "Error creating mandi",
            "मंडी बनाने में त्रुटि"
        ),
        "failedUpdateStatus": (
            "Failed to update status",
            "स्थिति अद्यतन करने में विफल"
        ),
        "errorUpdatingMandiStatus": (
            "Error updating mandi status",
            "मंडी स्थिति अद्यतन करने में त्रुटि"
        ),
        "failedUpdateCommodity": (
            "Failed to update commodity",
            "वस्तु अद्यतन करने में विफल"
        ),
        "commodityMspUpdated": (
            'Commodity "{name}" MSP updated to ₹{msp}/Qt!',
            'वस्तु "{name}" एमएसपी ₹{msp}/क्विंटल पर अद्यतन किया गया!'
        ),
        "errorUpdatingCrop": (
            "Error updating crop",
            "फसल अद्यतन करने में त्रुटि"
        ),
        "confirmDeactivateCommodity": (
            'Are you sure you want to deactivate commodity "{name}"?',
            'क्या आप वाकई वस्तु "{name}" को निष्क्रिय करना चाहते हैं?'
        ),
        "failedDeactivateCommodity": (
            "Failed to deactivate commodity",
            "वस्तु निष्क्रिय करने में विफल"
        ),
        "commodityDeactivatedSuccess": (
            'Commodity "{name}" deactivated successfully.',
            'वस्तु "{name}" सफलतापूर्वक निष्क्रिय कर दी गई।'
        ),
        "errorDeactivatingCommodity": (
            "Error deactivating commodity",
            "वस्तु निष्क्रिय करने में त्रुटि"
        ),
        "failedGenerateSlots": (
            "Failed to generate slots",
            "स्लॉट उत्पन्न करने में विफल"
        ),
        "errorGeneratingSlots": (
            "Error generating slots",
            "स्लॉट उत्पन्न करने में त्रुटि"
        ),
        "cropCodePlaceholder": (
            "WHEAT_SHARBATI",
            "WHEAT_SHARBATI"
        ),
        "resetFailed": (
            "Reset failed",
            "रीसेट विफल"
        ),
        "simulationFailed": (
            "Simulation failed",
            "सिमुलेशन विफल"
        ),
    },
    "demoTools": {
        "farmerSwitched": (
            "Active demo farmer switched to: {name} (Farmer ID: {id}).",
            "सक्रिय डेमो किसान बदला गया: {name} (किसान आईडी: {id})।"
        ),
    },
    "journey": {
        "networkFailure": (
            "Network failure occurred",
            "नेटवर्क विफलता हुई"
        ),
        "stageError": (
            "Unexpected error during stage execution",
            "चरण निष्पादन के दौरान अप्रत्याशित त्रुटि"
        ),
        "resetFailed": (
            "Reset failed",
            "रीसेट विफल"
        ),
        "preflightFailed": (
            "Pre-flight reset failed",
            "प्री-फ़्लाइट रीसेट विफल"
        ),
        "stageFailed": (
            "Stage failed",
            "चरण विफल"
        ),
    },
}


def update_translations_file():
    text = TRANSLATIONS_FILE.read_text(encoding="utf-8")
    
    # 1. Update interface Translations
    # We locate each section in `export interface Translations {` and insert new keys before closing `};`
    interface_match = re.search(r"export\s+interface\s+Translations\s*\{", text)
    if not interface_match:
        raise ValueError("Could not find interface Translations")
    
    # Find the end of interface Translations
    intf_start = interface_match.start()
    depth = 0
    intf_end = -1
    for i in range(interface_match.end() - 1, len(text)):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                intf_end = i + 1
                break
                
    intf_block = text[intf_start:intf_end]
    new_intf_block = intf_block
    
    for section, keys in NEW_KEYS.items():
        # Find section in interface
        sec_m = re.search(rf"(\b{section}\s*:\s*\{{[^}}]*?)(\n\s*\}};)", new_intf_block)
        if sec_m:
            existing = sec_m.group(1)
            closing = sec_m.group(2)
            lines_to_add = []
            for k in keys:
                if f"{k}:" not in existing:
                    lines_to_add.append(f"    {k}: string;")
            if lines_to_add:
                new_sec = existing + "\n" + "\n".join(lines_to_add) + closing
                new_intf_block = new_intf_block.replace(sec_m.group(0), new_sec)
    
    text = text[:intf_start] + new_intf_block + text[intf_end:]
    
    # 2. Update `en` dictionary
    en_match = re.search(r"\ben\s*:\s*\{", text)
    if not en_match:
        raise ValueError("Could not find 'en:' dictionary")
    en_start = en_match.start()
    depth = 0
    en_end = -1
    for i in range(en_match.end() - 1, len(text)):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                en_end = i + 1
                break
    en_block = text[en_start:en_end]
    new_en_block = en_block
    for section, keys in NEW_KEYS.items():
        sec_m = re.search(rf"(\b{section}\s*:\s*\{{[^}}]*?)(\n\s*\}},?)", new_en_block)
        if sec_m:
            existing = sec_m.group(1)
            closing = sec_m.group(2)
            lines_to_add = []
            for k, (en_val, _) in keys.items():
                if f"{k}:" not in existing:
                    # escape single quotes
                    escaped_val = en_val.replace("'", "\\'")
                    lines_to_add.append(f"      {k}: '{escaped_val}',")
            if lines_to_add:
                new_sec = existing + "\n" + "\n".join(lines_to_add) + closing
                new_en_block = new_en_block.replace(sec_m.group(0), new_sec)
    text = text[:en_start] + new_en_block + text[en_end:]

    # 3. Update `hi` dictionary
    hi_match = re.search(r"\bhi\s*:\s*\{", text)
    if not hi_match:
        raise ValueError("Could not find 'hi:' dictionary")
    hi_start = hi_match.start()
    depth = 0
    hi_end = -1
    for i in range(hi_match.end() - 1, len(text)):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                hi_end = i + 1
                break
    hi_block = text[hi_start:hi_end]
    new_hi_block = hi_block
    for section, keys in NEW_KEYS.items():
        sec_m = re.search(rf"(\b{section}\s*:\s*\{{[^}}]*?)(\n\s*\}},?)", new_hi_block)
        if sec_m:
            existing = sec_m.group(1)
            closing = sec_m.group(2)
            lines_to_add = []
            for k, (_, hi_val) in keys.items():
                if f"{k}:" not in existing:
                    escaped_val = hi_val.replace("'", "\\'")
                    lines_to_add.append(f"      {k}: '{escaped_val}',")
            if lines_to_add:
                new_sec = existing + "\n" + "\n".join(lines_to_add) + closing
                new_hi_block = new_hi_block.replace(sec_m.group(0), new_sec)
    text = text[:hi_start] + new_hi_block + text[hi_end:]

    TRANSLATIONS_FILE.write_text(text, encoding="utf-8")
    print("translations.ts updated successfully!")


if __name__ == "__main__":
    update_translations_file()
