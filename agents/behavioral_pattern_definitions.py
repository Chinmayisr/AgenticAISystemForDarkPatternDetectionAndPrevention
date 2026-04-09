BEHAVIORAL_PATTERN_DEFINITIONS = {
    "DP02": {
        "id": "DP02",
        "name": "Basket Sneaking",
        "description": (
            "Items, paid add-ons, or subscriptions are inserted into the cart without "
            "clear, explicit user intent. This often appears through pre-checked paid "
            "boxes or system-added extras during checkout."
        ),
        "behavioral_signals": [
            "New item appears in cart after a non-add-to-cart action",
            "System-added warranty, insurance, or subscription",
            "Paid checkbox starts pre-selected and the user never changed it",
            "Cart total increases because of an unauthorized add-on",
        ],
        "detection_logic": (
            "Compare cart_before vs cart_after for each event. Flag items added without "
            "an explicit matching user add-to-cart action, plus any paid pre-checked boxes."
        ),
        "severity_rules": {
            "high": "Recurring or expensive sneaked item, or multiple unauthorized additions",
            "medium": "At least one unauthorized paid item added",
            "low": "Pre-checked paid add-on present without strong value impact",
        },
    },
    "DP05": {
        "id": "DP05",
        "name": "Subscription Trap",
        "description": (
            "It is easy to subscribe or start a trial, but difficult to cancel. "
            "The cancellation path is longer, buried, or obstructed, and trial-to-paid "
            "conversion may happen without a fair reminder."
        ),
        "behavioral_signals": [
            "Cancellation takes far more steps than signup",
            "Free trial auto-converts without reminder",
            "Retention popups interrupt cancellation",
            "Mandatory survey blocks or delays cancellation",
            "Cancel button is buried in account settings",
        ],
        "detection_logic": (
            "Compare signup flow steps versus cancellation flow steps and inspect "
            "auto-renewal reminder behavior, retention prompts, and cancellation friction."
        ),
        "severity_rules": {
            "high": "Cancellation is at least 2x harder and trial converts without reminder",
            "medium": "Significant cancellation friction or missing reminder",
            "low": "At least one cancellation friction signal is present",
        },
    },
    "DP10": {
        "id": "DP10",
        "name": "Nagging",
        "description": (
            "The interface repeatedly interrupts the user with popups, prompts, or "
            "consent requests after dismissal, creating pressure through repetition."
        ),
        "behavioral_signals": [
            "Same popup reappears after dismissal",
            "Subscription or push prompt appears multiple times in one session",
            "Cookie rejection is ignored and the banner returns",
            "Repeated interruptions across multiple actions",
        ],
        "detection_logic": (
            "Group popup events by popup_id and count reappearances, especially after dismissal "
            "or after the user rejected a consent option."
        ),
        "severity_rules": {
            "high": "Popup repeats 3+ times or reappears after cookie rejection",
            "medium": "Popup repeats after dismissal at least once",
            "low": "Mild repetition without strong obstruction",
        },
    },
    "DP12": {
        "id": "DP12",
        "name": "SaaS Billing",
        "description": (
            "Billing or renewal practices are opaque, unexpectedly hard to manage, "
            "or asymmetric in favor of upgrades over downgrades."
        ),
        "behavioral_signals": [
            "No pre-renewal reminder before auto-charge",
            "Billing settings are buried behind many clicks",
            "Downgrade is much harder than upgrade",
            "Unexpected or unnotified charges occur",
            "Current charges are not clearly visible on the dashboard",
        ],
        "detection_logic": (
            "Inspect renewal reminder behavior, settings accessibility, upgrade/downgrade "
            "friction, and unnotified charges in billing history."
        ),
        "severity_rules": {
            "high": "Unnotified charges or severe downgrade friction",
            "medium": "Missing renewal reminder or materially opaque billing controls",
            "low": "At least one weak billing opacity signal is present",
        },
    },
}
