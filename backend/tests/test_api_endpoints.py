"""
Backend API Tests for Social Media Growth App
Tests: Health check, Profile CRUD, AI Analysis, Post Generation, Reminders
"""
import pytest
import requests
import os
import time
from pathlib import Path
from dotenv import load_dotenv

# Load frontend .env to get EXPO_PUBLIC_BACKEND_URL
frontend_env = Path(__file__).parent.parent.parent / 'frontend' / '.env'
load_dotenv(frontend_env)

BASE_URL = os.environ.get('EXPO_PUBLIC_BACKEND_URL')
if not BASE_URL:
    raise ValueError("EXPO_PUBLIC_BACKEND_URL not found in environment")
BASE_URL = BASE_URL.rstrip('/')

class TestHealthCheck:
    """Health check endpoint test"""
    
    def test_health_check(self, api_client):
        """Test GET /api/ returns 200"""
        response = api_client.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        print(f"✓ Health check passed: {data}")


class TestProfileCRUD:
    """Profile creation, retrieval, listing, and update tests"""
    
    def test_create_profile_and_verify(self, api_client):
        """Test POST /api/profiles creates profile and verify with GET"""
        create_payload = {
            "display_name": "TEST_JohnDoe",
            "handles": {
                "instagram": "johndoe_insta",
                "tiktok": "johndoe_tiktok",
                "twitter": "johndoe_x"
            }
        }
        
        # Create profile
        create_response = api_client.post(f"{BASE_URL}/api/profiles", json=create_payload)
        assert create_response.status_code == 200
        
        created_profile = create_response.json()
        assert created_profile["display_name"] == create_payload["display_name"]
        assert created_profile["handles"]["instagram"] == create_payload["handles"]["instagram"]
        assert "id" in created_profile
        assert created_profile["analyzed"] == False
        
        profile_id = created_profile["id"]
        print(f"✓ Profile created: {profile_id}")
        
        # Verify persistence with GET
        get_response = api_client.get(f"{BASE_URL}/api/profiles/{profile_id}")
        assert get_response.status_code == 200
        
        retrieved_profile = get_response.json()
        assert retrieved_profile["id"] == profile_id
        assert retrieved_profile["display_name"] == create_payload["display_name"]
        print(f"✓ Profile retrieved and verified: {profile_id}")
        
        return profile_id
    
    def test_get_all_profiles(self, api_client):
        """Test GET /api/profiles returns list"""
        response = api_client.get(f"{BASE_URL}/api/profiles")
        assert response.status_code == 200
        
        profiles = response.json()
        assert isinstance(profiles, list)
        print(f"✓ Retrieved {len(profiles)} profiles")
    
    def test_get_nonexistent_profile(self, api_client):
        """Test GET /api/profiles/{invalid_id} returns 404"""
        response = api_client.get(f"{BASE_URL}/api/profiles/nonexistent-id-12345")
        assert response.status_code == 404
        print("✓ 404 returned for nonexistent profile")
    
    def test_update_profile_fields(self, api_client, test_profile_id):
        """Test PUT /api/profiles/{id} updates editable fields and verify with GET"""
        # First analyze the profile to get initial values
        api_client.post(f"{BASE_URL}/api/profiles/{test_profile_id}/analyze")
        
        # Update fields
        update_payload = {
            "niche": "Updated Fitness & Wellness",
            "target_audience": "Updated 25-40 year olds interested in health",
            "best_morning_time": "6:30 AM",
            "best_evening_time": "8:30 PM"
        }
        
        update_response = api_client.put(f"{BASE_URL}/api/profiles/{test_profile_id}", json=update_payload)
        assert update_response.status_code == 200
        
        updated_profile = update_response.json()
        assert updated_profile["id"] == test_profile_id
        assert updated_profile["niche"] == update_payload["niche"]
        assert updated_profile["target_audience"] == update_payload["target_audience"]
        assert updated_profile["best_morning_time"] == update_payload["best_morning_time"]
        assert updated_profile["best_evening_time"] == update_payload["best_evening_time"]
        
        print(f"✓ Profile updated successfully")
        print(f"  Niche: {updated_profile['niche']}")
        print(f"  Audience: {updated_profile['target_audience']}")
        print(f"  Morning: {updated_profile['best_morning_time']}")
        print(f"  Evening: {updated_profile['best_evening_time']}")
        
        # Verify persistence with GET
        get_response = api_client.get(f"{BASE_URL}/api/profiles/{test_profile_id}")
        assert get_response.status_code == 200
        
        verified = get_response.json()
        assert verified["niche"] == update_payload["niche"]
        assert verified["target_audience"] == update_payload["target_audience"]
        assert verified["best_morning_time"] == update_payload["best_morning_time"]
        assert verified["best_evening_time"] == update_payload["best_evening_time"]
        print("✓ Update persisted correctly")
    
    def test_update_partial_fields(self, api_client, test_profile_id):
        """Test PUT /api/profiles/{id} with partial update (only niche)"""
        partial_update = {
            "niche": "Tech Reviews & Gadgets"
        }
        
        response = api_client.put(f"{BASE_URL}/api/profiles/{test_profile_id}", json=partial_update)
        assert response.status_code == 200
        
        updated = response.json()
        assert updated["niche"] == "Tech Reviews & Gadgets"
        print("✓ Partial update (niche only) successful")
    
    def test_update_nonexistent_profile(self, api_client):
        """Test PUT /api/profiles/{invalid_id} returns 404"""
        update_payload = {
            "niche": "Test Niche"
        }
        
        response = api_client.put(f"{BASE_URL}/api/profiles/nonexistent-id-99999", json=update_payload)
        assert response.status_code == 404
        print("✓ 404 returned for updating nonexistent profile")


