# agents/pricing_pattern_definitions.py

PRICING_PATTERN_DEFINITIONS = {

    "DP07": {
        "id":   "DP07",
        "name": "Bait and Switch",
        "description": (
            "The price shown on the product page or early in the funnel is "
            "significantly lower than the final price at checkout. The item "
            "price itself changes — not through disclosed fees but through "
            "unexplained item price inflation between funnel stages. "
            "Threshold: item price increase of more than 5% between any two stages."
        ),
        "detection_signals": [
            "Item unit price is higher at checkout than on the product page",
            "Product price increases after being added to cart",
            "Advertised price does not match the price in order summary",
            "Price changes after applying a coupon or discount code",
            "Item price in cart differs from item price at payment stage",
            "Checkout total is higher than cart total for same items at same quantity",
        ],
        "calculation": (
            "Compare item prices at each stage. "
            "If (checkout_item_price - product_page_item_price) / product_page_item_price > 0.05, "
            "flag as Bait and Switch."
        ),
        "examples": [
            "Product page: ₹24,990 → Checkout: ₹27,489 (10% increase on item price)",
            "Cart shows $29.99 → Payment page shows $34.99 for same item",
            "Advertised sale price ₹999 → Order summary shows ₹1,299",
        ]
    },

    "DP08": {
        "id":   "DP08",
        "name": "Drip Pricing",
        "description": (
            "Hidden fees that are only revealed at the checkout or payment stage, "
            "after the user has already committed time and intent to purchase. "
            "The item prices remain the same, but mandatory fees are injected "
            "late in the funnel that significantly inflate the final total. "
            "These fees were not shown or estimable at the product page stage."
        ),
        "detection_signals": [
            "New fee line items appearing for the first time at checkout",
            "Service fee, convenience fee, or platform fee not shown on product page",
            "Delivery fee hidden until the final checkout step",
            "Surcharges (rain, peak, night) appearing only at payment",
            "Tax amount significantly higher than expected and shown only at checkout",
            "Fees that together exceed 10% of the item subtotal",
            "Number of fee line items increases between cart and checkout",
        ],
        "calculation": (
            "Compare fees_shown at product_page vs checkout. "
            "Any fee appearing at checkout that was absent at product_page is a drip fee. "
            "If total drip fees / item_subtotal > 0.10, severity is HIGH. "
            "If between 0.05 and 0.10, severity is MEDIUM."
        ),
        "examples": [
            "Product page: ₹398 total → Checkout: ₹489 (₹91 in hidden fees added)",
            "Cart shows $45 → Payment shows $45 + $8.99 service fee + $3.50 convenience fee",
            "Booking site: ₹2,000/night → Final: ₹2,000 + ₹400 resort fee + ₹180 tax",
        ]
    }
}