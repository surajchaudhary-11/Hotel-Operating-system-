from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.config import settings
from app.core.security import get_password_hash
from app.models.models import (
    User, Hotel, HotelMembership, Floor, RoomType, Room,
    AssetCategory, Asset, InventoryTransaction, HousekeepingTask,
    CleaningChecklist, MaintenanceTicket, LaundryVendor, LaundryBatch,
    LaundryItem, Guest, GuestStay, ExpenseCategory, Expense, Revenue, Payment
)

async def seed_initial_data(db: AsyncSession, force: bool = False):
    # Strictly forbid demo seeding in production environments unless explicitly forced
    if settings.ENVIRONMENT.lower() == "production" and not force:
        return

    # In non-production, check ENABLE_DEMO_SEEDING unless forced or running in test environment
    if not settings.ENABLE_DEMO_SEEDING and not force and settings.ENVIRONMENT.lower() != "test":
        return

    # Check if already seeded
    res = await db.execute(select(User).where(User.email == "owner@kashiheritage.com"))
    if res.scalar_one_or_none():
        return # Already seeded

    # 1. Create Default Owner User
    owner = User(
        email="owner@kashiheritage.com",
        full_name="Rajesh Sharma",
        phone_number="+91 98765 43210",
        password_hash=get_password_hash("HotelOS2026!"),
        is_active=True,
        is_platform_admin=False
    )
    db.add(owner)
    await db.flush()

    # 2. Create Hotel (Varanasi property)
    hotel = Hotel(
        name="Kashi Heritage Haveli",
        slug="kashi-heritage-haveli",
        address="D 24/11, Dashashwamedh Ghat Road",
        city="Varanasi",
        state="Uttar Pradesh",
        country="India",
        postal_code="221001",
        phone="+91 542 2450123",
        email="namaste@kashiheritage.com",
        timezone="Asia/Kolkata",
        currency="INR",
        check_in_time="12:00",
        check_out_time="11:00",
        reporting_time="23:59",
        is_active=True
    )
    db.add(hotel)
    await db.flush()

    # 3. Create Hotel Membership
    membership = HotelMembership(
        user_id=owner.id,
        hotel_id=hotel.id,
        role="OWNER",
        is_active=True
    )
    db.add(membership)

    # 4. Create Floors
    floor1 = Floor(hotel_id=hotel.id, floor_number=1, name="Ground Courtyard")
    floor2 = Floor(hotel_id=hotel.id, floor_number=2, name="Ganga View Floor")
    floor3 = Floor(hotel_id=hotel.id, floor_number=3, name="Rooftop Heritage")
    db.add_all([floor1, floor2, floor3])
    await db.flush()

    # 5. Create Room Types
    rt_deluxe = RoomType(
        hotel_id=hotel.id,
        name="Deluxe Heritage Room",
        base_price=Decimal("3500.00"),
        max_capacity=2,
        amenities=["High-Speed WiFi", "Split AC", "King Bed", "Ensuite Bath", "Tea Maker"],
        description="Spacious room with traditional Banarasi wood carvings."
    )
    rt_ganga = RoomType(
        hotel_id=hotel.id,
        name="Executive Ganga View",
        base_price=Decimal("5200.00"),
        max_capacity=2,
        amenities=["Ganga River Balcony", "Smart TV", "Split AC", "King Bed", "Mini Fridge"],
        description="Panoramic views of the Holy Ganges and sunrise ghats."
    )
    rt_suite = RoomType(
        hotel_id=hotel.id,
        name="Royal Maharaja Suite",
        base_price=Decimal("8500.00"),
        max_capacity=4,
        amenities=["Private Terrace", "Living Room", "Jacuzzi", "Smart TV 55-inch", "Butler Service"],
        description="Opulent suite with private courtyard terrace."
    )
    db.add_all([rt_deluxe, rt_ganga, rt_suite])
    await db.flush()

    # 6. Create Rooms
    r101 = Room(hotel_id=hotel.id, floor_id=floor1.id, room_type_id=rt_deluxe.id, room_number="101", status="OCCUPIED")
    r102 = Room(hotel_id=hotel.id, floor_id=floor1.id, room_type_id=rt_deluxe.id, room_number="102", status="VACANT_CLEAN")
    r103 = Room(hotel_id=hotel.id, floor_id=floor1.id, room_type_id=rt_deluxe.id, room_number="103", status="VACANT_DIRTY")
    r201 = Room(hotel_id=hotel.id, floor_id=floor2.id, room_type_id=rt_ganga.id, room_number="201", status="OCCUPIED")
    r202 = Room(hotel_id=hotel.id, floor_id=floor2.id, room_type_id=rt_ganga.id, room_number="202", status="INSPECTION_PENDING")
    r203 = Room(hotel_id=hotel.id, floor_id=floor2.id, room_type_id=rt_ganga.id, room_number="203", status="BLOCKED_MAINTENANCE")
    r301 = Room(hotel_id=hotel.id, floor_id=floor3.id, room_type_id=rt_suite.id, room_number="301", status="VACANT_CLEAN")
    r302 = Room(hotel_id=hotel.id, floor_id=floor3.id, room_type_id=rt_suite.id, room_number="302", status="OCCUPIED")
    db.add_all([r101, r102, r103, r201, r202, r203, r301, r302])
    await db.flush()

    # 7. Asset Categories
    cat_linen = AssetCategory(hotel_id=hotel.id, name="Bed Linens & Bedding", is_linen=True, low_stock_threshold=20)
    cat_towel = AssetCategory(hotel_id=hotel.id, name="Bath & Pool Towels", is_linen=True, low_stock_threshold=15)
    cat_electronics = AssetCategory(hotel_id=hotel.id, name="Appliances & Electronics", is_linen=False, low_stock_threshold=3)
    cat_furniture = AssetCategory(hotel_id=hotel.id, name="Teakwood Furniture", is_linen=False, low_stock_threshold=2)
    db.add_all([cat_linen, cat_towel, cat_electronics, cat_furniture])
    await db.flush()

    # 8. Physical Assets
    tv203 = Asset(
        hotel_id=hotel.id,
        category_id=cat_electronics.id,
        name="Samsung 43-inch 4K Smart TV",
        asset_tag="ELEC-203-TV",
        qr_code_identifier="QR-KH-ELEC-203-TV",
        current_location_type="ROOM",
        current_room_id=r203.id,
        condition="DAMAGED",
        purchase_price=Decimal("28990.00"),
        purchase_date=date(2025, 8, 15)
    )
    ac203 = Asset(
        hotel_id=hotel.id,
        category_id=cat_electronics.id,
        name="Daikin 1.5 Ton Inverter AC",
        asset_tag="ELEC-203-AC",
        qr_code_identifier="QR-KH-ELEC-203-AC",
        current_location_type="ROOM",
        current_room_id=r203.id,
        condition="GOOD",
        purchase_price=Decimal("42500.00"),
        purchase_date=date(2025, 4, 10)
    )
    linen1 = Asset(
        hotel_id=hotel.id,
        category_id=cat_linen.id,
        name="400 TC Egyptian Cotton Bedsheet (White King)",
        asset_tag="LIN-001",
        qr_code_identifier="QR-KH-LIN-001",
        current_location_type="ROOM",
        current_room_id=r101.id,
        condition="GOOD",
        purchase_price=Decimal("1850.00"),
        purchase_date=date(2026, 1, 10)
    )
    towel_missing = Asset(
        hotel_id=hotel.id,
        category_id=cat_towel.id,
        name="Plush Bath Sheet (Turkish Cotton)",
        asset_tag="TWL-089",
        qr_code_identifier="QR-KH-TWL-089",
        current_location_type="STORAGE",
        current_room_id=None,
        condition="MISSING",
        purchase_price=Decimal("750.00"),
        purchase_date=date(2026, 2, 1)
    )
    db.add_all([tv203, ac203, linen1, towel_missing])
    await db.flush()

    # 9. Maintenance Ticket for Room 203
    ticket = MaintenanceTicket(
        hotel_id=hotel.id,
        room_id=r203.id,
        asset_id=tv203.id,
        title="TV Display Screen Flickering / No Signal",
        description="Guest reported that HDMI ports and screen backlight turn off intermittently.",
        priority="HIGH",
        status="REPORTED",
        reported_by_user_id=owner.id,
        estimated_cost=Decimal("2500.00")
    )
    db.add(ticket)

    # 10. Housekeeping Task for Room 103
    hk_task = HousekeepingTask(
        hotel_id=hotel.id,
        room_id=r103.id,
        assigned_to_user_id=owner.id,
        status="PENDING",
        priority="HIGH",
        notes="Guest checked out at 11:00 AM. Deep clean and change all linens."
    )
    db.add(hk_task)
    await db.flush()

    cl1 = CleaningChecklist(task_id=hk_task.id, item_key="Strip soiled bedsheets and pillow covers", is_completed=False)
    cl2 = CleaningChecklist(task_id=hk_task.id, item_key="Sanitize bathroom and replace towels", is_completed=False)
    cl3 = CleaningChecklist(task_id=hk_task.id, item_key="Vacuum floor and dust surfaces", is_completed=False)
    cl4 = CleaningChecklist(task_id=hk_task.id, item_key="Replenish drinking water and tea station", is_completed=False)
    db.add_all([cl1, cl2, cl3, cl4])

    # 11. Guests and Active Stays
    guest1 = Guest(
        hotel_id=hotel.id,
        full_name="Aarav Verma",
        phone="+91 99887 76655",
        email="aarav.verma@example.com",
        nationality="Indian",
        city="Mumbai",
        state="Maharashtra",
        id_type="DRIVING_LICENSE",
        id_number_masked="MH-03-XXXX9876"
    )
    guest2 = Guest(
        hotel_id=hotel.id,
        full_name="Elena Rostova",
        phone="+44 7700 900123",
        email="elena.r@example.co.uk",
        nationality="British",
        id_type="PASSPORT",
        id_number_masked="PA-XXXX765"
    )
    db.add_all([guest1, guest2])
    await db.flush()

    now = datetime.now(timezone.utc)
    stay1 = GuestStay(
        hotel_id=hotel.id,
        guest_id=guest1.id,
        room_id=r101.id,
        check_in_time=now - timedelta(days=1),
        expected_check_out_time=now + timedelta(days=2),
        status="CHECKED_IN",
        adult_count=2,
        child_count=0,
        room_rate_per_night=Decimal("3500.00"),
        total_room_charge=Decimal("7000.00"),
        total_tax_charge=Decimal("840.00"),
        total_paid=Decimal("4000.00"),
        balance_due=Decimal("3840.00")
    )
    stay2 = GuestStay(
        hotel_id=hotel.id,
        guest_id=guest2.id,
        room_id=r201.id,
        check_in_time=now,
        expected_check_out_time=now + timedelta(days=3),
        status="CHECKED_IN",
        adult_count=1,
        child_count=0,
        room_rate_per_night=Decimal("5200.00"),
        total_room_charge=Decimal("5200.00"),
        total_tax_charge=Decimal("624.00"),
        total_paid=Decimal("5824.00"),
        balance_due=Decimal("0.00")
    )
    db.add_all([stay1, stay2])
    await db.flush()

    # 12. Revenues & Payments
    rev1 = Revenue(
        hotel_id=hotel.id,
        stay_id=stay1.id,
        room_id=r101.id,
        revenue_type="ROOM_TARIFF",
        amount=Decimal("3500.00"),
        tax_amount=Decimal("420.00"),
        posting_date=date.today() - timedelta(days=1)
    )
    rev2 = Revenue(
        hotel_id=hotel.id,
        stay_id=stay2.id,
        room_id=r201.id,
        revenue_type="ROOM_TARIFF",
        amount=Decimal("5200.00"),
        tax_amount=Decimal("624.00"),
        posting_date=date.today()
    )
    pay1 = Payment(
        hotel_id=hotel.id,
        stay_id=stay1.id,
        amount=Decimal("4000.00"),
        payment_mode="UPI_QR",
        transaction_reference="UPI/20261029/987654",
        collected_by_user_id=owner.id
    )
    pay2 = Payment(
        hotel_id=hotel.id,
        stay_id=stay2.id,
        amount=Decimal("5824.00"),
        payment_mode="CREDIT_DEBIT_CARD",
        transaction_reference="CARD/AUTH/883491",
        collected_by_user_id=owner.id
    )
    db.add_all([rev1, rev2, pay1, pay2])

    # 13. Expense Categories and Today's Expenses
    cat_elec = ExpenseCategory(hotel_id=hotel.id, name="Electricity & Utilities", is_direct_room_expense=False)
    cat_hk = ExpenseCategory(hotel_id=hotel.id, name="Housekeeping Consumables", is_direct_room_expense=False)
    db.add_all([cat_elec, cat_hk])
    await db.flush()

    exp1 = Expense(
        hotel_id=hotel.id,
        category_id=cat_elec.id,
        amount=Decimal("3200.00"),
        expense_date=date.today(),
        payment_method="NEFT_RTGS",
        description="UPPCL Commercial Power Bill Advance Payment"
    )
    exp2 = Expense(
        hotel_id=hotel.id,
        category_id=cat_hk.id,
        amount=Decimal("1450.00"),
        expense_date=date.today(),
        payment_method="UPI",
        description="Purchased disinfectant liquids, room fresheners, and toiletries"
    )
    db.add_all([exp1, exp2])

    # 14. Laundry Vendor
    laundry_vendor = LaundryVendor(
        hotel_id=hotel.id,
        name="Banaras Steam Laundry & Dry Cleaners",
        contact_person="Manoj Chaurasia",
        phone="+91 94152 33445",
        rate_per_kg=Decimal("45.00"),
        rate_per_piece=Decimal("18.00"),
        is_active=True
    )
    db.add(laundry_vendor)

    await db.commit()