class TestProfileAnalysis:
    """AI analysis endpoint tests"""
    
    def test_analyze_profile(self, api_client, test_profile_id):
        """Test POST /api/profiles/{id}/analyze returns AI analysis"""
        response = api_client.post(f"{BASE_URL}/api/profiles/{test_profile_id}/analyze")
        assert response.status_code == 200
        
        analyzed_profile = response.json()
        assert analyzed_profile["id"] == test_profile_id
        assert analyzed_profile["analyzed"] == True
        assert analyzed_profile["niche"] is not None
        assert analyzed_profile["target_audience"] is not None
        assert analyzed_profile["best_morning_time"] is not None
        assert analyzed_profile["best_evening_time"] is not None
        assert analyzed_profile["analysis_summary"] is not None
        
        print(f"✓ Profile analyzed successfully")
        print(f"  Niche: {analyzed_profile['niche']}")
        print(f"  Audience: {analyzed_profile['target_audience']}")
        print(f"  Morning time: {analyzed_profile['best_morning_time']}")
        print(f"  Evening time: {analyzed_profile['best_evening_time']}")
        
        # Verify persistence
        get_response = api_client.get(f"{BASE_URL}/api/profiles/{test_profile_id}")
        assert get_response.status_code == 200
        verified = get_response.json()
        assert verified["analyzed"] == True
        assert verified["niche"] == analyzed_profile["niche"]
        print("✓ Analysis persisted correctly")
    
    def test_analyze_nonexistent_profile(self, api_client):
        """Test POST /api/profiles/{invalid_id}/analyze returns 404"""
        response = api_client.post(f"{BASE_URL}/api/profiles/nonexistent-id-12345/analyze")
        assert response.status_code == 404
        print("✓ 404 returned for analyzing nonexistent profile")


class TestPostGeneration:
    """Post generation endpoint tests"""
    
    def test_generate_post_and_verify(self, api_client, test_profile_id):
        """Test POST /api/posts/generate creates post and verify with GET"""
        generate_payload = {
            "profile_id": test_profile_id,
            "topic": "morning routine tips",
            "platform": "instagram"
        }
        
        # Generate post
        gen_response = api_client.post(f"{BASE_URL}/api/posts/generate", json=generate_payload)
        assert gen_response.status_code == 200
        
        generated_post = gen_response.json()
        assert generated_post["profile_id"] == test_profile_id
        assert generated_post["platform"] == "instagram"
        assert "caption" in generated_post
        assert "hashtags" in generated_post
        assert isinstance(generated_post["hashtags"], list)
        assert len(generated_post["hashtags"]) > 0
        assert "text_overlay" in generated_post
        assert "image_guidance" in generated_post
        assert "id" in generated_post
        
        post_id = generated_post["id"]
        print(f"✓ Post generated: {post_id}")
        print(f"  Caption: {generated_post['caption'][:50]}...")
        print(f"  Hashtags: {generated_post['hashtags'][:3]}")
        
        # Verify persistence with GET
        get_response = api_client.get(f"{BASE_URL}/api/posts/{test_profile_id}")
        assert get_response.status_code == 200
        
        posts = get_response.json()
        assert isinstance(posts, list)
        assert len(posts) > 0
        
        # Find our post
        found = False
        for post in posts:
            if post["id"] == post_id:
                found = True
                assert post["caption"] == generated_post["caption"]
                break
        assert found, "Generated post not found in GET response"
        print(f"✓ Post retrieved and verified: {post_id}")
    
    def test_generate_post_without_topic(self, api_client, test_profile_id):
        """Test POST /api/posts/generate works without topic"""
        generate_payload = {
            "profile_id": test_profile_id,
            "platform": "tiktok"
        }
        
        response = api_client.post(f"{BASE_URL}/api/posts/generate", json=generate_payload)
        assert response.status_code == 200
        
        post = response.json()
        assert post["platform"] == "tiktok"
        assert "caption" in post
        print("✓ Post generated without topic")
    
    def test_generate_post_for_nonexistent_profile(self, api_client):
        """Test POST /api/posts/generate returns 404 for invalid profile"""
        generate_payload = {
            "profile_id": "nonexistent-id-12345",
            "platform": "twitter"
        }
        
        response = api_client.post(f"{BASE_URL}/api/posts/generate", json=generate_payload)
        assert response.status_code == 404
        print("✓ 404 returned for generating post with nonexistent profile")
    
    def test_get_posts_for_profile(self, api_client, test_profile_id):
        """Test GET /api/posts/{profile_id} returns posts list"""
        response = api_client.get(f"{BASE_URL}/api/posts/{test_profile_id}")
        assert response.status_code == 200
        
        posts = response.json()
        assert isinstance(posts, list)
        print(f"✓ Retrieved {len(posts)} posts for profile")


