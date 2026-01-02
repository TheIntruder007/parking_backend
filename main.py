from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime, timedelta
import random
import string
from bson import ObjectId
import motor.motor_asyncio
from pydantic import Field, ConfigDict
from pydantic.functional_validators import field_validator
import pytz
import bcrypt
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# MongoDB connection
MONGODB_URI = "mongodb+srv://wisdomkagyan_db_user:gqbCoXr99sKOcXEw@cluster0.itxqujm.mongodb.net/?appName=Cluster0&retryWrites=true&w=majority"
client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URI)
db = client.smart_parking

# Collections
users_collection = db.users
vehicles_collection = db.vehicles
wallets_collection = db.wallets
bookings_collection = db.bookings
slots_collection = db.slots

app = FastAPI(title="Smart Parking API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models with ObjectId handling
class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)

    @classmethod
    def __modify_schema__(cls, field_schema):
        field_schema.update(type="string")

class UserBase(BaseModel):
    name: str
    mobile: str
    email: EmailStr
    password: str

class UserCreate(UserBase):
    pass

class UserResponse(BaseModel):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    name: str
    mobile: str
    email: EmailStr
    created_at: datetime
    
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str}
    )

class VehicleBase(BaseModel):
    vehicle_number: str
    vehicle_type: str

class VehicleCreate(VehicleBase):
    user_id: str

class VehicleResponse(BaseModel):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    user_id: str
    vehicle_number: str
    vehicle_type: str
    
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str}
    )

class WalletResponse(BaseModel):
    user_id: str
    balance: float = 0.0

class WalletRecharge(BaseModel):
    user_id: str
    amount: float
    
    @field_validator('amount')
    def validate_amount(cls, v):
        if v <= 0:
            raise ValueError('Amount must be positive')
        return v

class SlotBase(BaseModel):
    area: str
    slot_code: str
    vehicle_type_allowed: str
    status: str = "FREE"

class SlotResponse(BaseModel):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    area: str
    slot_code: str
    vehicle_type_allowed: str
    status: str
    
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str}
    )

class BookingCreate(BaseModel):
    user_id: str
    vehicle_id: str
    duration_hours: int
    
    @field_validator('duration_hours')
    def validate_duration(cls, v):
        if v <= 0:
            raise ValueError('Duration must be positive')
        return v

class BookingResponse(BaseModel):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    booking_token: str
    user_id: str
    vehicle_id: str
    vehicle_type: str
    area: str
    slot_id: str
    slot_code: str
    start_time: datetime
    end_time: datetime
    amount: float
    status: str
    
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str}
    )

class QRValidate(BaseModel):
    booking_token: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

# Constants
RATES = {"2W": 50, "4W": 100}
TIMEZONE = pytz.timezone('UTC')

# Helper functions
def generate_booking_token():
    random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    timestamp_part = datetime.now().strftime("%y%m%d%H%M%S")
    return f"BK-{random_part}-{timestamp_part}"

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

async def init_slots():
    """Initialize parking slots if they don't exist"""
    count = await slots_collection.count_documents({})
    if count == 0:
        slot_config = [
            {"area": "A", "prefix": "A", "count": 5, "vehicle_type_allowed": "4W"},
            {"area": "B", "prefix": "B", "count": 5, "vehicle_type_allowed": "4W"},
            {"area": "C", "prefix": "C", "count": 5, "vehicle_type_allowed": "2W"},
            {"area": "D", "prefix": "D", "count": 5, "vehicle_type_allowed": "2W"}
        ]
        
        slots = []
        slot_id_counter = 1
        for config in slot_config:
            for i in range(1, config["count"] + 1):
                slot = {
                    "slot_id": slot_id_counter,
                    "area": config["area"],
                    "slot_code": f"{config['prefix']}{i}",
                    "vehicle_type_allowed": config["vehicle_type_allowed"],
                    "status": "FREE"
                }
                slots.append(slot)
                slot_id_counter += 1
        
        if slots:
            await slots_collection.insert_many(slots)

