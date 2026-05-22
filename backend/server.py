from fastapi import FastAPI, APIRouter, HTTPException, Request
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional
import uuid
from datetime import datetime, timezone
from emergentintegrations.llm.chat import LlmChat, UserMessage
from emergentintegrations.payments.stripe.checkout import StripeCheckout, CheckoutSessionRequest
import json

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Setup logging early
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

EMERGENT_LLM_KEY = os.environ['EMERGENT_LLM_KEY']

app = FastAPI()
api_router = APIRouter(prefix="/api")

# --- Models ---
class SocialHandles(BaseModel):
    instagram: Optional[str] = ""
    tiktok: Optional[str] = ""
    twitter: Optional[str] = ""

class ProfileCreate(BaseModel):
    display_name: str
    handles: SocialHandles

class ProfileAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    display_name: str
    handles: SocialHandles
    niche: Optional[str] = None
    target_audience: Optional[str] = None
    best_morning_time: Optional[str] = None
    best_evening_time: Optional[str] = None
    analysis_summary: Optional[str] = None
    analyzed: bool = False
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class PostGenerateRequest(BaseModel):
    profile_id: str
    topic: Optional[str] = ""
    platform: Optional[str] = "instagram"

class GeneratedPost(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    profile_id: str
    platform: str
    caption: str
    hashtags: List[str]
    text_overlay: str
    image_guidance: str
    status: str = "draft"
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class ReminderCreate(BaseModel):
    profile_id: str
    morning_time: str
    evening_time: str
    enabled: bool = True

class Reminder(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    profile_id: str
    morning_time: str
    evening_time: str
    enabled: bool = True
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class FollowerEntry(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    profile_id: str
    count: int
    date: str = Field(default_factory=lambda: datetime.now(timezone.utc).strftime('%Y-%m-%d'))
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# --- Routes ---
@api_router.get("/")
async def root():
    return {"message": "Social Media Growth API"}

# Profile endpoints
@api_router.post("/profiles")
async def create_profile(data: ProfileCreate):
    profile = ProfileAnalysis(
        display_name=data.display_name,
        handles=data.handles
    )
    profile_dict = profile.dict()
    await db.profiles.insert_one(profile_dict)
    profile_dict.pop("_id", None)
    return profile_dict

@api_router.get("/profiles")
async def get_profiles():
    profiles = await db.profiles.find({}, {"_id": 0}).to_list(100)
    return profiles

@api_router.get("/profiles/{profile_id}")
async def get_profile(profile_id: str):
    profile = await db.profiles.find_one({"id": profile_id}, {"_id": 0})
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile

# Update profile (editable fields)
class ProfileUpdate(BaseModel):
    niche: Optional[str] = None
    target_audience: Optional[str] = None
    best_morning_time: Optional[str] = None
    best_evening_time: Optional[str] = None

@api_router.put("/profiles/{profile_id}")
async def update_profile(profile_id: str, data: ProfileUpdate):
    profile = await db.profiles.find_one({"id": profile_id}, {"_id": 0})
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    update_fields = {k: v for k, v in data.dict().items() if v is not None}
    if update_fields:
        await db.profiles.update_one({"id": profile_id}, {"$set": update_fields})
    updated = await db.profiles.find_one({"id": profile_id}, {"_id": 0})
    return updated

# AI Analysis endpoint
@api_router.post("/profiles/{profile_id}/analyze")
async def analyze_profile(profile_id: str):
    profile = await db.profiles.find_one({"id": profile_id}, {"_id": 0})
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    handles = profile.get("handles", {})
    display_name = profile.get("display_name", "User")

    prompt = f"""You are a social media growth expert. Analyze the following creator's social media presence and provide strategic insights.

Creator: {display_name}
Instagram: @{handles.get('instagram', 'N/A')}
TikTok: @{handles.get('tiktok', 'N/A')}
Twitter/X: @{handles.get('twitter', 'N/A')}

Based on these handles, infer their likely niche, content style, and audience. Provide your analysis in the following JSON format only, no other text:
{{
    "niche": "their primary content niche (e.g., Fitness & Wellness, Fashion, Tech Reviews, Food, Travel, etc.)",
    "target_audience": "description of their ideal audience (age range, interests, demographics)",
    "best_morning_time": "optimal morning posting time like 8:30 AM",
    "best_evening_time": "optimal evening posting time like 7:00 PM",
    "analysis_summary": "2-3 sentence summary of their brand and growth potential"
}}"""

    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"analyze-{profile_id}-{uuid.uuid4()}",
            system_message="You are a social media growth strategist. Always respond with valid JSON only."
        )
        chat.with_model("openai", "gpt-4o")

        response = await chat.send_message(UserMessage(text=prompt))

        # Parse JSON from response
        response_text = response.strip()
        if response_text.startswith("```"):
            response_text = response_text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        analysis = json.loads(response_text)

        update_data = {
            "niche": analysis.get("niche", "General Content"),
            "target_audience": analysis.get("target_audience", "18-34 year olds interested in lifestyle content"),
            "best_morning_time": analysis.get("best_morning_time", "9:00 AM"),
            "best_evening_time": analysis.get("best_evening_time", "7:00 PM"),
            "analysis_summary": analysis.get("analysis_summary", "Great potential for growth with consistent posting."),
            "analyzed": True
        }

        await db.profiles.update_one({"id": profile_id}, {"$set": update_data})
        updated = await db.profiles.find_one({"id": profile_id}, {"_id": 0})
        return updated

    except Exception as e:
        logger.error(f"Analysis error: {e}")
        # Fallback analysis
        fallback = {
            "niche": "Lifestyle & Content Creation",
            "target_audience": "18-34 year olds interested in trending content",
            "best_morning_time": "9:00 AM",
            "best_evening_time": "7:30 PM",
            "analysis_summary": f"{display_name} has great potential for growth. Consistent posting at peak times will help increase engagement.",
            "analyzed": True
        }
        await db.profiles.update_one({"id": profile_id}, {"$set": fallback})
        updated = await db.profiles.find_one({"id": profile_id}, {"_id": 0})
        return updated


# Post generation endpoint
@api_router.post("/posts/generate")
async def generate_post(data: PostGenerateRequest):
    profile = await db.profiles.find_one({"id": data.profile_id}, {"_id": 0})
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    niche = profile.get("niche", "general content")
    audience = profile.get("target_audience", "general audience")
    topic_hint = f" about {data.topic}" if data.topic else ""

    prompt = f"""You are an expert social media content creator. Create a perfect {data.platform} post for a creator in the "{niche}" niche targeting {audience}{topic_hint}.

IMPORTANT: Keep the image guidance SUPER simple and easy. The creator should NOT overthink this. One simple sentence like "Smile for a selfie in good lighting" or "Take a quick photo of your setup". No complicated poses or detailed staging. Make it feel effortless.

Provide the response in the following JSON format only, no other text:
{{
    "caption": "an engaging, authentic caption (2-4 sentences with personality and a call-to-action)",
    "hashtags": ["hashtag1", "hashtag2", "hashtag3", "hashtag4", "hashtag5", "hashtag6", "hashtag7", "hashtag8"],
    "text_overlay": "short punchy text to overlay on the image (5-8 words max)",
    "image_guidance": "ONE simple sentence. Keep it easy - like 'Snap a quick selfie with a smile' or 'Take a photo of your morning coffee'. Nothing complicated. The goal is to just POST, not stress about the perfect photo."
}}"""

    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"post-{data.profile_id}-{uuid.uuid4()}",
            system_message="You are a viral social media content strategist. Always respond with valid JSON only."
        )
        chat.with_model("openai", "gpt-4o")

        response = await chat.send_message(UserMessage(text=prompt))

        response_text = response.strip()
        if response_text.startswith("```"):
            response_text = response_text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        post_data = json.loads(response_text)

        generated = GeneratedPost(
            profile_id=data.profile_id,
            platform=data.platform,
            caption=post_data.get("caption", "Check out my latest post!"),
            hashtags=post_data.get("hashtags", ["viral", "fyp", "trending"]),
            text_overlay=post_data.get("text_overlay", "New Post Alert"),
            image_guidance=post_data.get("image_guidance", "Take a well-lit photo in natural light with a clean background.")
        )

        gen_dict = generated.dict()
        await db.posts.insert_one(gen_dict)
        gen_dict.pop("_id", None)
        return gen_dict

    except Exception as e:
        logger.error(f"Post generation error: {e}")
        generated = GeneratedPost(
            profile_id=data.profile_id,
            platform=data.platform,
            caption="Ready to level up! What do you think? Drop a comment below!",
            hashtags=["growth", "creator", "viral", "trending", "fyp", "inspo", "content", "socialmedia"],
            text_overlay="Level Up Today",
            image_guidance="Take a bright, well-lit selfie or flat-lay photo. Use natural lighting near a window. Keep the background clean and minimal."
        )
        gen_dict = generated.dict()
        await db.posts.insert_one(gen_dict)
        gen_dict.pop("_id", None)
        return gen_dict

@api_router.get("/posts/{profile_id}")
async def get_posts(profile_id: str):
    posts = await db.posts.find({"profile_id": profile_id}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return posts

@api_router.delete("/posts/{post_id}")
async def delete_post(post_id: str):
    result = await db.posts.delete_one({"id": post_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Post not found")
    return {"deleted": True}

@api_router.put("/posts/{post_id}/status")
async def update_post_status(post_id: str, data: dict):
    status = data.get("status", "draft")
    result = await db.posts.update_one({"id": post_id}, {"$set": {"status": status}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Post not found")
    updated = await db.posts.find_one({"id": post_id}, {"_id": 0})
    return updated

# Reminder endpoints
@api_router.post("/reminders")
async def create_or_update_reminder(data: ReminderCreate):
    existing = await db.reminders.find_one({"profile_id": data.profile_id}, {"_id": 0})
    if existing:
        await db.reminders.update_one(
            {"profile_id": data.profile_id},
            {"$set": {
                "morning_time": data.morning_time,
                "evening_time": data.evening_time,
                "enabled": data.enabled
            }}
        )
        updated = await db.reminders.find_one({"profile_id": data.profile_id}, {"_id": 0})
        return updated
    else:
        reminder = Reminder(
            profile_id=data.profile_id,
            morning_time=data.morning_time,
            evening_time=data.evening_time,
            enabled=data.enabled
        )
        rem_dict = reminder.dict()
        await db.reminders.insert_one(rem_dict)
        rem_dict.pop("_id", None)
        return rem_dict

@api_router.get("/reminders/{profile_id}")
async def get_reminder(profile_id: str):
    reminder = await db.reminders.find_one({"profile_id": profile_id}, {"_id": 0})
    if not reminder:
        return {"profile_id": profile_id, "morning_time": "9:00 AM", "evening_time": "7:00 PM", "enabled": False}
    return reminder

# Follower tracking endpoints
@api_router.post("/followers")
async def add_follower_count(data: dict):
    profile_id = data.get("profile_id")
    count = data.get("count", 0)
    if not profile_id:
        raise HTTPException(status_code=400, detail="profile_id required")

    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    existing = await db.followers.find_one({"profile_id": profile_id, "date": today})
    if existing:
        await db.followers.update_one(
            {"profile_id": profile_id, "date": today},
            {"$set": {"count": count}}
        )
    else:
        entry = FollowerEntry(profile_id=profile_id, count=count, date=today)
        entry_dict = entry.dict()
        await db.followers.insert_one(entry_dict)
        entry_dict.pop("_id", None)

    updated = await db.followers.find_one({"profile_id": profile_id, "date": today}, {"_id": 0})
    return updated

@api_router.get("/followers/{profile_id}")
async def get_follower_history(profile_id: str):
    entries = await db.followers.find(
        {"profile_id": profile_id}, {"_id": 0}
    ).sort("date", 1).to_list(365)
    return entries

# Stripe config
STRIPE_API_KEY = os.environ['STRIPE_API_KEY']

STRIPE_MONTHLY_PRODUCT = os.environ.get('STRIPE_MONTHLY_PRODUCT', '')
STRIPE_YEARLY_PRODUCT = os.environ.get('STRIPE_YEARLY_PRODUCT', '')

SUBSCRIPTION_PLANS = {
    "monthly": {"amount": 4.99, "label": "Monthly", "product_id": STRIPE_MONTHLY_PRODUCT},
    "yearly": {"amount": 39.99, "label": "Yearly", "product_id": STRIPE_YEARLY_PRODUCT},
}

# Stripe endpoints
@api_router.post("/checkout/create")
async def create_checkout(request: Request, data: dict):
    plan_id = data.get("plan_id", "monthly")
    origin_url = data.get("origin_url", "")

    if plan_id not in SUBSCRIPTION_PLANS:
        raise HTTPException(status_code=400, detail="Invalid plan")

    plan = SUBSCRIPTION_PLANS[plan_id]
    host_url = str(request.base_url).rstrip("/")
    webhook_url = f"{host_url}/api/webhook/stripe"

    stripe_checkout = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)

    success_url = f"{origin_url}/payment-success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{origin_url}/paywall"

    checkout_req = CheckoutSessionRequest(
        amount=plan["amount"],
        currency="usd",
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={"plan_id": plan_id, "plan_label": plan["label"]},
    )

    session = await stripe_checkout.create_checkout_session(checkout_req)

    # Save transaction
    tx = {
        "id": str(uuid.uuid4()),
        "session_id": session.session_id,
        "plan_id": plan_id,
        "amount": plan["amount"],
        "currency": "usd",
        "payment_status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.payment_transactions.insert_one(tx)
    tx.pop("_id", None)

    return {"url": session.url, "session_id": session.session_id}

@api_router.get("/checkout/status/{session_id}")
async def get_checkout_status(request: Request, session_id: str):
    import stripe
    stripe.api_key = STRIPE_API_KEY
    try:
        session = stripe.checkout.Session.retrieve(session_id)
        payment_status = session.get("payment_status", "unpaid")
        status = session.get("status", "open")

        # Update transaction
        if payment_status == "paid":
            await db.payment_transactions.update_one(
                {"session_id": session_id},
                {"$set": {"payment_status": "paid", "status": status}}
            )

        return {
            "status": status,
            "payment_status": payment_status,
            "amount_total": session.get("amount_total", 0),
            "currency": session.get("currency", "usd"),
        }
    except Exception as e:
        logger.error(f"Status check error: {e}")
        # Check our DB as fallback
        tx = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
        if tx:
            return {"status": tx.get("status", "open"), "payment_status": tx.get("payment_status", "unpaid"), "amount_total": 0, "currency": "usd"}
        raise HTTPException(status_code=404, detail="Session not found")

@api_router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    body = await request.body()
    sig = request.headers.get("Stripe-Signature", "")
    host_url = str(request.base_url).rstrip("/")
    webhook_url = f"{host_url}/api/webhook/stripe"
    stripe_checkout = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)

    try:
        event = await stripe_checkout.handle_webhook(body, sig)
        if event.payment_status == "paid":
            await db.payment_transactions.update_one(
                {"session_id": event.session_id},
                {"$set": {"payment_status": "paid", "event_type": event.event_type}}
            )
        return {"received": True}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return {"received": True}

# Include the router
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