class TestPostHistory:
    """Post history endpoints - GET sorted posts, UPDATE status, DELETE post"""
    
    def test_get_posts_sorted_by_date(self, api_client, test_profile_id):
        """Test GET /api/posts/{profile_id} returns posts sorted by created_at descending"""
        # Generate 2 posts with slight delay to ensure different timestamps
        api_client.post(f"{BASE_URL}/api/posts/generate", json={
            "profile_id": test_profile_id,
            "platform": "instagram",
            "topic": "first post"
        })
        time.sleep(1)
        
        second_post_response = api_client.post(f"{BASE_URL}/api/posts/generate", json={
            "profile_id": test_profile_id,
            "platform": "tiktok",
            "topic": "second post"
        })
        second_post = second_post_response.json()
        
        # Get posts
        response = api_client.get(f"{BASE_URL}/api/posts/{test_profile_id}")
        assert response.status_code == 200
        
        posts = response.json()
        assert isinstance(posts, list)
        assert len(posts) >= 2
        
        # Verify sorted descending (newest first)
        assert posts[0]["id"] == second_post["id"], "Posts should be sorted by created_at descending (newest first)"
        print(f"✓ Posts sorted correctly (newest first)")
        print(f"  First post: {posts[0]['platform']} - {posts[0]['created_at']}")
        print(f"  Second post: {posts[1]['platform']} - {posts[1]['created_at']}")
    
    def test_update_post_status_and_verify(self, api_client, test_profile_id):
        """Test PUT /api/posts/{post_id}/status updates status and verify with GET"""
        # Generate a post
        gen_response = api_client.post(f"{BASE_URL}/api/posts/generate", json={
            "profile_id": test_profile_id,
            "platform": "twitter"
        })
        post = gen_response.json()
        post_id = post["id"]
        
        # Update status to 'posted'
        update_response = api_client.put(f"{BASE_URL}/api/posts/{post_id}/status", json={
            "status": "posted"
        })
        assert update_response.status_code == 200
        
        updated_post = update_response.json()
        assert updated_post["id"] == post_id
        assert updated_post["status"] == "posted"
        print(f"✓ Post status updated to 'posted': {post_id}")
        
        # Verify persistence with GET
        get_response = api_client.get(f"{BASE_URL}/api/posts/{test_profile_id}")
        assert get_response.status_code == 200
        
        posts = get_response.json()
        found_post = next((p for p in posts if p["id"] == post_id), None)
        assert found_post is not None
        assert found_post["status"] == "posted"
        print("✓ Status update persisted correctly")
    
    def test_update_status_nonexistent_post(self, api_client):
        """Test PUT /api/posts/{invalid_id}/status returns 404"""
        response = api_client.put(f"{BASE_URL}/api/posts/nonexistent-post-id/status", json={
            "status": "posted"
        })
        assert response.status_code == 404
        print("✓ 404 returned for updating status of nonexistent post")
    
    def test_delete_post_and_verify(self, api_client, test_profile_id):
        """Test DELETE /api/posts/{post_id} removes post and verify with GET"""
        # Generate a post
        gen_response = api_client.post(f"{BASE_URL}/api/posts/generate", json={
            "profile_id": test_profile_id,
            "platform": "instagram"
        })
        post = gen_response.json()
        post_id = post["id"]
        
        # Get initial count
        get_before = api_client.get(f"{BASE_URL}/api/posts/{test_profile_id}")
        posts_before = get_before.json()
        count_before = len(posts_before)
        
        # Delete post
        delete_response = api_client.delete(f"{BASE_URL}/api/posts/{post_id}")
        assert delete_response.status_code == 200
        
        delete_data = delete_response.json()
        assert delete_data["deleted"] == True
        print(f"✓ Post deleted: {post_id}")
        
        # Verify deletion with GET
        get_after = api_client.get(f"{BASE_URL}/api/posts/{test_profile_id}")
        posts_after = get_after.json()
        count_after = len(posts_after)
        
        assert count_after == count_before - 1, "Post count should decrease by 1"
        
        # Verify post is not in list
        found = any(p["id"] == post_id for p in posts_after)
        assert not found, "Deleted post should not appear in GET response"
        print("✓ Post deletion verified")
    
    def test_delete_nonexistent_post(self, api_client):
        """Test DELETE /api/posts/{invalid_id} returns 404"""
        response = api_client.delete(f"{BASE_URL}/api/posts/nonexistent-post-id")
        assert response.status_code == 404
        print("✓ 404 returned for deleting nonexistent post")


