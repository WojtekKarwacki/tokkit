from src.auth import AuthService

def test_authenticate():
    svc = AuthService()
    assert svc.authenticate("admin", "password") == True

def test_logout():
    svc = AuthService()
    svc.logout()
