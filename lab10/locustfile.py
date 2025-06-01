from locust import HttpUser, task, between
import random

class LibraryUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        """Реєстрація та логін нового користувача"""
        random_id = random.randint(1000, 9999)
        self.email = f"test_user_{random_id}@example.com"
        self.password = "testpassword123"
        self.username = f"testuser_{random_id}"

        # Реєстрація
        user_data = {
            "email": self.email,
            "username": self.username,
            "password": self.password
        }
        reg_response = self.client.post("/api/auth/register", json=user_data)
        print("Register:", reg_response.status_code, reg_response.text)

        # Логін
        login_data = {
            "email": self.email,
            "password": self.password
        }
        login_response = self.client.post("/api/auth/login", json=login_data)
        print("Login:", login_response.status_code, login_response.text)

        if login_response.status_code == 200:
            try:
                token_data = login_response.json()
                access_token = token_data.get("access_token")
                if access_token:
                    self.client.headers.update({
                        "Authorization": f"Bearer {access_token}"
                    })
                    print("Token OK")
                else:
                    print("Token not found in login response.")
            except Exception as e:
                print("Failed to parse token:", e)
        else:
            print("Login failed. Status:", login_response.status_code)

    @task
    def get_books(self):
        """Навантажувальний тест GET /api/books"""
        skip = random.randint(0, 50)
        limit = random.randint(5, 20)
        response = self.client.get(f"/api/books?skip={skip}&limit={limit}")
        print("Books:", response.status_code)
