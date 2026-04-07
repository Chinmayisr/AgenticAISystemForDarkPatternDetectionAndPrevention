# agents/pattern_definitions.py
# Single source of truth for all NLP-detectable dark pattern definitions.
# The NLP agent loads this to build its system prompt and few-shot examples.

PATTERN_DEFINITIONS = {

    "DP01": {
        "id":          "DP01",
        "name":        "False Urgency",
        "description": (
            "Creating artificial time pressure or fake scarcity to force faster decisions. "
            "The urgency is manufactured — stock levels, viewer counts, and countdown timers "
            "are either fake or reset frequently."
        ),
        "signals": [
            "Countdown timers on products that are always in stock",
            "Phrases like 'Only X left' when stock is abundant",
            "Real-time viewer counts ('17 people viewing now')",
            "Flash sale timers that reset when they expire",
            "Urgency language: hurry, act now, limited time, selling fast",
            "Lightning deal or deal-of-the-day formatting",
        ],
        "examples": [
            "Only 3 left in stock – order soon!",
            "17 people are viewing this right now",
            "Deal ends in: 02:34:18",
            "🔥 Selling fast! Only 2 remaining",
            "Last chance! Sale ends tonight",
            "⚡ Flash Sale – 89% claimed",
        ],
        "false_positives": [
            "Concert tickets with genuine limited seats",
            "Actual limited edition product runs",
        ]
    },

    "DP03": {
        "id":          "DP03",
        "name":        "Confirm Shaming",
        "description": (
            "Using guilt-inducing, shame-based, or emotionally manipulative language "
            "on the opt-out or decline button/link, making users feel bad for not accepting "
            "an offer. The decline option is worded to shame rather than neutrally decline."
        ),
        "signals": [
            "Opt-out button uses self-deprecating language",
            "Decline option implies the user is making a poor financial decision",
            "Phrases like 'No thanks, I hate...' or 'No, I don't want free...'",
            "Contrast between enthusiastic accept text and shame-filled decline text",
            "Negative consequences implied in the opt-out choice",
        ],
        "examples": [
            "No thanks, I don't want to save ₹5,000",
            "No, I hate free shipping",
            "I prefer paying full price",
            "No thanks, I don't need protection",
            "Skip – I don't want exclusive deals",
            "No, I'll take my chances without insurance",
        ],
        "false_positives": [
            "Humor-based copy that is clearly playful and not manipulative",
            "User preference confirmations with neutral language",
        ]
    },

    "DP04": {
        "id":          "DP04",
        "name":        "Forced Action",
        "description": (
            "Forcing users to take actions they did not intend or want to take as a "
            "precondition for accessing a service or completing a task. This includes "
            "mandatory account creation, forced social sharing, required app downloads, "
            "or unnecessary form fields."
        ),
        "signals": [
            "Must create account to proceed / see price / checkout",
            "Share with N friends to unlock content or discounts",
            "Must download app to access something available on web",
            "Required phone number or personal info not needed for transaction",
            "Forced newsletter signup before accessing content",
            "Mandatory survey or feedback before proceeding",
        ],
        "examples": [
            "Share with 3 friends to unlock this price",
            "You must create an account to continue",
            "Download our app to see this offer",
            "Enter your phone number to view pricing",
            "Complete your profile to checkout",
            "Sign up to see the full article",
        ],
        "false_positives": [
            "Login required for genuinely personalized content",
            "Age verification for age-restricted products",
        ]
    },

    "DP11": {
        "id":          "DP11",
        "name":        "Trick Question",
        "description": (
            "Using confusing, double-negative, or deliberately ambiguous language in "
            "checkboxes, consent forms, or option labels so that users cannot easily "
            "determine what they are actually agreeing to or opting into. The phrasing "
            "is designed to cause users to make choices opposite to their actual preferences."
        ),
        "signals": [
            "Double negatives in checkbox labels",
            "Opt-out phrased as opt-in or vice versa",
            "Confusing 'Uncheck to not receive' phrasing",
            "Pre-checked boxes with misleading labels",
            "Ambiguous checkbox where both checked and unchecked mean consent",
            "Nested negations that are hard to parse",
        ],
        "examples": [
            "Uncheck this box if you do not wish to NOT receive promotional emails",
            "Deselect to not opt-out of marketing",
            "Check here to prevent us from not sharing your data",
            "Untick if you don't want to unsubscribe",
            "Leave unchecked to opt out of not receiving newsletters",
        ],
        "false_positives": [
            "Clear, single-negative opt-out: 'Uncheck to stop emails'",
            "Straightforward consent checkboxes",
        ]
    },

    "DP09": {
        "id":          "DP09",
        "name":        "Disguised Ads",
        "description": (
            "Advertisements or paid sponsored content designed to look like organic, "
            "editorial, or non-commercial content. The paid nature is hidden, obscured, "
            "or presented in a way that a reasonable user would not recognize it as advertising."
        ),
        "signals": [
            "Sponsored content mixed with organic results without clear labeling",
            "'Recommended for you' or 'Top picks' sections that are fully paid placements",
            "Tiny, faded, or absent 'Sponsored' / 'Ad' labels",
            "Native ads styled identically to editorial content",
            "Affiliate product listings presented as editorial recommendations",
            "Paid search results without clear distinguishing markers",
        ],
        "examples": [
            "RECOMMENDED FOR YOU [all items are paid placements with no disclosure]",
            "[Sponsored] label in tiny grey text nearly invisible",
            "TOP PICKS [looks editorial but all links are paid]",
            "Editorial-style headline linking to advertiser product",
            "Search results where paid listings look identical to organic",
        ],
        "false_positives": [
            "Clearly labeled 'Advertisement' or 'Sponsored' in visible formatting",
            "Native ads with prominent disclosure",
        ]
    },
}