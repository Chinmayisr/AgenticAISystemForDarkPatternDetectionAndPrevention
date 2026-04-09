# agents/visual_pattern_definitions.py

VISUAL_PATTERN_DEFINITIONS = {

    "DP09": {
        "id":   "DP09",
        "name": "Disguised Ads",
        "description": (
            "Advertisements or paid/sponsored content intentionally designed "
            "to look like organic, editorial, or non-commercial content. "
            "The paid nature is hidden, absent, or presented so subtly that "
            "a normal user would not recognize it as advertising."
        ),
        "visual_signals": [
            "Sponsored or Ad label present but in very small, faded, or low-contrast text",
            "Ad container styled identically to organic product listings or articles",
            "Paid placement section labeled 'Recommended', 'Top Picks', 'You May Also Like' without disclosure",
            "Native ad with same font, card size, image style as surrounding organic content",
            "Banner ad disguised to look like a site notification or system alert",
            "Search results where paid listings have no visual distinction from organic results",
            "Affiliate product listed as 'Editor's Choice' or 'Best Pick' without disclosure",
            "'Download' or 'Play' button that is actually an ad, not a real action button",
        ],
        "what_to_look_for": [
            "Look for 'Sponsored', 'Ad', 'Promoted', 'Paid' labels — check their size, color, contrast",
            "Compare ad cards to organic content cards — are they visually identical?",
            "Check if 'Recommended' or 'Top Picks' sections have any disclosure",
            "Look for content that mimics news articles, reviews, or editorial content but links to products",
            "Check if download or action buttons look like real OS/browser dialogs but are ads",
        ],
        "examples_description": [
            "Amazon search results: 'Sponsored' label in light grey tiny text above paid listing",
            "Google search: ads styled exactly like organic results, only 'Ad' badge distinguishes",
            "News site: 'Recommended Content' section with no disclosure that it's paid",
            "Fake 'Download Now' button styled as OS dialog — actually an ad",
            "YouTube-style 'Play' button overlay on an image that opens an ad",
        ]
    },

    "DP06": {
        "id":   "DP06",
        "name": "Interface Interference",
        "description": (
            "UI elements deliberately designed to mislead users into making unintended "
            "choices. This includes pre-checked boxes, deceptive button styling, "
            "intentionally hidden or tiny close/decline buttons, misleading color choices "
            "that make the 'wrong' option look like the 'right' one, and important "
            "information hidden through tiny fonts or poor contrast."
        ),
        "visual_signals": [
            "Checkbox pre-checked by default for something user likely doesn't want",
            "Close (X) button extremely small, low contrast, or positioned off-screen",
            "Decline/cancel button styled as plain text link while accept is a prominent button",
            "Accept button colored green/blue (positive), decline button colored grey/faded",
            "Important opt-out text in tiny font below a large colorful CTA",
            "Confirm button positioned where cancel button is typically expected",
            "Visual hierarchy that draws eye to accept/buy while hiding alternatives",
            "Cookie banner where 'Accept All' is large and prominent, 'Reject' is hidden",
            "Modal that is very hard to dismiss — no obvious close button",
            "Radio button pre-selected on the most expensive option",
        ],
        "what_to_look_for": [
            "Check every visible checkbox — is it pre-checked? What does checking it do?",
            "Look for the close/X button — how big is it? What is its contrast ratio?",
            "Compare the visual weight of Accept vs Decline options",
            "Check if positive and negative CTAs are styled differently to favor one",
            "Look for any tiny text near buttons that changes what the button actually does",
            "Check if modals, popups, or cookie banners make rejection harder than acceptance",
        ],
        "examples_description": [
            "Checkout page: 'Add travel insurance $4.99' checkbox pre-ticked",
            "Newsletter popup: 'Accept' is large blue button, 'No thanks' is tiny grey text",
            "Cookie consent: 'Accept All' prominent, settings/reject buried in small link",
            "Radio buttons for subscription plan: most expensive pre-selected",
            "Modal with no visible X button — only way out is to accept",
            "Button layout: 'Confirm Purchase' where you'd expect 'Back', 'Back' where you'd expect cancel",
        ]
    },

    "DP13": {
        "id":   "DP13",
        "name": "Rogue / Malicious Patterns",
        "description": (
            "Deceptive UI elements designed to trick users into downloading malware, "
            "clicking on malicious links, or performing actions that harm their device "
            "or security. These patterns impersonate legitimate OS dialogs, download "
            "buttons, browser alerts, or system notifications."
        ),
        "visual_signals": [
            "Multiple fake 'Download' buttons where only one (hard to find) is real",
            "Large green/orange 'Download Now' button that is actually an ad or malware",
            "Fake browser alert or system dialog with 'Your computer has a virus' message",
            "Fake Windows/Mac update dialog on a website",
            "Fake CAPTCHA that leads to malware download",
            "Fake 'Play' button on video that triggers ad or download",
            "Popup claiming prizes, lottery wins, or rewards",
            "Fake 'Adobe Flash Player required' or plugin update prompts",
            "Clickjacking overlay — transparent element placed over a real button",
            "Fake security scanner showing 'threats found' to scare user",
        ],
        "what_to_look_for": [
            "Count download buttons — if there are 3+, most are likely fake/malicious",
            "Check if download button styling matches the rest of the site or looks foreign",
            "Look for dialog boxes styled to look like OS native windows",
            "Check for virus/threat warnings on non-security websites",
            "Look for 'Your computer is at risk' or 'You have won' style messages",
            "Identify buttons that look like real UI actions but are positioned deceptively",
            "Check for blurred/overlay content requiring a click to 'reveal'",
        ],
        "examples_description": [
            "Software download site with 3 green buttons — only middle one is real download",
            "Pop-up styled as Windows Security Center warning about viruses",
            "Fake Adobe Flash update dialog with 'Install Now' button",
            "Video page where fake Play button opens ad instead of video",
            "Webpage with 'You are the 1,000,000th visitor! Claim prize' overlay",
        ]
    }
}