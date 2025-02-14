S2FrbcDeviceState(systemDescriptions=[class FRBCSystemDescription {
    validFrom: 1970-01-01T02:00+01:00
    actuators: [class FRBCActuatorDescription {
        id: 74d81672-4698-4d92-bc26-12d15369a428
        diagnosticLabel: charge
        supportedCommodities: [ELECTRICITY]
        status: class FRBCActuatorStatus {
            activeOperationModeId: charge.on
            operationModeFactor: 0
            previousOperationModeId: null
            transitionTimestamp: null
        }
        operationModes: [class FRBCOperationMode {
            id: charge.on
            diagnosticLabel: charge.on
            elements: [class FRBCOperationModeElement {
                fillLevelRange: class CommonNumberRange {
                    startOfRange: 0
                    endOfRange: 100
                }
                fillRate: class CommonNumberRange {
                    startOfRange: 0.0054012349
                    endOfRange: 0.0054012349
                }
                powerRanges: [class CommonPowerRange {
                    startOfRange: 28000.0
                    endOfRange: 28000.0
                    commodityQuantity: ELECTRIC.POWER.L1
                }]
                runningCosts: null
            }]
            abnormalConditionOnly: false
        }, class FRBCOperationMode {
            id: charge.off
            diagnosticLabel: charge.off
            elements: [class FRBCOperationModeElement {
                fillLevelRange: class CommonNumberRange {
                    startOfRange: 0
                    endOfRange: 100
                }
                fillRate: class CommonNumberRange {
                    startOfRange: 0
                    endOfRange: 0
                }
                powerRanges: [class CommonPowerRange {
                    startOfRange: 0
                    endOfRange: 0
                    commodityQuantity: ELECTRIC.POWER.L1
                }]
                runningCosts: null
            }]
            abnormalConditionOnly: false
        }]
        transitions: [class CommonTransition {
            id: off.to.on
            from: charge.off
            to: charge.on
            startTimers: [on.to.off.timer]
            blockingTimers: [off.to.on.timer]
            transitionCosts: null
            transitionDuration: null
            abnormalConditionOnly: false
        }, class CommonTransition {
            id: on.to.off
            from: charge.on
            to: charge.off
            startTimers: [off.to.on.timer]
            blockingTimers: [on.to.off.timer]
            transitionCosts: null
            transitionDuration: null
            abnormalConditionOnly: false
        }]
        timers: [class CommonTimer {
            id: on.to.off.timer
            diagnosticLabel: on.to.off.timer
            duration: 30
            finishedAt: -999999999-01-01T00:00+18:00
        }, class CommonTimer {
            id: off.to.on.timer
            diagnosticLabel: off.to.on.timer
            duration: 30
            finishedAt: -999999999-01-01T00:00+18:00
        }]
    }]
    storage: class FRBCStorageDescription {
        diagnosticLabel: battery
        fillLevelLabel: SoC %
        providesLeakageBehaviour: false
        providesFillLevelTargetProfile: true
        providesUsageForecast: false
        fillLevelRange: class CommonNumberRange {
            startOfRange: 0
            endOfRange: 100
        }
        status: class FRBCStorageStatus {
            presentFillLevel: 0.0
        }
        leakageBehaviour: null
    }
}, class FRBCSystemDescription {
    validFrom: 1970-01-01T09:13+01:00
    actuators: [class FRBCActuatorDescription {
        id: e0ddc962-e865-4d85-bff5-17a2c14bcec6
        diagnosticLabel: off
        supportedCommodities: [ELECTRICITY]
        status: class FRBCActuatorStatus {
            activeOperationModeId: off
            operationModeFactor: 0
            previousOperationModeId: null
            transitionTimestamp: null
        }
        operationModes: [class FRBCOperationMode {
            id: off
            diagnosticLabel: off
            elements: [class FRBCOperationModeElement {
                fillLevelRange: class CommonNumberRange {
                    startOfRange: 0
                    endOfRange: 100
                }
                fillRate: class CommonNumberRange {
                    startOfRange: 0
                    endOfRange: 0
                }
                powerRanges: [class CommonPowerRange {
                    startOfRange: 0
                    endOfRange: 0
                    commodityQuantity: ELECTRIC.POWER.L1
                }]
                runningCosts: null
            }]
            abnormalConditionOnly: false
        }]
        transitions: []
        timers: []
    }]
    storage: class FRBCStorageDescription {
        diagnosticLabel: battery
        fillLevelLabel: SoC %
        providesLeakageBehaviour: false
        providesFillLevelTargetProfile: false
        providesUsageForecast: true
        fillLevelRange: class CommonNumberRange {
            startOfRange: 0
            endOfRange: 100
        }
        status: class FRBCStorageStatus {
            presentFillLevel: 100.0
        }
        leakageBehaviour: null
    }
}, class FRBCSystemDescription {
    validFrom: 1970-01-01T13:49+01:00
    actuators: [class FRBCActuatorDescription {
        id: 751551e9-acd0-4ec8-9da8-377f9faa5e36
        diagnosticLabel: charge
        supportedCommodities: [ELECTRICITY]
        status: class FRBCActuatorStatus {
            activeOperationModeId: charge.on
            operationModeFactor: 0
            previousOperationModeId: null
            transitionTimestamp: null
        }
        operationModes: [class FRBCOperationMode {
            id: charge.on
            diagnosticLabel: charge.on
            elements: [class FRBCOperationModeElement {
                fillLevelRange: class CommonNumberRange {
                    startOfRange: 0
                    endOfRange: 100
                }
                fillRate: class CommonNumberRange {
                    startOfRange: 0.01099537114
                    endOfRange: 0.01099537114
                }
                powerRanges: [class CommonPowerRange {
                    startOfRange: 57000.0
                    endOfRange: 57000.0
                    commodityQuantity: ELECTRIC.POWER.L1
                }]
                runningCosts: null
            }]
            abnormalConditionOnly: false
        }, class FRBCOperationMode {
            id: charge.off
            diagnosticLabel: charge.off
            elements: [class FRBCOperationModeElement {
                fillLevelRange: class CommonNumberRange {
                    startOfRange: 0
                    endOfRange: 100
                }
                fillRate: class CommonNumberRange {
                    startOfRange: 0
                    endOfRange: 0
                }
                powerRanges: [class CommonPowerRange {
                    startOfRange: 0
                    endOfRange: 0
                    commodityQuantity: ELECTRIC.POWER.L1
                }]
                runningCosts: null
            }]
            abnormalConditionOnly: false
        }]
        transitions: [class CommonTransition {
            id: off.to.on
            from: charge.off
            to: charge.on
            startTimers: [on.to.off.timer]
            blockingTimers: [off.to.on.timer]
            transitionCosts: null
            transitionDuration: null
            abnormalConditionOnly: false
        }, class CommonTransition {
            id: on.to.off
            from: charge.on
            to: charge.off
            startTimers: [off.to.on.timer]
            blockingTimers: [on.to.off.timer]
            transitionCosts: null
            transitionDuration: null
            abnormalConditionOnly: false
        }]
        timers: [class CommonTimer {
            id: on.to.off.timer
            diagnosticLabel: on.to.off.timer
            duration: 30
            finishedAt: -999999999-01-01T00:00+18:00
        }, class CommonTimer {
            id: off.to.on.timer
            diagnosticLabel: off.to.on.timer
            duration: 30
            finishedAt: -999999999-01-01T00:00+18:00
        }]
    }]
    storage: class FRBCStorageDescription {
        diagnosticLabel: battery
        fillLevelLabel: SoC %
        providesLeakageBehaviour: false
        providesFillLevelTargetProfile: true
        providesUsageForecast: false
        fillLevelRange: class CommonNumberRange {
            startOfRange: 0
            endOfRange: 100
        }
        status: class FRBCStorageStatus {
            presentFillLevel: 37.7463951
        }
        leakageBehaviour: null
    }
}], leakageBehaviours=[class FRBCLeakageBehaviour {
    validFrom: 1970-01-01T02:00+01:00
    elements: [class FRBCLeakageBehaviourElement {
        fillLevelRange: class CommonNumberRange {
            startOfRange: 0
            endOfRange: 100
        }
        leakageRate: 0
    }]
}, class FRBCLeakageBehaviour {
    validFrom: 1970-01-01T13:49+01:00
    elements: [class FRBCLeakageBehaviourElement {
        fillLevelRange: class CommonNumberRange {
            startOfRange: 0
            endOfRange: 100
        }
        leakageRate: 0
    }]
}], usageForecasts=[class FRBCUsageForecast {
    startTime: 1970-01-01T02:00+01:00
    elements: [class FRBCUsageForecastElement {
        duration: 25980
        usageRateUpperLimit: 0
        usageRateUpper95PPR: 0
        usageRateUpper68PPR: 0
        usageRateExpected: 0
        usageRateLower68PPR: 0
        usageRateLower95PPR: 0
        usageRateLowerLimit: 0
    }]
}, class FRBCUsageForecast {
    startTime: 1970-01-01T09:13+01:00
    elements: [class FRBCUsageForecastElement {
        duration: 16560
        usageRateUpperLimit: null
        usageRateUpper95PPR: null
        usageRateUpper68PPR: null
        usageRateExpected: -0.00...