# Initialize database on startup
@app.on_event("startup")
async def startup_db_client():
    await init_slots()
    # Create indexes
    await users_collection.create_index("email", unique=True)
    await bookings_collection.create_index("booking_token", unique=True)

# Health check
@app.get("/api/health")
async def health_check():
    return {"success": True, "message": "Smart Parking API running"}

# Root endpoint
@app.get("/")
async def root():
    return {"message": "Welcome to Smart Parking API"}

# ---------- USER ROUTES ----------
@app.post("/api/register", response_model=dict, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate):
    """Register a new user"""
    # Check if user already exists
    existing_user = await users_collection.find_one({"email": user_data.email.lower()})
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create user document
    user_doc = {
        "name": user_data.name,
        "mobile": user_data.mobile,
        "email": user_data.email.lower(),
        "password_hash": hash_password(user_data.password),
        "created_at": datetime.now(TIMEZONE)
    }
    
    # Insert user
    result = await users_collection.insert_one(user_doc)
    
    # Create wallet for user
    wallet_doc = {
        "user_id": str(result.inserted_id),
        "balance": 0.0
    }
    await wallets_collection.insert_one(wallet_doc)
    
    return {
        "success": True,
        "message": "User registered successfully",
        "user_id": str(result.inserted_id),
        "name": user_data.name
    }

@app.post("/api/login", response_model=dict)
async def login(login_data: LoginRequest):
    """Login user"""
    user = await users_collection.find_one({"email": login_data.email.lower()})
    
    if not user or not verify_password(login_data.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    return {
        "success": True,
        "message": "Login successful",
        "user_id": str(user["_id"]),
        "name": user["name"]
    }

# ---------- WALLET ROUTES ----------
@app.get("/api/wallet/{user_id}", response_model=dict)
async def get_wallet(user_id: str):
    """Get user wallet"""
    wallet = await wallets_collection.find_one({"user_id": user_id})
    
    if not wallet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wallet not found"
        )
    
    return {"success": True, "wallet": wallet}

@app.post("/api/wallet/recharge", response_model=dict)
async def recharge_wallet(recharge_data: WalletRecharge):
    """Recharge user wallet"""
    wallet = await wallets_collection.find_one({"user_id": recharge_data.user_id})
    
    if not wallet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wallet not found"
        )
    
    # Update balance
    new_balance = wallet["balance"] + recharge_data.amount
    await wallets_collection.update_one(
        {"user_id": recharge_data.user_id},
        {"$set": {"balance": new_balance}}
    )
    
    updated_wallet = await wallets_collection.find_one({"user_id": recharge_data.user_id})
    return {"success": True, "wallet": updated_wallet}

# ---------- VEHICLE ROUTES ----------
@app.post("/api/vehicles", response_model=dict, status_code=status.HTTP_201_CREATED)
async def add_vehicle(vehicle_data: VehicleCreate):
    """Add a vehicle for user"""
    # Check if user exists
    user = await users_collection.find_one({"_id": ObjectId(vehicle_data.user_id)})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Create vehicle document
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

@app.get("/api/vehicles/{user_id}", response_model=dict)
async def get_user_vehicles(user_id: str):
    """Get all vehicles for a user"""
    vehicles = await vehicles_collection.find({"user_id": user_id}).to_list(1000)
    
    # Convert ObjectId to string
    for vehicle in vehicles:
        vehicle["_id"] = str(vehicle["_id"])
    
    return {"success": True, "vehicles": vehicles}

