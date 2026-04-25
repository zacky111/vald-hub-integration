TEST_TYPE_METRIC_CATEGORIES = {
    "CMJ": {
        "Output": [
            "JUMP_HEIGHT", #### TO BE DELETED
            "Jump Height (Imp-Mom)",
            "RSI-modified (Imp-Mom)",
            "Peak Power / BM",
            "Vertical Velocity at Takeoff",
            "Force at Peak Power",
        ],

        "Monitoring": [
            "Bodyweight in Kilograms",
            "Flight Time:Contraction Time",
            "Contraction Time",
            "Force at Peak Power",
            "Velocity at Peak Power",
            "Force at Zero Velocity",
            "Concentric Impulse:Eccentric Deceleration Impulse Ratio",
        ],

        "Unweighting": [
            "Eccentric Unloading Impulse",
            "Minimum Eccentric Force",
        ],

        "Landing": [
            "Peak Landing Force",
        ],

        "Eccentric": [
            "Eccentric Peak Velocity",
            "Eccentric Duration",
            "Braking Phase Duration",
            "Eccentric Deceleration Impulse",
            "Eccentric Braking Impulse",
            "Force at Zero Velocity",
            "Minimum Eccentric Force",
            "Eccentric Deceleration Mean Force",
            "Eccentric Deceleration Mean Force / BW",
            "Eccentric Braking RFD",
            "CMJ Stiffness",
        ],

        "Concentric": [
            "Concentric Impulse",
            "P1 Concentric Impulse",
            "P2 Concentric Impulse",
            "Concentric Mean Force",
            "Concentric Peak Force",
        ],

        "Asymmetry": [
            "Eccentric Unloading Impulse - Asym",
            "Eccentric Braking Impulse - Asym",
            "Eccentric Deceleration Impulse - Asym",
            "Concentric Impulse - Asym",
            "P1 Concentric Impulse - Asym",
            "P2 Concentric Impulse - Asym",
            "Force at Zero Velocity - Asym",
            "Landing Impulse - Asym",
        ],
    },

    "SLJ": {
        "Output": [
            "JUMP_HEIGHT", #### TO BE DELETED
            "JUMP_HEIGHT_IMP_MOM",
            "RSI_MODIFIED",
            "BODYMASS_RELATIVE_TAKEOFF_POWER",
            "TAKEOFF_VELOCITY",
            "FORCE_AT_PEAK_POWER"
        ],
        "Monitoring": [
            "BODY_WEIGHT",
            "FLIGHT_CONTRACTION_TIME_RATIO",
            "CONTRACTION_TIME",
            "FORCE_AT_PEAK_POWER",
            "VELOCITY_AT_PEAK_POWER",
            "FORCE_AT_ZERO_VELOCITY",
            "COUNTERMOVEMENT_DEPTH"
        ],
        "Unweighting": [
            "MIN_ECCENTRIC_FORCE"
            ],
        "Landing": [
            "PEAK_LANDING_FORCE",
            "LANDING_IMPULSE"
            ],
        "Eccentric": [
            "ECCENTRIC_PEAK_VELOCITY",
            "ECCENTRIC_TIME",
            "BRAKING_PHASE_DURATION",
            "ECCENTRIC_DECEL_IMPULSE",
            "ECCENTRIC_BRAKING_IMPULSE",
            "FORCE_AT_ZERO_VELOCITY",
            "MEAN_ECCENTRIC_DECELERATION_FORCE",
            "ECCENTRIC_BRAKING_RFD",
            "LOWER_LIMB_STIFFNESS",
            "COUNTERMOVEMENT_DEPTH"
            ],
        "Concentric": [
            "CONCENTRIC_IMPULSE",
            "CONCENTRIC_IMPULSE_P1",
            "CONCENTRIC_IMPULSE_P2",
            "MEAN_TAKEOFF_FORCE",
            "PEAK_CONCENTRIC_FORCE"
        ],
    },


    "All": {
        "Output": [],
        "Monitoring": [],
        "Unweighting": [],
        "Landing": [],
        "Eccentric": [],
        "Concentric": [],
        "Asymmetry": [],
    },
}