class TestFollowerTracking:
    """Follower tracking endpoints - POST follower count, GET follower history"""
    
    def test_add_follower_count_and_verify(self, api_client, test_profile_id):
        """Test POST /api/followers adds follower count and verify with GET"""
        # Add first follower count
        follower_payload = {
            "profile_id": test_profile_id,
            "count": 100
        }
        
        add_response = api_client.post(f"{BASE_URL}/api/followers", json=follower_payload)
        assert add_response.status_code == 200
        
        added_entry = add_response.json()
        assert added_entry["profile_id"] == test_profile_id
        assert added_entry["count"] == 100
        assert "date" in added_entry
        assert "id" in added_entry
        
        print(f"✓ Follower count added: {added_entry['count']} on {added_entry['date']}")
        
        # Verify persistence with GET
        get_response = api_client.get(f"{BASE_URL}/api/followers/{test_profile_id}")
        assert get_response.status_code == 200
        
        entries = get_response.json()
        assert isinstance(entries, list)
        assert len(entries) >= 1
        
        # Find our entry
        found = any(e["count"] == 100 for e in entries)
        assert found, "Added follower count not found in GET response"
        print(f"✓ Follower count retrieved and verified")
    
    def test_update_follower_count_same_day(self, api_client, test_profile_id):
        """Test POST /api/followers updates count if same day entry exists"""
        # Add initial count
        api_client.post(f"{BASE_URL}/api/followers", json={
            "profile_id": test_profile_id,
            "count": 150
        })
        
        # Update count for same day
        update_response = api_client.post(f"{BASE_URL}/api/followers", json={
            "profile_id": test_profile_id,
            "count": 175
        })
        assert update_response.status_code == 200
        
        updated_entry = update_response.json()
        assert updated_entry["count"] == 175
        print(f"✓ Follower count updated for same day: {updated_entry['count']}")
        
        # Verify only one entry for today
        get_response = api_client.get(f"{BASE_URL}/api/followers/{test_profile_id}")
        entries = get_response.json()
        
        today_entries = [e for e in entries if e["date"] == updated_entry["date"]]
        assert len(today_entries) == 1, "Should only have one entry per day"
        assert today_entries[0]["count"] == 175
        print("✓ Same-day update verified (no duplicate entries)")
    
    def test_get_follower_history_sorted(self, api_client, test_profile_id):
        """Test GET /api/followers/{profile_id} returns entries sorted by date ascending"""
        get_response = api_client.get(f"{BASE_URL}/api/followers/{test_profile_id}")
        assert get_response.status_code == 200
        
        entries = get_response.json()
        assert isinstance(entries, list)
        
        if len(entries) > 1:
            # Verify sorted ascending (oldest first)
            for i in range(len(entries) - 1):
                assert entries[i]["date"] <= entries[i+1]["date"], "Entries should be sorted by date ascending"
            print(f"✓ Follower history sorted correctly (oldest first)")
            print(f"  Total entries: {len(entries)}")
        else:
            print(f"✓ Follower history retrieved ({len(entries)} entries)")
    
    def test_add_follower_count_missing_profile_id(self, api_client):
        """Test POST /api/followers returns 400 if profile_id missing"""
        invalid_payload = {
            "count": 100
        }
        
        response = api_client.post(f"{BASE_URL}/api/followers", json=invalid_payload)
        assert response.status_code == 400
        print("✓ 400 returned for missing profile_id")
    
    def test_get_follower_history_empty(self, api_client):
        """Test GET /api/followers/{profile_id} returns empty list for profile with no entries"""
        response = api_client.get(f"{BASE_URL}/api/followers/nonexistent-profile-12345")
        assert response.status_code == 200
        
        entries = response.json()
        assert isinstance(entries, list)
        assert len(entries) == 0
        print("✓ Empty list returned for profile with no follower entries")


