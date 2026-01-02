from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime, timedelta
import random
import string
import os
import asyncio

# For Vercel, we need to handle MongoDB connection differently
# Use environment variables for MongoDB URI
MONGODB_URI = os.environ.get("MONGODB_URI", "mongodb+srv://wisdomkagyan_db_user:gqbCoXr99sKOcXEw@cluster0.itxqujm.mongodb.net/?appName=Cluster0&retryWrites=true&w=majority")

# Import MongoDB drivers conditionally
try:
    from motor.motor_asyncio import AsyncIOMotorClient
    from bson import ObjectId
    from pydantic import Field, ConfigDict
    from pydantic.functional_validators import field_validator
    import bcrypt
    MONGODB_AVAILABLE = True
except ImportError:
    print("MongoDB dependencies not installed. Using in-memory storage.")
    MONGODB_AVAILABLE = False

app = FastAPI(title="Smart Parking API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- IN-MEMORY STORAGE (Fallback when MongoDB is not available) ----------
if not MONGODB_AVAILABLE:
    users = []
    vehicles = []
    wallets = []
    bookings = []
    slots = []
    
    userIdCounter = 1
    vehicleIdCounter = 1
    bookingIdCounter = 1
    slotIdCounter = 1
    
    RATES = {"2W": 50, "4W": 100}
    
    # Helper functions for in-memory storage
    def init_slots_in_memory():
        global slots, slotIdCounter
        config = [
            {"area": "A", "prefix": "A", "count": 5, "vehicle_type_allowed": "4W"},
            {"area": "B", "prefix": "B", "count": 5, "vehicle_type_allowed": "4W"},
            {"area": "C", "prefix": "C", "count": 5, "vehicle_type_allowed": "2W"},
            {"area": "D", "prefix": "D", "count": 5, "vehicle_type_allowed": "2W"}
        ]
        
        for cfg in config:
            for i in range(1, cfg["count"] + 1):
                slots.append({
                    "id": slotIdCounter,
                    "area": cfg["area"],
                    "slot_code": f"{cfg['prefix']}{i}",
                    "vehicle_type_allowed": cfg["vehicle_type_allowed"],
                    "status": "FREE"
                })
                slotIdCounter += 1
    
    def generate_booking_token():
        random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        timestamp_part = datetime.now().strftime("%y%m%d%H%M%S")
        return f"BK-{random_part}-{timestamp_part}"
    
    def find_wallet(user_id):
        for wallet in wallets:
            if wallet.get("user_id") == user_id:
                return wallet
        return None
    
    # Initialize in-memory slots
    init_slots_in_memory()

# ---------- MONGODB SETUP ----------
else:
    # MongoDB connection with error handling
    client = None
    db = None
    
    try:
        client = AsyncIOMotorClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
        db = client.smart_parking
        
        # Test connection
        async def test_connection():
            try:
                await client.admin.command('ping')
                print("✅ MongoDB connected successfully")
                return True
            except Exception as e:
                print(f"❌ MongoDB connection failed: {e}")
                return False
        
        # Run connection test
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        connected = loop.run_until_complete(test_connection())
        loop.close()
        
        if not connected:
            print("⚠️ MongoDB not available, falling back to in-memory storage")
            MONGODB_AVAILABLE = False
            # Initialize in-memory storage
            users = []
            vehicles = []
            wallets = []
            bookings = []
            slots = []
            userIdCounter = 1
            vehicleIdCounter = 1
            bookingIdCounter = 1
            slotIdCounter = 1
            RATES = {"2W": 50, "4W": 100}
            
            def init_slots_in_memory():
                global slots, slotIdCounter
                config = [
                    {"area": "A", "prefix": "A", "count": 5, "vehicle_type_allowed": "4W"},
                    {"area": "B", "prefix": "B", "count": 5, "vehicle_type_allowed": "4W"},
                    {"area": "C", "prefix": "C", "count": 5, "vehicle_type_allowed": "2W"},
                    {"area": "D", "prefix": "D", "count": 5, "vehicle_type_allowed": "2W"}
                ]
                
                for cfg in config:
                    for i in range(1, cfg["count"] + 1):
                        slots.append({
                            "id": slotIdCounter,
                            "area": cfg["area"],
                            "slot_code": f"{cfg['prefix']}{i}",
                            "vehicle_type_allowed": cfg["vehicle_type_allowed"],
                            "status": "FREE"
                        })
                        slotIdCounter += 1
            
            def generate_booking_token():
                random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
                timestamp_part = datetime.now().strftime("%y%m%d%H%M%S")
                return f"BK-{random_part}-{timestamp_part}"
            
            def find_wallet(user_id):
                for wallet in wallets:
                    if wallet.get("user_id") == user_id:
                        return wallet
                return None
            
            init_slots_in_memory()
            
        else:
            # MongoDB is available, set up collections
            users_collection = db.users
            vehicles_collection = db.vehicles
            wallets_collection = db.wallets
            bookings_collection = db.bookings
            slots_collection = db.slots
            
            # Helper functions for MongoDB
            def hash_password(password: str) -> str:
                salt = bcrypt.gensalt()
                hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
                return hashed.decode('utf-8')
            
            def verify_password(plain_password: str, hashed_password: str) -> bool:
                return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
            
            def generate_booking_token():
                random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
                timestamp_part = datetime.now().strftime("%y%m%d%H%M%S")
                return f"BK-{random_part}-{timestamp_part}"
            
            RATES = {"2W": 50, "4W": 100}
            
    except Exception as e:
        print(f"❌ MongoDB initialization error: {e}")
        MONGODB_AVAILABLE = False
        # Fallback to in-memory storage
        users = []
        vehicles = []
        wallets = []
        bookings = []
        slots = []
        userIdCounter = 1
        vehicleIdCounter = 1
        bookingIdCounter = 1
        slotIdCounter = 1
        RATES = {"2W": 50, "4W": 100}
        
        def init_slots_in_memory():
            global slots, slotIdCounter
            config = [
                {"area": "A", "prefix": "A", "count": 5, "vehicle_type_allowed": "4W"},
                {"area": "B", "prefix": "B", "count": 5, "vehicle_type_allowed": "4W"},
                {"area": "C", "prefix": "C", "count": 5, "vehicle_type_allowed": "2W"},
                {"area": "D", "prefix": "D", "count": 5, "vehicle_type_allowed": "2W"}
            ]
            
            for cfg in config:
                for i in range(1, cfg["count"] + 1):
                    slots.append({
                        "id": slotIdCounter,
                        "area": cfg["area"],
                        "slot_code": f"{cfg['prefix']}{i}",
                        "vehicle_type_allowed": cfg["vehicle_type_allowed"],
                        "status": "FREE"
                    })
                    slotIdCounter += 1
        
        def generate_booking_token():
            random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            timestamp_part = datetime.now().strftime("%y%m%d%H%M%S")
            return f"BK-{random_part}-{timestamp_part}"
        
        def find_wallet(user_id):
            for wallet in wallets:
                if wallet.get("user_id") == user_id:
                    return wallet
            return None
        
        init_slots_in_memory()

# ---------- PYDANTIC MODELS ----------
class UserCreate(BaseModel):
    name: str
    mobile: str
    email: EmailStr
    password: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class VehicleCreate(BaseModel):
    user_id: str
    vehicle_number: str
    vehicle_type: str

class WalletRecharge(BaseModel):
    user_id: str
    amount: float

class BookingCreate(BaseModel):
    user_id: str
    vehicle_id: str
    duration_hours: int

class QRValidate(BaseModel):
    booking_token: str

# ---------- API ROUTES ----------
@app.get("/")
async def root():
    return {
        "message": "Smart Parking API",
        "status": "running",
        "database": "MongoDB" if MONGODB_AVAILABLE else "In-Memory"
    }

@app.get("/api/health")
async def health_check():
    return {"success": True, "message": "Smart Parking API running"}

@app.post("/api/register")
async def register(user_data: UserCreate):
    """Register a new user"""
    if MONGODB_AVAILABLE:
        try:
            # Check if user exists
            existing = await users_collection.find_one({"email": user_data.email.lower()})
            if existing:
                raise HTTPException(
                    status_code=400,
                    detail="Email already registered"
                )
            
            # Create user
            user_doc = {
                "name": user_data.name,
                "mobile": user_data.mobile,
                "email": user_data.email.lower(),
                "password_hash": hash_password(user_data.password),
                "created_at": datetime.now()
            }
            
            result = await users_collection.insert_one(user_doc)
            user_id = str(result.inserted_id)
            
            # Create wallet
            await wallets_collection.insert_one({
                "user_id": user_id,
                "balance": 0.0
            })
            
            return {
                "success": True,
                "message": "User registered successfully",
                "user_id": user_id,
                "name": user_data.name
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    else:
        # In-memory implementation
        global users, wallets, userIdCounter
        
        # Check if email exists
        for user in users:
            if user.get("email", "").lower() == user_data.email.lower():
                raise HTTPException(status_code=400, detail="Email already registered")
        
        # Create user
        new_user = {
            "id": userIdCounter,
            "name": user_data.name,
            "mobile": user_data.mobile,
            "email": user_data.email.lower(),
            "password": user_data.password,  # In production, hash this
            "created_at": datetime.now().isoformat()
        }
        users.append(new_user)
        
        # Create wallet
        wallets.append({
            "user_id": str(userIdCounter),
            "balance": 0.0
        })
        
        user_id = str(userIdCounter)
        userIdCounter += 1
        
        return {
            "success": True,
            "message": "User registered successfully",
            "user_id": user_id,
            "name": user_data.name
        }

@app.post("/api/login")
async def login(login_data: LoginRequest):
    """Login user"""
    if MONGODB_AVAILABLE:
        try:
            user = await users_collection.find_one({"email": login_data.email.lower()})
            
            if not user or not verify_password(login_data.password, user["password_hash"]):
                raise HTTPException(status_code=401, detail="Invalid credentials")
            
            return {
                "success": True,
                "message": "Login successful",
                "user_id": str(user["_id"]),
                "name": user["name"]
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    else:
        # In-memory implementation
        for user in users:
            if user.get("email", "").lower() == login_data.email.lower():
                # Simple password check (in production, use hashing)
                if user.get("password") == login_data.password:
                    return {
                        "success": True,
                        "message": "Login successful",
                        "user_id": str(user["id"]),
                        "name": user["name"]
                    }
        
        raise HTTPException(status_code=401, detail="Invalid credentials")

@app.get("/api/wallet/{user_id}")
async def get_wallet(user_id: str):
    """Get user wallet"""
    if MONGODB_AVAILABLE:
        try:
            wallet = await wallets_collection.find_one({"user_id": user_id})
            if not wallet:
                raise HTTPException(status_code=404, detail="Wallet not found")
            
            wallet["_id"] = str(wallet["_id"])
            return {"success": True, "wallet": wallet}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    else:
        wallet = find_wallet(user_id)
        if not wallet:
            raise HTTPException(status_code=404, detail="Wallet not found")
        
        return {"success": True, "wallet": wallet}

@app.post("/api/wallet/recharge")
async def recharge_wallet(recharge_data: WalletRecharge):
    """Recharge user wallet"""
    if MONGODB_AVAILABLE:
        try:
            if recharge_data.amount <= 0:
                raise HTTPException(status_code=400, detail="Amount must be positive")
            
            result = await wallets_collection.update_one(
                {"user_id": recharge_data.user_id},
                {"$inc": {"balance": recharge_data.amount}}
            )
            
            if result.matched_count == 0:
                raise HTTPException(status_code=404, detail="Wallet not found")
            
            wallet = await wallets_collection.find_one({"user_id": recharge_data.user_id})
            wallet["_id"] = str(wallet["_id"])
            
            return {"success": True, "wallet": wallet}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    else:
        wallet = find_wallet(recharge_data.user_id)
        if not wallet:
            raise HTTPException(status_code=404, detail="Wallet not found")
        
        if recharge_data.amount <= 0:
            raise HTTPException(status_code=400, detail="Amount must be positive")
        
        wallet["balance"] += recharge_data.amount
        return {"success": True, "wallet": wallet}

@app.post("/api/vehicles")
async def add_vehicle(vehicle_data: VehicleCreate):
    """Add a vehicle for user"""
    if MONGODB_AVAILABLE:
        try:
            # Check if user exists
            try:
                user_id_obj = ObjectId(vehicle_data.user_id)
            except:
                raise HTTPException(status_code=400, detail="Invalid user ID format")
            
            user = await users_collection.find_one({"_id": user_id_obj})
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            
            # Add vehicle
            vehicle_doc = {
                "user_id": vehicle_data.user_id,
                "vehicle_number": vehicle_data.vehicle_number,
                "vehicle_type": vehicle_data.vehicle_type
            }
            
            result = await vehicles_collection.insert_one(vehicle_doc)
            
            return {
                "success": True,
                "message": "Vehicle added",
                "vehicle": {
                    "id": str(result.inserted_id),
                    "user_id": vehicle_data.user_id,
                    "vehicle_number": vehicle_data.vehicle_number,
                    "vehicle_type": vehicle_data.vehicle_type
                }
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    else:
        global vehicles, vehicleIdCounter
        
        # Check if user exists
        user_exists = False
        for user in users:
            if str(user.get("id")) == vehicle_data.user_id:
                user_exists = True
                break
        
        if not user_exists:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Add vehicle
        new_vehicle = {
            "id": vehicleIdCounter,
            "user_id": vehicle_data.user_id,
            "vehicle_number": vehicle_data.vehicle_number,
            "vehicle_type": vehicle_data.vehicle_type
        }
        vehicles.append(new_vehicle)
        
        vehicleIdCounter += 1
        
        return {
            "success": True,
            "message": "Vehicle added",
            "vehicle": new_vehicle
        }

@app.get("/api/vehicles/{user_id}")
async def get_user_vehicles(user_id: str):
    """Get all vehicles for a user"""
    if MONGODB_AVAILABLE:
        try:
            vehicles_list = await vehicles_collection.find({"user_id": user_id}).to_list(1000)
            
            for vehicle in vehicles_list:
                vehicle["_id"] = str(vehicle["_id"])
            
            return {"success": True, "vehicles": vehicles_list}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    else:
        user_vehicles = [v for v in vehicles if v.get("user_id") == user_id]
        return {"success": True, "vehicles": user_vehicles}

@app.post("/api/bookings/create")
async def create_booking(booking_data: BookingCreate):
    """Create a new booking"""
    if MONGODB_AVAILABLE:
        try:
            # Validate user
            try:
                user_id_obj = ObjectId(booking_data.user_id)
                vehicle_id_obj = ObjectId(booking_data.vehicle_id)
            except:
                raise HTTPException(status_code=400, detail="Invalid ID format")
            
            user = await users_collection.find_one({"_id": user_id_obj})
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            
            # Validate vehicle
            vehicle = await vehicles_collection.find_one({
                "_id": vehicle_id_obj,
                "user_id": booking_data.user_id
            })
            if not vehicle:
                raise HTTPException(status_code=404, detail="Vehicle not found")
            
            # Get wallet
            wallet = await wallets_collection.find_one({"user_id": booking_data.user_id})
            if not wallet:
                raise HTTPException(status_code=404, detail="Wallet not found")
            
            # Calculate amount
            rate = RATES.get(vehicle["vehicle_type"])
            if not rate:
                raise HTTPException(status_code=400, detail="Invalid vehicle type")
            
            amount = rate * booking_data.duration_hours
            
            # Check balance
            if wallet["balance"] < amount:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "message": "Insufficient wallet balance",
                        "required_amount": amount,
                        "current_balance": wallet["balance"]
                    }
                )
            
            # Find available slot
            available_slot = await slots_collection.find_one({
                "vehicle_type_allowed": vehicle["vehicle_type"],
                "status": "FREE"
            })
            
            if not available_slot:
                raise HTTPException(
                    status_code=400,
                    detail="No free slots available for this vehicle type"
                )
            
            # Update wallet
            await wallets_collection.update_one(
                {"user_id": booking_data.user_id},
                {"$inc": {"balance": -amount}}
            )
            
            # Update slot
            await slots_collection.update_one(
                {"_id": available_slot["_id"]},
                {"$set": {"status": "RESERVED"}}
            )
            
            # Create booking
            now = datetime.now()
            end_time = now + timedelta(hours=booking_data.duration_hours)
            booking_token = generate_booking_token()
            
            booking_doc = {
                "booking_token": booking_token,
                "user_id": booking_data.user_id,
                "vehicle_id": booking_data.vehicle_id,
                "vehicle_type": vehicle["vehicle_type"],
                "area": available_slot["area"],
                "slot_id": str(available_slot["_id"]),
                "slot_code": available_slot["slot_code"],
                "start_time": now,
                "end_time": end_time,
                "amount": amount,
                "status": "PAID"
            }
            
            result = await bookings_collection.insert_one(booking_doc)
            booking_doc["id"] = str(result.inserted_id)
            
            # Get updated wallet
            updated_wallet = await wallets_collection.find_one({"user_id": booking_data.user_id})
            
            return {
                "success": True,
                "message": "Booking created",
                "booking": booking_doc,
                "wallet_balance": updated_wallet["balance"]
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    else:
        global bookings, bookingIdCounter, slots, wallets
        
        # Find user
        user = None
        for u in users:
            if str(u.get("id")) == booking_data.user_id:
                user = u
                break
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Find vehicle
        vehicle = None
        for v in vehicles:
            if str(v.get("id")) == booking_data.vehicle_id and v.get("user_id") == booking_data.user_id:
                vehicle = v
                break
        
        if not vehicle:
            raise HTTPException(status_code=404, detail="Vehicle not found")
        
        # Get wallet
        wallet = find_wallet(booking_data.user_id)
        if not wallet:
            raise HTTPException(status_code=404, detail="Wallet not found")
        
        # Calculate amount
        rate = RATES.get(vehicle["vehicle_type"])
        if not rate:
            raise HTTPException(status_code=400, detail="Invalid vehicle type")
        
        amount = rate * booking_data.duration_hours
        
        # Check balance
        if wallet["balance"] < amount:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Insufficient wallet balance",
                    "required_amount": amount,
                    "current_balance": wallet["balance"]
                }
            )
        
        # Find available slot
        available_slot = None
        for slot in slots:
            if slot["vehicle_type_allowed"] == vehicle["vehicle_type"] and slot["status"] == "FREE":
                available_slot = slot
                break
        
        if not available_slot:
            raise HTTPException(
                status_code=400,
                detail="No free slots available for this vehicle type"
            )
        
        # Update wallet
        wallet["balance"] -= amount
        
        # Update slot
        available_slot["status"] = "RESERVED"
        
        # Create booking
        now = datetime.now()
        end_time = now + timedelta(hours=booking_data.duration_hours)
        booking_token = generate_booking_token()
        
        new_booking = {
            "id": bookingIdCounter,
            "booking_token": booking_token,
            "user_id": booking_data.user_id,
            "vehicle_id": booking_data.vehicle_id,
            "vehicle_type": vehicle["vehicle_type"],
            "area": available_slot["area"],
            "slot_id": available_slot["id"],
            "slot_code": available_slot["slot_code"],
            "start_time": now.isoformat(),
            "end_time": end_time.isoformat(),
            "amount": amount,
            "status": "PAID"
        }
        bookings.append(new_booking)
        bookingIdCounter += 1
        
        return {
            "success": True,
            "message": "Booking created",
            "booking": new_booking,
            "wallet_balance": wallet["balance"]
        }

@app.get("/api/bookings/{user_id}")
async def get_user_bookings(user_id: str):
    """Get all bookings for a user"""
    if MONGODB_AVAILABLE:
        try:
            bookings_list = await bookings_collection.find({"user_id": user_id}).to_list(1000)
            
            for booking in bookings_list:
                booking["_id"] = str(booking["_id"])
                booking["start_time"] = booking["start_time"].isoformat()
                booking["end_time"] = booking["end_time"].isoformat()
            
            return {"success": True, "bookings": bookings_list}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    else:
        user_bookings = [b for b in bookings if b.get("user_id") == user_id]
        return {"success": True, "bookings": user_bookings}

@app.post("/api/qr/validate")
async def validate_qr(qr_data: QRValidate):
    """Validate booking token at gate"""
    if not qr_data.booking_token:
        raise HTTPException(status_code=400, detail="Token is required")
    
    if MONGODB_AVAILABLE:
        try:
            booking = await bookings_collection.find_one({"booking_token": qr_data.booking_token})
            if not booking:
                return {
                    "success": False,
                    "message": "ACCESS DENIED – No valid booking found."
                }
            
            now = datetime.now()
            start_time = booking["start_time"]
            end_time = booking["end_time"]
            
            if now > end_time:
                await bookings_collection.update_one(
                    {"_id": booking["_id"]},
                    {"$set": {"status": "EXPIRED"}}
                )
                
                await slots_collection.update_one(
                    {"_id": ObjectId(booking["slot_id"])},
                    {"$set": {"status": "FREE"}}
                )
                
                return {
                    "success": False,
                    "message": "TIME SLOT ENDED – Please pay extra."
                }
            
            if now < start_time:
                return {
                    "success": False,
                    "message": "ACCESS DENIED – Booking not yet active."
                }
            
            await slots_collection.update_one(
                {"_id": ObjectId(booking["slot_id"])},
                {"$set": {"status": "OCCUPIED"}}
            )
            
            await bookings_collection.update_one(
                {"_id": booking["_id"]},
                {"$set": {"status": "ACTIVE"}}
            )
            
            slot = await slots_collection.find_one({"_id": ObjectId(booking["slot_id"])})
            
            return {
                "success": True,
                "message": f"ACCESS GRANTED – Proceed to Area {booking['area']}, Slot {slot['slot_code'] if slot else ''}",
                "area": booking["area"],
                "slot_id": booking["slot_id"],
                "slot_code": slot["slot_code"] if slot else None
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    else:
        global bookings, slots
        
        # Find booking
        booking = None
        for b in bookings:
            if b.get("booking_token") == qr_data.booking_token:
                booking = b
                break
        
        if not booking:
            return {
                "success": False,
                "message": "ACCESS DENIED – No valid booking found."
            }
        
        now = datetime.now()
        start_time = datetime.fromisoformat(booking["start_time"])
        end_time = datetime.fromisoformat(booking["end_time"])
        
        if now > end_time:
            booking["status"] = "EXPIRED"
            
            # Free up slot
            for slot in slots:
                if slot["id"] == booking["slot_id"]:
                    slot["status"] = "FREE"
                    break
            
            return {
                "success": False,
                "message": "TIME SLOT ENDED – Please pay extra."
            }
        
        if now < start_time:
            return {
                "success": False,
                "message": "ACCESS DENIED – Booking not yet active."
            }
        
        # Update slot to occupied
        for slot in slots:
            if slot["id"] == booking["slot_id"]:
                slot["status"] = "OCCUPIED"
                booking["status"] = "ACTIVE"
                slot_code = slot["slot_code"]
                break
        
        return {
            "success": True,
            "message": f"ACCESS GRANTED – Proceed to Area {booking['area']}, Slot {slot_code}",
            "area": booking["area"],
            "slot_id": booking["slot_id"],
            "slot_code": slot_code
        }

@app.get("/api/slots")
async def get_all_slots():
    """Get all parking slots"""
    if MONGODB_AVAILABLE:
        try:
            slots_list = await slots_collection.find().to_list(1000)
            
            for slot in slots_list:
                slot["_id"] = str(slot["_id"])
            
            return {"success": True, "slots": slots_list}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    else:
        return {"success": True, "slots": slots}

@app.post("/api/book-slot")
async def book_slot(data: dict):
    """Legacy endpoint"""
    return {
        "success": True,
        "booking": {
            "area": "C",
            "slot": "C1",
            "amount": 50,
            "vehicle": data.get("vehicle", ""),
            "duration": data.get("duration", 1)
        }
    }

@app.post("/api/gate")
async def control_gate():
    """Legacy endpoint"""
    return {"success": True, "gate": "OPEN"}

# Vercel requires this for serverless functions
app = app
