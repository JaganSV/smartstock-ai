"""Static master data and product construction (fictional entities only; currency INR)."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

import numpy as np

CURRENCY = "INR"
NUM_PRODUCTS = 50
CASE_PACKS = (1, 6, 12, 24)
CREATED_DAYS_BEFORE_AS_OF = 180


@dataclass(frozen=True)
class CategoryRow:
    code: str
    name: str
    description: str


@dataclass(frozen=True)
class SupplierRow:
    code: str
    name: str
    lead_time_days: int
    lead_time_std_days: Decimal
    min_order_qty: int
    reliability_pct: Decimal
    contact_email: str


@dataclass(frozen=True)
class WarehouseRow:
    code: str
    name: str
    city: str
    region: str
    demand_share: float


@dataclass(frozen=True)
class ProductRow:
    number: int  # 1..50
    sku: str
    name: str
    category_code: str
    supplier_code: str
    unit_cost: Decimal
    unit_price: Decimal
    case_pack: int
    created_at: datetime


CATEGORIES = (
    CategoryRow("ELEC", "Electronics Accessories", "Chargers, cables and small accessories"),
    CategoryRow("HOME", "Home & Kitchen", "Kitchenware and household items"),
    CategoryRow("PCARE", "Personal Care", "Grooming and hygiene products"),
    CategoryRow("SPORT", "Sports & Fitness", "Fitness and sports equipment"),
    CategoryRow("STAT", "Stationery & Office", "Office and school stationery"),
)

SUPPLIERS = (
    SupplierRow("SUP-A", "Apex Components Ltd (fictional)", 5, Decimal("1.0"), 24, Decimal("97"),
                "sup-a@example.com"),
    SupplierRow("SUP-B", "Bluehill Distributors (fictional)", 7, Decimal("1.5"), 50, Decimal("95"),
                "sup-b@example.com"),
    SupplierRow("SUP-C", "Cedar Supply Co (fictional)", 10, Decimal("2.0"), 100, Decimal("92"),
                "sup-c@example.com"),
    SupplierRow("SUP-D", "Delta Trade Partners (fictional)", 14, Decimal("3.0"), 36, Decimal("90"),
                "sup-d@example.com"),
    SupplierRow("SUP-E", "Eastwind Imports (fictional)", 21, Decimal("5.0"), 200, Decimal("85"),
                "sup-e@example.com"),
)  # fmt: skip

WAREHOUSES = (
    WarehouseRow("WH-MUM", "Mumbai West DC", "Mumbai", "West", 0.45),
    WarehouseRow("WH-BLR", "Bengaluru South DC", "Bengaluru", "South", 0.35),
    WarehouseRow("WH-DEL", "Delhi NCR DC", "Delhi", "North", 0.20),
)

# Ten generic names per category (no real brands). Product n uses name index (n-1) // 5.
PRODUCT_NAMES: dict[str, tuple[str, ...]] = {
    "ELEC": (
        "USB-C Charging Cable 1m", "Wireless Optical Mouse", "Wireless Earbuds",
        "Power Bank 20000mAh", "Adjustable Phone Stand", "HDMI Cable 2m", "USB Hub 4-Port",
        "Laptop Sleeve 15in", "Screen Cleaning Kit", "Webcam Cover Pack",
    ),
    "HOME": (
        "Steel Water Bottle 750ml", "Non-Stick Frying Pan 24cm", "Glass Storage Jar Set",
        "Silicone Spatula Set", "Ceramic Coffee Mug", "Bamboo Cutting Board",
        "Kitchen Towel Pack", "Insulated Lunch Box", "Steel Colander 26cm", "Cotton Bath Towel",
    ),
    "PCARE": (
        "Herbal Shampoo 250ml", "Moisturising Lotion 200ml", "Bamboo Toothbrush Pack",
        "Sunscreen SPF 50 100ml", "Hand Wash Refill 500ml", "Cordless Beard Trimmer",
        "Face Wash Gel 100ml", "Lip Balm Pack", "Body Soap Bar Pack", "Hair Oil 200ml",
    ),
    "SPORT": (
        "Yoga Mat 6mm", "Adjustable Dumbbell Pair", "Skipping Rope", "Resistance Band Set",
        "Sports Water Jug 2L", "Gym Gloves", "Foam Roller", "Badminton Racket Pair",
        "Running Armband", "Cricket Tennis Ball Pack",
    ),
    "STAT": (
        "A4 Notebook Ruled", "Gel Pen Pack of 10", "Desk Organiser", "Sticky Notes Pack",
        "Stapler Medium", "Whiteboard Marker Set", "Paper Clips Box", "Spiral Diary",
        "Highlighter Set", "File Folder Pack",
    ),
}  # fmt: skip

# unit_cost bands in INR (design assumption: currency is INR).
COST_BANDS: dict[str, tuple[float, float]] = {
    "ELEC": (150.0, 2500.0),
    "HOME": (200.0, 3000.0),
    "PCARE": (80.0, 900.0),
    "SPORT": (250.0, 4000.0),
    "STAT": (20.0, 600.0),
}


def sku_of(number: int) -> str:
    return f"SKU-{number:03d}"


def category_index(number: int) -> int:
    return (number - 1) % 5


def supplier_index(number: int) -> int:
    return ((number - 1) // 5 + (number - 1)) % 5


def _money(value: float) -> Decimal:
    return Decimal(f"{value:.2f}")


def build_products(rng: np.random.Generator, as_of: date) -> tuple[ProductRow, ...]:
    """Draw cost, margin and case pack for all products (three vectorised RNG calls)."""
    cost_u = rng.uniform(size=NUM_PRODUCTS)
    margin = rng.uniform(1.25, 1.80, size=NUM_PRODUCTS)
    pack_idx = rng.integers(0, len(CASE_PACKS), size=NUM_PRODUCTS)
    created_at = datetime.combine(as_of, time(0), tzinfo=UTC) - timedelta(
        days=CREATED_DAYS_BEFORE_AS_OF
    )
    products = []
    for i in range(NUM_PRODUCTS):
        number = i + 1
        category = CATEGORIES[category_index(number)]
        low, high = COST_BANDS[category.code]
        unit_cost = _money(low + float(cost_u[i]) * (high - low))
        unit_price = _money(float(unit_cost) * float(margin[i]))
        products.append(
            ProductRow(
                number=number,
                sku=sku_of(number),
                name=PRODUCT_NAMES[category.code][(number - 1) // 5],
                category_code=category.code,
                supplier_code=SUPPLIERS[supplier_index(number)].code,
                unit_cost=unit_cost,
                unit_price=unit_price,
                case_pack=CASE_PACKS[int(pack_idx[i])],
                created_at=created_at,
            )
        )
    return tuple(products)