class TestReminders:
    """Reminder creation and retrieval tests"""
    
    def test_create_reminder_and_verify(self, api_client, test_profile_id):
        """Test POST /api/reminders creates/updates reminder and verify with GET"""
        reminder_payload = {
            "profile_id": test_profile_id,
            "morning_time": "8:30 AM",
            "evening_time": "7:30 PM",
            "enabled": True
        }
        
        # Create reminder
        create_response = api_client.post(f"{BASE_URL}/api/reminders", json=reminder_payload)
        assert create_response.status_code == 200
        
        created_reminder = create_response.json()
        assert created_reminder["profile_id"] == test_profile_id
        assert created_reminder["morning_time"] == "8:30 AM"
        assert created_reminder["evening_time"] == "7:30 PM"
        assert created_reminder["enabled"] == True
        assert "id" in created_reminder
        
        print(f"✓ Reminder created for profile {test_profile_id}")
        
        # Verify persistence with GET
        get_response = api_client.get(f"{BASE_URL}/api/reminders/{test_profile_id}")
        assert get_response.status_code == 200
        
        retrieved_reminder = get_response.json()
        assert retrieved_reminder["profile_id"] == test_profile_id
        assert retrieved_reminder["morning_time"] == "8:30 AM"
        assert retrieved_reminder["evening_time"] == "7:30 PM"
        assert retrieved_reminder["enabled"] == True
        print("✓ Reminder retrieved and verified")
    
    def test_update_reminder(self, api_client, test_profile_id):
        """Test POST /api/reminders updates existing reminder"""
        # First create
        initial_payload = {
            "profile_id": test_profile_id,
            "morning_time": "9:00 AM",
            "evening_time": "8:00 PM",
            "enabled": True
        }
        api_client.post(f"{BASE_URL}/api/reminders", json=initial_payload)
        
        # Update
        update_payload = {
            "profile_id": test_profile_id,
            "morning_time": "7:00 AM",
            "evening_time": "6:00 PM",
            "enabled": False
        }
        
        update_response = api_client.post(f"{BASE_URL}/api/reminders", json=update_payload)
        assert update_response.status_code == 200
        
        updated_reminder = update_response.json()
        assert updated_reminder["morning_time"] == "7:00 AM"
        assert updated_reminder["evening_time"] == "6:00 PM"
        assert updated_reminder["enabled"] == False
        
        print("✓ Reminder updated successfully")
        
        # Verify with GET
        get_response = api_client.get(f"{BASE_URL}/api/reminders/{test_profile_id}")
        verified = get_response.json()
        assert verified["morning_time"] == "7:00 AM"
        print("✓ Update persisted correctly")
    
    def test_get_reminder_for_nonexistent_profile(self, api_client):
        """Test GET /api/reminders/{invalid_id} returns default values"""
        response = api_client.get(f"{BASE_URL}/api/reminders/nonexistent-id-12345")
        assert response.status_code == 200
        
        reminder = response.json()
        assert reminder["profile_id"] == "nonexistent-id-12345"
        assert reminder["enabled"] == False
        print("✓ Default reminder returned for nonexistent profile")


# Fixtures
@pytest.fixture(scope="session")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="session")
def test_profile_id(api_client):
    """Create a test profile for use across tests"""
    create_payload = {
        "display_name": "TEST_SharedProfile",
        "handles": {
            "instagram": "test_shared_insta",
            "tiktok": "test_shared_tiktok",
            "twitter": "test_shared_x"
        }
    }
    
    response = api_client.post(f"{BASE_URL}/api/profiles", json=create_payload)
    profile = response.json()
    profile_id = profile["id"]
    
    # Analyze the profile for post generation tests
    api_client.post(f"{BASE_URL}/api/profiles/{profile_id}/analyze")
    
    print(f"\n=== Created shared test profile: {profile_id} ===\n")
    return profile_id
