/**
 * MandiQ Localization Dictionary
 * Strict Single-Language strings for English (en) and Hindi (hi).
 * NO mixed-language slash strings.
 */

export interface Translations {
  common: {
    appName: string;
    appSubtitle: string;
    apmcPwa: string;
    loading: string;
    confirm: string;
    cancel: string;
    close: string;
    refresh: string;
    status: string;
    action: string;
    verified: string;
    pending: string;
    operational: string;
    today: string;
    logout: string;
    online: string;
    offline: string;
    synced: string;
    error: string;
    success: string;
    quintals: string;
    kg: string;
    inr: string;
    language: string;
    all: string;
    search: string;
    filter: string;
    details: string;
    noData: string;

    activeTransaction: string;
    apmcProcurementSystem: string;

    backendOffline: string;
    inMemoryQueue: string;
    noActiveTransaction: string;
    tareWeightError: string;
    noMandiSelected: string;
    reservationFailed: string;
    cancellationFailed: string;
    networkErrorCancel: string;
    selectOperationalMandi: string;
    unlinkedFarmerReservation: string;
    noVehiclesInQueue: string;
    jformMissingNetWeight: string;
    savedLocallyWal: string;
    generateJformFirst: string;
    dualSigAdminNotice: string;
    dbtOfflineWal: string;
    dbtPfmsConfirmed: string;
    dbtOfflineRecorded: string;
    supervisorOverrideRecorded: string;
    adminBackendUnavailable: string;
    noMandiSimulation: string;
    noMandiReset: string;
    initializing: string;
    txnPlaceholder: string;
    load: string;
    txnNotFound: string;
    txnNotFoundServer: string;
    txnNotFoundLocally: string;
    txnFarmerMismatch: string;
    txnMandiMismatch: string;
    txnInvalidState: string;
    networkError: string;
    adminDataUnavailable: string;
    demoFarmersError: string;
    crop: string;
  };
  nav: {
    admin: string;
    farmer: string;
    gate: string;
    quality: string;
    queue: string;
    weighbridge: string;
    billing: string;
    sync: string;
    advanceStation: string;
    nextStation: string;
    demoTools: string;
  };
  roles: {
    admin: string;
    supervisor: string;
    inspector: string;
    operator: string;
    farmer: string;
  };
  login: {
    title: string;
    subtitle: string;
    selectRole: string;
    username: string;
    usernamePlaceholder: string;
    password: string;
    passwordPlaceholder: string;
    signIn: string;
    signingIn: string;
    quickDemoUsers: string;
    credentialsError: string;
    offlineFallbackNotice: string;

    hmacSession: string;
    footerStandards: string;
  };
  farmer: {
    greeting: string;
    profileTitle: string;
    kisanId: string;
    mobile: string;
    remainingCeiling: string;
    availableCapacity: string;
    remainingAfterBooking: string;
    targetMandi: string;
    yardOperational: string;
    processFlow: string;
    stepOf: string;
    step1Crop: string;
    step2Token: string;
    step3Gate: string;
    step4Quality: string;
    step5Weight: string;
    step6Payment: string;
    activeToken: string;
    tokenNo: string;
    scanAtGate: string;
    cancelSlot: string;
    cancelSlotPrompt: string;
    viewReceipt: string;
    bookDeliveryTitle: string;
    bookDeliverySubtitle: string;
    step1Title: string;
    govtMsp: string;
    loadingCrops: string;
    noCrops: string;
    step2Title: string;
    quantityHint: string;
    quickPills: string;
    step3Title: string;
    landTenure: string;
    ownerCultivator: string;
    ownerDesc: string;
    tenantCultivator: string;
    tenantDesc: string;
    landownerName: string;
    landownerNamePlaceholder: string;
    panchayatCert: string;
    panchayatCertHint: string;
    bonaFideDeclaration: string;
    step4Title: string;
    scheduledDate: string;
    step5Title: string;
    slotsHint: string;
    loadingSlots: string;
    noSlots: string;
    capacityRemaining: string;
    confirming: string;
    reserveButton: string;
    slotUnavailable: string;
    valQtyPositive: string;
    valQtyExceedsCeiling: string;
    valLandownerRequired: string;
    valBonaFideRequired: string;
    valSlotRequired: string;
    valOfflineBooking: string;
    appointmentSuccess: string;

    targetMandiAndDate: string;
    sourceOfTruthSlots: string;
    destinationMandi: string;
    noMandisAvailable: string;
    scheduledDeliveryDate: string;
    minus: string;
    plus: string;
    unlinkedProfileTitle: string;
    unlinkedProfileDesc: string;
    appointmentCancelledSuccess: string;
    invalidQuantityError: string;
    ceilingExceededError: string;
    slotCapacityExhaustedError: string;
    arrivalRiskTitle: string;
    modelledRiskBadge: string;
    expectedTime: string;
    actualTime: string;
    deviationMinutes: string;
    riskProbability: string;
  };
  gate: {
    title: string;
    subtitle: string;
    scanQrTitle: string;
    scanQrSubtitle: string;
    tokenPlaceholder: string;
    verifyButton: string;
    verifying: string;
    driverMobile: string;
    vehicleNo: string;
    vehicleNoPlaceholder: string;
    checkInButton: string;
    checkingIn: string;
    checkInSuccess: string;
    waitingVehicle: string;
    entryVerified: string;
    inspectionReady: string;

    cryptoRules: string;
    tamperProtection: string;
    tamperDesc: string;
    offlineResilience: string;
    offlineDesc: string;
    stateProgression: string;
    stateProgressionDesc: string;
    stateProgressionSuffix: string;
    farmerIdPlaceholder: string;
    slotIdPlaceholder: string;
    signaturePlaceholder: string;
    entryVerifiedDetails: string;
    passValidationFailed: string;
    checkinRejected: string;
    passVerifiedOnline: string;
    passVerifiedOffline: string;
    verificationFailed: string;
    noTxnPrompt: string;
    hmacFormatInvalid: string;
    hmacMissing: string;
    mandiMismatchError: string;
    yieldCeilingExceeded: string;
  };
  quality: {
    title: string;
    subtitle: string;
    sensorReading: string;
    cropMoisture: string;
    optimalRange: string;
    maxLimit: string;
    assessing: string;
    assessButton: string;
    resultApproved: string;
    resultRejected: string;
    eligibleForQueue: string;
    routedToDrying: string;
    routeToDrying: string;
    priorityScore: string;
    supervisorOverrideTitle: string;
    overrideReason: string;
    overrideButton: string;
    overriding: string;

    supervisorAuthToken: string;
    supervisorAuthTokenPlaceholder: string;
    technicalFormulasInDemoTools: string;
    standardsTitle: string;
    gradeATitle: string;
    gradeADesc: string;
    gradeBTitle: string;
    gradeBDesc: string;
    rejectionTitle: string;
    rejectionDesc: string;
    calibratedMoisture: string;
    confirmOverride: string;
    dcdqFormula: string;
    elapsedWaitMinutes: string;
    cannotAssessState: string;
    assessmentRejected: string;
    assessmentFailed: string;
    offlineRejected: string;
    offlineApproved: string;
    overrideFailed: string;
    supervisorOverrideAuthorized: string;
    preflightNotice: string;
    unauthorizedRole: string;
    autoResolvedGate: string;
    awaitingGateLots: string;
  };
  queue: {
    title: string;
    subtitle: string;
    liveQueueStatus: string;
    vehiclesWaiting: string;
    rank: string;
    tokenNo: string;
    farmer: string;
    quantity: string;
    dcdqScore: string;
    status: string;
    dispatchButton: string;
    dispatching: string;
    emptyQueue: string;
    emptyQueueHint: string;
    dispatchedToWeighbridge: string;
    offlineNotice: string;
    fetchError: string;
    simulationInjected: string;
    simulationError: string;
    resetSuccess: string;
    resetError: string;
    dispatchFailed: string;
    offlineDispatched: string;
    dispatchError: string;
    scoreA: string;
    scoreD: string;
    scoreM: string;
    scoreW: string;
    scoreS: string;
    scoreBreakdown: string;
    adherence: string;
    demurrage: string;
    moistureRisk: string;
    waitBonus: string;
    advanceQueueTime: string;
    advancingQueueTime: string;
    rerankQueue: string;
    rerankingQueue: string;
    offlineProvisional: string;
    authoritativeRouted: string;
    conflictRejected: string;
    dispatchedVehiclesTitle: string;
    dispatchedVehiclesDesc: string;
    noDispatchedVehicles: string;
    offlineDispatchedProvisional: string;
    dispatchedAuthoritative: string;
    estimatedWait: string;
    estimatedWaitNext: string;
    calculatingTelemetry: string;
    vehiclesAhead: string;
    payloadAhead: string;
    serviceRate: string;
    activeScales: string;
    scaleOffline: string;
    scaleOnline: string;
    toggleScale: string;
    technicalBreakdown: string;
    crop: string;
    moisture: string;
    appointmentAdherence: string;
    demurrageScore: string;
    moistureRiskScore: string;
    antiStarvationWait: string;
    finalDcdqScore: string;
    liveQueueHeader: string;
    operationalTelemetry: string;
    algorithmSimulationHeader: string;
    algorithmSimulationDesc: string;
    simulatedLot: string;
    scaleCount1: string;
    scaleCount2: string;
    scaleCount3: string;
    scales: string;
    dcdqFormulationSubtitle: string;
    serviceRateTelemetry: string;
  };
  weighbridge: {
    title: string;
    subtitle: string;
    grossWeight: string;
    tareWeight: string;
    netWeight: string;
    scaleReading: string;
    captureGross: string;
    capturingGross: string;
    captureTare: string;
    capturingTare: string;
    weightSummary: string;
    proceedToBilling: string;
    tareInstruction: string;

    rulesTitle: string;
    physicalInvariant: string;
    physicalDesc: string;
    yieldCeiling: string;
    yieldDesc: string;
    distributedLock: string;
    lockDesc: string;
    lockSuffix: string;
    captureUnified: string;
    scaleInvariance: string;
    twoStepWeighment: string;
    unifiedWeighment: string;
    vehicleMustBeRouted: string;
    grossRejected: string;
    grossRecordedProceedTare: string;
    offlineGrossSaved: string;
    errorGross: string;
    grossMustBeCapturedBeforeTare: string;
    tareRejected: string;
    tareRecordedNetSettlement: string;
    offlineTareSaved: string;
    errorTare: string;
    unifiedRejected: string;
    unifiedCaptured: string;
    offlineUnifiedSaved: string;
    errorWeighment: string;
    preflightNotice: string;
    activeLaneVehicles: string;
    selectVehiclePrompt: string;
    invalidTareRange: string;
    autoResolvedQueue: string;
    noVehiclesInLane: string;
  };
  billing: {
    title: string;
    subtitle: string;
    jformTitle: string;
    invoiceNo: string;
    mandiName: string;
    cropName: string;
    netWeight: string;
    mspPrice: string;
    grossPayable: string;
    mandiDeductions: string;
    netPayable: string;
    generateInvoice: string;
    generateButton: string;
    generating: string;
    dualSignatureRequired: string;
    inspectorSig: string;
    operatorSig: string;
    authorizePayout: string;
    authorizing: string;
    payoutSettled: string;
    dbtReference: string;

    deductionsCut: string;
    targetInvoiceAmount: string;
    verifyingSignatures: string;
    stageDualSignature: string;
    simulatePfms: string;
    officialFormJ: string;
    totalNetAmount: string;
    totalDisbursement: string;
    farmerName: string;
    commodityNetQty: string;
    ratePerQuintal: string;
    totalDeductions: string;
    dbtConfirmation: string;
    payoutBlockHash: string;
    pfmsReference: string;
    inspectorRemarks: string;
    inspectorHmac: string;
    operatorHmac: string;
    enterOrVerifyHmac: string;
    noCropSpecified: string;
    mspNotFoundInMaster: string;
    failedFetchCropMaster: string;
    vehicleMustBeWeighedTare: string;
    mspUnresolvedWait: string;
    jformRejectedServer: string;
    invoiceGeneratedDualSig: string;
    offlineInvoiceSaved: string;
    unknownBillingError: string;
    failedGenerateDemoSigs: string;
    couldNotObtainDemoSigs: string;
    payoutStagingFailed: string;
    payoutStagedSettled: string;
    generateJformFirstDbt: string;
    pfmsSimRejected: string;
    dbtFailed: string;
    preflightNotice: string;
    mspRatePlaceholder: string;
    resolvingMsp: string;
    unresolved: string;
    resolvingAuthoritativeMsp: string;
    authoritativeSettlementSummary: string;
    grossValue: string;
    dbtStatus: string;
    statusPendingStaging: string;
    statusStaged: string;
    statusSettled: string;
    autoResolvedWeighed: string;
  };
  sync: {
    title: string;
    subtitle: string;
    walStatus: string;
    pendingMutations: string;
    syncedMutations: string;
    triggerSync: string;
    syncing: string;
    mutationId: string;
    targetState: string;
    timestamp: string;
    statusLabel: string;
  };
  demoTools: {
    title: string;
    subtitle: string;
    tabControls: string;
    tabFarmerSwitcher: string;
    tabEvidence: string;
    resetShowcase: string;
    resetting: string;
    resetSuccess: string;
    simulateTraffic: string;
    simulatingTraffic: string;
    simulateBlackout: string;
    blackoutActive: string;
    launchE2E: string;
    resetShowcaseDesc: string;
    simulateTrafficDesc: string;
    launchE2EDesc: string;
    showcaseCommandCenter: string;
    showcaseSubtitle: string;
    openUSSD: string;
    switchFarmerTitle: string;
    switchFarmerDesc: string;
    activeContextNotice: string;
    technicalEvidenceTitle: string;
    dcdqTitle: string;
    dcdqFormula: string;
    dcdqAlpha: string;
    dcdqBeta: string;
    dcdqGamma: string;
    dcdqLambda: string;
    invariantsTitle: string;
    invCeiling: string;
    invSlot: string;
    invState: string;
    invCrypto: string;
    invWal: string;

    accessRestricted: string;
    accessRestrictedDesc: string;
    invCeilingTitle: string;
    invSlotTitle: string;
    invStateTitle: string;
    invCryptoTitle: string;
    invWalTitle: string;
    farmerSwitched: string;
    advanceTime: string;
    advancingTime: string;
    advanceTimeDesc: string;
    optimizeSlots: string;
    optimizeSlotsDesc: string;
    tasTitle: string;
    tasSubtitle: string;
    tasRunSolver: string;
    tasSolving: string;
    tasBefore: string;
    tasAfter: string;
    tasOverload: string;
    tasObjective: string;
    tasMaxSlotLoad: string;
    tasTrucks: string;
    tasSolverBadge: string;
    failureModelTitle: string;
    failureModelDesc: string;
    failureModelLabel: string;
    expectedArrival: string;
    actualArrival: string;
    arrivalDeviation: string;
    failureProbability: string;
    concurrentBookingTitle: string;
    concurrentBookingDesc: string;
    runConcurrentTest: string;
    runningConcurrentTest: string;
    totalRequests: string;
    successfulRequests: string;
    rejectedRequests: string;
    capacityExceededZero: string;
    lockAcquisitionTimeline: string;
    redisMutexBadge: string;
    lwwConflictTitle: string;
    lwwConflictDesc: string;
    runLWWTest: string;
    runningLWWTest: string;
    lwwMutationA: string;
    lwwMutationB: string;
    authoritativeSequenceWinner: string;
    governanceNotice: string;
    clientTimestampDiagnostic: string;
    field: string;
    oldValue: string;
    incomingValue: string;
    winner: string;
    reason: string;
    gzipSyncTitle: string;
    gzipSyncDesc: string;
    testGzipSync: string;
    testingGzipSync: string;
    rawSize: string;
    compressedSize: string;
    compressionRatio: string;
    recordCount: string;
    decompressionVerified: string;
    slotCapacity: string;
    serverSequence: string;
    tabAlgorithms: string;
  };
  controlCenter: {
    title: string;
    subtitle: string;
    dataIsolationNotice: string;
    resetDemoBtn: string;
    resettingDemo: string;
    resetDemoSuccess: string;
    statusLive: string;
    statusSimulation: string;
    statusAlgoDemo: string;
    statusDemo: string;
    statusDocumented: string;
    statusNotImplemented: string;
    verifiedStatus: string;
    executionTrace: string;
    formulaLabel: string;
    liveInputsLabel: string;
    actualOutputLabel: string;
    summaryCountLive: string;
    summaryCountDemo: string;
    summaryCountDocumented: string;
    summaryCountNotImplemented: string;
    mandiSelectionRequiredDesc: string;
    twoModules: string;
    sixModules: string;
    liveModulesSummary: string;
    demoModulesSummary: string;

    // Module 1: DCDQ
    dcdqModuleTitle: string;
    dcdqModuleDesc: string;
    dcdqVehicleCol: string;
    dcdqScoreACol: string;
    dcdqScoreDCol: string;
    dcdqScoreMCol: string;
    dcdqScoreWCol: string;
    dcdqScoreSCol: string;
    dcdqRankCol: string;
    dcdqWaitSliderLabel: string;
    dcdqMoistureSliderLabel: string;
    dcdqTriggerReorderBtn: string;
    dcdqReordering: string;
    dcdqReorderResultNotice: string;
    dcdqLiveQueueEmpty: string;
    dcdqRerankLiveBtn: string;
    dcdqRerankingLive: string;
    dcdqCanonicalFormulaNotice: string;

    // Module 2: ETA
    etaModuleTitle: string;
    etaModuleDesc: string;
    etaQueueAhead: string;
    etaPayloadAhead: string;
    etaServiceRate: string;
    etaActiveScales: string;
    etaCalculatedEta: string;
    etaScaleCountStepper: string;
    etaRecalculating: string;

    // Module 3: TAS BILP
    tasModuleTitle: string;
    tasModuleDesc: string;
    tasInputTrucks: string;
    tasCandidateSlots: string;
    tasSlotCapacity: string;
    tasPenalties: string;
    tasBeforeCongestion: string;
    tasOptimizedAssignment: string;
    tasAfterCongestion: string;
    tasRunSolverBtn: string;
    tasOptimizing: string;

    // Module 4: Redis Lock
    redisModuleTitle: string;
    redisModuleDesc: string;
    redisDisclaimer: string;
    redisConcurrentRequests: string;
    redisLockAcquisition: string;
    redisWinner: string;
    redisRejections: string;
    redisTtl: string;
    redisAtomicRelease: string;
    redisRunTestBtn: string;
    redisTesting: string;

    // Module 5: LWW
    lwwModuleTitle: string;
    lwwModuleDesc: string;
    lwwMutationA: string;
    lwwMutationB: string;
    lwwFieldConflict: string;
    lwwServerSequence: string;
    lwwClientTimestamp: string;
    lwwWinningValue: string;
    lwwDeduplication: string;
    lwwSyncStatus: string;
    lwwRunTestBtn: string;
    lwwTesting: string;

    // Module 6: HMAC
    hmacModuleTitle: string;
    hmacModuleDesc: string;
    hmacCanonicalPayload: string;
    hmacSignatureLength: string;
    hmacVerificationResult: string;
    hmacTamperedPayload: string;
    hmacRejectionResult: string;
    hmacSecretKeyRedacted: string;
    hmacRunVerifyBtn: string;
    hmacVerifying: string;
    hmacTestPayload: string;
    hmacTestFixtureNotice: string;
    hmacSyntheticFixtureInputs: string;

    // Module 7: Gzip
    gzipModuleTitle: string;
    gzipModuleDesc: string;
    gzipRawSize: string;
    gzipCompressedSize: string;
    gzipCompressionRatio: string;
    gzipRecordCount: string;
    gzipSyncResult: string;
    gzipRunCompressBtn: string;
    gzipCompressing: string;

    // Module 8: Logistic Booking Risk
    riskModuleTitle: string;
    riskModuleDesc: string;
    riskModelledDisclaimer: string;
    riskExpectedArrival: string;
    riskActualArrival: string;
    riskDeviation: string;
    riskParameterK: string;
    riskCalculatedRisk: string;
    riskDeviationSlider: string;
  };
  receipt: {
    title: string;
    govtHeader: string;
    jformSubheader: string;
    qrValid: string;
    printSlip: string;
    close: string;

    cryptoAuditTrail: string;
    ledgerHash: string;
    hmacToken: string;
    dbtRef: string;
  };
  admin: {
    title: string;
    subtitle: string;
    tabMandis: string;
    tabCrops: string;
    tabUsers: string;
    tabSlots: string;
    totalRegisteredFarmers: string;
    activeTransactions: string;
    queuedVehicles: string;
    volumeProcured: string;
    payoutSettled: string;
    qualityInspected: string;
    rejectionRate: string;
    activeWeighbridges: string;
    dailyCapacity: string;
    operationalStatus: string;
    simulateTraffic: string;
    simulatingTraffic: string;
    resetShowcase: string;
    resetting: string;
    resetConfirmPrompt: string;
    addMandi: string;
    addCrop: string;
    addUser: string;
    generateBatchSlots: string;
    generatingSlots: string;
    refreshData: string;
    toggleOperational: string;
    toggleActive: string;
    mandiName: string;
    districtState: string;
    dailyCapacityQt: string;
    weighbridges: string;
    status: string;
    actions: string;
    cropName: string;
    cropCode: string;
    category: string;
    mspPrice: string;
    optimalMoisture: string;
    maxMoisture: string;
    username: string;
    fullName: string;
    role: string;
    assignedMandi: string;
    slotTime: string;
    allocatedCapacity: string;
    bookedCapacity: string;
    remainingCapacity: string;
    scheduledDate: string;
    createMandiTitle: string;
    createCropTitle: string;
    createUserTitle: string;
    generateSlotsTitle: string;
    mandiNameLabel: string;
    districtLabel: string;
    stateLabel: string;
    dailyCapacityLabel: string;
    weighbridgesLabel: string;
    cropNameLabel: string;
    cropCodeLabel: string;
    categoryLabel: string;
    mspLabel: string;
    optimalMoistureLabel: string;
    maxMoistureLabel: string;
    usernameLabel: string;
    fullNameLabel: string;
    roleLabel: string;
    passwordLabel: string;
    targetDateLabel: string;
    startHourLabel: string;
    endHourLabel: string;
    capacityPerHourLabel: string;
    saveButton: string;
    cancelButton: string;
    activeStatus: string;
    inactiveStatus: string;
    operationalStatusActive: string;
    operationalStatusInactive: string;
    noMandisFound: string;
    noCropsFound: string;
    noUsersFound: string;
    noSlotsFound: string;
    selectMandiToViewSlots: string;
    offlineNotice: string;

    hubSubtitle: string;
    hubDesc: string;
    apmcBoardAdmin: string;
    eNamCloudAuth: string;
    offlineWalMode: string;
    backendOffline: string;
    backendOfflineDesc: string;
    startInTerminal: string;
    simulateTooltip: string;
    resetTooltip: string;
    liveDynamicStream: string;
    dcdqSorted: string;
    totalPipeline: string;
    quintalsProcured: string;
    pfmsSettled: string;
    moistureRejection: string;
    agriStackVerified: string;
    mandisSubtitle: string;
    cropsSubtitle: string;
    usersSubtitle: string;
    slotsSubtitle: string;
    universalAccess: string;
    noMandisAvailable: string;
    clickGenerateSlots: string;
    slotId: string;
    utilization: string;
    editMsp: string;
    deactivate: string;
    mandiNamePlaceholder: string;
    districtPlaceholder: string;
    statePlaceholder: string;
    cropNamePlaceholder: string;
    mspPriceUnit: string;
    optimalMoistureUnit: string;
    maxMoistureUnit: string;
    perQuintal: string;
    dataUnavailable: string;
    showcaseInjected: string;
    errorSimulating: string;
    showcaseResetClean: string;
    errorResetting: string;
    failedCreateMandi: string;
    mandiRegisteredSuccess: string;
    errorCreatingMandi: string;
    failedUpdateStatus: string;
    errorUpdatingMandiStatus: string;
    failedUpdateCommodity: string;
    commodityMspUpdated: string;
    errorUpdatingCrop: string;
    confirmDeactivateCommodity: string;
    failedDeactivateCommodity: string;
    commodityDeactivatedSuccess: string;
    errorDeactivatingCommodity: string;
    failedGenerateSlots: string;
    errorGeneratingSlots: string;
    slotsGeneratedSuccess: string;
    cropCodePlaceholder: string;
    resetFailed: string;
    simulationFailed: string;
    tasAdminTitle: string;
    tasAdminSubtitle: string;
    tasOptimizeNow: string;
  };
  journey: {
    modalTitle: string;
    modalSubtitle: string;
    runAll: string;
    runningAll: string;
    resetAll: string;
    close: string;
    statusPending: string;
    statusRunning: string;
    statusSuccess: string;
    statusFailed: string;
    statusBlocked: string;
    stageDetails: string;
    duration: string;
    invariantsChecked: string;
    payloadResponse: string;
    stage1Title: string;
    stage1Desc: string;
    stage2Title: string;
    stage2Desc: string;
    stage3Title: string;
    stage3Desc: string;
    stage4Title: string;
    stage4Desc: string;
    stage5Title: string;
    stage5Desc: string;
    stage6Title: string;
    stage6Desc: string;
    stage7Title: string;
    stage7Desc: string;
    stage8Title: string;
    stage8Desc: string;
    stage9Title: string;
    stage9Desc: string;
    stage10Title: string;
    stage10Desc: string;
    stage11Title: string;
    stage11Desc: string;
    stage12Title: string;
    stage12Desc: string;
    networkFailure: string;
    stageError: string;
    resetFailed: string;
    preflightFailed: string;
    stageFailed: string;
  };
  ussd: {
    simulatorTitle: string;
    simulatorSubtitle: string;
    activeCallState: string;
    standbyState: string;
    dialPrompt: string;
    sessionEnded: string;
    networkTimeout: string;
    transmittingPacket: string;
    inputLabel: string;
    sendDial: string;
    endCall: string;
    clearInput: string;
    callerLabel: string;
  };
  walMonitor: {
    bannerTag: string;
    title: string;
    description: string;
    refreshButton: string;
    syncBatch: string;
    syncingBatch: string;
    tabLedger: string;
    tabMaterialized: string;
    filterAll: string;
    filterPending: string;
    filterSynced: string;
    filterFailed: string;
    colMutationId: string;
    colType: string;
    colEntityId: string;
    colStatus: string;
    colTimestamp: string;
    colActions: string;
    noRecordsFound: string;
    viewPayload: string;
    modalPayloadTitle: string;
    serverMonotonicSeq: string;
    statusPending: string;
    statusSynced: string;
    statusFailed: string;
    lastSyncResultTitle: string;
    mutationsSynced: string;
    conflictsResolved: string;
    errorsEncountered: string;
    localTransactionsTitle: string;
    noLocalTransactions: string;
    colTxnId: string;
    colFarmerId: string;
    colMandiId: string;
    colCurrentState: string;

    totalMutations: string;
    indexedDbWal: string;
    pendingSync: string;
    queuedReplication: string;
    reconciled: string;
    acknowledgedServer: string;
    networkRail: string;
    liveCloudLink: string;
    offlineAirGap: string;
    directRestGzip: string;
    indexedDbLocalFallback: string;
    generateMutations: string;
    generateMutationsSubtitle: string;
    transactionId: string;
    currentState: string;
    farmer: string;
    mandi: string;
    syncStatus: string;
    lastUpdated: string;
    details: string;
    payloadInspector: string;
    mutationUuid: string;
    metadataAttributes: string;
    stateAttributes: string;
    targetState: string;
    hmacIntegrity: string;
    parsedPayload: string;
    materializedTransaction: string;
    aggregatedPayload: string;
    lastMutationId: string;
  };
}