# ---------- BOOKING ROUTES ----------
@app.post("/api/bookings/create", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_booking(booking_data: BookingCreate):
    """Create a new booking"""
    # Validate user
    user = await users_collection.find_one({"_id": ObjectId(booking_data.user_id)})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Validate vehicle
    vehicle = await vehicles_collection.find_one({
        "_id": ObjectId(booking_data.vehicle_id),
        "user_id": booking_data.user_id
    })
    if not vehicle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vehicle not found"
        )
    
    # Get wallet
    wallet = await wallets_collection.find_one({"user_id": booking_data.user_id})
    if not wallet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wallet not found"
        )
    
    # Calculate amount
    rate = RATES.get(vehicle["vehicle_type"])
    if not rate:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid vehicle type"
        )
    
    amount = rate * booking_data.duration_hours
    
    # Check balance
    if wallet["balance"] < amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
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
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No free slots available for this vehicle type"
        )
    
    # Update wallet balance
    new_balance = wallet["balance"] - amount
    await wallets_collection.update_one(
        {"user_id": booking_data.user_id},
        {"$set": {"balance": new_balance}}
    )
    
    # Update slot status
    await slots_collection.update_one(
        {"_id": available_slot["_id"]},
        {"$set": {"status": "RESERVED"}}
    )
    
    # Create booking
    now = datetime.now(TIMEZONE)
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
    booking_doc["_id"] = str(result.inserted_id)
    
    return {
        "success": True,
        "message": "Booking created",
        "booking": booking_doc,
        "wallet_balance": new_balance
    }

@app.get("/api/bookings/{user_id}", response_model=dict)
async def get_user_bookings(user_id: str):
    """Get all bookings for a user"""
    bookings = await bookings_collection.find({"user_id": user_id}).to_list(1000)
    
    # Convert ObjectId to string and datetime to ISO format
    for booking in bookings:
        booking["_id"] = str(booking["_id"])
        booking["start_time"] = booking["start_time"].isoformat()
        booking["end_time"] = booking["end_time"].isoformat()
    
    return {"success": True, "bookings": bookings}

# ---------- QR VALIDATION ----------
@app.post("/api/qr/validate", response_model=dict)
async def validate_qr(qr_data: QRValidate):
    """Validate booking token at gate"""
    if not qr_data.booking_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token is required"
        )
    
    booking = await bookings_collection.find_one({"booking_token": qr_data.booking_token})
    if not booking:
        return {
            "success": False,
            "message": "ACCESS DENIED – No valid booking found."
        }
    
    now = datetime.now(TIMEZONE)
    start_time = booking["start_time"]
    end_time = booking["end_time"]
    
    # Check if booking has expired
    if now > end_time:
        # Update booking status
        await bookings_collection.update_one(
            {"_id": booking["_id"]},
            {"$set": {"status": "EXPIRED"}}
        )
        
        # Free up the slot
        await slots_collection.update_one(
            {"_id": ObjectId(booking["slot_id"])},
            {"$set": {"status": "FREE"}}
        )
        
        return {
            "success": False,
            "message": "TIME SLOT ENDED – Please pay extra."
        }
    
    # Check if booking hasn't started yet
    if now < start_time:
        return {
            "success": False,
            "message": "ACCESS DENIED – Booking not yet active."
        }
    
    # Update slot to occupied
    await slots_collection.update_one(
        {"_id": ObjectId(booking["slot_id"])},
        {"$set": {"status": "OCCUPIED"}}
    )
    
    # Update booking status
    await bookings_collection.update_one(
        {"_id": booking["_id"]},
        {"$set": {"status": "ACTIVE"}}
    )
    
    # Get slot info
    slot = await slots_collection.find_one({"_id": ObjectId(booking["slot_id"])})
    
    return {
        "success": True,
        "message": f"ACCESS GRANTED – Proceed to Area {booking['area']}, Slot {slot['slot_code'] if slot else ''}",
        "area": booking["area"],
        "slot_id": booking["slot_id"],
        "slot_code": slot["slot_code"] if slot else None
    }

# ---------- SLOT ROUTES ----------
@app.get("/api/slots", response_model=dict)
async def get_all_slots():
    """Get all parking slots"""
    slots = await slots_collection.find().to_list(1000)
    
    # Convert ObjectId to string
    for slot in slots:
        slot["_id"] = str(slot["_id"])
    
    return {"success": True, "slots": slots}

# ---------- EXTRA ENDPOINTS FOR COMPATIBILITY ----------
@app.post("/api/book-slot", response_model=dict)
async def book_slot(data: dict):
    """Legacy endpoint for compatibility"""
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

@app.post("/api/gate", response_model=dict)
async def control_gate():
    """Legacy endpoint for gate control"""
    return {"success": True, "gate": "OPEN"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
