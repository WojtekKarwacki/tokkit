from src.auth import AuthService
from src.user import UserService

def main():
    auth = AuthService()
    auth.authenticate("admin", "password")
    user_svc = UserService()
    user = user_svc.get_user(1)
    return user