export const translations: Record<'en' | 'hi', Translations> = {
  en: {
    common: {
      appName: 'MandiQ',
      appSubtitle: 'Intelligent Dynamic Queue & Local-First WAL',
      apmcPwa: 'APMC PWA',
      loading: 'Loading...',
      confirm: 'Confirm',
      cancel: 'Cancel',
      close: 'Close',
      refresh: 'Refresh',
      status: 'Status',
      action: 'Action',
      verified: 'VERIFIED',
      pending: 'PENDING',
      operational: 'Operational',
      today: 'Today',
      logout: 'Sign Out',
      online: 'ONLINE',
      offline: 'OFFLINE',
      synced: 'SYNCED',
      error: 'Error',
      success: 'Success',
      quintals: 'Quintals',
      kg: 'kg',
      inr: '₹',
      language: 'Language',
      all: 'All',
      search: 'Search',
      filter: 'Filter',
      details: 'Details',
      noData: 'No data available',

      activeTransaction: 'Active Transaction',
      apmcProcurementSystem: 'Agricultural Produce Market Committee Procurement System',

      backendOffline: 'Backend offline',
      inMemoryQueue: 'In-Memory Queue (Redis Fallback)',
      noActiveTransaction: 'No authoritative transaction selected.',
      tareWeightError: 'Physical Invariant Violation: Tare weight cannot be >= Gross weight.',
      noMandiSelected: 'No operational mandi selected.',
      reservationFailed: 'Reservation failed',
      cancellationFailed: 'Failed to cancel appointment',
      networkErrorCancel: 'Network error cancelling appointment.',
      selectOperationalMandi: 'Please select an operational mandi.',
      unlinkedFarmerReservation: 'Authenticated farmer profile is not linked. Slot reservation cannot proceed.',
      noVehiclesInQueue: 'No vehicles currently present in queue to dispatch.',
      jformMissingNetWeight: 'Cannot generate bill: Authoritative transaction has no verified net weight. Vehicle must complete weighbridge tare weighing first.',
      savedLocallyWal: 'Saved locally in IndexedDB transactionsWAL.',
      generateJformFirst: 'Please generate or fetch a valid J-Form invoice first.',
      dualSigAdminNotice: 'Dual-signature verification requires both Inspector and Operator cryptographic signatures. Prototype demo auto-approvals require ADMIN authorization.',
      dbtOfflineWal: '[OFFLINE WAL] Dual-signature DBT authorization stored locally in IndexedDB transactionsWAL. Ready to settle when online.',
      dbtPfmsConfirmed: 'Direct Benefit Transfer (DBT) confirmed by PFMS Settlement Rail!',
      dbtOfflineRecorded: 'Offline Blackout: Direct Benefit Transfer (DBT) recorded locally in Dexie. Will reconcile when online.',
      supervisorOverrideRecorded: '[OFFLINE WAL] Supervisor override recorded locally in Dexie. Truck re-admitted to dispatch queue.',
      adminBackendUnavailable: 'Backend unavailable. Reconnect to manage server-side administration.',
      noMandiSimulation: 'No operational mandi selected for simulation.',
      noMandiReset: 'No operational mandi selected for reset.',
      initializing: 'Initializing MandiQ System...',
      txnPlaceholder: 'e.g. TXN-...',
      load: 'Load',
      txnNotFound: 'Authoritative transaction "{txnId}" not found.',
      txnNotFoundServer: 'Authoritative transaction "{txnId}" not found on server.',
      txnNotFoundLocally: 'Transaction "{txnId}" not found locally or remotely.',
      txnFarmerMismatch: 'Transaction belongs to Farmer #{txnFarmerId}, but active session is Farmer #{sessionFarmerId}',
      txnMandiMismatch: 'Transaction belongs to Mandi #{txnMandiId}, but selected Mandi is #{selectedMandiId}',
      txnInvalidState: 'Transaction is in state \'{currentState}\', but required state is one of: [{allowedStates}]',
      networkError: 'Network connection error. Please verify your connection.',
      adminDataUnavailable: 'Admin data unavailable: {errors}',
      demoFarmersError: 'Network error fetching demo farmers',
      crop: 'Crop',
    },
    nav: {
      admin: 'Admin Hub',
      farmer: 'Farmer Portal',
      gate: 'Gate Terminal',
      quality: 'Quality Gate',
      queue: 'Live Queue',
      weighbridge: 'Weighbridge',
      billing: 'Billing & DBT',
      sync: 'Offline WAL',
      advanceStation: 'Advance Station',
      nextStation: 'Next station',
      demoTools: 'Demo Tools',
    },
    roles: {
      admin: 'Administrator',
      supervisor: 'Yard Supervisor',
      inspector: 'Quality Assayer',
      operator: 'Gate & Weighbridge Operator',
      farmer: 'Verified Farmer',
    },
    login: {
      title: 'APMC Gate & Procurement Gateway',
      subtitle: 'Decentralized Queue Dispatch & Local-First Assaying Terminal',
      selectRole: 'Select Station Role',
      username: 'Operator / Aadhaar ID',
      usernamePlaceholder: 'Enter your registered identity ID',
      password: 'Security Passcode',
      passwordPlaceholder: 'Enter security passcode',
      signIn: 'Authenticate & Access Terminal',
      signingIn: 'Verifying Security Credentials...',
      quickDemoUsers: 'Quick Demo Access Accounts',
      credentialsError: 'Invalid credentials. Please verify your ID and passcode.',
      offlineFallbackNotice: 'Offline Mode: Operating with cached local credentials.',

      hmacSession: 'Cryptographically signed HMAC-SHA256 session',
      footerStandards: 'MandiQ APMC Procurement System • National Standards',
    },
    farmer: {
      greeting: 'Namaste, {name}',
      profileTitle: 'Verified Kisan Profile',
      kisanId: 'Kisan ID',
      mobile: 'Registered Mobile',
      remainingCeiling: 'Remaining Crop Ceiling',
      availableCapacity: 'Available Capacity',
      remainingAfterBooking: 'Remaining After Booking',
      targetMandi: 'Procurement Mandi',
      yardOperational: 'Yard Operational',
      processFlow: 'Procurement Process Workflow',
      stepOf: 'Step {current} of {total}',
      step1Crop: 'Registered Crop',
      step2Token: 'Token Issued',
      step3Gate: 'Gate Entry',
      step4Quality: 'Assaying',
      step5Weight: 'Weighbridge',
      step6Payment: 'DBT Payout',
      activeToken: 'Active Delivery Appointment Token',
      tokenNo: 'Token Number',
      scanAtGate: 'Present this QR barcode upon arrival at the APMC entry gate.',
      cancelSlot: 'Cancel Reservation',
      cancelSlotPrompt: 'Are you sure you want to cancel this scheduled delivery slot?',
      viewReceipt: 'View Digital J-Form Receipt',
      bookDeliveryTitle: 'Schedule Harvest Delivery',
      bookDeliverySubtitle: 'Reserve an hourly arrival window to eliminate physical queue delays.',
      step1Title: 'Select Registered Crop',
      govtMsp: 'Govt. MSP',
      loadingCrops: 'Loading registered crops...',
      noCrops: 'No crops found for this mandi.',
      step2Title: 'Delivery Quantity (Quintals)',
      quantityHint: 'Specify quantity in quintals (1 qt = 100 kg = 0.1 tonne)',
      quickPills: 'Quick Selection',
      step3Title: 'Land Cultivator Verification',
      landTenure: 'Cultivator Status',
      ownerCultivator: 'Owner Cultivator',
      ownerDesc: 'Self-owned land with verified AgriStack record.',
      tenantCultivator: 'Tenant / Sharecropper',
      tenantDesc: 'Cultivating under lease agreement.',
      landownerName: 'Landowner Full Name',
      landownerNamePlaceholder: 'Enter name as on revenue record',
      panchayatCert: 'Panchayat Verification Certificate No.',
      panchayatCertHint: 'Certificate from Gram Panchayat or Tehsildar',
      bonaFideDeclaration: 'I declare under penalty of law that this produce is cultivated by me.',
      step4Title: 'Procurement Date',
      scheduledDate: 'Select Arrival Date',
      step5Title: 'Available Hourly Slots',
      slotsHint: 'Hourly arrival slot prevents road congestion and yard stagnation.',
      loadingSlots: 'Loading hourly slots...',
      noSlots: 'No available slots for this date.',
      capacityRemaining: 'remaining',
      confirming: 'Reserving Slot...',
      reserveButton: 'Confirm Delivery Appointment',
      slotUnavailable: 'Selected slot is exhausted. Please pick an alternative time.',
      valQtyPositive: 'Quantity must be greater than zero.',
      valQtyExceedsCeiling: 'Requested quantity exceeds your remaining production ceiling.',
      valLandownerRequired: 'Landowner name is required for tenant cultivators.',
      valBonaFideRequired: 'You must check the bona fide cultivator declaration.',
      valSlotRequired: 'Please select an arrival slot to continue.',
      valOfflineBooking: 'Saved locally in Offline WAL. Will synchronize once connected.',
      appointmentSuccess: 'Appointment confirmed! Your QR delivery pass is ready.',

      targetMandiAndDate: 'Target APMC Mandi & Date',
      sourceOfTruthSlots: 'Source of truth for hourly slots',
      destinationMandi: 'Destination Mandi',
      noMandisAvailable: 'No operational mandis available',
      scheduledDeliveryDate: 'Scheduled Delivery Date',
      minus: 'Minus',
      plus: 'Plus',
      unlinkedProfileTitle: 'Authenticated farmer profile is not linked',
      unlinkedProfileDesc: 'Your login account is not currently linked to an operational farmer profile in the APMC database. Slot reservations are disabled until a verified farmer profile is linked.',
      appointmentCancelledSuccess: 'Scheduled delivery slot reservation cancelled successfully.',
      invalidQuantityError: 'Please enter a valid procurement quantity in quintals greater than zero.',
      ceilingExceededError: 'Specified quantity exceeds your remaining verified land ceiling ({remaining} Qtl).',
      slotCapacityExhaustedError: 'The selected arrival slot capacity is exhausted. Please select another slot.',
      arrivalRiskTitle: 'Scheduled Arrival Window Risk',
      modelledRiskBadge: 'MODELLED RISK — NOT AN ACTUAL FAILURE PREDICTION',
      expectedTime: 'Expected Arrival',
      actualTime: 'Actual / Est. Arrival',
      deviationMinutes: 'Arrival Deviation',
      riskProbability: 'Modelled Failure Probability',
    },
    gate: {
      title: 'APMC Inbound Gate Terminal',
      subtitle: 'QR Token Cryptographic Verification & Fast Vehicle Check-in',
      scanQrTitle: 'Scan Farmer Delivery Pass',
      scanQrSubtitle: 'Verify digital signature and HMAC validity.',
      tokenPlaceholder: 'Enter Token No. or scan QR barcode',
      verifyButton: 'Verify Cryptographic Token',
      verifying: 'Verifying Signature...',
      driverMobile: 'Driver Mobile Number',
      vehicleNo: 'Vehicle Registration Number',
      vehicleNoPlaceholder: 'e.g., MP-04-AB-1234',
      checkInButton: 'Admit Vehicle to Yard',
      checkingIn: 'Recording Gate Check-In...',
      checkInSuccess: 'Vehicle admitted successfully. Directed to Quality Assaying Station.',
      waitingVehicle: 'Vehicle Waiting at Inbound Barrier',
      entryVerified: 'Gate Entry Verified',
      inspectionReady: 'Proceed to Assaying Station',

      cryptoRules: 'Cryptographic Protocol Rules',
      tamperProtection: 'Tamper Protection',
      tamperDesc: 'Any alteration to quantity, farmer ID, or slot invalidates the 64-character HMAC token signature.',
      offlineResilience: 'Offline Resilience',
      offlineDesc: 'During cellular blackouts, gate verification executes locally in IndexedDB without unhandled exceptions.',
      stateProgression: 'State Progression',
      stateProgressionDesc: 'Successful check-in transitions transaction state to',
      stateProgressionSuffix: 'and routes truck to Quality Assaying.',
      farmerIdPlaceholder: 'Farmer ID',
      slotIdPlaceholder: 'Slot ID',
      signaturePlaceholder: '64-character hex signature...',
      entryVerifiedDetails: 'Gate Entry Verified for {farmerName} ({crop}). State: {state}. Authorized for mandi yard staging entry.',
      passValidationFailed: 'Gate pass failed cryptographic signature or structural validation.',
      checkinRejected: 'Gate check-in rejected.',
      passVerifiedOnline: 'Gate Pass Verified! Authoritative cloud check-in synchronized and vehicle admitted.',
      passVerifiedOffline: '[OFFLINE PROVISIONAL] Gate entry structurally verified and committed to IndexedDB WAL. Vehicle admitted under offline protocol.',
      verificationFailed: 'Gate verification failed',
      noTxnPrompt: 'No active transaction selected. Please select an active transaction from the queue or recent workflow, or enter a Transaction ID below:',
      hmacFormatInvalid: 'Invalid HMAC signature format: expected 64-character hexadecimal digest, received {length} chars',
      hmacMissing: 'Missing cryptographic token signature',
      mandiMismatchError: 'Mandi Mismatch: Gate pass is registered for Mandi ID {passMandi}, but this terminal is Mandi ID {terminalMandi}',
      yieldCeilingExceeded: 'Yield Ceiling Exceeded: {projected} qt would exceed farmer ceiling of {ceiling} qt',
    },
    quality: {
      title: 'Digital Quality Assaying Gate',
      subtitle: 'IoT Sensor Telemetry & Automated APMC Grade Standards',
      sensorReading: 'Sensor Telemetry',
      cropMoisture: 'Grain Moisture Content',
      optimalRange: 'Optimal: <= 12.0%',
      maxLimit: 'Max Limit: 17.0%',
      assessing: 'Assaying Crop Quality...',
      assessButton: 'Record Quality Assessment',
      resultApproved: 'Quality Approved: Grade-A APMC Standard',
      resultRejected: 'Rejected: Moisture exceeds maximum 17.0% threshold',
      eligibleForQueue: 'Admitted to Dynamic Priority Queue',
      routedToDrying: 'Directed to Solar Drying Yard',
      routeToDrying: 'Send to Drying Yard',
      priorityScore: 'Computed DCDQ Priority Score',
      supervisorOverrideTitle: 'Supervisor Quality Override',
      overrideReason: 'Official Justification for Variance Override',
      overrideButton: 'Authorize Supervisory Override',
      overriding: 'Authorizing Override...',

      supervisorAuthToken: 'Supervisor Authorization Token',
      supervisorAuthTokenPlaceholder: '•••••••• (Supervisor Security PIN)',
      technicalFormulasInDemoTools: 'Technical prioritization formulas and dynamic queue weights are located in Demo Tools → Algorithm Center.',
      standardsTitle: 'APMC Lot Assaying Standards',
      gradeATitle: 'Grade A (FAQ Standard)',
      gradeADesc: 'Lot directly accepted for immediate weighment and electronic MSP settlement.',
      gradeBTitle: 'Grade B (Priority Lot)',
      gradeBDesc: 'Admitted to priority queue to ensure timely processing and avoid yard decay.',
      rejectionTitle: 'Quality Rejection',
      rejectionDesc: 'Excessive moisture detected. Diverted to solar drying apron unless authorized by supervisor.',
      calibratedMoisture: 'Calibrated Moisture Analyzer Reading',
      confirmOverride: 'Confirm Supervisor Quality Override',
      dcdqFormula: 'P(lot) = 0.35 * P_arrival + 0.30 * P_moisture + 0.20 * P_wait + 0.15 * P_demurrage',
      elapsedWaitMinutes: 'Elapsed Yard Wait Time',
      cannotAssessState: 'Cannot assess quality: Transaction is in state \'{state}\'. Expected \'GATE_ENTRY_VERIFIED\'.',
      assessmentRejected: 'Quality assessment rejected by server',
      assessmentFailed: 'Quality assessment failed',
      offlineRejected: '[OFFLINE WAL] Lot rejected: Moisture exceeds 17.0% limit. Stored locally.',
      offlineApproved: '[OFFLINE WAL] Quality approved and stored to IndexedDB transactionsWAL. Will sync to Redis queue when online.',
      overrideFailed: 'Supervisor override failed',
      supervisorOverrideAuthorized: 'Supervisor Override Authorized: {message}',
      preflightNotice: 'Please book a slot and complete Gate Entry verification before quality assaying.',
      unauthorizedRole: 'Access restricted: Station requires INSPECTOR, SUPERVISOR, or ADMIN role.',
      autoResolvedGate: 'Auto-resolved incoming vehicle verified at Gate',
      awaitingGateLots: 'Awaiting incoming lots verified at Gate...',
    },
    queue: {
      title: 'real time Yard Queue Dispatcher',
      subtitle: 'Real-Time DCDQ FIFO & Anti-Starvation Traffic Controller',
      liveQueueStatus: 'Live Yard Queue Registry',
      vehiclesWaiting: 'Vehicles Awaiting Weighment',
      rank: 'Rank',
      tokenNo: 'Token No.',
      farmer: 'Farmer',
      quantity: 'Quantity',
      dcdqScore: 'DCDQ Score',
      status: 'Status',
      dispatchButton: 'Dispatch to Weighbridge',
      dispatching: 'Dispatching...',
      emptyQueue: 'Queue is clear. No vehicles awaiting weighment.',
      emptyQueueHint: 'Admitted vehicles from Quality Assaying will appear here.',
      dispatchedToWeighbridge: 'Vehicle dispatched to Weighbridge Scale.',
      offlineNotice: 'Queue offline: displaying locally cached queue if available.',
      fetchError: 'Network error fetching queue',
      simulationInjected: 'Showcase traffic injected. Live DCDQ re-ordered queue.',
      simulationError: 'Simulation error',
      resetSuccess: 'Showcase queue reset to clean baseline.',
      resetError: 'Reset error',
      dispatchFailed: 'Dispatch failed',
      offlineDispatched: '[OFFLINE LOCAL] Vehicle {txnId} popped from local queue and routed to weighbridge.',
      dispatchError: 'Dispatch error',
      scoreA: 'A (Adherence)',
      scoreD: 'D (Demurrage)',
      scoreM: 'M (Moisture)',
      scoreW: 'W (Wait Bonus)',
      scoreS: 'S (Final Score)',
      scoreBreakdown: 'DCDQ Component Decomposition',
      adherence: 'Appointment Adherence',
      demurrage: 'Demurrage & Weight',
      moistureRisk: 'Crop Moisture Risk',
      waitBonus: 'Anti-Starvation Wait Bonus',
      advanceQueueTime: 'Advance Showcase Time',
      advancingQueueTime: 'Advancing Time...',
      rerankQueue: 'Recalculate & Rerank',
      rerankingQueue: 'Reranking...',
      offlineProvisional: 'OFFLINE — PROVISIONAL',
      authoritativeRouted: 'AUTHORITATIVE — ROUTED_TO_WEIGHBRIDGE',
      conflictRejected: 'CONFLICT — REJECTED',
      dispatchedVehiclesTitle: 'Dispatched to Weighbridge',
      dispatchedVehiclesDesc: 'Vehicles routed from active queue to gross weighment',
      noDispatchedVehicles: 'No vehicles dispatched yet.',
      offlineDispatchedProvisional: '[OFFLINE WAL] Vehicle {txnId} dispatched offline (Provisional). Stored in IndexedDB WAL.',
      dispatchedAuthoritative: '[AUTHORITATIVE] Vehicle {txnId} routed to weighbridge scale.',
      estimatedWait: 'Estimated Wait',
      estimatedWaitNext: 'Estimated wait: Next in line (0 min)',
      calculatingTelemetry: 'Estimated wait: Calculating... (Insufficient Telemetry)',
      vehiclesAhead: 'Vehicles ahead',
      payloadAhead: 'Payload ahead',
      serviceRate: 'Service rate',
      activeScales: 'Active scales',
      scaleOffline: 'Scale Offline',
      scaleOnline: 'Scale Online',
      toggleScale: 'Toggle Scale',
      technicalBreakdown: 'Technical Decomposition (M(t)/E_k/c(t) Estimator)',
      crop: 'Crop',
      moisture: 'Moisture',
      appointmentAdherence: 'Appointment Adherence',
      demurrageScore: 'Demurrage',
      moistureRiskScore: 'Moisture Risk',
      antiStarvationWait: 'Anti-Starvation Wait',
      finalDcdqScore: 'Final DCDQ Score',
      liveQueueHeader: 'LIVE QUEUE',
      operationalTelemetry: 'OPERATIONAL TELEMETRY',
      algorithmSimulationHeader: 'ALGORITHM SIMULATION',
      algorithmSimulationDesc: 'Simulated traffic and scenario controls. Isolated from live operational transactions.',
      simulatedLot: 'SIMULATED',
      scaleCount1: '1 Scale',
      scaleCount2: '2 Scales',
      scaleCount3: '3 Scales',
      scales: 'Scales',
      dcdqFormulationSubtitle: 'DCDQ Multi-Factor Priority Formulation',
      serviceRateTelemetry: 'Service Rate Telemetry',
    },
    weighbridge: {
      title: 'Electronic Weighbridge Scale',
      subtitle: 'Load-Cell Telemetry & Gross/Tare Weight Calculation',
      grossWeight: 'Gross Weight (Loaded Truck)',
      tareWeight: 'Tare Weight (Empty Truck)',
      netWeight: 'Net Weight (Produce)',
      scaleReading: 'Live Digital Scale Reading',
      captureGross: 'Capture Gross Weight',
      capturingGross: 'Capturing Scale Telemetry...',
      captureTare: 'Capture Tare Weight',
      capturingTare: 'Capturing Empty Scale...',
      weightSummary: 'Weighment Certified Summary',
      proceedToBilling: 'Proceed to J-Form Billing & Payout',
      tareInstruction: 'Empty truck on scale after yard unloading to determine net produce weight.',

      rulesTitle: 'Weighbridge Operational Rules',
      physicalInvariant: 'Physical Invariant',
      physicalDesc: 'Tare weight must strictly be < Gross weight ($Tare \ge Gross$ is rejected with HTTP 422).',
      yieldCeiling: 'Yield Ceiling Enforcement',
      yieldDesc: 'Net delivered weight plus prior delivered batches cannot exceed the farmer\'s registered production ceiling.',
      distributedLock: 'Redis Atomic Reservation Lock',
      lockDesc: 'Parallel weighments for the same farmer serialize under',
      lockSuffix: 'to eliminate race conditions.',
      captureUnified: 'Record Certified Net Weight',
      scaleInvariance: 'Scale Reading Invariance & Calibration Verified',
      twoStepWeighment: 'Two-Step Weighment (Gross & Tare)',
      unifiedWeighment: 'Unified Weighment Telemetry',
      vehicleMustBeRouted: 'Transaction is in state \'{state}\'. Vehicle must be routed to weighbridge before gross capture.',
      grossRejected: 'Gross weighment rejected by server',
      grossRecordedProceedTare: 'Gross weight recorded: {gross} qt. State: {state}. Now proceed to unload grain and capture tare weight.',
      offlineGrossSaved: '[OFFLINE WAL] Gross weight ({gross} qt) saved to IndexedDB transactionsWAL.',
      errorGross: 'Error capturing gross weight',
      grossMustBeCapturedBeforeTare: 'Transaction is in state \'{state}\'. Gross weight must be captured before tare weight.',
      tareRejected: 'Tare weighment rejected by server',
      tareRecordedNetSettlement: 'Tare weight recorded: {tare} qt. Net Settlement: {net} qt. State: {state}. Ready for J-Form billing.',
      offlineTareSaved: '[OFFLINE WAL] Tare weight ({tare} qt) saved to IndexedDB transactionsWAL. Net weight: {net} qt.',
      errorTare: 'Error capturing tare weight',
      unifiedRejected: 'Unified weighment rejected by server',
      unifiedCaptured: 'Unified Weighment Captured: Gross={gross} qt, Tare={tare} qt, Net={net} qt. State: {state}.',
      offlineUnifiedSaved: '[OFFLINE WAL] Unified weighment saved to IndexedDB transactionsWAL. Net weight: {net} qt.',
      errorWeighment: 'Error capturing weighment',
      preflightNotice: 'Please dispatch a vehicle from the Live Priority Queue to perform weighbridge scale capture.',
      activeLaneVehicles: 'Active Vehicles in Lane',
      selectVehiclePrompt: 'Select vehicle from queue to begin weighment',
      invalidTareRange: 'Tare weight must be strictly positive and less than gross weight (0 < tare < gross)',
      autoResolvedQueue: 'Auto-selected vehicle from Live Queue',
      noVehiclesInLane: 'No vehicles currently queued or awaiting weighment.',
    },
    billing: {
      title: 'Procurement Billing & Direct Benefit Transfer',
      subtitle: 'Official J-Form Settlement & Cryptographic Dual-Signature DBT',
      jformTitle: 'Official J-Form Joint-Sale Certificate',
      invoiceNo: 'J-Form Invoice Number',
      mandiName: 'Procuring APMC Mandi',
      cropName: 'Procured Commodity',
      netWeight: 'Certified Net Weight',
      mspPrice: 'Applicable Govt. MSP',
      grossPayable: 'Gross Produce Value',
      mandiDeductions: 'Statutory APMC Market Deductions',
      netPayable: 'Net DBT Payment to Farmer',
      generateInvoice: 'Generate Official J-Form',
      generateButton: 'Generate Official J-Form',
      generating: 'Generating Invoice...',
      dualSignatureRequired: 'Dual Cryptographic Signatures Required',
      inspectorSig: 'Quality Assayer Signature',
      operatorSig: 'Weighbridge Operator Signature',
      authorizePayout: 'Authorize & Disburse DBT Payout',
      authorizing: 'Processing Cryptographic Authorization...',
      payoutSettled: 'Payment Settled: DBT Bank Transfer Initiated',
      dbtReference: 'PFMS / DBT Reference Number',

      deductionsCut: 'Moisture or handling cut',
      targetInvoiceAmount: 'Target Invoice Amount',
      verifyingSignatures: 'Verifying Cryptographic Signatures...',
      stageDualSignature: 'Stage Dual-Signature DBT Payout',
      simulatePfms: 'Simulate PFMS / NPCI Aadhaar Settlement Direct Rail',
      officialFormJ: 'Official Form J — Sale Intimation & Receipt',
      totalNetAmount: 'Total Net Amount Payable',
      totalDisbursement: 'Total Approved Disbursement',
      farmerName: 'Farmer Name',
      commodityNetQty: 'Commodity / Net Qty',
      ratePerQuintal: 'Rate Per Quintal',
      totalDeductions: 'Total Deductions',
      dbtConfirmation: 'Government DBT Settlement Confirmation',
      payoutBlockHash: 'Cryptographic Payout Block Hash',
      pfmsReference: 'PFMS Aadhaar Reference',
      inspectorRemarks: 'Inspector Remarks',
      inspectorHmac: 'Inspector HMAC-SHA256',
      operatorHmac: 'Operator HMAC-SHA256',
      enterOrVerifyHmac: 'Enter or auto-verify HMAC',
      noCropSpecified: 'No crop commodity specified for active transaction.',
      mspNotFoundInMaster: 'Authoritative MSP not found in Crop Master for \'{crop}\'.',
      failedFetchCropMaster: 'Failed to fetch Crop Master directory.',
      vehicleMustBeWeighedTare: 'Transaction is in state \'{state}\'. Vehicle must be in \'WEIGHED_TARE\' before generating J-Form.',
      mspUnresolvedWait: 'Authoritative crop MSP is unresolved. Please wait for Crop Master resolution.',
      jformRejectedServer: 'J-Form billing rejected by server',
      invoiceGeneratedDualSig: 'Official J-Form invoice generated: ₹{amount}. State: {state}. Ready for dual-signature payout staging.',
      offlineInvoiceSaved: '[OFFLINE WAL] J-Form invoice (₹{amount}) saved to IndexedDB transactionsWAL.',
      unknownBillingError: 'Unknown billing error',
      failedGenerateDemoSigs: 'Failed to generate demo signatures.',
      couldNotObtainDemoSigs: 'Could not obtain demo signatures.',
      payoutStagingFailed: 'Payout staging failed',
      payoutStagedSettled: 'DBT Payout Staged & Settled! Block Hash: {hash}...',
      generateJformFirstDbt: 'Cannot trigger DBT disbursement: Please generate a J-Form invoice first.',
      pfmsSimRejected: 'PFMS Aadhaar Payment Rail simulation rejected.',
      dbtFailed: 'DBT disbursement failed',
      preflightNotice: 'Please complete weighbridge net settlement before generating J-Form billing.',
      mspRatePlaceholder: 'Authoritative MSP rate',
      resolvingMsp: 'Resolving MSP...',
      unresolved: 'Unresolved',
      resolvingAuthoritativeMsp: 'Resolving Authoritative MSP...',
      authoritativeSettlementSummary: 'Authoritative Procurement Settlement',
      grossValue: 'Gross Value',
      dbtStatus: 'DBT Status',
      statusPendingStaging: 'Pending Staging',
      statusStaged: 'Dual-Signature Staged',
      statusSettled: 'Payment Settled via PFMS',
      autoResolvedWeighed: 'Auto-resolved vehicle with completed weighment',
    },
    sync: {
      title: 'Offline Write-Ahead Log (WAL) Sync',
      subtitle: 'Local-First Ledger & Cryptographic Replay Security',
      walStatus: 'IndexedDB WAL Status',
      pendingMutations: 'Pending Offline Mutations',
      syncedMutations: 'Synced Mutations',
      triggerSync: 'Synchronize All Mutations Now',
      syncing: 'Syncing with Mandi Server...',
      mutationId: 'Mutation ID',
      targetState: 'Target State',
      timestamp: 'Logged At',
      statusLabel: 'Sync Status',
    },
    demoTools: {
      title: 'MandiQ Demonstration Suite',
      subtitle: 'Showcase Controls, Farmer Switching & Technical Verification',
      tabControls: 'Showcase Actions',
      tabFarmerSwitcher: 'Switch Showcase Farmer',
      tabEvidence: 'Technical Evidence',
      resetShowcase: 'Reset Demo Database',
      resetting: 'Resetting Database...',
      resetSuccess: 'Demo database cleanly reset to baseline state.',
      simulateTraffic: 'Simulate Dynamic Traffic',
      simulatingTraffic: 'Generating vehicles...',
      simulateBlackout: 'Simulate Rural Grid/Internet Blackout',
      blackoutActive: 'Outage simulation active: Offline Mode enforced.',
      launchE2E: 'Run Full End-to-End Automated Journey',
      resetShowcaseDesc: 'Restores deterministic demo state',
      simulateTrafficDesc: 'Creates several real showcase queue records',
      launchE2EDesc: 'Advances one showcase transaction through the real workflow',
      showcaseCommandCenter: 'Showcase Demo Controls',
      showcaseSubtitle: 'Deterministic Showcase Suite',
      openUSSD: 'Open Feature Phone USSD Simulator (*247#)',
      switchFarmerTitle: 'Showcase Farmer Selection',
      switchFarmerDesc: 'Select an authorized farmer profile to inspect dynamic ceiling and booking isolation.',
      activeContextNotice: 'Prototype Demonstration Context: For evaluation and testing purposes.',
      technicalEvidenceTitle: 'MandiQ Technical Architecture & Invariants',
      dcdqTitle: 'DCDQ Multi-Criteria Priority Formulation',
      dcdqFormula: 'S_i = alpha * A_i + beta * D_i + gamma * M_i + lambda * W_i',
      dcdqAlpha: 'alpha * A_i (Distance Factor): Prioritizes smallholders traveling from remote villages.',
      dcdqBeta: 'beta * D_i (Perishability Factor): Protects high-spoilage agricultural commodities.',
      dcdqGamma: 'gamma * M_i (Moisture Factor): Prioritizes 15-17% moisture grain to prevent mold formation.',
      dcdqLambda: 'lambda * W_i (Anti-Starvation Bonus): Dynamically increases score to prevent starvation.',
      invariantsTitle: 'Guaranteed Mathematical & Security Invariants',
      invCeiling: 'Farmer Production Ceiling: Active bookings cannot exceed registered land yield capacity.',
      invSlot: 'Hourly Slot Capacity: Inbound hourly volume cannot exceed yard gate throughput limits.',
      invState: 'Monotonic Lifecycle: Mandatory progression (Gate -> Assaying -> Weighment -> Billing -> Payout).',
      invCrypto: 'Cryptographic Integrity: Tamper-evident HMAC-SHA256 tokens fail closed if secret or payload altered.',
      invWal: 'Local-First Offline WAL: ACID-compliant IndexedDB mutation queue with monotonic sequence replay.',

      accessRestricted: 'Access Restricted',
      accessRestrictedDesc: 'Demo Tools and Technical Evidence are restricted to Mandi Board Administrators and APMC Yard Supervisors.',
      invCeilingTitle: '1. Yield Ceiling Invariant',
      invSlotTitle: '2. Slot Capacity Invariant',
      invStateTitle: '3. Monotonic Lifecycle',
      invCryptoTitle: '4. HMAC-SHA256 Cryptography',
      invWalTitle: '5. Local-First Write-Ahead Log',
      farmerSwitched: 'Active demo farmer switched to: {name} (Farmer ID: {id}).',
      advanceTime: 'Advance Showcase Time',
      advancingTime: 'Advancing Showcase Time...',
      advanceTimeDesc: 'Simulates elapsed waiting time using isolated simulation clock to demonstrate dynamic DCDQ anti-starvation reordering.',
      optimizeSlots: 'Optimize Appointment Slots',
      optimizeSlotsDesc: 'Executes HiGHS BILP optimization to balance yard slot distribution and minimize total congestion.',
      tasTitle: 'TAS BILP Slot Optimizer',
      tasSubtitle: 'Mixed-Integer Linear Program for Inbound Truck Load Balancing (Algorithm 6)',
      tasRunSolver: 'Run HiGHS BILP Solver',
      tasSolving: 'Solving Linear Program...',
      tasBefore: 'BEFORE',
      tasAfter: 'AFTER',
      tasOverload: 'Yard Overload',
      tasObjective: 'Objective Value',
      tasMaxSlotLoad: 'Max Slot Load',
      tasTrucks: 'trucks',
      tasSolverBadge: 'HiGHS BILP Solver',
      failureModelTitle: 'Logistic Booking Failure Risk Model',
      failureModelDesc: 'Evaluates empirical probability of appointment failure based on time arrival deviations.',
      failureModelLabel: 'MODELLED RISK — NOT AN ACTUAL FAILURE PREDICTION',
      expectedArrival: 'Expected Arrival',
      actualArrival: 'Actual Arrival',
      arrivalDeviation: 'Arrival Deviation',
      failureProbability: 'Failure Probability',
      concurrentBookingTitle: 'Concurrent Slot Booking Test',
      concurrentBookingDesc: 'Simulates 10 concurrent reservations against the same slot using Redis SET NX PX atomic locking.',
      runConcurrentTest: 'Run Concurrent Booking Test',
      runningConcurrentTest: 'Testing Concurrent Locks...',
      totalRequests: 'Total Requests',
      successfulRequests: 'Successful',
      rejectedRequests: 'Rejected',
      capacityExceededZero: 'Capacity Exceeded: 0',
      lockAcquisitionTimeline: 'Lock Acquisition & Release Timeline',
      redisMutexBadge: 'Redis SET NX PX Distributed Mutex (Prototype)',
      lwwConflictTitle: 'LWW Conflict Resolution (Authoritative Server Sequence)',
      lwwConflictDesc: 'Visualizes field-level Last-Write-Wins merge using authoritative server sequence.',
      runLWWTest: 'Demonstrate LWW Resolution',
      runningLWWTest: 'Resolving Conflicts...',
      lwwMutationA: 'Mutation A',
      lwwMutationB: 'Mutation B',
      authoritativeSequenceWinner: 'Higher Authoritative Server Sequence',
      governanceNotice: 'Governance Notice: Authoritative conflict ordering is governed by server_receive_sequence, not client clocks.',
      clientTimestampDiagnostic: 'Client Timestamp (Diagnostic Metadata)',
      field: 'Field',
      oldValue: 'Old Value',
      incomingValue: 'Incoming Value',
      winner: 'Winner',
      reason: 'Resolution Reason',
      gzipSyncTitle: 'Offline WAL Gzip Compression Evidence',
      gzipSyncDesc: 'Demonstrates IndexedDB WAL batch compression before transmission to cloud server.',
      testGzipSync: 'Test Gzip WAL Sync',
      testingGzipSync: 'Compressing & Syncing...',
      rawSize: 'Raw Payload Size',
      compressedSize: 'Compressed Gzip Size',
      compressionRatio: 'Compression Savings',
      recordCount: 'Record Count',
      decompressionVerified: 'Decompressed & Verified on Server',
      slotCapacity: 'Slot Capacity (Qt)',
      serverSequence: 'server_receive_sequence',
      tabAlgorithms: 'Algorithm Control Center',
    },
    controlCenter: {
      title: 'MandiQ Algorithm Control Center',
      subtitle: 'Authoritative Live Execution Showcase of Real Operational Algorithms',
      dataIsolationNotice: 'All algorithms execute with is_showcase=true. Operational procurement records are strictly isolated.',
      resetDemoBtn: 'Reset Algorithm Demo',
      resettingDemo: 'Purging Demo Records...',
      resetDemoSuccess: 'Algorithm demo records cleanly purged. Real procurement logs strictly preserved.',
      statusLive: 'LIVE SYSTEM',
      statusSimulation: 'CONTROLLED SIMULATION',
      statusAlgoDemo: 'ALGORITHM DEMONSTRATION',
      statusDemo: 'ALGORITHM DEMONSTRATION',
      statusDocumented: 'DOCUMENTED ONLY',
      statusNotImplemented: 'NOT IMPLEMENTED IN CURRENT BUILD',
      verifiedStatus: 'Verification Status',
      executionTrace: 'Execution Trace',
      formulaLabel: 'Canonical Formula',
      liveInputsLabel: 'Live Inputs & Controls',
      actualOutputLabel: 'Actual Computed Output',
      summaryCountLive: 'Live Operational',
      summaryCountDemo: 'Executing Showcase',
      summaryCountDocumented: 'Documented Reference',
      summaryCountNotImplemented: 'Not Implemented',
      mandiSelectionRequiredDesc: 'Algorithm operations, live queue telemetry, and showcase tests require an active selected mandi. Zero magic identity fallbacks permitted per DATA-001.',
      twoModules: '2 Modules',
      sixModules: '6 Modules',
      liveModulesSummary: '1. DCDQ Live APMC Queue & 2. Multi-Server ETA (100% Live Backend Results)',
      demoModulesSummary: '3. TAS BILP, 4. Redis Atomic Lock, 5. Server-Seq Merge, 6. HMAC, 7. Gzip, 8. Logistic Risk',

      // Module 1: DCDQ
      dcdqModuleTitle: '1. DCDQ Dynamic Queue Prioritization',
      dcdqModuleDesc: 'Dynamic Crop-Dehydration and Congestion Queue (DCDQ) sorts vehicles in Redis ZSET descending by composite priority score S_i.',
      dcdqVehicleCol: 'Vehicle / Lot',
      dcdqScoreACol: 'A (Adherence)',
      dcdqScoreDCol: 'D (Demurrage)',
      dcdqScoreMCol: 'M (Moisture Risk)',
      dcdqScoreWCol: 'W (Wait Bonus)',
      dcdqScoreSCol: 'S (Priority)',
      dcdqRankCol: 'Rank',
      dcdqWaitSliderLabel: 'Simulate Wait Time Adjustment (+min)',
      dcdqMoistureSliderLabel: 'Simulate Moisture Adjustment (%)',
      dcdqTriggerReorderBtn: 'Demonstrate Queue Reorder',
      dcdqReordering: 'Re-evaluating DCDQ Scores...',
      dcdqReorderResultNotice: 'Anti-starvation bonus W_i updated. Vehicle rank changed dynamically.',
      dcdqLiveQueueEmpty: 'Live APMC Queue is currently empty. Check in arrivals at Gate Terminal or click \'Create Demo Traffic\' in Demo Tools.',
      dcdqRerankLiveBtn: 'Recompute & Re-rank Live Queue',
      dcdqRerankingLive: 'Executing Canonical DCDQ Re-ranking...',
      dcdqCanonicalFormulaNotice: 'S_i = 1.0 * A_i + 1.0 * D_i + 1.0 * M_i + 1.0 * W_i (Evaluated exclusively by backend canonical DCDQ engine in Redis ZSET)',

      // Module 2: ETA
      etaModuleTitle: '2. M(t)/E_k/c(t) Multi-Server Queue ETA Model',
      etaModuleDesc: 'Estimates vehicle service waiting times based on preceding payload, rolling 15-minute weighbridge throughput, and active scale count.',
      etaQueueAhead: 'Vehicles Ahead',
      etaPayloadAhead: 'Payload Ahead',
      etaServiceRate: '15-Min Service Rate',
      etaActiveScales: 'Active Scales c(t)',
      etaCalculatedEta: 'Estimated Time of Service (ETA)',
      etaScaleCountStepper: 'Configure Active Weighbridge Scales',
      etaRecalculating: 'Recalculating multi-server ETA...',

      // Module 3: TAS BILP
      tasModuleTitle: '3. TAS BILP Truck Congestion Optimizer',
      tasModuleDesc: 'Executes HiGHS Mixed-Integer Linear Program via SciPy to optimally allocate inbound truck arrival slots and eliminate yard congestion.',
      tasInputTrucks: 'Input Trucks',
      tasCandidateSlots: 'Candidate Slots',
      tasSlotCapacity: 'Capacity Limit',
      tasPenalties: 'Penalty Factors',
      tasBeforeCongestion: 'Before Congestion (Baseline)',
      tasOptimizedAssignment: 'Optimized Slot Allocation Matrix',
      tasAfterCongestion: 'After Congestion (Balanced)',
      tasRunSolverBtn: 'Execute HiGHS BILP Solver',
      tasOptimizing: 'Solving Mixed-Integer Linear Program...',

      // Module 4: Redis Lock
      redisModuleTitle: '4. Redis Atomic Reservation Lock (Capacity Preservation)',
      redisModuleDesc: 'Simulates concurrent reservation attempts to enforce zero-capacity-overflow invariant under high-concurrency race conditions.',
      redisDisclaimer: 'Architecture Note: Single-instance Redis SET NX PX distributed lock with atomic Lua release. Not a multi-instance Redlock quorum.',
      redisConcurrentRequests: 'Concurrent Requests',
      redisLockAcquisition: 'Lock Acquisition Timeline',
      redisWinner: 'Winning Worker',
      redisRejections: 'Rejected Requests',
      redisTtl: 'Lock TTL',
      redisAtomicRelease: 'Atomic Release Mechanism',
      redisRunTestBtn: 'Launch 10-Worker Race Test',
      redisTesting: 'Executing concurrent lock requests...',

      // Module 5: LWW
      lwwModuleTitle: '5. Server-Sequence-Authoritative Field-Level Merge',
      lwwModuleDesc: 'Field-level Last-Write-Wins merge using authoritative server receive sequence. Guarantees deterministic convergence across offline nodes.',
      lwwMutationA: 'Mutation A (Offline Terminal 01)',
      lwwMutationB: 'Mutation B (Offline Terminal 02)',
      lwwFieldConflict: 'Field-by-Field Conflict Analysis',
      lwwServerSequence: 'Authoritative Server Sequence',
      lwwClientTimestamp: 'Client Timestamps (Diagnostic Only)',
      lwwWinningValue: 'Authoritative Winner',
      lwwDeduplication: 'WAL Replay Deduplication',
      lwwSyncStatus: 'Convergence Sync Status',
      lwwRunTestBtn: 'Run LWW Conflict Test',
      lwwTesting: 'Resolving mutation conflict...',

      // Module 6: HMAC
      hmacModuleTitle: '6. HMAC-SHA256 Cryptographic Auditing',
      hmacModuleDesc: 'Evaluates tamper-evident cryptographic signatures over canonical booking payloads using constant-time comparison (FIPS 198-1).',
      hmacCanonicalPayload: 'Canonical Payload',
      hmacSignatureLength: 'Signature Length (Hex Chars)',
      hmacVerificationResult: 'Authentic Verification Result',
      hmacTamperedPayload: 'Tampered Payload (1-Byte Altered)',
      hmacRejectionResult: 'Adversarial Rejection Result',
      hmacSecretKeyRedacted: 'Secret Key Status: [REDACTED — 256-Bit Cryptographic Entropy in Server Vault]',
      hmacRunVerifyBtn: 'Verify Cryptographic Integrity',
      hmacVerifying: 'Computing SHA-256 HMAC digest...',
      hmacTestPayload: 'Cryptographic Test Payload',
      hmacTestFixtureNotice: 'Test Fixture Notice: The IDs below are deterministic cryptographic test fixtures, not operational farmer identities.',
      hmacSyntheticFixtureInputs: 'Synthetic Fixture Inputs: Farmer #101, Slot #5',

      // Module 7: Gzip
      gzipModuleTitle: '7. RFC 1952 Gzip Offline WAL Compression',
      gzipModuleDesc: 'Measures genuine byte compression and round-trip server decompression for offline IndexedDB Write-Ahead Log batches.',
      gzipRawSize: 'Raw JSON Payload Size',
      gzipCompressedSize: 'Compressed Gzip Size',
      gzipCompressionRatio: 'Compression Savings Ratio',
      gzipRecordCount: 'WAL Mutation Count',
      gzipSyncResult: 'Server Decompression Status',
      gzipRunCompressBtn: 'Execute Gzip Compression Batch',
      gzipCompressing: 'Compressing WAL batch...',

      // Module 8: Logistic Booking Risk
      riskModuleTitle: '8. Logistic Booking Failure Risk Predictor',
      riskModuleDesc: 'Evaluates empirical appointment no-show and transit failure probability based on arrival time deviation.',
      riskModelledDisclaimer: 'MATHEMATICALLY MODELLED RISK — NOT AN ACTUAL PROCUREMENT FAILURE PREDICTION',
      riskExpectedArrival: 'Expected Arrival Time',
      riskActualArrival: 'Actual Arrival Time',
      riskDeviation: 'Transit Deviation (Delta t)',
      riskParameterK: 'Sensitivity Parameter (k)',
      riskCalculatedRisk: 'Calculated Failure Probability',
      riskDeviationSlider: 'Adjust Arrival Deviation (Minutes)',
    },
    receipt: {
      title: 'Digital J-Form Joint-Sale Certificate',
      govtHeader: 'Agricultural Produce Market Committee (APMC)',
      jformSubheader: 'Authorized e-NAM Electronic Procurement & Direct Benefit Transfer Record',
      qrValid: 'Cryptographically Verified Token',
      printSlip: 'Print J-Form Slip',
      close: 'Close Window',

      cryptoAuditTrail: 'Cryptographic Audit & Payout Trail',
      ledgerHash: 'Ledger Hash',
      hmacToken: 'HMAC Token',
      dbtRef: 'DBT Ref',
    },
    admin: {
      title: 'APMC Administration Hub',
      subtitle: 'State Procurement Authority & Yard Infrastructure Management',
      tabMandis: 'APMC Mandis',
      tabCrops: 'Commodities & MSP',
      tabUsers: 'Station Users',
      tabSlots: 'Procurement Slots',
      totalRegisteredFarmers: 'Registered Farmers',
      activeTransactions: 'Active Yard Transactions',
      queuedVehicles: 'Queued Vehicles',
      volumeProcured: 'Total Volume Procured',
      payoutSettled: 'Total DBT Settled',
      qualityInspected: 'Assayed Lots',
      rejectionRate: 'Rejection Rate',
      activeWeighbridges: 'Active Weighbridges',
      dailyCapacity: 'Daily Capacity',
      operationalStatus: 'Operational Status',
      simulateTraffic: 'Simulate Traffic',
      simulatingTraffic: 'Simulating...',
      resetShowcase: 'Reset Showcase',
      resetting: 'Resetting...',
      resetConfirmPrompt: 'Are you sure you want to reset the showcase database to baseline?',
      addMandi: 'Add Mandi Yard',
      addCrop: 'Add Commodity',
      addUser: 'Add Staff Account',
      generateBatchSlots: 'Generate Daily Slots',
      generatingSlots: 'Generating...',
      refreshData: 'Refresh Metrics',
      toggleOperational: 'Toggle Operational Status',
      toggleActive: 'Toggle Active Status',
      mandiName: 'Mandi Name',
      districtState: 'District & State',
      dailyCapacityQt: 'Daily Capacity (qt)',
      weighbridges: 'Weighbridges',
      status: 'Status',
      actions: 'Actions',
      cropName: 'Commodity Name',
      cropCode: 'Commodity Code',
      category: 'Category',
      mspPrice: 'MSP Price (₹/qt)',
      optimalMoisture: 'Optimal Moisture (%)',
      maxMoisture: 'Max Moisture (%)',
      username: 'Username',
      fullName: 'Full Name',
      role: 'Assigned Role',
      assignedMandi: 'Assigned Mandi',
      slotTime: 'Time Window',
      allocatedCapacity: 'Allocated (qt)',
      bookedCapacity: 'Booked (qt)',
      remainingCapacity: 'Available (qt)',
      scheduledDate: 'Scheduled Date',
      createMandiTitle: 'Register New APMC Mandi',
      createCropTitle: 'Register Procurement Commodity',
      createUserTitle: 'Register Station Operator Account',
      generateSlotsTitle: 'Generate Hourly Procurement Slots',
      mandiNameLabel: 'Mandi Yard Name',
      districtLabel: 'District',
      stateLabel: 'State',
      dailyCapacityLabel: 'Daily Throughput Capacity (qt)',
      weighbridgesLabel: 'Number of Active Weighbridges',
      cropNameLabel: 'Commodity Name',
      cropCodeLabel: 'Commodity Code',
      categoryLabel: 'Crop Category',
      mspLabel: 'Minimum Support Price (₹/qt)',
      optimalMoistureLabel: 'Optimal Moisture Standard (%)',
      maxMoistureLabel: 'Maximum Moisture Limit (%)',
      usernameLabel: 'Login Username',
      fullNameLabel: 'Operator Full Name',
      roleLabel: 'Station Role',
      passwordLabel: 'Access Passcode',
      targetDateLabel: 'Procurement Target Date',
      startHourLabel: 'Start Hour (24h format)',
      endHourLabel: 'End Hour (24h format)',
      capacityPerHourLabel: 'Capacity Per Hourly Slot (qt)',
      saveButton: 'Save Record',
      cancelButton: 'Cancel',
      activeStatus: 'ACTIVE',
      inactiveStatus: 'INACTIVE',
      operationalStatusActive: 'OPERATIONAL',
      operationalStatusInactive: 'CLOSED',
      noMandisFound: 'No registered mandis found.',
      noCropsFound: 'No registered commodities found.',
      noUsersFound: 'No user accounts found.',
      noSlotsFound: 'No procurement slots found for this date.',
      selectMandiToViewSlots: 'Select a mandi yard above to inspect its procurement schedule.',
      offlineNotice: 'Admin configuration updates require active server connectivity.',

      hubSubtitle: 'System Master & Yard Governance Hub',
      hubDesc: 'Configure APMC mandis, update statutory MSP rates, oversee operational staff roles, and allocate hourly gate capacity.',
      apmcBoardAdmin: 'APMC Board Administration',
      eNamCloudAuth: 'e-NAM Cloud Authoritative',
      offlineWalMode: 'Offline WAL Mode',
      backendOffline: 'MandiQ Backend API Is Offline (Port 8000)',
      backendOfflineDesc: 'The Python FastAPI server is currently unreachable. Live yard telemetry, slot reservation, and DCDQ simulation require the backend process to be running.',
      startInTerminal: 'Start in terminal:',
      simulateTooltip: 'Inject realistic vehicles across stages to demonstrate dynamic re-ranking',
      resetTooltip: 'Reset showcase database to clean baseline',
      liveDynamicStream: 'Live Dynamic Stream (5s)',
      dcdqSorted: 'DCDQ Sorted',
      totalPipeline: 'Total pipeline',
      quintalsProcured: 'Quintals procured',
      pfmsSettled: 'PFMS Settled',
      moistureRejection: '> 17% moisture',
      agriStackVerified: 'AgriStack Verified',
      mandisSubtitle: 'Centrally certified procurement yards with defined weighbridges and daily tonnage ceilings.',
      cropsSubtitle: 'Standard procurement rates enforced during automated J-Form billing and moisture rejection ceilings.',
      usersSubtitle: 'Authoritative role mappings derived from signed HMAC cryptographic tokens.',
      slotsSubtitle: 'Monitor real-time slot occupancy and batch-generate booking windows.',
      universalAccess: 'Universal System Access',
      noMandisAvailable: 'No operational mandis available',
      clickGenerateSlots: 'Click \"Generate Slots (Next 7 Days)\" above to initialize hourly windows.',
      slotId: 'Slot ID',
      utilization: 'Utilization',
      editMsp: 'Edit MSP',
      deactivate: 'Deactivate',
      mandiNamePlaceholder: 'e.g. Ujjain APMC Mandi',
      districtPlaceholder: 'Ujjain',
      statePlaceholder: 'Madhya Pradesh',
      cropNamePlaceholder: 'Wheat (Sharbati)',
      mspPriceUnit: 'Statutory MSP Price (₹ / Quintal)',
      optimalMoistureUnit: 'Optimal Moisture %',
      maxMoistureUnit: 'Max Moisture Ceiling %',
      perQuintal: '/ Qt',
      dataUnavailable: 'Admin data unavailable: {errors}',
      showcaseInjected: 'Live showcase traffic successfully injected into database and priority queue!',
      errorSimulating: 'Error simulating showcase traffic',
      showcaseResetClean: 'Showcase database and priority queue cleanly reset!',
      errorResetting: 'Error resetting showcase database',
      failedCreateMandi: 'Failed to create mandi',
      mandiRegisteredSuccess: 'APMC Mandi "{name}" registered successfully!',
      errorCreatingMandi: 'Error creating mandi',
      failedUpdateStatus: 'Failed to update status',
      errorUpdatingMandiStatus: 'Error updating mandi status',
      failedUpdateCommodity: 'Failed to update commodity',
      commodityMspUpdated: 'Commodity "{name}" MSP updated to ₹{msp}/Qt!',
      errorUpdatingCrop: 'Error updating crop',
      confirmDeactivateCommodity: 'Are you sure you want to deactivate commodity "{name}"?',
      failedDeactivateCommodity: 'Failed to deactivate commodity',
      commodityDeactivatedSuccess: 'Commodity "{name}" deactivated successfully.',
      errorDeactivatingCommodity: 'Error deactivating commodity',
      failedGenerateSlots: 'Failed to generate slots',
      errorGeneratingSlots: 'Error generating slots',
      slotsGeneratedSuccess: 'Hourly procurement slots generated successfully for the next 7 days.',
      cropCodePlaceholder: 'e.g., WHEAT_SHARBATI',
      resetFailed: 'Reset failed',
      simulationFailed: 'Simulation failed',
      tasAdminTitle: 'TAS Slot Optimization & Arrival Risk',
      tasAdminSubtitle: 'Run mathematical BILP solver to balance vehicle appointments and audit logistic booking failure risks.',
      tasOptimizeNow: 'Balance Slot Allocations',
    },
    journey: {
      modalTitle: 'Automated End-to-End Procurement Journey',
      modalSubtitle: 'Interactive Architectural Simulation Across All 12 MandiQ Lifecycle Stages',
      runAll: 'Run Complete E2E Journey',
      runningAll: 'Executing Stage Pipeline...',
      resetAll: 'Reset All Stages',
      close: 'Close Journey Modal',
      statusPending: 'PENDING',
      statusRunning: 'IN PROGRESS',
      statusSuccess: 'VERIFIED SUCCESS',
      statusFailed: 'FAILED',
      statusBlocked: 'BLOCKED BY POLICY',
      stageDetails: 'Stage Technical Details',
      duration: 'Execution Duration',
      invariantsChecked: 'Mathematical & Security Invariants',
      payloadResponse: 'Cryptographic Payload & Response',
      stage1Title: 'Farmer e-KYC & Land Record (Simulated)',
      stage1Desc: 'Query simulated UIDAI e-KYC and AgriStack land registry for verified identity and production ceiling.',
      stage2Title: 'Atomic Slot Reservation + HMAC',
      stage2Desc: 'Atomically reserve delivery slot and generate tamper-proof HMAC-SHA256 booking token.',
      stage3Title: 'Gate QR Verification & Entry',
      stage3Desc: 'Gate scanner verifies cryptographic HMAC signature on arrival and admits truck.',
      stage4Title: 'Digital Quality Assaying',
      stage4Desc: 'Digital sensor moisture assaying. Invariant: moisture <= 17.0% for queue admission.',
      stage5Title: 'DCDQ Priority Queue Placement',
      stage5Desc: 'Calculate composite priority score (S_i) and place vehicle in priority queue.',
      stage6Title: 'Weighbridge Gross Weighment',
      stage6Desc: 'Scale load-cell telemetry captures gross weight of loaded truck (100.00 qt).',
      stage7Title: 'Weighbridge Tare & Net Weight',
      stage7Desc: 'Unloaded tare scale capture (37.50 qt). Net weight = 62.50 qt. Yield ceiling checked.',
      stage8Title: 'J-Form Joint-Sale Billing',
      stage8Desc: 'Compute official procurement invoice: 62.50 qt * ₹2,275 MSP = ₹142,187.50.',
      stage9Title: 'Dual-Signature DBT Staging',
      stage9Desc: 'Dual cryptographic HMAC-SHA256 signatures from Inspector and Operator bound to block hash.',
      stage10Title: 'PFMS Aadhaar Payment Rail (Mock)',
      stage10Desc: 'Simulated government PFMS / NPCI Aadhaar Payment Bridge disbursement and settlement.',
      stage11Title: 'Offline WAL Replay & LWW Merge',
      stage11Desc: 'Batch synchronization with monotonic server receive sequence and conflict resolution.',
      stage12Title: 'Live Queue Starvation Prevention',
      stage12Desc: 'Verify anti-starvation lambda bonus promotes low-priority grain before max wait threshold.',
      networkFailure: 'Network failure occurred',
      stageError: 'Unexpected error during stage execution',
      resetFailed: 'Reset failed',
      preflightFailed: 'Pre-flight reset failed',
      stageFailed: 'Stage failed',
    },
    ussd: {
      simulatorTitle: 'Zero-Data Cellular Simulator',
      simulatorSubtitle: 'GSM MAP Layer (*247#)',
      activeCallState: 'MAP ACTIVE',
      standbyState: 'STANDBY',
      dialPrompt: 'MandiQ Feature Phone Simulator\nDial *247# to begin zero-data session.',
      sessionEnded: 'Session ended.\nDial *247# to begin.',
      networkTimeout: 'Network / MAP signaling timeout.\nCheck connectivity.',
      transmittingPacket: 'Transmitting signaling packet...',
      inputLabel: 'Input:',
      sendDial: 'SEND / DIAL',
      endCall: 'END CALL',
      clearInput: 'Clear Input',
      callerLabel: 'Caller Mobile:',
    },
    walMonitor: {
      bannerTag: 'Offline Storage & Sync Status',
      title: 'Client Mutation Ledger & Sync Engine',
      description: 'Local-first IndexedDB ledger preserves ACID mutation safety on edge devices during rural APMC power & network outages. Upon reconnect, mutations are Gzip-compressed, uploaded to /api/v1/sync/wal, and reconciled via authoritative server monotonic sequence.',
      refreshButton: 'Refresh local records',
      syncBatch: 'Sync Batch Now',
      syncingBatch: 'Syncing Batch...',
      tabLedger: 'WAL Mutation Ledger',
      tabMaterialized: 'Materialized Client View',
      filterAll: 'All Mutations',
      filterPending: 'Pending Sync',
      filterSynced: 'Synced',
      filterFailed: 'Failed',
      colMutationId: 'Mutation ID',
      colType: 'Mutation Type',
      colEntityId: 'Entity / Txn ID',
      colStatus: 'Status',
      colTimestamp: 'Recorded Timestamp',
      colActions: 'Action',
      noRecordsFound: 'No write-ahead log mutations found.',
      viewPayload: 'Inspect Payload',
      modalPayloadTitle: 'WAL Mutation Payload Details',
      serverMonotonicSeq: 'Server Monotonic Sequence',
      statusPending: 'PENDING',
      statusSynced: 'SYNCED',
      statusFailed: 'FAILED',
      lastSyncResultTitle: 'Last Server Sync Result',
      mutationsSynced: 'Mutations Reconciled',
      conflictsResolved: 'Conflicts Resolved',
      errorsEncountered: 'Errors Encountered',
      localTransactionsTitle: 'Local Materialized Transactions',
      noLocalTransactions: 'No local transactions recorded in offline store.',
      colTxnId: 'Transaction ID',
      colFarmerId: 'Farmer ID',
      colMandiId: 'Mandi ID',
      colCurrentState: 'Current State',

      totalMutations: 'Total Mutations',
      indexedDbWal: 'IndexedDB transactionsWAL',
      pendingSync: 'Pending Sync',
      queuedReplication: 'Queued for server replication',
      reconciled: 'Reconciled',
      acknowledgedServer: 'Acknowledged by server',
      networkRail: 'Network Rail',
      liveCloudLink: 'LIVE CLOUD LINK',
      offlineAirGap: 'OFFLINE AIR-GAP',
      directRestGzip: 'Direct REST & Gzip WAL',
      indexedDbLocalFallback: 'IndexedDB Local Fallback',
      generateMutations: 'Generate Local Offline WAL Mutations',
      generateMutationsSubtitle: 'Click to inject test entries into IndexedDB without cloud connection',
      transactionId: 'Transaction ID',
      currentState: 'Current State',
      farmer: 'Farmer',
      mandi: 'Mandi',
      syncStatus: 'Sync Status',
      lastUpdated: 'Last Updated',
      details: 'Details',
      payloadInspector: 'WAL Payload Inspector',
      mutationUuid: 'Mutation UUID',
      metadataAttributes: 'Metadata Attributes',
      stateAttributes: 'State Attributes',
      targetState: 'Target State',
      hmacIntegrity: 'HMAC Integrity',
      parsedPayload: 'Parsed Payload JSON',
      materializedTransaction: 'Materialized Transaction',
      aggregatedPayload: 'Aggregated Payload JSON',
      lastMutationId: 'Last Mutation ID',
    },
  },
  hi: {
    common: {
      appName: 'मंडीक्यू',
      appSubtitle: 'स्मार्ट गतिशील कतार एवं लोकल-फर्स्ट डब्ल्यूएएल',
      apmcPwa: 'एपीएमसी पीडब्ल्यूए',
      loading: 'लोड हो रहा है...',
      confirm: 'पुष्टि करें',
      cancel: 'रद्द करें',
      close: 'बंद करें',
      refresh: 'ताज़ा करें',
      status: 'स्थिति',
      action: 'कार्रवाई',
      verified: 'सत्यापित',
      pending: 'लंबित',
      operational: 'सक्रिय मंडी',
      today: 'आज',
      logout: 'लॉग आउट',
      online: 'ऑनलाइन',
      offline: 'ऑफलाइन',
      synced: 'सिंक पूर्ण',
      error: 'त्रुटि',
      success: 'सफल',
      quintals: 'क्विंटल',
      kg: 'किग्रा',
      inr: '₹',
      language: 'भाषा',
      all: 'सभी',
      search: 'खोजें',
      filter: 'फ़िल्टर',
      details: 'विवरण',
      noData: 'कोई डेटा उपलब्ध नहीं',

      activeTransaction: 'सक्रिय लेनदेन',
      apmcProcurementSystem: 'कृषि उपज मंडी समिति खरीद प्रणाली',

      backendOffline: 'बैकएंड ऑफ़लाइन',
      inMemoryQueue: 'इन-मेमोरी कतार (रेडिस फॉलबैक)',
      noActiveTransaction: 'कोई अधिकृत लेनदेन चयनित नहीं है।',
      tareWeightError: 'भौतिक सीमा उल्लंघन: खाली वजन सकल वजन से अधिक या बराबर नहीं हो सकता।',
      noMandiSelected: 'कोई कार्यशील मंडी चयनित नहीं है।',
      reservationFailed: 'आरक्षण विफल रहा',
      cancellationFailed: 'अपॉइंटमेंट रद्द करने में विफल',
      networkErrorCancel: 'अपॉइंटमेंट रद्द करने में नेटवर्क त्रुटि।',
      selectOperationalMandi: 'कृपया एक कार्यशील मंडी चुनें।',
      unlinkedFarmerReservation: 'प्रमाणित किसान प्रोफ़ाइल लिंक नहीं है। स्लॉट आरक्षण आगे नहीं बढ़ सकता।',
      noVehiclesInQueue: 'कतार में प्रेषण के लिए वर्तमान में कोई वाहन उपलब्ध नहीं है।',
      jformMissingNetWeight: 'बिल जनरेट नहीं किया जा सकता: लेनदेन में सत्यापित शुद्ध वजन नहीं है। वाहन को पहले तौलकांटा वजन पूरा करना होगा।',
      savedLocallyWal: 'IndexedDB transactionsWAL में स्थानीय रूप से सहेजा गया।',
      generateJformFirst: 'कृपया पहले एक वैध जे-फॉर्म चालान जनरेट या प्राप्त करें।',
      dualSigAdminNotice: 'दोहरे हस्ताक्षर सत्यापन के लिए निरीक्षक और ऑपरेटर दोनों के हस्ताक्षर आवश्यक हैं। प्रोटोटाइप ऑटो-स्वीकृति के लिए व्यवस्थापक प्राधिकरण की आवश्यकता है।',
      dbtOfflineWal: '[ऑफ़लाइन वाल] दोहरे हस्ताक्षर डीबीटी प्राधिकरण स्थानीय रूप से सहेजा गया। ऑनलाइन होने पर निपटान के लिए तैयार।',
      dbtPfmsConfirmed: 'पीएफएमएस निपटान रेल द्वारा प्रत्यक्ष लाभ अंतरण (डीबीटी) की पुष्टि की गई!',
      dbtOfflineRecorded: 'ऑफ़लाइन ब्लैकआउट: डीबीटी स्थानीय रूप से दर्ज किया गया। ऑनलाइन होने पर मिलान किया जाएगा।',
      supervisorOverrideRecorded: '[ऑफ़लाइन वाल] पर्यवेक्षक ओवरराइड स्थानीय रूप से दर्ज किया गया। ट्रक को फिर से प्रेषण कतार में शामिल किया गया।',
      adminBackendUnavailable: 'बैकएंड अनुपलब्ध है। सर्वर-साइड प्रशासन प्रबंधित करने के लिए पुनः कनेक्ट करें।',
      noMandiSimulation: 'सिमुलेशन के लिए कोई कार्यशील मंडी चयनित नहीं है।',
      noMandiReset: 'रीसेट के लिए कोई कार्यशील मंडी चयनित नहीं है।',
      initializing: 'मंडी-क्यू प्रणाली प्रारंभ हो रही है...',
      txnPlaceholder: 'उदा. TXN-...',
      load: 'लोड करें',
      txnNotFound: 'प्राधिकृत लेनदेन "{txnId}" नहीं मिला।',
      txnNotFoundServer: 'सर्वर पर प्राधिकृत लेनदेन "{txnId}" नहीं मिला।',
      txnNotFoundLocally: 'लेनदेन "{txnId}" स्थानीय या रिमोट में नहीं मिला।',
      txnFarmerMismatch: 'लेनदेन किसान #{txnFarmerId} का है, लेकिन सक्रिय सत्र किसान #{sessionFarmerId} का है',
      txnMandiMismatch: 'लेनदेन मंडी #{txnMandiId} का है, लेकिन चयनित मंडी #{selectedMandiId} है',
      txnInvalidState: 'लेनदेन \'{currentState}\' स्थिति में है, लेकिन आवश्यक स्थिति इनमें से एक होनी चाहिए: [{allowedStates}]',
      networkError: 'नेटवर्क कनेक्शन त्रुटि। कृपया अपने कनेक्शन की पुष्टि करें।',
      adminDataUnavailable: 'प्रशासन डेटा अनुपलब्ध: {errors}',
      demoFarmersError: 'डेमो किसानों को प्राप्त करने में नेटवर्क त्रुटि',
      crop: 'फसल',
    },
    nav: {
      admin: 'प्रशासन केंद्र',
      farmer: 'किसान पोर्टल',
      gate: 'प्रवेश द्वार',
      quality: 'गुणवत्ता जांच',
      queue: 'सक्रिय कतार',
      weighbridge: 'धर्मकांटा तौल',
      billing: 'बिलिंग एवं भुगतान',
      sync: 'ऑफलाइन डब्ल्यूएएल',
      advanceStation: 'अगला स्टेशन',
      nextStation: 'अगला चरण',
      demoTools: 'डेमो टूल्स',
    },
    roles: {
      admin: 'प्रशासक',
      supervisor: 'यार्ड सुपरवाइजर',
      inspector: 'गुणवत्ता निरीक्षक',
      operator: 'गेट एवं तौल ऑपरेटर',
      farmer: 'पंजीकृत किसान',
    },
    login: {
      title: 'एपीएमसी प्रवेश द्वार एवं खरीद गेटवे',
      subtitle: 'विकेंद्रीकृत कतार प्रबंधन एवं लोकल-फर्स्ट गुणवत्ता Assaying टर्मिनल',
      selectRole: 'स्टेशन पद चुनें',
      username: 'ऑपरेटर / आधार पहचान संख्या',
      usernamePlaceholder: 'अपनी पंजीकृत पहचान संख्या दर्ज करें',
      password: 'सुरक्षा पासकोड',
      passwordPlaceholder: 'सुरक्षा पासकोड दर्ज करें',
      signIn: 'प्रमाणित करें एवं टर्मिनल खोलें',
      signingIn: 'प्रमाणपत्र सत्यापित हो रहे हैं...',
      quickDemoUsers: 'त्वरित डेमो पहुंच खाते',
      credentialsError: 'अमान्य पहचान या पासकोड। कृपया पुनः जांचें।',
      offlineFallbackNotice: 'ऑफलाइन मोड: स्थानीय संग्रहीत प्रमाणपत्रों द्वारा संचालित।',

      hmacSession: 'क्रिप्टोग्राफिक रूप से हस्ताक्षरित HMAC-SHA256 सत्र',
      footerStandards: 'मंडीक्यू एपीएमसी खरीद प्रणाली • राष्ट्रीय मानक',
    },
    farmer: {
      greeting: 'नमस्ते, {name}',
      profileTitle: 'सत्यापित किसान प्रोफ़ाइल',
      kisanId: 'किसान आईडी',
      mobile: 'पंजीकृत मोबाइल',
      remainingCeiling: 'शेष फसल उपज सीमा',
      availableCapacity: 'उपलब्ध बुकिंग क्षमता',
      remainingAfterBooking: 'बुकिंग उपरांत शेष क्षमता',
      targetMandi: 'खरीद मंडी यार्ड',
      yardOperational: 'मंडी परिचालन सक्रिय',
      processFlow: 'खरीद प्रक्रिया कार्यप्रवाह',
      stepOf: 'चरण {current} / {total}',
      step1Crop: 'पंजीकृत फसल',
      step2Token: 'टोकन जारी',
      step3Gate: 'गेट प्रवेश',
      step4Quality: 'गुणवत्ता परीक्षण',
      step5Weight: 'तौल धर्मकांटा',
      step6Payment: 'डीबीटी भुगतान',
      activeToken: 'सक्रिय फसल वितरण टोकन',
      tokenNo: 'टोकन संख्या',
      scanAtGate: 'एपीएमसी प्रवेश द्वार पर आगमन पर यह क्यूआर बारकोड प्रस्तुत करें।',
      cancelSlot: 'बुकिंग रद्द करें',
      cancelSlotPrompt: 'क्या आप वाकई इस निर्धारित स्लॉट को रद्द करना चाहते हैं?',
      viewReceipt: 'डिजिटल जे-फॉर्म रसीद देखें',
      bookDeliveryTitle: 'फसल वितरण स्लॉट बुक करें',
      bookDeliverySubtitle: 'सड़क जाम और अनावश्यक प्रतीक्षा से बचने हेतु प्रति घंटा स्लॉट आरक्षित करें।',
      step1Title: 'पंजीकृत फसल का चयन करें',
      govtMsp: 'सरकारी एमएसपी',
      loadingCrops: 'पंजीकृत फसलें लोड हो रही हैं...',
      noCrops: 'इस मंडी हेतु कोई फसल उपलब्ध नहीं है।',
      step2Title: 'विक्रय मात्रा (क्विंटल में)',
      quantityHint: 'मात्रा क्विंटल में दर्ज करें (1 क्विंटल = 100 किग्रा = 0.1 टन)',
      quickPills: 'त्वरित चयन',
      step3Title: 'कृषक एवं भूमि स्वामित्व सत्यापन',
      landTenure: 'कृषक का प्रकार',
      ownerCultivator: 'स्वयं-भूस्वामी कृषक',
      ownerDesc: 'सत्यापित एग्रीस्टैक राजस्व रिकॉर्ड युक्त निजी भूमि।',
      tenantCultivator: 'बटाईदार / पट्टाधारक कृषक',
      tenantDesc: 'पट्टा या मौखिक समझौते के तहत खेती।',
      landownerName: 'मूल भूस्वामी का पूरा नाम',
      landownerNamePlaceholder: 'राजस्व रिकॉर्ड अनुसार नाम दर्ज करें',
      panchayatCert: 'पंचायत सत्यापन प्रमाण पत्र संख्या',
      panchayatCertHint: 'ग्राम पंचायत अथवा तहसीलदार से जारी प्रमाण पत्र संख्या',
      bonaFideDeclaration: 'मैं विधिपूर्वक घोषणा करता हूँ कि यह उपज मेरे द्वारा स्वयं उपजाई गई है।',
      step4Title: 'फसल लाने की तिथि',
      scheduledDate: 'मंडी आगमन तिथि चुनें',
      step5Title: 'उपलब्ध प्रति घंटा स्लॉट',
      slotsHint: 'प्रति घंटा स्लॉट मंडी प्रांगण में अनावश्यक भीड़ को रोकता है।',
      loadingSlots: 'उपलब्ध स्लॉट लोड हो रहे हैं...',
      noSlots: 'इस तिथि हेतु कोई स्लॉट उपलब्ध नहीं है।',
      capacityRemaining: 'उपलब्ध',
      confirming: 'स्लॉट आरक्षित हो रहा है...',
      reserveButton: 'फसल वितरण स्लॉट सुरक्षित करें',
      slotUnavailable: 'चयनित स्लॉट भर चुका है। कृपया दूसरा समय चुनें।',
      valQtyPositive: 'मात्रा शून्य से अधिक होनी अनिवार्य है।',
      valQtyExceedsCeiling: 'अनुरोधित मात्रा आपकी शेष उत्पादन सीमा से अधिक है।',
      valLandownerRequired: 'बटाईदार कृषकों हेतु भूस्वामी का नाम अनिवार्य है।',
      valBonaFideRequired: 'स्वप्रमाणित कृषक घोषणा पत्र पर टिक करना अनिवार्य है।',
      valSlotRequired: 'कृपया आगे बढ़ने हेतु एक आगमन स्लॉट चुनें।',
      valOfflineBooking: 'ऑफलाइन स्थानीय रिकॉर्ड में सहेजा गया। नेटवर्क मिलने पर सिंक होगा।',
      appointmentSuccess: 'स्लॉट सफलतापूर्वक आरक्षित! आपका डिजिटल क्यूआर पास तैयार है।',

      targetMandiAndDate: 'लक्षित एपीएमसी मंडी एवं दिनांक',
      sourceOfTruthSlots: 'प्रति घंटा स्लॉट के लिए प्रामाणिक स्रोत',
      destinationMandi: 'गंतव्य मंडी',
      noMandisAvailable: 'कोई क्रियाशील मंडी उपलब्ध नहीं है',
      scheduledDeliveryDate: 'निर्धारित डिलीवरी दिनांक',
      minus: 'घटाएं',
      plus: 'जोड़ें',
      unlinkedProfileTitle: 'प्रमाणित किसान प्रोफ़ाइल लिंक नहीं है',
      unlinkedProfileDesc: 'आपका लॉगिन खाता वर्तमान में एपीएमसी डेटाबेस में किसी क्रियाशील किसान प्रोफ़ाइल से लिंक नहीं है। सत्यापित किसान प्रोफ़ाइल लिंक होने तक स्लॉट बुकिंग अक्षम है।',
      appointmentCancelledSuccess: 'निर्धारित डिलीवरी स्लॉट आरक्षण सफलतापूर्वक रद्द कर दिया गया।',
      invalidQuantityError: 'कृपया शून्य से अधिक क्विंटल में एक मान्य खरीद मात्रा दर्ज करें।',
      ceilingExceededError: 'निर्दिष्ट मात्रा आपकी शेष सत्यापित भूमि सीमा ({remaining} क्विंटल) से अधिक है।',
      slotCapacityExhaustedError: 'चयनित आगमन स्लॉट की क्षमता समाप्त हो गई है। कृपया दूसरा स्लॉट चुनें।',
      arrivalRiskTitle: 'निर्धारित आगमन विंडो जोखिम',
      modelledRiskBadge: 'MODELLED RISK — NOT AN ACTUAL FAILURE PREDICTION',
      expectedTime: 'अपेक्षित आगमन',
      actualTime: 'वास्तविक / अनुमानित आगमन',
      deviationMinutes: 'आगमन विचलन',
      riskProbability: 'मॉडल विफलता संभावना',
    },
    gate: {
      title: 'एपीएमसी आवक गेट टर्मिनल',
      subtitle: 'क्यूआर टोकन डिजिटल सत्यापन एवं त्वरित वाहन प्रवेश',
      scanQrTitle: 'किसान डिलीवरी पास स्कैन करें',
      scanQrSubtitle: 'डिजिटल हस्ताक्षर एवं एचएमएसी वैधता की तुरंत जांच करें।',
      tokenPlaceholder: 'टोकन संख्या दर्ज करें या बारकोड स्कैन करें',
      verifyButton: 'क्रिप्टोग्राफिक टोकन सत्यापित करें',
      verifying: 'हस्ताक्षर सत्यापित हो रहे हैं...',
      driverMobile: 'चालक का मोबाइल नंबर',
      vehicleNo: 'वाहन पंजीयन संख्या',
      vehicleNoPlaceholder: 'उदा. MP-04-AB-1234',
      checkInButton: 'वाहन को मंडी प्रांगण में प्रवेश दें',
      checkingIn: 'गेट प्रवेश दर्ज हो रहा है...',
      checkInSuccess: 'वाहन प्रवेश सफल। गुणवत्ता परीक्षण स्टेशन हेतु निर्देशित।',
      waitingVehicle: 'आवक बैरियर पर प्रतीक्षारत वाहन',
      entryVerified: 'गेट प्रवेश सफलतापूर्वक सत्यापित',
      inspectionReady: 'गुणवत्ता परीक्षण केंद्र पर आगे बढ़ें',

      cryptoRules: 'क्रिप्टोग्राफिक प्रोटोकॉल नियम',
      tamperProtection: 'छेड़छाड़ सुरक्षा',
      tamperDesc: 'मात्रा, किसान आईडी या स्लॉट में कोई भी परिवर्तन 64-वर्ण वाले एचएमएसी टोकन हस्ताक्षर को अमान्य कर देता है।',
      offlineResilience: 'ऑफलाइन लचीलापन',
      offlineDesc: 'सेलुलर ब्लैकआउट के दौरान, गेट सत्यापन स्थानीय रूप से IndexedDB में बिना किसी रुकावट के निष्पादित होता है।',
      stateProgression: 'स्थिति प्रगति',
      stateProgressionDesc: 'सफल चेक-इन लेनदेन की स्थिति को इसमें बदल देता है:',
      stateProgressionSuffix: 'और ट्रक को गुणवत्ता परख के लिए अग्रेषित करता है।',
      farmerIdPlaceholder: 'किसान आईडी',
      slotIdPlaceholder: 'स्लॉट आईडी',
      signaturePlaceholder: '64-वर्ण हेक्स हस्ताक्षर...',
      entryVerifiedDetails: '{farmerName} ({crop}) के लिए गेट प्रवेश सत्यापित। स्थिति: {state}। मंडी यार्ड स्टेजिंग प्रवेश के लिए अधिकृत।',
      passValidationFailed: 'गेट पास क्रिप्टोग्राफिक हस्ताक्षर या संरचनात्मक सत्यापन में विफल रहा।',
      checkinRejected: 'गेट चेक-इन अस्वीकृत।',
      passVerifiedOnline: 'गेट पास सत्यापित! प्राधिकृत क्लाउड चेक-इन सिंक हुआ और वाहन को प्रवेश दिया गया।',
      passVerifiedOffline: '[ऑफलाइन अनंतिम] गेट प्रवेश संरचनात्मक रूप से सत्यापित और IndexedDB WAL में सहेजा गया। वाहन को ऑफलाइन प्रोटोकॉल के तहत प्रवेश दिया गया।',
      verificationFailed: 'गेट सत्यापन विफल',
      noTxnPrompt: 'कोई सक्रिय लेनदेन चयनित नहीं है। कृपया कतार या हालिया कार्यप्रवाह से एक सक्रिय लेनदेन चुनें, या नीचे लेनदेन आईडी दर्ज करें:',
      hmacFormatInvalid: 'अमान्य HMAC हस्ताक्षर प्रारूप: 64-वर्ण हेक्साडेसिमल डाइजेस्ट अपेक्षित, {length} वर्ण प्राप्त हुए',
      hmacMissing: 'क्रिप्टोग्राफिक टोकन हस्ताक्षर गायब है',
      mandiMismatchError: 'मंडी बेमेल: गेट पास मंडी आईडी {passMandi} के लिए पंजीकृत है, लेकिन यह टर्मिनल मंडी आईडी {terminalMandi} है',
      yieldCeilingExceeded: 'उत्पादन सीमा पार: {projected} क्विंटल किसान सीमा {ceiling} क्विंटल से अधिक होगा',
    },
    quality: {
      title: 'डिजिटल गुणवत्ता परीक्षण केंद्र',
      subtitle: 'सेंसर टेलीमेट्री एवं स्वचालित एपीएमसी ग्रेड मूल्यांकन',
      sensorReading: 'सेंसर रीडिंग',
      cropMoisture: 'अनाज नमी प्रतिशत',
      optimalRange: 'आदर्श नमी: <= 12.0%',
      maxLimit: 'अधिकतम स्वीकार्य सीमा: 17.0%',
      assessing: 'गुणवत्ता जांच की जा रही है...',
      assessButton: 'गुणवत्ता परिणाम दर्ज करें',
      resultApproved: 'गुणवत्ता स्वीकृत: ग्रेड-ए सरकारी मानक अनुरूप',
      resultRejected: 'अस्वीकृत: नमी 17.0% की अधिकतम सीमा से अधिक है',
      eligibleForQueue: 'गतिशील प्राथमिकता कतार हेतु स्वीकृत',
      routedToDrying: 'प्रांगण में धूप में सुखाने हेतु भेजा गया',
      routeToDrying: 'सुखाने हेतु यार्ड में भेजें',
      priorityScore: 'परिकलित DCDQ प्राथमिकता स्कोर',
      supervisorOverrideTitle: 'सुपरवाइजर विशेष गुणवत्ता ओवरराइड',
      overrideReason: 'स्वीकृति का आधिकारिक कारण व औचित्य',
      overrideButton: 'सुपरवाइजर स्वीकृति जारी करें',
      overriding: 'स्वीकृति जारी हो रही है...',

      supervisorAuthToken: 'पर्यवेक्षक प्राधिकरण टोकन',
      supervisorAuthTokenPlaceholder: '•••••••• (पर्यवेक्षक सुरक्षा पिन)',
      technicalFormulasInDemoTools: 'तकनीकी प्राथमिकता सूत्र और गतिशील कतार गणना डेमो टूल्स → एल्गोरिथम केंद्र में स्थित हैं।',
      standardsTitle: 'एपीएमसी लॉट परख मानक',
      gradeATitle: 'ग्रेड ए (एफएक्यू मानक)',
      gradeADesc: 'लॉट को सीधे तत्काल तौल एवं इलेक्ट्रॉनिक एमएसपी निपटान के लिए स्वीकार किया जाता है।',
      gradeBTitle: 'ग्रेड बी (प्राथमिकता लॉट)',
      gradeBDesc: 'यार्ड में सड़न से बचने और समय पर प्रसंस्करण सुनिश्चित करने के लिए प्राथमिकता कतार में भर्ती।',
      rejectionTitle: 'गुणवत्ता अस्वीकृति',
      rejectionDesc: 'अत्यधिक नमी पाई गई। सौर सुखाने वाले एप्रन पर भेजा गया, जब तक कि पर्यवेक्षक द्वारा अधिकृत न हो।',
      calibratedMoisture: 'कैलिब्रेटेड नमी विश्लेषक रीडिंग',
      confirmOverride: 'पर्यवेक्षक गुणवत्ता ओवरराइड की पुष्टि करें',
      dcdqFormula: 'P(लॉट) = 0.35 * P_आगमन + 0.30 * P_नमी + 0.20 * P_प्रतीक्षा + 0.15 * P_विलंब',
      elapsedWaitMinutes: 'मंडी प्रांगण प्रतीक्षा समय',
      cannotAssessState: 'गुणवत्ता का आकलन नहीं किया जा सकता: लेनदेन \'{state}\' स्थिति में है। \'GATE_ENTRY_VERIFIED\' अपेक्षित है।',
      assessmentRejected: 'सर्वर द्वारा गुणवत्ता मूल्यांकन अस्वीकृत',
      assessmentFailed: 'गुणवत्ता मूल्यांकन विफल',
      offlineRejected: '[ऑफलाइन WAL] लॉट अस्वीकृत: नमी 17.0% सीमा से अधिक है। स्थानीय रूप से सहेजा गया।',
      offlineApproved: '[ऑफलाइन WAL] गुणवत्ता स्वीकृत और IndexedDB transactionsWAL में संग्रहीत। ऑनलाइन होने पर Redis कतार में सिंक होगी।',
      overrideFailed: 'पर्यवेक्षक अधिरोहण विफल',
      supervisorOverrideAuthorized: 'पर्यवेक्षक अधिरोहण अधिकृत: {message}',
      preflightNotice: 'कृपया गुणवत्ता परीक्षण से पहले स्लॉट बुक करें और गेट प्रवेश सत्यापन पूर्ण करें।',
      unauthorizedRole: 'पहुंच प्रतिबंधित: इस स्टेशन हेतु निरीक्षक, पर्यवेक्षक या व्यवस्थापक की भूमिका आवश्यक है।',
      autoResolvedGate: 'गेट पर सत्यापित आने वाले वाहन का स्वतः समाधान हुआ',
      awaitingGateLots: 'गेट पर सत्यापित आने वाले लॉट की प्रतीक्षा है...',
    },
    queue: {
      title: 'वास्तविक समय मंडी कतार प्रेषण केंद्र',
      subtitle: 'वास्तविक समय DCDQ प्राथमिकता एवं एंटी-स्टारवेशन यातायात नियंत्रक',
      liveQueueStatus: 'सक्रिय मंडी कतार रजिस्टर',
      vehiclesWaiting: 'तौल हेतु प्रतीक्षारत कुल वाहन',
      rank: 'वरीयता',
      tokenNo: 'टोकन नं.',
      farmer: 'किसान',
      quantity: 'मात्रा',
      dcdqScore: 'DCDQ स्कोर',
      status: 'स्थिति',
      dispatchButton: 'धर्मकांटा तौल हेतु भेजें',
      dispatching: 'वाहन भेजा जा रहा है...',
      emptyQueue: 'कतार खाली है। कोई वाहन प्रतीक्षारत नहीं है।',
      emptyQueueHint: 'गुणवत्ता परीक्षण से पास होने वाले वाहन स्वतः यहाँ प्रदर्शित होंगे।',
      dispatchedToWeighbridge: 'वाहन को धर्मकांटा तौल हेतु प्रेषित किया गया।',
      offlineNotice: 'कतार ऑफलाइन है: यदि उपलब्ध हो तो स्थानीय रूप से कैश्ड कतार प्रदर्शित हो रही है।',
      fetchError: 'कतार प्राप्त करने में नेटवर्क त्रुटि',
      simulationInjected: 'शोकेस ट्रैफ़िक प्रविष्ट किया गया। लाइव DCDQ ने कतार को पुन: व्यवस्थित किया।',
      simulationError: 'सिमुलेशन त्रुटि',
      resetSuccess: 'शोकेस कतार स्वच्छ बेसलाइन पर रीसेट की गई।',
      resetError: 'रीसेट त्रुटि',
      dispatchFailed: 'प्रेषण विफल',
      offlineDispatched: '[ऑफलाइन स्थानीय] वाहन {txnId} स्थानीय कतार से निकाला गया और धर्मकांटे पर भेजा गया।',
      dispatchError: 'प्रेषण त्रुटि',
      scoreA: 'A (समय पालन)',
      scoreD: 'D (विलंब शुल्क एवं भार)',
      scoreM: 'M (नमी जोखिम)',
      scoreW: 'W (प्रतीक्षा बोनस)',
      scoreS: 'S (कुल स्कोर)',
      scoreBreakdown: 'DCDQ घटक विश्लेषण',
      adherence: 'स्लॉट समय पालन',
      demurrage: 'भार एवं विलंब घटक',
      moistureRisk: 'अनाज नमी जोखिम',
      waitBonus: 'एंटी-स्टारवेशन प्रतीक्षा बोनस',
      advanceQueueTime: 'कतार समय आगे बढ़ाएं (+60 मिनट)',
      advancingQueueTime: 'समय आगे बढ़ रहा है...',
      rerankQueue: 'पुनः गणना एवं क्रम निर्धारण',
      rerankingQueue: 'क्रम पुनः निर्धारित हो रहा है...',
      offlineProvisional: 'ऑफलाइन — अनंतिम',
      authoritativeRouted: 'प्राधिकृत — धर्मकांटे पर प्रेषित',
      conflictRejected: 'संघर्ष — अस्वीकृत',
      dispatchedVehiclesTitle: 'धर्मकांटे पर प्रेषित वाहन',
      dispatchedVehiclesDesc: 'सक्रिय कतार से धर्मकांटा तौल हेतु भेजे गए वाहन',
      noDispatchedVehicles: 'अभी तक कोई वाहन प्रेषित नहीं किया गया।',
      offlineDispatchedProvisional: '[ऑफलाइन WAL] वाहन {txnId} ऑफलाइन प्रेषित (अनंतिम)। IndexedDB WAL में दर्ज।',
      dispatchedAuthoritative: '[प्राधिकृत] वाहन {txnId} धर्मकांटा तौल हेतु प्रेषित।',
      estimatedWait: 'अनुमानित प्रतीक्षा',
      estimatedWaitNext: 'अनुमानित प्रतीक्षा: कतार में अगला (0 मिनट)',
      calculatingTelemetry: 'अनुमानित प्रतीक्षा: गणना जारी... (अपर्याप्त टेलीमेट्री)',
      vehiclesAhead: 'आगे वाहन',
      payloadAhead: 'आगे कुल वजन',
      serviceRate: 'सेवा दर',
      activeScales: 'सक्रिय कांटे',
      scaleOffline: 'कांटा ऑफलाइन',
      scaleOnline: 'कांटा ऑनलाइन',
      toggleScale: 'कांटा बदलें',
      technicalBreakdown: 'तकनीकी विश्लेषण (M(t)/E_k/c(t) मॉडल)',
      crop: 'फसल',
      moisture: 'नमी',
      appointmentAdherence: 'स्लॉट समय पालन',
      demurrageScore: 'विलंब एवं भार',
      moistureRiskScore: 'नमी जोखिम',
      antiStarvationWait: 'एंटी-स्टारवेशन प्रतीक्षा',
      finalDcdqScore: 'अंतिम DCDQ स्कोर',
      liveQueueHeader: 'सक्रिय मंडी कतार',
      operationalTelemetry: 'परिचालन टेलीमेट्री',
      algorithmSimulationHeader: 'एल्गोरिदम सिमुलेशन',
      algorithmSimulationDesc: 'सिमुलेटेड यातायात एवं परिदृश्य नियंत्रण। वास्तविक परिचालनों से पूर्णतः पृथक।',
      simulatedLot: 'सिमुलेटेड',
      scaleCount1: '1 कांटा',
      scaleCount2: '2 कांटे',
      scaleCount3: '3 कांटे',
      scales: 'कांटे',
      dcdqFormulationSubtitle: 'DCDQ बहु-कारक प्राथमिकता सूत्रीकरण',
      serviceRateTelemetry: 'सेवा दर टेलीमेट्री',
    },
    weighbridge: {
      title: 'इलेक्ट्रॉनिक धर्मकांटा तौल स्टेशन',
      subtitle: 'लोड-सेल टेलीमेट्री एवं कुल/खाली वजन परिकलन',
      grossWeight: 'सकल वजन (भरे वाहन का कुल वजन)',
      tareWeight: 'खाली वजन (खाली वाहन का वजन)',
      netWeight: 'शुद्ध फसल वजन',
      scaleReading: 'सक्रिय डिजिटल धर्मकांटा वजन',
      captureGross: 'सकल वजन (Gross) दर्ज करें',
      capturingGross: 'धर्मकांटा वजन दर्ज हो रहा है...',
      captureTare: 'खाली वजन (Tare) दर्ज करें',
      capturingTare: 'खाली वाहन वजन दर्ज हो रहा है...',
      weightSummary: 'प्रमाणित तौल सारांश',
      proceedToBilling: 'जे-फॉर्म बिलिंग एवं भुगतान हेतु आगे बढ़ें',
      tareInstruction: 'अनाज खाली करने के उपरांत खाली वाहन को धर्मकांटे पर लाएं।',

      rulesTitle: 'वे-ब्रिज परिचालन नियम',
      physicalInvariant: 'भौतिक अपरिवर्तनीय',
      physicalDesc: 'खाली वजन (टेयर) स्पष्ट रूप से कुल वजन (ग्रॉस) से कम होना चाहिए (टेयर >= ग्रॉस अस्वीकार कर दिया जाता है)।',
      yieldCeiling: 'उपज सीमा प्रवर्तन',
      yieldDesc: 'शुद्ध वितरित वजन और पहले वितरित बैच किसान की पंजीकृत उत्पादन सीमा से अधिक नहीं हो सकते।',
      distributedLock: 'रेडिस एटॉमिक आरक्षण लॉक',
      lockDesc: 'एक ही किसान के लिए समानांतर तौल इस लॉक के तहत क्रमबद्ध होती है:',
      lockSuffix: 'ताकि रेस कंडीशंस समाप्त हो सकें।',
      captureUnified: 'प्रमाणित शुद्ध वजन दर्ज करें',
      scaleInvariance: 'कांटा रीडिंग स्थिरता एवं अंशांकन सत्यापित',
      twoStepWeighment: 'दो-चरणीय तौल (सकल एवं खाली)',
      unifiedWeighment: 'एकीकृत तौल टेलीमेट्री',
      vehicleMustBeRouted: 'लेनदेन \'{state}\' स्थिति में है। सकल वजन दर्ज करने से पहले वाहन को धर्मकांटे पर भेजा जाना चाहिए।',
      grossRejected: 'सर्वर द्वारा सकल वजन अस्वीकृत',
      grossRecordedProceedTare: 'सकल वजन दर्ज: {gross} क्विंटल। स्थिति: {state}। अब अनाज खाली करने और खाली वजन लेने के लिए आगे बढ़ें।',
      offlineGrossSaved: '[ऑफलाइन WAL] सकल वजन ({gross} क्विंटल) IndexedDB transactionsWAL में सहेजा गया।',
      errorGross: 'सकल वजन दर्ज करने में त्रुटि',
      grossMustBeCapturedBeforeTare: 'लेनदेन \'{state}\' स्थिति में है। खाली वजन से पहले सकल वजन दर्ज किया जाना चाहिए।',
      tareRejected: 'सर्वर द्वारा खाली वजन अस्वीकृत',
      tareRecordedNetSettlement: 'खाली वजन दर्ज: {tare} क्विंटल। शुद्ध निपटान: {net} क्विंटल। स्थिति: {state}। जे-फॉर्म बिलिंग के लिए तैयार।',
      offlineTareSaved: '[ऑफलाइन WAL] खाली वजन ({tare} क्विंटल) IndexedDB transactionsWAL में सहेजा गया। शुद्ध वजन: {net} क्विंटल।',
      errorTare: 'खाली वजन दर्ज करने में त्रुटि',
      unifiedRejected: 'सर्वर द्वारा एकीकृत वजन अस्वीकृत',
      unifiedCaptured: 'एकीकृत वजन दर्ज: सकल={gross} क्विंटल, खाली={tare} क्विंटल, शुद्ध={net} क्विंटल। स्थिति: {state}।',
      offlineUnifiedSaved: '[ऑफलाइन WAL] एकीकृत वजन IndexedDB transactionsWAL में सहेजा गया। शुद्ध वजन: {net} क्विंटल।',
      errorWeighment: 'वजन दर्ज करने में त्रुटि',
      preflightNotice: 'धर्मकांटा माप दर्ज करने के लिए कृपया लाइव प्राथमिकता कतार से एक वाहन प्रेषित करें।',
      activeLaneVehicles: 'लेन में सक्रिय वाहन',
      selectVehiclePrompt: 'तौल प्रारंभ करने हेतु कतार से वाहन चुनें',
      invalidTareRange: 'तौल मान अमान्य: खाली वजन धनात्मक और भरे वजन से कम होना अनिवार्य है (0 < tare < gross)',
      autoResolvedQueue: 'सक्रिय कतार से वाहन स्वतः चयनित',
      noVehiclesInLane: 'वर्तमान में कोई वाहन कतार में या तौल हेतु प्रतीक्षारत नहीं है।',
    },
    billing: {
      title: 'खरीद बिलिंग एवं प्रत्यक्ष लाभ अंतरण (DBT)',
      subtitle: 'आधिकारिक जे-फॉर्म विक्रय एवं दोहरे क्रिप्टोग्राफिक डिजिटल हस्ताक्षर',
      jformTitle: 'आधिकारिक जे-फॉर्म संयुक्त विक्रय प्रमाण पत्र',
      invoiceNo: 'जे-फॉर्म चालान संख्या',
      mandiName: 'खरीद एपीएमसी मंडी',
      cropName: 'खरीदी गई फसल',
      netWeight: 'सत्यापित शुद्ध वजन',
      mspPrice: 'लागू सरकारी एमएसपी',
      grossPayable: 'कुल देय फसल मूल्य',
      mandiDeductions: 'वैधानिक मंडी कटौती',
      netPayable: 'किसान को देय शुद्ध डीबीटी भुगतान',
      generateInvoice: 'डिजिटल जे-फॉर्म चालान तैयार करें',
      generateButton: 'डिजिटल जे-फॉर्म चालान तैयार करें',
      generating: 'चालान तैयार हो रहा है...',
      dualSignatureRequired: 'दोहरे क्रिप्टोग्राफिक डिजिटल हस्ताक्षर अनिवार्य',
      inspectorSig: 'गुणवत्ता निरीक्षक हस्ताक्षर',
      operatorSig: 'तौल ऑपरेटर हस्ताक्षर',
      authorizePayout: 'हस्ताक्षर कर डीबीटी भुगतान जारी करें',
      authorizing: 'हस्ताक्षर सत्यापन एवं भुगतान प्रक्रिया जारी...',
      payoutSettled: 'भुगतान पूर्ण: डीबीटी बैंक खाता ट्रांसफर संपन्न',
      dbtReference: 'पीएफएमएस / डीबीटी संदर्भ संख्या',

      deductionsCut: 'नमी या हैंडलिंग कटौती',
      targetInvoiceAmount: 'लक्षित चालान राशि',
      verifyingSignatures: 'क्रिप्टोग्राफिक हस्ताक्षरों का सत्यापन जारी...',
      stageDualSignature: 'दोहरे हस्ताक्षर डीबीटी भुगतान चरणबद्ध करें',
      simulatePfms: 'पीएफएमएस / एनपीसीआई आधार निपटान डायरेक्ट रेल सिमुलेट करें',
      officialFormJ: 'आधिकारिक फॉर्म जे — बिक्री सूचना एवं रसीद',
      totalNetAmount: 'कुल शुद्ध देय राशि',
      totalDisbursement: 'कुल स्वीकृत संवितरण',
      farmerName: 'किसान का नाम',
      commodityNetQty: 'जिंस / शुद्ध मात्रा',
      ratePerQuintal: 'दर प्रति क्विंटल',
      totalDeductions: 'कुल कटौती',
      dbtConfirmation: 'सरकारी डीबीटी निपटान पुष्टिकरण',
      payoutBlockHash: 'क्रिप्टोग्राफिक भुगतान ब्लॉक हैश',
      pfmsReference: 'पीएफएमएस आधार संदर्भ',
      inspectorRemarks: 'निरीक्षक टिप्पणी',
      inspectorHmac: 'निरीक्षक एचएमएसी-एसएचए256',
      operatorHmac: 'ऑपरेटर एचएमएसी-एसएचए256',
      enterOrVerifyHmac: 'एचएमएसी दर्ज करें या सत्यापित करें',
      noCropSpecified: 'सक्रिय लेनदेन के लिए कोई फसल वस्तु निर्दिष्ट नहीं है।',
      mspNotFoundInMaster: '\'{crop}\' के लिए फसल मास्टर में प्राधिकृत एमएसपी नहीं मिला।',
      failedFetchCropMaster: 'फसल मास्टर निर्देशिका प्राप्त करने में विफल।',
      vehicleMustBeWeighedTare: 'लेनदेन \'{state}\' स्थिति में है। जे-फॉर्म उत्पन्न करने से पहले वाहन \'WEIGHED_TARE\' स्थिति में होना चाहिए।',
      mspUnresolvedWait: 'प्राधिकृत फसल एमएसपी अनसुलझा है। कृपया फसल मास्टर समाधान की प्रतीक्षा करें।',
      jformRejectedServer: 'सर्वर द्वारा जे-फॉर्म बिलिंग अस्वीकृत',
      invoiceGeneratedDualSig: 'आधिकारिक जे-फॉर्म चालान उत्पन्न: ₹{amount}। स्थिति: {state}। दोहरे हस्ताक्षर भुगतान स्टेजिंग के लिए तैयार।',
      offlineInvoiceSaved: '[ऑफलाइन WAL] जे-फॉर्म चालान (₹{amount}) IndexedDB transactionsWAL में सहेजा गया।',
      unknownBillingError: 'अज्ञात बिलिंग त्रुटि',
      failedGenerateDemoSigs: 'डेमो हस्ताक्षर उत्पन्न करने में विफल।',
      couldNotObtainDemoSigs: 'डेमो हस्ताक्षर प्राप्त नहीं किए जा सके।',
      payoutStagingFailed: 'भुगतान स्टेजिंग विफल',
      payoutStagedSettled: 'डीबीटी भुगतान स्टेज और निपटारा पूर्ण! ब्लॉक हैश: {hash}...',
      generateJformFirstDbt: 'डीबीटी संवितरण शुरू नहीं किया जा सकता: कृपया पहले जे-फॉर्म चालान उत्पन्न करें।',
      pfmsSimRejected: 'पीएफएमएस आधार भुगतान रेल सिमुलेशन अस्वीकृत।',
      dbtFailed: 'डीबीटी संवितरण विफल',
      preflightNotice: 'जे-फॉर्म बिलिंग उत्पन्न करने से पहले कृपया धर्मकांटा शुद्ध निपटान पूर्ण करें।',
      mspRatePlaceholder: 'प्राधिकृत एमएसपी दर',
      resolvingMsp: 'एमएसपी समाधान हो रहा है...',
      unresolved: 'अनसुलझा',
      resolvingAuthoritativeMsp: 'प्राधिकृत एमएसपी समाधान हो रहा है...',
      authoritativeSettlementSummary: 'प्राधिकृत उपार्जन निपटान सारांश',
      grossValue: 'सकल मूल्य',
      dbtStatus: 'डीबीटी स्थिति',
      statusPendingStaging: 'स्टेजिंग लंबित',
      statusStaged: 'दोहरे हस्ताक्षर सत्यापित',
      statusSettled: 'पीएफएमएस द्वारा भुगतान संपन्न',
      autoResolvedWeighed: 'तौल पूर्ण हो चुके वाहन का स्वतः समाधान हुआ',
    },
    sync: {
      title: 'ऑफलाइन डब्ल्यूएएल सिंक मॉनिटर',
      subtitle: 'लोकल-फर्स्ट ट्रांजेक्शन लॉग एवं क्रिप्टोग्राफिक रीप्ले सुरक्षा',
      walStatus: 'राइट-अहेड लॉग (WAL) रजिस्टर',
      pendingMutations: 'लंबित ऑफलाइन प्रविष्टियां',
      syncedMutations: 'सिंक पूर्ण प्रविष्टियां',
      triggerSync: 'सभी प्रविष्टियों को तुरंत सिंक करें',
      syncing: 'मंडी सर्वर से सिंक हो रहा है...',
      mutationId: 'प्रविष्टि आईडी',
      targetState: 'लक्षित स्थिति',
      timestamp: 'दर्ज समय',
      statusLabel: 'सिंक स्थिति',
    },
    demoTools: {
      title: 'मंडीक्यू डेमो प्रदर्शन टूल्स',
      subtitle: 'प्रदर्शन नियंत्रण, किसान अदला-बदली एवं तकनीकी प्रमाण',
      tabControls: 'प्रदर्शन क्रियाएं',
      tabFarmerSwitcher: 'प्रदर्शन किसान बदलें',
      tabEvidence: 'तकनीकी प्रमाण',
      resetShowcase: 'डेमो डेटाबेस रीसेट करें',
      resetting: 'रीसेट हो रहा है...',
      resetSuccess: 'डेमो डेटाबेस स्वच्छतापूर्वक मूल स्थिति में रीसेट हो गया।',
      simulateTraffic: 'यातायात वाहन कतार बनाएं',
      simulatingTraffic: 'वाहन जोड़े जा रहे हैं...',
      simulateBlackout: 'ग्रामीण बिजली/इंटरनेट गुल सिमुलेशन',
      blackoutActive: 'आउटेज सिमुलेशन सक्रिय: ऑफलाइन मोड लागू',
      launchE2E: 'स्वचालित ई2ई परीक्षण यात्रा चलाएं',
      resetShowcaseDesc: 'नियत डेमो स्थिति को पुनर्स्थापित करता है',
      simulateTrafficDesc: 'कतार में वास्तविक डेमो रिकॉर्ड दर्ज करता है',
      launchE2EDesc: 'एक लेन-देन को वास्तविक वर्कफ़्लो में आगे बढ़ाता है',
      showcaseCommandCenter: 'शोकेस नियंत्रण केंद्र',
      showcaseSubtitle: 'निर्णायक मंडल हेतु प्रामाणिक डेमो',
      openUSSD: 'मोबाइल यूएसएसडी फोन खोलें (*247#)',
      switchFarmerTitle: 'प्रदर्शन किसान चयन',
      switchFarmerDesc: 'किसान प्रोफाइल, उत्पादन सीमा और बुकिंग व्यवहार प्रदर्शित करने हेतु अधिकृत किसान चुनें।',
      activeContextNotice: 'प्रोटोटाइप डेमो संदर्भ: केवल व्यवस्थापक और सुपरवाइजर प्रदर्शन के लिए।',
      technicalEvidenceTitle: 'मंडीक्यू तकनीकी वास्तुकला एवं सिद्धांत',
      dcdqTitle: 'DCDQ बहु-मानदंडीय प्राथमिकता गणितीय सूत्र',
      dcdqFormula: 'S_i = alpha * A_i + beta * D_i + gamma * M_i + lambda * W_i',
      dcdqAlpha: 'alpha * A_i (दूरी घटक): दूरस्थ गांवों से आने वाले किसानों को प्राथमिकता।',
      dcdqBeta: 'beta * D_i (खराब होने का जोखिम): शीघ्र खराब होने वाली फसलों का संरक्षण।',
      dcdqGamma: 'gamma * M_i (नमी घटक): 15-17% नमी वाले अनाज को फफूंद से बचाने हेतु प्राथमिकता।',
      dcdqLambda: 'lambda * W_i (एंटी-स्टारवेशन बोनस): प्रतीक्षा समय के साथ स्कोर बढ़ता है ताकि सूखा अनाज न छूटे।',
      invariantsTitle: 'गारंटीकृत गणितीय एवं सुरक्षा सिद्धांत',
      invCeiling: 'किसान उपज सीमा सिद्धांत: सक्रिय बुकिंग पंजीकृत भूमि उत्पादन क्षमता से अधिक नहीं हो सकती।',
      invSlot: 'स्लॉट क्षमता सिद्धांत: प्रति घंटा वाहन भार मंडी यार्ड सीमा से अधिक नहीं हो सकता।',
      invState: 'अपरिवर्तनीय जीवन चक्र: चरण कभी छोड़े नहीं जा सकते (गेट -> जांच -> वजन -> बिल -> भुगतान)।',
      invCrypto: 'क्रिप्टोग्राफिक सुरक्षा: की अथवा डेटा में बदलाव होने पर HMAC तुरंत अस्वीकृत होता है।',
      invWal: 'लोकल-फर्स्ट ऑफलाइन WAL: बिना नेटवर्क के भी इंडेक्स्ड-डीबी में सुरक्षित डेटा रिकॉर्डिंग।',

      accessRestricted: 'पहुंच प्रतिबंधित',
      accessRestrictedDesc: 'डेमो टूल्स एवं तकनीकी साक्ष्य केवल मंडी बोर्ड प्रशासकों और एपीएमसी यार्ड पर्यवेक्षकों के लिए प्रतिबंधित हैं।',
      invCeilingTitle: '1. उपज सीमा अपरिवर्तनीय',
      invSlotTitle: '2. स्लॉट क्षमता अपरिवर्तनीय',
      invStateTitle: '3. एकदिशीय जीवनचक्र',
      invCryptoTitle: '4. HMAC-SHA256 क्रिप्टोग्राफी',
      invWalTitle: '5. स्थानीय-प्रथम राइट-अहेड लॉग',
      farmerSwitched: 'सक्रिय डेमो किसान बदला गया: {name} (किसान आईडी: {id})।',
      advanceTime: 'कतार समय आगे बढ़ाएं / पुनः गणना',
      advancingTime: 'समय आगे बढ़ रहा है...',
      advanceTimeDesc: 'अलग सिमुलेशन घड़ी का उपयोग कर प्रतीक्षा समय बढ़ाता है ताकि DCDQ एंटी-स्टारवेशन क्रम परिवर्तन प्रदर्शित हो सके।',
      optimizeSlots: 'अपॉइंटमेंट स्लॉट अनुकूलित करें',
      optimizeSlotsDesc: 'यार्ड स्लॉट वितरण संतुलित करने और कुल भीड़ को कम करने के लिए HiGHS BILP अनुकूलन चलाएं।',
      tasTitle: 'टीएएस बीआईएलपी स्लॉट अनुकूलक',
      tasSubtitle: 'आवक ट्रक भार संतुलन हेतु मिक्स्ड-इंटीजर लीनियर प्रोग्राम (एल्गोरिदम 6)',
      tasRunSolver: 'HiGHS BILP सॉल्वर चलाएं',
      tasSolving: 'लीनियर प्रोग्राम हल हो रहा है...',
      tasBefore: 'पहले',
      tasAfter: 'बाद में',
      tasOverload: 'यार्ड अधिभार',
      tasObjective: 'उद्देश्य मूल्य',
      tasMaxSlotLoad: 'अधिकतम स्लॉट लोड',
      tasTrucks: 'ट्रक',
      tasSolverBadge: 'HiGHS BILP सॉल्वर',
      failureModelTitle: 'लॉजिस्टिक बुकिंग विफलता जोखिम मॉडल',
      failureModelDesc: 'आगमन समय विचलन के आधार पर अपॉइंटमेंट विफलता की अनुभवजन्य संभावना का मूल्यांकन।',
      failureModelLabel: 'MODELLED RISK — NOT AN ACTUAL FAILURE PREDICTION',
      expectedArrival: 'अपेक्षित आगमन',
      actualArrival: 'वास्तविक आगमन',
      arrivalDeviation: 'आगमन विचलन',
      failureProbability: 'विफलता संभावना',
      concurrentBookingTitle: 'समवर्ती स्लॉट बुकिंग परीक्षण',
      concurrentBookingDesc: 'रेडिस SET NX PX एटॉमिक लॉकिंग का उपयोग करके एक ही स्लॉट पर 10 समवर्ती आरक्षण का अनुकरण।',
      runConcurrentTest: 'समवर्ती बुकिंग परीक्षण चलाएं',
      runningConcurrentTest: 'समवर्ती लॉक परीक्षण जारी...',
      totalRequests: 'कुल अनुरोध',
      successfulRequests: 'सफल',
      rejectedRequests: 'अस्वीकृत',
      capacityExceededZero: 'क्षमता उल्लंघन: 0',
      lockAcquisitionTimeline: 'लॉक अधिग्रहण एवं रिलीज समयरेखा',
      redisMutexBadge: 'रेडिस SET NX PX वितरित म्यूटेक्स (प्रोटोटाइप)',
      lwwConflictTitle: 'LWW संघर्ष समाधान (प्राधिकृत सर्वर अनुक्रम)',
      lwwConflictDesc: 'प्राधिकृत सर्वर अनुक्रम का उपयोग करके फ़ील्ड-स्तरीय LWW विलय का प्रदर्शन।',
      runLWWTest: 'LWW समाधान प्रदर्शित करें',
      runningLWWTest: 'संघर्ष समाधान जारी...',
      lwwMutationA: 'उत्परिवर्तन A',
      lwwMutationB: 'उत्परिवर्तन B',
      authoritativeSequenceWinner: 'उच्च प्राधिकृत सर्वर अनुक्रम',
      governanceNotice: 'शासन सूचना: प्राधिकृत क्रम सर्वर अनुक्रम द्वारा संचालित है, क्लाइंट घड़ियों द्वारा नहीं।',
      clientTimestampDiagnostic: 'क्लाइंट समय टिकट (नैदानिक मेटाडेटा)',
      field: 'फ़ील्ड',
      oldValue: 'पुराना मान',
      incomingValue: 'आवक मान',
      winner: 'विजेता',
      reason: 'समाधान का कारण',
      gzipSyncTitle: 'ऑफलाइन WAL Gzip संपीड़न साक्ष्य',
      gzipSyncDesc: 'क्लाउड सर्वर पर प्रेषण से पूर्व IndexedDB WAL बैच संपीड़न का प्रदर्शन।',
      testGzipSync: 'Gzip WAL सिंक परीक्षण करें',
      testingGzipSync: 'संपीड़न एवं सिंक जारी...',
      rawSize: 'मूल पेलोड आकार',
      compressedSize: 'संपीड़ित Gzip आकार',
      compressionRatio: 'संपीड़न बचत',
      recordCount: 'रिकॉर्ड संख्या',
      decompressionVerified: 'सर्वर पर विकीर्ण एवं सत्यापित',
      slotCapacity: 'स्लॉट क्षमता (क्विंटल)',
      serverSequence: 'सर्वर अनुक्रम (server_receive_sequence)',
      tabAlgorithms: 'एल्गोरिदम कंट्रोल सेंटर',
    },
    controlCenter: {
      title: 'मंडीक्यू एल्गोरिदम कंट्रोल सेंटर',
      subtitle: 'वास्तविक परिचालन एल्गोरिदम का प्रामाणिक लाइव निष्पादन प्रदर्शन',
      dataIsolationNotice: 'सभी एल्गोरिदम is_showcase=true के साथ निष्पादित होते हैं। वास्तविक खरीद रिकॉर्ड पूर्णतः सुरक्षित हैं।',
      resetDemoBtn: 'एल्गोरिदम डेमो रीसेट करें',
      resettingDemo: 'डेमो रिकॉर्ड हटाए जा रहे हैं...',
      resetDemoSuccess: 'एल्गोरिदम डेमो रिकॉर्ड सफलतापूर्वक हटा दिए गए। वास्तविक खरीद लॉग पूरी तरह सुरक्षित हैं।',
      statusLive: 'लाइव सिस्टम',
      statusSimulation: 'नियंत्रित सिमुलेशन',
      statusAlgoDemo: 'एल्गोरिद्म प्रदर्शन',
      statusDemo: 'एल्गोरिद्म प्रदर्शन',
      statusDocumented: 'केवल प्रलेखित',
      statusNotImplemented: 'वर्तमान संस्करण में लागू नहीं',
      verifiedStatus: 'सत्यापन स्थिति',
      executionTrace: 'निष्पादन ट्रेस',
      formulaLabel: 'प्रामाणिक सूत्र',
      liveInputsLabel: 'लाइव इनपुट एवं नियंत्रण',
      actualOutputLabel: 'वास्तविक परिकलित परिणाम',
      summaryCountLive: 'लाइव परिचालन',
      summaryCountDemo: 'निष्पादन डेमो',
      summaryCountDocumented: 'प्रलेखित संदर्भ',
      summaryCountNotImplemented: 'लागू नहीं',
      mandiSelectionRequiredDesc: 'एल्गोरिदम संचालन, लाइव कतार टेलीमेट्री और प्रदर्शन परीक्षणों के लिए एक सक्रिय चयनित मंडी आवश्यक है। DATA-001 के अनुसार कोई जादुई डिफ़ॉल्ट की अनुमति नहीं है।',
      twoModules: '2 मॉड्यूल',
      sixModules: '6 मॉड्यूल',
      liveModulesSummary: '1. DCDQ लाइव कतार एवं 2. बहु-सर्वर ईटीए (100% लाइव बैकएंड डेटा)',
      demoModulesSummary: '3. TAS BILP, 4. रेडिस लॉक, 5. सर्वर-अनुक्रम विलय, 6. HMAC, 7. Gzip, 8. लॉजिस्टिक जोखिम',

      // Module 1: DCDQ
      dcdqModuleTitle: '1. DCDQ गतिशील कतार प्राथमिकता',
      dcdqModuleDesc: 'डायनामिक क्रॉप-डिहाइड्रेशन एवं कंजेशन कतार (DCDQ) वाहनों को समग्र स्कोर S_i के अनुसार रेडिस ZSET में व्यवस्थित करता है।',
      dcdqVehicleCol: 'वाहन / लॉट',
      dcdqScoreACol: 'A (अपॉइंटमेंट पालन)',
      dcdqScoreDCol: 'D (डेमरेज एवं भार)',
      dcdqScoreMCol: 'M (नमी जोखिम सूचकांक)',
      dcdqScoreWCol: 'W (प्रतीक्षा बोनस)',
      dcdqScoreSCol: 'S (समग्र प्राथमिकता)',
      dcdqRankCol: 'रैंक',
      dcdqWaitSliderLabel: 'प्रतीक्षा समय बदलाव सिमुलेट करें (+मिनट)',
      dcdqMoistureSliderLabel: 'नमी बदलाव सिमुलेट करें (%)',
      dcdqTriggerReorderBtn: 'कतार पुनर्व्यवस्था प्रदर्शित करें',
      dcdqReordering: 'DCDQ स्कोर पुनः परिकलित हो रहे हैं...',
      dcdqReorderResultNotice: 'एंटी-स्टारवेशन बोनस W_i अद्यतन हुआ। वाहन रैंक गतिशील रूप से बदल गई।',
      dcdqLiveQueueEmpty: 'लाइव एपीएमसी कतार वर्तमान में खाली है। गेट टर्मिनल पर आवक दर्ज करें या डेमो टूल्स में \'डेमो ट्रैफिक बनाएं\' पर क्लिक करें।',
      dcdqRerankLiveBtn: 'लाइव कतार पुनः परिकलित एवं व्यवस्थित करें',
      dcdqRerankingLive: 'प्रामाणिक DCDQ री-रैंकिंग जारी...',
      dcdqCanonicalFormulaNotice: 'S_i = 1.0 * A_i + 1.0 * D_i + 1.0 * M_i + 1.0 * W_i (रेडिस ZSET में बैकएंड प्रामाणिक DCDQ इंजन द्वारा मूल्यांकित)',

      // Module 2: ETA
      etaModuleTitle: '2. M(t)/E_k/c(t) बहु-सर्वर कतार ईटीए मॉडल',
      etaModuleDesc: 'आगे उपस्थित पेलोड, पिछले 15 मिनट के धर्मकांटा थ्रूपुट और सक्रिय स्केल्स की संख्या के आधार पर सेवा प्रतीक्षा समय का सटीक अनुमान।',
      etaQueueAhead: 'आगे वाहन',
      etaPayloadAhead: 'आगे पेलोड',
      etaServiceRate: '15-मिनट सेवा दर',
      etaActiveScales: 'सक्रिय स्केल्स c(t)',
      etaCalculatedEta: 'अनुमानित सेवा समय (ईटीए)',
      etaScaleCountStepper: 'सक्रिय धर्मकांटा स्केल्स की संख्या सेट करें',
      etaRecalculating: 'बहु-सर्वर ईटीए की पुनः गणना जारी...',

      // Module 3: TAS BILP
      tasModuleTitle: '3. TAS BILP ट्रक भीड़ अनुकूलक',
      tasModuleDesc: 'SciPy के माध्यम से HiGHS मिक्स्ड-इंटीजर लीनियर प्रोग्राम चलाकर आवक ट्रक स्लॉट आवंटन को अनुकूलित करता है एवं यार्ड भीड़ समाप्त करता है।',
      tasInputTrucks: 'इनपुट ट्रक',
      tasCandidateSlots: 'प्रस्तावित स्लॉट',
      tasSlotCapacity: 'क्षमता सीमा',
      tasPenalties: 'दंड कारक',
      tasBeforeCongestion: 'भीड़ से पहले (प्रारंभिक)',
      tasOptimizedAssignment: 'अनुकूलित स्लॉट आवंटन आव्यूह',
      tasAfterCongestion: 'भीड़ के बाद (संतुलित)',
      tasRunSolverBtn: 'HiGHS BILP सॉल्वर चलाएं',
      tasOptimizing: 'मिक्स्ड-इंटीजर लीनियर प्रोग्राम हल हो रहा है...',

      // Module 4: Redis Lock
      redisModuleTitle: '4. रेडिस एटॉमिक आरक्षण लॉक (क्षमता संरक्षण)',
      redisModuleDesc: 'अति-समवर्ती स्थिति में शून्य-क्षमता-उल्लंघन सिद्धांत को लागू करने हेतु समवर्ती आरक्षण प्रयासों का अनुकरण करता है।',
      redisDisclaimer: 'वास्तुशिल्प नोट: एकल-इंस्टेंस रेडिस SET NX PX वितरित लॉक एवं एटॉमिक लुआ रिलीज। यह मल्टी-इंस्टेंस रेडलॉक कोरम नहीं है।',
      redisConcurrentRequests: 'समवर्ती अनुरोध',
      redisLockAcquisition: 'लॉक अधिग्रहण समयरेखा',
      redisWinner: 'विजेता वर्कर',
      redisRejections: 'अस्वीकृत अनुरोध',
      redisTtl: 'लॉक टीटीएल',
      redisAtomicRelease: 'एटॉमिक रिलीज तंत्र',
      redisRunTestBtn: '10-वर्कर रेस टेस्ट शुरू करें',
      redisTesting: 'समवर्ती लॉक अनुरोध निष्पादित हो रहे हैं...',

      // Module 5: LWW
      lwwModuleTitle: '5. सर्वर-अनुक्रम-प्राधिकृत फ़ील्ड-स्तरीय विलय',
      lwwModuleDesc: 'प्राधिकृत सर्वर अनुक्रम का उपयोग करके फ़ील्ड-स्तरीय लास्ट-राइट-विन्स विलय। ऑफलाइन नोड्स में सटीक एकरूपता सुनिश्चित करता है।',
      lwwMutationA: 'उत्परिवर्तन A (ऑफलाइन टर्मिनल 01)',
      lwwMutationB: 'उत्परिवर्तन B (ऑफलाइन टर्मिनल 02)',
      lwwFieldConflict: 'फ़ील्ड-दर-फ़ील्ड संघर्ष विश्लेषण',
      lwwServerSequence: 'प्राधिकृत सर्वर अनुक्रम',
      lwwClientTimestamp: 'क्लाइंट समय टिकट (केवल नैदानिक)',
      lwwWinningValue: 'प्राधिकृत विजेता मान',
      lwwDeduplication: 'WAL रिप्ले दोहराव जांच',
      lwwSyncStatus: 'सिंक स्थिति',
      lwwRunTestBtn: 'LWW संघर्ष परीक्षण चलाएं',
      lwwTesting: 'उत्परिवर्तन संघर्ष हल हो रहा है...',

      // Module 6: HMAC
      hmacModuleTitle: '6. HMAC-SHA256 क्रिप्टोग्राफिक ऑडिटिंग',
      hmacModuleDesc: 'कानस्टेंट-टाइम तुलना (FIPS 198-1) का उपयोग करके प्रामाणिक बुकिंग पेलोड पर डिजिटल हस्ताक्षरों का सत्यापन करता है।',
      hmacCanonicalPayload: 'प्रामाणिक पेलोड',
      hmacSignatureLength: 'हस्ताक्षर लंबाई (हेक्स वर्ण)',
      hmacVerificationResult: 'प्रामाणिक सत्यापन परिणाम',
      hmacTamperedPayload: 'छेड़छाड़ किया गया पेलोड (1 बाइट बदला)',
      hmacRejectionResult: 'अस्वीकृति परिणाम',
      hmacSecretKeyRedacted: 'सीक्रेट की स्थिति: [संरक्षित — सर्वर वॉल्ट में 256-बिट क्रिप्टोग्राफिक एन्ट्रॉपी]',
      hmacRunVerifyBtn: 'क्रिप्टोग्राफिक सत्यनिष्ठा जांचें',
      hmacVerifying: 'SHA-256 HMAC डाइजेस्ट परिकलित हो रहा है...',
      hmacTestPayload: 'क्रिप्टोग्राफिक टेस्ट पेलोड',
      hmacTestFixtureNotice: 'परीक्षण सूचना: नीचे दिए गए पहचानकर्ता सिंथेटिक परीक्षण फिक्स्चर हैं, वास्तविक किसान पहचान नहीं।',
      hmacSyntheticFixtureInputs: 'सिंथेटिक फिक्सचर इनपुट: किसान #101, स्लॉट #5',

      // Module 7: Gzip
      gzipModuleTitle: '7. RFC 1952 Gzip ऑफलाइन WAL संपीड़न',
      gzipModuleDesc: 'ऑफलाइन IndexedDB राइट-अहेड लॉग बैचों के लिए वास्तविक बाइट संपीड़न और सर्वर डीकंप्रेशन का मापन करता है।',
      gzipRawSize: 'मूल JSON पेलोड आकार',
      gzipCompressedSize: 'संपीड़ित Gzip आकार',
      gzipCompressionRatio: 'संपीड़न बचत अनुपात',
      gzipRecordCount: 'WAL उत्परिवर्तन संख्या',
      gzipSyncResult: 'सर्वर डीकंप्रेशन स्थिति',
      gzipRunCompressBtn: 'Gzip संपीड़न बैच चलाएं',
      gzipCompressing: 'WAL बैच संपीड़ित हो रहा है...',

      // Module 8: Logistic Booking Risk
      riskModuleTitle: '8. लॉजिस्टिक बुकिंग विफलता जोखिम भविष्यवक्ता',
      riskModuleDesc: 'आगमन समय विचलन के आधार पर अपॉइंटमेंट अनुपस्थिति और परिवहन विफलता की अनुभवजन्य संभावना का मूल्यांकन।',
      riskModelledDisclaimer: 'गणितीय रूप से मॉडल किया गया जोखिम — वास्तविक खरीद विफलता भविष्यवाणी नहीं',
      riskExpectedArrival: 'अपेक्षित आगमन समय',
      riskActualArrival: 'वास्तविक आगमन समय',
      riskDeviation: 'परिवहन विचलन (Delta t)',
      riskParameterK: 'संवेदनशीलता पैरामीटर (k)',
      riskCalculatedRisk: 'परिकलित विफलता संभावना',
      riskDeviationSlider: 'आगमन विचलन समायोजित करें (मिनट)',
    },
    receipt: {
      title: 'डिजिटल जे-फॉर्म खरीद रसीद',
      govtHeader: 'कृषि उपज मंडी समिति (एपीएमसी)',
      jformSubheader: 'अधिकृत ई-नाम एवं प्रत्यक्ष लाभ अंतरण (DBT) प्रमाण पत्र',
      qrValid: 'क्रिप्टोग्राफिक रूप से सत्यापित टोकन',
      printSlip: 'रसीद प्रिंट करें',
      close: 'खिड़की बंद करें',

      cryptoAuditTrail: 'क्रिप्टोग्राफिक ऑडिट एवं भुगतान ट्रेल',
      ledgerHash: 'लेज़र हैश',
      hmacToken: 'एचएमएसी टोकन',
      dbtRef: 'डीबीटी संदर्भ',
    },
    admin: {
      title: 'एपीएमसी प्रशासन केंद्र',
      subtitle: 'राज्य खरीद प्राधिकरण एवं मंडी प्रांगण अवसंरचना प्रबंधन',
      tabMandis: 'एपीएमसी मंडियां',
      tabCrops: 'फसलें एवं एमएसपी',
      tabUsers: 'स्टेशन उपयोगकर्ता',
      tabSlots: 'खरीद स्लॉट',
      totalRegisteredFarmers: 'पंजीकृत किसान',
      activeTransactions: 'सक्रिय यार्ड लेनदेन',
      queuedVehicles: 'कतारबद्ध वाहन',
      volumeProcured: 'कुल खरीदी गई मात्रा',
      payoutSettled: 'कुल डीबीटी भुगतान',
      qualityInspected: 'परीक्षित लॉट',
      rejectionRate: 'अस्वीकृति दर',
      activeWeighbridges: 'सक्रिय धर्मकांटे',
      dailyCapacity: 'दैनिक क्षमता',
      operationalStatus: 'परिचालन स्थिति',
      simulateTraffic: 'यातायात सिमुलेट करें',
      simulatingTraffic: 'सिमुलेशन जारी...',
      resetShowcase: 'शोकेस रीसेट करें',
      resetting: 'रीसेट हो रहा है...',
      resetConfirmPrompt: 'क्या आप वाकई शोकेस डेटाबेस को मूल स्थिति में रीसेट करना चाहते हैं?',
      addMandi: 'नई मंडी जोड़ें',
      addCrop: 'नई फसल जोड़ें',
      addUser: 'कर्मचारी खाता जोड़ें',
      generateBatchSlots: 'दैनिक स्लॉट बनाएं',
      generatingSlots: 'स्लॉट बन रहे हैं...',
      refreshData: 'डेटा ताज़ा करें',
      toggleOperational: 'परिचालन स्थिति बदलें',
      toggleActive: 'सक्रिय स्थिति बदलें',
      mandiName: 'मंडी का नाम',
      districtState: 'जिला एवं राज्य',
      dailyCapacityQt: 'दैनिक क्षमता (क्विंटल)',
      weighbridges: 'धर्मकांटे',
      status: 'स्थिति',
      actions: 'कार्रवाई',
      cropName: 'फसल का नाम',
      cropCode: 'फसल कोड',
      category: 'श्रेणी',
      mspPrice: 'एमएसपी दर (₹/क्विंटल)',
      optimalMoisture: 'आदर्श नमी (%)',
      maxMoisture: 'अधिकतम नमी (%)',
      username: 'उपयोगकर्ता नाम',
      fullName: 'पूरा नाम',
      role: 'निर्धारित पद',
      assignedMandi: 'आवंटित मंडी',
      slotTime: 'समय अंतराल',
      allocatedCapacity: 'आवंटित क्षमता (क्विंटल)',
      bookedCapacity: 'आरक्षित क्षमता (क्विंटल)',
      remainingCapacity: 'उपलब्ध क्षमता (क्विंटल)',
      scheduledDate: 'निर्धारित तिथि',
      createMandiTitle: 'नई एपीएमसी मंडी पंजीकृत करें',
      createCropTitle: 'नई खरीद फसल पंजीकृत करें',
      createUserTitle: 'नया स्टेशन ऑपरेटर खाता बनाएं',
      generateSlotsTitle: 'प्रति घंटा खरीद स्लॉट बनाएं',
      mandiNameLabel: 'मंडी यार्ड का नाम',
      districtLabel: 'जिला',
      stateLabel: 'राज्य',
      dailyCapacityLabel: 'दैनिक खरीद क्षमता (क्विंटल)',
      weighbridgesLabel: 'सक्रिय धर्मकांटों की संख्या',
      cropNameLabel: 'फसल का नाम',
      cropCodeLabel: 'फसल कोड',
      categoryLabel: 'फसल श्रेणी',
      mspLabel: 'न्यूनतम समर्थन मूल्य (₹/क्विंटल)',
      optimalMoistureLabel: 'आदर्श नमी मानक (%)',
      maxMoistureLabel: 'अधिकतम नमी सीमा (%)',
      usernameLabel: 'लॉगिन पहचान नाम',
      fullNameLabel: 'ऑपरेटर का पूरा नाम',
      roleLabel: 'स्टेशन पद',
      passwordLabel: 'पहुंच पासकोड',
      targetDateLabel: 'खरीद लक्ष्य तिथि',
      startHourLabel: 'प्रारंभिक घंटा (24h प्रारूप)',
      endHourLabel: 'अंतिम घंटा (24h प्रारूप)',
      capacityPerHourLabel: 'प्रति घंटा स्लॉट क्षमता (क्विंटल)',
      saveButton: 'रिकॉर्ड सहेजें',
      cancelButton: 'रद्द करें',
      activeStatus: 'सक्रिय',
      inactiveStatus: 'निष्क्रिय',
      operationalStatusActive: 'सक्रिय परिचालन',
      operationalStatusInactive: 'बंद',
      noMandisFound: 'कोई पंजीकृत मंडी उपलब्ध नहीं है।',
      noCropsFound: 'कोई पंजीकृत फसल उपलब्ध नहीं है।',
      noUsersFound: 'कोई उपयोगकर्ता खाता नहीं मिला।',
      noSlotsFound: 'इस तिथि हेतु कोई खरीद स्लॉट नहीं मिला।',
      selectMandiToViewSlots: 'खरीद समय-सारणी देखने हेतु ऊपर किसी मंडी यार्ड का चयन करें।',
      offlineNotice: 'प्रशासनिक सेटिंग्स अद्यतन करने हेतु सक्रिय सर्वर नेटवर्क अनिवार्य है।',

      hubSubtitle: 'सिस्टम मास्टर एवं यार्ड शासन केंद्र',
      hubDesc: 'एपीएमसी मंडियों को कॉन्फ़िगर करें, वैधानिक एमएसपी दरें अपडेट करें, स्टाफ की भूमिकाओं की निगरानी करें और प्रति घंटा गेट क्षमता आवंटित करें।',
      apmcBoardAdmin: 'एपीएमसी बोर्ड प्रशासन',
      eNamCloudAuth: 'ई-नाम क्लाउड अधिकृत',
      offlineWalMode: 'ऑफलाइन वाल मोड',
      backendOffline: 'मंडीक्यू बैकएंड एपीआई ऑफलाइन है (पोर्ट 8000)',
      backendOfflineDesc: 'पायथन फास्टएपीआई सर्वर वर्तमान में अनुपलब्ध है। लाइव यार्ड टेलीमेट्री, स्लॉट बुकिंग और डीसीडीक्यू सिमुलेशन के लिए बैकएंड चलना आवश्यक है।',
      startInTerminal: 'टर्मिनल में प्रारंभ करें:',
      simulateTooltip: 'गतिशील पुन: रैंकिंग प्रदर्शित करने के लिए चरणों में यथार्थवादी वाहन जोड़ें',
      resetTooltip: 'प्रदर्शन डेटाबेस को रीसेट करें',
      liveDynamicStream: 'लाइव गतिशील स्ट्रीम (5s)',
      dcdqSorted: 'डीसीडीक्यू क्रमबद्ध',
      totalPipeline: 'कुल पाइपलाइन',
      quintalsProcured: 'कुल क्विंटल खरीदा',
      pfmsSettled: 'पीएफएमएस निपटान',
      moistureRejection: '> 17% नमी',
      agriStackVerified: 'एग्रीस्टैक सत्यापित',
      mandisSubtitle: 'निर्धारित वे-ब्रिज और दैनिक टन भार सीमा वाले केंद्रीय रूप से प्रमाणित खरीद यार्ड।',
      cropsSubtitle: 'स्वचालित जे-फॉर्म बिलिंग और नमी अस्वीकृति सीमा के दौरान लागू मानक खरीद दरें।',
      usersSubtitle: 'हस्ताक्षरित एचएमएसी क्रिप्टोग्राफिक टोकन से प्राप्त आधिकारिक भूमिका मानचित्रण।',
      slotsSubtitle: 'रीयल-टाइम स्लॉट अधिभोग की निगरानी करें और बैच बुकिंग विंडो उत्पन्न करें।',
      universalAccess: 'सार्वभौमिक सिस्टम पहुंच',
      noMandisAvailable: 'कोई क्रियाशील मंडी उपलब्ध नहीं है',
      clickGenerateSlots: 'प्रति घंटा विंडो प्रारंभ करने के लिए ऊपर \"स्लॉट उत्पन्न करें (अगले 7 दिन)\" पर क्लिक करें।',
      slotId: 'स्लॉट आईडी',
      utilization: 'उपयोग',
      editMsp: 'एमएसपी संपादित करें',
      deactivate: 'निष्क्रिय करें',
      mandiNamePlaceholder: 'उदा. उज्जैन एपीएमसी मंडी',
      districtPlaceholder: 'उज्जैन',
      statePlaceholder: 'मध्य प्रदेश',
      cropNamePlaceholder: 'गेहूँ (शरबती)',
      mspPriceUnit: 'वैधानिक एमएसपी मूल्य (₹ / क्विंटल)',
      optimalMoistureUnit: 'इष्टतम नमी %',
      maxMoistureUnit: 'अधिकतम नमी सीमा %',
      perQuintal: '/ क्विंटल',
      dataUnavailable: 'प्रशासन डेटा अनुपलब्ध: {errors}',
      showcaseInjected: 'लाइव शोकेस ट्रैफ़िक सफलतापूर्वक डेटाबेस और प्राथमिकता कतार में प्रविष्ट किया गया!',
      errorSimulating: 'शोकेस ट्रैफ़िक सिमुलेशन में त्रुटि',
      showcaseResetClean: 'शोकेस डेटाबेस और प्राथमिकता कतार स्वच्छ रूप से रीसेट किए गए!',
      errorResetting: 'शोकेस डेटाबेस रीसेट करने में त्रुटि',
      failedCreateMandi: 'मंडी बनाने में विफल',
      mandiRegisteredSuccess: 'एपीएमसी मंडी "{name}" सफलतापूर्वक पंजीकृत की गई!',
      errorCreatingMandi: 'मंडी बनाने में त्रुटि',
      failedUpdateStatus: 'स्थिति अद्यतन करने में विफल',
      errorUpdatingMandiStatus: 'मंडी स्थिति अद्यतन करने में त्रुटि',
      failedUpdateCommodity: 'वस्तु अद्यतन करने में विफल',
      commodityMspUpdated: 'वस्तु "{name}" एमएसपी ₹{msp}/क्विंटल पर अद्यतन किया गया!',
      errorUpdatingCrop: 'फसल अद्यतन करने में त्रुटि',
      confirmDeactivateCommodity: 'क्या आप वाकई वस्तु "{name}" को निष्क्रिय करना चाहते हैं?',
      failedDeactivateCommodity: 'वस्तु निष्क्रिय करने में विफल',
      commodityDeactivatedSuccess: 'वस्तु "{name}" सफलतापूर्वक निष्क्रिय कर दी गई।',
      errorDeactivatingCommodity: 'वस्तु निष्क्रिय करने में त्रुटि',
      failedGenerateSlots: 'स्लॉट उत्पन्न करने में विफल',
      errorGeneratingSlots: 'स्लॉट उत्पन्न करने में त्रुटि',
      slotsGeneratedSuccess: 'अगले 7 दिनों के लिए प्रति घंटा खरीद स्लॉट सफलतापूर्वक उत्पन्न किए गए।',
      cropCodePlaceholder: 'उदा. WHEAT_SHARBATI',
      resetFailed: 'रीसेट विफल',
      simulationFailed: 'सिमुलेशन विफल',
      tasAdminTitle: 'टीएएस स्लॉट अनुकूलन एवं आगमन जोखिम',
      tasAdminSubtitle: 'वाहन नियुक्तियों को संतुलित करने और लॉजिस्टिक विफलता जोखिमों का ऑडिट करने हेतु BILP सॉल्वर चलाएं।',
      tasOptimizeNow: 'स्लॉट आवंटन संतुलित करें',
    },
    journey: {
      modalTitle: 'स्वचालित एंड-टू-एंड खरीद यात्रा',
      modalSubtitle: 'मंडीक्यू के सभी 12 जीवन-चक्र चरणों का इंटरैक्टिव तकनीकी सिमुलेशन',
      runAll: 'संपूर्ण ई2ई यात्रा निष्पादित करें',
      runningAll: 'चरण निष्पादित हो रहे हैं...',
      resetAll: 'सभी चरण रीसेट करें',
      close: 'विंडो बंद करें',
      statusPending: 'लंबित',
      statusRunning: 'प्रक्रिया जारी',
      statusSuccess: 'सत्यापित सफल',
      statusFailed: 'विफल',
      statusBlocked: 'नीति द्वारा अवरुद्ध',
      stageDetails: 'चरण का तकनीकी विवरण',
      duration: 'निष्पादन समय',
      invariantsChecked: 'गणितीय एवं सुरक्षा सिद्धांत',
      payloadResponse: 'क्रिप्टोग्राफिक पेलोड एवं उत्तर',
      stage1Title: 'किसान ई-केवाईसी एवं भूमि रिकॉर्ड (सिमुलेटेड)',
      stage1Desc: 'सत्यापित पहचान एवं उत्पादन सीमा हेतु यूआईडीएआई ई-केवाईसी और एग्रीस्टैक भूमि रजिस्ट्री क्वेरी।',
      stage2Title: 'परमाण्विक स्लॉट आरक्षण + एचएमएसी',
      stage2Desc: 'डिलीवरी स्लॉट आरक्षित कर छेड़छाड़-रोधी HMAC-SHA256 बुकिंग टोकन जारी करना।',
      stage3Title: 'गेट क्यूआर सत्यापन एवं प्रवेश',
      stage3Desc: 'गेट स्कैनर द्वारा आगमन पर क्रिप्टोग्राफिक एचएमएसी हस्ताक्षर की जांच और ट्रक को प्रवेश।',
      stage4Title: 'डिजिटल गुणवत्ता परीक्षण',
      stage4Desc: 'डिजिटल सेंसर द्वारा अनाज नमी परीक्षण। कतार प्रवेश नियम: नमी <= 17.0%।',
      stage5Title: 'DCDQ प्राथमिकता कतार प्रविष्टि',
      stage5Desc: 'समग्र प्राथमिकता स्कोर (S_i) का परिकलन और वाहन को प्राथमिकता कतार में स्थान।',
      stage6Title: 'धर्मकांटा सकल वजन (Gross)',
      stage6Desc: 'लोड-सेल टेलीमेट्री द्वारा भरे ट्रक के कुल वजन (100.00 क्विंटल) का प्रमाणीकरण।',
      stage7Title: 'धर्मकांटा खाली एवं शुद्ध वजन (Tare & Net)',
      stage7Desc: 'खाली ट्रक का वजन (37.50 क्विंटल)। शुद्ध उपज = 62.50 क्विंटल। उपज सीमा की पुनः जांच।',
      stage8Title: 'जे-फॉर्म संयुक्त विक्रय बिलिंग',
      stage8Desc: 'आधिकारिक खरीद चालान परिकलन: 62.50 क्विंटल * ₹2,275 एमएसपी = ₹142,187.50।',
      stage9Title: 'दोहरे हस्ताक्षर डीबीटी स्टेजिंग',
      stage9Desc: 'निरीक्षक एवं ऑपरेटर के दोहरे क्रिप्टोग्राफिक HMAC-SHA256 हस्ताक्षर ब्लॉक हैश से संबद्ध।',
      stage10Title: 'पीएफएमएस आधार भुगतान रेल (मॉक)',
      stage10Desc: 'सरकारी PFMS / NPCI आधार भुगतान ब्रिज द्वारा धनराशि वितरण एवं निस्तारण।',
      stage11Title: 'ऑफलाइन डब्ल्यूएएल रीप्ले एवं एलडब्ल्यूडब्ल्यू विलय',
      stage11Desc: 'सर्वर मोनोटोनिक अनुक्रम और संघर्ष समाधान के साथ बैच सिंक्रोनाइज़ेशन।',
      stage12Title: 'सक्रिय कतार भुखमरी रोकथाम (Anti-Starvation)',
      stage12Desc: 'सत्यापन कि एंटी-स्टारवेशन लैम्ब्डा बोनस अधिकतम प्रतीक्षा से पूर्व कम-प्राथमिकता अनाज को आगे बढ़ाता है।',
      networkFailure: 'नेटवर्क विफलता हुई',
      stageError: 'चरण निष्पादन के दौरान अप्रत्याशित त्रुटि',
      resetFailed: 'रीसेट विफल',
      preflightFailed: 'प्री-फ़्लाइट रीसेट विफल',
      stageFailed: 'चरण विफल',
    },
    ussd: {
      simulatorTitle: 'जीरो-डेटा सेल्युलर सिम्युलेटर',
      simulatorSubtitle: 'जीएसएम मैप लेयर (*247#)',
      activeCallState: 'कॉल सक्रिय',
      standbyState: 'स्टैंडबाय',
      dialPrompt: 'मंडीक्यू फीचर फोन सिम्युलेटर\nजीरो-डेटा सत्र प्रारंभ करने हेतु *247# डायल करें।',
      sessionEnded: 'सत्र समाप्त हुआ।\nप्रारंभ करने हेतु *247# डायल करें।',
      networkTimeout: 'नेटवर्क / मैप सिग्नलिंग टाइमआउट।\nकनेक्टिविटी जांचें।',
      transmittingPacket: 'सिग्नलिंग पैकेट भेजा जा रहा है...',
      inputLabel: 'इनपुट:',
      sendDial: 'डायल करें',
      endCall: 'कॉल समाप्त',
      clearInput: 'साफ़ करें',
      callerLabel: 'कॉलर मोबाइल:',
    },
    walMonitor: {
      bannerTag: 'ऑफलाइन स्टोरेज एवं सिंक स्थिति',
      title: 'क्लाइंट म्यूटेशन लेजर एवं सिंक इंजन',
      description: 'ग्रामीण एपीएमसी में बिजली/इंटरनेट गुल होने पर लोकल-फर्स्ट इंडेक्स-डीबी लेजर उपकरणों पर ACID सुरक्षा बनाए रखता है। पुनः कनेक्ट होने पर म्यूटेशन Gzip-कंप्रेस होकर /api/v1/sync/wal पर अपलोड होते हैं और सर्वर मोनोटोनिक अनुक्रम द्वारा मिलान होते हैं।',
      refreshButton: 'स्थानीय रिकॉर्ड ताज़ा करें',
      syncBatch: 'तुरंत सिंक करें',
      syncingBatch: 'सिंक हो रहा है...',
      tabLedger: 'WAL म्यूटेशन लेजर',
      tabMaterialized: 'मटेरियलाइज्ड क्लाइंट दृश्य',
      filterAll: 'सभी म्यूटेशन',
      filterPending: 'सिंक लंबित',
      filterSynced: 'सिंक पूर्ण',
      filterFailed: 'विफल',
      colMutationId: 'म्यूटेशन आईडी',
      colType: 'म्यूटेशन प्रकार',
      colEntityId: 'संस्था / लेनदेन आईडी',
      colStatus: 'स्थिति',
      colTimestamp: 'दर्ज समय',
      colActions: 'कार्रवाई',
      noRecordsFound: 'कोई राइट-अहेड लॉग म्यूटेशन नहीं मिला।',
      viewPayload: 'पेलोड विवरण देखें',
      modalPayloadTitle: 'WAL म्यूटेशन पेलोड विवरण',
      serverMonotonicSeq: 'सर्वर मोनोटोनिक अनुक्रम',
      statusPending: 'लंबित',
      statusSynced: 'सिंक पूर्ण',
      statusFailed: 'विफल',
      lastSyncResultTitle: 'अंतिम सर्वर सिंक परिणाम',
      mutationsSynced: 'सफलतापूर्वक मिलान म्यूटेशन',
      conflictsResolved: 'सुलझाए गए विवाद',
      errorsEncountered: 'आई हुई त्रुटियां',
      localTransactionsTitle: 'स्थानीय मटेरियलाइज्ड लेनदेन',
      noLocalTransactions: 'ऑफलाइन स्टोर में कोई स्थानीय लेनदेन दर्ज नहीं है।',
      colTxnId: 'लेनदेन संख्या (Txn ID)',
      colFarmerId: 'किसान आईडी',
      colMandiId: 'मंडी आईडी',
      colCurrentState: 'वर्तमान स्थिति',

      totalMutations: 'कुल म्यूटेशन',
      indexedDbWal: 'IndexedDB लेनदेन वाल',
      pendingSync: 'लंबित सिंक',
      queuedReplication: 'सर्वर प्रतिकृति के लिए कतारबद्ध',
      reconciled: 'सुलझाया गया',
      acknowledgedServer: 'सर्वर द्वारा स्वीकृत',
      networkRail: 'नेटवर्क रेल',
      liveCloudLink: 'लाइव क्लाउड लिंक',
      offlineAirGap: 'ऑफलाइन एयर-गैप',
      directRestGzip: 'सीधा REST एवं Gzip WAL',
      indexedDbLocalFallback: 'IndexedDB स्थानीय फ़ॉलबैक',
      generateMutations: 'स्थानीय ऑफलाइन वाल म्यूटेशन उत्पन्न करें',
      generateMutationsSubtitle: 'क्लाउड कनेक्शन के बिना IndexedDB में परीक्षण प्रविष्टियां दर्ज करने के लिए क्लिक करें',
      transactionId: 'लेनदेन आईडी',
      currentState: 'वर्तमान स्थिति',
      farmer: 'किसान',
      mandi: 'मंडी',
      syncStatus: 'सिंक स्थिति',
      lastUpdated: 'अंतिम अपडेट',
      details: 'विवरण',
      payloadInspector: 'वाल पेलोड निरीक्षक',
      mutationUuid: 'म्यूटेशन यूयूआईडी',
      metadataAttributes: 'मेटाडेटा विशेषताएँ',
      stateAttributes: 'स्थिति विशेषताएँ',
      targetState: 'लक्षित स्थिति',
      hmacIntegrity: 'एचएमएसी अखंडता',
      parsedPayload: 'पार्स किया गया पेलोड JSON',
      materializedTransaction: 'सामग्रीकृत लेनदेन',
      aggregatedPayload: 'एकत्रित पेलोड JSON',
      lastMutationId: 'अंतिम म्यूटेशन आईडी',
    },
  },
};
