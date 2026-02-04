import httpx
import time
import uuid

BASE_URL = "http://localhost:8000"

def run_test():
    with httpx.Client(base_url=BASE_URL, timeout=10.0) as client:
        print("🚀 Starting Social Flow Test...")
        
        # 1. Register
        username = f"user_{uuid.uuid4().hex[:6]}"
        password = "password123"
        print(f"👤 Registering user: {username}...")
        
        resp = client.post("/auth/register", json={
            "username": username,
            "nickname": "Test Critic",
            "password": password
        })
        if resp.status_code == 201:
            print(f"✅ Registered: {resp.json()['username']}")
        else:
            print(f"❌ Registration failed: {resp.text}")
            return

        # 2. Login
        print("🔑 Logging in...")
        resp = client.post("/auth/login", data={
            "username": username,
            "password": password
        })
        if resp.status_code == 200:
            token = resp.json()["access_token"]
            print(f"✅ Login successful. Token obtained.")
        else:
            print(f"❌ Login failed: {resp.text}")
            return
            
        auth_headers = {"Authorization": f"Bearer {token}"}
        
        # 3. Get a Movie ID
        print("🎬 Searching for a movie...")
        resp = client.post("/search", json={"query": "horror", "limit": 1})
        if resp.status_code == 200 and resp.json()["results"]:
            movie_id = resp.json()["results"][0]["movie_id"]
            movie_title = resp.json()["results"][0]["title"]
            print(f"✅ Found movie: {movie_title} ({movie_id})")
        else:
            print("❌ Search failed or no results.")
            return

        # 4. Post Review
        print("📝 Posting review...")
        review_content = "This is a test review. Best social app ever!"
        resp = client.post(f"/movies/{movie_id}/reviews", json={
            "content": review_content,
            "rating": 5.0
        }, headers=auth_headers)
        
        if resp.status_code == 200:
            review_data = resp.json()
            review_id = review_data["id"]
            print(f"✅ Review posted! ID: {review_id}")
            print(f"   Content: {review_data['content']}")
        else:
            print(f"❌ Review failed: {resp.text}")
            return

        # 5. Like Review
        print("❤️ Liking the review...")
        resp = client.post(f"/reviews/{review_id}/like", headers=auth_headers)
        if resp.status_code == 200:
            print(f"✅ Like toggled. Valid: {resp.json().get('status') == 'success'}")
            print(f"   Action: {resp.json().get('action')}")
        else:
            print(f"❌ Like failed: {resp.text}")
            return
            
        print("\n🎉 All social tests passed!")

if __name__ == "__main__":
    run_test()
