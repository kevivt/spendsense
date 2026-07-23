"""
Hand-labeled evaluation set for extraction accuracy - same practice as
Mail Agent's 20-email hand-labeled eval set. Each entry pairs the
DISTILLED email text (output of ingestion.html_clean.distill_order_text)
with the expected JSON, verified by reading the real email.

To add more examples: run ingestion.fetch_orders.fetch_order_emails to get
real clean_body text, open the original email yourself to verify the true
restaurant/date/items/total, then add an entry here. Aim for 15-20+ for a
meaningful accuracy number - one example is a starting scaffold, not a
finished eval set.
"""

EVAL_SET = [
    {
        "id": "truth_bowl_2026_06_26",
        "distilled_text": (
            "Restaurant: Truth Bowl\n"
            "Order Time: Jun 26, 7:03 PM\n"
            "Delivery Time: Jun 26, 7:42 PM\n"
            "Items:\n"
            "  Paneer Tikka Masala Bowl x1 - ₹329\n"
            "Total Paid: ₹238.00"
        ),
        "reference_year": 2026,
        "expected": {
            "restaurant": "Truth Bowl",
            "order_date": "2026-06-26",
            "total_amount": 238.0,
            "items": [
                {"item_name": "Paneer Tikka Masala Bowl", "quantity": 1, "item_price": 329.0}
            ],
        },
    },
    {
        "id": "dominos_multi_item_2026_03_23",
        "distilled_text": (
            "Restaurant: Domino's Pizza\n"
            "Order Time: Mar 23, 12:14 PM\n"
            "Delivery Time: Mar 25, 4:00 PM\n"
            "Items:\n"
            "  Sourdough Creamy Truffle Mushroom Pizza (Reg) x1 - ₹419\n"
            "  Garlic Breadsticks x1 - ₹129\n"
            "  Cheesy Dip x1 - ₹27.57\n"
            "Total Paid: ₹605.00"
        ),
        "reference_year": 2026,
        "expected": {
            "restaurant": "Domino's Pizza",
            "order_date": "2026-03-23",
            "total_amount": 605.0,
            "items": [
                {"item_name": "Sourdough Creamy Truffle Mushroom Pizza (Reg)", "quantity": 1, "item_price": 419.0},
                {"item_name": "Garlic Breadsticks", "quantity": 1, "item_price": 129.0},
                {"item_name": "Cheesy Dip", "quantity": 1, "item_price": 27.57},
            ],
        },
    },
    {
        # Real order confirming item_price is the LINE TOTAL for the stated
        # quantity, not a per-unit price: 490 (x2) + 359 (x1) = 849, which
        # plus taxes/fees lands close to the 967 total paid. If 490 were
        # per-unit, the item total alone would exceed what was paid.
        "id": "nandhana_palace_quantity_2_2026_04_30",
        "distilled_text": (
            "Restaurant: Nandhana Palace\n"
            "Order Time: Apr 30, 6:32 PM\n"
            "Delivery Time: Apr 30, 7:13 PM\n"
            "Items:\n"
            "  Bowl Supreme Boneless Chicken Biryani x2 - ₹490\n"
            "  Supreme Boneless Chicken Biryani x1 - ₹359\n"
            "Total Paid: ₹967.00"
        ),
        "reference_year": 2026,
        "expected": {
            "restaurant": "Nandhana Palace",
            "order_date": "2026-04-30",
            "total_amount": 967.0,
            "items": [
                {"item_name": "Bowl Supreme Boneless Chicken Biryani", "quantity": 2, "item_price": 490.0},
                {"item_name": "Supreme Boneless Chicken Biryani", "quantity": 1, "item_price": 359.0},
            ],
        },
    },
    {
        "id": "california_burrito_single_item_2026_06_09",
        "distilled_text": (
            "Restaurant: California Burrito\n"
            "Order Time: Jun 9, 7:29 PM\n"
            "Delivery Time: Jun 9, 8:37 PM\n"
            "Items:\n"
            "  Peri Peri Potato Rice Bowl (Mini) x1 - ₹235\n"
            "Total Paid: ₹186.00"
        ),
        "reference_year": 2026,
        "expected": {
            "restaurant": "California Burrito",
            "order_date": "2026-06-09",
            "total_amount": 186.0,
            "items": [
                {"item_name": "Peri Peri Potato Rice Bowl (Mini)", "quantity": 1, "item_price": 235.0}
            ],
        },
    },
    {
        "id": "paris_panini_two_items_2026_05_03",
        "distilled_text": (
            "Restaurant: Paris Panini - Gourmet Sandwiches & Wraps\n"
            "Order Time: May 3, 12:43 PM\n"
            "Delivery Time: May 3, 1:29 PM\n"
            "Items:\n"
            "  Michel (Chicken & Mozza Sandwich) x1 - ₹255\n"
            "  Hugo (Fried Chicken & Mozza Sandwich) x1 - ₹435\n"
            "Total Paid: ₹692.00"
        ),
        "reference_year": 2026,
        "expected": {
            "restaurant": "Paris Panini - Gourmet Sandwiches & Wraps",
            "order_date": "2026-05-03",
            "total_amount": 692.0,
            "items": [
                {"item_name": "Michel (Chicken & Mozza Sandwich)", "quantity": 1, "item_price": 255.0},
                {"item_name": "Hugo (Fried Chicken & Mozza Sandwich)", "quantity": 1, "item_price": 435.0},
            ],
        },
    },
]
